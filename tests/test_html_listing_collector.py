from app.collectors.html_listing_collector import HTMLListingCollector
from app.config import SourceConfig


def test_html_listing_collector_extracts_matching_article_links():
    source = SourceConfig(
        name="Example Research",
        type="html_listing",
        url="https://example.com/research",
        include_url_patterns=("/research/articles/",),
    )
    collector = HTMLListingCollector(source)
    html = """
    <html>
      <body>
        <a href="/about">About</a>
        <article>
          <a href="/research/articles/market-structure">
            Market Structure in Digital Assets
          </a>
          <span>Jul 24, 2026</span>
        </article>
        <article>
          <a href="https://other.example.com/research/articles/offsite">
            Offsite article
          </a>
        </article>
      </body>
    </html>
    """

    articles = collector._parse_listing(html)

    assert len(articles) == 1
    assert articles[0].source_name == "Example Research"
    assert articles[0].title == "Market Structure in Digital Assets"
    assert articles[0].url == "https://example.com/research/articles/market-structure"
    assert articles[0].external_id == articles[0].url
    assert articles[0].published_at is not None


def test_html_listing_collector_respects_exclude_patterns():
    source = SourceConfig(
        name="Example Research",
        type="html_listing",
        url="https://example.com/research",
        include_url_patterns=("/p/",),
        exclude_url_patterns=("/subscribe",),
    )
    collector = HTMLListingCollector(source)
    html = """
    <a href="/p/report">Useful report</a>
    <a href="/p/subscribe">Subscribe page</a>
    """

    articles = collector._parse_listing(html)

    assert [article.url for article in articles] == ["https://example.com/p/report"]
