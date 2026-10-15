import json
from datetime import datetime

from alerts import notify, report
from alerts.models import Listing
from alerts.report import RunSummary, SourceSummary
from alerts.runner import ISRAEL


def _run(n_new=2):
    new = [Listing("yad2", f"id{i}", f"https://www.yad2.co.il/realestate/item/id{i}", price=10000 + i,
                   sqm=250, city="חיפה", property_type="shop", property_type_raw="חנות <מסחרי>")
           for i in range(n_new)]
    return RunSummary(started=datetime(2026, 10, 15, 8, 0, tzinfo=ISRAEL), new=new, matches=new,
                      sources=[SourceSummary("yad2", "ok", 40, n_new), SourceSummary("madlan", "blocked")],
                      source_labels={"yad2": "יד2", "madlan": "מדלן"})


class FakeResponse:
    def __init__(self, body=b'{"ok": true}'):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


def test_telegram_individual_and_digest(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(notify.time, "sleep", lambda s: None)
    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append(json.loads(request.data))
        return FakeResponse()

    monkeypatch.setattr(notify.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(notify.json, "load", lambda fh: {"ok": True})

    notify.Telegram().send_run(_run(2), "he", individual_limit=10)
    assert len(calls) == 3  # summary + one message per listing
    assert calls[0]["text"].startswith("<b>🏢")
    assert "⚠️ מדלן" in calls[0]["text"]
    assert "&lt;מסחרי&gt;" in calls[1]["text"]  # HTML-escaped for Telegram
    assert calls[1]["link_preview_options"] == {"is_disabled": False}

    calls.clear()
    notify.Telegram().send_run(_run(60), "he", individual_limit=10)
    assert all(len(c["text"]) <= 4096 for c in calls)
    assert sum(c["text"].count("• <a href=") for c in calls) == 60


def test_email(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.delenv("EMAIL_TO", raising=False)
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, context=None, timeout=None):
            sent["server"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, user, password):
            sent["login"] = user

        def sendmail(self, sender, to, message):
            sent["to"], sent["message"] = to, message

    monkeypatch.setattr(notify.smtplib, "SMTP_SSL", FakeSMTP)
    notify.Email().send_run(_run(2), "he", 10)
    assert sent["server"] == ("smtp.gmail.com", 465)
    assert sent["to"] == ["me@example.com"]  # defaults to sending to yourself
    assert "Subject:" in sent["message"]


def test_deliver_reports_failure(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    for var in ("SMTP_USER", "WHATSAPP_PHONE"):
        monkeypatch.delenv(var, raising=False)

    def boom(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr(notify.urllib.request, "urlopen", boom)
    assert notify.deliver(_run(1), "he", 10) is False


def test_chunk_lines_limit():
    chunks = report.chunk_lines(["x" * 100] * 100, limit=1000)
    assert all(len(c) <= 1000 for c in chunks) and sum(c.count("x" * 100) for c in chunks) == 100
