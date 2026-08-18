from __future__ import annotations

import json
import re
from urllib.parse import urlparse

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
        if _is_coinmarketcap_community_article(url):
            content = self._extract_coinmarketcap_article(html)
        else:
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
            headers={"User-Agent": _browser_user_agent()},
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

    def _extract_coinmarketcap_article(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if script is None:
            raise ArticleExtractionError("CoinMarketCap article data was not found")

        try:
            payload = json.loads(script.string or script.get_text())
            article = payload["props"]["pageProps"]["article"]
            title = str(article.get("title", "")).strip()
            content_html = str(article["content"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ArticleExtractionError(
                "CoinMarketCap article data is invalid"
            ) from exc

        content_soup = BeautifulSoup(content_html, "html.parser")
        for tag in content_soup(["script", "style", "img"]):
            tag.decompose()

        parts: list[str] = []
        for node in content_soup.find_all(
            ["h1", "h2", "h3", "h4", "p", "li", "blockquote"]
        ):
            if node.find_parent(["p", "li", "blockquote"]):
                continue
            text = node.get_text(" ", strip=True)
            if not text:
                continue
            if node.name == "p" and title and title.casefold() in text.casefold():
                if len(text) <= len(title) + 100:
                    continue
            if node.name in {"h1", "h2", "h3", "h4"}:
                parts.append(f"## {text}")
            elif node.name == "li":
                parts.append(f"- {text}")
            else:
                parts.append(text)

        content = "\n\n".join(parts).strip()
        if not content:
            raise ArticleExtractionError("CoinMarketCap article body is empty")
        return content


def _normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_coinmarketcap_community_article(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.netloc.lower() in {"coinmarketcap.com", "www.coinmarketcap.com"}
        and parsed.path.startswith("/community/articles/")
    )


def _browser_user_agent() -> str:
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    )
