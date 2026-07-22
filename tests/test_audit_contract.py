"""Structural guarantees that must hold regardless of how the policy evolves.

These are the checks that block a merge unconditionally — not because a
verdict changed, but because the machinery that makes verdicts *accountable*
was weakened. A guardrail whose decisions cannot be reconstructed afterwards
is decoration, so removing the audit write-back or dropping the evidence a
verdict was based on has to fail the build even when every golden case still
passes.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from security.governance_bridge import (GovernanceBridge, GuardrailVerdict,
                                        decide)
from security.policy import get_policy
from tools.datahub_mcp_tool import DatasetContext


def ctx(**kw):
    base = dict(urn="urn:li:dataset:(urn:li:dataPlatform:pg,t,PROD)", name="t")
    base.update(kw)
    return DatasetContext(**base)


# ----------------------------------------------------------------------
# Every verdict must be reconstructable
# ----------------------------------------------------------------------

def test_verdict_payload_carries_evidence():
    payload = decide(ctx(deprecated=True, tags=["hipaa"]), mode="enforce").to_dict()
    assert "evidence" in payload, "verdict must ship the evidence it decided on"
    for key in ("urn", "tags_consulted", "quality_state", "deprecated",
                "checked_at", "metadata_age_sec"):
        assert key in payload["evidence"], f"evidence missing '{key}'"


def test_evidence_records_metadata_staleness():
    """The 5-minute cache means a verdict can rest on minutes-old metadata."""
    fresh = decide(ctx(deprecated=True, fetched_at=time.time() - 120),
                   mode="enforce")
    age = fresh.evidence()["metadata_age_sec"]
    assert age is not None and 119 <= age <= 125, (
        f"expected ~120s of staleness to be reported, got {age}")


def test_evidence_is_honest_when_metadata_is_absent():
    ev = decide(None).evidence()
    assert ev["urn"] is None and ev["metadata_age_sec"] is None


def test_every_verdict_states_the_policy_version_that_made_it():
    for kwargs in ({}, {"mode": "enforce"}, {"mode": "off"}):
        v = decide(ctx(deprecated=True), **kwargs)
        assert v.policy_version == get_policy().version


def test_suggestion_carries_both_exact_and_readable_identifiers():
    """The URN is what you query; the short name is what a human reads.

    Losing the URN makes the audit record ambiguous across platforms; showing
    it raw makes the UI unreadable. Both ship, and the short one must never
    just be the URN again.
    """
    urn = "urn:li:dataset:(urn:li:dataPlatform:bigquery,session_metrics_v2,PROD)"
    v = decide(ctx(name="session_metrics_v1", deprecated=True, downstream=[urn]),
               mode="enforce")
    fix = v.remediation
    assert fix is not None
    assert fix["suggested_dataset"] == urn, "exact identifier must survive"
    assert fix["display_name"] == "session_metrics_v2"
    assert "urn:li:" not in fix["display_name"], "display name is still a URN"


def test_display_name_passes_through_bare_names_unchanged():
    v = decide(ctx(deprecated=True,
                   deprecation_note="Use metrics_v2 instead."), mode="enforce")
    assert v.remediation["display_name"] == "metrics_v2"
    assert v.remediation["suggested_dataset"] == "metrics_v2"


def test_reasons_and_codes_stay_in_lockstep():
    """A code with no message is unreadable; a message with no code is untestable."""
    for context in (None, ctx(), ctx(deprecated=True, tags=["hipaa"]),
                    ctx(assertions_passing=False, tags=["pii"])):
        v = decide(context, dlp_enabled=False, mode="enforce")
        assert len(v.reasons) == len(v.reason_codes)


# ----------------------------------------------------------------------
# The write-back path must survive refactors
# ----------------------------------------------------------------------

def test_governance_bridge_still_records_blocks():
    bridge = GovernanceBridge(tool=None)  # unconfigured: no network, still audits
    event = bridge.record_block("urn:li:dataset:(x,y,PROD)", ["deprecated"])
    assert event["event"] == "guardrail_block"
    assert event["tag"] == GovernanceBridge.TAG_BLOCKED
    assert event["ts"] > 0
    assert bridge.events, "block must land in the in-process audit trail"


def test_audit_trail_survives_a_dead_datahub():
    """Write-back is fire-and-forget; losing DataHub must not lose the record."""
    class Exploding:
        configured = True

        def add_tag(self, *a, **kw):
            raise RuntimeError("GMS unreachable")

    bridge = GovernanceBridge(tool=Exploding())
    bridge.record_block("urn:li:dataset:(x,y,PROD)", ["deprecated"])
    assert len(bridge.events) == 1, (
        "the local audit trail must outlive a failed remote write")


def test_dlp_and_remediation_events_are_recorded():
    bridge = GovernanceBridge(tool=None)
    bridge.record_dlp_violation("urn:li:dataset:(x,y,PROD)", "rule-1", "high")
    bridge.record_remediation("urn:li:dataset:(x,y,PROD)", "spike", "throttle")
    kinds = {e["event"] for e in bridge.events}
    assert kinds == {"dlp_violation", "remediation"}


# ----------------------------------------------------------------------
# The kill switch must never be invisible
# ----------------------------------------------------------------------

def test_disabled_guardrail_is_still_recorded():
    v = decide(ctx(deprecated=True, tags=["hipaa"]), dlp_enabled=False,
               mode="off")
    assert v.action == "allow"
    assert v.reason_codes == ["guardrail_off"], (
        "a bypass must never be indistinguishable from a clean allow")


def test_catastrophic_rules_exist_and_cannot_be_downgraded():
    policy = get_policy()
    assert policy.downgradable("catastrophic") is False
    assert [r for r in policy.rules if r.tier == "catastrophic"], (
        "policy has no catastrophic rule left — the guardrail is advisory only")
