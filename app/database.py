from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from app.models import Article, STATUS_COMPLETED, STATUS_DISCOVERED


class ArticleRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    external_id TEXT,
                    published_at TEXT,
                    discovered_at TEXT NOT NULL,
                    processed_at TEXT,
                    status TEXT NOT NULL,
                    summary TEXT,
                    korean_title TEXT,
                    error_message TEXT
                )
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(articles)").fetchall()
            }
            if "korean_title" not in columns:
                conn.execute("ALTER TABLE articles ADD COLUMN korean_title TEXT")
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_articles_external_id
                ON articles(source_name, external_id)
                WHERE external_id IS NOT NULL
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_articles_status
                ON articles(status)
                """
            )

    def is_duplicate(self, article: Article) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id FROM articles WHERE url = ? LIMIT 1",
                (article.url,),
            ).fetchone()
            if row:
                return True
            if article.external_id:
                row = conn.execute(
                    """
                    SELECT id FROM articles
                    WHERE source_name = ? AND external_id = ?
                    LIMIT 1
                    """,
                    (article.source_name, article.external_id),
                ).fetchone()
            return row is not None

    def save_discovered(self, article: Article) -> int | None:
        if self.is_duplicate(article):
            self._refresh_metadata(article)
            return None
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO articles (
                    source_name, title, url, external_id, published_at,
                    discovered_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article.source_name,
                    article.title,
                    article.url,
                    article.external_id,
                    _datetime_to_text(article.published_at),
                    _datetime_to_text(_now()),
                    STATUS_DISCOVERED,
                ),
            )
            return int(cursor.lastrowid)

    def _refresh_metadata(self, article: Article) -> None:
        published_at = _datetime_to_text(article.published_at)
        with self.connect() as conn:
            if article.external_id:
                conn.execute(
                    """
                    UPDATE articles
                    SET title = ?, published_at = COALESCE(?, published_at)
                    WHERE url = ? OR (source_name = ? AND external_id = ?)
                    """,
                    (
                        article.title,
                        published_at,
                        article.url,
                        article.source_name,
                        article.external_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE articles
                    SET title = ?, published_at = COALESCE(?, published_at)
                    WHERE url = ?
                    """,
                    (article.title, published_at, article.url),
                )

    def update_status(
        self,
        article_id: int,
        status: str,
        summary: str | None = None,
        korean_title: str | None = None,
        error_message: str | None = None,
    ) -> None:
        processed_at = _datetime_to_text(_now()) if status == STATUS_COMPLETED else None
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE articles
                SET status = ?, summary = COALESCE(?, summary),
                    korean_title = COALESCE(?, korean_title),
                    error_message = ?, processed_at = COALESCE(?, processed_at)
                WHERE id = ?
                """,
                (status, summary, korean_title, error_message, processed_at, article_id),
            )

    def pending_articles(self, retry_failed: bool = False) -> list[tuple[int, Article]]:
        statuses = ["discovered"]
        if retry_failed:
            statuses.extend(["extract_failed", "summary_failed", "publish_failed"])
        placeholders = ",".join("?" for _ in statuses)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM articles
                WHERE status IN ({placeholders})
                ORDER BY COALESCE(published_at, discovered_at) DESC, discovered_at DESC
                """,
                statuses,
            ).fetchall()
        return [(int(row["id"]), _row_to_article(row)) for row in rows]


def _row_to_article(row: sqlite3.Row) -> Article:
    return Article(
        source_name=row["source_name"],
        title=row["title"],
        url=row["url"],
        external_id=row["external_id"],
        published_at=_text_to_datetime(row["published_at"]),
        summary=row["summary"],
        korean_title=row["korean_title"] if "korean_title" in row.keys() else None,
        status=row["status"],
        error_message=row["error_message"],
    )


def _datetime_to_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _text_to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _now() -> datetime:
    return datetime.now(UTC)
