"""Celery tasks for scraping."""

from src.core.logging import get_logger
from src.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="scrape_case")
def scrape_case_task(case_number: str) -> dict:
    """Scrape case by number.

    Args:
        case_number: Case number to scrape

    Returns:
        Dict with result
    """
    logger.info("scrape_case_task_started", case_number=case_number)

    # TODO: Implement actual scraping logic
    result = {
        "case_number": case_number,
        "status": "success",
    }

    logger.info("scrape_case_task_completed", case_number=case_number)
    return result


@celery_app.task(name="parse_document")
def parse_document_task(document_id: int) -> dict:
    """Parse document.

    Args:
        document_id: Document ID to parse

    Returns:
        Dict with result
    """
    logger.info("parse_document_task_started", document_id=document_id)

    # TODO: Implement actual parsing logic
    result = {
        "document_id": document_id,
        "status": "success",
    }

    logger.info("parse_document_task_completed", document_id=document_id)
    return result
