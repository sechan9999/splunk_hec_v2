"""Plotly chart builders with the shared dark theme."""
import plotly.express as px
import plotly.graph_objects as go

from demo_data import MODELS, M_COLOR

PAPER = "#1e1e2e"
PLOT = "#181825"


def dark(fig, height=280, legend_y=1.1, show_legend=True):
    fig.update_layout(
        paper_bgcolor=PAPER, plot_bgcolor=PLOT, template="plotly_dark",
        height=height, margin=dict(l=0, r=0, t=30, b=0),
        showlegend=show_legend,
        legend=dict(orientation="h", y=legend_y),
    )
    return fig


def cost_line(df):
    pivot = df.groupby(["time", "model"])["cost"].sum().reset_index()
    fig = px.line(pivot, x="time", y="cost", color="model",
                  color_discrete_map=M_COLOR,
                  labels={"cost": "Cost (USD)", "time": "", "model": "Model"},
                  template="plotly_dark")
    fig.update_traces(line_width=2.5)
    return dark(fig, legend_y=1.12)


def model_pie(df):
    calls = df.groupby("model")["calls"].sum().reset_index()
    fig = px.pie(calls, values="calls", names="model", color="model",
                 color_discrete_map=M_COLOR, hole=0.55, template="plotly_dark")
    fig.update_traces(textposition="inside", textinfo="percent")
    return dark(fig, height=240, legend_y=-0.1)


def cache_bar(hits, misses):
    fig = go.Figure(go.Bar(
        x=["Cache Hit", "Cache Miss"], y=[hits, misses],
        marker_color=["#a6e3a1", "#f38ba8"],
        text=[f"{hits:,}", f"{misses:,}"], textposition="outside"))
    fig.update_yaxes(showgrid=False, visible=False)
    return dark(fig, height=240, show_legend=False)


def anomaly_heat(hours, counts):
    fig = go.Figure(go.Bar(
        x=hours, y=counts,
        marker=dict(color=counts,
                    colorscale=[[0, "#1e1e2e"], [0.5, "#fab387"], [1, "#f38ba8"]],
                    showscale=False)))
    fig.update_xaxes(title="Hour")
    fig.update_yaxes(title="Events", showgrid=False)
    return dark(fig, height=240, show_legend=False)


def latency_bars(lat_df):
    fig = go.Figure()
    for pct, color in [("p50", "#a6e3a1"), ("p95", "#fab387"), ("p99", "#f38ba8")]:
        fig.add_trace(go.Bar(
            name=pct, x=lat_df["model"], y=lat_df[pct], marker_color=color,
            text=lat_df[pct].astype(str) + "ms", textposition="outside"))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="Latency (ms)", showgrid=True, gridcolor="#313244")
    return dark(fig, height=260)


def roi_waterfall(baseline, cache_saved, routing_saved, ratelimit_saved):
    final = baseline - cache_saved - routing_saved - ratelimit_saved
    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute", "relative", "relative", "relative", "total"],
        x=["Baseline Cost", "Semantic Cache", "Smart Routing",
           "Rate Limiting", "Final Cost"],
        y=[baseline, -cache_saved, -routing_saved, -ratelimit_saved, 0],
        connector={"line": {"color": "#313244"}},
        increasing={"marker": {"color": "#f38ba8"}},
        decreasing={"marker": {"color": "#a6e3a1"}},
        totals={"marker": {"color": "#89b4fa"}},
        text=[f"${baseline:,.0f}", f"-${cache_saved:,.0f}",
              f"-${routing_saved:,.0f}", f"-${ratelimit_saved:,.0f}",
              f"${final:,.0f}"],
        textposition="outside"))
    fig.update_yaxes(title="Cost (USD)", gridcolor="#313244")
    return dark(fig, height=300, show_legend=False)


def savings_trend(days, baseline, actual):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=days, y=baseline, name="Baseline",
        line=dict(color="#f38ba8", width=2, dash="dash"), fill=None))
    fig.add_trace(go.Scatter(
        x=days, y=actual, name="With MCPAgents",
        line=dict(color="#a6e3a1", width=2.5),
        fill="tonexty", fillcolor="rgba(166,227,161,0.12)"))
    fig.update_yaxes(title="Daily Cost (USD)", gridcolor="#313244")
    return dark(fig, height=300)


def arch_diagram():
    """Closed-loop architecture diagram (agent <-> Splunk)."""
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
    nodes = [
        (3.8, 6.4, 6.2, 7.1, "user",   "👤 User Query",        ""),
        (0.2, 4.6, 4.4, 5.7, "agent",  "🤖 AdvancedMCPAgent",  "Multi-LLM Router"),
        (5.6, 4.6, 9.8, 5.7, "splunk", "🔍 Splunk MCP Tool",   "REST API + NL to SPL"),
        (0.2, 2.9, 3.8, 3.9, "hec",    "📡 HEC Telemetry",     "index=mcp_agents"),
        (6.2, 2.9, 9.8, 3.9, "dlp",    "🛡️ DLP Engine",        "Realtime PII scan"),
        (0.2, 1.3, 3.8, 2.3, "cdts",   "🔎 Splunk CDTS",       "Anomaly Detection"),
        (6.2, 1.3, 9.8, 2.3, "fsec",   "🏛️ Foundation-sec",    "SOAR Playbook"),
        (2.8, 0.0, 5.8, 1.0, "alert",  "⚡ /splunk/alert",     "Auto-Remediation"),
        (6.2, 0.0, 9.8, 1.0, "soar",   "🛡️ SOAR",              "Playbook Triggered"),
    ]

    shapes, annotations = [], []
    for x0, y0, x1, y1, style, top, bot in nodes:
        fill, border = C[style]
        shapes.append(dict(type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
                           fillcolor=fill, line=dict(color=border, width=1.8),
                           xref="x", yref="y"))
        label = f"<b>{top}</b>" + (f"<br><sub>{bot}</sub>" if bot else "")
        annotations.append(dict(
            x=(x0 + x1) / 2, y=(y0 + y1) / 2, text=label, showarrow=False,
            xref="x", yref="y", align="center",
            font=dict(color=border, size=11, family="monospace")))

    def arrow(x0, y0, x1, y1, label="", color="#585b70"):
        annotations.append(dict(
            x=x1, y=y1, ax=x0, ay=y0,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=3, arrowsize=1.3,
            arrowwidth=1.6, arrowcolor=color, text=label,
            font=dict(color=color, size=9), bgcolor="rgba(17,17,27,0.7)"))

    arrow(5.0, 6.4, 2.3, 5.7)
    arrow(4.4, 5.25, 5.6, 5.35, "1. NL to SPL", "#a6e3a1")
    arrow(5.6, 5.05, 4.4, 4.95, "results", "#a6e3a1")
    arrow(2.3, 4.6, 2.0, 3.9, "2. HEC emit", "#cba6f7")
    arrow(4.4, 5.15, 6.2, 3.7, "3. DLP scan", "#f38ba8")
    arrow(2.0, 2.9, 2.0, 2.3, "anomaly?", "#89b4fa")
    arrow(8.0, 2.9, 8.0, 2.3, "violation", "#f38ba8")
    arrow(3.0, 1.3, 4.0, 1.0, "trigger", "#fab387")
    arrow(5.8, 0.55, 6.2, 0.55, "playbook", "#fab387")

    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor=PLOT, plot_bgcolor=PLOT,
        shapes=shapes, annotations=annotations,
        xaxis=dict(visible=False, range=[-0.3, 10.3]),
        yaxis=dict(visible=False, range=[-0.4, 7.6]),
        height=480, margin=dict(l=10, r=10, t=10, b=10))
    return fig
