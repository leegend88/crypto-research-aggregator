from __future__ import annotations

import html
import time
from datetime import datetime

import requests

from app.models import Article
from app.publishers.base import BasePublisher

TELEGRAM_LIMIT = 4096


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
    title = html.escape(article.title)
    source = html.escape(article.source_name)
    published = _format_date(article.published_at)
    url = html.escape(article.url, quote=True)

    header = (
        f"📌 <b>{title}</b>\n"
        f"원문 제목: {title}\n"
        f"출처: {source}\n"
        f"발행일: {published}\n\n"
        f"<b>핵심 요약</b>"
    )
    continuation = f"📌 <b>{title}</b> (계속)"
    footer = f'🔗 <a href="{url}">원문 보기</a>'
    reserve = len(footer) + 2
    content_limit = TELEGRAM_LIMIT - reserve

    blocks = _format_summary_blocks(article.summary or "", content_limit)
    messages: list[str] = []
    current = header
    for block in blocks:
        separator = "\n\n"
        if len(current) + len(separator) + len(block) <= content_limit:
            current += separator + block
            continue
        messages.append(current)
        current = continuation + separator + block

    messages.append(current + "\n\n" + footer)
    return messages


def _format_summary_blocks(summary: str, content_limit: int) -> list[str]:
    sections = _parse_summary_sections(summary)
    if not sections:
        return ["요약 내용이 없습니다."]

    max_body_length = max(200, content_limit - 300)
    blocks: list[str] = []
    for heading, body in sections:
        escaped_heading = html.escape(heading) if heading else ""
        prefix = f"<b>{escaped_heading}</b>\n" if escaped_heading else ""
        available = max(100, max_body_length - len(prefix))
        body_parts = _split_escaped_text(body, available)
        for index, body_part in enumerate(body_parts):
            part_prefix = prefix
            if index > 0 and escaped_heading:
                part_prefix = f"<b>{escaped_heading} (계속)</b>\n"
            blocks.append(part_prefix + html.escape(body_part))
    return blocks


def _parse_summary_sections(summary: str) -> list[tuple[str | None, str]]:
    paragraphs = [part.strip() for part in summary.split("\n\n") if part.strip()]
    sections: list[tuple[str | None, str]] = []
    for paragraph in paragraphs:
        lines = paragraph.splitlines()
        if lines[0].startswith("## "):
            heading = lines[0][3:].strip()
            body = "\n".join(lines[1:]).strip()
            if heading and body:
                sections.append((heading, body))
        else:
            sections.append((None, paragraph))
    return sections


def _split_escaped_text(text: str, limit: int) -> list[str]:
    remaining = text.strip()
    parts: list[str] = []
    while remaining:
        if len(html.escape(remaining)) <= limit:
            parts.append(remaining)
            break

        low, high = 1, len(remaining)
        while low < high:
            middle = (low + high + 1) // 2
            if len(html.escape(remaining[:middle])) <= limit:
                low = middle
            else:
                high = middle - 1

        split_at = low
        whitespace = max(
            remaining.rfind(" ", 0, split_at),
            remaining.rfind("\n", 0, split_at),
        )
        if whitespace > 0:
            split_at = whitespace
        parts.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    return parts


def _format_date(value: datetime | None) -> str:
    if value is None:
        return "확인 불가"
    return value.date().isoformat()
