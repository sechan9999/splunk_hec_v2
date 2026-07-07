"""HTTP client for live-mode backends.

TLS verification is ON by default. Setting verify_ssl=False is an explicit,
per-session opt-in intended only for local dev against self-signed Splunk
certs; the insecure-request warning is suppressed only in that case, never
globally.
"""
import warnings
from dataclasses import dataclass

import requests


@dataclass
class BackendConfig:
    mcpagents_url: str = "http://localhost:8001"
    api_token: str = ""
    splunk_rest: str = "https://localhost:8089"
    splunk_user: str = ""
    splunk_pass: str = ""
    hec_url: str = "http://localhost:8088"
    splunk_index: str = "mcp_agents"
    soar_webhook: str = ""
    verify_ssl: bool = True

    @property
    def auth_headers(self):
        return {"X-MCP-Token": self.api_token} if self.api_token else None


def _request(method, url, cfg, timeout, **kw):
    try:
        with warnings.catch_warnings():
            if not cfg.verify_ssl:
                # scoped to this request only, and only when explicitly opted in
                import urllib3
                warnings.simplefilter(
                    "ignore", urllib3.exceptions.InsecureRequestWarning)
            return requests.request(method, url, timeout=timeout,
                                    verify=cfg.verify_ssl, **kw)
    except Exception:
        return None


def get(url, cfg, timeout=5, **kw):
    return _request("GET", url, cfg, timeout, **kw)


def post(url, cfg, timeout=30, **kw):
    return _request("POST", url, cfg, timeout, **kw)


def safe_json(resp, fallback_error):
    """Parse a response defensively -- backend may be down or non-JSON."""
    if resp is None or not resp.ok:
        return {"success": False, "handled": False, "error": fallback_error}
    try:
        return resp.json()
    except Exception:
        return {"success": False, "handled": False,
                "error": f"Non-JSON response (HTTP {resp.status_code})"}


def check_connections(cfg):
    """Probe each backend separately. Returns {service: (state, detail)} where
    state is 'ok', 'fail', or 'unconfigured'."""
    status = {}

    r = get(f"{cfg.mcpagents_url}/health", cfg)
    status["MCPAgents API"] = (
        ("ok", f"HTTP {r.status_code}") if r is not None and r.ok
        else ("fail", "unreachable" if r is None else f"HTTP {r.status_code}"))

    r = get(f"{cfg.hec_url}/services/collector/health", cfg)
    status["Splunk HEC"] = (
        ("ok", "healthy") if r is not None and r.ok
        else ("fail", "unreachable" if r is None else f"HTTP {r.status_code}"))

    if cfg.splunk_user:
        r = get(f"{cfg.splunk_rest}/services/server/info?output_mode=json",
                cfg, auth=(cfg.splunk_user, cfg.splunk_pass))
        status["Splunk REST"] = (
            ("ok", "authenticated") if r is not None and r.ok
            else ("fail", "unreachable" if r is None else f"HTTP {r.status_code}"))
    else:
        status["Splunk REST"] = ("unconfigured", "no credentials")

    # Never ping a SOAR webhook -- a probe could trigger a playbook.
    status["Splunk SOAR"] = (
        ("ok", "webhook configured") if cfg.soar_webhook
        else ("unconfigured", "no webhook URL"))

    return status
