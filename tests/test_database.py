from datetime import UTC, datetime

from app.database import ArticleRepository
from app.models import Article, STATUS_COMPLETED


def test_same_url_is_not_saved_twice(tmp_path):
    repo = ArticleRepository(tmp_path / "articles.db")
    article = Article(source_name="Source", title="Title", url="https://example.com/a")

    first_id = repo.save_discovered(article)
    second_id = repo.save_discovered(article)

    assert first_id is not None
    assert second_id is None


def test_external_id_detects_duplicate_within_source(tmp_path):
    repo = ArticleRepository(tmp_path / "articles.db")
    first = Article(
        source_name="Source",
        title="Title",
        url="https://example.com/a",
        external_id="abc",
    )
    second = Article(
        source_name="Source",
        title="Title 2",
        url="https://example.com/b",
        external_id="abc",
    )

    assert repo.save_discovered(first) is not None
    assert repo.save_discovered(second) is None


def test_completed_articles_are_not_pending(tmp_path):
    database_path = tmp_path / "articles.db"
    repo = ArticleRepository(database_path)
    article = Article(
        source_name="Source",
        title="Title",
        url="https://example.com/a",
        published_at=datetime(2026, 7, 28, tzinfo=UTC),
    )
    article_id = repo.save_discovered(article)

    repo.update_status(article_id or 0, STATUS_COMPLETED, summary="- 요약")

    reopened_repo = ArticleRepository(database_path)

    assert reopened_repo.pending_articles() == []
    assert reopened_repo.save_discovered(article) is None


def test_duplicate_refreshes_title_for_pending_article(tmp_path):
    repo = ArticleRepository(tmp_path / "articles.db")
    original = Article(
        source_name="Source",
        title="Title with card description appended",
        url="https://example.com/a",
    )
    refreshed = Article(
        source_name="Source",
        title="Clean title",
        url="https://example.com/a",
    )

    assert repo.save_discovered(original) is not None
    assert repo.save_discovered(refreshed) is None

    pending = repo.pending_articles()
    assert pending[0][1].title == "Clean title"
