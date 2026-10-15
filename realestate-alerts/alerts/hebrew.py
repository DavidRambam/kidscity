"""Parsing helpers for Hebrew listing text: prices, sizes, floors, property types."""
from __future__ import annotations

import re

_PUNCT_RE = re.compile(r"[\"'״׳`\-–—_,.()/\\|:;!?]+")
_SPACE_RE = re.compile(r"\s+")
_KIRYAT_ABBR_RE = re.compile(r"(?<![א-ת])ק\.\s*")  # "ק. ביאליק" -> "קרית ביאליק"


def normalize(text: str | None) -> str:
    """Lower-case, unify spelling variants and drop punctuation (for matching only)."""
    if not text:
        return ""
    text = str(text).replace("קריית", "קרית")
    text = _KIRYAT_ABBR_RE.sub("קרית ", text)
    text = _PUNCT_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip().lower()


def contains_phrase(haystack: str, phrase: str) -> bool:
    """Whole-word match of an already-normalized phrase inside normalized text."""
    phrase = normalize(phrase)
    return bool(phrase) and f" {phrase} " in f" {normalize(haystack)} "


# --- numbers --------------------------------------------------------------

_NUM = r"\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?"


def to_number(value) -> float | None:
    """'18,000 ₪' -> 18000.0, 250 -> 250.0, 'לא צוין' -> None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    match = re.search(_NUM, str(value))
    if not match:
        return None
    number = float(match.group(0).replace(",", ""))
    return number if number > 0 else None


def to_int(value) -> int | None:
    number = to_number(value)
    return int(round(number)) if number is not None else None


_CURRENCY = r"(?:₪|ש\"ח|ש״ח|ש''ח|שח\b|nis\b|ils\b)"
_PRICE_RES = [
    re.compile(rf"{_CURRENCY}\s*:?\s*({_NUM})", re.I),
    re.compile(rf"({_NUM})\s*{_CURRENCY}", re.I),
    re.compile(rf"(?:מחיר|שכירות|שכ\"ד|שכ״ד|דמי שכירות)\s*:?\s*({_NUM})"),
]


def find_price(text: str) -> int | None:
    for regex in _PRICE_RES:
        match = regex.search(text or "")
        if match:
            price = to_int(match.group(1))
            if price and price >= 100:
                return price
    return None


_SQM_UNIT = r"(?:מ\"ר|מ״ר|מ''ר|מ'ר|מ׳ר|מ\.ר|מטר רבוע|מטרים רבועים|מר\b|sqm\b|sq\.?\s?m\b|m2\b|m²)"
_SQM_AFTER = re.compile(rf"(\d{{1,3}}(?:,\d{{3}})+|\d{{2,5}}(?:\.\d{{1,2}})?)\s*{_SQM_UNIT}", re.I)
_SQM_BEFORE = re.compile(
    rf"(?:{_SQM_UNIT}|שטח(?:\s+בנוי)?|גודל(?:\s+הנכס)?)\s*:?\s*(\d{{1,3}}(?:,\d{{3}})+|\d{{2,5}}(?:\.\d{{1,2}})?)",
    re.I,
)
_METERS_LOOSE = re.compile(r"(\d{2,5})\s*(?:מטר|מטרים|מ׳|מ')(?![\"״'׳]?ר)")
_HEIGHT_BEFORE = re.compile(r"(?:גובה|תקרה|תקרת|מרחק|במרחק)\s*\S{0,6}\s*$")
_DISTANCE_AFTER = re.compile(r"^\s*(?:גובה|מה|מן|ממ|ליד|מהים|מהכביש|הליכה|עד)")


def find_sqm(text: str) -> float | None:
    """Size in m². Avoids ceiling heights ("גובה 7 מטר") and distances ("200 מטר מהים")."""
    text = text or ""
    for regex in (_SQM_AFTER, _SQM_BEFORE):
        match = regex.search(text)
        if match:
            value = to_number(match.group(1))
            if value and value >= 5:
                return value
    for match in _METERS_LOOSE.finditer(text):
        before = text[max(0, match.start() - 14): match.start()]
        after = text[match.end(): match.end() + 8]
        value = to_number(match.group(1))
        if value and value >= 30 and not _HEIGHT_BEFORE.search(before) and not _DISTANCE_AFTER.search(after):
            return value
    return None


_FLOOR_RE = re.compile(r"קומה\s*:?\s*(-?\d+|קרקע|מרתף|כניסה)")


def find_floor(text: str) -> str:
    match = _FLOOR_RE.search(text or "")
    return match.group(1) if match else ""


def find_deal(text: str) -> str:
    text = text or ""
    rent = "להשכרה" in text or "השכרה" in text or "for rent" in text.lower()
    sale = "למכירה" in text or "for sale" in text.lower()
    if rent and not sale:
        return "rent"
    if sale and not rent:
        return "sale"
    return ""


# --- property types ---------------------------------------------------------

# (canonical type, keywords). Multi-word keywords win over shorter ones that
# start at the same place ("מבנה תעשייה" is industrial, not "מבנה").
_TYPE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("industrial", ["מבנה תעשייה", "מבנה תעשיה", "תעשייה", "תעשיה", "מפעל", "סדנה", "סדנא",
                    "מוסך", "בית מלאכה", "industrial", "factory", "workshop", "garage"]),
    ("warehouse", ["מחסן", "מחסנים", "מרלו\"ג", "מרלוג", "לוגיסטי", "warehouse", "storage", "logistic"]),
    ("hall", ["אולם תצוגה", "אולם", "showroom", "hall"]),
    ("shop", ["חנות", "חנויות", "שטח מסחרי", "שטחי מסחר", "מסעדה", "בית קפה", "קיוסק",
              "retail", "shop", "store", "restaurant", "commercial space"]),
    ("office", ["משרד", "משרדים", "קליניקה", "קליניקות", "מרפאה", "office", "clinic"]),
    ("building", ["מבנה מסחרי", "מבנה", "בניין", "בנין", "building"]),
    ("land", ["מגרש", "קרקע", "land", "plot"]),
    ("parking", ["חניה", "חנייה", "חניון", "parking"]),
]


def classify_type(text: str | None) -> str:
    """Return the canonical property type mentioned first in the text, or ''."""
    if not text:
        return ""
    lowered = str(text).lower()
    best: tuple[int, int, str] | None = None  # (position, -keyword length, type)
    for canonical, keywords in _TYPE_KEYWORDS:
        for keyword in keywords:
            pos = lowered.find(keyword.lower())
            if pos < 0:
                continue
            candidate = (pos, -len(keyword), canonical)
            if best is None or candidate < best:
                best = candidate
    return best[2] if best else ""
