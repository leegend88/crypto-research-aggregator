from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urldefrag, urljoin, urlparse

import dateparser
import requests
from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector
from app.config import SourceConfig
from app.models import Article


class HTMLListingCollector(BaseCollector):
    def __init__(self, source: SourceConfig, timeout_seconds: int = 20) -> None:
        self.source = source
        self.timeout_seconds = timeout_seconds

    def collect(self) -> list[Article]:
        response = requests.get(
            self.source.url,
            headers={"User-Agent": _browser_user_agent()},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return self._parse_listing(response.text)

    def _parse_listing(self, html: str) -> list[Article]:
        soup = BeautifulSoup(html, "html.parser")
        articles: list[Article] = []
        seen_urls: set[str] = set()

        for anchor in soup.select("a[href]"):
            url = _normalize_url(urljoin(self.source.url, anchor.get("href", "")))
            if url in seen_urls or not self._should_include_url(url):
                continue

            title = _extract_title(anchor)
            if not title:
                continue

            seen_urls.add(url)
            articles.append(
                Article(
                    source_name=self.source.name,
                    title=title,
                    url=url,
                    external_id=url,
                    published_at=_extract_date(anchor),
                )
            )
            if len(articles) >= self.source.max_items:
                break
        return articles

    def _should_include_url(self, url: str) -> bool:
        if url.rstrip("/") == self.source.url.rstrip("/"):
            return False
        parsed_source = urlparse(self.source.url)
        parsed_url = urlparse(url)
        if parsed_url.netloc and parsed_url.netloc != parsed_source.netloc:
            return False

        target = f"{parsed_url.path}?{parsed_url.query}" if parsed_url.query else parsed_url.path
        includes = self.source.include_url_patterns
        excludes = self.source.exclude_url_patterns
        if includes and not any(pattern in target for pattern in includes):
            return False
        if excludes and any(pattern in target for pattern in excludes):
            return False
        return True


def _normalize_url(url: str) -> str:
    return urldefrag(url)[0].rstrip("/")


def _extract_title(anchor) -> str | None:
    candidates = [
        anchor.get_text(" ", strip=True),
        anchor.get("title", ""),
        anchor.get("aria-label", ""),
    ]
    parent = anchor.find_parent(["article", "li", "div"])
    if parent:
        candidates.append(parent.get_text(" ", strip=True))

    for candidate in candidates:
        title = _clean_title(candidate)
        if title:
            return title
    return None


def _clean_title(value: str) -> str | None:
    value = re.sub(r"\s+", " ", value).strip()
    if not value or len(value) < 8:
        return None
    value = re.sub(
        r"^(?:Crypto|Asia|Institution|Investment|Tech)\s+·\s+\w+\s+",
        "",
        value,
    ).strip()
    value = re.sub(r"\b\d{4}-\d{2}-\d{2}\b.*$", "", value).strip()
    value = re.sub(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2}.*$",
        "",
        value,
    ).strip()
    value = re.sub(
        r"\s+(?:Eren|Steve|Jay|Heechang|Ponyo|100y|Jun)(?:\s+·)?\s*$",
        "",
        value,
    ).strip()
    value = re.sub(r"\s+#\S+.*$", "", value).strip()
    return value[:180].strip() or None


def _extract_date(anchor) -> datetime | None:
    parent = anchor.find_parent(["article", "li", "div"]) or anchor
    text = parent.get_text(" ", strip=True)
    patterns = [
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}\b",
        r"\b\d+\s+(?:hours?|hrs?|days?|weeks?)\s+ago\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            parsed = dateparser.parse(match.group(0))
            if parsed:
                return parsed
    return None


def _browser_user_agent() -> str:
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    )
