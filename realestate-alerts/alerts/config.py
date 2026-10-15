from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SOURCE_TYPES = ("yad2", "madlan", "generic")


@dataclass
class SearchConfig:
    deal: str = "rent"
    min_sqm: float | None = 200
    max_sqm: float | None = 300
    size_tolerance_pct: float = 10
    include_unknown_size: bool = False
    min_price: int | None = None
    max_price: int | None = None
    include_unknown_price: bool = True
    sale_price_threshold: int = 150_000
    property_types: list[str] = field(default_factory=lambda: [
        "shop", "warehouse", "building", "industrial", "hall", "office"])
    include_unknown_type: bool = True
    cities: dict[str, list[str]] = field(default_factory=dict)
    exclude_keywords: list[str] = field(default_factory=list)
    price_drop_pct: float = 3


@dataclass
class SourceConfig:
    name: str
    type: str
    urls: list[str]
    label: str = ""
    enabled: bool = True
    max_pages: int = 1
    page_param: str = "page"
    link_pattern: str = ""
    wait_selector: str = ""
    scrolls: int = 5

    @property
    def display_name(self) -> str:
        return self.label or self.name


@dataclass
class BrowserConfig:
    engine: str = "chromium"
    channel: str = ""
    headless: bool = True
    profile_dir: Path = Path(".browser-profile")
    delay_seconds: tuple[float, float] = (4, 9)
    timeout_seconds: int = 60
    challenge_wait_seconds: int = 25
    headed_challenge_wait_seconds: int = 180


@dataclass
class NotifyConfig:
    language: str = "he"
    notify_when_empty: bool = False
    telegram_individual_limit: int = 10


@dataclass
class Config:
    base_dir: Path
    search: SearchConfig
    sources: list[SourceConfig]
    browser: BrowserConfig
    notify: NotifyConfig
    state_file: Path
    reports_dir: Path


class ConfigError(ValueError):
    pass


def _known(cls, data: dict) -> dict:
    unknown = set(data) - set(cls.__dataclass_fields__)
    if unknown:
        raise ConfigError(f"Unknown setting(s) for {cls.__name__}: {', '.join(sorted(unknown))}")
    return data


def load_config(path: str | Path) -> Config:
    path = Path(path).resolve()
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    base = path.parent

    search_raw = dict(raw.get("search") or {})
    cities = {}
    for canonical, aliases in (search_raw.get("cities") or {}).items():
        names = [str(a) for a in (aliases or [])]
        if str(canonical) not in names:
            names.insert(0, str(canonical))
        cities[str(canonical)] = names
    search_raw["cities"] = cities
    search = SearchConfig(**_known(SearchConfig, search_raw))
    if search.deal not in ("rent", "sale", "any"):
        raise ConfigError("search.deal must be rent, sale or any")

    sources = []
    for item in raw.get("sources") or []:
        item = dict(item)
        item["urls"] = [str(u) for u in (item.get("urls") or [])]
        source = SourceConfig(**_known(SourceConfig, item))
        if source.type not in SOURCE_TYPES:
            raise ConfigError(f"Source {source.name}: type must be one of {SOURCE_TYPES}")
        if source.type == "generic" and source.enabled and not source.link_pattern:
            raise ConfigError(f"Source {source.name}: generic sources need a link_pattern")
        sources.append(source)

    browser_raw = dict(raw.get("browser") or {})
    if "profile_dir" in browser_raw:
        browser_raw["profile_dir"] = base / browser_raw["profile_dir"]
    else:
        browser_raw["profile_dir"] = base / ".browser-profile"
    if "delay_seconds" in browser_raw:
        low, high = browser_raw["delay_seconds"]
        browser_raw["delay_seconds"] = (float(low), float(high))
    browser = BrowserConfig(**_known(BrowserConfig, browser_raw))

    notify = NotifyConfig(**_known(NotifyConfig, dict(raw.get("notify") or {})))

    return Config(
        base_dir=base,
        search=search,
        sources=sources,
        browser=browser,
        notify=notify,
        state_file=base / raw.get("state_file", "state/seen.json"),
        reports_dir=base / raw.get("reports_dir", "reports"),
    )


def load_dotenv(path: str | Path) -> None:
    """Minimal .env loader: KEY=value lines; real environment variables win."""
    path = Path(path)
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
