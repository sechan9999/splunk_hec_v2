# datahub-agent Design Document

> **Summary**: DataHub as the metadata brain of the closed agent-ops loop — MCP tool, pre-flight guardrails, governance write-back, and a Data Context tab.
>
> **Project**: splunk_hec_v2 (Agentic Ops Control Center)
> **Version**: v2 (post commit 2c2ae53)
> **Author**: sechan9999
> **Date**: 2026-07-07
> **Status**: Draft
> **Planning Doc**: [datahub-agent.plan.md](../../01-plan/features/datahub-agent.plan.md)

---

## 1. Overview

### 1.1 Design Goals

1. Make DataHub a **decision input** for the agent (guardrails) and a **decision record** (governance write-back) — not a decorative search tool. This is what "DataHub as the foundation" must mean for judging.
2. Zero regressions in the existing platform when DataHub is absent (env-gated, same policy as the Splunk layer).
3. Demo Mode parity: every DataHub feature works fully simulated on Streamlit Cloud.

### 1.2 Design Principles

- **Mirror the Splunk pattern**: `DataHubMCPTool` follows `tools/splunk_mcp_tool.py` (NL keyword map -> query templates -> MCP-first / REST-fallback client); `DataHubPlugin` follows `SplunkPlugin` in `tool_manager.py`.
- **Graceful degradation**: every integration point wrapped in try/except; missing `DATAHUB_GMS_URL` disables the layer silently.
- **One new concept per layer**: agent gets one new tool (`datahub_query`) plus one interceptor (guardrail); UI gets one new tab.

---

## 2. Architecture

### 2.1 Component Diagram

```
                       ┌────────────────────────────┐
  User query ────────▶ │  AdvancedMCPAgent          │
                       │  (tool loop, max 20 steps) │
                       └──────┬──────────┬──────────┘
             ① datahub_query  │          │  ② guardrail pre-flight
                              ▼          ▼
                  ┌──────────────────┐  ┌─────────────────────────┐
                  │ DataHubMCPTool   │  │ MetadataGuardrail        │
                  │ NL → entity/     │  │ before data-tool calls:  │
                  │ lineage/owner    │  │ deprecated? failing      │
                  │ MCP ▸ GraphQL FB │  │ assertions? PII-tagged?  │
                  └────────┬─────────┘  └───────────┬─────────────┘
                           │                        │ verdict: allow /
                           ▼                        ▼ warn / block
                  ┌─────────────────────────────────────────────┐
                  │              DataHub (GMS)                  │
                  │  context graph · ownership · lineage ·      │
                  │  assertions · tags                          │
                  └───────────────────▲─────────────────────────┘
                                      │ ③ write-back (tags/props)
                  ┌───────────────────┴─────────────────────────┐
                  │ GovernanceBridge                             │
                  │ DLP violation ──▶ tag `llmai:dlp-violation`  │
                  │ remediation  ──▶ dataset property + timeline │
                  └──────────────────────────────────────────────┘

  (Splunk loop unchanged: HEC telemetry, CDTS anomaly → /splunk/alert)
```

### 2.2 Data Flow (guardrail path — the core demo moment)

```
agent plans supabase_query("visitors")
  → MetadataGuardrail.check("visitors")
    → DataHubMCPTool.get_context(urn)          (cached 5 min/session)
      → verdict:
         allow  → tool runs; context attached to result
         warn   → tool runs; ⚠ shown in UI ("dataset deprecated, owner: x")
         block  → tool refused; agent reports why + owner to contact
  → GovernanceBridge.record(event)              (fire-and-forget)
  → HEC telemetry emits mcp_guardrail event     (Splunk loop sees it too)
```

### 2.3 Dependencies

| Component | Depends On | Purpose |
|-----------|-----------|---------|
| `tools/datahub_mcp_tool.py` | `acryl-datahub` SDK (optional) / raw GraphQL via requests | metadata queries |
| `security/governance_bridge.py` | `DataHubMCPTool` client | tag/property write-back |
| `advanced_agent.py` (small patch) | guardrail + tool registration | pre-flight check hook |
| `enterprise_mcp_connector/tool_manager.py` | `DataHubPlugin` | plugin registry entry |
| `demo_data.py` | none | simulated context graph |
| `demo_app.py` | `ui/components.py`, `demo_data.py` | Data Context tab |

New dependency policy: `acryl-datahub` goes in `requirements-full.txt` only; the demo app must not require it (Demo Mode simulates; live mode uses raw GraphQL over `requests`, already a dependency).

---

## 3. Data Model

### 3.1 Entity Definition

```python
# tools/datahub_mcp_tool.py
@dataclass
class DatasetContext:
    urn: str                    # urn:li:dataset:(urn:li:dataPlatform:postgres,visitors,PROD)
    name: str
    platform: str               # postgres / supabase / s3 ...
    owners: list[str]           # ["data-eng@corp"]
    deprecated: bool
    tags: list[str]             # ["pii", "gold", "llmai:dlp-violation"]
    assertions_passing: bool | None   # None = no assertions defined
    upstream: list[str]         # URNs, depth 1
    downstream: list[str]       # URNs, depth 1
    fetched_at: float           # epoch, for 5-min cache

@dataclass
class GuardrailVerdict:
    action: str                 # "allow" | "warn" | "block"
    reasons: list[str]          # ["dataset deprecated", "failing assertions"]
    context: DatasetContext | None
```

### 3.2 Guardrail Decision Table

| Condition (evaluated in order) | Verdict |
|---|---|
| DataHub unreachable / not configured | `allow` (degrade open — availability first, log it) |
| dataset `deprecated == True` | `block` |
| `assertions_passing == False` | `warn` |
| `"pii"` in tags AND DLP engine disabled | `warn` |
| otherwise | `allow` |

### 3.3 Write-back Schema

| Trigger | DataHub mutation | Value |
|---|---|---|
| DLP violation on dataset output | `addTag` | tag `llmai:dlp-violation`; property `llmai.last_dlp`: `{rule_id, severity, ts}` |
| Auto-remediation fired | `upsertStructuredProperties` | `llmai.last_remediation`: `{anomaly_type, action, ts}` |
| Guardrail block | `addTag` | tag `llmai:blocked-by-guardrail` (removed on next allow) |

GraphQL fallback mutations use DataHub's standard `addTag` / `upsertStructuredProperties` endpoints; MCP path uses the equivalent MCP tools when the server exposes them.

---

## 4. Tool Interface Specification

### 4.1 DataHubMCPTool methods (mirrors SplunkMCPTool)

| Method | Input | Output | Path |
|--------|-------|--------|------|
| `execute(nl_query)` | natural language | formatted answer + raw results | NL keyword map → method |
| `search_entities(q, type)` | text, entity type | list of URN + name + platform | MCP `search` ▸ GraphQL `search` |
| `get_context(urn)` | dataset URN | `DatasetContext` | MCP `get_entity` ▸ GraphQL |
| `get_lineage(urn, dir, depth=1)` | URN, up/down | URN list | MCP `lineage` ▸ GraphQL `scrollAcrossLineage` |
| `add_tag(urn, tag)` | URN, tag name | ok/err | GraphQL mutation |
| `upsert_property(urn, key, val)` | URN, key, json | ok/err | GraphQL mutation |

### 4.2 NL keyword map (initial)

| Keywords | Method |
|---|---|
| "who owns", "owner", "소유자" | `get_context` → owners |
| "lineage", "upstream", "downstream", "리니지" | `get_lineage` |
| "find", "search", "dataset", "테이블 찾" | `search_entities` |
| "quality", "assertion", "품질" | `get_context` → assertions |

### 4.3 Plugin registration

```python
# tool_manager.py — mirrors SplunkPlugin (lines ~258-293)
class DataHubPlugin(MCPServerPlugin):
    # methods: datahub_search, datahub_context, datahub_lineage
PLUGIN_REGISTRY["datahub"] = DataHubPlugin
```

### 4.4 Configuration

| Env var | Default | Meaning |
|---|---|---|
| `DATAHUB_GMS_URL` | "" (disabled) | GMS endpoint, e.g. http://localhost:8080 |
| `DATAHUB_TOKEN` | "" | PAT; sent as Bearer |
| `DATAHUB_MCP_URL` | "" | optional MCP server endpoint; empty → GraphQL only |
| `GUARDRAIL_MODE` | "warn" | "off" / "warn" / "enforce" (enforce enables block) |

---

## 5. UI/UX Design

### 5.1 New tab: "🧭 Data Context" (7th tab)

```
┌─ sec_header: Dataset Context — what the agent knows before it acts ─┐
│ [selectbox: dataset touched by agent]   [🎮 simulated badge]        │
│ ┌─────────────┬──────────────┬─────────────────┐                    │
│ │ Owner card  │ Quality card │ Guardrail card  │  (kpi-card style)  │
│ │ data-eng@   │ ✅ assertions│ ALLOW / WARN /  │                    │
│ │             │ passing      │ BLOCK + reason  │                    │
│ └─────────────┴──────────────┴─────────────────┘                    │
│ Lineage strip (plotly, reuse arch_diagram node style):              │
│   upstream ──▶ [dataset] ──▶ downstream                             │
│ Governance events table: ts · event · tag written · urn             │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Existing surfaces touched

| Surface | Change |
|---|---|
| Agent Lab tool-call expander | guardrail verdict line when a data tool ran (`🧭 guardrail: allow — owner data-eng@`) |
| Sidebar connections | add "DataHub GMS" row (5th service) to `connection_status` |
| Journey card #3 | mention DataHub in "Why Splunk matters" → retitle "Why Splunk + DataHub" |
| README / architecture diagram | add DataHub plane |

### 5.3 Demo Mode simulation (`demo_data.py`)

`gen_datahub_context()` returns 4-5 fake datasets (visitors, llm_costs, patients_pii, legacy_metrics-deprecated) with owners/tags/assertions arranged so each guardrail verdict (allow/warn/block) is demoable; `gen_governance_events()` returns recent write-back rows. Cached with `st.cache_data(ttl=60)`, RNG-stable.

---

## 6. Error Handling

| Failure | Behavior |
|---|---|
| GMS unreachable | tool returns `{"error": "...", "degraded": True}`; guardrail → `allow` + log; UI shows 🔴 in connections |
| Auth failure (401) | same as unreachable + hint "check DATAHUB_TOKEN" |
| MCP endpoint missing | silent fallback to GraphQL (parity with Splunk tool's MCP▸REST fallback) |
| Write-back failure | fire-and-forget with warning log; never breaks the agent loop |
| Unknown URN | `search_entities` first; if still unknown, guardrail `allow` with reason "unknown dataset" |

Error payload format matches `backend_client.safe_json` conventions.

---

## 7. Security Considerations

- [ ] `DATAHUB_TOKEN` via env / `st.secrets` only; never rendered in UI (password input in Advanced setup)
- [ ] TLS verify default on; reuse `BackendConfig.verify_ssl` policy
- [ ] Guardrail never sends row data to DataHub — metadata URNs only
- [ ] Write-back tags are namespaced `llmai:*` to avoid clobbering org tags
- [ ] `GUARDRAIL_MODE=enforce` documented as opt-in (blocking behavior changes agent output)

---

## 8. Test Plan

### 8.1 Test Scope

| Type | Target | Tool |
|------|--------|------|
| Unit | guardrail decision table (5 cases), NL keyword map | pytest (pure functions, no st) |
| Headless UI | Data Context tab renders, verdict badges, 5th connection row | AppTest (extend smoke suite) |
| Regression | existing 46 checks | AppTest |
| Live spike | search/context/lineage/add_tag against DataHub quickstart | manual, recorded |

### 8.2 Key Test Cases

- [ ] Happy path: agent query touches `visitors` → allow verdict shown in tool expander
- [ ] Block path: query touching `legacy_metrics` (deprecated) → blocked with owner in message
- [ ] Warn path: `patients_pii` with DLP off → warn
- [ ] Degradation: `DATAHUB_GMS_URL` unset → all 6 existing tabs unchanged, no new tab errors
- [ ] Write-back: DLP violation fires → governance event row appears (simulated)

---

## 9. Layer Assignment (project structure)

| Component | Layer | Location |
|-----------|-------|----------|
| `DataHubMCPTool`, `DataHubGraphQLClient` | Infrastructure | `tools/datahub_mcp_tool.py` |
| `MetadataGuardrail` | Application | `security/governance_bridge.py` |
| `GovernanceBridge` (write-back) | Application | `security/governance_bridge.py` |
| `DataHubPlugin` | Infrastructure | `enterprise_mcp_connector/tool_manager.py` |
| `gen_datahub_context`, `gen_governance_events` | Demo data | `demo_data.py` |
| Data Context tab | Presentation | `demo_app.py` + `ui/components.py` |

Dependency rule kept: `demo_app.py` never imports `tools/` directly — live calls go through the FastAPI backend or `backend_client`, simulation through `demo_data`.

---

## 10. Conventions

| Item | Convention Applied |
|------|-------------------|
| Naming | snake_case functions, PascalCase classes (existing codebase) |
| Comments | minimal; ASCII-safe in new files (encoding hygiene) |
| Commits | conventional commits, ≤50-char subject |
| Env vars | `DATAHUB_*`, `GUARDRAIL_MODE` documented in `.env.example` |
| Degradation | env-gated init + try/except (established platform policy) |

---

## 11. Implementation Guide

### 11.1 Implementation Order

1. [ ] **Spike (0.5d)**: DataHub quickstart via docker; confirm GraphQL search/entity/lineage/addTag calls; note MCP server surface
2. [ ] `tools/datahub_mcp_tool.py` — client + `DatasetContext` + NL map (mirror splunk tool; unit tests for keyword map)
3. [ ] `security/governance_bridge.py` — `MetadataGuardrail` (decision table + cache) + `GovernanceBridge` write-back
4. [ ] `tool_manager.py` + `advanced_agent.py` patches — plugin registry + pre-flight hook (graceful-degradation gates)
5. [ ] `demo_data.py` — simulated context + governance events
6. [ ] `demo_app.py` / `ui/components.py` — Data Context tab, sidebar 5th connection, Agent Lab verdict line
7. [ ] AppTest extension + pytest for guardrail; full suite green
8. [ ] docker-compose `datahub` service + `.env.example`; README + architecture diagram update
9. [ ] Live-path evidence recording; <3-min video; Devpost submission

### 11.2 Cut Line (if time runs short)

Keep 1-6; cut lineage strip visual (5.1) and FR-05 timeline events; never cut guardrails or write-back (they are the judging story).

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-07-07 | Initial draft | sechan9999 |
