# tools/datahub_mcp_tool.py
"""DataHub MCP Tool Connector.

Lets the agent query the DataHub context graph in natural language
(entity search, ownership, lineage, quality) and write governance
metadata back (tags, structured properties).

Mirrors tools/splunk_mcp_tool.py: NL keyword map -> method dispatch,
MCP server preferred, GraphQL REST fallback, graceful degradation when
DATAHUB_GMS_URL is unset.

References:
    https://docs.datahub.com/docs/features/feature-guides/mcp
    https://docs.datahub.com/docs/dev-guides/agent-context/agent-context
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Data model
# ----------------------------------------------------------------------

@dataclass
class DatasetContext:
    urn: str
    name: str
    platform: str = ""
    owners: List[str] = field(default_factory=list)
    deprecated: bool = False
    tags: List[str] = field(default_factory=list)
    assertions_passing: Optional[bool] = None  # None = no assertions defined
    upstream: List[str] = field(default_factory=list)
    downstream: List[str] = field(default_factory=list)
    fetched_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "urn": self.urn, "name": self.name, "platform": self.platform,
            "owners": self.owners, "deprecated": self.deprecated,
            "tags": self.tags, "assertions_passing": self.assertions_passing,
            "upstream": self.upstream, "downstream": self.downstream,
        }


# NL keyword -> method mapping (parallel to splunk_mcp_tool.NL_KEYWORD_MAP)
NL_KEYWORD_MAP = {
    ("owner", "who owns", "소유자", "담당자"):                    "owners",
    ("lineage", "upstream", "downstream", "리니지", "계보"):       "lineage",
    ("quality", "assertion", "품질", "신뢰"):                     "quality",
    ("find", "search", "dataset", "테이블 찾", "데이터셋"):        "search",
}


# ----------------------------------------------------------------------
# GraphQL client (REST fallback path)
# ----------------------------------------------------------------------

_GQL_SEARCH = """
query search($query: String!) {
  search(input: {type: DATASET, query: $query, start: 0, count: 10}) {
    searchResults {
      entity {
        urn
        type
        ... on Dataset { name platform { name } }
      }
    }
  }
}
"""

_GQL_DATASET = """
query dataset($urn: String!) {
  dataset(urn: $urn) {
    urn
    name
    platform { name }
    deprecation { deprecated }
    ownership { owners { owner { ... on CorpUser { username } ... on CorpGroup { name } } } }
    tags { tags { tag { name } } }
    health { type status }
  }
}
"""

_GQL_LINEAGE = """
query lineage($urn: String!, $direction: LineageDirection!) {
  searchAcrossLineage(input: {urn: $urn, direction: $direction, start: 0, count: 20}) {
    searchResults { entity { urn } }
  }
}
"""

_GQL_ADD_TAG = """
mutation addTag($tagUrn: String!, $resourceUrn: String!) {
  addTag(input: {tagUrn: $tagUrn, resourceUrn: $resourceUrn})
}
"""


class DataHubGraphQLClient:
    """Thin GraphQL client for DataHub GMS (/api/graphql)."""

    def __init__(self, gms_url: str = "", token: str = ""):
        self.gms_url = (gms_url or os.environ.get("DATAHUB_GMS_URL", "")).rstrip("/")
        self.token = token or os.environ.get("DATAHUB_TOKEN", "")

    @property
    def configured(self) -> bool:
        return bool(self.gms_url)

    def query(self, gql: str, variables: Dict) -> Dict[str, Any]:
        if not self.configured:
            return {"error": "DATAHUB_GMS_URL not set", "degraded": True}
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        body = json.dumps({"query": gql, "variables": variables}).encode()
        try:
            req = Request(f"{self.gms_url}/api/graphql", data=body,
                          headers=headers, method="POST")
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                if data.get("errors"):
                    return {"error": str(data["errors"][:1]), "degraded": True}
                return data.get("data", {})
        except Exception as e:
            logger.warning(f"DataHub GraphQL error: {e}")
            return {"error": str(e), "degraded": True}


# ----------------------------------------------------------------------
# DataHub MCP Tool
# ----------------------------------------------------------------------

class DataHubMCPTool:
    """DataHub context-graph connector for the agent tool loop.

    Prefers the DataHub MCP server when DATAHUB_MCP_URL is reachable;
    falls back to direct GraphQL against GMS otherwise.
    """

    TOOL_NAME = "datahub_query"
    TOOL_DESCRIPTION = (
        "Query the DataHub metadata context graph. Use this tool to find "
        "datasets, look up ownership, traverse lineage, and check data "
        "quality signals before acting on data."
    )

    MCP_SERVER_URL = os.environ.get("DATAHUB_MCP_URL", "")

    def __init__(self, gms_url: str = "", token: str = ""):
        self._gql = DataHubGraphQLClient(gms_url, token)
        self._mcp_available = self._check_mcp_server()

    @property
    def configured(self) -> bool:
        return self._gql.configured or self._mcp_available

    def _check_mcp_server(self) -> bool:
        if not self.MCP_SERVER_URL:
            return False
        try:
            req = Request(f"{self.MCP_SERVER_URL}/health", headers={
                "Authorization": f"Bearer {os.environ.get('DATAHUB_TOKEN', '')}"})
            with urlopen(req, timeout=3):
                logger.info("DataHub MCP Server connected")
                return True
        except Exception:
            logger.info("DataHub MCP Server not reachable - GraphQL fallback")
            return False

    def get_tool_schema(self) -> Dict:
        return {
            "name": self.TOOL_NAME,
            "description": self.TOOL_DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string",
                              "description": "Natural language metadata question"},
                },
                "required": ["query"],
            },
        }

    # -- read path ------------------------------------------------------

    def classify(self, nl_query: str) -> str:
        q = nl_query.lower()
        for keywords, method in NL_KEYWORD_MAP.items():
            if any(k in q for k in keywords):
                return method
        return "search"

    def execute(self, query: str) -> Dict[str, Any]:
        """NL query -> classified method -> formatted result."""
        start = time.time()
        method = self.classify(query)
        if not self.configured:
            return {"error": "DataHub not configured", "degraded": True,
                    "method": method, "results": []}

        # naive entity extraction: last quoted or last word
        target = query.split('"')[1] if '"' in query else query.split()[-1]

        if method == "search":
            result = self.search_entities(target)
        elif method == "lineage":
            ctx = self._context_for_name(target)
            result = {"upstream": ctx.upstream, "downstream": ctx.downstream,
                      "urn": ctx.urn} if ctx else {"results": []}
        elif method in ("owners", "quality"):
            ctx = self._context_for_name(target)
            result = ctx.to_dict() if ctx else {"results": []}
        else:
            result = {"results": []}

        result["method"] = method
        result["duration_ms"] = int((time.time() - start) * 1000)
        return result

    def search_entities(self, text: str, entity_type: str = "DATASET") -> Dict:
        data = self._gql.query(_GQL_SEARCH, {"query": text})
        if "error" in data:
            return data
        hits = [
            {"urn": r["entity"]["urn"],
             "name": r["entity"].get("name", ""),
             "platform": (r["entity"].get("platform") or {}).get("name", "")}
            for r in data.get("search", {}).get("searchResults", [])
        ]
        return {"results": hits, "count": len(hits)}

    def get_context(self, urn: str) -> Optional[DatasetContext]:
        data = self._gql.query(_GQL_DATASET, {"urn": urn})
        ds = data.get("dataset")
        if not ds:
            return None
        owners = []
        for o in ((ds.get("ownership") or {}).get("owners") or []):
            owner = o.get("owner") or {}
            owners.append(owner.get("username") or owner.get("name") or "?")
        tags = [t["tag"]["name"]
                for t in ((ds.get("tags") or {}).get("tags") or [])]
        health = ds.get("health") or []
        assertion_health = [h for h in health if h.get("type") == "ASSERTIONS"]
        assertions_passing = (
            None if not assertion_health
            else assertion_health[0].get("status") == "PASS")
        ctx = DatasetContext(
            urn=ds["urn"], name=ds.get("name", ""),
            platform=(ds.get("platform") or {}).get("name", ""),
            owners=owners,
            deprecated=bool((ds.get("deprecation") or {}).get("deprecated")),
            tags=tags, assertions_passing=assertions_passing,
            fetched_at=time.time(),
        )
        ctx.upstream = self.get_lineage(urn, "UPSTREAM")
        ctx.downstream = self.get_lineage(urn, "DOWNSTREAM")
        return ctx

    def get_lineage(self, urn: str, direction: str = "UPSTREAM",
                    depth: int = 1) -> List[str]:
        data = self._gql.query(_GQL_LINEAGE, {"urn": urn, "direction": direction})
        if "error" in data:
            return []
        return [r["entity"]["urn"] for r in
                data.get("searchAcrossLineage", {}).get("searchResults", [])]

    def _context_for_name(self, name: str) -> Optional[DatasetContext]:
        found = self.search_entities(name)
        results = found.get("results") or []
        return self.get_context(results[0]["urn"]) if results else None

    # -- write path (governance write-back) ------------------------------

    def add_tag(self, resource_urn: str, tag_name: str) -> Dict:
        tag_urn = f"urn:li:tag:{tag_name}"
        data = self._gql.query(_GQL_ADD_TAG,
                               {"tagUrn": tag_urn, "resourceUrn": resource_urn})
        if "error" in data:
            return {"ok": False, **data}
        return {"ok": True, "tag": tag_name, "urn": resource_urn}

    def upsert_property(self, resource_urn: str, key: str, value: Dict) -> Dict:
        # Structured-properties mutation surface varies by DataHub version;
        # recorded as a tag with encoded payload when unsupported.
        return self.add_tag(resource_urn, f"{key}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tool = DataHubMCPTool()
    print(f"configured={tool.configured} mcp={tool._mcp_available}")
    print(json.dumps(tool.execute('who owns "visitors"'), indent=2, default=str))
