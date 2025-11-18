"""Celery tasks for scraping and parsing."""

import asyncio
from datetime import datetime

from src.core.logging import get_logger
from src.parser.docx_parser import DOCXDocumentParser
from src.parser.html_parser import HTMLCaseParser
from src.parser.pdf_parser import PDFDocumentParser
from src.scraper.kad_client import KadArbitrClient
from src.storage.database.base import AsyncSessionLocal
from src.storage.database.models import CaseStatus, TaskStatus
from src.storage.database.repository import (
    CaseRepository,
    DocumentRepository,
    HearingRepository,
    ParticipantRepository,
    ScrapingTaskRepository,
)
from src.storage.database.webhook_models import WebhookEvent
from src.storage.files.minio_storage import get_storage
from src.tasks.celery_app import celery_app
from src.webhooks.dispatcher import WebhookDispatcher

logger = get_logger(__name__)


@celery_app.task(name="scrape_case", bind=True)
def scrape_case_task(self, case_number: str) -> dict:
    """Scrape case by number.

    Args:
        self: Task instance
        case_number: Case number to scrape

    Returns:
        Dict with result
    """
    logger.info("scrape_case_task_started", case_number=case_number, task_id=self.request.id)
    start_time = datetime.utcnow()

    # Run async code in sync context
    result = asyncio.run(_scrape_case_async(self.request.id, case_number))

    duration = (datetime.utcnow() - start_time).total_seconds()
    logger.info(
        "scrape_case_task_completed",
        case_number=case_number,
        task_id=self.request.id,
        duration=duration,
        status=result["status"],
    )

    return result


async def _scrape_case_async(task_id: str, case_number: str) -> dict:
    """Async implementation of case scraping.

    Args:
        task_id: Celery task ID
        case_number: Case number

    Returns:
        Result dict
    """
    async with AsyncSessionLocal() as session:
        task_repo = ScrapingTaskRepository(session)
        case_repo = CaseRepository(session)
        participant_repo = ParticipantRepository(session)
        document_repo = DocumentRepository(session)
        hearing_repo = HearingRepository(session)

        # Create scraping task record
        scraping_task = await task_repo.create(
            task_id=task_id,
            task_type="scrape_case",
            status=TaskStatus.RUNNING,
            params={"case_number": case_number},
            started_at=datetime.utcnow(),
        )

        # Initialize webhook dispatcher
        webhook_dispatcher = WebhookDispatcher(session)

        # Dispatch task started event
        await webhook_dispatcher.dispatch(
            WebhookEvent.CASE_SCRAPING_STARTED,
            {
                "task_id": task_id,
                "case_number": case_number,
                "started_at": datetime.utcnow().isoformat(),
            },
        )

        try:
            # Search for case using KAD client
            async with KadArbitrClient() as client:
                logger.info("searching_case", case_number=case_number)
                search_result = await client.search_cases(case_number=case_number)

                if not search_result.get("Result", {}).get("Items"):
                    await task_repo.update(
                        scraping_task,
                        status=TaskStatus.FAILED,
                        error="Case not found in KAD",
                        completed_at=datetime.utcnow(),
                    )
                    return {"status": "error", "message": "Case not found"}

                # Get first matching case
                kad_case = search_result["Result"]["Items"][0]
                case_id = kad_case.get("CaseId")

                # Get case card HTML
                logger.info("fetching_case_card", case_id=case_id)
                html = await client.get_case_card(case_id)

                # Parse HTML
                parser = HTMLCaseParser(html)
                case_info = parser.parse_case_info()
                participants_data = parser.parse_participants()
                documents_data = parser.parse_documents()
                hearings_data = parser.parse_hearings()

                # Create or update case
                existing_case = await case_repo.get_by_case_number(case_number)
                if existing_case:
                    case = await case_repo.update(
                        existing_case,
                        **case_info,
                        status=CaseStatus.IN_PROGRESS,
                        last_scraped_at=datetime.utcnow(),
                    )
                    # Dispatch case updated event
                    await webhook_dispatcher.dispatch(
                        WebhookEvent.CASE_UPDATED,
                        {
                            "case_id": case.id,
                            "case_number": case.case_number,
                            "updated_at": datetime.utcnow().isoformat(),
                        },
                    )
                else:
                    case = await case_repo.create(
                        **case_info,
                        last_scraped_at=datetime.utcnow(),
                    )
                    # Dispatch case created event
                    await webhook_dispatcher.dispatch(
                        WebhookEvent.CASE_CREATED,
                        {
                            "case_id": case.id,
                            "case_number": case.case_number,
                            "created_at": datetime.utcnow().isoformat(),
                        },
                    )

                # Create participants
                for p_data in participants_data:
                    await participant_repo.create(case_id=case.id, **p_data)

                # Create documents
                for d_data in documents_data:
                    document = await document_repo.create(case_id=case.id, **d_data)

                    # Download document file if URL available
                    if d_data.get("file_url"):
                        try:
                            file_content = await client.download_document(d_data["file_url"])

                            # Upload to MinIO
                            storage = get_storage()
                            object_name = f"documents/{document.id}/file.pdf"
                            file_path, file_hash = storage.upload_file(
                                file_content,
                                object_name,
                                "application/pdf",
                            )

                            # Update document
                            await document_repo.update(
                                document,
                                file_path=file_path,
                                file_size=len(file_content),
                                file_hash=file_hash,
                            )

                            # Trigger parsing task
                            parse_document_task.delay(document.id)

                        except Exception as e:
                            logger.error(
                                "document_download_failed",
                                document_id=document.id,
                                error=str(e),
                            )

                # Create hearings
                for h_data in hearings_data:
                    await hearing_repo.create(case_id=case.id, **h_data)

                # Update task as successful
                await task_repo.update(
                    scraping_task,
                    status=TaskStatus.SUCCESS,
                    result={
                        "case_id": case.id,
                        "participants": len(participants_data),
                        "documents": len(documents_data),
                        "hearings": len(hearings_data),
                    },
                    items_processed=1,
                    completed_at=datetime.utcnow(),
                )

                await session.commit()

                # Dispatch scraping completed event
                await webhook_dispatcher.dispatch(
                    WebhookEvent.CASE_SCRAPING_COMPLETED,
                    {
                        "task_id": task_id,
                        "case_id": case.id,
                        "case_number": case.case_number,
                        "completed_at": datetime.utcnow().isoformat(),
                        "stats": {
                            "participants": len(participants_data),
                            "documents": len(documents_data),
                            "hearings": len(hearings_data),
                        },
                    },
                )

                return {
                    "status": "success",
                    "case_id": case.id,
                    "case_number": case.case_number,
                    "stats": {
                        "participants": len(participants_data),
                        "documents": len(documents_data),
                        "hearings": len(hearings_data),
                    },
                }

        except Exception as e:
            logger.error("scrape_case_error", case_number=case_number, error=str(e))

            await task_repo.update(
                scraping_task,
                status=TaskStatus.FAILED,
                error=str(e),
                completed_at=datetime.utcnow(),
            )

            # Dispatch scraping failed event
            await webhook_dispatcher.dispatch(
                WebhookEvent.CASE_SCRAPING_FAILED,
                {
                    "task_id": task_id,
                    "case_number": case_number,
                    "error": str(e),
                    "failed_at": datetime.utcnow().isoformat(),
                },
            )

            await session.commit()

            return {"status": "error", "message": str(e)}


@celery_app.task(name="parse_document", bind=True)
def parse_document_task(self, document_id: int) -> dict:
    """Parse document file.

    Args:
        self: Task instance
        document_id: Document ID to parse

    Returns:
        Dict with result
    """
    logger.info("parse_document_task_started", document_id=document_id, task_id=self.request.id)
    start_time = datetime.utcnow()

    # Run async code
    result = asyncio.run(_parse_document_async(self.request.id, document_id))

    duration = (datetime.utcnow() - start_time).total_seconds()
    logger.info(
        "parse_document_task_completed",
        document_id=document_id,
        task_id=self.request.id,
        duration=duration,
        status=result["status"],
    )

    return result


async def _parse_document_async(task_id: str, document_id: int) -> dict:
    """Async implementation of document parsing.

    Args:
        task_id: Celery task ID
        document_id: Document ID

    Returns:
        Result dict
    """
    async with AsyncSessionLocal() as session:
        doc_repo = DocumentRepository(session)

        try:
            # Get document
            document = await doc_repo.get_by_id(document_id)
            if not document:
                return {"status": "error", "message": "Document not found"}

            if not document.file_path:
                return {"status": "error", "message": "No file to parse"}

            # Download file from MinIO
            storage = get_storage()
            object_name = document.file_path.split("/", 1)[1]
            file_content = storage.download_file(object_name)

            # Determine file type and parse
            text = ""
            if document.file_path.endswith(".pdf"):
                parser = PDFDocumentParser(file_content)
                text = parser.extract_with_fallback()
            elif document.file_path.endswith(".docx"):
                parser = DOCXDocumentParser(file_content)
                text = parser.extract_text()
            else:
                return {"status": "error", "message": "Unsupported file type"}

            # Update document with parsed text
            await doc_repo.update(
                document,
                content_text=text,
                is_parsed=True,
                parse_error=None,
            )

            await session.commit()

            logger.info("document_parsed", document_id=document_id, text_length=len(text))

            return {
                "status": "success",
                "document_id": document_id,
                "text_length": len(text),
            }

        except Exception as e:
            logger.error("parse_document_error", document_id=document_id, error=str(e))

            # Update document with error
            document = await doc_repo.get_by_id(document_id)
            if document:
                await doc_repo.update(
                    document,
                    is_parsed=False,
                    parse_error=str(e),
                )
                await session.commit()

            return {"status": "error", "message": str(e)}


@celery_app.task(name="bulk_scrape_cases")
def bulk_scrape_cases_task(case_numbers: list[str]) -> dict:
    """Scrape multiple cases.

    Args:
        case_numbers: List of case numbers

    Returns:
        Dict with results
    """
    logger.info("bulk_scrape_started", count=len(case_numbers))

    results = []
    for case_number in case_numbers:
        task = scrape_case_task.delay(case_number)
        results.append({"case_number": case_number, "task_id": task.id})

    return {
        "status": "success",
        "total": len(case_numbers),
        "tasks": results,
    }
