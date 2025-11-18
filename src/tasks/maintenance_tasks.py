"""Maintenance and scheduled tasks."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import delete, select, update

from src.core.logging import get_logger
from src.storage.database.base import async_session_maker
from src.storage.database.models import Case, CaseStatus, ScrapingTask, TaskStatus
from src.storage.database.webhook_models import WebhookDelivery
from src.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="cleanup_old_deliveries")
def cleanup_old_deliveries_task() -> dict:
    """Clean up old webhook delivery records.

    Deletes webhook deliveries older than 30 days.

    Returns:
        Dict with results
    """
    result = asyncio.run(_cleanup_old_deliveries_async())
    return result


async def _cleanup_old_deliveries_async() -> dict:
    """Async implementation of cleanup."""
    async with async_session_maker() as session:
        try:
            # Delete deliveries older than 30 days
            cutoff_date = datetime.utcnow() - timedelta(days=30)

            result = await session.execute(
                delete(WebhookDelivery).where(WebhookDelivery.created_at < cutoff_date)
            )

            deleted_count = result.rowcount
            await session.commit()

            logger.info("old_deliveries_cleaned", deleted=deleted_count, cutoff_date=cutoff_date.isoformat())

            return {
                "status": "completed",
                "deleted": deleted_count,
                "cutoff_date": cutoff_date.isoformat(),
            }

        except Exception as e:
            logger.error("cleanup_deliveries_failed", error=str(e), exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
            }


@celery_app.task(name="update_case_statistics")
def update_case_statistics_task() -> dict:
    """Update case statistics.

    Calculates and updates various case statistics.

    Returns:
        Dict with results
    """
    result = asyncio.run(_update_case_statistics_async())
    return result


async def _update_case_statistics_async() -> dict:
    """Async implementation of statistics update."""
    async with async_session_maker() as session:
        try:
            # Get statistics
            total_cases = await session.execute(select(Case))
            total_count = len(total_cases.scalars().all())

            active_cases = await session.execute(
                select(Case).where(Case.status == CaseStatus.IN_PROGRESS)
            )
            active_count = len(active_cases.scalars().all())

            logger.info(
                "case_statistics_updated",
                total_cases=total_count,
                active_cases=active_count,
            )

            return {
                "status": "completed",
                "total_cases": total_count,
                "active_cases": active_count,
            }

        except Exception as e:
            logger.error("update_statistics_failed", error=str(e), exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
            }


@celery_app.task(name="check_stuck_tasks")
def check_stuck_tasks_task() -> dict:
    """Check for stuck scraping tasks.

    Finds tasks that have been running for more than 1 hour and marks them as failed.

    Returns:
        Dict with results
    """
    result = asyncio.run(_check_stuck_tasks_async())
    return result


async def _check_stuck_tasks_async() -> dict:
    """Async implementation of stuck task check."""
    async with async_session_maker() as session:
        try:
            # Find tasks running for more than 1 hour
            cutoff_time = datetime.utcnow() - timedelta(hours=1)

            result = await session.execute(
                select(ScrapingTask).where(
                    ScrapingTask.status == TaskStatus.RUNNING,
                    ScrapingTask.started_at < cutoff_time,
                )
            )

            stuck_tasks = result.scalars().all()

            # Mark as failed
            for task in stuck_tasks:
                task.status = TaskStatus.FAILED
                task.error = "Task timeout - marked as stuck"
                task.completed_at = datetime.utcnow()

            await session.commit()

            logger.info("stuck_tasks_checked", found=len(stuck_tasks))

            return {
                "status": "completed",
                "stuck_tasks": len(stuck_tasks),
                "task_ids": [t.task_id for t in stuck_tasks],
            }

        except Exception as e:
            logger.error("check_stuck_tasks_failed", error=str(e), exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
            }


@celery_app.task(name="cleanup_expired_sessions")
def cleanup_expired_sessions_task() -> dict:
    """Clean up expired sessions and temporary data.

    Returns:
        Dict with results
    """
    result = asyncio.run(_cleanup_expired_sessions_async())
    return result


async def _cleanup_expired_sessions_async() -> dict:
    """Async implementation of session cleanup."""
    async with async_session_maker() as session:
        try:
            # Clean up expired API keys
            from src.storage.database.auth_models import APIKey

            cutoff_date = datetime.utcnow()

            # Mark expired API keys as inactive
            result = await session.execute(
                update(APIKey)
                .where(
                    APIKey.expires_at.isnot(None),
                    APIKey.expires_at < cutoff_date,
                    APIKey.is_active.is_(True),
                )
                .values(is_active=False)
            )

            expired_keys = result.rowcount
            await session.commit()

            logger.info("expired_sessions_cleaned", expired_api_keys=expired_keys)

            return {
                "status": "completed",
                "expired_api_keys": expired_keys,
            }

        except Exception as e:
            logger.error("cleanup_sessions_failed", error=str(e), exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
            }
