from datetime import UTC, datetime, timedelta
import sqlite3

import pytest

from app import database
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


@pytest.mark.parametrize("status", ["extract_failed", "summary_failed"])
def test_retry_cooldown_attempt_limit_and_completion(tmp_path, monkeypatch, status):
    now = datetime(2026, 9, 29, tzinfo=UTC)
    monkeypatch.setattr(database, "_now", lambda: now)
    repo = ArticleRepository(tmp_path / "articles.db")
    article = Article(source_name="Tiger", title="Report", url="https://example.com/a")
    article_id = repo.save_discovered(article)
    for attempt in range(3):
        assert [item[0] for item in repo.pending_articles(retry_failed=True)] == [article_id]
        repo.record_attempt(article_id)
        repo.update_status(article_id, status, error_message="Temporary failure")
        assert repo.pending_articles(retry_failed=True) == []
        assert repo.pending_articles(retry_failed=False) == []
        assert repo.save_discovered(article) is None
        now += timedelta(hours=6)

    assert repo.pending_articles(retry_failed=True) == []
    repo.update_status(article_id, STATUS_COMPLETED)
    assert repo.pending_articles(retry_failed=True) == []


def test_publish_failures_are_not_automatically_replayed(tmp_path):
    repo = ArticleRepository(tmp_path / "articles.db")
    article_id = repo.save_discovered(Article("Tiger", "Report", "https://example.com/a"))
    repo.update_status(article_id, "publish_failed")
    assert repo.pending_articles(retry_failed=True) == []


def test_legacy_database_migration_preserves_history_and_allows_bounded_retries(tmp_path):
    path = tmp_path / "articles.db"
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE articles (
            id INTEGER PRIMARY KEY, source_name TEXT, title TEXT, url TEXT UNIQUE,
            external_id TEXT, published_at TEXT, discovered_at TEXT, processed_at TEXT,
            status TEXT, summary TEXT, error_message TEXT)""")
        for index, status in enumerate(["extract_failed", "completed", "publish_failed"], 1):
            conn.execute(
                "INSERT INTO articles (id, source_name, title, url, discovered_at, status) "
                "VALUES (?, 'Tiger', 'Report', ?, '2026-09-01T00:00:00+00:00', ?)",
                (index, f"https://example.com/{index}", status),
            )
    repo = ArticleRepository(path)
    repo.record_attempt(1)
    repo = ArticleRepository(path)
    with repo.connect() as conn:
        assert [tuple(row) for row in conn.execute(
            "SELECT id, attempt_count FROM articles ORDER BY id"
        )] == [(1, 2), (2, 1), (3, 1)]
        conn.execute("UPDATE articles SET last_attempt_at = NULL WHERE id = 1")
    assert [item[0] for item in repo.pending_articles(retry_failed=True)] == [1]


def test_rediscovered_dates_correct_order_without_republishing_completed_articles(tmp_path):
    repo = ArticleRepository(tmp_path / "articles.db")
    first = Article("Tiger", "First", "https://example.com/first")
    second = Article("Tiger", "Second", "https://example.com/second")
    first_id = repo.save_discovered(first)
    repo.save_discovered(second)
    first.published_at = datetime(2026, 9, 23, tzinfo=UTC)
    second.published_at = datetime(2026, 9, 17, tzinfo=UTC)
    repo.save_discovered(first)
    repo.save_discovered(second)
    assert [a.title for _, a in repo.pending_articles()] == ["First", "Second"]
    repo.update_status(first_id, STATUS_COMPLETED)
    repo.save_discovered(first)
    assert [a.title for _, a in repo.pending_articles(retry_failed=True)] == ["Second"]
