"""Phase 11 — dark-mode theme config smoke test.

Locks that .streamlit/config.toml parses and carries both the light default (top-level [theme]) and
the on-brand [theme.dark] variant with its core palette keys. Not a visual check (that's recorded QA
in the running app, §14) — just that the config is well-formed and the dark theme exists.
"""

import tomllib
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml"


def _theme() -> dict:
    return tomllib.loads(CONFIG.read_text())["theme"]


def test_light_default_unchanged():
    theme = _theme()
    assert theme["base"] == "light"
    assert theme["backgroundColor"] == "#f3ece1"  # quilt-backing paper
    assert "font" in theme and "headingFont" in theme  # shared faces, inherited by dark


def test_dark_theme_present_and_on_brand():
    dark = _theme()["dark"]
    assert dark["base"] == "dark"
    # core palette keys present and dark (not Streamlit's stock dark)
    for key in (
        "primaryColor",
        "backgroundColor",
        "secondaryBackgroundColor",
        "textColor",
        "linkColor",
        "borderColor",
    ):
        assert dark[key].startswith("#")
    assert dark["backgroundColor"] == "#111a26"  # deep ink navy
    assert dark["textColor"] == "#f3ece1"  # brand paper-cream as text (continuity with light)
