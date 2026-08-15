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

