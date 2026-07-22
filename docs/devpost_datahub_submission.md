# Devpost Submission — Build with DataHub: The Agent Hackathon

> Challenge track: **Production ML Protection Agents**
> Live demo: https://splunkhec2.streamlit.app/ (Demo Mode, zero setup)
> Repo: https://github.com/sechan9999/splunk_hec_v2 (Apache-2.0)
> Video: https://youtu.be/0GBCgEzIF1g

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

| DataHub says... | Verdict | Tier |
|---|---|---|
| regulated (HIPAA/PHI/PCI) **and** DLP scanning is off | **BLOCK** — refuses even in warn mode | catastrophic |
| dataset is deprecated | **BLOCK** — refuses, names the owner, suggests a successor | serious |
| quality assertions failing | **WARN** — proceeds, flagged in the UI | serious |
| PII-tagged and DLP scanning is off | **WARN** | serious |
| regulated **and** DLP scanning is on | **ALLOW** — permitted, but recorded | informational |
| DataHub unreachable | **ALLOW** (degrade open — availability first, logged) | informational |
| clean | **ALLOW** | — |

The tier column is the load-bearing part. A `serious` finding downgrades to a
warning unless an operator opts into `GUARDRAIL_MODE=enforce`; a `catastrophic`
one refuses to be downgraded at all. And permitted is not the same as
unremarkable — a regulated read with DLP on still leaves a reason code, because
a governance layer that records nothing when it says yes has no audit trail.

The verdict rides along with every tool result — in the Agent Lab you see `🧭 guardrail: allow — owner data-eng@...` on each call.

**2. Governance write-back (decision record).** Every DLP violation, auto-remediation, and guardrail block the agent produces is written back to the affected dataset in DataHub as namespaced `llmai:*` tags and properties. The context graph doubles as the compliance audit trail — a data steward opens DataHub and sees exactly which datasets the AI touched and what went wrong.

**3. Natural-language metadata queries.** The agent gained a `datahub_query` tool: "who owns the visitors table?", "show upstream lineage of llm_costs", "data quality of user_features" — classified and routed to DataHub search/ownership/lineage/quality lookups.

**4. Data Context tab.** The Control Center's new tab shows, per dataset the agent touched: owner, quality status, guardrail verdict with reasons, depth-1 lineage, and the live governance write-back feed.

**5. A block that tells you where to go instead.** When the agent is stopped on a deprecated dataset, the verdict carries a suggested successor plus the evidence for it — a replacement named in DataHub's deprecation note, or a downstream table sharing the deprecated one's name stem. Every suggestion reports its basis and confidence, and none is ever auto-applied: a redirect the system cannot justify is worse than no redirect.

All of this coexists with the original Splunk loop — Splunk watches the agent's *behavior*, DataHub governs the agent's *access*. Two planes, one closed loop.

### Who owns what

Governance breaks down when it is unclear which decisions belong to a person and which to the machine, so we drew the line explicitly:

| | Owns |
|---|---|
| **Humans** | What the policy says, which datasets are regulated, approval of policy merges (CODEOWNERS on `policies/`) |
| **Agent** | Interpreting the question, choosing tools, drafting SQL — never its own permissions |
| **Code** | Enforcing the policy deterministically, capping what is reachable, writing the audit trail |

The agent never adjudicates its own access. That is the whole point.

## How we built it

- **DataHub integration** (`tools/datahub_mcp_tool.py`): MCP-server-first with a raw GraphQL fallback against GMS (`search`, `dataset`, `searchAcrossLineage`, `addTag`), a `DatasetContext` model, and an NL keyword classifier. The dual-path design mirrors our proven Splunk MCP tool.
- **Guardrail + write-back** (`security/governance_bridge.py`): the decision table is a pure function (`decide()`) — trivially unit-testable — with a 5-minute context cache and a `GUARDRAIL_MODE` env (off/warn/enforce). Write-back is fire-and-forget: governance must never break the agent loop.
- **The policy is a contract, not code** (`policies/governance.yaml` + `security/policy.py`): the rules live in versioned YAML with CODEOWNERS review, so changing what the agent may touch is a diff a reviewer reads rather than a code change buried in a function. The policy is *data* — a rule may only select among predicates the evaluator implements, so there is no path by which editing the file executes anything, and an unknown predicate is rejected at load. Every verdict carries the policy version that produced it. Rules are tiered: `catastrophic` findings (regulated data read with DLP off) refuse to be downgraded, while `serious` ones stay advisory unless an operator opts into enforce.
- **Golden-case regression suite** (`tests/golden/`, 19 cases): real questions the guardrail got wrong become permanent fixtures, asserted on stable reason codes rather than on prose that is free to be reworded. A coverage gate fails the build if a policy rule ships without a case — we verified it bites by adding a throwaway rule and watching CI refuse it. A second suite pins the demo graph to the live engine, so the Streamlit demo can never drift into showing a verdict the product would not produce.
- **Risk-tiered CI gating** (`.github/workflows/governance.yml`): the depth of validation follows what a change can break. Structural audit contracts run first and block unconditionally — a verdict that stops carrying its evidence, or a removed write-back, fails the merge no matter what the pass rate says. A diff touching `policies/` additionally runs the coverage gate and flags that CODEOWNERS approval is required. Verified end to end on PR #1: `verify` passed in 34s and `policy-change` correctly skipped in 7s because that PR did not touch the policy.
- **Agent wiring**: `DataHubPlugin` registered in the platform's plugin registry; guardrail pre-flight hooked into the data-tool path; verdicts attached to results.
- **Demo Mode**: the public Streamlit app simulates a 7-dataset context graph deliberately covering all three verdicts *and* all three successor-evidence paths — a stated deprecation note, an inference from lineage, and a deprecated table where no successor can be justified and the UI says so — so judges can experience block/warn/allow with zero setup. Live mode connects to a real GMS via `DATAHUB_GMS_URL` + token (st.secrets), with per-service connection checks in the sidebar.
- **Method**: full PDCA cycle with docs in-repo (plan → design → implementation → gap analysis → report). Gap analysis scored 30 design items at 93% match after two iterations.
- **Validated against a real DataHub quickstart** (GMS v1.5.0.6) with the official [healthcare sample dataset](https://github.com/datahub-project/static-assets/tree/main/datasets/healthcare): live NL ownership/lineage queries, guardrail WARN on the PII-tagged mart, and round-trip-verified `llmai:*` tag write-back — evidence in [`docs/live_spike_evidence.md`](live_spike_evidence.md). The spike even caught a real API constraint (tags must be created before association) that simulation couldn't.

## Challenges we ran into

- **Degrade-open vs degrade-closed.** If DataHub is down, should the agent stop? We chose degrade-open (allow + log) so governance never becomes an availability dependency — but made blocking opt-in via `GUARDRAIL_MODE=enforce` for teams that want it strict.
- **Structured-properties mutation surface varies across DataHub versions** — we shipped a tag-encoded fallback for remediation properties and documented the real `upsertStructuredProperties` as a follow-up, rather than pretending version-fragile code works everywhere.
- **Demoing governance without infrastructure.** DataHub quickstart is multi-container; Streamlit Cloud can't run it. Solution: a faithful simulated context graph in Demo Mode, with the live GraphQL path behind a connection panel.

## Accomplishments we're proud of

- Governance that's **load-bearing, not decorative**: the guardrail actually changes agent behavior (a deprecated dataset gets refused with the owner's name), and the write-back makes DataHub the system of record for AI data access.
- **The guardrail is defended by evidence, not by hope.** Anyone can write a decision table; the question a governance jury should ask is how you know it still decides correctly after ten policy edits. Our answer is a coverage gate that refuses to merge a rule nobody wrote a case for.
- **Zero regressions, and you can check**: the entire DataHub layer is env-gated, so the base platform runs identically without it. The suite grew from 10 checks to **74** — golden cases, structural audit contracts, demo-versus-engine consistency, and headless AppTest coverage of the Data Context tab — without breaking one of the original ten. Every number here comes from `pytest tests -q` on a clean checkout; nothing is cited that a reader cannot reproduce.
- **Governance is not where the latency goes**: policy evaluation costs p50 0.006 ms / p95 0.014 ms per decision (n=2000, measured on this repo, excluding the DataHub lookup the 5-minute cache absorbs). Being auditable did not cost us a runtime budget.
- Shipping a **complete, documented engineering cycle** (plan/design/analysis/report in-repo) in the submission window.

## What we learned

- A pure decision function is the cheapest insurance for a security feature — every guardrail rule has a one-line test.
- Mirroring an existing proven integration pattern (our Splunk MCP tool) cut both design time and review risk for the DataHub tool to nearly zero.
- "Metadata as decision input" is a stronger agent-safety primitive than output filtering alone: the agent that never reads the deprecated table doesn't need its answer corrected.
- **The regression suite found two governance bugs our unit tests could not.** The original decision table returned on the first match, so a dataset that was both deprecated *and* holding unscanned regulated data reported only the deprecation — the more serious finding was silently masked. And a HIPAA-tagged read with DLP enabled produced a bare allow with no reason code at all, meaning regulated-data access left no trace in the audit log. Permitted is not the same as unremarkable. Both are now golden cases, so neither can come back.
- **Pinning the demo to the engine caught the demo lying.** Our Streamlit demo shipped precomputed verdicts so it could run without DataHub; one of them claimed a warn the policy would never produce. A test that replays the demo graph through the live evaluator now makes that drift impossible.
- Failures sort cleanly into three buckets, and each has one right place to fix it: a wrong idea about the data is a *policy* change, a wrong procedure is a *code* change, and something that should never have run at all is a *guard*. Knowing which bucket you are in is most of the debugging.

## What's next

- **Drift → PR loop**: today we write governance *into* DataHub; the missing half is reading back out. A nightly scan for datasets newly deprecated or newly tagged as regulated would open a PR updating `policies/governance.yaml` and its golden cases, with the diff and reasoning attached — self-healing in the only sense that means anything, which is routing a detected change into a verifiable code review rather than into a silent behavior change.
- **Schema-verified successors**: successor suggestions currently rank their evidence (deprecation note > lineage > naming) but explicitly do *not* claim schema compatibility, because we have no column-level metadata to check it with. Fetching schemas would let a suggestion say "drop-in" and mean it.
- Real `upsertStructuredProperties` + DataHub timeline events for remediation history
- Column-level guardrails (PII tags per field → selective masking instead of dataset-level warn)
- Guardrail verdicts emitted as HEC events so Splunk can alert on block-rate spikes — closing the loop between both planes
- Lineage-aware blast-radius checks: refuse writes upstream of gold dashboards

## Open-source contributions to DataHub (filed during the hackathon)

Both discovered while building this submission against the quickstart:

- [datahub-project/static-assets#211](https://github.com/datahub-project/static-assets/issues/211) — sample dataset scripts (`add_lineage.py`, `add_metadata.py`) crash on Windows (cp1252 `UnicodeEncodeError`); includes repro, workaround, and a suggested fix (PR offered).
- [datahub-project/datahub#18246](https://github.com/datahub-project/datahub/issues/18246) — `addTag` DX for programmatic governance tagging: BAD_REQUEST for not-yet-created tags; documents the idempotent create-then-associate pattern and proposes `createIfNotExists` / docs note.

## Built with

Python · DataHub (MCP Server + GraphQL/GMS) · Streamlit · FastAPI · Splunk (HEC, SOAR, CDTS) · Plotly · pytest + streamlit AppTest · Docker

## Try it out

**Live demo (no setup):** https://splunkhec2.streamlit.app/ → the **🧭 Data Context** tab. Three datasets tell the whole story in about thirty seconds:

1. `user_events_v1` — BLOCK, and the agent is handed `user_events_v2` at **high** confidence because a human wrote the replacement into DataHub's deprecation note.
2. `session_metrics_v1` — BLOCK with no note anywhere, so the successor is **inferred from lineage** and the confidence visibly drops to medium. There is a consumer dashboard downstream too; it is not offered, because consumers are not successors.
3. `legacy_metrics` — BLOCK with nothing to go on, and the app says exactly that instead of guessing.

Then pick `patients_pii`: an ALLOW that still carries a reason code, because a regulated read that leaves no audit trail is not really a governed one. Finally, in **AI Agent Lab**, run "Number of cumulative visitors" and expand the tool call to see the guardrail verdict riding along with the result.

**Repo:** https://github.com/sechan9999/splunk_hec_v2 — `pip install -r requirements.txt && streamlit run demo_app.py`, then `pytest tests -q` for the 74 checks behind every claim above.
- **Live DataHub path:** `datahub docker quickstart`, set `DATAHUB_GMS_URL=http://localhost:8080`, switch the sidebar to Live Mode → Check connections.
