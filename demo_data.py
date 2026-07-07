"""Simulated demo-mode data generators. No backend or credentials required.

All numbers produced here are synthetic. Functions decorated with
st.cache_data draw from the module-global `random` stream (seeded per
session by the app); per-rerun display numbers should use the dedicated
RNG instance created in demo_app.py instead.
"""
import math
import random
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

MODELS = ["gpt-4o", "claude-sonnet-4", "gemini-2.0-flash", "gpt-4o-mini"]
M_COLOR = {"gpt-4o": "#74c7ec", "claude-sonnet-4": "#cba6f7",
           "gemini-2.0-flash": "#a6e3a1", "gpt-4o-mini": "#f9e2af"}
M_COST = {"gpt-4o": 0.030, "claude-sonnet-4": 0.015,
          "gemini-2.0-flash": 0.0035, "gpt-4o-mini": 0.0006}


@st.cache_data(ttl=30)
def gen_timeseries(hours=24, points_per_hour=4):
    """Cost/call time-series for the last N hours with a business-hours peak."""
    now = datetime.now()
    rows = []
    for h in range(hours * points_per_hour, 0, -1):
        ts = now - timedelta(minutes=15 * h)
        load = 1.0 + 2.0 * math.exp(-0.5 * ((ts.hour - 14) / 3) ** 2)
        for model in MODELS:
            calls = max(0, int(random.gauss(load * 8, 2)))
            cost = calls * M_COST[model] * random.uniform(0.8, 1.4)
            rows.append({"time": ts, "model": model,
                         "calls": calls, "cost": round(cost, 4)})
    return pd.DataFrame(rows)


@st.cache_data(ttl=30)
def gen_events(n=120):
    """Raw telemetry event log sample."""
    now = datetime.now()
    etypes = ["mcp_llm_call", "mcp_router_decision", "mcp_cache_hit",
              "mcp_cache_miss", "mcp_dlp_violation", "mcp_anomaly"]
    weights = [0.40, 0.25, 0.18, 0.08, 0.05, 0.04]
    rows = []
    for _ in range(n):
        ts = now - timedelta(seconds=random.randint(10, 86400))
        rows.append({
            "_time": ts.strftime("%H:%M:%S"),
            "event_type": random.choices(etypes, weights=weights)[0],
            "model": random.choice(MODELS),
            "cost_usd": round(random.uniform(0.001, 0.12), 4),
            "latency_ms": random.randint(80, 1800),
            "ts": ts,
        })
    return pd.DataFrame(rows).sort_values("ts", ascending=False).drop(columns="ts")


@st.cache_data(ttl=60)
def gen_dlp_events(n=30):
    """DLP violation feed sample."""
    rules = [
        ("DLP-001", "SSN Pattern",   "HIGH",   "block"),
        ("DLP-002", "Credit Card",   "HIGH",   "block"),
        ("DLP-003", "Email Address", "MEDIUM", "redact"),
        ("DLP-004", "API Key Leak",  "HIGH",   "block"),
        ("DLP-005", "Internal IP",   "LOW",    "log"),
    ]
    now = datetime.now()
    rows = []
    for _ in range(n):
        rule_id, rule_name, sev, action = random.choice(rules)
        ts = now - timedelta(seconds=random.randint(0, 7200))
        rows.append({
            "time": ts,
            "rule": f"{rule_id} - {rule_name}",
            "severity": sev,
            "action": action,
            "user": f"user_{random.randint(1, 20):03d}",
            "soar_triggered": sev == "HIGH",
        })
    return pd.DataFrame(rows).sort_values("time", ascending=False)


def demo_agent_run(query, render_steps):
    """Simulated agent execution. render_steps(steps) animates the tool loop."""
    q = query.lower()

    if any(k in q for k in ["visitor", "cumulative"]):
        render_steps([
            ("supabase_query", "Connecting to Supabase visitors table..."),
            ("aggregate", "Counting cumulative rows..."),
            ("synthesize", "Generating response..."),
        ])
        n = random.randint(8500, 42000)
        return {"success": True, "result": {
            "response": (f"Cumulative visitors: {n:,} (+{random.randint(40, 320)} today). "
                         "Source: Supabase visitors table."),
            "tool_results": [{"tool": "supabase_query",
                              "result": {"count": n, "table": "visitors"}}],
        }}

    if any(k in q for k in ["cost", "dlp", "error", "cache", "latency", "splunk"]):
        render_steps([
            ("spl_translate", "Translating NL to SPL..."),
            ("splunk_query", "Querying index=mcp_agents..."),
            ("cost_analyzer", "Aggregating cost by model..."),
            ("synthesize", "Generating response..."),
        ])
        df = gen_timeseries(hours=1)
        total = df["cost"].sum()
        top_m = df.groupby("model")["cost"].sum().idxmax()
        return {"success": True, "result": {
            "response": (f"Last hour: total cost ${total:.4f}. Top model: {top_m} "
                         f"(${df[df.model == top_m]['cost'].sum():.4f}). "
                         "Cache saved ~40%. 2 DLP events."),
            "tool_results": [
                {"tool": "splunk_query",
                 "result": {"spl": "index=mcp_agents | stats sum(cost_usd) by model",
                            "rows": 4}},
                {"tool": "cost_analyzer",
                 "result": {"total_cost": round(total, 4), "top_model": top_m}},
            ],
        }}

    render_steps([
        ("recall", "Checking memory store..."),
        ("analyze_data", "Analyzing query intent..."),
        ("synthesize", "Generating response..."),
    ])
    return {"success": True, "result": {
        "response": (f"Query processed: '{query}'. Agent completed in "
                     f"{random.randint(180, 900)}ms via {random.choice(MODELS)}."),
        "tool_results": [{"tool": "analyze_data",
                          "result": {"intent": "general", "confidence": 0.87}}],
    }}


@st.cache_data(ttl=60)
def gen_datahub_context():
    """Simulated DataHub context graph: one dataset per guardrail verdict.

    Keys mirror tools.datahub_mcp_tool.DatasetContext.to_dict() plus a
    precomputed 'verdict' so the UI can demo allow/warn/block paths.
    """
    def urn(platform, name):
        return f"urn:li:dataset:(urn:li:dataPlatform:{platform},{name},PROD)"

    return {
        "visitors": {
            "urn": urn("supabase", "visitors"), "name": "visitors",
            "platform": "supabase", "owners": ["data-eng@llmai.dev"],
            "deprecated": False, "tags": ["gold", "product-analytics"],
            "assertions_passing": True,
            "upstream": [urn("kafka", "web_events")],
            "downstream": [urn("looker", "traffic_dashboard")],
            "verdict": {"action": "allow", "reasons": []},
        },
        "llm_costs": {
            "urn": urn("postgres", "llm_costs"), "name": "llm_costs",
            "platform": "postgres", "owners": ["platform-team@llmai.dev"],
            "deprecated": False, "tags": ["gold", "finops"],
            "assertions_passing": True,
            "upstream": [urn("splunk", "mcp_agents_index")],
            "downstream": [urn("looker", "cost_dashboard")],
            "verdict": {"action": "allow", "reasons": []},
        },
        "patients_pii": {
            "urn": urn("postgres", "patients_pii"), "name": "patients_pii",
            "platform": "postgres", "owners": ["health-data@llmai.dev"],
            "deprecated": False, "tags": ["pii", "restricted", "hipaa"],
            "assertions_passing": True,
            "upstream": [urn("s3", "raw_intake")],
            "downstream": [],
            "verdict": {"action": "warn",
                        "reasons": ["PII-tagged dataset - DLP scan enforced"]},
        },
        "user_features_v1": {
            "urn": urn("s3", "user_features_v1"), "name": "user_features_v1",
            "platform": "s3", "owners": ["ml-team@llmai.dev"],
            "deprecated": False, "tags": ["ml-features"],
            "assertions_passing": False,
            "upstream": [urn("postgres", "llm_costs")],
            "downstream": [urn("mlflow", "router_model")],
            "verdict": {"action": "warn",
                        "reasons": ["failing quality assertions"]},
        },
        "legacy_metrics": {
            "urn": urn("mysql", "legacy_metrics"), "name": "legacy_metrics",
            "platform": "mysql", "owners": ["data-eng@llmai.dev"],
            "deprecated": True, "tags": ["deprecated"],
            "assertions_passing": None,
            "upstream": [], "downstream": [],
            "verdict": {"action": "block",
                        "reasons": ["dataset deprecated "
                                    "(owners: data-eng@llmai.dev)"]},
        },
    }


@st.cache_data(ttl=60)
def gen_governance_events(n=12):
    """Simulated governance write-back feed (DLP tags, remediation props)."""
    ctx = gen_datahub_context()
    kinds = [
        ("dlp_violation", "llmai:dlp-violation", "patients_pii"),
        ("remediation", "llmai:last-remediation", "llm_costs"),
        ("guardrail_block", "llmai:blocked-by-guardrail", "legacy_metrics"),
        ("dlp_violation", "llmai:dlp-violation", "visitors"),
    ]
    now = datetime.now()
    rows = []
    for _ in range(n):
        event, tag, ds = random.choice(kinds)
        ts = now - timedelta(seconds=random.randint(60, 86400))
        rows.append({
            "time": ts.strftime("%H:%M:%S"),
            "event": event,
            "tag_written": tag,
            "dataset": ds,
            "urn": ctx[ds]["urn"],
            "ts": ts,
        })
    return (pd.DataFrame(rows).sort_values("ts", ascending=False)
            .drop(columns="ts"))


def demo_alert(anomaly_type, value):
    """Simulated auto-remediation response for a fired anomaly alert."""
    thresholds = {"cost_spike": 5.0, "latency_spike": 3000,
                  "error_rate_high": 0.15, "dlp_burst": 10, "token_overrun": 100000}
    return {
        "handled": True, "anomaly_type": anomaly_type,
        "anomaly_value": float(value),
        "threshold": thresholds.get(anomaly_type, 5.0),
        "actions": [
            {"action": "downgrade_model", "result": "gpt-4o -> gemini-2.0-flash"},
            {"action": "enable_cache", "result": "semantic_cache=ON"},
            {"action": "rate_limit", "result": "max_rpm=30"},
            {"action": "emit_telemetry", "result": "HEC event sent to index=mcp_agents"},
        ],
        "cooldown_sec": 600,
    }
