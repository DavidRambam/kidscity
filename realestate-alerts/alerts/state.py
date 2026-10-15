"""Remembers which listings were already sent, so each one is reported once."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from .models import Listing

NEW, PRICE_DROP, SEEN = "new", "price_drop", "seen"


class State:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data: dict = {"version": 1, "listings": {}}
        if self.path.is_file():
            with open(self.path, encoding="utf-8") as fh:
                self.data = json.load(fh)
            self.data.setdefault("listings", {})

    @property
    def listings(self) -> dict[str, dict]:
        return self.data["listings"]

    def is_empty(self) -> bool:
        return not self.listings

    def classify(self, listing: Listing, drop_pct: float) -> str:
        previous = self.listings.get(listing.key)
        if previous is None:
            return NEW
        old_price = previous.get("price")
        if old_price and listing.price and listing.price <= old_price * (1 - drop_pct / 100):
            listing.price_drop_from = old_price
            return PRICE_DROP
        return SEEN

    def find_similar(self, listing: Listing) -> dict | None:
        """An earlier listing (different id) with the same city, size and price."""
        fp = listing.fingerprint()
        if not fp:
            return None
        for key, entry in self.listings.items():
            if key != listing.key and entry.get("fp") == fp:
                return entry
        return None

    def remember(self, listing: Listing, now: datetime) -> None:
        stamp = now.isoformat(timespec="seconds")
        entry = self.listings.get(listing.key)
        if entry is None:
            entry = self.listings[listing.key] = {"first_seen": stamp}
        entry.update({
            "last_seen": stamp,
            "source": listing.source,
            "url": listing.url,
            "price": listing.price if listing.price else entry.get("price"),
            "sqm": listing.sqm,
            "city": listing.city,
            "title": listing.title[:140],
            "fp": listing.fingerprint(),
        })

    def prune(self, now: datetime, keep_days: int = 90) -> int:
        cutoff = (now - timedelta(days=keep_days)).isoformat(timespec="seconds")
        stale = [k for k, v in self.listings.items() if v.get("last_seen", "") < cutoff]
        for key in stale:
            del self.listings[key]
        return len(stale)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, self.path)
