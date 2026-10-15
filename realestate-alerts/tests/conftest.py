import re
from pathlib import Path

import pytest

from alerts.config import SearchConfig, load_config

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Fixed search for the tests, so editing config.yaml never breaks them.
TEST_SEARCH = SearchConfig(
    min_sqm=200, max_sqm=300, size_tolerance_pct=10,
    property_types=["shop", "warehouse", "building", "industrial", "hall", "office"],
    cities={
        "חיפה": ["חיפה", "haifa", "קרית חיים"],
        "קרית ביאליק": ["קרית ביאליק"],
        "קרית מוצקין": ["קרית מוצקין"],
        "קרית אתא": ["קרית אתא"],
        "קרית ים": ["קרית ים"],
    },
    exclude_keywords=["דרוש", "מחפש"],
)


@pytest.fixture
def cfg():
    """The project's config.yaml (sources, browser...) with the fixed test search."""
    config = load_config(ROOT / "config.yaml")
    config.search = TEST_SEARCH
    return config


def embedded_state(name: str) -> list[str]:
    """The JSON a browser would read from window state / __NEXT_DATA__ in a fixture page."""
    html = (FIXTURES / name).read_text(encoding="utf-8")
    out = re.findall(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    out += re.findall(r"window\.__SSR_HYDRATED_CONTEXT__ = (.*?);</script>", html, re.S)
    return out
