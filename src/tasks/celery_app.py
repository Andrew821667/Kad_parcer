"""Celery application configuration."""

from celery import Celery

from src.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "kad_parser",
    broker=settings.broker_url,
    backend=settings.result_backend,
    include=[
        "src.tasks.scraping_tasks",
        "src.tasks.webhook_tasks",
        "src.tasks.maintenance_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
)

# Import and configure beat schedule
from src.tasks.beat_schedule import beat_schedule

celery_app.conf.beat_schedule = beat_schedule
