"""Webhook-related Celery tasks."""

import asyncio

from src.core.logging import get_logger
from src.storage.database.base import async_session_maker
from src.tasks.celery_app import celery_app
from src.webhooks.dispatcher import WebhookDispatcher

logger = get_logger(__name__)


@celery_app.task(name="retry_failed_webhooks")
def retry_failed_webhooks_task() -> dict:
    """Retry all failed webhook deliveries that are due for retry.

    This task should be run periodically (e.g., every minute) to retry
    failed webhook deliveries.

    Returns:
        Dict with results
    """
    result = asyncio.run(_retry_failed_webhooks_async())
    return result


async def _retry_failed_webhooks_async() -> dict:
    """Async implementation of webhook retry."""
    async with async_session_maker() as session:
        try:
            dispatcher = WebhookDispatcher(session)
            retried_count = await dispatcher.retry_pending_deliveries()

            logger.info("webhook_retry_completed", retried=retried_count)

            return {
                "status": "completed",
                "retried": retried_count,
            }

        except Exception as e:
            logger.error("webhook_retry_failed", error=str(e), exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
            }
