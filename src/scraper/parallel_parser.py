"""
Parallel browser-based parsing with progress tracking and error recovery.

Manages multiple Playwright browser instances to parse millions of court cases
efficiently while avoiding rate limiting.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import aiofiles
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.scraper.playwright_scraper import PlaywrightScraper
from src.storage.database.base import get_db_session
from src.storage.database.models import Case

logger = get_logger(__name__)


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ParsingTask:
    """
    Represents a single parsing task (one court + one date period).
    """

    court_code: str
    date_from: date
    date_to: date
    status: TaskStatus = TaskStatus.PENDING
    cases_count: int = 0
    error_message: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "court_code": self.court_code,
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
            "status": self.status.value,
            "cases_count": self.cases_count,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ParallelParser:
    """
    Manages parallel parsing with multiple browser instances.

    Features:
    - Multiple concurrent workers (browsers)
    - Progress tracking with checkpoints
    - Automatic error recovery and retry
    - Task queue management
    - Database integration
    """

    def __init__(
        self,
        num_workers: int = 5,
        headless: bool = True,
        checkpoint_file: Path | None = None,
    ) -> None:
        """
        Initialize parallel parser.

        Args:
            num_workers: Number of parallel browser instances
            headless: Run browsers in headless mode
            checkpoint_file: File to save/restore progress
        """
        self.num_workers = num_workers
        self.headless = headless
        self.checkpoint_file = checkpoint_file or Path("parsing_progress.json")

        self.task_queue: asyncio.Queue[ParsingTask | None] = asyncio.Queue()
        self.completed_tasks: list[ParsingTask] = []
        self.failed_tasks: list[ParsingTask] = []

        self._workers: list[asyncio.Task] = []
        self._total_cases = 0
        self._lock = asyncio.Lock()

    async def add_tasks(self, tasks: list[ParsingTask]) -> None:
        """
        Add parsing tasks to queue.

        Args:
            tasks: List of parsing tasks
        """
        for task in tasks:
            await self.task_queue.put(task)

        logger.info("tasks_added_to_queue", count=len(tasks))

    async def start(self) -> None:
        """Start all worker processes."""
        logger.info("starting_parallel_parser", num_workers=self.num_workers)

        # Create workers
        for worker_id in range(self.num_workers):
            worker = asyncio.create_task(self._worker(worker_id))
            self._workers.append(worker)

        logger.info("workers_started", count=len(self._workers))

    async def stop(self) -> None:
        """Stop all workers and save progress."""
        logger.info("stopping_parallel_parser")

        # Send stop signals
        for _ in range(self.num_workers):
            await self.task_queue.put(None)

        # Wait for workers to finish
        await asyncio.gather(*self._workers, return_exceptions=True)

        # Save final checkpoint
        await self._save_checkpoint()

        logger.info(
            "parallel_parser_stopped",
            total_cases=self._total_cases,
            completed_tasks=len(self.completed_tasks),
            failed_tasks=len(self.failed_tasks),
        )

    async def _worker(self, worker_id: int) -> None:
        """
        Worker process that consumes tasks from queue.

        Args:
            worker_id: Unique worker identifier
        """
        logger.info("worker_started", worker_id=worker_id)

        # Initialize browser
        scraper = PlaywrightScraper(
            headless=self.headless,
            browser_type="firefox",
            base_delay=(3.0, 5.0),
        )

        try:
            await scraper.start()

            while True:
                # Get task from queue
                task = await self.task_queue.get()

                # None is stop signal
                if task is None:
                    break

                # Process task
                await self._process_task(worker_id, scraper, task)

                # Mark task as done
                self.task_queue.task_done()

        except Exception as e:
            logger.error("worker_fatal_error", worker_id=worker_id, error=str(e))
        finally:
            await scraper.close()
            logger.info("worker_stopped", worker_id=worker_id)

    async def _process_task(
        self,
        worker_id: int,
        scraper: PlaywrightScraper,
        task: ParsingTask,
    ) -> None:
        """
        Process a single parsing task.

        Args:
            worker_id: Worker identifier
            scraper: Playwright scraper instance
            task: Parsing task
        """
        logger.info(
            "processing_task",
            worker_id=worker_id,
            court=task.court_code,
            date_from=task.date_from,
            date_to=task.date_to,
        )

        # Update status
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()

        try:
            # Parse cases
            results = await scraper.search_by_court_and_date(
                court_code=task.court_code,
                date_from=task.date_from,
                date_to=task.date_to,
            )

            # Save to database
            cases_saved = await self._save_cases(results)

            # Update task
            task.status = TaskStatus.COMPLETED
            task.cases_count = cases_saved
            task.completed_at = datetime.utcnow()

            async with self._lock:
                self._total_cases += cases_saved
                self.completed_tasks.append(task)

            logger.info(
                "task_completed",
                worker_id=worker_id,
                court=task.court_code,
                cases_count=cases_saved,
                total_cases=self._total_cases,
            )

        except Exception as e:
            logger.error(
                "task_failed",
                worker_id=worker_id,
                court=task.court_code,
                error=str(e),
            )

            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()

            async with self._lock:
                self.failed_tasks.append(task)

        # Save checkpoint after each task
        await self._save_checkpoint()

    async def _save_cases(self, cases_data: list[dict[str, Any]]) -> int:
        """
        Save parsed cases to database.

        Args:
            cases_data: List of case dictionaries

        Returns:
            Number of cases saved
        """
        if not cases_data:
            return 0

        saved_count = 0

        async for session in get_db_session():
            try:
                for case_dict in cases_data:
                    # Check if case already exists
                    stmt = select(Case).where(Case.case_number == case_dict["case_number"])
                    result = await session.execute(stmt)
                    existing_case = result.scalar_one_or_none()

                    if existing_case:
                        logger.debug("case_already_exists", case_number=case_dict["case_number"])
                        continue

                    # Create new case
                    case = Case(
                        case_number=case_dict["case_number"],
                        court=case_dict["court"],
                        case_type=case_dict.get("case_type", ""),
                        url=case_dict["url"],
                        plaintiff=case_dict.get("plaintiff", ""),
                        # Note: respondents is list, storing as JSON in text field for now
                        # Can be improved with proper JSONB column
                        status="pending",
                    )

                    session.add(case)
                    saved_count += 1

                await session.commit()

            except Exception as e:
                logger.error("failed_to_save_cases", error=str(e))
                await session.rollback()

        return saved_count

    async def _save_checkpoint(self) -> None:
        """Save current progress to checkpoint file."""
        checkpoint_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_cases": self._total_cases,
            "completed_tasks": [t.to_dict() for t in self.completed_tasks],
            "failed_tasks": [t.to_dict() for t in self.failed_tasks],
        }

        try:
            import json

            async with aiofiles.open(self.checkpoint_file, "w") as f:
                await f.write(json.dumps(checkpoint_data, indent=2, ensure_ascii=False))

            logger.debug("checkpoint_saved", file=str(self.checkpoint_file))

        except Exception as e:
            logger.error("failed_to_save_checkpoint", error=str(e))

    async def load_checkpoint(self) -> None:
        """Load progress from checkpoint file."""
        if not self.checkpoint_file.exists():
            logger.info("no_checkpoint_found")
            return

        try:
            import json

            async with aiofiles.open(self.checkpoint_file) as f:
                content = await f.read()
                checkpoint_data = json.loads(content)

            self._total_cases = checkpoint_data.get("total_cases", 0)

            # Load completed tasks
            for task_dict in checkpoint_data.get("completed_tasks", []):
                task = self._task_from_dict(task_dict)
                self.completed_tasks.append(task)

            # Load failed tasks
            for task_dict in checkpoint_data.get("failed_tasks", []):
                task = self._task_from_dict(task_dict)
                self.failed_tasks.append(task)

            logger.info(
                "checkpoint_loaded",
                total_cases=self._total_cases,
                completed=len(self.completed_tasks),
                failed=len(self.failed_tasks),
            )

        except Exception as e:
            logger.error("failed_to_load_checkpoint", error=str(e))

    @staticmethod
    def _task_from_dict(task_dict: dict[str, Any]) -> ParsingTask:
        """Convert dictionary to ParsingTask."""
        return ParsingTask(
            court_code=task_dict["court_code"],
            date_from=datetime.fromisoformat(task_dict["date_from"]).date(),
            date_to=datetime.fromisoformat(task_dict["date_to"]).date(),
            status=TaskStatus(task_dict["status"]),
            cases_count=task_dict.get("cases_count", 0),
            error_message=task_dict.get("error_message", ""),
            started_at=(
                datetime.fromisoformat(task_dict["started_at"])
                if task_dict.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(task_dict["completed_at"])
                if task_dict.get("completed_at")
                else None
            ),
        )

    def get_progress_stats(self) -> dict[str, Any]:
        """
        Get current progress statistics.

        Returns:
            Dictionary with progress stats
        """
        total_tasks = len(self.completed_tasks) + len(self.failed_tasks)
        pending_tasks = self.task_queue.qsize()

        return {
            "total_cases": self._total_cases,
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
            "pending_tasks": pending_tasks,
            "total_tasks": total_tasks + pending_tasks,
            "success_rate": (
                len(self.completed_tasks) / total_tasks * 100 if total_tasks > 0 else 0
            ),
        }
