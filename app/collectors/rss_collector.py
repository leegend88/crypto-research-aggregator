from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser
import requests

from app.collectors.base import BaseCollector
from app.config import SourceConfig
from app.models import Article


class RSSCollector(BaseCollector):
    def __init__(self, source: SourceConfig, timeout_seconds: int = 20) -> None:
        self.source = source
        self.timeout_seconds = timeout_seconds

    def collect(self) -> list[Article]:
        response = requests.get(
            self.source.url,
            headers={"User-Agent": "crypto-research-aggregator/0.1"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        parsed = feedparser.parse(
            response.content,
            request_headers={"User-Agent": "crypto-research-aggregator/0.1"},
        )
        if getattr(parsed, "bozo", False) and not parsed.entries:
            raise ValueError(f"Could not parse RSS feed: {self.source.url}")
        return [
            self._entry_to_article(entry)
            for entry in parsed.entries[: self.source.max_items]
        ]

    def _entry_to_article(self, entry: object) -> Article:
        title = _first_text(entry, "title") or "(untitled)"
        url = _first_text(entry, "link") or _first_text(entry, "id")
        if not url:
            raise ValueError(f"RSS entry has no URL in source {self.source.name}")
        return Article(
            source_name=self.source.name,
            title=title.strip(),
            url=url.strip(),
            published_at=_parse_published(entry),
            external_id=_first_text(entry, "id", "guid"),
        )


def _first_text(entry: object, *names: str) -> str | None:
    for name in names:
        value = getattr(entry, name, None)
        if value:
            return str(value)
        if isinstance(entry, dict) and entry.get(name):
            return str(entry[name])
    return None


def _parse_published(entry: object) -> datetime | None:
    for attr in ("published", "updated", "created"):
        value = _first_text(entry, attr)
        if value:
            try:
                return parsedate_to_datetime(value)
            except (TypeError, ValueError, IndexError):
                continue
    parsed_struct = getattr(entry, "published_parsed", None) or getattr(
        entry, "updated_parsed", None
    )
    if parsed_struct:
        return datetime(*parsed_struct[:6])
    return None
