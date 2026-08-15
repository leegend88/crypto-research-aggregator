from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class SourceConfig:
    name: str
    type: str
    url: str
    enabled: bool = True
    include_url_patterns: tuple[str, ...] = ()
    exclude_url_patterns: tuple[str, ...] = ()
    max_items: int = 50
    max_sitemaps: int = 3


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_model: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    schedule_hour: int
    schedule_minute: int
    timezone: str
    database_path: Path
    sources_config_path: Path
    request_timeout_seconds: int
    min_article_length: int
    max_article_length: int
    max_articles_per_run: int
    retry_failed_articles: bool
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
            schedule_hour=_int_env("SCHEDULE_HOUR", 8),
            schedule_minute=_int_env("SCHEDULE_MINUTE", 0),
            timezone=os.getenv("TIMEZONE", "Asia/Seoul"),
            database_path=Path(os.getenv("DATABASE_PATH", "data/articles.db")),
            sources_config_path=Path(
                os.getenv("SOURCES_CONFIG_PATH", "config/sources.yaml")
            ),
            request_timeout_seconds=_int_env("REQUEST_TIMEOUT_SECONDS", 20),
            min_article_length=_int_env("MIN_ARTICLE_LENGTH", 500),
            max_article_length=_int_env("MAX_ARTICLE_LENGTH", 50000),
            max_articles_per_run=_int_env("MAX_ARTICLES_PER_RUN", 5),
            retry_failed_articles=_bool_env("RETRY_FAILED_ARTICLES", False),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

    def validate_for_run(self) -> None:
        missing: list[str] = []
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.telegram_chat_id:
            missing.append("TELEGRAM_CHAT_ID")
        if missing:
            names = ", ".join(missing)
            raise ValueError(f"Missing required environment variable(s): {names}")


def load_sources(path: Path) -> list[SourceConfig]:
    if not path.exists():
        raise FileNotFoundError(f"Sources config not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    sources = raw.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("config/sources.yaml must contain a 'sources' list")

    return [_source_from_mapping(item) for item in sources]


def enabled_sources(path: Path) -> list[SourceConfig]:
    return [source for source in load_sources(path) if source.enabled]


def _source_from_mapping(item: Any) -> SourceConfig:
    if not isinstance(item, dict):
        raise ValueError("Each source must be a mapping")
    for field in ("name", "type", "url"):
        if not item.get(field):
            raise ValueError(f"Source is missing required field: {field}")
    return SourceConfig(
        name=str(item["name"]),
        type=str(item["type"]),
        url=str(item["url"]),
        enabled=bool(item.get("enabled", True)),
        include_url_patterns=_string_tuple(item.get("include_url_patterns", [])),
        exclude_url_patterns=_string_tuple(item.get("exclude_url_patterns", [])),
        max_items=int(item.get("max_items", 50)),
        max_sitemaps=int(item.get("max_sitemaps", 3)),
    )


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list):
        raise ValueError("URL patterns must be a string or list of strings")
    return tuple(str(item) for item in value)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
