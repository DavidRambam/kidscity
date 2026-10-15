from datetime import datetime

from alerts.extract import combine, listing_from_card, listings_from_json
from alerts.filters import evaluate, filter_listings, merge_cross_posts
from alerts.models import Listing
from alerts.state import NEW, PRICE_DROP, SEEN, State

from conftest import embedded_state


def test_yad2_json(cfg):
    listings = listings_from_json("yad2", "yad2", embedded_state("yad2_page.html"))
    assert set(listings) == {"abc12345", "def67890", "ghi11111", "jkl22222", "mno33333"}
    shop = listings["abc12345"]
    assert (shop.price, shop.sqm, shop.city, shop.neighborhood) == (18000, 250, "חיפה", "הדר הכרמל")
    assert shop.street == "הרצל 12" and shop.floor == "0"
    assert shop.property_type == "shop" and shop.is_agency is True
    assert shop.url == "https://www.yad2.co.il/realestate/item/abc12345"
    assert shop.image.endswith("abc12345.jpg")


def test_madlan_json(cfg):
    listings = listings_from_json("madlan", "madlan", embedded_state("madlan_page.html"))
    assert set(listings) == {"XyZ123ab", "Qwe456rt", "Asd789fg", "Zxc000vb"}
    wh = listings["Qwe456rt"]
    assert (wh.price, wh.sqm, wh.city, wh.deal, wh.property_type) == (20000, 300, "קריית מוצקין", "rent", "warehouse")
    assert listings["Asd789fg"].deal == "sale"
    assert wh.url == "https://www.madlan.co.il/listings/Qwe456rt"


def test_card_parsing():
    card = {"id": "pqr44444", "href": "https://www.yad2.co.il/realestate/item/pqr44444",
            "text": "מחסן | אזור תעשייה מילואות, קרית אתא | 260 מ״ר | קומה 0 | ₪ 14,000", "image": ""}
    listing = listing_from_card("yad2", card)
    assert (listing.price, listing.sqm, listing.property_type, listing.floor) == (14000, 260, "warehouse", "0")


def test_filters_on_yad2_fixture(cfg):
    listings = listings_from_json("yad2", "yad2", embedded_state("yad2_page.html"))
    cards = {"pqr44444": listing_from_card("yad2", {
        "id": "pqr44444", "href": "https://www.yad2.co.il/realestate/item/pqr44444",
        "text": "מחסן | אזור תעשייה מילואות, קרית אתא | 260 מ״ר | ₪ 14,000"})}
    matched, reasons = filter_listings(combine(listings, cards).values(), cfg.search)
    by_id = {l.id: l for l in matched}
    assert set(by_id) == {"abc12345", "def67890", "pqr44444"}
    assert by_id["def67890"].near_match is True          # 190 m² is within the 10% tolerance
    assert by_id["def67890"].city == "קרית ביאליק"       # normalized to the configured name
    assert by_id["pqr44444"].city == "קרית אתא"          # city found in the card text
    assert reasons == {"size out of range": 1, "other city": 1, "deal is sale": 1}


def test_filter_rules(cfg):
    base = dict(source="x", id="1", url="u", city="חיפה", sqm=250, price=10000)
    assert evaluate(Listing(**base, property_type="parking"), cfg.search) == "type parking"
    assert evaluate(Listing(**{**base, "sqm": None}), cfg.search) == "size unknown"
    assert evaluate(Listing(**{**base, "price": None}), cfg.search) is None
    assert evaluate(Listing(**base, text="דרוש מחסן 250 מ\"ר"), cfg.search) == "excluded keyword"
    assert evaluate(Listing(**{**base, "sqm": 340}), cfg.search) == "size out of range"
    cfg.search.max_price = 9000
    assert evaluate(Listing(**base), cfg.search) == "too expensive"


def test_cross_post_merge():
    a = Listing("yad2", "a", "https://yad2/a", city="חיפה", sqm=250, price=18000)
    b = Listing("madlan", "b", "https://madlan/b", city="חיפה", sqm=250, price=18000, image="img")
    c = Listing("madlan", "c", "https://madlan/c", city="חיפה", sqm=251, price=18000)
    merged = merge_cross_posts([a, b, c])
    assert [l.id for l in merged] == ["a", "c"]
    assert a.also_on == ["https://madlan/b"] and a.image == "img"


def test_state_new_seen_drop(tmp_path):
    now = datetime(2026, 10, 15, 8, 0)
    state = State(tmp_path / "seen.json")
    listing = Listing("yad2", "a", "u", city="חיפה", sqm=250, price=20000)
    assert state.classify(listing, 3) == NEW
    state.remember(listing, now)
    state.save()

    state = State(tmp_path / "seen.json")
    assert state.classify(Listing("yad2", "a", "u", price=19800), 3) == SEEN   # -1% is noise
    cheaper = Listing("yad2", "a", "u", price=18000)
    assert state.classify(cheaper, 3) == PRICE_DROP and cheaper.price_drop_from == 20000

    repost = Listing("yad2", "b", "u2", city="חיפה", sqm=250, price=20000)
    assert state.find_similar(repost)["url"] == "u"

    assert state.prune(datetime(2027, 3, 1)) == 1 and state.is_empty()
