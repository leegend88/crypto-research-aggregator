from __future__ import annotations

import re

import requests
import trafilatura
from bs4 import BeautifulSoup


class ArticleExtractionError(RuntimeError):
    pass


class ArticleExtractor:
    def __init__(
        self,
        timeout_seconds: int = 20,
        min_length: int = 500,
        max_length: int = 50000,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.min_length = min_length
        self.max_length = max_length

    def extract(self, url: str) -> str:
        html = self._download(url)
        content = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_formatting=True,
            output_format="markdown",
        )
        if not content:
            content = self._fallback_extract(html)
        content = _normalize_text(content or "")
        if len(content) < self.min_length:
            raise ArticleExtractionError(
                f"Extracted content is too short: {len(content)} characters"
            )
        return content[: self.max_length]

    def _download(self, url: str) -> str:
        response = requests.get(
            url,
            headers={"User-Agent": "crypto-research-aggregator/0.1"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.text

    def _fallback_extract(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "aside", "footer", "header"]):
            tag.decompose()

        selectors = [
            "article",
            "main",
            ".post-content",
            ".entry-content",
            ".article-content",
            ".content",
        ]
        for selector in selectors:
            node = soup.select_one(selector)
            if node:
                text = node.get_text("\n", strip=True)
                if len(text) >= self.min_length:
                    return text
        return soup.get_text("\n", strip=True)


def _normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
