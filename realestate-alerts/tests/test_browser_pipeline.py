"""End-to-end: real Chromium loading fixture pages from a local web server."""
import functools
import http.server
import json
import threading
from datetime import datetime
from pathlib import Path

import pytest

from alerts import notify
from alerts.browser import BrowserSession, looks_blocked
from alerts.config import SourceConfig
from alerts.runner import ISRAEL, run_scan
from alerts.sources import scan_source, with_page

from conftest import FIXTURES

pytest.importorskip("playwright")


@pytest.fixture(scope="module")
def server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES))
    handler.log_message = lambda *a, **k: None
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture
def test_cfg(cfg, tmp_path, server):
    cfg.browser.profile_dir = tmp_path / "profile"
    cfg.browser.delay_seconds = (0, 0)
    cfg.browser.challenge_wait_seconds = 2
    cfg.state_file = tmp_path / "state" / "seen.json"
    cfg.reports_dir = tmp_path / "reports"
    for source in cfg.sources:
        if source.name == "yad2":
            source.urls = [f"{server}/yad2_page.html"]
        elif source.name == "madlan":
            source.urls = [f"{server}/madlan_page.html"]
        source.scrolls = 1
    return cfg


def _browser(cfg):
    try:
        return BrowserSession(cfg.browser).__enter__()
    except Exception as exc:  # no Chromium installed here
        pytest.skip(f"Chromium not available: {exc}")


def test_with_page():
    assert with_page("https://x.co/a?city=4000", "page", 1) == "https://x.co/a?city=4000"
    assert with_page("https://x.co/a?city=4000&page=2", "page", 3) == "https://x.co/a?city=4000&page=3"


def test_looks_blocked():
    assert looks_blocked("Radware Page", "")
    assert looks_blocked("", (FIXTURES / "blocked_page.html").read_text())
    assert not looks_blocked("נדל\"ן מסחרי", "<html>" + "x" * 70_000 + "px-captcha</html>")


def test_scan_yad2_and_madlan_pages(test_cfg):
    browser = _browser(test_cfg)
    try:
        yad2 = scan_source(browser, next(s for s in test_cfg.sources if s.name == "yad2"))
        madlan = scan_source(browser, next(s for s in test_cfg.sources if s.name == "madlan"))
    finally:
        browser.__exit__(None, None, None)

    assert yad2.status == "ok" and yad2.pages == 2  # page 2 adds nothing new -> no page 3
    ids = {l.id: l for l in yad2.listings}
    assert set(ids) == {"abc12345", "def67890", "ghi11111", "jkl22222", "mno33333", "pqr44444"}
    assert ids["pqr44444"].sqm == 260 and ids["pqr44444"].price == 14000  # card-only listing
    assert ids["abc12345"].url == "https://www.yad2.co.il/realestate/item/abc12345"

    assert madlan.status == "ok"
    assert {l.id for l in madlan.listings} == {"XyZ123ab", "Qwe456rt", "Asd789fg", "Zxc000vb"}


def test_blocked_source_is_reported(test_cfg, server):
    browser = _browser(test_cfg)
    try:
        source = SourceConfig(name="yad2", type="yad2", urls=[f"{server}/blocked_page.html"])
        result = scan_source(browser, source)
    finally:
        browser.__exit__(None, None, None)
    assert result.blocked and result.status == "blocked"


def test_full_run_then_nothing_new(test_cfg, monkeypatch):
    for var in ("TELEGRAM_BOT_TOKEN", "SMTP_USER", "WHATSAPP_PHONE"):
        monkeypatch.delenv(var, raising=False)
    sent = []
    monkeypatch.setattr(notify, "deliver", lambda run, lang, limit: sent.append(run) or True)
    factory = lambda: BrowserSession(test_cfg.browser)  # noqa: E731
    try:
        first = run_scan(test_cfg, factory, now=datetime(2026, 10, 15, 8, 0, tzinfo=ISRAEL))
    except Exception as exc:
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Chromium not available")
        raise

    assert first.first_run
    # yad2: abc12345 (shop), def67890 (near), pqr44444 (card only)
    # madlan: Qwe456rt (warehouse); XyZ123ab is the same shop as yad2 abc12345 -> merged
    assert sorted(l.id for l in first.new) == ["Qwe456rt", "abc12345", "def67890", "pqr44444"]
    shop = next(l for l in first.new if l.id == "abc12345")
    assert shop.also_on == ["https://www.madlan.co.il/listings/XyZ123ab"]
    assert [s.status for s in first.sources] == ["ok", "ok"]
    assert len(sent) == 1

    saved = json.loads(Path(test_cfg.state_file).read_text(encoding="utf-8"))
    assert "madlan:XyZ123ab" in saved["listings"]

    report = (test_cfg.reports_dir / "latest.html").read_text(encoding="utf-8")
    assert "הרצל 12" in report and 'dir="rtl"' in report

    # Make one listing "cheaper than before": the next run reports only that price drop.
    saved["listings"]["madlan:Qwe456rt"]["price"] = 25000
    Path(test_cfg.state_file).write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
    second = run_scan(test_cfg, factory, now=datetime(2026, 10, 15, 18, 0, tzinfo=ISRAEL))
    assert not second.first_run and second.new == []
    assert [(l.id, l.price_drop_from, l.price) for l in second.drops] == [("Qwe456rt", 25000, 20000)]
