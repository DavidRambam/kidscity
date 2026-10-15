"""Decide which listings match the search."""
from __future__ import annotations

from collections import Counter
from typing import Iterable

from .config import SearchConfig
from .hebrew import contains_phrase, find_deal
from .models import Listing


def match_city(listing: Listing, cities: dict[str, list[str]]) -> str | None:
    """Canonical city name if the listing is in one of the configured cities."""
    if not cities:
        return listing.city or ""
    if listing.city:
        for canonical, aliases in cities.items():
            if any(contains_phrase(listing.city, a) for a in aliases):
                return canonical
        return None
    haystack = " ".join(p for p in (listing.neighborhood, listing.street, listing.title, listing.text) if p)
    for canonical, aliases in cities.items():
        if any(contains_phrase(haystack, a) for a in aliases):
            return canonical
    return None


def evaluate(listing: Listing, cfg: SearchConfig) -> str | None:
    """None if the listing matches; otherwise a short reason it was skipped.

    Side effects on match: normalizes listing.city, sets listing.deal / near_match.
    """
    text = " ".join(p for p in (listing.title, listing.text) if p)

    for word in cfg.exclude_keywords:
        if contains_phrase(text, word):
            return "excluded keyword"

    # Deal type: explicit data first, then very-high price (sale), then text.
    if not listing.deal:
        if listing.price and listing.price >= cfg.sale_price_threshold:
            listing.deal = "sale"
        else:
            listing.deal = find_deal(text)
    if cfg.deal != "any" and listing.deal and listing.deal != cfg.deal:
        return f"deal is {listing.deal}"
    if cfg.deal == "rent" and listing.price and listing.price >= cfg.sale_price_threshold:
        return "price looks like a sale"

    city = match_city(listing, cfg.cities)
    if city is None:
        return "other city"
    if city:
        listing.city = city

    if listing.sqm is None:
        if not cfg.include_unknown_size:
            return "size unknown"
    else:
        tolerance = (cfg.size_tolerance_pct or 0) / 100
        low = cfg.min_sqm * (1 - tolerance) if cfg.min_sqm else None
        high = cfg.max_sqm * (1 + tolerance) if cfg.max_sqm else None
        if (low and listing.sqm < low) or (high and listing.sqm > high):
            return "size out of range"
        listing.near_match = bool(
            (cfg.min_sqm and listing.sqm < cfg.min_sqm) or (cfg.max_sqm and listing.sqm > cfg.max_sqm))

    if listing.price is None:
        if not cfg.include_unknown_price:
            return "price unknown"
    else:
        if cfg.max_price and listing.price > cfg.max_price:
            return "too expensive"
        if cfg.min_price and listing.price < cfg.min_price:
            return "too cheap"

    if listing.property_type:
        if cfg.property_types and listing.property_type not in cfg.property_types:
            return f"type {listing.property_type}"
    elif not cfg.include_unknown_type:
        return "type unknown"

    return None


def filter_listings(listings: Iterable[Listing], cfg: SearchConfig) -> tuple[list[Listing], Counter]:
    matched: list[Listing] = []
    reasons: Counter = Counter()
    for listing in listings:
        reason = evaluate(listing, cfg)
        if reason:
            reasons[reason] += 1
        else:
            matched.append(listing)
    return matched, reasons


def merge_cross_posts(listings: list[Listing]) -> list[Listing]:
    """Collapse the same property posted several times (same city, size and price)."""
    by_fp: dict[str, Listing] = {}
    out: list[Listing] = []
    for listing in listings:
        fp = listing.fingerprint()
        if fp and fp in by_fp:
            primary = by_fp[fp]
            if listing.url not in primary.also_on and listing.url != primary.url:
                primary.also_on.append(listing.url)
            primary.merge_missing(listing)
            continue
        if fp:
            by_fp[fp] = listing
        out.append(listing)
    return out
