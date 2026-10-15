"""Turn raw page data (embedded JSON state, API responses, listing cards) into Listings.

Sites change their markup often, so every source is read two ways:
  1. structured JSON the page already carries (exact price / size / address), and
  2. the visible listing cards (link + text), parsed with the Hebrew helpers.
Whatever (1) misses, (2) fills in.
"""
from __future__ import annotations

import json
import re
from collections import deque
from typing import Any, Callable, Iterable

from .hebrew import classify_type, find_deal, find_floor, find_price, find_sqm, to_int, to_number
from .models import Listing

_TOKEN_RE = re.compile(r"^[A-Za-z0-9]{5,20}$")
_MADLAN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{4,40}$")


def _get(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


def _first(obj: dict, *paths: str) -> Any:
    """First non-empty value among dotted paths. {'text': 'x'} style wrappers are unwrapped."""
    for path in paths:
        value = _get(obj, path)
        if isinstance(value, dict):
            value = next((value[k] for k in ("text", "name", "title", "value", "label")
                          if value.get(k) not in (None, "")), None)
        if value not in (None, "", [], {}):
            return value
    return None


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def walk_json(root: Any, is_listing: Callable[[dict], bool], max_nodes: int = 500_000) -> list[dict]:
    """Breadth-first search for dicts that look like listings (not descending into them)."""
    found: list[dict] = []
    queue: deque = deque([root])
    seen = 0
    while queue and seen < max_nodes:
        node = queue.popleft()
        seen += 1
        if isinstance(node, dict):
            if is_listing(node):
                found.append(node)
                continue
            queue.extend(node.values())
        elif isinstance(node, list):
            queue.extend(node)
        elif isinstance(node, str) and len(node) > 50 and node[:1] in "{[":
            # Some sites embed JSON as a string inside JSON.
            try:
                queue.append(json.loads(node))
            except ValueError:
                pass
    return found


def parse_json_blobs(blobs: Iterable[Any]) -> list[Any]:
    out = []
    for blob in blobs:
        if isinstance(blob, str):
            try:
                out.append(json.loads(blob))
            except ValueError:
                continue
        elif blob is not None:
            out.append(blob)
    return out


# --- Yad2 -----------------------------------------------------------------

def _is_yad2_listing(d: dict) -> bool:
    token = d.get("token") or d.get("link_token")
    if not isinstance(token, str) or not _TOKEN_RE.match(token):
        return False
    return any(k in d for k in ("price", "additionalDetails", "address", "square_meters",
                                "row_1", "metaData", "squareMeter"))


def _yad2_listing(d: dict) -> Listing:
    token = d.get("token") or d.get("link_token")
    street = _text(_first(d, "address.street", "street"))
    house = _text(_first(d, "address.house.number", "address_home_number"))
    if street and house:
        street = f"{street} {house}"
    ptype_raw = _text(_first(d, "additionalDetails.property", "property", "propertyType",
                             "title_1", "row_1"))
    ad_type = _text(_first(d, "adType", "ad_type", "merchant_name")).lower()
    deal_raw = _text(_first(d, "dealType", "deal_type")).lower()
    deal = "rent" if "rent" in deal_raw or "השכרה" in deal_raw else (
        "sale" if "sale" in deal_raw or "מכירה" in deal_raw else "")
    listing = Listing(
        source="yad2",
        id=token,
        url=f"https://www.yad2.co.il/realestate/item/{token}",
        price=to_int(_first(d, "price", "priceInfo.price")),
        sqm=to_number(_first(d, "additionalDetails.squareMeter", "squareMeter", "square_meters",
                             "squareMeters", "metaData.squareMeterBuild", "SquareMeter")),
        city=_text(_first(d, "address.city", "city", "city_text")),
        neighborhood=_text(_first(d, "address.neighborhood", "neighborhood")),
        street=street,
        floor=_text(_first(d, "address.house.floor", "floor", "Floor_text")),
        property_type_raw=ptype_raw,
        property_type=classify_type(ptype_raw),
        deal=deal,
        is_agency=("agency" in ad_type or "broker" in ad_type or "תיווך" in ad_type) if ad_type else None,
        image=_text(_first(d, "metaData.coverImage", "coverImage", "img_url", "images_urls.0",
                           "metaData.images.0")),
        published=_text(_first(d, "createdAt", "date_added", "date")),
    )
    listing.title = " · ".join(p for p in (ptype_raw, street, listing.neighborhood, listing.city) if p)
    listing.text = " | ".join(p for p in (listing.title, _text(_first(d, "description", "info_text"))) if p)
    return listing


# --- Madlan ---------------------------------------------------------------

_MADLAN_DEAL = {"unitrent": "rent", "rent": "rent", "unitbuy": "sale", "buy": "sale", "sale": "sale"}


def _is_madlan_listing(d: dict) -> bool:
    lid = d.get("id")
    if isinstance(lid, int):
        lid = str(lid)
    if not isinstance(lid, str) or not _MADLAN_ID_RE.match(lid):
        return False
    if not ("price" in d or "area" in d):
        return False
    return any(k in d for k in ("address", "addressDetails", "dealType", "locationPoint",
                                "buildingClass", "poiType"))


def _madlan_listing(d: dict) -> Listing:
    lid = str(d["id"])
    city = _text(_first(d, "addressDetails.city", "address.city", "city"))
    address = d.get("address") if isinstance(d.get("address"), str) else ""
    if not city and address and "," in address:
        city = address.rsplit(",", 1)[1].strip()
    street = _text(_first(d, "addressDetails.streetName", "streetName"))
    number = _text(_first(d, "addressDetails.streetNumber", "streetNumber"))
    if street and number:
        street = f"{street} {number}"
    if not street and address:
        street = address.split(",", 1)[0].strip()
    ptype_raw = _text(_first(d, "commercialType", "propertyType", "buildingClass", "assetType",
                             "buildingType"))
    image = _first(d, "images.0.imageUrl", "images.0.url", "images.0", "image")
    image = image if isinstance(image, str) and image.startswith("http") else ""
    poc_type = _text(_first(d, "poc.type", "contactType")).lower()
    listing = Listing(
        source="madlan",
        id=lid,
        url=f"https://www.madlan.co.il/listings/{lid}",
        price=to_int(_first(d, "price", "monthlyPrice")),
        sqm=to_number(_first(d, "area", "size", "squareMeters", "builtArea")),
        city=city,
        neighborhood=_text(_first(d, "addressDetails.neighbourhood", "addressDetails.neighborhood",
                                  "neighbourhood", "neighborhood")),
        street=street,
        floor=_text(_first(d, "floor")),
        property_type_raw=ptype_raw,
        property_type=classify_type(ptype_raw),
        deal=_MADLAN_DEAL.get(_text(d.get("dealType")).lower(), ""),
        is_agency=("agent" in poc_type or "agency" in poc_type) if poc_type else None,
        image=image,
        published=_text(_first(d, "firstTimeSeen", "createdAt", "lastUpdated")),
    )
    listing.title = " · ".join(p for p in (ptype_raw, street, listing.neighborhood, city) if p)
    listing.text = " | ".join(p for p in (listing.title, _text(_first(d, "description"))) if p)
    return listing


JSON_PROFILES: dict[str, tuple[Callable[[dict], bool], Callable[[dict], Listing]]] = {
    "yad2": (_is_yad2_listing, _yad2_listing),
    "madlan": (_is_madlan_listing, _madlan_listing),
}


def listings_from_json(source_type: str, source_name: str, blobs: Iterable[Any]) -> dict[str, Listing]:
    profile = JSON_PROFILES.get(source_type)
    if not profile:
        return {}
    is_listing, build = profile
    out: dict[str, Listing] = {}
    for root in parse_json_blobs(blobs):
        for raw in walk_json(root, is_listing):
            try:
                listing = build(raw)
            except Exception:  # one odd record must not kill the scan
                continue
            listing.source = source_name
            if listing.id in out:
                out[listing.id].merge_missing(listing)
            else:
                out[listing.id] = listing
    return out


# --- listing cards (any site) ---------------------------------------------

def listing_from_card(source_name: str, card: dict) -> Listing:
    """card = {'id', 'href', 'text', 'image'} as collected from the page."""
    text = _text(card.get("text"))
    title = text.split(" | ")[0][:140] if text else ""
    ptype = classify_type(text)
    return Listing(
        source=source_name,
        id=str(card["id"]),
        url=card.get("href") or "",
        title=title,
        price=find_price(text),
        sqm=find_sqm(text),
        floor=find_floor(text),
        property_type=ptype,
        deal=find_deal(text),
        image=_text(card.get("image")),
        text=text,
    )


def combine(json_listings: dict[str, Listing], card_listings: dict[str, Listing]) -> dict[str, Listing]:
    out = dict(json_listings)
    for lid, card in card_listings.items():
        if lid in out:
            out[lid].merge_missing(card)
        else:
            out[lid] = card
    return out
