# Devpost Submission — Build with DataHub: The Agent Hackathon

> Challenge track: **Production ML Protection Agents**
> Live demo: https://splunkhec2.streamlit.app/ (Demo Mode, zero setup)
> Repo: https://github.com/sechan9999/splunk_hec_v2 (Apache-2.0)
> Video: [ADD YOUTUBE LINK]

---

## Project name

**Agentic Ops Control Center — DataHub-guarded AI agents**

## Elevator pitch (200 chars)

An AI agent that checks DataHub before it touches your data — ownership, deprecation, quality — and writes every DLP violation and remediation back to the context graph as the audit trail.

---

## Inspiration

AI agents are being handed database credentials and told to "do the work." But an agent doesn't know what a data engineer knows: that `legacy_metrics` was deprecated last quarter, that `patients_pii` is HIPAA-restricted, that `user_features_v1` has been failing its quality assertions all week. Agents act on data the way a new hire would on day one — confidently and blindly.

We had already built a closed-loop agent-ops platform for the Splunk Agentic Ops Hackathon: an agent that streams its own cost/latency/DLP telemetry into Splunk, and Splunk reaches back to auto-remediate anomalies. That loop answers *"what is the agent doing?"* — but not *"should the agent be doing it?"* That question needs metadata, and metadata lives in DataHub.

## What it does

The DataHub context graph becomes both the agent's **decision input** and its **decision record**:

**1. Pre-flight metadata guardrails (decision input).** Before the agent executes any data tool, a `MetadataGuardrail` consults DataHub and applies an explicit decision table:

| DataHub says... | Verdict |
|---|---|
| dataset is deprecated | **BLOCK** — agent refuses and reports the owner to contact |
| quality assertions failing | **WARN** — proceeds, flagged in the UI |
| PII-tagged and DLP scanning is off | **WARN** |
| DataHub unreachable | **ALLOW** (degrade open — availability first, logged) |
| clean | **ALLOW** |

The verdict rides along with every tool result — in the Agent Lab you see `🧭 guardrail: allow — owner data-eng@...` on each call.

**2. Governance write-back (decision record).** Every DLP violation, auto-remediation, and guardrail block the agent produces is written back to the affected dataset in DataHub as namespaced `llmai:*` tags and properties. The context graph doubles as the compliance audit trail — a data steward opens DataHub and sees exactly which datasets the AI touched and what went wrong.

**3. Natural-language metadata queries.** The agent gained a `datahub_query` tool: "who owns the visitors table?", "show upstream lineage of llm_costs", "data quality of user_features" — classified and routed to DataHub search/ownership/lineage/quality lookups.

**4. Data Context tab.** The Control Center's new tab shows, per dataset the agent touched: owner, quality status, guardrail verdict with reasons, depth-1 lineage, and the live governance write-back feed.

All of this coexists with the original Splunk loop — Splunk watches the agent's *behavior*, DataHub governs the agent's *access*. Two planes, one closed loop.

## How we built it

- **DataHub integration** (`tools/datahub_mcp_tool.py`): MCP-server-first with a raw GraphQL fallback against GMS (`search`, `dataset`, `searchAcrossLineage`, `addTag`), a `DatasetContext` model, and an NL keyword classifier. The dual-path design mirrors our proven Splunk MCP tool.
- **Guardrail + write-back** (`security/governance_bridge.py`): the decision table is a pure function (`decide()`) — trivially unit-testable — with a 5-minute context cache and a `GUARDRAIL_MODE` env (off/warn/enforce). Write-back is fire-and-forget: governance must never break the agent loop.
- **Agent wiring**: `DataHubPlugin` registered in the platform's plugin registry; guardrail pre-flight hooked into the data-tool path; verdicts attached to results.
- **Demo Mode**: the public Streamlit app simulates a 5-dataset context graph deliberately covering all three verdicts, so judges can experience block/warn/allow with zero setup. Live mode connects to a real GMS via `DATAHUB_GMS_URL` + token (st.secrets), with per-service connection checks in the sidebar.
- **Method**: full PDCA cycle with docs in-repo (plan → design → implementation → gap analysis → report). Gap analysis scored 30 design items at 90% match after one cleanup iteration.

## Challenges we ran into

- **Degrade-open vs degrade-closed.** If DataHub is down, should the agent stop? We chose degrade-open (allow + log) so governance never becomes an availability dependency — but made blocking opt-in via `GUARDRAIL_MODE=enforce` for teams that want it strict.
- **Structured-properties mutation surface varies across DataHub versions** — we shipped a tag-encoded fallback for remediation properties and documented the real `upsertStructuredProperties` as a follow-up, rather than pretending version-fragile code works everywhere.
- **Demoing governance without infrastructure.** DataHub quickstart is multi-container; Streamlit Cloud can't run it. Solution: a faithful simulated context graph in Demo Mode, with the live GraphQL path behind a connection panel.

## Accomplishments we're proud of

- Governance that's **load-bearing, not decorative**: the guardrail actually changes agent behavior (a deprecated dataset gets refused with the owner's name), and the write-back makes DataHub the system of record for AI data access.
- **Zero regressions**: the entire DataHub layer is env-gated; the base platform runs identically without it — verified by a 55-check headless test suite plus 10 unit tests on the decision table.
- Shipping a **complete, documented engineering cycle** (plan/design/analysis/report in-repo) in the submission window.

## What we learned

- A pure decision function is the cheapest insurance for a security feature — every guardrail rule has a one-line test.
- Mirroring an existing proven integration pattern (our Splunk MCP tool) cut both design time and review risk for the DataHub tool to nearly zero.
- "Metadata as decision input" is a stronger agent-safety primitive than output filtering alone: the agent that never reads the deprecated table doesn't need its answer corrected.

## What's next

- Real `upsertStructuredProperties` + DataHub timeline events for remediation history
- Column-level guardrails (PII tags per field → selective masking instead of dataset-level warn)
- Guardrail verdicts emitted as HEC events so Splunk can alert on block-rate spikes — closing the loop between both planes
- Lineage-aware blast-radius checks: refuse writes upstream of gold dashboards

## Built with

Python · DataHub (MCP Server + GraphQL/GMS) · Streamlit · FastAPI · Splunk (HEC, SOAR, CDTS) · Plotly · pytest + streamlit AppTest · Docker

## Try it out

- **Live demo (no setup):** https://splunkhec2.streamlit.app/ — open the **🧭 Data Context** tab, pick `legacy_metrics` to see a BLOCK verdict; then in **AI Agent Lab** run "Number of cumulative visitors" and expand the tool call to see the guardrail line.
- **Repo:** https://github.com/sechan9999/splunk_hec_v2 — `pip install -r requirements.txt && streamlit run demo_app.py`
- **Live DataHub path:** `datahub docker quickstart`, set `DATAHUB_GMS_URL=http://localhost:8080`, switch the sidebar to Live Mode → Check connections.
