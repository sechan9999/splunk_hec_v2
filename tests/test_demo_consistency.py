"""The demo graph must agree with the live policy engine.

The Streamlit demo ships precomputed verdicts so it can run without DataHub.
That is fine right up until the policy changes and the demo keeps showing the
old answer — at which point the demo is quietly misrepresenting the product.
This test pins the two together, so a policy edit that changes a verdict fails
the build until demo_data.py is updated with it.

It earned its place: the first run found patients_pii claiming a warn the
engine never produced.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from security.governance_bridge import decide
from tools.datahub_mcp_tool import DatasetContext

demo_data = pytest.importorskip("demo_data", reason="streamlit not installed")

# The demo narrates a fully governed environment: DLP on, guardrail enforcing.
DEMO_DLP_ENABLED = True
DEMO_MODE = "enforce"


def _contexts():
    raw = demo_data.gen_datahub_context
    raw = getattr(raw, "__wrapped__", raw)  # bypass st.cache_data
    return raw()


def _to_context(spec):
    fields = {k: v for k, v in spec.items()
              if k in DatasetContext.__dataclass_fields__}
    return DatasetContext(**fields)


CASES = sorted(_contexts().items())


@pytest.mark.parametrize("name,spec", CASES, ids=[n for n, _ in CASES])
def test_demo_verdict_matches_live_policy(name, spec):
    live = decide(_to_context(spec), dlp_enabled=DEMO_DLP_ENABLED,
                  mode=DEMO_MODE)
    claimed = spec["verdict"]

    assert claimed["action"] == live.action, (
        f"demo dataset '{name}' claims {claimed['action']} but the policy "
        f"returns {live.action} ({live.reasons}) — update demo_data.py")

    if "reason_codes" in claimed:
        assert claimed["reason_codes"] == live.reason_codes, (
            f"demo dataset '{name}' reason codes drifted from the policy")

    if "remediation" in claimed:
        want, got = claimed["remediation"], live.remediation
        if want is None:
            assert got is None, f"demo '{name}' should offer no successor"
        else:
            assert got is not None, f"demo '{name}' should offer a successor"
            assert want["suggested_dataset"] == got["suggested_dataset"], name
            assert want["basis"] == got["basis"], name


def test_demo_graph_covers_every_verdict_type():
    """A demo that only ever shows 'allow' proves nothing."""
    actions = {spec["verdict"]["action"] for _, spec in CASES}
    assert {"allow", "warn", "block"} <= actions, (
        f"demo graph only exercises {sorted(actions)}")


def test_demo_graph_shows_a_successor_redirect():
    """At least one block must demonstrate the block-becomes-redirect path."""
    redirects = [n for n, s in CASES
                 if (s["verdict"].get("remediation") or {}).get("suggested_dataset")]
    assert redirects, "no demo dataset demonstrates a successor suggestion"
