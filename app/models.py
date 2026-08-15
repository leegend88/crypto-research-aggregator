from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


STATUS_DISCOVERED = "discovered"
STATUS_EXTRACT_FAILED = "extract_failed"
STATUS_SUMMARY_FAILED = "summary_failed"
STATUS_PUBLISH_FAILED = "publish_failed"
STATUS_COMPLETED = "completed"

FINAL_STATUSES = {STATUS_COMPLETED}
FAILED_STATUSES = {
    STATUS_EXTRACT_FAILED,
    STATUS_SUMMARY_FAILED,
    STATUS_PUBLISH_FAILED,
}


@dataclass(slots=True)
class Article:
    source_name: str
    title: str
    url: str
    published_at: datetime | None = None
    external_id: str | None = None
    content: str | None = None
    summary: str | None = None
    korean_title: str | None = None
    status: str = STATUS_DISCOVERED
    error_message: str | None = None


@dataclass(slots=True)
class RunStats:
    collected: int = 0
    new: int = 0
    duplicates: int = 0
    extraction_success: int = 0
    summary_success: int = 0
    publish_success: int = 0
    failed: int = 0
