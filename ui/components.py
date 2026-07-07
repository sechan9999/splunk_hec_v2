"""Reusable HTML/Streamlit UI components."""
import time

import streamlit as st


def kpi(label, value, delta=None, color="#cdd6f4", delta_good=True):
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


def sec_header(text):
    st.markdown(f'<div class="sec-header">{text}</div>', unsafe_allow_html=True)


def journey_section():
    """First-screen guide: what this is, what to try, why Splunk. Kept compact."""
    j1, j2, j3 = st.columns(3)
    j1.markdown("""
    <div class="journey-card">
      <div class="journey-title">What this demonstrates</div>
      A <b>closed loop</b>: a local AI agent streams its own telemetry
      (cost, latency, DLP, errors) into Splunk - and Splunk reaches back to
      <b>auto-remediate</b> anomalies by re-weighting the agent's model router.
    </div>""", unsafe_allow_html=True)
    j2.markdown("""
    <div class="journey-card">
      <div class="journey-title">Try these 3 actions</div>
      1. <b>AI Agent Lab</b>: ask "LLM cost last hour?"<br>
      2. <b>Live Threat Feed</b>: press <b>Fire</b> on Cost Spike<br>
      3. <b>SPL Query Lab</b>: run a preset, export CSV
    </div>""", unsafe_allow_html=True)
    j3.markdown("""
    <div class="journey-card">
      <div class="journey-title">Why Splunk + DataHub matter</div>
      Splunk HEC ingests 8 agent event types; CDTS detects anomalies; SOAR
      responds to DLP. DataHub adds the metadata brain: guardrails consult
      ownership/quality before the agent acts, and violations are written
      back to the context graph.
    </div>""", unsafe_allow_html=True)


def insights_strip(top_model, top_model_color, top_cost, total_cost,
                   peak_hour, cache_saved, dlp_blocked, remediations):
    st.markdown(
        f'<div class="insights-strip">'
        f'💡 <b style="color:#cdd6f4">Insights:</b> '
        f'Top cost driver is <b style="color:{top_model_color}">{top_model}</b> '
        f'(${top_cost:.2f}, {top_cost / total_cost * 100:.0f}% of spend) · '
        f'peak traffic at <b style="color:#cdd6f4">{peak_hour:02d}:00</b> · '
        f'semantic cache saved <b style="color:#a6e3a1">${cache_saved:.2f}</b> · '
        f'{dlp_blocked} DLP blocks &amp; {remediations} auto-remediations in 24h'
        f'</div>', unsafe_allow_html=True)


def stream_steps(placeholder, steps, delay=0.45):
    """Animate the agent tool-loop step pills."""
    done = []
    for name, desc in steps:
        with placeholder.container():
            pills = "".join(
                f'<span class="step-pill done">✓ {d}</span>' for d in done)
            pills += f'<span class="step-pill run">⟳ {name}</span>'
            st.markdown(pills, unsafe_allow_html=True)
            st.caption(f"▶ {desc}")
        time.sleep(delay)
        done.append(name)
    with placeholder.container():
        pills = "".join(f'<span class="step-pill done">✓ {d}</span>' for d in done)
        st.markdown(pills, unsafe_allow_html=True)


def dlp_alert_row(row):
    cls = {"HIGH": "alert-high", "MEDIUM": "alert-medium",
           "LOW": "alert-low"}[row.severity]
    soar_tag = " → 🛡️ SOAR triggered" if row.soar_triggered else ""
    st.markdown(
        f'<div class="{cls}">'
        f'<strong>{row["rule"]}</strong> &nbsp;|&nbsp; '
        f'<code>{row.action}</code> &nbsp;|&nbsp; '
        f'{row["time"].strftime("%H:%M:%S")} &nbsp;|&nbsp; '
        f'{row.user}{soar_tag}'
        f'</div>',
        unsafe_allow_html=True)


def connection_status(status):
    """Render per-service connection badges from backend_client.check_connections."""
    icon = {"ok": "🟢", "fail": "🔴", "unconfigured": "⚪"}
    cls = {"ok": "conn-ok", "fail": "conn-bad", "unconfigured": "conn-na"}
    for service, (state, detail) in status.items():
        st.markdown(
            f'{icon[state]} <span class="{cls[state]}">'
            f'<b>{service}</b> — {detail}</span>',
            unsafe_allow_html=True)
