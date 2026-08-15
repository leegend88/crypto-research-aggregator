from app.models import Article
from app.publishers.telegram_publisher import TELEGRAM_LIMIT, format_telegram_message


def test_message_formatter_escapes_html():
    article = Article(
        source_name="A&B Research",
        title="<ETH> update",
        url="https://example.com/?a=1&b=2",
        korean_title="<ETH> 업데이트",
        summary="• ETH staking increased\n• Fees fell",
    )

    message = format_telegram_message(article)

    assert "&lt;ETH&gt;" in message
    assert "원문 제목: &lt;ETH&gt; update" in message
    assert "A&amp;B Research" in message
    assert "https://example.com/?a=1&amp;b=2" in message


def test_message_formatter_fits_telegram_limit():
    article = Article(
        source_name="Source",
        title="Title",
        url="https://example.com/article",
        korean_title="한국어 제목",
        summary="• " + ("long text " * 1000),
    )

    message = format_telegram_message(article)

    assert len(message) <= TELEGRAM_LIMIT
    assert "원문 보기" in message


def test_message_formatter_uses_required_order():
    article = Article(
        source_name="Source",
        title="English Original Title",
        url="https://example.com/article",
        korean_title="자연스러운 한국어 제목",
        summary="• 첫 번째 핵심\n• 두 번째 핵심\n• 세 번째 핵심",
    )

    message = format_telegram_message(article)
    lines = message.splitlines()

    assert lines[0] == "📌 <b>자연스러운 한국어 제목</b>"
    assert lines[1] == "원문 제목: English Original Title"
    assert lines[2] == "출처: Source"
    assert lines[3].startswith("발행일:")
    assert "🔗" in message
