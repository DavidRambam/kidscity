"""One scan: load every source, filter, compare with last time, notify, save."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import notify
from .config import Config
from .filters import filter_listings, merge_cross_posts
from .report import RunSummary, SourceSummary, render_html
from .sources import scan_source
from .state import NEW, PRICE_DROP, State

log = logging.getLogger(__name__)
ISRAEL = ZoneInfo("Asia/Jerusalem")


def run_scan(cfg: Config, browser_factory, *, only: set[str] | None = None, dry_run: bool = False,
             now: datetime | None = None) -> RunSummary:
    now = now or datetime.now(ISRAEL)
    state = State(cfg.state_file)
    run = RunSummary(started=now, first_run=state.is_empty())
    sources = [s for s in cfg.sources if s.enabled and s.urls and (not only or s.name in only)]
    run.source_labels = {s.name: s.display_name for s in cfg.sources}
    if not sources:
        log.error("No enabled sources with URLs in the config.")
        return run

    matched_all = []
    with browser_factory() as browser:
        for source in sources:
            try:
                result = scan_source(browser, source)
            except Exception as exc:  # keep going with the other sites
                log.exception("[%s] crashed", source.name)
                run.sources.append(SourceSummary(source.name, "failed", errors=[str(exc)]))
                continue
            matched, skipped = filter_listings(result.listings, cfg.search)
            log.info("[%s] %d scanned, %d match; skipped: %s", source.name, len(result.listings),
                     len(matched), dict(skipped) or "-")
            run.sources.append(SourceSummary(source.name, result.status, len(result.listings),
                                             len(matched), skipped, result.errors))
            matched_all.extend(matched)

    new, drops = [], []
    for listing in matched_all:
        status = state.classify(listing, cfg.search.price_drop_pct)
        if status == NEW:
            similar = state.find_similar(listing)
            if similar:
                seen_on = similar.get("first_seen", "")[:10]
                label = run.source_labels.get(similar.get("source", ""), similar.get("source", ""))
                listing.similar_to = f"{label} {seen_on}".strip()
            new.append(listing)
        elif status == PRICE_DROP:
            drops.append(listing)

    run.new = merge_cross_posts(new)
    run.drops = drops
    run.matches = merge_cross_posts(list(matched_all))
    log.info("Result: %d new, %d price drops, %d matching in total", len(run.new), len(run.drops),
             len(run.matches))

    write_reports(cfg.reports_dir, run, cfg.notify.language)

    if dry_run:
        log.info("Dry run - nothing sent, nothing saved.")
        return run

    should_send = run.has_news or run.problems or cfg.notify.notify_when_empty
    delivered = notify.deliver(run, cfg.notify.language, cfg.notify.telegram_individual_limit) \
        if should_send else True
    if delivered:
        for listing in matched_all:
            state.remember(listing, now)
        pruned = state.prune(now)
        if pruned:
            log.info("Forgot %d listings not seen for 90 days", pruned)
        state.save()
    else:
        log.error("Nothing was delivered - listings stay 'new' and will be retried next run.")
    return run


def write_reports(reports_dir: Path, run: RunSummary, lang: str) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    page = render_html(run, lang, include_all=True)
    latest = reports_dir / "latest.html"
    latest.write_text(page, encoding="utf-8")
    (reports_dir / f"{run.started:%Y-%m-%d_%H%M}.html").write_text(page, encoding="utf-8")
    log.info("Report: %s", latest)
    return latest
