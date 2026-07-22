# security/policy.py
"""Loader and evaluator for the governance policy contract.

The rules live in policies/governance.yaml; this module only knows how to
read them and apply them. Keeping the two apart means a behaviour change is
a policy diff a reviewer can read, not a code change.

A rule's `when:` block may only reference predicates registered in
PREDICATES below — the policy is data, never code, so there is no path by
which editing the YAML executes anything.

A missing or malformed policy raises. That is deliberate: a governance layer
that silently allows everything when its own rules fail to load is worse
than one that refuses to start, and CI catches it via test_policy_contract.
Connectivity degradation (DataHub unreachable) is a different thing entirely
and is handled *inside* the policy by the no_metadata rule.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "policies" / "governance.yaml"

# allow < warn < block
SEVERITY = {"allow": 0, "warn": 1, "block": 2}


class PolicyError(RuntimeError):
    """Raised when the policy contract is missing, malformed, or inconsistent."""


SUPPORTED_REMEDIATIONS = {"successor_lookup"}


@dataclass
class Rule:
    id: str
    reason_code: str
    when: Dict[str, Any]
    verdict: str
    tier: str
    message: str
    notify_owners: bool = False
    remediation: str = ""   # name of a remediation strategy, or "" for none


@dataclass
class Policy:
    version: str
    rules: List[Rule]
    tiers: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    sensitive_tags: List[str] = field(default_factory=list)
    pii_tags: List[str] = field(default_factory=list)

    def downgradable(self, tier: str) -> bool:
        return bool(self.tiers.get(tier, {}).get("downgradable", True))

    @property
    def reason_codes(self) -> List[str]:
        return [r.reason_code for r in self.rules]


# ----------------------------------------------------------------------
# Predicates — the complete vocabulary available to a rule's `when:` block
# ----------------------------------------------------------------------

def _tags(context) -> List[str]:
    return [t.lower() for t in getattr(context, "tags", []) or []]


def _matched_sensitive(context, policy: Policy) -> List[str]:
    return [t for t in _tags(context) if t in policy.sensitive_tags]


PREDICATES: Dict[str, Callable[[Any, Any, "_Env"], bool]] = {
    # key: (context, expected_value, env) -> bool
    "metadata": lambda ctx, expected, env: (
        (ctx is None) if expected == "absent" else (ctx is not None)
    ),
    "deprecated": lambda ctx, expected, env: (
        ctx is not None and bool(getattr(ctx, "deprecated", False)) is bool(expected)
    ),
    "assertions_passing": lambda ctx, expected, env: (
        ctx is not None and getattr(ctx, "assertions_passing", None) is expected
    ),
    "has_sensitive_tag": lambda ctx, expected, env: (
        ctx is not None
        and bool(_matched_sensitive(ctx, env.policy)) is bool(expected)
    ),
    "has_pii_tag": lambda ctx, expected, env: (
        ctx is not None
        and any(t in env.policy.pii_tags for t in _tags(ctx)) is bool(expected)
    ),
    "dlp_enabled": lambda ctx, expected, env: env.dlp_enabled is bool(expected),
}


@dataclass
class _Env:
    """Evaluation inputs that are not part of the dataset context."""
    policy: Policy
    dlp_enabled: bool


# ----------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------

def load_policy(path: Optional[os.PathLike | str] = None) -> Policy:
    """Parse and validate the policy contract."""
    path = Path(path or os.environ.get("GUARDRAIL_POLICY_PATH") or DEFAULT_POLICY_PATH)
    if not path.exists():
        raise PolicyError(f"governance policy not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise PolicyError(f"governance policy is not valid YAML: {e}") from e

    version = str(raw.get("version") or "").strip()
    if not version:
        raise PolicyError("governance policy is missing a version")

    rules: List[Rule] = []
    seen_ids, seen_codes = set(), set()
    for i, item in enumerate(raw.get("rules") or []):
        missing = {"id", "reason_code", "when", "verdict", "tier"} - set(item)
        if missing:
            raise PolicyError(f"rule #{i} is missing keys: {sorted(missing)}")
        if item["verdict"] not in SEVERITY:
            raise PolicyError(
                f"rule '{item['id']}' has unknown verdict '{item['verdict']}'")
        unknown = set(item["when"]) - set(PREDICATES)
        if unknown:
            raise PolicyError(
                f"rule '{item['id']}' uses unknown predicates: {sorted(unknown)}")
        if item["id"] in seen_ids:
            raise PolicyError(f"duplicate rule id '{item['id']}'")
        if item["reason_code"] in seen_codes:
            raise PolicyError(f"duplicate reason_code '{item['reason_code']}'")
        seen_ids.add(item["id"])
        seen_codes.add(item["reason_code"])
        remediation = item.get("remediation", "") or ""
        if remediation and remediation not in SUPPORTED_REMEDIATIONS:
            raise PolicyError(
                f"rule '{item['id']}' requests unknown remediation "
                f"'{remediation}'; supported: {sorted(SUPPORTED_REMEDIATIONS)}")
        rules.append(Rule(
            id=item["id"], reason_code=item["reason_code"], when=item["when"],
            verdict=item["verdict"], tier=item["tier"],
            message=item.get("message", item["reason_code"]),
            notify_owners=bool(item.get("notify_owners", False)),
            remediation=remediation,
        ))

    if not rules:
        raise PolicyError("governance policy defines no rules")

    policy = Policy(
        version=version, rules=rules, tiers=raw.get("tiers") or {},
        sensitive_tags=[t.lower() for t in raw.get("sensitive_tags") or []],
        pii_tags=[t.lower() for t in raw.get("pii_tags") or []],
    )

    unknown_tiers = {r.tier for r in rules} - set(policy.tiers)
    if unknown_tiers:
        raise PolicyError(f"rules reference undeclared tiers: {sorted(unknown_tiers)}")
    return policy


_cached: Optional[Policy] = None


def get_policy(reload: bool = False) -> Policy:
    """Process-wide policy singleton."""
    global _cached
    if _cached is None or reload:
        _cached = load_policy()
    return _cached


# ----------------------------------------------------------------------
# Evaluation
# ----------------------------------------------------------------------

def _render(rule: Rule, context, policy: Policy) -> str:
    owners = ", ".join(getattr(context, "owners", []) or []) or "unknown"
    matched = ", ".join(_matched_sensitive(context, policy)) if context else ""
    try:
        return rule.message.format(owners=owners, matched_sensitive_tags=matched,
                                   name=getattr(context, "name", ""))
    except (KeyError, IndexError):
        # a malformed placeholder must not take the guardrail down
        return rule.message


@dataclass
class Evaluation:
    action: str
    reasons: List[str]
    reason_codes: List[str]
    policy_version: str
    notify_owners: bool = False
    remediations: List[str] = field(default_factory=list)  # strategies the policy asked for


def evaluate(context, dlp_enabled: bool = True, mode: str = "warn",
             policy: Optional[Policy] = None) -> Evaluation:
    """Apply the policy to one dataset context. Pure: no I/O, no globals."""
    policy = policy or get_policy()
    env = _Env(policy=policy, dlp_enabled=dlp_enabled)

    if mode == "off":
        # Explicit operator kill switch. Recorded so the bypass is auditable.
        return Evaluation("allow", ["guardrail disabled"], ["guardrail_off"],
                          policy.version)

    action, reasons, codes, notify = "allow", [], [], False
    remediations: List[str] = []
    for rule in policy.rules:
        if not all(PREDICATES[key](context, expected, env)
                   for key, expected in rule.when.items()):
            continue

        verdict = rule.verdict
        if (verdict == "block" and mode != "enforce"
                and policy.downgradable(rule.tier)):
            verdict = "warn"

        reasons.append(_render(rule, context, policy))
        codes.append(rule.reason_code)
        notify = notify or rule.notify_owners
        if rule.remediation and rule.remediation not in remediations:
            remediations.append(rule.remediation)
        if SEVERITY[verdict] > SEVERITY[action]:
            action = verdict

    return Evaluation(action, reasons, codes, policy.version, notify,
                      remediations)
