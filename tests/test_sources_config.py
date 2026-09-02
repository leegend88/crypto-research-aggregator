from pathlib import Path

from app.config import load_sources


def test_4pillars_uses_research_listing_instead_of_rate_limited_sitemap():
    config_path = Path(__file__).parents[1] / "config" / "sources.yaml"

    sources = load_sources(config_path)
    source = next(item for item in sources if item.name == "4Pillars Research")

    assert source.enabled is True
    assert source.type == "html_listing"
    assert source.url == "https://research.4pillars.io/en/research"
    assert source.include_url_patterns == ("/en/research/",)
