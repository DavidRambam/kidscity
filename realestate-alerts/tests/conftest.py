import re
from pathlib import Path

import pytest

from alerts.config import load_config

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def cfg():
    """The real config.yaml shipped with the project."""
    return load_config(ROOT / "config.yaml")


def embedded_state(name: str) -> list[str]:
    """The JSON a browser would read from window state / __NEXT_DATA__ in a fixture page."""
    html = (FIXTURES / name).read_text(encoding="utf-8")
    out = re.findall(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    out += re.findall(r"window\.__SSR_HYDRATED_CONTEXT__ = (.*?);</script>", html, re.S)
    return out
