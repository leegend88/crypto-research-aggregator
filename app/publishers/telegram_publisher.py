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
        message = format_telegram_message(article)
        endpoint = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        response = requests.post(
            endpoint,
            json={
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=self.timeout_seconds,
        )
        if response.status_code == 429:
            retry_after = response.json().get("parameters", {}).get("retry_after", 1)
            time.sleep(float(retry_after))
            response = requests.post(
                endpoint,
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                },
                timeout=self.timeout_seconds,
            )
        if not response.ok:
            raise TelegramPublishError(
                f"Telegram API error {response.status_code}: {response.text[:300]}"
            )
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)


def format_telegram_message(article: Article) -> str:
    korean_title = html.escape(article.korean_title or article.title)
    original_title = html.escape(article.title)
    source = html.escape(article.source_name)
    published = _format_date(article.published_at)
    summary = _format_summary(article.summary or "")
    url = html.escape(article.url, quote=True)

    message = (
        f"📌 <b>{korean_title}</b>\n"
        f"원문 제목: {original_title}\n"
        f"출처: {source}\n"
        f"발행일: {published}\n\n"
        f"{summary}\n\n"
        f'🔗 <a href="{url}">원문 보기</a>'
    )
    return _fit_telegram_limit(message, url)


def _format_summary(summary: str) -> str:
    lines = [line.strip() for line in summary.splitlines() if line.strip()]
    escaped: list[str] = []
    for line in lines[:4]:
        if line.startswith(("-", "*", "•")):
            line = line[1:].strip()
        escaped.append(f"• {html.escape(line)}")
    return "\n".join(escaped)


def _format_date(value: datetime | None) -> str:
    if value is None:
        return "Unknown"
    return value.date().isoformat()


def _fit_telegram_limit(message: str, escaped_url: str) -> str:
    if len(message) <= TELEGRAM_LIMIT:
        return message
    link = f'\n\n🔗 <a href="{escaped_url}">원문 보기</a>'
    available = TELEGRAM_LIMIT - len(link) - 20
    trimmed = message[:available].rsplit("\n", 1)[0].rstrip()
    return f"{trimmed}\n...{link}"
