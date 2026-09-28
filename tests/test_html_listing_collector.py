from datetime import UTC, datetime

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


def test_html_listing_collector_prefers_heading_over_card_description():
    source = SourceConfig(
        name="Example Research",
        type="html_listing",
        url="https://example.com/community/articles",
        include_url_patterns=("/community/articles/",),
    )
    collector = HTMLListingCollector(source)
    html = """
    <a href="/community/articles/market-update">
      <h3>Market Update</h3>
      <p>This description must not be appended to the article title.</p>
    </a>
    """

    articles = collector._parse_listing(html)

    assert articles[0].title == "Market Update"


def test_nested_cards_use_their_own_machine_readable_dates():
    source = SourceConfig("Tiger", "html_listing", "https://example.com/archive",
                          include_url_patterns=("/p/",))
    html = """
    <div class="listing">
      <div class="card"><div><a href="/p/first">First report</a></div>
        <div><time datetime="2026-09-23T01:14:33.008+09:00">Sep 22</time></div>
      </div>
      <div class="card"><div><a href="/p/undated">Undated report</a></div></div>
      <div class="card"><div><a href="/p/second">Second report</a></div>
        <div><time datetime="2026-09-17T13:01:46.494Z">Sep 17</time></div>
      </div>
    </div>
    """
    articles = HTMLListingCollector(source)._parse_listing(html)

    assert [a.published_at for a in articles] == [
        datetime(2026, 9, 22, 16, 14, 33, 8000, tzinfo=UTC),
        None,
        datetime(2026, 9, 17, 13, 1, 46, 494000, tzinfo=UTC),
    ]


def test_invalid_datetime_falls_back_to_visible_date():
    source = SourceConfig("Source", "html_listing", "https://example.com/archive",
                          include_url_patterns=("/p/",))
    html = """
    <article><a href="/p/report">Useful report</a>
      <time datetime="invalid">Sep 22, 2026</time>
    </article>
    """
    article = HTMLListingCollector(source)._parse_listing(html)[0]
    assert article.published_at.date().isoformat() == "2026-09-22"
