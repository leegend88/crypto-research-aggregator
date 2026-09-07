from __future__ import annotations

from collections import Counter, deque
import logging
from datetime import UTC, datetime

from app.collectors.html_listing_collector import HTMLListingCollector
from app.collectors.rss_collector import RSSCollector
from app.collectors.sitemap_collector import SitemapCollector
from app.config import Settings, enabled_sources
from app.database import ArticleRepository
from app.extractors.article_extractor import ArticleExtractor
from app.models import (
    Article,
    RunStats,
    STATUS_COMPLETED,
    STATUS_EXTRACT_FAILED,
    STATUS_PUBLISH_FAILED,
    STATUS_SUMMARY_FAILED,
)
from app.publishers.telegram_publisher import TelegramPublisher
from app.summarizers.openai_summarizer import OpenAISummarizer

logger = logging.getLogger(__name__)


def run_pipeline(settings: Settings) -> RunStats:
    settings.validate_for_run()
    repository = ArticleRepository(settings.database_path)
    extractor = ArticleExtractor(
        timeout_seconds=settings.request_timeout_seconds,
        min_length=settings.min_article_length,
        max_length=settings.max_article_length,
    )
    summarizer = OpenAISummarizer(
        api_key=settings.openai_api_key or "",
        model=settings.openai_model,
    )
    publisher = TelegramPublisher(
        bot_token=settings.telegram_bot_token or "",
        chat_id=settings.telegram_chat_id or "",
        timeout_seconds=settings.request_timeout_seconds,
    )
    stats = RunStats()
    collected_articles: list[Article] = []

    for source in enabled_sources(settings.sources_config_path):
        collector_class = _collector_for_source_type(source.type)
        if collector_class is None:
            logger.warning("Skipping unsupported source type: %s", source.type)
            continue
        try:
            articles = collector_class(source, settings.request_timeout_seconds).collect()
        except Exception:
            logger.exception("Collection failed for source=%s", source.name)
            stats.failed += 1
            continue

        stats.collected += len(articles)
        collected_articles.extend(articles)
        logger.info("Collected %s article(s) from %s", len(articles), source.name)

    new_by_source: Counter[str] = Counter()
    duplicate_by_source: Counter[str] = Counter()
    for article in sorted(collected_articles, key=_article_sort_key, reverse=True):
        article_id = repository.save_discovered(article)
        if article_id is None:
            stats.duplicates += 1
            duplicate_by_source[article.source_name] += 1
            continue
        stats.new += 1
        new_by_source[article.source_name] += 1

    pending = repository.pending_articles(retry_failed=settings.retry_failed_articles)
    selected = _select_articles_for_run(pending, settings.max_articles_per_run)
    selected_by_source = Counter(article.source_name for _, article in selected)
    for source_name in dict.fromkeys(article.source_name for article in collected_articles):
        logger.info(
            "Source status: source=%s new=%s duplicates=%s selected=%s",
            source_name, new_by_source[source_name],
            duplicate_by_source[source_name], selected_by_source[source_name],
        )
    for article_id, article in selected:
        _process_article(
            article_id,
            article,
            repository,
            extractor,
            summarizer,
            publisher,
            stats,
        )

    logger.info(
        "Run summary: collected=%s new=%s duplicates=%s extracted=%s summarized=%s "
        "published=%s failed=%s",
        stats.collected,
        stats.new,
        stats.duplicates,
        stats.extraction_success,
        stats.summary_success,
        stats.publish_success,
        stats.failed,
    )
    return stats


def _process_article(
    article_id: int,
    article: Article,
    repository: ArticleRepository,
    extractor: ArticleExtractor,
    summarizer: OpenAISummarizer,
    publisher: TelegramPublisher,
    stats: RunStats,
) -> None:
    logger.info("Processing article: %s", article.url)
    try:
        article.content = extractor.extract(article.url)
        stats.extraction_success += 1
    except Exception as exc:
        logger.exception("Article extraction failed: %s", article.url)
        repository.update_status(
            article_id,
            STATUS_EXTRACT_FAILED,
            error_message=str(exc),
        )
        stats.failed += 1
        return

    try:
        summary_result = summarizer.summarize(
            title=article.title,
            source_name=article.source_name,
            content=article.content,
        )
        article.summary = summary_result.summary_text
        article.korean_title = summary_result.korean_title or article.title
        stats.summary_success += 1
    except Exception as exc:
        logger.exception("Article summary failed: %s", article.url)
        repository.update_status(
            article_id,
            STATUS_SUMMARY_FAILED,
            error_message=str(exc),
        )
        stats.failed += 1
        return

    try:
        publisher.publish(article)
        repository.update_status(
            article_id,
            STATUS_COMPLETED,
            summary=article.summary,
            korean_title=article.korean_title,
        )
        stats.publish_success += 1
        logger.info("Published article: source=%s url=%s", article.source_name, article.url)
    except Exception as exc:
        logger.exception("Article publish failed: %s", article.url)
        repository.update_status(
            article_id,
            STATUS_PUBLISH_FAILED,
            summary=article.summary,
            korean_title=article.korean_title,
            error_message=str(exc),
        )
        stats.failed += 1


def _article_sort_key(article: Article) -> datetime:
    if article.published_at is None:
        return datetime.min.replace(tzinfo=UTC)
    if article.published_at.tzinfo is None:
        return article.published_at.replace(tzinfo=UTC)
    return article.published_at.astimezone(UTC)


def _select_articles_for_run(
    pending: list[tuple[int, Article]],
    limit: int,
) -> list[tuple[int, Article]]:
    if limit <= 0:
        return []

    by_source: dict[str, deque[tuple[int, Article]]] = {}
    for item in pending:
        by_source.setdefault(item[1].source_name, deque()).append(item)

    selected: list[tuple[int, Article]] = []
    queues = list(by_source.values())
    while queues and len(selected) < limit:
        active: list[deque[tuple[int, Article]]] = []
        for queue in queues:
            if queue and len(selected) < limit:
                selected.append(queue.popleft())
            if queue:
                active.append(queue)
        queues = active
    return selected


def _collector_for_source_type(source_type: str):
    collectors = {
        "rss": RSSCollector,
        "html_listing": HTMLListingCollector,
        "sitemap": SitemapCollector,
    }
    return collectors.get(source_type)
