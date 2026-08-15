from datetime import datetime

from app.collectors.rss_collector import RSSCollector
from app.config import SourceConfig, load_sources


def test_rss_entry_maps_to_article():
    source = SourceConfig(
        name="Example",
        type="rss",
        url="https://example.com/feed.xml",
    )
    collector = RSSCollector(source)
    entry = {
        "title": "Market structure update",
        "link": "https://example.com/article",
        "id": "entry-1",
        "published": "Tue, 28 Jul 2026 08:00:00 GMT",
    }

    article = collector._entry_to_article(entry)

    assert article.source_name == "Example"
    assert article.title == "Market structure update"
    assert article.url == "https://example.com/article"
    assert article.external_id == "entry-1"
    assert isinstance(article.published_at, datetime)


def test_source_config_loads_url_patterns(tmp_path):
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        """
        sources:
          - name: Example
            type: html_listing
            url: https://example.com/research
            include_url_patterns:
              - /research/
            exclude_url_patterns:
              - /subscribe
        """,
        encoding="utf-8",
    )

    source = load_sources(config_path)[0]

    assert source.include_url_patterns == ("/research/",)
    assert source.exclude_url_patterns == ("/subscribe",)
