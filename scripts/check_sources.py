"""Check public collection and extraction without credentials or publication."""

from pathlib import Path

import requests

from app.collectors.html_listing_collector import HTMLListingCollector
from app.config import enabled_sources
from app.extractors.article_extractor import ArticleExtractor


def main() -> None:
    failed = False
    for source in enabled_sources(Path("config/sources.yaml")):
        if source.name not in {"4Pillars Research", "Tiger Research Korean"}:
            continue
        try:
            articles = HTMLListingCollector(source).collect()
            if not articles:
                raise RuntimeError("No article links found")
            print(f"{source.name}: collected={len(articles)}", flush=True)
            for article in articles[:2]:
                content = ArticleExtractor().extract(article.url)
                print(f"extracted={len(content)} url={article.url}", flush=True)
        except Exception as exc:
            failed = True
            print(f"{source.name}: {type(exc).__name__}: {exc}", flush=True)
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                response = exc.response
                print(f"server={response.headers.get('server')} "
                      f"retry-after={response.headers.get('retry-after')} "
                      f"content-type={response.headers.get('content-type')}")
                print(response.text[:500].encode("ascii", "backslashreplace").decode())
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
