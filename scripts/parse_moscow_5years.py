#!/usr/bin/env python3
"""
Master script to parse 5 years of Moscow district arbitration court decisions (2020-2025).

This script orchestrates the entire parsing operation:
- Generates tasks for all 18 courts × 60 months = 1,080 tasks
- Manages 5-10 parallel browser instances
- Tracks progress with checkpoints
- Saves data to PostgreSQL

Expected: ~1.75 million cases over ~15 days of continuous parsing.

Usage:
    python scripts/parse_moscow_5years.py --workers 10 --headless
"""

from __future__ import annotations

import asyncio
from calendar import monthrange
from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from structlog import get_logger

from src.scraper.parallel_parser import ParallelParser, ParsingTask

logger = get_logger(__name__)
console = Console()
app = typer.Typer()


# Moscow District Courts (18 courts)
COURTS = {
    # Cassation (1)
    "А40-КС": "Арбитражный суд Московского округа (кассация)",
    # Appeal (1)
    "А40-АП": "Девятый арбитражный апелляционный суд",
    # First instance (16)
    "А40": "Арбитражный суд г. Москвы",
    "А41": "Арбитражный суд Московской области",
    "А54": "Арбитражный суд Рязанской области",
    "А56": "Арбитражный суд Санкт-Петербурга и ЛО",
    "А13": "Арбитражный суд Вологодской области",
    "А05": "Арбитражный суд Архангельской области",
    "А66": "Арбитражный суд Тверской области",
    "А21": "Арбитражный суд Калининградской области",
    "А26": "Арбитражный суд Республики Карелия",
    "А42": "Арбитражный суд Мурманской области",
    "А44": "Арбитражный суд Новгородской области",
    "А52": "Арбитражный суд Псковской области",
    "А14": "Арбитражный суд Воронежской области",
    "А36": "Арбитражный суд Липецкой области",
    "А08": "Арбитражный суд Белгородской области",
    "А64": "Арбитражный суд Тамбовской области",
}

# Court priorities (for phased approach)
PRIORITY_1_CASSATION = ["А40-КС"]
PRIORITY_2_APPEAL = ["А40-АП"]
PRIORITY_3_LARGE = ["А40", "А41", "А56"]
PRIORITY_4_MEDIUM = ["А14", "А54", "А66", "А36", "А08", "А13", "А05"]
PRIORITY_5_SMALL = ["А21", "А26", "А42", "А44", "А52", "А64"]

# Date range for 5 years
START_YEAR = 2020
END_YEAR = 2025
END_MONTH = 12  # Current month (adjust if needed)


def generate_monthly_tasks(
    court_code: str,
    start_year: int,
    end_year: int,
    end_month: int = 12,
) -> list[ParsingTask]:
    """
    Generate monthly parsing tasks for a court.

    Args:
        court_code: Court code (e.g. 'А40')
        start_year: First year (e.g. 2020)
        end_year: Last year (e.g. 2025)
        end_month: Last month for end_year (e.g. 12 for December)

    Returns:
        List of parsing tasks (one per month)
    """
    tasks = []

    for year in range(start_year, end_year + 1):
        # Determine months range for this year
        if year == end_year:
            months = range(1, end_month + 1)
        else:
            months = range(1, 13)

        for month in months:
            # Get first and last day of month
            _, last_day = monthrange(year, month)
            date_from = date(year, month, 1)
            date_to = date(year, month, last_day)

            task = ParsingTask(
                court_code=court_code,
                date_from=date_from,
                date_to=date_to,
            )
            tasks.append(task)

    return tasks


def generate_all_tasks(
    start_year: int = START_YEAR,
    end_year: int = END_YEAR,
    end_month: int = END_MONTH,
    prioritized: bool = True,
) -> list[ParsingTask]:
    """
    Generate all parsing tasks for all courts.

    Args:
        start_year: First year
        end_year: Last year
        end_month: Last month for end_year
        prioritized: Order by priority (cassation first, then appeal, etc.)

    Returns:
        List of all parsing tasks
    """
    all_tasks = []

    if prioritized:
        # Order by priority
        court_groups = [
            PRIORITY_1_CASSATION,
            PRIORITY_2_APPEAL,
            PRIORITY_3_LARGE,
            PRIORITY_4_MEDIUM,
            PRIORITY_5_SMALL,
        ]
        courts_ordered = [c for group in court_groups for c in group]
    else:
        # Alphabetical order
        courts_ordered = sorted(COURTS.keys())

    for court_code in courts_ordered:
        court_tasks = generate_monthly_tasks(court_code, start_year, end_year, end_month)
        all_tasks.extend(court_tasks)

    return all_tasks


def display_plan(tasks: list[ParsingTask]) -> None:
    """Display parsing plan in rich table."""
    console.print("\n[bold cyan]📊 ПЛАН ПАРСИНГА: 5 ЛЕТ МОСКОВСКОГО ОКРУГА[/bold cyan]\n")

    # Count tasks per court
    court_task_counts: dict[str, int] = {}
    for task in tasks:
        court_task_counts[task.court_code] = court_task_counts.get(task.court_code, 0) + 1

    # Create table
    table = Table(title="18 Судов Московского Округа")
    table.add_column("Код", style="cyan", no_wrap=True)
    table.add_column("Название суда", style="white")
    table.add_column("Периодов", justify="right", style="green")
    table.add_column("Приоритет", justify="center", style="yellow")

    # Add rows by priority
    def get_priority_label(court: str) -> str:
        if court in PRIORITY_1_CASSATION:
            return "⭐⭐⭐⭐⭐"
        if court in PRIORITY_2_APPEAL:
            return "⭐⭐⭐⭐"
        if court in PRIORITY_3_LARGE:
            return "⭐⭐⭐"
        if court in PRIORITY_4_MEDIUM:
            return "⭐⭐"
        return "⭐"

    for court_code in court_task_counts:
        table.add_row(
            court_code,
            COURTS.get(court_code, "Unknown"),
            str(court_task_counts[court_code]),
            get_priority_label(court_code),
        )

    console.print(table)

    console.print(f"\n[bold]Всего задач:[/bold] {len(tasks)}")
    console.print(f"[bold]Период:[/bold] {START_YEAR} - {END_YEAR}")
    console.print(f"[bold]Примерная оценка дел:[/bold] ~1,750,000\n")


async def display_live_progress(parser: ParallelParser) -> None:
    """Display live progress during parsing."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
    ) as progress:
        # Add main progress bar
        main_task = progress.add_task("[cyan]Парсинг дел...", total=None)

        while not progress.finished:
            stats = parser.get_progress_stats()

            # Update progress
            if stats["total_tasks"] > 0:
                progress.update(
                    main_task,
                    description=f"[cyan]Парсинг: {stats['total_cases']:,} дел",
                    completed=stats["completed_tasks"],
                    total=stats["total_tasks"],
                )

            # Display current stats
            console.print(
                f"\r[green]✓ Завершено:[/green] {stats['completed_tasks']} | "
                f"[red]✗ Ошибок:[/red] {stats['failed_tasks']} | "
                f"[yellow]⏳ В очереди:[/yellow] {stats['pending_tasks']} | "
                f"[cyan]📊 Дел всего:[/cyan] {stats['total_cases']:,}",
                end="",
            )

            await asyncio.sleep(5)


@app.command()
def main(
    workers: int = typer.Option(5, "--workers", "-w", help="Количество параллельных браузеров"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Headless режим"),
    checkpoint_file: Path = typer.Option(
        Path("parsing_progress.json"),
        "--checkpoint",
        "-c",
        help="Файл для сохранения прогресса",
    ),
    test_mode: bool = typer.Option(
        False,
        "--test",
        help="Тестовый режим (только кассация за 2024)",
    ),
    resume: bool = typer.Option(
        False,
        "--resume",
        help="Продолжить с последнего чекпоинта",
    ),
) -> None:
    """
    Запустить парсинг 5-летней выборки Московского округа.

    Парсит 18 судов за 2020-2025 годы с помощью нескольких параллельных браузеров.
    """
    console.print("\n[bold magenta]🚀 КАД АРБИТР - ПАРСЕР МОСКОВСКОГО ОКРУГА[/bold magenta]\n")

    # Generate tasks
    if test_mode:
        console.print("[yellow]⚠️  ТЕСТОВЫЙ РЕЖИМ:[/yellow] Только кассация за 2024\n")
        tasks = generate_monthly_tasks("А40-КС", 2024, 2024, 12)
    else:
        tasks = generate_all_tasks()

    # Display plan
    display_plan(tasks)

    # Confirm start
    if not test_mode:
        confirm = typer.confirm(
            "\n✅ Начать парсинг? (Это займет ~15 дней непрерывной работы)",
            default=True,
        )
        if not confirm:
            console.print("[yellow]Отменено пользователем[/yellow]")
            raise typer.Exit()

    # Run parsing
    asyncio.run(
        run_parsing(
            tasks=tasks,
            workers=workers,
            headless=headless,
            checkpoint_file=checkpoint_file,
            resume=resume,
        )
    )


async def run_parsing(
    tasks: list[ParsingTask],
    workers: int,
    headless: bool,
    checkpoint_file: Path,
    resume: bool,
) -> None:
    """
    Run the parsing operation.

    Args:
        tasks: List of parsing tasks
        workers: Number of parallel workers
        headless: Headless browser mode
        checkpoint_file: Checkpoint file path
        resume: Resume from checkpoint
    """
    console.print(f"\n[cyan]Запуск {workers} параллельных браузеров...[/cyan]\n")

    # Initialize parser
    parser = ParallelParser(
        num_workers=workers,
        headless=headless,
        checkpoint_file=checkpoint_file,
    )

    # Load checkpoint if resuming
    if resume:
        await parser.load_checkpoint()
        console.print("[green]✓[/green] Прогресс загружен из чекпоинта\n")

    # Add tasks
    await parser.add_tasks(tasks)

    # Start workers
    await parser.start()

    try:
        # Monitor progress
        console.print("[cyan]Парсинг запущен! Нажмите Ctrl+C для остановки.[/cyan]\n")

        # Simple progress loop
        while True:
            stats = parser.get_progress_stats()

            console.print(
                f"\r[green]✓ {stats['completed_tasks']}[/green] | "
                f"[red]✗ {stats['failed_tasks']}[/red] | "
                f"[yellow]⏳ {stats['pending_tasks']}[/yellow] | "
                f"[cyan]📊 {stats['total_cases']:,} дел[/cyan]",
                end="",
            )

            # Check if done
            if stats["pending_tasks"] == 0 and parser.task_queue.empty():
                break

            await asyncio.sleep(5)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠️  Прерывание пользователем...[/yellow]")

    finally:
        # Stop parser
        await parser.stop()

        # Final statistics
        stats = parser.get_progress_stats()

        console.print("\n\n[bold green]✅ ПАРСИНГ ЗАВЕРШЕН![/bold green]\n")

        results_table = Table(title="Итоговая статистика")
        results_table.add_column("Метрика", style="cyan")
        results_table.add_column("Значение", style="white", justify="right")

        results_table.add_row("Всего дел спарсено", f"{stats['total_cases']:,}")
        results_table.add_row("Задач завершено", str(stats["completed_tasks"]))
        results_table.add_row("Задач с ошибками", str(stats["failed_tasks"]))
        results_table.add_row(
            "Успешность",
            f"{stats['success_rate']:.1f}%",
        )

        console.print(results_table)

        if stats["failed_tasks"] > 0:
            console.print(
                f"\n[yellow]⚠️  {stats['failed_tasks']} задач завершились с ошибками.[/yellow]"
            )
            console.print("[yellow]Проверьте лог-файлы для деталей.[/yellow]")

        console.print(f"\n[green]Прогресс сохранен в:[/green] {checkpoint_file}")


if __name__ == "__main__":
    app()
