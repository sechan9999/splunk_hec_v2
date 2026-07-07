# Live Spike Evidence — DataHub Integration (datahub-agent)

**Date:** 2026-07-07
**Environment:** DataHub quickstart (GMS v1.5.0.6, `serverType: quickstart`) —
frontend http://localhost:9002, GMS http://localhost:8080. CLI: acryl-datahub 1.6.0.10.
**Closes:** gap-analysis item 30 (live validation vs real DataHub).

---

## 1. Sample data ingested

Source: [datahub-project/static-assets — healthcare dataset](https://github.com/datahub-project/static-assets/tree/main/datasets/healthcare)
(chosen deliberately: planted data-quality issues, PII tags, forking pipeline — maps 1:1
onto our guardrail verdict paths).

```
datahub ingest -c ingest.yaml      -> Pipeline finished successfully; 51 events, 0 failures
python add_lineage.py              -> 5 lineage relationships
                                      raw_patients -> staging_patients -> mart_billing + mart_demographics
python add_metadata.py             -> Tags: pii, critical, internal, quality_monitored, pipeline_stage
                                      Glossary: Billing Amount, Admission Date, Length of Stay
                                      Owners: clinical_team, finance_team, research_team
```

## 2. DataHubMCPTool read path (our code, real GMS)

`search_entities("patients")` returned the ingested URNs
(`urn:li:dataset:(urn:li:dataPlatform:sqlite,healthcare.main.raw_patients,PROD)`, ...).

NL query `who owns "mart_billing"` (classified -> `owners`):

```json
{
  "name": "mart_billing", "platform": "sqlite",
  "owners": ["finance_team"],
  "deprecated": false,
  "tags": ["critical", "pipeline_stage"],
  "upstream": [".../raw_patients,PROD)", ".../staging_patients,PROD)"],
  "method": "owners", "duration_ms": 522
}
```

## 3. Guardrail verdicts on live metadata

```
mart_demographics (pii tag, DLP disabled)  -> WARN  ['PII-tagged dataset with DLP disabled']
mart_billing (clean)                       -> ALLOW []
```

## 4. Governance write-back, round-trip verified

First attempt surfaced a real API constraint: `addTag` fails with
"Urn does not exist" unless the tag entity is created first. Fixed in
`tools/datahub_mcp_tool.py` — `add_tag` now issues `createTag` (idempotent,
cached) before association.

After fix, re-read from GMS:

```
mart_demographics tags: ['pii', 'internal', 'pipeline_stage', 'llmai:dlp-violation']
raw_patients tags:      ['pii', 'quality_monitored', 'pipeline_stage', 'llmai:blocked-by-guardrail']
WRITE_BACK_VERIFIED
```

## 5. Regression after fix

- `tests/test_guardrail.py`: 10/10
- AppTest smoke suite: 55/55

## Notes

- GMS auth: quickstart ran with unauthenticated GMS; production deployments
  should set `DATAHUB_TOKEN` (Bearer) — already supported by the client.
- NL context lookup measured 522 ms against local GMS (3 sequential GraphQL
  calls); guardrail lookups are cached 5 min per dataset, so per-tool-call
  overhead amortizes well under the 500 ms NFR after first touch.
- `upsertStructuredProperties` remains deferred (tag-encoded fallback verified
  working live); see design 3.3 accepted deviation.
