# security/governance_bridge.py
"""DataHub governance layer: pre-flight guardrails + write-back.

MetadataGuardrail — consulted BEFORE the agent runs a data tool. The rules
themselves live in policies/governance.yaml (loaded by security/policy.py),
so changing what the agent is allowed to do is a reviewable policy diff
rather than a code change. See that file for the decision table and for the
tier semantics that decide when a block may be downgraded to a warning.

GovernanceBridge — fire-and-forget write-back of DLP violations and
auto-remediation events to DataHub as namespaced llmai:* tags.

Both degrade to no-ops when DataHub is not configured; the base agent
must never break because of this layer.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from security.policy import evaluate as _evaluate_policy
from security.remediation import suggest_successor

logger = logging.getLogger(__name__)

CACHE_TTL_SEC = 300  # 5 minutes per design


@dataclass
class GuardrailVerdict:
    action: str                       # "allow" | "warn" | "block"
    reasons: List[str] = field(default_factory=list)
    context: Optional[object] = None  # DatasetContext | None
    reason_codes: List[str] = field(default_factory=list)
    policy_version: str = ""
    notify_owners: bool = False
    remediation: Optional[Dict] = None   # advisory next step, never auto-applied

    def evidence(self) -> Dict:
        """Self-contained record of what this verdict was decided on.

        A verdict that cannot be re-justified later is not an audit trail.
        `metadata_age_sec` matters because the guardrail caches contexts for
        five minutes: without it, a block and the metadata that produced it
        can be minutes apart with nothing saying so.
        """
        ctx = self.context
        if ctx is None:
            return {"urn": None, "tags_consulted": [], "quality_state": None,
                    "deprecated": None, "checked_at": None,
                    "metadata_age_sec": None}
        fetched_at = getattr(ctx, "fetched_at", 0.0) or 0.0
        return {
            "urn": getattr(ctx, "urn", None),
            "tags_consulted": list(getattr(ctx, "tags", []) or []),
            "quality_state": getattr(ctx, "assertions_passing", None),
            "deprecated": getattr(ctx, "deprecated", None),
            "checked_at": fetched_at or None,
            "metadata_age_sec": (round(time.time() - fetched_at, 3)
                                 if fetched_at else None),
        }

    def to_dict(self) -> Dict:
        return {
            "action": self.action,
            "reasons": self.reasons,
            "reason_codes": self.reason_codes,
            "policy_version": self.policy_version,
            "notify_owners": self.notify_owners,
            "remediation": self.remediation,
            "evidence": self.evidence(),
            "context": self.context.to_dict() if self.context else None,
        }


def decide(context, dlp_enabled: bool = True, mode: str = "warn",
           policy=None, catalog: Optional[List[str]] = None) -> GuardrailVerdict:
    """Pure decision function (unit-testable, no I/O).

    context: DatasetContext or None (None = DataHub had no answer).
    mode: "off" | "warn" | "enforce".
    policy: optional Policy override; defaults to the shipped contract.
    catalog: optional known dataset URNs, used only for the weakest
        successor-matching path (see security/remediation.py).

    Prose in `reasons` is for humans and may be reworded at any time —
    assert on `reason_codes` instead, which are part of the policy contract.
    """
    ev = _evaluate_policy(context, dlp_enabled=dlp_enabled, mode=mode,
                          policy=policy)

    remediation = None
    if "successor_lookup" in ev.remediations:
        suggestion = suggest_successor(context, catalog=catalog)
        remediation = suggestion.to_dict() if suggestion else None

    return GuardrailVerdict(ev.action, ev.reasons, context,
                            reason_codes=ev.reason_codes,
                            policy_version=ev.policy_version,
                            notify_owners=ev.notify_owners,
                            remediation=remediation)


class MetadataGuardrail:
    """Pre-flight metadata check with a per-instance 5-minute context cache."""

    def __init__(self, tool=None, dlp_enabled: bool = True):
        if tool is None:
            try:
                from tools.datahub_mcp_tool import DataHubMCPTool
                tool = DataHubMCPTool()
            except Exception as e:
                logger.warning(f"DataHub tool unavailable: {e}")
                tool = None
        self._tool = tool
        self._dlp_enabled = dlp_enabled
        self._cache: Dict[str, tuple] = {}

    @property
    def mode(self) -> str:
        return os.environ.get("GUARDRAIL_MODE", "warn").lower()

    def _get_context(self, dataset_name: str):
        cached = self._cache.get(dataset_name)
        if cached and time.time() - cached[1] < CACHE_TTL_SEC:
            return cached[0]
        ctx = None
        if self._tool is not None and getattr(self._tool, "configured", False):
            try:
                ctx = self._tool._context_for_name(dataset_name)
            except Exception as e:
                logger.warning(f"guardrail context lookup failed: {e}")
        self._cache[dataset_name] = (ctx, time.time())
        return ctx

    def check(self, dataset_name: str) -> GuardrailVerdict:
        ctx = self._get_context(dataset_name)
        verdict = decide(ctx, dlp_enabled=self._dlp_enabled, mode=self.mode)
        logger.info(f"guardrail[{dataset_name}] -> {verdict.action} "
                    f"{verdict.reasons}")
        return verdict


class GovernanceBridge:
    """Write agent security/ops events back into the DataHub context graph."""

    TAG_DLP = "llmai:dlp-violation"
    TAG_BLOCKED = "llmai:blocked-by-guardrail"

    def __init__(self, tool=None):
        if tool is None:
            try:
                from tools.datahub_mcp_tool import DataHubMCPTool
                tool = DataHubMCPTool()
            except Exception:
                tool = None
        self._tool = tool
        self.events: List[Dict] = []  # in-process audit trail (UI/telemetry)

    def _enabled(self) -> bool:
        return self._tool is not None and getattr(self._tool, "configured", False)

    def _record(self, event: Dict) -> Dict:
        event["ts"] = time.time()
        self.events.append(event)
        return event

    def record_dlp_violation(self, dataset_urn: str, rule_id: str,
                             severity: str) -> Dict:
        event = self._record({"event": "dlp_violation", "urn": dataset_urn,
                              "rule_id": rule_id, "severity": severity,
                              "tag": self.TAG_DLP})
        if self._enabled():
            try:
                self._tool.add_tag(dataset_urn, self.TAG_DLP)
            except Exception as e:
                logger.warning(f"DLP write-back failed (non-fatal): {e}")
        return event

    def record_remediation(self, dataset_urn: str, anomaly_type: str,
                           action: str) -> Dict:
        event = self._record({"event": "remediation", "urn": dataset_urn,
                              "anomaly_type": anomaly_type, "action": action,
                              "tag": "llmai:last-remediation"})
        if self._enabled():
            try:
                self._tool.upsert_property(dataset_urn, "llmai.last_remediation",
                                           {"anomaly_type": anomaly_type,
                                            "action": action})
            except Exception as e:
                logger.warning(f"remediation write-back failed (non-fatal): {e}")
        return event

    def record_block(self, dataset_urn: str, reasons: List[str]) -> Dict:
        event = self._record({"event": "guardrail_block", "urn": dataset_urn,
                              "reasons": reasons, "tag": self.TAG_BLOCKED})
        if self._enabled():
            try:
                self._tool.add_tag(dataset_urn, self.TAG_BLOCKED)
            except Exception as e:
                logger.warning(f"block write-back failed (non-fatal): {e}")
        return event


_guardrail: Optional[MetadataGuardrail] = None
_bridge: Optional[GovernanceBridge] = None


def get_guardrail() -> MetadataGuardrail:
    global _guardrail
    if _guardrail is None:
        _guardrail = MetadataGuardrail()
    return _guardrail


def get_governance_bridge() -> GovernanceBridge:
    global _bridge
    if _bridge is None:
        _bridge = GovernanceBridge()
    return _bridge
