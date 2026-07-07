# datahub-agent Planning Document

> **Summary**: Adapt the Agentic Ops Control Center for the "Build with DataHub: The Agent Hackathon" — add DataHub as the metadata brain of the closed observability/remediation loop.
>
> **Project**: splunk_hec_v2 (Agentic Ops Control Center)
> **Version**: v2 (post-refactor, commit b27f85a)
> **Author**: sechan9999
> **Date**: 2026-07-07
> **Status**: Draft

---

## 1. Overview

### 1.1 Purpose

Enter the **Build with DataHub: The Agent Hackathon** (deadline **2026-08-10 17:00 EDT**, $20,500 pool) by extending the existing closed-loop agent-ops platform with DataHub as a mandatory foundation. Target track: **"Production ML protection agents"** — our pitch: *an agent that watches its own cost/latency/DLP telemetry and consults DataHub metadata (ownership, lineage, quality signals) before acting or remediating.*

### 1.2 Background

- The v2 platform already implements the hard parts: agentic tool loop, telemetry emission, DLP scanning, anomaly-driven auto-remediation, and a polished Streamlit Control Center (live at https://splunkhec2.streamlit.app/).
- The hackathon **requires DataHub to be "the foundation"** — Splunk-only does not qualify. Judging criterion #1 is meaningful use of DataHub's **MCP Server**, **Agent Context Kit**, or Skills.
- Our architecture is MCP-native: `tools/splunk_mcp_tool.py` + `PLUGIN_REGISTRY` in `enterprise_mcp_connector/tool_manager.py` were built exactly for adding new MCP tool backends. DataHub integration follows the same pattern as the Week-2 Splunk MCP tool.
- Submission requirements already satisfied: Apache-2.0 ✅, public repo ✅, hosted demo ✅, screenshots ✅. Missing: DataHub integration, <3-min video.

### 1.3 Related Documents

- Hackathon rules: https://datahub.devpost.com/
- DataHub MCP Server guide: https://docs.datahub.com/docs/features/feature-guides/mcp
- DataHub Agent Context Kit: https://docs.datahub.com/docs/dev-guides/agent-context/agent-context
- Existing pattern to follow: `tools/splunk_mcp_tool.py`, `auto_remediation.py`, `security/soar_bridge.py`

---

## 2. Scope

### 2.1 In Scope

- [ ] **DataHub MCP tool** (`tools/datahub_mcp_tool.py`): NL → entity search / lineage / ownership queries via DataHub MCP Server, with GraphQL REST fallback (same dual-path design as the Splunk tool)
- [ ] **Metadata-aware guardrails**: before the agent runs a data tool (e.g., `supabase_query`), consult DataHub for the dataset's ownership, deprecation status, and quality signals; refuse/warn on deprecated or failing-quality datasets
- [ ] **Governance write-back**: DLP violations and auto-remediation events pushed to DataHub as tags/properties on the affected dataset (the context graph becomes the audit trail)
- [ ] **Control Center tab**: new "Data Context" tab (or extension of Mission Control) showing DataHub-sourced lineage/ownership for entities the agent touched — Demo Mode simulates it like everything else
- [ ] **Local DataHub quickstart** in docker-compose for the live path
- [ ] **Submission assets**: <3-min video, Devpost write-up, updated README/architecture diagram

### 2.2 Out of Scope

- Replacing Splunk — the Splunk loop stays; DataHub adds the *metadata* dimension (this differentiates the entry)
- DataHub Cloud-only features; target open-source DataHub quickstart
- Changes to the original v1 repo (frozen)
- Multi-tenant / production hardening beyond demo quality

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | `DataHubMCPTool.execute(nl_query)` returns entity search, schema, ownership, and lineage results via DataHub MCP Server; REST/GraphQL fallback when MCP unavailable | High | Pending |
| FR-02 | `DataHubPlugin` registered in `PLUGIN_REGISTRY["datahub"]`; agent can invoke `datahub_query` in its tool loop | High | Pending |
| FR-03 | Pre-flight guardrail: before executing a data tool, agent checks target dataset in DataHub (deprecated? failing assertions? owner?) and annotates or blocks the call | High | Pending |
| FR-04 | DLP violation → DataHub tag write-back (`dlp:violation`, severity, timestamp) on the affected dataset URN | High | Pending |
| FR-05 | Auto-remediation events recorded as DataHub dataset properties / timeline events | Medium | Pending |
| FR-06 | Demo Mode: simulated DataHub context (lineage graph, owners, quality) in `demo_data.py`, zero backend required — consistent with existing demo philosophy | High | Pending |
| FR-07 | Control Center surfaces DataHub context: lineage snippet, owner, quality badge per touched dataset | Medium | Pending |
| FR-08 | docker-compose service for DataHub quickstart + `.env` wiring (`DATAHUB_GMS_URL`, `DATAHUB_TOKEN`) | Medium | Pending |
| FR-09 | Devpost submission: <3-min video, description, architecture diagram updated with DataHub plane | High | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|----------|----------|-------------------|
| Graceful degradation | Base agent runs with zero regressions when DataHub absent (env-gated, try/except — same policy as Splunk layer) | AppTest suite passes without DataHub |
| Performance | Guardrail metadata lookup adds < 500ms per tool call (cached per-session) | timing log |
| Security | DataHub token via env/st.secrets only; TLS verify default on (reuse `backend_client` policy) | code review |
| Testing | AppTest smoke suite extended for new tab/flows; all checks pass | `smoke_test` run |
| License | All new code Apache-2.0 (hackathon requirement) | LICENSE unchanged |

---

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] All High-priority FRs implemented and demoable in Demo Mode on Streamlit Cloud
- [ ] Live path verified once against local DataHub quickstart (screenshot/recording as evidence)
- [ ] AppTest suite green (existing 46 checks + new DataHub checks)
- [ ] Devpost submission complete before 2026-08-10 17:00 EDT

### 4.2 Quality Criteria

- [ ] Judging criterion #1 satisfied: MCP Server used meaningfully (not decoratively) — guardrails + write-back, not just search
- [ ] Zero regressions in existing 6 tabs
- [ ] README + architecture diagram updated; video < 3 min on YouTube

---

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| DataHub quickstart heavy to run locally (multiple containers) | Medium | High | Demo Mode simulation is the primary demo path (proven strategy from Splunk hackathon); live path recorded once for evidence |
| MCP Server API surface changes / docs gaps | Medium | Medium | Dual path: Agent Context Kit SDK bundling as fallback to MCP server connection |
| "DataHub as foundation" judged as bolt-on | High | Medium | Make guardrails + governance write-back the *narrative center*: agent decisions flow through DataHub context, not just alongside it |
| Time budget (~4 weeks, part-time) | Medium | Medium | Week 1 tool, Week 2 guardrails+write-back, Week 3 UI+demo data, Week 4 video/polish; cut FR-05/FR-07 to Medium if needed |
| Student-only style eligibility surprises | Low | Low | Rules reviewed: adults, all countries, pre-existing projects allowed |

---

## 6. Architecture Considerations

### 6.1 Project Level Selection

| Level | Selected |
|-------|:--------:|
| Starter | ☐ |
| Dynamic | ☐ |
| **Enterprise** (existing multi-module Python platform) | ☑ |

### 6.2 Key Architectural Decisions

| Decision | Options | Selected | Rationale |
|----------|---------|----------|-----------|
| DataHub integration path | MCP Server connection / Agent Context Kit SDK | **MCP Server first**, SDK fallback | Judging highlights MCP Server; matches existing MCP-native design |
| Tool pattern | New framework / existing plugin registry | **`PLUGIN_REGISTRY` plugin** | Proven with `SplunkPlugin`; zero-regression policy |
| Metadata queries | GraphQL direct / MCP tools | MCP tools, GraphQL fallback | Same dual-path resilience as `splunk_mcp_tool.py` |
| Demo strategy | Live-only / simulated-first | **Demo Mode simulation first** | Streamlit Cloud can't reach local DataHub; proven with Splunk demo |
| UI | New tab / extend Mission Control | New "Data Context" tab | Keeps 60-second first-screen story intact |
| Testing | AppTest extension | AppTest extension | Existing harness catches regressions cheaply |

### 6.3 Structure Preview

```
tools/datahub_mcp_tool.py        # NL -> DataHub MCP (search/lineage/ownership), GraphQL fallback
enterprise_mcp_connector/
  tool_manager.py                # + DataHubPlugin, PLUGIN_REGISTRY["datahub"]
security/governance_bridge.py    # DLP/remediation -> DataHub tags/properties write-back
demo_data.py                     # + gen_datahub_context() simulated lineage/owners/quality
demo_app.py                      # + "Data Context" tab wiring
docker-compose.yml               # + datahub quickstart service (live path)
```

---

## 7. Convention Prerequisites

### 7.1 Existing Project Conventions

- [x] `CLAUDE.md` conventions (conventional commits, minimal comments, error handling)
- [x] Graceful-degradation policy (env-gated integrations, try/except, zero base regressions)
- [x] `.gitattributes` (UTF-8/EOL hygiene)
- [ ] `docs/01-plan/conventions.md` (not used in this repo)

### 7.2 Environment Variables Needed

| Variable | Purpose | Scope | To Be Created |
|----------|---------|-------|:-------------:|
| `DATAHUB_GMS_URL` | DataHub metadata service endpoint | Server | ☐ |
| `DATAHUB_TOKEN` | DataHub PAT for MCP/GraphQL auth | Server (env/st.secrets only) | ☐ |
| `DATAHUB_MCP_URL` | MCP server endpoint (if remote) | Server | ☐ |

---

## 8. Next Steps

1. [ ] `/pdca design datahub-agent` — tool interface, guardrail decision flow, write-back schema, tab layout
2. [ ] Spike: run DataHub quickstart + MCP server locally, confirm tool call surface (timebox: half a day)
3. [ ] Implementation (`/pdca do datahub-agent`), then `/pdca analyze datahub-agent`

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-07-07 | Initial draft (hackathon adaptation plan) | sechan9999 |
