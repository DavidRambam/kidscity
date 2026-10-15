"""Message and report formatting (Hebrew by default, English optional)."""
from __future__ import annotations

import html
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from .models import Listing

_HEBREW_RE = re.compile(r"[֐-׿]")

LABELS = {
    "he": {
        "new": "🆕 נכס חדש",
        "drop": "📉 ירידת מחיר",
        "price_na": "מחיר לא צוין",
        "month": "לחודש",
        "sqm": "מ\"ר",
        "per_sqm": "למ\"ר",
        "floor": "קומה",
        "agency": "תיווך",
        "private": "פרטי",
        "near": "קרוב לטווח",
        "also": "פורסם גם כאן",
        "similar": "🔁 ייתכן שזה אותו נכס שנשלח כבר",
        "view": "לצפייה במודעה",
        "was": "היה",
        "arrow": "←",
        "new_section": "🆕 נכסים חדשים",
        "drop_section": "📉 ירידות מחיר",
        "title": "🏢 נדל\"ן מסחרי - חיפה והקריות",
        "first_run": "סריקה ראשונה - כל הנכסים המתאימים שנמצאו כרגע",
        "new_count": "חדשים: {n}",
        "drop_count": "ירידות מחיר: {n}",
        "nothing_new": "אין נכסים חדשים מאז הסריקה הקודמת",
        "source_line": "{name}: נסרקו {scanned}, מתאימים {matched}",
        "blocked": "⚠️ {name}: נחסם ע\"י בדיקת אנטי-בוט",
        "failed": "⚠️ {name}: הטעינה נכשלה",
        "empty": "⚠️ {name}: לא נמצאו מודעות - ייתכן שהאתר שינה מבנה",
        "all_matches": "כל הנכסים המתאימים בסריקה הזו",
        "sources": "מקורות",
        "more": "ועוד {n}...",
        "types": {"shop": "חנות", "warehouse": "מחסן", "building": "מבנה", "industrial": "מבנה תעשייה",
                  "hall": "אולם", "office": "משרד", "land": "קרקע", "parking": "חניה", "": "נכס מסחרי"},
    },
    "en": {
        "new": "🆕 New listing",
        "drop": "📉 Price drop",
        "price_na": "price not stated",
        "month": "per month",
        "sqm": "m²",
        "per_sqm": "per m²",
        "floor": "floor",
        "agency": "agency",
        "private": "private",
        "near": "close to range",
        "also": "also posted at",
        "similar": "🔁 possibly the same property sent before",
        "view": "Open listing",
        "was": "was",
        "arrow": "→",
        "new_section": "🆕 New listings",
        "drop_section": "📉 Price drops",
        "title": "🏢 Commercial real estate - Haifa & Krayot",
        "first_run": "First scan - everything that matches right now",
        "new_count": "new: {n}",
        "drop_count": "price drops: {n}",
        "nothing_new": "Nothing new since the last scan",
        "source_line": "{name}: scanned {scanned}, matching {matched}",
        "blocked": "⚠️ {name}: blocked by an anti-bot check",
        "failed": "⚠️ {name}: failed to load",
        "empty": "⚠️ {name}: no listings found - the site may have changed",
        "all_matches": "All matching listings in this scan",
        "sources": "Sources",
        "more": "and {n} more...",
        "types": {"shop": "Shop", "warehouse": "Warehouse", "building": "Building",
                  "industrial": "Industrial building", "hall": "Hall", "office": "Office",
                  "land": "Land", "parking": "Parking", "": "Commercial property"},
    },
}


@dataclass
class SourceSummary:
    name: str
    status: str  # ok / empty / blocked / failed
    scanned: int = 0
    matched: int = 0
    skipped: Counter = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)


@dataclass
class RunSummary:
    started: datetime
    new: list[Listing] = field(default_factory=list)
    drops: list[Listing] = field(default_factory=list)
    matches: list[Listing] = field(default_factory=list)
    sources: list[SourceSummary] = field(default_factory=list)
    first_run: bool = False
    source_labels: dict[str, str] = field(default_factory=dict)

    @property
    def problems(self) -> list[SourceSummary]:
        return [s for s in self.sources if s.status != "ok"]

    @property
    def has_news(self) -> bool:
        return bool(self.new or self.drops)


def L(lang: str) -> dict:
    return LABELS.get(lang, LABELS["he"])


def money(value: int | None) -> str:
    return f"₪{value:,}" if value else ""


def sqm_str(value: float | None) -> str:
    if not value:
        return ""
    return f"{int(value)}" if float(value).is_integer() else f"{value:.1f}"


def type_label(listing: Listing, lang: str) -> str:
    raw = listing.property_type_raw
    if raw and (_HEBREW_RE.search(raw) or not listing.property_type):
        return raw
    return L(lang)["types"].get(listing.property_type, L(lang)["types"][""])


def headline(listing: Listing, lang: str) -> str:
    lab = L(lang)
    parts = [type_label(listing, lang)]
    if listing.sqm:
        size = f"{sqm_str(listing.sqm)} {lab['sqm']}"
        parts.append(f"{size} (≈ {lab['near']})" if listing.near_match else size)
    parts.append(f"{money(listing.price)} {lab['month']}" if listing.price else lab["price_na"])
    return " · ".join(parts)


def location(listing: Listing, lang: str) -> str:
    place = ", ".join(p for p in (listing.street, listing.neighborhood, listing.city) if p)
    if listing.floor not in ("", None):
        place = f"{place} · {L(lang)['floor']} {listing.floor}" if place else f"{L(lang)['floor']} {listing.floor}"
    return place


def details(listing: Listing, lang: str, source_label: str) -> str:
    lab = L(lang)
    parts = []
    if listing.price_per_sqm:
        parts.append(f"{money(listing.price_per_sqm)} {lab['per_sqm']}")
    if listing.is_agency is not None:
        parts.append(lab["agency"] if listing.is_agency else lab["private"])
    parts.append(source_label)
    return " · ".join(parts)


# --- Telegram (HTML parse mode) --------------------------------------------

def _tg(text: str) -> str:
    return html.escape(text, quote=False)


def telegram_listing(listing: Listing, lang: str, source_label: str, kind: str = "new") -> str:
    lab = L(lang)
    e = _tg
    lines = [f"{lab['drop'] if kind == 'drop' else lab['new']}", f"<b>{e(headline(listing, lang))}</b>"]
    if kind == "drop" and listing.price_drop_from:
        lines.append(f"{lab['was']} {money(listing.price_drop_from)} {lab['arrow']} {money(listing.price)}")
    place = location(listing, lang)
    if place:
        lines.append(f"📍 {e(place)}")
    lines.append(f"💰 {e(details(listing, lang, source_label))}")
    if listing.similar_to:
        lines.append(f"{lab['similar']}: {e(listing.similar_to)}")
    lines.append(f'🔗 <a href="{html.escape(listing.url)}">{lab["view"]}</a>')
    for url in listing.also_on:
        lines.append(f'↪️ <a href="{html.escape(url)}">{lab["also"]}</a>')
    return "\n".join(lines)


def telegram_digest_line(listing: Listing, lang: str, source_label: str) -> str:
    e = _tg
    text = headline(listing, lang)
    place = ", ".join(p for p in (listing.neighborhood, listing.city) if p)
    if place:
        text += f" - {place}"
    if listing.price_drop_from:
        text = f"📉 {text} ({L(lang)['was']} {money(listing.price_drop_from)})"
    return f'• <a href="{html.escape(listing.url)}">{e(text)}</a> ({e(source_label)})'


def summary_lines(run: RunSummary, lang: str) -> list[str]:
    lab = L(lang)
    lines = [lab["title"], run.started.strftime("%d/%m/%Y %H:%M")]
    if run.first_run:
        lines.append(lab["first_run"])
    counts = []
    if run.new:
        counts.append(lab["new_count"].format(n=len(run.new)))
    if run.drops:
        counts.append(lab["drop_count"].format(n=len(run.drops)))
    lines.append(" · ".join(counts) if counts else lab["nothing_new"])
    for source in run.sources:
        name = run.source_labels.get(source.name, source.name)
        if source.status == "ok":
            lines.append(lab["source_line"].format(name=name, scanned=source.scanned, matched=source.matched))
        else:
            lines.append(lab[source.status].format(name=name))
    return lines


def telegram_summary(run: RunSummary, lang: str) -> list[str]:
    lines = [_tg(line) for line in summary_lines(run, lang)]
    lines[0] = f"<b>{lines[0]}</b>"
    return lines


def chunk_lines(lines: list[str], limit: int = 3800, sep: str = "\n") -> list[str]:
    chunks, current = [], ""
    for line in lines:
        line = line[:limit]
        candidate = f"{current}{sep}{line}" if current else line
        if len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


# --- plain text (email text part, WhatsApp) ---------------------------------

def plain_listing(listing: Listing, lang: str, source_label: str) -> str:
    lines = [headline(listing, lang)]
    if listing.price_drop_from:
        lines[0] = f"📉 {lines[0]} ({L(lang)['was']} {money(listing.price_drop_from)})"
    place = location(listing, lang)
    if place:
        lines.append(place)
    lines.append(f"{details(listing, lang, source_label)}")
    lines.append(listing.url)
    return "\n".join(lines)


def plain_text(run: RunSummary, lang: str) -> str:
    blocks = ["\n".join(summary_lines(run, lang))]
    for listing in run.drops + run.new:
        blocks.append(plain_listing(listing, lang, run.source_labels.get(listing.source, listing.source)))
    return "\n\n".join(blocks)


# --- HTML (email + local report) --------------------------------------------

_CSS = """
:root { color-scheme: light dark; --bg:#f6f7f9; --card:#fff; --ink:#1d2433; --muted:#5b6475;
  --line:#e3e6ec; --accent:#0b6bcb; --warn:#a15c00; --near:#6b4fbb; }
@media (prefers-color-scheme: dark) { :root { --bg:#14171c; --card:#1d2128; --ink:#e8ebf0;
  --muted:#9aa3b2; --line:#2c323c; --accent:#5aa9ff; --warn:#f0b35a; --near:#b9a5ff; } }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 system-ui, -apple-system,
  "Segoe UI", Arial, sans-serif; }
main { max-width:760px; margin:0 auto; padding:20px 16px 40px; }
h1 { font-size:20px; margin:0 0 4px; } h2 { font-size:16px; margin:28px 0 10px; }
.meta, .muted { color:var(--muted); font-size:13px; }
.warn { color:var(--warn); }
.card { display:flex; gap:12px; background:var(--card); border:1px solid var(--line);
  border-radius:10px; padding:12px; margin:0 0 10px; }
.card img { width:120px; height:90px; object-fit:cover; border-radius:6px; flex:none; }
.card b { display:block; font-size:15px; }
.near { color:var(--near); font-size:12px; }
a { color:var(--accent); }
@media (max-width:480px) { .card { flex-direction:column; } .card img { width:100%; height:160px; } }
"""


def _html_card(listing: Listing, lang: str, source_label: str) -> str:
    e = html.escape
    lab = L(lang)
    img = f'<img src="{e(listing.image, quote=True)}" alt="" loading="lazy">' if listing.image else ""
    drop = (f'<div>{lab["drop"]}: {lab["was"]} {money(listing.price_drop_from)} {lab["arrow"]} {money(listing.price)}</div>'
            if listing.price_drop_from else "")
    similar = f'<div class="muted">{lab["similar"]}: {e(listing.similar_to)}</div>' if listing.similar_to else ""
    also = "".join(f' · <a href="{e(u, quote=True)}">{lab["also"]}</a>' for u in listing.also_on)
    return (
        f'<div class="card">{img}<div>'
        f'<b>{e(headline(listing, lang))}</b>{drop}'
        f'<div>{e(location(listing, lang))}</div>'
        f'<div class="muted">{e(details(listing, lang, source_label))}</div>{similar}'
        f'<div><a href="{e(listing.url, quote=True)}">{lab["view"]}</a>{also}</div>'
        f'</div></div>'
    )


def render_html(run: RunSummary, lang: str, include_all: bool = True) -> str:
    e = html.escape
    lab = L(lang)
    direction = "rtl" if lang == "he" else "ltr"
    summary = summary_lines(run, lang)
    label = lambda l: run.source_labels.get(l.source, l.source)  # noqa: E731
    parts = [
        f'<!doctype html><html lang="{lang}" dir="{direction}"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{e(summary[0])}</title><style>{_CSS}</style></head><body><main>",
        f"<h1>{e(summary[0])}</h1>",
    ]
    parts += [f'<div class="{"warn" if line.startswith("⚠️") else "meta"}">{e(line)}</div>' for line in summary[1:]]
    if run.drops:
        parts.append(f"<h2>{lab['drop_section']}</h2>")
        parts += [_html_card(l, lang, label(l)) for l in run.drops]
    if run.new:
        parts.append(f"<h2>{lab['new_section']}</h2>")
        parts += [_html_card(l, lang, label(l)) for l in run.new]
    if include_all and run.matches:
        parts.append(f"<h2>{lab['all_matches']} ({len(run.matches)})</h2>")
        parts += [_html_card(l, lang, label(l)) for l in run.matches]
    parts.append("</main></body></html>")
    return "\n".join(parts)
