"""Golden-case regression suite for the governance policy.

Two things run here:

1. Every case in tests/golden/*.yaml is replayed against the shipped policy.
   Cases are the memory of the system — a verdict a human judged wrong becomes
   a fixture so the same mistake cannot come back.
2. A coverage gate. Adding a rule to policies/governance.yaml without adding a
   case for it fails the build, which is what keeps (1) honest over time.
"""
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from security.governance_bridge import decide
from security.policy import PolicyError, get_policy, load_policy
from tools.datahub_mcp_tool import DatasetContext

GOLDEN_DIR = Path(__file__).parent / "golden"
DEFAULT_URN = "urn:li:dataset:(urn:li:dataPlatform:pg,{name},PROD)"


def _load_cases():
    cases = []
    for path in sorted(GOLDEN_DIR.glob("*.yaml")):
        for case in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            case["_file"] = path.name
            cases.append(case)
    return cases


CASES = _load_cases()


def _context(spec):
    """Build a DatasetContext from a fixture; None means 'DataHub had no answer'."""
    if spec is None:
        return None
    spec = dict(spec)
    name = spec.pop("name", "t")
    return DatasetContext(urn=spec.pop("urn", DEFAULT_URN.format(name=name)),
                          name=name, **spec)


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_golden_case(case):
    expect = case["expect"]
    verdict = decide(_context(case["dataset"]),
                     dlp_enabled=case.get("dlp_enabled", True),
                     mode=str(case.get("mode", "warn")))

    assert verdict.action == expect["verdict"], (
        f"{case['name']}: expected {expect['verdict']}, got {verdict.action} "
        f"({verdict.reasons})")
    # order matters: reasons are reported in policy order
    assert verdict.reason_codes == expect["reason_codes"], case["name"]
    if "notify_owners" in expect:
        assert verdict.notify_owners is expect["notify_owners"], case["name"]
    # every verdict must carry the policy version that produced it
    assert verdict.policy_version, case["name"]
    # one human-readable reason per code, so the audit log is never bare
    assert len(verdict.reasons) == len(verdict.reason_codes), case["name"]


def test_golden_suite_is_not_empty():
    assert len(CASES) >= 10, "golden suite has been gutted"


def test_case_names_are_unique():
    names = [c["name"] for c in CASES]
    assert len(names) == len(set(names)), "duplicate golden case names"


# ----------------------------------------------------------------------
# Coverage gate — the part that keeps the suite honest
# ----------------------------------------------------------------------

def test_every_reason_code_has_a_golden_case():
    """A new policy rule without a golden case fails the build."""
    covered = {code for c in CASES for code in c["expect"]["reason_codes"]}
    declared = set(get_policy().reason_codes)
    missing = declared - covered
    assert not missing, (
        f"policy reason codes with no golden case: {sorted(missing)} — "
        f"add a case to tests/golden/ before merging the rule")


def test_every_verdict_type_is_exercised():
    seen = {}
    for c in CASES:
        seen[c["expect"]["verdict"]] = seen.get(c["expect"]["verdict"], 0) + 1
    for verdict in ("allow", "warn", "block"):
        assert seen.get(verdict, 0) >= 2, (
            f"verdict '{verdict}' has {seen.get(verdict, 0)} cases, need >= 2")


def test_golden_cases_reference_real_reason_codes():
    """Guards against a typo'd expectation silently passing forever."""
    declared = set(get_policy().reason_codes) | {"guardrail_off"}
    for c in CASES:
        unknown = set(c["expect"]["reason_codes"]) - declared
        assert not unknown, f"{c['name']} expects unknown codes: {sorted(unknown)}"


# ----------------------------------------------------------------------
# The policy contract itself
# ----------------------------------------------------------------------

def test_shipped_policy_loads_and_validates():
    policy = load_policy()
    assert policy.version
    assert policy.rules
    assert "catastrophic" in policy.tiers


def test_catastrophic_tier_is_not_downgradable():
    """The property that makes the guardrail load-bearing."""
    policy = get_policy()
    assert policy.downgradable("catastrophic") is False
    assert any(r.tier == "catastrophic" for r in policy.rules)


def test_malformed_policy_raises_rather_than_allowing_everything(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: '1.0'\nrules:\n  - id: x\n", encoding="utf-8")
    with pytest.raises(PolicyError):
        load_policy(bad)


def test_policy_rejects_unknown_predicates(tmp_path):
    """The policy is data: it may only use predicates the evaluator implements."""
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "version: '1.0'\n"
        "tiers: {serious: {downgradable: true}}\n"
        "rules:\n"
        "  - {id: x, reason_code: x, verdict: warn, tier: serious, "
        "when: {os_system: 'rm -rf /'}}\n",
        encoding="utf-8")
    with pytest.raises(PolicyError, match="unknown predicates"):
        load_policy(bad)


def test_missing_policy_file_raises(tmp_path):
    with pytest.raises(PolicyError):
        load_policy(tmp_path / "nope.yaml")
