from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urldefrag, urlparse

import dateparser
import requests

from app.collectors.base import BaseCollector
from app.config import SourceConfig
from app.models import Article


class SitemapCollector(BaseCollector):
    def __init__(self, source: SourceConfig, timeout_seconds: int = 20) -> None:
        self.source = source
        self.timeout_seconds = timeout_seconds

    def collect(self) -> list[Article]:
        sitemap_urls = self._collect_sitemap_urls(self.source.url)
        articles: list[Article] = []
        seen_urls: set[str] = set()

        for sitemap_url in sitemap_urls[: self.source.max_sitemaps]:
            root = self._fetch_xml(sitemap_url)
            for url, published_at in self._iter_url_entries(root):
                url = urldefrag(url)[0].rstrip("/")
                if url in seen_urls or not self._should_include_url(url):
                    continue
                seen_urls.add(url)
                articles.append(
                    Article(
                        source_name=self.source.name,
                        title=_title_from_url(url),
                        url=url,
                        external_id=url,
                        published_at=published_at,
                    )
                )
                if len(articles) >= self.source.max_items:
                    break
            if len(articles) >= self.source.max_items:
                break

        articles.sort(key=lambda article: article.published_at or datetime.min, reverse=True)
        return articles

    def _collect_sitemap_urls(self, url: str) -> list[str]:
        root = self._fetch_xml(url)
        child_sitemaps = [
            loc.text.strip()
            for loc in root.findall(".//{*}sitemap/{*}loc")
            if loc.text and self._sitemap_allowed(loc.text.strip())
        ]
        return child_sitemaps[: self.source.max_sitemaps] or [url]

    def _fetch_xml(self, url: str) -> ET.Element:
        response = requests.get(
            url,
            headers={"User-Agent": _browser_user_agent()},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return ET.fromstring(response.content)

    def _iter_url_entries(self, root: ET.Element):
        for entry in root.findall(".//{*}url"):
            loc = entry.find("{*}loc")
            if loc is None or not loc.text:
                continue
            lastmod = entry.find("{*}lastmod")
            published_at = dateparser.parse(lastmod.text) if lastmod is not None and lastmod.text else None
            yield loc.text.strip(), published_at

    def _sitemap_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        target = f"{parsed.path}?{parsed.query}" if parsed.query else parsed.path
        includes = self.source.include_url_patterns
        if includes and not any(pattern in target for pattern in includes):
            return False
        return True

    def _should_include_url(self, url: str) -> bool:
        parsed = urlparse(url)
        target = f"{parsed.path}?{parsed.query}" if parsed.query else parsed.path
        includes = self.source.include_url_patterns
        excludes = self.source.exclude_url_patterns
        if includes and not any(pattern in target for pattern in includes):
            return False
        if excludes and any(pattern in target for pattern in excludes):
            return False
        return True


def _title_from_url(url: str) -> str:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    return slug.replace("-", " ").strip().title() or url


def _browser_user_agent() -> str:
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    )
