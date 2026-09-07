"""Check public collection and extraction without credentials or publication."""

from pathlib import Path
import argparse

import requests

from app.collectors.html_listing_collector import HTMLListingCollector
from app.config import enabled_sources
from app.extractors.article_extractor import ArticleExtractor


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
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
                if args.browser and source.name == "4Pillars Research":
                    from playwright.sync_api import sync_playwright

                    with sync_playwright() as playwright:
                        browser = playwright.chromium.launch()
                        page = browser.new_page()
                        page.goto(source.url, wait_until="domcontentloaded")
                        try:
                            page.locator('a[href*="/en/research/"]').first.wait_for(timeout=30000)
                            articles = HTMLListingCollector(source)._parse_listing(page.content())
                            print(f"Browser collected={len(articles)}", flush=True)
                            for article in articles[:2]:
                                page.goto(article.url, wait_until="networkidle")
                                print(f"Browser article title={page.title()} body_chars={len(page.inner_text('body'))}", flush=True)
                        except Exception as browser_exc:
                            print(f"Browser failed: {type(browser_exc).__name__} title={page.title()}", flush=True)
                        finally:
                            browser.close()
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
