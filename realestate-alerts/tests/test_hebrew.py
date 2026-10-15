import pytest

from alerts.hebrew import classify_type, find_deal, find_floor, find_price, find_sqm, normalize, to_int


@pytest.mark.parametrize("text, expected", [
    ("₪ 18,000", 18000),
    ("18,000 ₪", 18000),
    ("מחיר: 9500", 9500),
    ('שכ"ד 12,500 ש"ח לחודש', 12500),
    ("לא צוין מחיר", None),
    ("חנות | חיפה | 250 מ״ר | קומה 0 | ₪ 18,000", 18000),
])
def test_find_price(text, expected):
    assert find_price(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("250 מ״ר", 250),
    ('שטח 230 מ"ר', 230),
    ("מ\"ר: 210", 210),
    ("מחסן 1,200 מ\"ר", 1200),
    ("אולם 280 מטר רבוע", 280),
    ("מחסן 250 מטר, גובה 7 מטר", 250),
    ("גובה תקרה 12 מטר, 220 מטרים", 220),       # ceiling height is not the size
    ("200 מטר מהים, חנות", None),                # a distance, not a size
    ("חנות של כ-300 sqm", 300),
    ("חנות במרכז העיר", None),
])
def test_find_sqm(text, expected):
    assert find_sqm(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("חנות להשכרה בהדר", "shop"),
    ("מבנה תעשייה במפרץ", "industrial"),
    ("מבנה להשכרה", "building"),
    ("מחסן לוגיסטי", "warehouse"),
    ("משרדים בבניין מסחרי", "office"),
    ("אולם תצוגה", "hall"),
    ("office", "office"),
    ("Warehouse", "warehouse"),
    ("", ""),
    ("נכס", ""),
])
def test_classify_type(text, expected):
    assert classify_type(text) == expected


def test_normalize_spelling_variants():
    assert normalize("קריית ביאליק") == normalize("קרית-ביאליק") == normalize("ק. ביאליק")
    assert normalize("צ'ק פוסט") == "צ ק פוסט"
    assert "שוק" in normalize("שוק.")  # abbreviation rule must not eat other words


def test_misc():
    assert to_int("12,000 ₪") == 12000
    assert to_int(0) is None
    assert find_floor("קומה 2 מתוך 4") == "2"
    assert find_floor("קומה: קרקע") == "קרקע"
    assert find_deal("חנות להשכרה") == "rent"
    assert find_deal("חנות למכירה") == "sale"
    assert find_deal("להשכרה או למכירה") == ""
