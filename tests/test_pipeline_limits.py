from datetime import UTC, datetime

from app import main as pipeline
from app.config import Settings, SourceConfig
from app.database import ArticleRepository
from app.models import Article
from app.summarizers.openai_summarizer import SummaryResult


def test_run_pipeline_processes_latest_articles_up_to_limit(tmp_path, monkeypatch):
    published: list[str] = []
    articles = [
        Article(
            source_name="Source",
            title="Old",
            url="https://example.com/old",
            published_at=datetime(2026, 7, 26, tzinfo=UTC),
        ),
        Article(
            source_name="Source",
            title="Latest",
            url="https://example.com/latest",
            published_at=datetime(2026, 7, 28, tzinfo=UTC),
        ),
        Article(
            source_name="Source",
            title="Middle",
            url="https://example.com/middle",
            published_at=datetime(2026, 7, 27, tzinfo=UTC),
        ),
    ]

    class FakeCollector:
        def __init__(self, source, timeout_seconds):
            pass

        def collect(self):
            return articles

    class FakeExtractor:
        def __init__(self, **kwargs):
            pass

        def extract(self, url):
            return "content long enough"

    class FakeSummarizer:
        def __init__(self, api_key, model):
            pass

        def summarize(self, title, source_name, content):
            return SummaryResult(
                korean_title=f"{title} 한국어",
                bullets=["하나", "둘", "셋"],
            )

    class FakePublisher:
        def __init__(self, **kwargs):
            pass

        def publish(self, article):
            published.append(article.url)

    monkeypatch.setattr(
        pipeline,
        "enabled_sources",
        lambda path: [SourceConfig("Source", "rss", "https://example.com/feed")],
    )
    monkeypatch.setattr(pipeline, "RSSCollector", FakeCollector)
    monkeypatch.setattr(pipeline, "ArticleExtractor", FakeExtractor)
    monkeypatch.setattr(pipeline, "OpenAISummarizer", FakeSummarizer)
    monkeypatch.setattr(pipeline, "TelegramPublisher", FakePublisher)

    settings = Settings(
        openai_api_key="key",
        openai_model="model",
        telegram_bot_token="token",
        telegram_chat_id="chat",
        schedule_hour=8,
        schedule_minute=0,
        timezone="Asia/Seoul",
        database_path=tmp_path / "articles.db",
        sources_config_path=tmp_path / "sources.yaml",
        request_timeout_seconds=20,
        min_article_length=10,
        max_article_length=50000,
        max_articles_per_run=2,
        retry_failed_articles=False,
        log_level="INFO",
    )

    stats = pipeline.run_pipeline(settings)
    repo = ArticleRepository(settings.database_path)

    assert stats.new == 3
    assert stats.publish_success == 2
    assert published == ["https://example.com/latest", "https://example.com/middle"]
    assert [article.url for _, article in repo.pending_articles()] == [
        "https://example.com/old"
    ]
