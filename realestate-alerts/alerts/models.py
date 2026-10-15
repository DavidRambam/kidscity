from __future__ import annotations

from dataclasses import dataclass, field

from .hebrew import normalize


@dataclass
class Listing:
    source: str
    id: str
    url: str
    title: str = ""
    price: int | None = None  # NIS; monthly when deal == "rent"
    sqm: float | None = None
    city: str = ""
    neighborhood: str = ""
    street: str = ""
    floor: str = ""
    property_type: str = ""  # canonical: shop/warehouse/building/industrial/hall/office/land/parking
    property_type_raw: str = ""
    deal: str = ""  # rent / sale / ""
    is_agency: bool | None = None
    image: str = ""
    published: str = ""
    text: str = ""  # free text from the card, used for keyword filters

    # Set while filtering / comparing with previous runs.
    near_match: bool = False
    also_on: list[str] = field(default_factory=list)
    price_drop_from: int | None = None
    similar_to: str = ""  # human readable note about an earlier, similar listing

    @property
    def key(self) -> str:
        return f"{self.source}:{self.id}"

    @property
    def price_per_sqm(self) -> int | None:
        if self.price and self.sqm:
            return round(self.price / self.sqm)
        return None

    def fingerprint(self) -> str | None:
        """Same city + size + price is almost always the same property cross-posted."""
        if not (self.price and self.sqm and self.city):
            return None
        return f"{normalize(self.city)}|{round(self.sqm)}|{self.price}"

    def merge_missing(self, other: Listing) -> None:
        """Fill empty fields from another parse of the same listing."""
        for name in ("title", "price", "sqm", "city", "neighborhood", "street", "floor",
                     "property_type", "property_type_raw", "deal", "is_agency", "image",
                     "published"):
            if getattr(self, name) in (None, "") and getattr(other, name) not in (None, ""):
                setattr(self, name, getattr(other, name))
        if other.text and other.text not in self.text:
            self.text = f"{self.text} | {other.text}" if self.text else other.text
