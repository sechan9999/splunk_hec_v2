# security/governance_bridge.py
"""DataHub governance layer: pre-flight guardrails + write-back.

MetadataGuardrail — consulted BEFORE the agent runs a data tool.
Decision table (design 3.2), evaluated in order:

    DataHub unreachable / unconfigured  -> allow  (degrade open, log)
    dataset deprecated                  -> block  (warn unless GUARDRAIL_MODE=enforce)
    assertions failing                  -> warn
    'pii' tag AND DLP engine disabled   -> warn
    otherwise                           -> allow

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

logger = logging.getLogger(__name__)

CACHE_TTL_SEC = 300  # 5 minutes per design


@dataclass
class GuardrailVerdict:
    action: str                       # "allow" | "warn" | "block"
    reasons: List[str] = field(default_factory=list)
    context: Optional[object] = None  # DatasetContext | None

    def to_dict(self) -> Dict:
        return {
            "action": self.action,
            "reasons": self.reasons,
            "context": self.context.to_dict() if self.context else None,
        }


def decide(context, dlp_enabled: bool = True, mode: str = "warn") -> GuardrailVerdict:
    """Pure decision function (unit-testable, no I/O).

    context: DatasetContext or None (None = DataHub had no answer).
    mode: "off" | "warn" | "enforce".
    """
    if mode == "off":
        return GuardrailVerdict("allow", ["guardrail disabled"])
    if context is None:
        return GuardrailVerdict("allow", ["no metadata available - degrading open"])

    if context.deprecated:
        action = "block" if mode == "enforce" else "warn"
        return GuardrailVerdict(
            action,
            [f"dataset deprecated (owners: {', '.join(context.owners) or 'unknown'})"],
            context)
    if context.assertions_passing is False:
        return GuardrailVerdict("warn", ["failing quality assertions"], context)
    if "pii" in [t.lower() for t in context.tags] and not dlp_enabled:
        return GuardrailVerdict("warn", ["PII-tagged dataset with DLP disabled"],
                                context)
    return GuardrailVerdict("allow", [], context)


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
