"""Scan one configured source (all its search URLs and pages)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .config import SourceConfig
from .extract import combine, listing_from_card, listings_from_json
from .models import Listing

log = logging.getLogger(__name__)

# Per site: listing link pattern (group 1 = id), which API responses to capture,
# and an element that shows results have rendered.
SITE_DEFAULTS = {
    "yad2": {
        "link_pattern": r"yad2\.co\.il/(?:realestate/)?item/(?:[^/?#]+/)*([A-Za-z0-9]{5,20})(?=[/?#]|$)",
        "json_capture": r"gw\.yad2\.co\.il|yad2\.co\.il/api",
        "wait_selector": 'a[href*="/item/"]',
    },
    "madlan": {
        "link_pattern": r"madlan\.co\.il/listings/([A-Za-z0-9_-]{4,40})",
        "json_capture": r"madlan\.co\.il/api",
        "wait_selector": 'a[href*="/listings/"]',
    },
    "generic": {"link_pattern": "", "json_capture": "", "wait_selector": ""},
}


@dataclass
class SourceResult:
    source: SourceConfig
    listings: list[Listing] = field(default_factory=list)
    pages: int = 0
    blocked: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.pages > 0 and not self.blocked

    @property
    def status(self) -> str:
        if self.blocked:
            return "blocked"
        if not self.pages:
            return "failed"
        if not self.listings:
            return "empty"
        return "ok"


def with_page(url: str, param: str, page: int) -> str:
    if page <= 1:
        return url
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != param]
    query.append((param, str(page)))
    return urlunsplit(parts._replace(query=urlencode(query)))


def scan_source(browser, source: SourceConfig) -> SourceResult:
    defaults = SITE_DEFAULTS[source.type]
    link_pattern = source.link_pattern or defaults["link_pattern"]
    wait_selector = source.wait_selector or defaults["wait_selector"]
    result = SourceResult(source=source)
    collected: dict[str, Listing] = {}

    for url in source.urls:
        for page_no in range(1, max(1, source.max_pages) + 1):
            page_url = with_page(url, source.page_param, page_no)
            log.info("[%s] loading %s", source.name, page_url)
            page = browser.fetch(page_url, link_pattern=link_pattern, json_capture=defaults["json_capture"],
                                 wait_selector=wait_selector, scrolls=source.scrolls,
                                 label=f"{source.name}_p{page_no}")
            if page.blocked:
                result.blocked = True
                result.errors.append(f"blocked by anti-bot check: {page_url}")
                log.warning("[%s] blocked - skipping the rest of this source", source.name)
                return _finish(result, collected)
            if page.error:
                result.errors.append(page.error)
                break
            result.pages += 1

            from_json = listings_from_json(source.type, source.name, page.states + page.payloads)
            from_cards = {}
            for card in page.cards:
                listing = listing_from_card(source.name, card)
                from_cards[listing.id] = listing
            found = combine(from_json, from_cards)
            fresh = [lid for lid in found if lid not in collected]
            log.info("[%s] page %d: %d listings (%d from data, %d cards), %d new this run",
                     source.name, page_no, len(found), len(from_json), len(from_cards), len(fresh))
            for lid, listing in found.items():
                if lid in collected:
                    collected[lid].merge_missing(listing)
                else:
                    collected[lid] = listing
            if not fresh:
                break  # empty page, or the site ignores the page parameter
    return _finish(result, collected)


def _finish(result: SourceResult, collected: dict[str, Listing]) -> SourceResult:
    result.listings = list(collected.values())
    return result
