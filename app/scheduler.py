from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import Settings
from app.main import run_pipeline

logger = logging.getLogger(__name__)


def start_scheduler(settings: Settings) -> None:
    settings.validate_for_run()
    scheduler = BlockingScheduler(timezone=settings.timezone)
    trigger = CronTrigger(
        hour=settings.schedule_hour,
        minute=settings.schedule_minute,
        timezone=settings.timezone,
    )
    scheduler.add_job(
        run_pipeline,
        trigger=trigger,
        args=[settings],
        id="daily_crypto_research_digest",
        replace_existing=True,
        max_instances=1,
    )
    logger.info(
        "Scheduler started: daily at %02d:%02d %s",
        settings.schedule_hour,
        settings.schedule_minute,
        settings.timezone,
    )
    scheduler.start()
