"""Agentic Ops Control Center - Splunk observability and remediation for AI agents.

Streamlit entrypoint (deployed on Streamlit Cloud as demo_app.py).
Module layout:
    styles.py          - CSS theme
    demo_data.py       - simulated data generators (Demo Mode)
    backend_client.py  - live-mode HTTP client + connection checks
    ui/components.py   - KPI cards, journey guide, status badges, step pills
    ui/charts.py       - Plotly chart builders (dark theme)
"""
import math
import os
import random
import re
import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

import backend_client as backend
import demo_data
import styles
from demo_data import M_COLOR, MODELS
from ui import charts
from ui.components import (connection_status, dlp_alert_row, insights_strip,
                           journey_section, kpi, sec_header, stream_steps)

SPLUNK_DASHBOARD_URL = "http://localhost:8000/en-US/app/search/llmai_agentic_ops"


def md_safe(text):
    """Escape $ so Streamlit markdown doesn't treat $...$ pairs as LaTeX math."""
    return str(text).replace("$", "\\$")

# --- Page config --------------------------------------------------------------
st.set_page_config(
    page_title="Agentic Ops Control Center",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Session-stable RNG: display numbers draw from RNG (re-seeded every rerun) so
# KPIs do not jump on widget interactions. The global `random` seed keeps the
# cached demo generators deterministic per session.
if "demo_seed" not in st.session_state:
    st.session_state.demo_seed = random.randint(0, 1_000_000)
random.seed(st.session_state.demo_seed)
RNG = random.Random(st.session_state.demo_seed)

styles.inject()

# --- Sidebar: mode selection --------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    mode = st.radio("Mode", ["🎮 Demo Mode", "🔌 Live Mode"], horizontal=True,
                    help="Demo Mode is a fully simulated guided tour. "
                         "Live Mode connects to real backends.")
    demo_mode = mode.startswith("🎮")

    cfg = backend.BackendConfig()

    if demo_mode:
        st.caption("Guided simulation — every number on screen is synthetic. "
                   "No backend, credentials, or setup needed.")
        st.markdown("**Connections**")
        connection_status({
            "MCPAgents API": ("unconfigured", "simulated"),
            "Splunk HEC": ("unconfigured", "simulated"),
            "Splunk REST": ("unconfigured", "simulated"),
            "Splunk SOAR": ("unconfigured", "simulated"),
        })
    else:
        with st.expander("🔧 Advanced setup", expanded=False):
            cfg.mcpagents_url = st.text_input("MCPAgents URL", cfg.mcpagents_url)
            cfg.api_token = st.text_input("API Token (X-MCP-Token)", "",
                                          type="password")
            cfg.splunk_rest = st.text_input("Splunk REST URL", cfg.splunk_rest)
            cfg.splunk_user = st.text_input("Splunk User", "")
            cfg.splunk_pass = st.text_input("Splunk Password", "", type="password")
            cfg.hec_url = st.text_input("HEC URL", cfg.hec_url)
            cfg.splunk_index = st.text_input("Index", cfg.splunk_index)
            cfg.soar_webhook = st.text_input("SOAR Webhook URL (optional)", "")
            cfg.verify_ssl = st.checkbox(
                "Verify TLS certificates", value=True,
                help="Disable ONLY for local dev against self-signed Splunk "
                     "certs. Never disable against production endpoints.")
            st.caption("Tip: on Streamlit Cloud, store these in "
                       "`st.secrets` instead of typing them here.")
        if not cfg.api_token:
            st.warning("API token is empty — agent and alert endpoints "
                       "will be called unauthenticated.")
        if st.button("🔍 Check connections", width="stretch"):
            with st.spinner("Probing backends..."):
                st.session_state.conn_status = backend.check_connections(cfg)
        if "conn_status" in st.session_state:
            st.markdown("**Connections**")
            connection_status(st.session_state.conn_status)

    st.divider()
    auto_refresh = st.toggle("🔄 Auto-refresh (10s)", value=False)
    st.divider()
    st.caption("**Stack:** FastAPI · Streamlit · Splunk HEC · Splunk SOAR · "
               "Multi-LLM Router · DLP Engine")

# --- Header -------------------------------------------------------------------
col_h, col_b = st.columns([7, 1])
with col_h:
    st.markdown("# 🔥 Agentic Ops Control Center")
    st.caption("Splunk observability and remediation for AI agents · MCPAgents")
with col_b:
    if demo_mode:
        st.markdown('<span class="demo-badge">🎮 DEMO</span>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<span class="live-badge">🔌 LIVE</span>',
                    unsafe_allow_html=True)

journey_section()
st.markdown("<br>", unsafe_allow_html=True)

# --- Global KPI bar -----------------------------------------------------------
df24 = demo_data.gen_timeseries(hours=24)
total_cost = df24["cost"].sum()
total_calls = df24["calls"].sum()
cache_saved = total_cost * 0.41
dlp_blocked = RNG.randint(11, 18)
remediations = RNG.randint(8, 14)

# Delta = last 12h vs first 12h of the generated window (data-driven)
_mid = df24["time"].min() + (df24["time"].max() - df24["time"].min()) / 2
_recent = df24[df24.time >= _mid]["cost"].sum()
_earlier = df24[df24.time < _mid]["cost"].sum()
_cost_delta = _recent - _earlier
_cost_up = _cost_delta >= 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.markdown(kpi("LLM Cost (24h)", f"${total_cost:.2f}",
                f"{'↑' if _cost_up else '↓'} ${abs(_cost_delta):.2f} vs prior 12h",
                "#f38ba8" if _cost_up else "#a6e3a1", not _cost_up),
            unsafe_allow_html=True)
c2.markdown(kpi("LLM Calls", f"{total_calls:,}", f"↑ {RNG.randint(5, 15)}%",
                "#89b4fa"), unsafe_allow_html=True)
c3.markdown(kpi("Cache Savings", f"${cache_saved:.2f}", "↓ 41% cost reduction",
                "#a6e3a1"), unsafe_allow_html=True)
c4.markdown(kpi("DLP Blocked", str(dlp_blocked),
                f"↓ {RNG.randint(2, 5)} vs avg", "#a6e3a1"),
            unsafe_allow_html=True)
c5.markdown(kpi("Remediations", str(remediations), "auto-healed", "#cba6f7"),
            unsafe_allow_html=True)

_by_model = df24.groupby("model")["cost"].sum()
_top_model = _by_model.idxmax()
_peak_hour = df24.assign(h=df24["time"].dt.hour).groupby("h")["calls"].sum().idxmax()
insights_strip(_top_model, M_COLOR[_top_model], _by_model.max(), total_cost,
               _peak_hour, cache_saved, dlp_blocked, remediations)

st.markdown("<br>", unsafe_allow_html=True)

# --- Tabs ---------------------------------------------------------------------
tab_mc, tab_agent, tab_threat, tab_roi, tab_spl, tab_overview = st.tabs([
    "🎯 Mission Control",
    "🤖 AI Agent Lab",
    "🔴 Live Threat Feed",
    "💰 ROI Impact",
    "🔧 SPL Query Lab",
    "🏠 Splunk Overview",
])

# --- Tab 1: Mission Control ---------------------------------------------------
with tab_mc:
    sec_header("Cost Over Time by Model (24h)")
    st.plotly_chart(charts.cost_line(df24), width="stretch")

    col_l, col_m, col_r = st.columns(3)
    with col_l:
        sec_header("Model Distribution")
        st.plotly_chart(charts.model_pie(df24), width="stretch")
    with col_m:
        sec_header("Cache Performance (24h)")
        hits = int(total_calls * 0.41)
        st.plotly_chart(charts.cache_bar(hits, total_calls - hits),
                        width="stretch")
    with col_r:
        sec_header("Anomaly Density (24h)")
        hours = list(range(24))
        counts = [max(0, int(RNG.gauss(
            3 * math.exp(-0.5 * ((h - 14) / 4) ** 2) + 0.5, 0.8)))
            for h in hours]
        st.plotly_chart(charts.anomaly_heat(hours, counts), width="stretch")

    sec_header("Latency Distribution by Model (p50 / p95 / p99)")
    lat_base = {"gpt-4o": 650, "claude-sonnet-4": 480,
                "gemini-2.0-flash": 320, "gpt-4o-mini": 210}
    lat_df = pd.DataFrame([
        {"model": m, "p50": b, "p95": int(b * 2.1), "p99": int(b * 3.4)}
        for m, b in lat_base.items()])
    st.plotly_chart(charts.latency_bars(lat_df), width="stretch")

# --- Tab 2: AI Agent Lab --------------------------------------------------------
with tab_agent:
    sec_header("Run a Query — Agent Thinks Step by Step")

    col_q, col_u = st.columns([5, 1])
    with col_q:
        query = st.text_input(
            "Query", placeholder="e.g. What's the LLM cost in the last hour?",
            label_visibility="collapsed")
    with col_u:
        user_id = st.text_input("User", "demo", label_visibility="collapsed")

    steps_area = st.empty()

    if st.button("▶ Run Agent", type="primary", width="stretch"):
        if not query.strip():
            st.warning("Enter a query.")
        else:
            t0 = time.time()
            with st.spinner(""):
                if demo_mode:
                    result = demo_data.demo_agent_run(
                        query, lambda steps: stream_steps(steps_area, steps))
                else:
                    r = backend.post(f"{cfg.mcpagents_url}/agent/run", cfg,
                                     json={"query": query, "user_id": user_id},
                                     headers=cfg.auth_headers)
                    result = backend.safe_json(
                        r, f"Backend unreachable at {cfg.mcpagents_url}")
                elapsed = time.time() - t0

            if result.get("success") is False or "error" in result:
                st.error(f"Agent error: {result}")
            else:
                st.success(f"✅ Completed in {elapsed:.2f}s")
                res_obj = result.get("result", {})
                if isinstance(res_obj, dict) and res_obj.get("response"):
                    st.info(f"**Agent:** {md_safe(res_obj['response'])}")
                    st.session_state.setdefault("agent_history", []).append({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "query": query,
                        "response": res_obj["response"],
                        "elapsed": f"{elapsed:.2f}s",
                    })
                tool_results = (res_obj.get("tool_results", [])
                                if isinstance(res_obj, dict) else [])
                if tool_results:
                    st.markdown("**Tool Calls**")
                    for step in tool_results:
                        with st.expander(f"🔧 `{step.get('tool', '?')}`"):
                            res = step.get("result", "")
                            if isinstance(res, dict):
                                st.json(res)
                            else:
                                st.code(str(res)[:2000])
                with st.expander("📄 Raw JSON"):
                    st.json(result)

    st.divider()
    st.markdown("**Quick Prompts**")
    quick_prompts = [
        "LLM cost last hour?",
        "Show DLP violations",
        "Cache hit rate?",
        "Model with highest latency?",
        "Number of cumulative visitors",
    ]
    q_cols = st.columns(len(quick_prompts))
    for i, qp in enumerate(quick_prompts):
        if q_cols[i].button(qp, key=f"qp_{i}", width="stretch"):
            ph = st.empty()
            if demo_mode:
                r = demo_data.demo_agent_run(
                    qp, lambda steps: stream_steps(ph, steps))
            else:
                r = {"success": False,
                     "result": {"response": "Run live queries from the box above."}}
            res = r.get("result", {})
            if isinstance(res, dict) and res.get("response"):
                st.info(f"**Agent:** {md_safe(res['response'])}")
            for step in (res.get("tool_results", [])
                         if isinstance(res, dict) else []):
                with st.expander(f"🔧 `{step.get('tool', '?')}`"):
                    st.json(step.get("result", ""))

    if st.session_state.get("agent_history"):
        st.divider()
        sec_header("Session History")
        for h in reversed(st.session_state["agent_history"][-5:]):
            with st.expander(f"🕐 {h['time']} — {h['query'][:60]}  ({h['elapsed']})"):
                st.markdown(f"**Agent:** {md_safe(h['response'])}")

    st.divider()
    sec_header("Agent Performance (24h)")
    ap1, ap2, ap3, ap4 = st.columns(4)
    ap1.metric("Avg Latency", f"{RNG.randint(320, 480)}ms",
               f"-{RNG.randint(5, 15)}%")
    ap2.metric("Success Rate", f"{RNG.uniform(96, 99.5):.1f}%", "+0.8%")
    ap3.metric("Cost / Query", f"${RNG.uniform(0.012, 0.035):.4f}", "-12%")
    ap4.metric("Queries (24h)", f"{total_calls:,}", f"+{RNG.randint(5, 18)}%")

# --- Tab 3: Live Threat Feed ----------------------------------------------------
with tab_threat:
    col_tl, col_tr = st.columns([1.4, 1])

    with col_tl:
        sec_header("DLP Violation Feed — Real-time")
        dlp_df = demo_data.gen_dlp_events(25)
        for _, row in dlp_df.head(12).iterrows():
            dlp_alert_row(row)

    with col_tr:
        sec_header("Severity Breakdown")
        sev_counts = dlp_df["severity"].value_counts().reset_index()
        sev_counts.columns = ["severity", "count"]
        fig_sev = px.pie(
            sev_counts, values="count", names="severity", color="severity",
            color_discrete_map={"HIGH": "#f38ba8", "MEDIUM": "#fab387",
                                "LOW": "#a6e3a1"},
            hole=0.6, template="plotly_dark")
        st.plotly_chart(charts.dark(fig_sev, height=220, legend_y=-0.1),
                        width="stretch")

        sec_header("SOAR Auto-Response")
        soar_actions = [
            ("mcp_block_user", "Block high-risk user session", "✅"),
            ("mcp_notify_security", "Alert security team (Slack)", "✅"),
            ("mcp_quarantine_session", "Isolate session + revoke token", "✅"),
            ("mcp_enrich_ioc", "IOC enrichment & threat intel", "⏳"),
        ]
        for pb, desc, status in soar_actions:
            st.markdown(f"{status} **`{pb}`** — {desc}")

    st.divider()

    sec_header("Auto-Remediation Simulator — Fire an Anomaly Alert")
    st.caption("Simulates: Splunk CDTS anomaly → POST /splunk/alert → "
               "auto-remediation policy engine")

    scenarios = {
        "💸 Cost Spike": ("cost_spike", 9.2),
        "🐢 Latency Spike": ("latency_spike", 6500),
        "❌ Error Rate": ("error_rate_high", 0.25),
        "🚨 DLP Burst": ("dlp_burst", 20),
        "📝 Token Overrun": ("token_overrun", 150000),
    }
    s_cols = st.columns(len(scenarios))
    for i, (label, (atype, val)) in enumerate(scenarios.items()):
        with s_cols[i]:
            st.markdown(f"**{label}**")
            st.caption(f"`{atype}` = {val:,}")
            if st.button("Fire", key=f"fire_{atype}", width="stretch"):
                with st.spinner("Sending alert..."):
                    if demo_mode:
                        resp = demo_data.demo_alert(atype, val)
                    else:
                        r = backend.post(
                            f"{cfg.mcpagents_url}/splunk/alert", cfg,
                            json={"result": {"anomaly_type": atype,
                                             "metric_value": str(val)}},
                            headers=cfg.auth_headers)
                        resp = backend.safe_json(
                            r, f"Backend unreachable at {cfg.mcpagents_url}")
                st.session_state[f"alert_{atype}"] = resp

    for label, (atype, _) in scenarios.items():
        key = f"alert_{atype}"
        if key in st.session_state:
            resp = st.session_state[key]
            with st.expander(f"✅ {label} — Remediation Result", expanded=True):
                if resp.get("handled"):
                    st.success(f"handled=True | value={resp.get('anomaly_value')} "
                               f"≥ threshold={resp.get('threshold')}")
                    for act in resp.get("actions", []):
                        st.markdown(f"- **{act['action']}** → `{act['result']}`")
                    st.caption(f"Cooldown: {resp.get('cooldown_sec')}s | "
                               "HEC event emitted to index=mcp_agents")
                else:
                    st.error(f"Alert not handled: {resp.get('error', resp)}")

# --- Tab 4: ROI Impact ----------------------------------------------------------
with tab_roi:
    sec_header("Business Impact — Simulated 30-Day Scenario")
    st.caption("🎮 All figures below are generated from the demo workload and the "
               "adjustable assumptions here — not measured production data.")

    a1, a2 = st.columns(2)
    baseline_spend = a1.slider(
        "Baseline monthly LLM spend (USD)", 1000, 50000, 11750, step=250,
        help="What you would spend per month with no caching or routing.")
    cache_rate = a2.slider(
        "Semantic cache hit rate (%)", 10, 70, 41,
        help="Share of LLM calls answered from the semantic cache.")

    cache_saved_m = baseline_spend * cache_rate / 100
    routing_saved_m = (baseline_spend - cache_saved_m) * 0.18
    ratelimit_saved_m = (baseline_spend - cache_saved_m - routing_saved_m) * 0.08
    total_saved_m = cache_saved_m + routing_saved_m + ratelimit_saved_m
    platform_cost_m = 580
    roi_mult = total_saved_m / platform_cost_m

    with st.expander("📋 Assumptions"):
        st.markdown(f"""
- **Cache savings** = baseline × hit rate = ${baseline_spend:,} × {cache_rate}% = **${cache_saved_m:,.0f}**
- **Smart routing** shifts premium-model traffic to cheaper models: 18% of post-cache spend = **${routing_saved_m:,.0f}**
- **Rate limiting** trims runaway/retry storms: 8% of the remainder = **${ratelimit_saved_m:,.0f}**
- **Platform cost** (Splunk ingest + infra, assumed): **${platform_cost_m}/month**
- **ROI multiplier** = total savings / platform cost = **{roi_mult:.1f}x**
- Threats-blocked and uptime figures are simulated demo telemetry.
""")

    r1, r2, r3, r4 = st.columns(4)
    r1.markdown(f"""
    <div class="kpi-card">
      <div class="roi-number">${total_saved_m:,.0f}</div>
      <div class="roi-label">LLM Cost Saved / mo</div>
      <div class="kpi-delta-good">↓ {total_saved_m / baseline_spend * 100:.0f}% via cache + routing</div>
    </div>""", unsafe_allow_html=True)
    r2.markdown(f"""
    <div class="kpi-card">
      <div class="roi-number">{RNG.randint(310, 380)}</div>
      <div class="roi-label">Threats Blocked</div>
      <div class="kpi-delta-good">simulated · 0 data breaches</div>
    </div>""", unsafe_allow_html=True)
    r3.markdown("""
    <div class="kpi-card">
      <div class="roi-number">99.4%</div>
      <div class="roi-label">Agent Uptime</div>
      <div class="kpi-delta-good">14 auto-heals (simulated)</div>
    </div>""", unsafe_allow_html=True)
    r4.markdown(f"""
    <div class="kpi-card">
      <div class="roi-number">{roi_mult:.1f}×</div>
      <div class="roi-label">ROI Multiplier</div>
      <div class="kpi-delta-good">vs ${platform_cost_m}/mo platform cost</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_rl, col_rr = st.columns(2)
    with col_rl:
        sec_header("Cost Reduction Waterfall (30d, simulated)")
        st.plotly_chart(
            charts.roi_waterfall(baseline_spend, cache_saved_m,
                                 routing_saved_m, ratelimit_saved_m),
            width="stretch")
    with col_rr:
        sec_header("Daily Savings Trend (30d, simulated)")
        days = pd.date_range(end=datetime.now(), periods=30, freq="D")
        daily_base = baseline_spend / 30
        baseline = [daily_base * RNG.uniform(0.92, 1.08) for _ in range(30)]
        keep_ratio = 1 - total_saved_m / baseline_spend
        actual = [b * keep_ratio * RNG.uniform(0.95, 1.05) for b in baseline]
        st.plotly_chart(charts.savings_trend(days, baseline, actual),
                        width="stretch")

    st.divider()
    sec_header("How the Closed Loop Works")
    st.plotly_chart(charts.arch_diagram(), width="stretch")
    col_l1, col_l2, col_l3 = st.columns(3)
    col_l1.markdown("**1. Query path** — NL query → SPL translation → Splunk "
                    "search → results injected back into agent context")
    col_l2.markdown("**2. Observability loop** — Every LLM call emits HEC event "
                    "→ `index=mcp_agents` → CDTS anomaly detect → "
                    "`/splunk/alert` → auto-remediation")
    col_l3.markdown("**3. Security path** — DLP scans every tool output in "
                    "realtime → HIGH violation → Foundation-sec SOAR playbook")

# --- Tab 5: SPL Query Lab -------------------------------------------------------
with tab_spl:
    sec_header("Interactive SPL Query Lab")
    st.caption("Write or pick a query → results render as a chart + table.")

    presets = {
        "Cost by model (24h)":  "index=mcp_agents event_type=mcp_llm_call | stats sum(cost_usd) as cost by model | sort - cost",
        "DLP violations (1h)":  "index=mcp_agents event_type=mcp_dlp_violation | table _time,rule_id,sensitivity,action_taken | sort - _time",
        "Cache hit rate":       "index=mcp_agents (event_type=mcp_cache_hit OR mcp_cache_miss) | stats count by event_type",
        "Anomaly timeline":     "index=mcp_agents event_type=mcp_anomaly | table _time,anomaly_type,current_value,threshold | sort - _time",
        "Router decisions":     "index=mcp_agents event_type=mcp_router_decision | stats count by selected_model",
        "P95 latency by model": "index=mcp_agents event_type=mcp_llm_call | stats perc95(latency_ms) as p95 by model | sort - p95",
        "Hourly cost trend":    "index=mcp_agents event_type=mcp_llm_call | timechart span=1h sum(cost_usd) by model",
        "Top users by cost":    "index=mcp_agents event_type=mcp_llm_call | stats sum(cost_usd) as cost by user_id | sort - cost | head 10",
    }

    col_pre, col_range = st.columns([3, 1])
    with col_pre:
        selected = st.selectbox("Preset queries", list(presets.keys()),
                                label_visibility="collapsed")
    with col_range:
        q_range = st.selectbox("Range", ["-1h", "-6h", "-24h", "-7d"],
                               label_visibility="collapsed")

    spl_query = st.text_area("SPL", presets[selected], height=80)

    run_col, _ = st.columns([1, 3])
    run_query = run_col.button("▶ Run Query", type="primary", width="stretch")

    if run_query:
        with st.spinner("Running..."):
            time.sleep(0.4)  # simulate round-trip

        range_hours = {"-1h": 1, "-6h": 6, "-24h": 24, "-7d": 168}[q_range]
        df_range = demo_data.gen_timeseries(hours=range_hours)
        st.caption(f"⏱ earliest={q_range} · {len(df_range):,} raw events scanned")

        sel = selected.lower()
        if "cost" in sel and "model" in sel and "timechart" not in sel:
            result_df = (df_range.groupby("model")["cost"].sum().reset_index()
                         .sort_values("cost", ascending=False))
            fig = px.bar(result_df, x="model", y="cost", color="model",
                         color_discrete_map=M_COLOR, template="plotly_dark",
                         labels={"cost": "Total Cost (USD)"})
        elif "cache" in sel:
            result_df = pd.DataFrame({
                "event_type": ["mcp_cache_hit", "mcp_cache_miss"],
                "count": [int(total_calls * 0.41), int(total_calls * 0.59)]})
            fig = px.bar(result_df, x="event_type", y="count", color="event_type",
                         color_discrete_map={"mcp_cache_hit": "#a6e3a1",
                                             "mcp_cache_miss": "#f38ba8"},
                         template="plotly_dark")
        elif "router" in sel:
            result_df = df_range.groupby("model")["calls"].sum().reset_index()
            result_df.columns = ["selected_model", "count"]
            fig = px.pie(result_df, values="count", names="selected_model",
                         color="selected_model", color_discrete_map=M_COLOR,
                         hole=0.5, template="plotly_dark")
        elif "latency" in sel or "p95" in sel:
            p95 = {"gpt-4o": 1380, "claude-sonnet-4": 990,
                   "gemini-2.0-flash": 650, "gpt-4o-mini": 430}
            result_df = (pd.DataFrame([{"model": m, "p95": p95[m]} for m in MODELS])
                         .sort_values("p95", ascending=False))
            fig = px.bar(result_df, x="model", y="p95", color="model",
                         color_discrete_map=M_COLOR, template="plotly_dark",
                         labels={"p95": "P95 Latency (ms)"})
        elif "timechart" in sel or "hourly" in sel:
            result_df = df_range.groupby(["time", "model"])["cost"].sum().reset_index()
            fig = px.line(result_df, x="time", y="cost", color="model",
                          color_discrete_map=M_COLOR, template="plotly_dark",
                          labels={"cost": "Cost (USD)", "time": ""})
        elif "dlp" in sel:
            dlp = demo_data.gen_dlp_events(20)
            result_df = dlp[["time", "rule", "severity", "action", "user"]].copy()
            result_df["time"] = result_df["time"].dt.strftime("%H:%M:%S")
            fig = px.histogram(dlp, x="severity", color="severity",
                               color_discrete_map={"HIGH": "#f38ba8",
                                                   "MEDIUM": "#fab387",
                                                   "LOW": "#a6e3a1"},
                               template="plotly_dark")
        else:
            result_df = demo_data.gen_events(30)[
                ["_time", "event_type", "model", "cost_usd", "latency_ms"]]
            fig = px.histogram(result_df, x="event_type", color="event_type",
                               template="plotly_dark")

        st.plotly_chart(charts.dark(fig, height=280), width="stretch")
        st.dataframe(result_df, width="stretch", height=200)
        st.download_button(
            "⬇ Export results (CSV)",
            result_df.to_csv(index=False).encode("utf-8"),
            file_name="spl_results.csv", mime="text/csv")

        with st.expander("📋 SPL Query (copy)"):
            st.code(spl_query, language="text")

    st.divider()
    sec_header("SPL Quick Reference — index=mcp_agents")
    ref_data = {
        "event_type values": "mcp_llm_call · mcp_router_decision · mcp_cache_hit · mcp_cache_miss · mcp_dlp_violation · mcp_anomaly · mcp_agent_complete",
        "Key fields": "model · cost_usd · latency_ms · prompt_tokens · completion_tokens · rule_id · sensitivity · action_taken · anomaly_type · current_value · threshold",
        "Useful aggregations": "stats sum(cost_usd) · stats perc95(latency_ms) · timechart span=1h · eval hit_rate=round(hits/total*100,1)",
    }
    for key, val in ref_data.items():
        st.markdown(f"**{key}:** `{val}`")

# --- Tab 6: Splunk Overview -----------------------------------------------------
with tab_overview:
    sec_header("Splunk Dashboard — LLMai Agentic Ops")
    st.caption("Splunk Dashboard Studio over `index=mcp_agents` — closed-loop "
               "observability: cost · routing · cache · DLP · anomaly→remediation.")

    _img = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "assets", "splunk_dashboard.png")
    if os.path.exists(_img):
        st.image(_img, width="stretch",
                 caption="Splunk Dashboard Studio — index=mcp_agents (live snapshot)")
    else:
        st.info("📸 Add a screenshot at `assets/splunk_dashboard.png` to show "
                "the Splunk dashboard here.")
    st.markdown(f"[↗ Open the live Splunk dashboard]({SPLUNK_DASHBOARD_URL})")

    with st.expander("Live embed instead of snapshot (local Splunk only)"):
        raw = st.text_area(
            "Splunk dashboard URL — or paste the full <iframe> Embed snippet",
            SPLUNK_DASHBOARD_URL, key="spl_embed_src", height=80)
        _m = re.search(r'''src=["']([^"']+)["']''', raw or "")
        spl_url = (_m.group(1) if _m else (raw or "").strip()) or SPLUNK_DASHBOARD_URL
        st.caption("Renders only with local Splunk reachable and framing allowed. "
                   f"[↗ Open in a new tab]({spl_url})")
        st.iframe(spl_url, height=900)

# --- Auto-refresh ---------------------------------------------------------------
if auto_refresh:
    time.sleep(10)
    st.rerun()
