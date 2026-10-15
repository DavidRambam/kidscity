"""A real browser (Playwright) that loads search pages the way a person would.

Yad2 (Radware) and Madlan (PerimeterX / Cloudflare) block plain HTTP scrapers,
so pages are loaded in Chromium with a persistent profile: once a challenge is
passed (automatically, or by you in a visible window), its cookies are reused.
"""
from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import BrowserConfig

log = logging.getLogger(__name__)

# Text that only shows up on anti-bot / block pages.
CHALLENGE_TITLES = ("radware page", "shieldsquare", "access denied", "just a moment",
                    "attention required", "access to this page has been denied", "are you a robot")
CHALLENGE_HTML = ("validate.perfdrive.com", "perfdrive.com/captcha", "px-captcha", "captcha-delivery.com",
                  "cf-challenge", "challenge-platform", "hcaptcha.com/1/api", "_pxcaptcha",
                  "please verify you are a human", "לחץ והחזק")

# Collects embedded page state that many sites ship with the HTML.
STATE_JS = """() => {
  const out = [];
  const nd = document.getElementById('__NEXT_DATA__');
  if (nd) out.push(nd.textContent);
  for (const k of ['__SSR_HYDRATED_CONTEXT__', '__INITIAL_STATE__', '__PRELOADED_STATE__',
                   '__APOLLO_STATE__', '__NUXT__']) {
    try { if (window[k]) out.push(JSON.stringify(window[k])); } catch (e) {}
  }
  return out;
}"""

# For every link that matches the listing pattern, climb to the biggest parent
# element that still belongs to that single listing, and take its text.
CARDS_JS = """(pattern) => {
  const re = new RegExp(pattern, 'i');
  const idOf = (href) => { const m = href.match(re); return m ? (m[1] || href) : null; };
  const found = new Map();
  for (const a of document.querySelectorAll('a[href]')) {
    const id = idOf(a.href);
    if (!id) continue;
    let best = a, node = a;
    for (let i = 0; i < 8 && node.parentElement; i++) {
      node = node.parentElement;
      const other = Array.from(node.querySelectorAll('a[href]')).some(x => {
        const xid = idOf(x.href); return xid && xid !== id; });
      if (other || (node.innerText || '').length > 2500) break;
      best = node;
    }
    const text = (best.innerText || a.innerText || '').replace(/\\s*\\n\\s*/g, ' | ').trim();
    const img = best.querySelector('img');
    const image = img ? (img.currentSrc || img.src || '') : '';
    const prev = found.get(id);
    if (!prev || text.length > prev.text.length) found.set(id, {id, href: a.href, text, image});
  }
  return Array.from(found.values());
}"""


@dataclass
class PageResult:
    url: str
    title: str = ""
    blocked: bool = False
    error: str = ""
    states: list[str] = field(default_factory=list)
    payloads: list[Any] = field(default_factory=list)
    cards: list[dict] = field(default_factory=list)


def looks_blocked(title: str, html: str) -> bool:
    title = (title or "").lower()
    if any(marker in title for marker in CHALLENGE_TITLES):
        return True
    # Block pages are small; real result pages can mention captcha scripts too.
    html = html or ""
    return len(html) < 60_000 and any(marker in html.lower() for marker in CHALLENGE_HTML)


class BrowserSession:
    def __init__(self, cfg: BrowserConfig, headed: bool | None = None, debug_dir: Path | None = None):
        self.cfg = cfg
        self.headless = cfg.headless if headed is None else not headed
        self.debug_dir = debug_dir
        self._pw = None
        self._camoufox = None
        self.context = None
        self.page = None
        self._loads = 0

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "BrowserSession":
        self.cfg.profile_dir.mkdir(parents=True, exist_ok=True)
        if self.cfg.engine == "camoufox":
            self._start_camoufox()
        else:
            self._start_chromium()
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.set_default_timeout(self.cfg.timeout_seconds * 1000)
        return self

    def __exit__(self, *exc) -> None:
        try:
            if self.context:
                self.context.close()
        finally:
            if self._camoufox:
                self._camoufox.__exit__(None, None, None)
            if self._pw:
                self._pw.stop()

    def _start_chromium(self) -> None:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        # "chromium" channel = full Chromium in new headless mode, much less detectable
        # than the stripped-down headless shell Playwright uses otherwise.
        channel = self.cfg.channel or "chromium"
        launch = dict(
            headless=self.headless,
            channel=channel,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        context_opts = dict(
            locale="he-IL",
            timezone_id="Asia/Jerusalem",
            viewport={"width": 1366, "height": 900},
        )
        if self.headless:
            context_opts["user_agent"] = self._headful_user_agent(launch)
        self.context = self._pw.chromium.launch_persistent_context(
            str(self.cfg.profile_dir), **launch, **context_opts)
        self.context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

    def _headful_user_agent(self, launch: dict) -> str:
        browser = self._pw.chromium.launch(**launch)
        try:
            ua = browser.new_page().evaluate("navigator.userAgent")
        finally:
            browser.close()
        return ua.replace("HeadlessChrome", "Chrome")

    def _start_camoufox(self) -> None:
        try:
            from camoufox.sync_api import Camoufox
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("engine: camoufox needs `pip install camoufox[geoip]` "
                               "and `python -m camoufox fetch`") from exc
        self._camoufox = Camoufox(headless=self.headless, persistent_context=True,
                                  user_data_dir=str(self.cfg.profile_dir), locale="he-IL",
                                  humanize=True)
        self.context = self._camoufox.__enter__()

    # -- page loading --------------------------------------------------------
    def fetch(self, url: str, *, link_pattern: str, json_capture: str = "", wait_selector: str = "",
              scrolls: int = 5, label: str = "page") -> PageResult:
        if self._loads:
            low, high = self.cfg.delay_seconds
            time.sleep(random.uniform(low, high))
        self._loads += 1

        page = self.page
        result = PageResult(url=url)
        captured = []
        capture_re = re.compile(json_capture) if json_capture else None

        def on_response(response) -> None:
            try:
                if capture_re and capture_re.search(response.url) and \
                        "json" in (response.headers.get("content-type") or ""):
                    captured.append(response)
            except Exception:
                pass

        page.on("response", on_response)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=self.cfg.timeout_seconds * 1000)
            if self._wait_out_challenge(page):
                result.blocked = True
            else:
                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=20_000)
                    except Exception:
                        log.info("No listing links appeared on %s (empty results or new markup)", url)
                self._scroll(page, scrolls)
                result.states = page.evaluate(STATE_JS) or []
                result.cards = page.evaluate(CARDS_JS, link_pattern) or []
                for response in captured:
                    try:
                        result.payloads.append(response.json())
                    except Exception:
                        pass
            result.title = page.title()
        except Exception as exc:
            result.error = f"{type(exc).__name__}: {exc}".splitlines()[0][:300]
            log.warning("Failed to load %s: %s", url, result.error)
        finally:
            page.remove_listener("response", on_response)
            self._dump_debug(page, label)
        return result

    def _wait_out_challenge(self, page) -> bool:
        """True if still blocked after waiting. In a visible window, you can solve it."""
        wait = self.cfg.challenge_wait_seconds if self.headless else self.cfg.headed_challenge_wait_seconds
        deadline = time.monotonic() + wait
        announced = False
        while True:
            try:
                blocked = looks_blocked(page.title(), page.content())
            except Exception:  # page navigating away from the challenge
                blocked = True
            if not blocked:
                return False
            if time.monotonic() > deadline:
                return True
            if not announced:
                log.warning("Anti-bot check on %s%s", page.url,
                            "" if self.headless else " - please solve it in the browser window")
                announced = True
            try:
                page.mouse.move(random.randint(100, 900), random.randint(100, 700), steps=8)
            except Exception:
                pass
            page.wait_for_timeout(2000)

    @staticmethod
    def _scroll(page, times: int) -> None:
        for _ in range(max(0, times)):
            try:
                page.mouse.wheel(0, random.randint(1800, 2800))
            except Exception:
                page.evaluate("window.scrollBy(0, 2400)")
            page.wait_for_timeout(random.randint(600, 1200))
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

    def _dump_debug(self, page, label: str) -> None:
        if not self.debug_dir:
            return
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        stem = self.debug_dir / f"{self._loads:02d}_{re.sub(r'[^A-Za-z0-9_-]+', '_', label)}"
        try:
            stem.with_suffix(".html").write_text(page.content(), encoding="utf-8")
            page.screenshot(path=str(stem.with_suffix(".png")), full_page=False)
        except Exception as exc:
            log.debug("Could not save debug files: %s", exc)
