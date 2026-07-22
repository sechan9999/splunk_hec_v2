"""Headless smoke tests for the demo app (Streamlit AppTest, no browser).

Committed deliberately: an unreproducible test count in a submission is worth
less than a smaller number anyone can run. Everything asserted here is
verifiable with `pytest tests/test_app_smoke.py`.

The Data Context tab gets the most attention because for most readers the
demo *is* the product — a governance claim that cannot be seen on screen is
a claim the reader has to take on faith.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

AppTest = pytest.importorskip("streamlit.testing.v1",
                              reason="streamlit not installed").AppTest

APP = str(Path(__file__).parent.parent / "demo_app.py")
DATA_CONTEXT_TAB = 5
EXPECTED_TABS = 7


@pytest.fixture(scope="module")
def app():
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    return at


def _tab_text(at, index=DATA_CONTEXT_TAB):
    tab = at.tabs[index]
    parts = [m.value for m in tab.markdown]
    parts += [e.value for e in tab.success] + [e.value for e in tab.info]
    return " ".join(parts)


# ----------------------------------------------------------------------
# The app runs at all
# ----------------------------------------------------------------------

def test_app_renders_without_exception(app):
    assert not app.exception


def test_app_has_all_tabs(app):
    assert len(app.tabs) == EXPECTED_TABS


def test_demo_mode_needs_no_datahub_credentials(app):
    """Demo Mode must work with zero configuration — that is its whole job."""
    assert not app.exception
    assert [r.label for r in app.sidebar.radio] == ["Mode"]


def test_kpis_render(app):
    assert len(app.metric) >= 1


# ----------------------------------------------------------------------
# Data Context tab — where the governance story is visible
# ----------------------------------------------------------------------

def test_data_context_tab_offers_every_demo_dataset(app):
    options = app.tabs[DATA_CONTEXT_TAB].selectbox[0].options
    for name in ("visitors", "patients_pii", "legacy_metrics", "user_events_v1"):
        assert name in options, f"{name} missing from the Data Context selector"


def test_clean_dataset_shows_allow(app):
    text = _tab_text(app)
    assert "ALLOW" in text


@pytest.mark.parametrize("dataset,expected", [
    ("legacy_metrics", "BLOCK"),
    ("user_events_v1", "BLOCK"),
    ("user_features_v1", "WARN"),
    ("visitors", "ALLOW"),
])
def test_verdict_is_shown_per_dataset(dataset, expected):
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    at.tabs[DATA_CONTEXT_TAB].selectbox[0].set_value(dataset).run()
    assert not at.exception
    assert expected in _tab_text(at), (
        f"{dataset} should render a {expected} verdict")


def test_block_with_known_successor_shows_the_redirect():
    """The claim 'a block tells you where to go instead' must be on screen."""
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    at.tabs[DATA_CONTEXT_TAB].selectbox[0].set_value("user_events_v1").run()
    text = _tab_text(at)
    assert "user_events_v2" in text, "successor not surfaced in the UI"
    assert "confidence" in text.lower(), "suggestion shown without its confidence"


def test_block_without_a_successor_says_so_instead_of_guessing():
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    at.tabs[DATA_CONTEXT_TAB].selectbox[0].set_value("legacy_metrics").run()
    text = _tab_text(at)
    assert "No successor" in text
    assert "user_events_v2" not in text, "suggested a successor for the wrong dataset"


def test_regulated_dataset_access_is_visible_even_when_allowed():
    """Permitted is not the same as unremarkable."""
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    at.tabs[DATA_CONTEXT_TAB].selectbox[0].set_value("patients_pii").run()
    text = _tab_text(at).lower()
    assert "hipaa" in text, "a regulated-data read left nothing on screen"
