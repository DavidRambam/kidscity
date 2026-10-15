from alerts.config import load_config
from alerts.filters import evaluate
from alerts.models import Listing
from alerts.setup_env import interactive, normalize_phone, read_env

from conftest import ROOT


def test_normalize_phone():
    assert normalize_phone("050-123 4567") == "+972501234567"
    assert normalize_phone("+972 50 123 4567") == "+972501234567"
    assert normalize_phone("00972501234567") == "+972501234567"
    assert normalize_phone("") == ""


def test_setup_writes_env_and_keeps_other_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# my notes\nTELEGRAM_BOT_TOKEN=keep-me\nSMTP_USER=\n", encoding="utf-8")
    answers = iter(["me@gmail.com", "abcd efgh ijkl mnop", "", "050-1234567", "123456"])
    interactive(env, ask=lambda prompt: next(answers), say=lambda text: None)
    values = read_env(env)
    assert values["SMTP_USER"] == values["EMAIL_TO"] == "me@gmail.com"
    assert values["SMTP_PASSWORD"] == "abcdefghijklmnop"
    assert values["WHATSAPP_PHONE"] == "+972501234567" and values["CALLMEBOT_APIKEY"] == "123456"
    assert values["TELEGRAM_BOT_TOKEN"] == "keep-me"
    assert env.read_text(encoding="utf-8").startswith("# my notes")

    # Running it again and pressing Enter everywhere keeps what was there.
    interactive(env, ask=lambda prompt: "", say=lambda text: None)
    assert read_env(env) == values


def test_shipped_config_matches_the_search():
    """150-250 m² (135-275 with tolerance), no offices, Haifa + Krayot + Nesher + Tirat Carmel."""
    search = load_config(ROOT / "config.yaml").search

    def check(**kw):
        base = dict(source="yad2", id="1", url="u", city="חיפה", sqm=200, price=12000, property_type="shop")
        listing = Listing(**{**base, **kw})
        return evaluate(listing, search), listing

    assert check()[0] is None
    assert check(property_type="office")[0] == "type office"
    assert check(property_type="warehouse", city="נשר")[0] is None
    assert check(city="טירת כרמל")[0] is None
    assert check(city="קריית מוצקין")[0] is None
    assert check(city="עכו")[0] == "other city"
    assert check(sqm=130)[0] == "size out of range"
    assert check(sqm=280)[0] == "size out of range"
    reason, listing = check(sqm=270)
    assert reason is None and listing.near_match
    assert check(price=95000)[0] is None  # no rent ceiling
