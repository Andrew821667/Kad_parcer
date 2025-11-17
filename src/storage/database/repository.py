"""Database repository layer."""

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.logging import get_logger
from src.storage.database.models import Case, Document, Hearing, Participant, ScrapingTask

logger = get_logger(__name__)


class CaseRepository:
    """Repository for Case model."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def create(self, **kwargs: Any) -> Case:
        """Create new case."""
        case = Case(**kwargs)
        self.session.add(case)
        await self.session.flush()
        await self.session.refresh(case)
        logger.info("case_created", case_id=case.id, case_number=case.case_number)
        return case

    async def get_by_id(self, case_id: int) -> Optional[Case]:
        """Get case by ID."""
        result = await self.session.execute(
            select(Case)
            .where(Case.id == case_id)
            .options(
                selectinload(Case.participants),
                selectinload(Case.documents),
                selectinload(Case.hearings),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_case_number(self, case_number: str) -> Optional[Case]:
        """Get case by case number."""
        result = await self.session.execute(
            select(Case).where(Case.case_number == case_number)
        )
        return result.scalar_one_or_none()

    async def update(self, case: Case, **kwargs: Any) -> Case:
        """Update case."""
        for key, value in kwargs.items():
            setattr(case, key, value)
        await self.session.flush()
        await self.session.refresh(case)
        logger.info("case_updated", case_id=case.id)
        return case

    async def list_cases(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Case]:
        """List cases with pagination."""
        result = await self.session.execute(
            select(Case).limit(limit).offset(offset).order_by(Case.created_at.desc())
        )
        return list(result.scalars().all())


class ParticipantRepository:
    """Repository for Participant model."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def create(self, **kwargs: Any) -> Participant:
        """Create new participant."""
        participant = Participant(**kwargs)
        self.session.add(participant)
        await self.session.flush()
        await self.session.refresh(participant)
        return participant

    async def get_by_case(self, case_id: int) -> list[Participant]:
        """Get all participants for a case."""
        result = await self.session.execute(
            select(Participant).where(Participant.case_id == case_id)
        )
        return list(result.scalars().all())


class DocumentRepository:
    """Repository for Document model."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def create(self, **kwargs: Any) -> Document:
        """Create new document."""
        document = Document(**kwargs)
        self.session.add(document)
        await self.session.flush()
        await self.session.refresh(document)
        logger.info("document_created", document_id=document.id, case_id=document.case_id)
        return document

    async def get_by_id(self, document_id: int) -> Optional[Document]:
        """Get document by ID."""
        result = await self.session.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_by_case(self, case_id: int) -> list[Document]:
        """Get all documents for a case."""
        result = await self.session.execute(
            select(Document).where(Document.case_id == case_id)
        )
        return list(result.scalars().all())

    async def update(self, document: Document, **kwargs: Any) -> Document:
        """Update document."""
        for key, value in kwargs.items():
            setattr(document, key, value)
        await self.session.flush()
        await self.session.refresh(document)
        return document


class HearingRepository:
    """Repository for Hearing model."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def create(self, **kwargs: Any) -> Hearing:
        """Create new hearing."""
        hearing = Hearing(**kwargs)
        self.session.add(hearing)
        await self.session.flush()
        await self.session.refresh(hearing)
        return hearing

    async def get_by_case(self, case_id: int) -> list[Hearing]:
        """Get all hearings for a case."""
        result = await self.session.execute(
            select(Hearing).where(Hearing.case_id == case_id)
        )
        return list(result.scalars().all())


class ScrapingTaskRepository:
    """Repository for ScrapingTask model."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def create(self, **kwargs: Any) -> ScrapingTask:
        """Create new task."""
        task = ScrapingTask(**kwargs)
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        logger.info("scraping_task_created", task_id=task.task_id)
        return task

    async def get_by_task_id(self, task_id: str) -> Optional[ScrapingTask]:
        """Get task by task ID."""
        result = await self.session.execute(
            select(ScrapingTask).where(ScrapingTask.task_id == task_id)
        )
        return result.scalar_one_or_none()

    async def update(self, task: ScrapingTask, **kwargs: Any) -> ScrapingTask:
        """Update task."""
        for key, value in kwargs.items():
            setattr(task, key, value)
        await self.session.flush()
        await self.session.refresh(task)
        return task
