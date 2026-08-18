import json

import pytest

from app.extractors.article_extractor import ArticleExtractionError, ArticleExtractor


def test_fallback_extracts_article_content():
    extractor = ArticleExtractor(min_length=20)
    html = """
    <html>
      <body>
        <nav>Navigation</nav>
        <article><p>This is the main article text with enough length.</p></article>
      </body>
    </html>
    """

    text = extractor._fallback_extract(html)

    assert "main article text" in text
    assert "Navigation" not in text


def test_short_content_raises(monkeypatch):
    extractor = ArticleExtractor(min_length=50)

    monkeypatch.setattr(extractor, "_download", lambda url: "<article>short</article>")

    with pytest.raises(ArticleExtractionError):
        extractor.extract("https://example.com/short")


def test_coinmarketcap_extracts_structured_article_body_only(monkeypatch):
    extractor = ArticleExtractor(min_length=20)
    article = {
        "title": "Private Credit Markets Show Signs of Stress",
        "content": """
            <p>BitcoinWorld<br>Private Credit Markets Show Signs of Stress</p>
            <p>Private credit debt has increased significantly.</p>
            <h2>Growing Debt Burden</h2>
            <p>Borrowers face higher refinancing costs and default risks.</p>
        """,
    }
    payload = {"props": {"pageProps": {"article": article}}}
    html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload)
        + "</script>"
        + "<h2>Other articles</h2><p>Unrelated HBAR price story.</p>"
    )
    monkeypatch.setattr(extractor, "_download", lambda url: html)

    text = extractor.extract(
        "https://coinmarketcap.com/community/articles/abc123"
    )

    assert "Private credit debt" in text
    assert "## Growing Debt Burden" in text
    assert "refinancing costs" in text
    assert "Other articles" not in text
    assert "HBAR" not in text


def test_coinmarketcap_does_not_fallback_to_page_chrome(monkeypatch):
    extractor = ArticleExtractor(min_length=20)
    monkeypatch.setattr(
        extractor,
        "_download",
        lambda url: "<main>Other articles and navigation only</main>",
    )

    with pytest.raises(ArticleExtractionError, match="article data was not found"):
        extractor.extract("https://coinmarketcap.com/community/articles/abc123")
