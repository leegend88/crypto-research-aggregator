from __future__ import annotations

import html
import time

import requests

from app.models import Article
from app.publishers.base import BasePublisher

TELEGRAM_LIMIT = 4096
SUMMARY_CHARS_PER_MESSAGE = 2000

SummarySectionData = tuple[str | None, list[str]]


class TelegramPublishError(RuntimeError):
    pass


class TelegramPublisher(BasePublisher):
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        timeout_seconds: int = 20,
        delay_seconds: float = 1.0,
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout_seconds = timeout_seconds
        self.delay_seconds = delay_seconds

    def publish(self, article: Article) -> None:
        messages = format_telegram_messages(article)
        for index, message in enumerate(messages):
            self._send_message(message)
            if self.delay_seconds > 0 and index < len(messages) - 1:
                time.sleep(self.delay_seconds)

    def _send_message(self, message: str) -> None:
        endpoint = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        response = requests.post(
            endpoint,
            json=payload,
            timeout=self.timeout_seconds,
        )
        if response.status_code == 429:
            retry_after = response.json().get("parameters", {}).get("retry_after", 1)
            time.sleep(float(retry_after))
            response = requests.post(
                endpoint,
                json=payload,
                timeout=self.timeout_seconds,
            )
        if not response.ok:
            raise TelegramPublishError(
                f"Telegram API error {response.status_code}: {response.text[:300]}"
            )


def format_telegram_message(article: Article) -> str:
    """Return the first message for compatibility with existing integrations."""
    return format_telegram_messages(article)[0]


def format_telegram_messages(article: Article) -> list[str]:
    title = html.escape(article.korean_title or article.title)
    url = html.escape(article.url, quote=True)
    sections = _parse_summary_sections(article.summary or "")
    if not sections:
        sections = [(None, ["요약 내용이 없습니다."])]

    pages = _paginate_summary_sections(sections, SUMMARY_CHARS_PER_MESSAGE)
    page_count = len(pages)
    messages: list[str] = []
    for index, page in enumerate(pages, start=1):
        page_label = f" ({index}/{page_count})" if page_count > 1 else ""
        header = (
            f"📌 <b>{title}</b>{page_label}\n\n"
            f"<b>핵심 요약{page_label}</b>"
        )
        blocks = [_format_summary_section(section) for section in page]
        message = header + "\n\n" + "\n\n".join(blocks)
        if index == page_count:
            message += f'\n\n🔗 <a href="{url}">원문 보기</a>'
        if len(message) > TELEGRAM_LIMIT:
            raise TelegramPublishError(
                f"Formatted Telegram message exceeds {TELEGRAM_LIMIT} characters"
            )
        messages.append(message)
    return messages


def _paginate_summary_sections(
    sections: list[SummarySectionData],
    limit: int,
) -> list[list[SummarySectionData]]:
    chunks: list[SummarySectionData] = []
    for heading, bullets in sections:
        chunks.extend(_split_section(heading, bullets, limit))

    pages: list[list[SummarySectionData]] = []
    current: list[SummarySectionData] = []
    current_length = 0
    for section in chunks:
        section_length = len(_serialize_summary_section(section))
        separator_length = 2 if current else 0
        if current and current_length + separator_length + section_length > limit:
            pages.append(current)
            current = []
            current_length = 0
            separator_length = 0
        current.append(section)
        current_length += separator_length + section_length

    if current:
        pages.append(current)
    return pages or [[(None, ["요약 내용이 없습니다."])]]


def _split_section(
    heading: str | None,
    bullets: list[str],
    limit: int,
) -> list[SummarySectionData]:
    continuation_heading = f"{heading} (계속)" if heading else None
    heading_budget = max(
        len(_section_prefix(heading)),
        len(_section_prefix(continuation_heading)),
    )
    bullet_limit = max(100, limit - heading_budget - 2)
    expanded_bullets = [
        part
        for bullet in bullets
        for part in _split_text_without_loss(bullet, bullet_limit)
    ]

    chunks: list[SummarySectionData] = []
    current_bullets: list[str] = []
    current_heading = heading
    for bullet in expanded_bullets:
        candidate = (current_heading, [*current_bullets, bullet])
        if current_bullets and len(_serialize_summary_section(candidate)) > limit:
            chunks.append((current_heading, current_bullets))
            current_heading = continuation_heading
            current_bullets = []
        current_bullets.append(bullet)

    if current_bullets:
        chunks.append((current_heading, current_bullets))
    return chunks


def _format_summary_section(section: SummarySectionData) -> str:
    heading, bullets = section
    lines: list[str] = []
    if heading:
        lines.append(f"<b>{html.escape(heading)}</b>")
    lines.extend(f"• {html.escape(bullet)}" for bullet in bullets)
    return "\n".join(lines)


def _serialize_summary_section(section: SummarySectionData) -> str:
    heading, bullets = section
    lines: list[str] = []
    if heading:
        lines.append(f"## {heading}")
    lines.extend(f"• {bullet}" for bullet in bullets)
    return "\n".join(lines)


def _section_prefix(heading: str | None) -> str:
    return f"## {heading}\n" if heading else ""


def _parse_summary_sections(summary: str) -> list[SummarySectionData]:
    paragraphs = [part.strip() for part in summary.split("\n\n") if part.strip()]
    sections: list[SummarySectionData] = []
    for paragraph in paragraphs:
        lines = paragraph.splitlines()
        if lines[0].startswith("## "):
            heading = lines[0][3:].strip()
            bullets = [_normalize_summary_bullet(line) for line in lines[1:]]
            bullets = [bullet for bullet in bullets if bullet]
            if heading and bullets:
                sections.append((heading, bullets))
        else:
            bullets = [_normalize_summary_bullet(line) for line in lines]
            bullets = [bullet for bullet in bullets if bullet]
            if bullets:
                sections.append((None, bullets))
    return sections


def _normalize_summary_bullet(value: str) -> str:
    value = value.strip()
    while value.startswith(("-", "*", "•")):
        value = value[1:].strip()
    return value


def _split_text_without_loss(text: str, limit: int) -> list[str]:
    remaining = text.strip()
    parts: list[str] = []
    while len(remaining) > limit:
        candidate = remaining[:limit]
        sentence_end = max(
            candidate.rfind(".") + 1,
            candidate.rfind("!") + 1,
            candidate.rfind("?") + 1,
            candidate.rfind("。") + 1,
        )
        if sentence_end >= int(limit * 0.5):
            split_at = sentence_end
        else:
            whitespace = max(candidate.rfind(" "), candidate.rfind("\n"))
            split_at = whitespace if whitespace >= int(limit * 0.5) else limit
        parts.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        parts.append(remaining)
    return parts
