"""
MCPAgents × Splunk — Hackathon Demo v2.0
Mission Control · AI Agent Lab · Live Threat Feed · ROI Impact · SPL Query Lab

Runs fully in DEMO MODE on Streamlit Cloud (no backend needed).
"""
import json
import math
import random
import time
import urllib3
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Constants ─────────────────────────────────────────────────────────────────
MODELS   = ["gpt-4o", "claude-sonnet-4", "gemini-2.0-flash", "gpt-4o-mini"]
M_COLOR  = {"gpt-4o": "#74c7ec", "claude-sonnet-4": "#cba6f7",
             "gemini-2.0-flash": "#a6e3a1", "gpt-4o-mini": "#f9e2af"}
M_COST   = {"gpt-4o": 0.030, "claude-sonnet-4": 0.015,
             "gemini-2.0-flash": 0.0035, "gpt-4o-mini": 0.0006}
OVERVIEW_URL = "https://sechan9999.github.io/splunk_hec/"
# Splunk Dashboard Studio view URL (local Splunk). Override in the Overview tab.
SPLUNK_DASHBOARD_URL = "http://localhost:8000/en-US/app/search/llmai_agentic_ops"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MCPAgents × Splunk",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Session-stable RNG: without this every widget interaction reruns the script
# and re-randomizes all KPIs, making the dashboard numbers jump around.
# Display numbers draw from RNG (a dedicated instance re-seeded each rerun) —
# NOT the global `random` module, whose stream position shifts depending on
# whether @st.cache_data generators hit or miss the cache.
if "demo_seed" not in st.session_state:
    st.session_state.demo_seed = random.randint(0, 1_000_000)
random.seed(st.session_state.demo_seed)
RNG = random.Random(st.session_state.demo_seed)

st.markdown("""
<style>
/* ── Global ── */
html, body, [data-testid="stApp"] { background: #11111b; }

/* ── KPI cards ── */
.kpi-card {
    background: #1e1e2e; border-radius: 12px; padding: 20px 24px;
    border: 1px solid #313244; text-align: center;
    box-shadow: 0 4px 20px rgba(0,0,0,0.4);
}
.kpi-value { font-size: 2.2em; font-weight: 800; margin: 0; }
.kpi-label { font-size: 0.78em; color: #6c7086; margin-top: 4px; letter-spacing: 0.05em; text-transform: uppercase; }
.kpi-delta-good { color: #a6e3a1; font-size: 0.85em; }
.kpi-delta-bad  { color: #f38ba8; font-size: 0.85em; }

/* ── Section header ── */
.sec-header {
    font-size: 1.05em; font-weight: 700; color: #cdd6f4;
    letter-spacing: 0.04em; margin-bottom: 4px;
    border-left: 3px solid #cba6f7; padding-left: 10px;
}

/* ── Demo badge ── */
.demo-badge {
    background: linear-gradient(135deg,#f5a623,#f7c948);
    color:#11111b; padding:3px 10px; border-radius:10px;
    font-weight:800; font-size:0.72em;
}

/* ── Step pill ── */
.step-pill {
    display:inline-block; background:#313244; border-radius:20px;
    padding:4px 14px; margin:3px 2px; font-size:0.82em; color:#cdd6f4;
}
.step-pill.done  { background:#1e3a2f; color:#a6e3a1; border:1px solid #a6e3a1; }
.step-pill.run   { background:#2a1e3a; color:#cba6f7; border:1px solid #cba6f7; }

/* ── Alert rows ── */
.alert-high   { border-left: 4px solid #f38ba8; padding: 8px 12px; background: #2a1e24; border-radius: 4px; margin: 4px 0; }
.alert-medium { border-left: 4px solid #fab387; padding: 8px 12px; background: #2a2218; border-radius: 4px; margin: 4px 0; }
.alert-low    { border-left: 4px solid #a6e3a1; padding: 8px 12px; background: #1e2a22; border-radius: 4px; margin: 4px 0; }

/* ── ROI number ── */
.roi-number { font-size:3em; font-weight:900; color:#a6e3a1; }
.roi-label  { color:#6c7086; font-size:0.85em; text-transform:uppercase; letter-spacing:0.06em; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Demo Data Generators
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def _gen_timeseries(hours=24, points_per_hour=4):
    """Generate realistic cost/call time-series for last N hours."""
    now = datetime.now()
    rows = []
    for h in range(hours * points_per_hour, 0, -1):
        ts = now - timedelta(minutes=15 * h)
        hour = ts.hour
        # business-hours spike pattern
        load = 1.0 + 2.0 * math.exp(-0.5 * ((hour - 14) / 3) ** 2)
        for model in MODELS:
            calls = max(0, int(random.gauss(load * 8, 2)))
            cost  = calls * M_COST[model] * random.uniform(0.8, 1.4)
            rows.append({
                "time":  ts,
                "model": model,
                "calls": calls,
                "cost":  round(cost, 4),
            })
    return pd.DataFrame(rows)


@st.cache_data(ttl=30)
def _gen_events(n=120):
    """Generate realistic event log."""
    now = datetime.now()
    etypes = ["mcp_llm_call", "mcp_router_decision", "mcp_cache_hit",
              "mcp_cache_miss", "mcp_dlp_violation", "mcp_anomaly"]
    weights = [0.40, 0.25, 0.18, 0.08, 0.05, 0.04]
    rows = []
    for _ in range(n):
        ts = now - timedelta(seconds=random.randint(10, 86400))
        etype = random.choices(etypes, weights=weights)[0]
        rows.append({
            "_time":      ts.strftime("%H:%M:%S"),
            "event_type": etype,
            "model":      random.choice(MODELS),
            "cost_usd":   round(random.uniform(0.001, 0.12), 4),
            "latency_ms": random.randint(80, 1800),
            "ts":         ts,
        })
    return pd.DataFrame(rows).sort_values("ts", ascending=False).drop(columns="ts")


@st.cache_data(ttl=60)
def _gen_dlp_events(n=30):
    rules = [
        ("DLP-001", "SSN Pattern",     "HIGH",   "block"),
        ("DLP-002", "Credit Card",     "HIGH",   "block"),
        ("DLP-003", "Email Address",   "MEDIUM", "redact"),
        ("DLP-004", "API Key Leak",    "HIGH",   "block"),
        ("DLP-005", "Internal IP",     "LOW",    "log"),
    ]
    now = datetime.now()
    rows = []
    for _ in range(n):
        rule_id, rule_name, sev, action = random.choice(rules)
        ts = now - timedelta(seconds=random.randint(0, 7200))
        rows.append({
            "time":      ts,
            "rule":      f"{rule_id} — {rule_name}",
            "severity":  sev,
            "action":    action,
            "user":      f"user_{random.randint(1,20):03d}",
            "soar_triggered": sev == "HIGH",
        })
    return pd.DataFrame(rows).sort_values("time", ascending=False)


def _arch_diagram():
    """Plotly closed-loop architecture diagram for ROI tab."""
    # Color palette per node type: (fill, border)
    C = {
        "user":   ("#313244", "#cdd6f4"),
        "agent":  ("#1a2744", "#89b4fa"),
        "splunk": ("#1a3025", "#a6e3a1"),
        "hec":    ("#2a1240", "#cba6f7"),
        "dlp":    ("#3a1215", "#f38ba8"),
        "cdts":   ("#1e2a40", "#89b4fa"),
        "alert":  ("#1a3025", "#a6e3a1"),
        "soar":   ("#3a2510", "#fab387"),
        "fsec":   ("#3a1520", "#f38ba8"),
    }

    # Node list: (x0, y0, x1, y1, style, label_top, label_bot)
    nodes = [
        (3.8, 6.4, 6.2, 7.1, "user",   "👤 User Query",           ""),
        (0.2, 4.6, 4.4, 5.7, "agent",  "🤖 AdvancedMCPAgent",    "Multi-LLM Router"),
        (5.6, 4.6, 9.8, 5.7, "splunk", "🔍 Splunk MCP Tool",     "REST API + NL→SPL"),
        (0.2, 2.9, 3.8, 3.9, "hec",    "📡 HEC Telemetry",       "index=mcp_agents"),
        (6.2, 2.9, 9.8, 3.9, "dlp",    "🛡️ DLP Engine",          "Realtime PII scan"),
        (0.2, 1.3, 3.8, 2.3, "cdts",   "🔎 Splunk CDTS",         "Anomaly Detection"),
        (6.2, 1.3, 9.8, 2.3, "fsec",   "🏛️ Foundation-sec",      "SOAR Playbook"),
        (2.8, 0.0, 5.8, 1.0, "alert",  "⚡ /splunk/alert",       "Auto-Remediation"),
        (6.2, 0.0, 9.8, 1.0, "soar",   "🛡️ SOAR",               "Playbook Triggered"),
    ]

    shapes, annotations = [], []

    for x0, y0, x1, y1, style, top, bot in nodes:
        fill, border = C[style]
        shapes.append(dict(
            type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
            fillcolor=fill, line=dict(color=border, width=1.8),
            xref="x", yref="y",
        ))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        label = f"<b>{top}</b>" + (f"<br><sub>{bot}</sub>" if bot else "")
        annotations.append(dict(
            x=cx, y=cy, text=label,
            showarrow=False, xref="x", yref="y",
            font=dict(color=border, size=11, family="monospace"),
            align="center",
        ))

    def arrow(x0, y0, x1, y1, label="", color="#585b70", ay_off=0):
        annotations.append(dict(
            x=x1, y=y1, ax=x0, ay=y0,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=3, arrowsize=1.3,
            arrowwidth=1.6, arrowcolor=color,
            text=label,
            font=dict(color=color, size=9),
            bgcolor="rgba(17,17,27,0.7)",
        ))

    # User → Agent
    arrow(5.0, 6.4,  2.3, 5.7,  "",          "#585b70")
    # Agent →→ Splunk MCP (forward)
    arrow(4.4, 5.25, 5.6, 5.35, "① NL→SPL", "#a6e3a1")
    # Splunk MCP →→ Agent (return)
    arrow(5.6, 5.05, 4.4, 4.95, "results ↩", "#a6e3a1")
    # Agent → HEC  (② emit)
    arrow(2.3, 4.6,  2.0, 3.9,  "② HEC emit", "#cba6f7")
    # Agent → DLP  (③ scan)
    arrow(4.4, 5.15, 6.2, 3.7,  "③ DLP scan", "#f38ba8")
    # HEC → CDTS
    arrow(2.0, 2.9,  2.0, 2.3,  "anomaly?",   "#89b4fa")
    # DLP → Foundation-sec
    arrow(8.0, 2.9,  8.0, 2.3,  "violation",  "#f38ba8")
    # CDTS → /splunk/alert
    arrow(3.0, 1.3,  4.0, 1.0,  "trigger",    "#fab387")
    # /splunk/alert → SOAR
    arrow(5.8, 0.55, 6.2, 0.55, "playbook →", "#fab387")

    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor="#181825", plot_bgcolor="#181825",
        shapes=shapes, annotations=annotations,
        xaxis=dict(visible=False, range=[-0.3, 10.3]),
        yaxis=dict(visible=False, range=[-0.4, 7.6]),
        height=480,
        margin=dict(l=10, r=10, t=10, b=10),
    )
    return fig


def _kpi(label, value, delta=None, color="#cdd6f4", delta_good=True):
    delta_html = ""
    if delta is not None:
        cls = "kpi-delta-good" if delta_good else "kpi-delta-bad"
        delta_html = f'<div class="{cls}">{delta}</div>'
    return f"""
    <div class="kpi-card">
      <div class="kpi-value" style="color:{color}">{value}</div>
      <div class="kpi-label">{label}</div>
      {delta_html}
    </div>"""


# ══════════════════════════════════════════════════════════════════════════════
# Backend helpers
# ══════════════════════════════════════════════════════════════════════════════

def _get(url, **kw):
    try:
        return requests.get(url, timeout=5, **kw)
    except Exception:
        return None

def _post(url, **kw):
    try:
        return requests.post(url, timeout=30, **kw)
    except Exception:
        return None

def _safe_json(resp, fallback_error):
    """Parse a requests response defensively — backend may be down or non-JSON."""
    if resp is None or not resp.ok:
        return {"success": False, "handled": False, "error": fallback_error}
    try:
        return resp.json()
    except Exception:
        return {"success": False, "handled": False,
                "error": f"Non-JSON response (HTTP {resp.status_code})"}

def _demo_health():
    return {
        "status": "ok", "version": "2.0.0-splunk",
        "telemetry": {"sent": random.randint(280, 350), "dropped": random.randint(0, 2)},
        "remediation": {"remediator": {
            "remediation_count": random.randint(8, 14),
            "active_cooldowns": {}
        }},
    }

def _demo_agent_run(query, steps_placeholder):
    """Simulated streaming agent execution."""
    q_lower = query.lower()

    # ── Visitor query ──
    if any(k in q_lower for k in ["visitor", "방문자", "누적"]):
        _stream_steps(steps_placeholder, [
            ("supabase_query", "Connecting to Supabase visitors table…"),
            ("aggregate",      "Counting cumulative rows…"),
            ("synthesize",     "Generating response…"),
        ])
        n = random.randint(8500, 42000)
        return {"success": True, "result": {
            "response": f"Cumulative visitors: {n:,} (+{random.randint(40,320)} today). Source: Supabase visitors table.",
            "tool_results": [{"tool": "supabase_query", "result": {"count": n, "table": "visitors"}}],
        }}

    # ── Cost / Splunk queries ──
    if any(k in q_lower for k in ["cost", "비용", "dlp", "error", "cache", "latency", "splunk"]):
        _stream_steps(steps_placeholder, [
            ("spl_translate",  "Translating NL → SPL…"),
            ("splunk_query",   "Querying index=mcp_agents…"),
            ("cost_analyzer",  "Aggregating cost by model…"),
            ("synthesize",     "Generating response…"),
        ])
        df = _gen_timeseries(hours=1)
        total = df["cost"].sum()
        top_m = df.groupby("model")["cost"].sum().idxmax()
        return {"success": True, "result": {
            "response": f"Last hour: total cost ${total:.4f}. Top model: {top_m} (${df[df.model==top_m]['cost'].sum():.4f}). Cache saved ~40%. 2 DLP events.",
            "tool_results": [
                {"tool": "splunk_query", "result": {"spl": "index=mcp_agents | stats sum(cost_usd) by model", "rows": 4}},
                {"tool": "cost_analyzer", "result": {"total_cost": round(total, 4), "top_model": top_m}},
            ],
        }}

    # ── General ──
    _stream_steps(steps_placeholder, [
        ("recall",        "Checking memory store…"),
        ("analyze_data",  "Analyzing query intent…"),
        ("synthesize",    "Generating response…"),
    ])
    return {"success": True, "result": {
        "response": f"Query processed: '{query}'. Agent completed in {random.randint(180,900)}ms via {random.choice(MODELS)}.",
        "tool_results": [{"tool": "analyze_data", "result": {"intent": "general", "confidence": 0.87}}],
    }}


def _stream_steps(placeholder, steps):
    """Animate agent steps visually."""
    done = []
    for name, desc in steps:
        with placeholder.container():
            pills = "".join(
                f'<span class="step-pill done">✓ {d}</span>' for d in done
            )
            pills += f'<span class="step-pill run">⟳ {name}</span>'
            st.markdown(pills, unsafe_allow_html=True)
            st.caption(f"▶ {desc}")
        time.sleep(0.45)
        done.append(name)
    with placeholder.container():
        pills = "".join(f'<span class="step-pill done">✓ {d}</span>' for d in done)
        st.markdown(pills, unsafe_allow_html=True)


def _demo_alert(anomaly_type, value):
    thresholds = {"cost_spike": 5.0, "latency_spike": 3000,
                  "error_rate_high": 0.15, "dlp_burst": 10, "token_overrun": 100000}
    return {
        "handled": True, "anomaly_type": anomaly_type,
        "anomaly_value": float(value), "threshold": thresholds.get(anomaly_type, 5.0),
        "actions": [
            {"action": "downgrade_model",  "result": "gpt-4o → gemini-2.0-flash"},
            {"action": "enable_cache",     "result": "semantic_cache=ON"},
            {"action": "rate_limit",       "result": "max_rpm=30"},
            {"action": "emit_telemetry",   "result": "HEC event sent to index=mcp_agents"},
        ],
        "cooldown_sec": 600,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    demo_mode = st.toggle("🎮 Demo Mode", value=True,
                          help="Fully simulated — no backend or credentials needed.")
    st.divider()
    if demo_mode:
        st.caption("🎮 All data is simulated. Toggle off to connect real backends.")
        mcpagents_url = "http://localhost:8001"
        api_token     = ""
        splunk_rest   = "https://localhost:8089"
        splunk_user   = ""
        splunk_pass   = ""
        hec_url       = "http://localhost:8088"
        splunk_index  = "mcp_agents"
    else:
        mcpagents_url = st.text_input("MCPAgents URL", "http://localhost:8001")
        api_token     = st.text_input("API Token (X-MCP-Token)", "", type="password")
        splunk_rest   = st.text_input("Splunk REST URL", "https://localhost:8089")
        splunk_user   = st.text_input("Splunk User", "")
        splunk_pass   = st.text_input("Splunk Password", "", type="password")
        hec_url       = st.text_input("HEC URL", "http://localhost:8088")
        splunk_index  = st.text_input("Index", "mcp_agents")

    st.divider()
    auto_refresh = st.toggle("🔄 Auto-refresh (10s)", value=False)
    st.divider()
    st.caption("**Stack:** FastAPI · Streamlit · Splunk HEC · Splunk SOAR · Multi-LLM Router · DLP Engine")


# ══════════════════════════════════════════════════════════════════════════════
# Header
# ══════════════════════════════════════════════════════════════════════════════

col_h, col_b = st.columns([7, 1])
with col_h:
    st.markdown("# 🔥 MCPAgents × Splunk")
    st.caption("Agentic Ops Control Center · Observability · Security · Auto-Remediation")
with col_b:
    if demo_mode:
        st.markdown('<span class="demo-badge">🎮 DEMO</span>', unsafe_allow_html=True)

with st.expander("❓ What am I looking at? (30-second tour)"):
    st.markdown(
        "**LLMai / MCPAgents** is a local-first AI agent whose every LLM call, router "
        "decision, cache hit, and DLP violation streams into **Splunk** (`index=mcp_agents`) — "
        "and Splunk reaches back to auto-remediate anomalies. Explore the tabs:\n\n"
        "- **Mission Control** — live cost / latency / cache observability\n"
        "- **AI Agent Lab** — run natural-language queries through the agent\n"
        "- **Live Threat Feed** — DLP violations, SOAR playbooks, and a *Fire an Anomaly* simulator\n"
        "- **ROI Impact** — business value + the closed-loop architecture diagram\n"
        "- **SPL Query Lab** — real SPL queries with charted results\n\n"
        "Demo Mode is fully simulated — no credentials or backend needed."
    )

# ── Global KPI bar ────────────────────────────────────────────────────────────
df24 = _gen_timeseries(hours=24)
total_cost   = df24["cost"].sum()
total_calls  = df24["calls"].sum()
cache_saved  = total_cost * 0.41
dlp_blocked  = RNG.randint(11, 18)
remediations = RNG.randint(8, 14)

# Delta = last 12h vs first 12h of the generated window (data-driven, not hardcoded)
_mid = df24["time"].min() + (df24["time"].max() - df24["time"].min()) / 2
_recent, _earlier = df24[df24.time >= _mid]["cost"].sum(), df24[df24.time < _mid]["cost"].sum()
_cost_delta = _recent - _earlier
_cost_up = _cost_delta >= 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.markdown(_kpi("LLM Cost (24h)", f"${total_cost:.2f}",
                 f"{'↑' if _cost_up else '↓'} ${abs(_cost_delta):.2f} vs prior 12h",
                 "#f38ba8" if _cost_up else "#a6e3a1", not _cost_up), unsafe_allow_html=True)
c2.markdown(_kpi("LLM Calls",      f"{total_calls:,}",   f"↑ {RNG.randint(5,15)}%", "#89b4fa"), unsafe_allow_html=True)
c3.markdown(_kpi("Cache Savings",  f"${cache_saved:.2f}", "↓ 41% cost reduction", "#a6e3a1"), unsafe_allow_html=True)
c4.markdown(_kpi("DLP Blocked",    str(dlp_blocked),     f"↓ {RNG.randint(2,5)} vs avg", "#a6e3a1"), unsafe_allow_html=True)
c5.markdown(_kpi("Remediations",   str(remediations),    "auto-healed", "#cba6f7"), unsafe_allow_html=True)

# ── Auto-generated insights strip ─────────────────────────────────────────────
_by_model = df24.groupby("model")["cost"].sum()
_top_model, _top_cost = _by_model.idxmax(), _by_model.max()
_peak_hour = df24.assign(h=df24["time"].dt.hour).groupby("h")["calls"].sum().idxmax()
st.markdown(
    f'<div style="background:#181825;border:1px solid #313244;border-radius:8px;'
    f'padding:8px 16px;margin-top:10px;color:#9399b2;font-size:0.86em;">'
    f'💡 <b style="color:#cdd6f4">Insights:</b> '
    f'Top cost driver is <b style="color:{M_COLOR[_top_model]}">{_top_model}</b> '
    f'(${_top_cost:.2f}, {_top_cost/total_cost*100:.0f}% of spend) · '
    f'peak traffic at <b style="color:#cdd6f4">{_peak_hour:02d}:00</b> · '
    f'semantic cache saved <b style="color:#a6e3a1">${cache_saved:.2f}</b> · '
    f'{dlp_blocked} DLP blocks &amp; {remediations} auto-remediations in 24h'
    f'</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Tabs
# ══════════════════════════════════════════════════════════════════════════════

tab_mc, tab_agent, tab_threat, tab_roi, tab_spl, tab_overview = st.tabs([
    "🎯 Mission Control",
    "🤖 AI Agent Lab",
    "🔴 Live Threat Feed",
    "💰 ROI Impact",
    "🔧 SPL Query Lab",
    "🏠 Splunk Overview",
])


# ══════════════════════════════════════════════════════════════════════════════
# Tab 1 — Mission Control
# ══════════════════════════════════════════════════════════════════════════════

with tab_mc:
    st.markdown('<div class="sec-header">Cost Over Time by Model (24h)</div>', unsafe_allow_html=True)

    cost_pivot = df24.groupby(["time", "model"])["cost"].sum().reset_index()
    fig_cost = px.line(
        cost_pivot, x="time", y="cost", color="model",
        color_discrete_map=M_COLOR,
        labels={"cost": "Cost (USD)", "time": "", "model": "Model"},
        template="plotly_dark",
    )
    fig_cost.update_layout(
        paper_bgcolor="#1e1e2e", plot_bgcolor="#181825",
        legend=dict(orientation="h", y=1.12),
        height=280, margin=dict(l=0, r=0, t=30, b=0),
    )
    fig_cost.update_traces(line_width=2.5)
    st.plotly_chart(fig_cost, width='stretch')

    col_l, col_m, col_r = st.columns([1, 1, 1])

    # Model distribution pie
    with col_l:
        st.markdown('<div class="sec-header">Model Distribution</div>', unsafe_allow_html=True)
        call_by_model = df24.groupby("model")["calls"].sum().reset_index()
        fig_pie = px.pie(
            call_by_model, values="calls", names="model",
            color="model", color_discrete_map=M_COLOR,
            hole=0.55, template="plotly_dark",
        )
        fig_pie.update_layout(
            paper_bgcolor="#1e1e2e", showlegend=True,
            legend=dict(orientation="h", y=-0.1),
            height=240, margin=dict(l=0, r=0, t=10, b=10),
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent")
        st.plotly_chart(fig_pie, width='stretch')

    # Cache hit/miss bar
    with col_m:
        st.markdown('<div class="sec-header">Cache Performance (24h)</div>', unsafe_allow_html=True)
        cache_hits   = int(total_calls * 0.41)
        cache_misses = total_calls - cache_hits
        fig_cache = go.Figure(go.Bar(
            x=["Cache Hit", "Cache Miss"],
            y=[cache_hits, cache_misses],
            marker_color=["#a6e3a1", "#f38ba8"],
            text=[f"{cache_hits:,}", f"{cache_misses:,}"],
            textposition="outside",
        ))
        fig_cache.update_layout(
            paper_bgcolor="#1e1e2e", plot_bgcolor="#181825",
            template="plotly_dark", showlegend=False,
            height=240, margin=dict(l=0, r=0, t=10, b=10),
            yaxis=dict(showgrid=False, visible=False),
        )
        st.plotly_chart(fig_cache, width='stretch')

    # Hourly anomaly heatmap
    with col_r:
        st.markdown('<div class="sec-header">Anomaly Density (24h)</div>', unsafe_allow_html=True)
        hours = list(range(24))
        anomaly_counts = [max(0, int(RNG.gauss(
            3 * math.exp(-0.5 * ((h - 14) / 4) ** 2) + 0.5, 0.8))) for h in hours]
        fig_heat = go.Figure(go.Bar(
            x=hours, y=anomaly_counts,
            marker=dict(
                color=anomaly_counts,
                colorscale=[[0, "#1e1e2e"], [0.5, "#fab387"], [1, "#f38ba8"]],
                showscale=False,
            ),
        ))
        fig_heat.update_layout(
            paper_bgcolor="#1e1e2e", plot_bgcolor="#181825",
            template="plotly_dark", showlegend=False,
            xaxis=dict(title="Hour"),
            yaxis=dict(title="Events", showgrid=False),
            height=240, margin=dict(l=0, r=0, t=10, b=10),
        )
        st.plotly_chart(fig_heat, width='stretch')

    # Latency percentile chart
    st.markdown('<div class="sec-header">Latency Distribution by Model (p50 / p95 / p99)</div>', unsafe_allow_html=True)
    lat_data = []
    for m in MODELS:
        base = {"gpt-4o": 650, "claude-sonnet-4": 480, "gemini-2.0-flash": 320, "gpt-4o-mini": 210}[m]
        lat_data.append({"model": m, "p50": base, "p95": int(base * 2.1), "p99": int(base * 3.4)})
    lat_df = pd.DataFrame(lat_data)

    fig_lat = go.Figure()
    for pct, color in [("p50", "#a6e3a1"), ("p95", "#fab387"), ("p99", "#f38ba8")]:
        fig_lat.add_trace(go.Bar(
            name=pct, x=lat_df["model"], y=lat_df[pct],
            marker_color=color, text=lat_df[pct].astype(str) + "ms",
            textposition="outside",
        ))
    fig_lat.update_layout(
        barmode="group",
        paper_bgcolor="#1e1e2e", plot_bgcolor="#181825",
        template="plotly_dark", legend=dict(orientation="h", y=1.1),
        height=260, margin=dict(l=0, r=0, t=30, b=0),
        yaxis=dict(title="Latency (ms)", showgrid=True, gridcolor="#313244"),
    )
    st.plotly_chart(fig_lat, width='stretch')


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2 — AI Agent Lab
# ══════════════════════════════════════════════════════════════════════════════

with tab_agent:
    st.markdown('<div class="sec-header">Run a Query — Agent Thinks Step by Step</div>',
                unsafe_allow_html=True)

    col_q, col_u = st.columns([5, 1])
    with col_q:
        query = st.text_input("Query", placeholder="e.g. What's the LLM cost in the last hour?",
                              label_visibility="collapsed")
    with col_u:
        user_id = st.text_input("User", "demo", label_visibility="collapsed")

    steps_area = st.empty()

    if st.button("▶ Run Agent", type="primary", width='stretch'):
        if not query.strip():
            st.warning("Enter a query.")
        else:
            t0 = time.time()
            with st.spinner(""):
                if demo_mode:
                    result = _demo_agent_run(query, steps_area)
                else:
                    r = _post(f"{mcpagents_url}/agent/run",
                              json={"query": query, "user_id": user_id},
                              headers={"X-MCP-Token": api_token} if api_token else None)
                    result = _safe_json(r, f"Backend unreachable at {mcpagents_url}")
                elapsed = time.time() - t0

            if result.get("success") is False or "error" in result:
                st.error(f"Agent error: {result}")
            else:
                st.success(f"✅ Completed in {elapsed:.2f}s")
                res_obj = result.get("result", {})
                if isinstance(res_obj, dict) and res_obj.get("response"):
                    st.info(f"**Agent:** {res_obj['response']}")
                    st.session_state.setdefault("agent_history", []).append({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "query": query,
                        "response": res_obj["response"],
                        "elapsed": f"{elapsed:.2f}s",
                    })
                tool_results = res_obj.get("tool_results", []) if isinstance(res_obj, dict) else []
                if tool_results:
                    st.markdown("**Tool Calls**")
                    for step in tool_results:
                        tool = step.get("tool", "?")
                        res  = step.get("result", "")
                        with st.expander(f"🔧 `{tool}`"):
                            st.json(res) if isinstance(res, dict) else st.code(str(res)[:2000])
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
        if q_cols[i].button(qp, key=f"qp_{i}", width='stretch'):
            ph = st.empty()
            r = _demo_agent_run(qp, ph) if demo_mode else {"success": False, "result": {"response": "Backend offline"}}
            res = r.get("result", {})
            if isinstance(res, dict) and res.get("response"):
                st.info(f"**Agent:** {res['response']}")
            for step in (res.get("tool_results", []) if isinstance(res, dict) else []):
                with st.expander(f"🔧 `{step.get('tool','?')}`"):
                    st.json(step.get("result", ""))

    if st.session_state.get("agent_history"):
        st.divider()
        st.markdown('<div class="sec-header">Session History</div>', unsafe_allow_html=True)
        for h in reversed(st.session_state["agent_history"][-5:]):
            with st.expander(f"🕐 {h['time']} — {h['query'][:60]}  ({h['elapsed']})"):
                st.markdown(f"**Agent:** {h['response']}")

    st.divider()
    st.markdown('<div class="sec-header">Agent Performance (24h)</div>', unsafe_allow_html=True)
    ap1, ap2, ap3, ap4 = st.columns(4)
    ap1.metric("Avg Latency",   f"{RNG.randint(320,480)}ms",  f"-{RNG.randint(5,15)}%")
    ap2.metric("Success Rate",  f"{RNG.uniform(96,99.5):.1f}%", "+0.8%")
    ap3.metric("Cost / Query",  f"${RNG.uniform(0.012,0.035):.4f}", "-12%")
    ap4.metric("Queries (24h)", f"{total_calls:,}", f"+{RNG.randint(5,18)}%")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3 — Live Threat Feed
# ══════════════════════════════════════════════════════════════════════════════

with tab_threat:
    col_tl, col_tr = st.columns([1.4, 1])

    # ── Left: Live DLP feed ──
    with col_tl:
        st.markdown('<div class="sec-header">DLP Violation Feed — Real-time</div>',
                    unsafe_allow_html=True)
        dlp_df = _gen_dlp_events(25)
        for _, row in dlp_df.head(12).iterrows():
            cls = {"HIGH": "alert-high", "MEDIUM": "alert-medium", "LOW": "alert-low"}[row.severity]
            soar_tag = " → 🛡️ SOAR triggered" if row.soar_triggered else ""
            st.markdown(
                f'<div class="{cls}">'
                f'<strong>{row["rule"]}</strong> &nbsp;|&nbsp; '
                f'<code>{row.action}</code> &nbsp;|&nbsp; '
                f'{row["time"].strftime("%H:%M:%S")} &nbsp;|&nbsp; '
                f'{row.user}{soar_tag}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Right: Severity donut + SOAR ──
    with col_tr:
        st.markdown('<div class="sec-header">Severity Breakdown</div>', unsafe_allow_html=True)
        sev_counts = dlp_df["severity"].value_counts().reset_index()
        sev_counts.columns = ["severity", "count"]
        sev_color = {"HIGH": "#f38ba8", "MEDIUM": "#fab387", "LOW": "#a6e3a1"}
        fig_sev = px.pie(
            sev_counts, values="count", names="severity",
            color="severity", color_discrete_map=sev_color,
            hole=0.6, template="plotly_dark",
        )
        fig_sev.update_layout(
            paper_bgcolor="#1e1e2e", height=220,
            margin=dict(l=0, r=0, t=0, b=0),
            showlegend=True, legend=dict(orientation="h", y=-0.1),
        )
        st.plotly_chart(fig_sev, width='stretch')

        st.markdown('<div class="sec-header">SOAR Auto-Response</div>', unsafe_allow_html=True)
        soar_actions = [
            ("mcp_block_user",        "Block high-risk user session",    "✅"),
            ("mcp_notify_security",   "Alert security team (Slack)",     "✅"),
            ("mcp_quarantine_session","Isolate session + revoke token",  "✅"),
            ("mcp_enrich_ioc",        "IOC enrichment & threat intel",   "⏳"),
        ]
        for pb, desc, status in soar_actions:
            st.markdown(f"{status} **`{pb}`** — {desc}")

    st.divider()

    # ── Auto-remediation simulator ──────────────────────────────────────────
    st.markdown('<div class="sec-header">Auto-Remediation Simulator — Fire an Anomaly Alert</div>',
                unsafe_allow_html=True)
    st.caption("Simulates: Splunk CDTS anomaly → POST /splunk/alert → auto-remediation policy engine")

    scenarios = {
        "💸 Cost Spike":     ("cost_spike",      9.2),
        "🐢 Latency Spike":  ("latency_spike",   6500),
        "❌ Error Rate":     ("error_rate_high",  0.25),
        "🚨 DLP Burst":      ("dlp_burst",        20),
        "📝 Token Overrun":  ("token_overrun", 150000),
    }
    s_cols = st.columns(len(scenarios))
    for i, (label, (atype, val)) in enumerate(scenarios.items()):
        with s_cols[i]:
            st.markdown(f"**{label}**")
            st.caption(f"`{atype}` = {val:,}")
            if st.button("Fire", key=f"fire_{atype}", width='stretch'):
                with st.spinner("Sending alert…"):
                    if demo_mode:
                        resp = _demo_alert(atype, val)
                    else:
                        r = _post(f"{mcpagents_url}/splunk/alert",
                                  json={"result": {"anomaly_type": atype, "metric_value": str(val)}},
                                  headers={"X-MCP-Token": api_token} if api_token else None)
                        resp = _safe_json(r, f"Backend unreachable at {mcpagents_url}")
                st.session_state[f"alert_{atype}"] = resp

    for label, (atype, _) in scenarios.items():
        key = f"alert_{atype}"
        if key in st.session_state:
            resp = st.session_state[key]
            with st.expander(f"✅ {label} — Remediation Result", expanded=True):
                if resp.get("handled"):
                    st.success(f"handled=True | value={resp.get('anomaly_value')} ≥ threshold={resp.get('threshold')}")
                    for act in resp.get("actions", []):
                        st.markdown(f"- **{act['action']}** → `{act['result']}`")
                    st.caption(f"Cooldown: {resp.get('cooldown_sec')}s | HEC event emitted to index=mcp_agents")
                else:
                    st.error(f"Alert not handled: {resp.get('error', resp)}")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 4 — ROI Impact
# ══════════════════════════════════════════════════════════════════════════════

with tab_roi:
    st.markdown('<div class="sec-header">Business Impact — Last 30 Days</div>',
                unsafe_allow_html=True)

    # Big impact numbers
    r1, r2, r3, r4 = st.columns(4)
    r1.markdown("""
    <div class="kpi-card">
      <div class="roi-number">$4,820</div>
      <div class="roi-label">LLM Cost Saved</div>
      <div class="kpi-delta-good">↓ 41% via cache + routing</div>
    </div>""", unsafe_allow_html=True)
    r2.markdown("""
    <div class="kpi-card">
      <div class="roi-number">347</div>
      <div class="roi-label">Threats Blocked</div>
      <div class="kpi-delta-good">↑ 0 data breaches</div>
    </div>""", unsafe_allow_html=True)
    r3.markdown("""
    <div class="kpi-card">
      <div class="roi-number">99.4%</div>
      <div class="roi-label">Agent Uptime</div>
      <div class="kpi-delta-good">14 auto-heals</div>
    </div>""", unsafe_allow_html=True)
    r4.markdown("""
    <div class="kpi-card">
      <div class="roi-number">8.3×</div>
      <div class="roi-label">ROI Multiplier</div>
      <div class="kpi-delta-good">vs baseline (no observability)</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_rl, col_rr = st.columns(2)

    # ── Cost comparison waterfall ──
    with col_rl:
        st.markdown('<div class="sec-header">Cost Reduction Waterfall (30d)</div>',
                    unsafe_allow_html=True)
        wf = go.Figure(go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "relative", "relative", "total"],
            x=["Baseline Cost", "Semantic Cache", "Smart Routing", "Rate Limiting", "Final Cost"],
            y=[11750, -2820, -1420, -690, 0],
            connector={"line": {"color": "#313244"}},
            increasing={"marker": {"color": "#f38ba8"}},
            decreasing={"marker": {"color": "#a6e3a1"}},
            totals={"marker": {"color": "#89b4fa"}},
            text=["$11,750", "-$2,820", "-$1,420", "-$690", "$6,820"],
            textposition="outside",
        ))
        wf.update_layout(
            paper_bgcolor="#1e1e2e", plot_bgcolor="#181825",
            template="plotly_dark", showlegend=False,
            height=300, margin=dict(l=0, r=0, t=20, b=0),
            yaxis=dict(title="Cost (USD)", gridcolor="#313244"),
        )
        st.plotly_chart(wf, width='stretch')

    # ── Daily savings trend ──
    with col_rr:
        st.markdown('<div class="sec-header">Daily Savings Trend (30d)</div>',
                    unsafe_allow_html=True)
        days = pd.date_range(end=datetime.now(), periods=30, freq="D")
        baseline = [RNG.uniform(360, 420) for _ in range(30)]
        actual   = [b * RNG.uniform(0.54, 0.62) for b in baseline]
        fig_sav = go.Figure()
        fig_sav.add_trace(go.Scatter(
            x=days, y=baseline, name="Baseline", line=dict(color="#f38ba8", width=2, dash="dash"),
            fill=None,
        ))
        fig_sav.add_trace(go.Scatter(
            x=days, y=actual, name="With MCPAgents", line=dict(color="#a6e3a1", width=2.5),
            fill="tonexty", fillcolor="rgba(166,227,161,0.12)",
        ))
        fig_sav.update_layout(
            paper_bgcolor="#1e1e2e", plot_bgcolor="#181825",
            template="plotly_dark", legend=dict(orientation="h", y=1.1),
            height=300, margin=dict(l=0, r=0, t=30, b=0),
            yaxis=dict(title="Daily Cost (USD)", gridcolor="#313244"),
        )
        st.plotly_chart(fig_sav, width='stretch')

    # ── Architecture closed-loop explanation ──
    st.divider()
    st.markdown('<div class="sec-header">How the Closed Loop Works</div>', unsafe_allow_html=True)
    st.plotly_chart(_arch_diagram(), width='stretch')
    col_l1, col_l2, col_l3 = st.columns(3)
    col_l1.markdown("**① Query path** — NL query → SPL translation → Splunk search → results injected back into agent context")
    col_l2.markdown("**② Observability loop** — Every LLM call emits HEC event → `index=mcp_agents` → CDTS anomaly detect → `/splunk/alert` → auto-remediation")
    col_l3.markdown("**③ Security path** — DLP scans every tool output in realtime → HIGH violation → Foundation-sec SOAR playbook")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 5 — SPL Query Lab
# ══════════════════════════════════════════════════════════════════════════════

with tab_spl:
    st.markdown('<div class="sec-header">Interactive SPL Query Lab</div>', unsafe_allow_html=True)
    st.caption("Write or pick a query → results render as a chart + table.")

    presets = {
        "Cost by model (24h)":      "index=mcp_agents event_type=mcp_llm_call | stats sum(cost_usd) as cost by model | sort - cost",
        "DLP violations (1h)":      "index=mcp_agents event_type=mcp_dlp_violation | table _time,rule_id,sensitivity,action_taken | sort - _time",
        "Cache hit rate":           "index=mcp_agents (event_type=mcp_cache_hit OR mcp_cache_miss) | stats count by event_type",
        "Anomaly timeline":         "index=mcp_agents event_type=mcp_anomaly | table _time,anomaly_type,current_value,threshold | sort - _time",
        "Router decisions":         "index=mcp_agents event_type=mcp_router_decision | stats count by selected_model",
        "P95 latency by model":     "index=mcp_agents event_type=mcp_llm_call | stats perc95(latency_ms) as p95 by model | sort - p95",
        "Hourly cost trend":        "index=mcp_agents event_type=mcp_llm_call | timechart span=1h sum(cost_usd) by model",
        "Top users by cost":        "index=mcp_agents event_type=mcp_llm_call | stats sum(cost_usd) as cost by user_id | sort - cost | head 10",
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
    run_query  = run_col.button("▶ Run Query", type="primary", width='stretch')

    if run_query:
        with st.spinner("Running…"):
            time.sleep(0.4)  # simulate round-trip

        range_hours = {"-1h": 1, "-6h": 6, "-24h": 24, "-7d": 168}[q_range]
        df_range = _gen_timeseries(hours=range_hours)
        st.caption(f"⏱ earliest={q_range} · {len(df_range):,} raw events scanned")

        # ── Generate contextual demo results ──
        if "cost" in selected.lower() and "model" in selected.lower() and "timechart" not in selected.lower():
            result_df = df_range.groupby("model")["cost"].sum().reset_index()
            result_df.columns = ["model", "cost"]
            result_df = result_df.sort_values("cost", ascending=False)
            fig = px.bar(result_df, x="model", y="cost", color="model",
                         color_discrete_map=M_COLOR, template="plotly_dark",
                         labels={"cost": "Total Cost (USD)"})

        elif "cache" in selected.lower():
            result_df = pd.DataFrame({"event_type": ["mcp_cache_hit", "mcp_cache_miss"],
                                       "count": [int(total_calls * 0.41), int(total_calls * 0.59)]})
            fig = px.bar(result_df, x="event_type", y="count",
                         color="event_type",
                         color_discrete_map={"mcp_cache_hit": "#a6e3a1", "mcp_cache_miss": "#f38ba8"},
                         template="plotly_dark")

        elif "router" in selected.lower():
            result_df = df24.groupby("model")["calls"].sum().reset_index()
            result_df.columns = ["selected_model", "count"]
            fig = px.pie(result_df, values="count", names="selected_model",
                         color="selected_model", color_discrete_map=M_COLOR,
                         hole=0.5, template="plotly_dark")

        elif "latency" in selected.lower() or "p95" in selected.lower():
            lat = [{"model": m,
                    "p95": {"gpt-4o":1380,"claude-sonnet-4":990,"gemini-2.0-flash":650,"gpt-4o-mini":430}[m]}
                   for m in MODELS]
            result_df = pd.DataFrame(lat).sort_values("p95", ascending=False)
            fig = px.bar(result_df, x="model", y="p95", color="model",
                         color_discrete_map=M_COLOR, template="plotly_dark",
                         labels={"p95": "P95 Latency (ms)"})

        elif "timechart" in selected.lower() or "hourly" in selected.lower():
            result_df = df_range.groupby(["time", "model"])["cost"].sum().reset_index()
            fig = px.line(result_df, x="time", y="cost", color="model",
                          color_discrete_map=M_COLOR, template="plotly_dark",
                          labels={"cost": "Cost (USD)", "time": ""})

        elif "dlp" in selected.lower():
            dlp = _gen_dlp_events(20)
            result_df = dlp[["time", "rule", "severity", "action", "user"]].copy()
            result_df["time"] = result_df["time"].dt.strftime("%H:%M:%S")
            fig = px.histogram(dlp, x="severity", color="severity",
                               color_discrete_map={"HIGH":"#f38ba8","MEDIUM":"#fab387","LOW":"#a6e3a1"},
                               template="plotly_dark")

        else:
            result_df = _gen_events(30)[["_time","event_type","model","cost_usd","latency_ms"]]
            fig = px.histogram(result_df, x="event_type", template="plotly_dark",
                               color="event_type")

        fig.update_layout(
            paper_bgcolor="#1e1e2e", plot_bgcolor="#181825",
            height=280, margin=dict(l=0, r=0, t=20, b=0),
            showlegend=True, legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig, width='stretch')
        st.dataframe(result_df, width='stretch', height=200)
        st.download_button(
            "⬇ Export results (CSV)",
            result_df.to_csv(index=False).encode("utf-8"),
            file_name="spl_results.csv", mime="text/csv",
        )

        with st.expander("📋 SPL Query (copy)"):
            st.code(spl_query, language="text")

    # ── Quick reference ──
    st.divider()
    st.markdown('<div class="sec-header">SPL Quick Reference — index=mcp_agents</div>',
                unsafe_allow_html=True)
    ref_data = {
        "event_type values": "mcp_llm_call · mcp_router_decision · mcp_cache_hit · mcp_cache_miss · mcp_dlp_violation · mcp_anomaly · mcp_agent_complete",
        "Key fields":        "model · cost_usd · latency_ms · prompt_tokens · completion_tokens · rule_id · sensitivity · action_taken · anomaly_type · current_value · threshold",
        "Useful aggregations": "stats sum(cost_usd) · stats perc95(latency_ms) · timechart span=1h · eval hit_rate=round(hits/total*100,1)",
    }
    for key, val in ref_data.items():
        st.markdown(f"**{key}:** `{val}`")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 6 — Splunk Overview (embedded Dashboard Studio dashboard)
# ══════════════════════════════════════════════════════════════════════════════

with tab_overview:
    import os, re
    st.markdown('<div class="sec-header">Splunk Dashboard — LLMai Agentic Ops</div>',
                unsafe_allow_html=True)
    st.caption("Splunk Dashboard Studio over `index=mcp_agents` — closed-loop "
               "observability: cost · routing · cache · DLP · anomaly→remediation.")

    _img = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "assets", "splunk_dashboard.png")
    if os.path.exists(_img):
        st.image(_img, width='stretch',
                 caption="Splunk Dashboard Studio — index=mcp_agents (live snapshot)")
    else:
        st.info(
            "📸 Add a screenshot at `assets/splunk_dashboard.png` to show the "
            "Splunk dashboard here. Easiest: open the dashboard in Splunk → "
            "top-right **Download → PNG** → save it to that path → commit."
        )
    st.markdown("[↗ Open the live Splunk dashboard](%s)" % SPLUNK_DASHBOARD_URL)

    with st.expander("Live embed instead of snapshot (local Splunk only)"):
        raw = st.text_area(
            "Splunk dashboard URL  —  or paste the full <iframe …> Embed snippet",
            SPLUNK_DASHBOARD_URL, key="spl_embed_src", height=80,
            help="A view URL, a Splunk Embed token URL, or the entire "
                 "<iframe src=...> snippet from Splunk's Embed dialog.")
        _m = re.search(r'''src=["']([^"']+)["']''', raw or "")
        spl_url = (_m.group(1) if _m else (raw or "").strip()) or SPLUNK_DASHBOARD_URL
        st.caption(
            "Renders only with local Splunk reachable **and** framing allowed. "
            "Disable Splunk frame-blocking (docker): "
            "`docker exec mcpagents-splunk bash -lc \"printf "
            "'[settings]\\nx_frame_options_sameorigin = false\\n' >> "
            "/opt/splunk/etc/system/local/web.conf\"` then "
            "`docker restart mcpagents-splunk`. "
            "Cloud note: localhost:8000 is the Streamlit server, not your PC. "
            "[↗ Open in a new tab](%s)" % spl_url
        )
        st.iframe(spl_url, height=900)


# ══════════════════════════════════════════════════════════════════════════════
# Auto-refresh
# ══════════════════════════════════════════════════════════════════════════════

if auto_refresh:
    time.sleep(10)
    st.rerun()
