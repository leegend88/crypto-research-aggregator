import xml.etree.ElementTree as ET

from app.collectors.sitemap_collector import SitemapCollector
from app.config import SourceConfig


def test_sitemap_collector_extracts_matching_urls(monkeypatch):
    source = SourceConfig(
        name="Binance Research",
        type="sitemap",
        url="https://example.com/sitemap_index.xml",
        include_url_patterns=("sitemap_en", "/en/research/analysis/"),
    )
    collector = SitemapCollector(source)

    index_xml = """
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://example.com/sitemap_en.xml</loc></sitemap>
      <sitemap><loc>https://example.com/sitemap_ko.xml</loc></sitemap>
    </sitemapindex>
    """
    url_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>https://example.com/en/research/analysis/market-cycle</loc>
        <lastmod>2026-07-28</lastmod>
      </url>
      <url>
        <loc>https://example.com/en/blog/unrelated</loc>
        <lastmod>2026-07-28</lastmod>
      </url>
    </urlset>
    """

    def fake_fetch_xml(url):
        if url.endswith("sitemap_index.xml"):
            return ET.fromstring(index_xml)
        return ET.fromstring(url_xml)

    monkeypatch.setattr(collector, "_fetch_xml", fake_fetch_xml)

    articles = collector.collect()

    assert len(articles) == 1
    assert articles[0].url == "https://example.com/en/research/analysis/market-cycle"
    assert articles[0].title == "Market Cycle"
