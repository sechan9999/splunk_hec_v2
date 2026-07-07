"""Global CSS for the Agentic Ops Control Center (dark glassmorphism theme)."""
import streamlit as st

CSS = """
<style>
/* Global */
html, body, [data-testid="stApp"] { background: #11111b; }

/* KPI cards */
.kpi-card {
    background: #1e1e2e; border-radius: 12px; padding: 20px 24px;
    border: 1px solid #313244; text-align: center;
    box-shadow: 0 4px 20px rgba(0,0,0,0.4);
}
.kpi-value { font-size: 2.2em; font-weight: 800; margin: 0; }
.kpi-label { font-size: 0.78em; color: #6c7086; margin-top: 4px; letter-spacing: 0.05em; text-transform: uppercase; }
.kpi-delta-good { color: #a6e3a1; font-size: 0.85em; }
.kpi-delta-bad  { color: #f38ba8; font-size: 0.85em; }

/* Section header */
.sec-header {
    font-size: 1.05em; font-weight: 700; color: #cdd6f4;
    letter-spacing: 0.04em; margin-bottom: 4px;
    border-left: 3px solid #cba6f7; padding-left: 10px;
}

/* Demo / Live badges */
.demo-badge {
    background: linear-gradient(135deg,#f5a623,#f7c948);
    color:#11111b; padding:3px 10px; border-radius:10px;
    font-weight:800; font-size:0.72em;
}
.live-badge {
    background: linear-gradient(135deg,#f38ba8,#eba0ac);
    color:#11111b; padding:3px 10px; border-radius:10px;
    font-weight:800; font-size:0.72em;
}

/* Journey cards (first-screen guide) */
.journey-card {
    background: #181825; border: 1px solid #313244; border-radius: 10px;
    padding: 12px 16px; height: 100%; font-size: 0.86em; color: #bac2de;
}
.journey-card b { color: #cdd6f4; }
.journey-title {
    font-size: 0.78em; font-weight: 800; letter-spacing: 0.06em;
    text-transform: uppercase; color: #cba6f7; margin-bottom: 6px;
}

/* Connection status pills */
.conn-ok   { color:#a6e3a1; font-size:0.85em; }
.conn-bad  { color:#f38ba8; font-size:0.85em; }
.conn-na   { color:#6c7086; font-size:0.85em; }

/* Step pill */
.step-pill {
    display:inline-block; background:#313244; border-radius:20px;
    padding:4px 14px; margin:3px 2px; font-size:0.82em; color:#cdd6f4;
}
.step-pill.done  { background:#1e3a2f; color:#a6e3a1; border:1px solid #a6e3a1; }
.step-pill.run   { background:#2a1e3a; color:#cba6f7; border:1px solid #cba6f7; }

/* Alert rows */
.alert-high   { border-left: 4px solid #f38ba8; padding: 8px 12px; background: #2a1e24; border-radius: 4px; margin: 4px 0; }
.alert-medium { border-left: 4px solid #fab387; padding: 8px 12px; background: #2a2218; border-radius: 4px; margin: 4px 0; }
.alert-low    { border-left: 4px solid #a6e3a1; padding: 8px 12px; background: #1e2a22; border-radius: 4px; margin: 4px 0; }

/* ROI number */
.roi-number { font-size:3em; font-weight:900; color:#a6e3a1; }
.roi-label  { color:#6c7086; font-size:0.85em; text-transform:uppercase; letter-spacing:0.06em; }

/* Insights strip */
.insights-strip {
    background:#181825; border:1px solid #313244; border-radius:8px;
    padding:8px 16px; margin-top:10px; color:#9399b2; font-size:0.86em;
}
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)
