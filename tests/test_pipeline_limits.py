from datetime import UTC, datetime

from app import main as pipeline
from app.config import Settings, SourceConfig
from app.database import ArticleRepository
from app.models import Article
from app.summarizers.openai_summarizer import SummaryResult, SummarySection


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
                sections=[
                    SummarySection(
                        heading="핵심 분석",
                        bullets=["상세한 핵심 내용"],
                    )
                ],
                korean_title=f"{title} 한국어 제목",
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


def test_select_articles_for_run_balances_sources_before_repeating():
    pending = [
        (1, Article(source_name="CoinMarketCap", title="CMC 1", url="cmc-1")),
        (2, Article(source_name="CoinMarketCap", title="CMC 2", url="cmc-2")),
        (3, Article(source_name="Tiger", title="Tiger 1", url="tiger-1")),
        (4, Article(source_name="4Pillars", title="4P 1", url="4p-1")),
        (5, Article(source_name="Tiger", title="Tiger 2", url="tiger-2")),
        (6, Article(source_name="CoinMarketCap", title="CMC 3", url="cmc-3")),
    ]

    selected = pipeline._select_articles_for_run(pending, limit=5)

    assert [article.url for _, article in selected] == [
        "cmc-1",
        "tiger-1",
        "4p-1",
        "cmc-2",
        "tiger-2",
    ]


def test_retries_reserve_at_most_one_slot_when_new_articles_exist():
    retries = [
        (i, Article("Tiger", "Failed", f"retry-{i}", status="extract_failed"))
        for i in range(10)
    ]
    fresh = [(20 + i, Article("CMC", "New", f"new-{i}")) for i in range(10)]
    selected = pipeline._select_articles_for_run(retries + fresh, 5)
    assert [a.url for _, a in selected] == ["new-0", "new-1", "new-2", "new-3", "retry-0"]
    assert pipeline._select_articles_for_run(retries + fresh, 1) == fresh[:1]
    assert len(pipeline._select_articles_for_run(retries, 5)) == 5
    assert pipeline._select_articles_for_run(retries + fresh, 0) == []


def test_pipeline_retries_failed_article_then_never_republishes_it(tmp_path, monkeypatch):
    from datetime import timedelta
    from types import SimpleNamespace
    from unittest.mock import Mock
    from app import config, database

    now = datetime(2026, 9, 29, tzinfo=UTC)
    monkeypatch.setattr(database, "_now", lambda: now)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    for name, value in {
        "OPENAI_API_KEY": "test", "TELEGRAM_BOT_TOKEN": "test", "TELEGRAM_CHAT_ID": "test",
        "DATABASE_PATH": str(tmp_path / "articles.db"), "RETRY_FAILED_ARTICLES": "true",
        "MAX_ARTICLES_PER_RUN": "5",
    }.items():
        monkeypatch.setenv(name, value)
    settings = Settings.from_env()
    article = Article("Tiger", "Report", "https://example.com/report")
    monkeypatch.setattr(pipeline, "enabled_sources", lambda path: [
        SourceConfig("Tiger", "html_listing", "https://example.com/archive")
    ])
    collector = Mock()
    collector.collect.return_value = [article]
    extractor = Mock()
    extractor.extract.side_effect = [RuntimeError("Temporary failure"), "Article body"]
    summarizer = Mock()
    summarizer.summarize.return_value = SimpleNamespace(summary_text="Summary", korean_title="Title")
    publisher = Mock()
    for name, instance in [("HTMLListingCollector", collector), ("ArticleExtractor", extractor),
                           ("OpenAISummarizer", summarizer), ("TelegramPublisher", publisher)]:
        monkeypatch.setattr(pipeline, name, lambda *args, _instance=instance, **kwargs: _instance)
    repo = ArticleRepository(settings.database_path)
    repo.save_discovered(Article("Disabled source", "Old", "https://example.com/disabled"))

    assert pipeline.run_pipeline(settings).failed == 1
    assert pipeline.run_pipeline(settings).publish_success == 0
    now += timedelta(hours=6)
    assert pipeline.run_pipeline(settings).publish_success == 1
    assert pipeline.run_pipeline(settings).publish_success == 0
    publisher.publish.assert_called_once()
    assert extractor.extract.call_count == 2
