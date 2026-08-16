from datetime import UTC, datetime

from app.models import Article
from app.publishers.telegram_publisher import (
    TELEGRAM_LIMIT,
    format_telegram_message,
    format_telegram_messages,
)


def test_message_formatter_escapes_html_and_uses_original_title_twice():
    article = Article(
        source_name="A&B Research",
        title="<ETH> update",
        url="https://example.com/?a=1&b=2",
        korean_title="사용하지 않을 번역 제목",
        published_at=datetime(2026, 8, 16, tzinfo=UTC),
        summary="## 시장 배경\nETH <staking>이 증가했다.",
    )

    message = format_telegram_message(article)

    assert message.startswith("📌 <b>&lt;ETH&gt; update</b>")
    assert "원문 제목: &lt;ETH&gt; update" in message
    assert "사용하지 않을 번역 제목" not in message
    assert "출처: A&amp;B Research" in message
    assert "발행일: 2026-08-16" in message
    assert "<b>시장 배경</b>" in message
    assert "ETH &lt;staking&gt;이 증가했다." in message
    assert "https://example.com/?a=1&amp;b=2" in message


def test_message_formatter_splits_long_summary_without_losing_content():
    long_text = "매우 긴 핵심 내용입니다. " * 1000
    article = Article(
        source_name="Source",
        title="Original Title",
        url="https://example.com/article",
        summary=f"## 상세 분석\n{long_text}",
    )

    messages = format_telegram_messages(article)

    assert len(messages) > 1
    assert all(len(message) <= TELEGRAM_LIMIT for message in messages)
    assert all("Original Title" in message for message in messages)
    assert "원문 보기" not in messages[0]
    assert "원문 보기" in messages[-1]
    combined = "".join(messages)
    assert combined.count("매우") == 1000


def test_message_formatter_uses_required_order_and_unknown_date_label():
    article = Article(
        source_name="Source",
        title="English Original Title",
        url="https://example.com/article",
        summary="## 개요\n첫 번째 핵심 내용이다.",
    )

    message = format_telegram_message(article)
    lines = message.splitlines()

    assert lines[0] == "📌 <b>English Original Title</b>"
    assert lines[1] == "원문 제목: English Original Title"
    assert lines[2] == "출처: Source"
    assert lines[3] == "발행일: 확인 불가"
    assert lines[5] == "<b>핵심 요약</b>"
    assert "🔗" in message
