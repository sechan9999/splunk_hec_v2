"""Unit tests for the metadata guardrail decision table (design 3.2)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from security.governance_bridge import decide
from tools.datahub_mcp_tool import DataHubMCPTool, DatasetContext


def ctx(**kw):
    base = dict(urn="urn:li:dataset:(urn:li:dataPlatform:pg,t,PROD)", name="t")
    base.update(kw)
    return DatasetContext(**base)


def test_no_metadata_degrades_open():
    v = decide(None)
    assert v.action == "allow"
    assert "degrading open" in v.reasons[0]


def test_deprecated_blocks_in_enforce_mode():
    v = decide(ctx(deprecated=True, owners=["a@b"]), mode="enforce")
    assert v.action == "block"
    assert "a@b" in v.reasons[0]


def test_deprecated_downgrades_to_warn_in_warn_mode():
    v = decide(ctx(deprecated=True), mode="warn")
    assert v.action == "warn"


def test_failing_assertions_warn():
    v = decide(ctx(assertions_passing=False), mode="enforce")
    assert v.action == "warn"
    assert "assertions" in v.reasons[0]


def test_pii_with_dlp_off_warns():
    v = decide(ctx(tags=["PII", "gold"]), dlp_enabled=False)
    assert v.action == "warn"


def test_pii_with_dlp_on_allows():
    v = decide(ctx(tags=["pii"]), dlp_enabled=True)
    assert v.action == "allow"


def test_clean_dataset_allows():
    v = decide(ctx(tags=["gold"], assertions_passing=True))
    assert v.action == "allow"
    assert v.reasons == []


def test_mode_off_always_allows():
    v = decide(ctx(deprecated=True, assertions_passing=False), mode="off")
    assert v.action == "allow"


def test_nl_keyword_classification():
    tool = DataHubMCPTool.__new__(DataHubMCPTool)  # skip network init
    assert tool.classify("who owns the visitors table") == "owners"
    assert tool.classify("show upstream lineage of llm_costs") == "lineage"
    assert tool.classify("data quality of user_features") == "quality"
    assert tool.classify("find datasets about billing") == "search"
    assert tool.classify("anything else") == "search"


def test_unconfigured_tool_degrades():
    import os
    for var in ("DATAHUB_GMS_URL", "DATAHUB_TOKEN", "DATAHUB_MCP_URL"):
        os.environ.pop(var, None)
    tool = DataHubMCPTool()
    assert tool.configured is False
    result = tool.execute("who owns visitors")
    assert result["degraded"] is True
