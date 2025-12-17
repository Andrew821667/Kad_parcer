#!/usr/bin/env python3
"""
Интеграционный pipeline для обработки дел КАД Арбитр.

Pipeline:
1. Парсинг метаданных месяца → JSON
2. Импорт в SQL базу (дедупликация)
3. Для каждого дела:
   a. Скачать важные PDF
   b. Конвертировать PDF → MD
   c. Удалить PDF (экономия места)
   d. Обновить БД (md_path)
4. Статистика и отчет

Особенности:
- Checkpoint система для возобновления
- Обработка ошибок на каждом этапе
- Детальное логирование
- Статистика в реальном времени

Usage:
    python scripts/process_cases.py --month 2025-11 --db data/kad_2025.db
    python scripts/process_cases.py --resume checkpoint_2025-11.json
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import argparse
import os
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import SQLiteManager
from src.converter import batch_convert
from src.downloader import DocumentDownloader
from src.scraper.playwright_scraper import PlaywrightScraper


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PipelineCheckpoint:
    """Управление checkpoint'ами для возобновления pipeline."""

    def __init__(self, checkpoint_path: str):
        self.checkpoint_path = Path(checkpoint_path)
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        """Загрузить checkpoint из файла."""
        if self.checkpoint_path.exists():
            with open(self.checkpoint_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'stage': 'init',
            'month': None,
            'db_path': None,
            'processed_cases': [],
            'failed_cases': [],
            'stats': {
                'total_cases': 0,
                'imported_cases': 0,
                'downloaded_documents': 0,
                'converted_documents': 0,
                'failed_downloads': 0,
                'failed_conversions': 0,
            },
            'started_at': None,
            'updated_at': None,
        }

    def save(self):
        """Сохранить checkpoint."""
        self.data['updated_at'] = datetime.now().isoformat()
        with open(self.checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        logger.debug(f"Checkpoint saved: {self.checkpoint_path}")

    def update_stage(self, stage: str):
        """Обновить текущий этап."""
        self.data['stage'] = stage
        self.save()

    def mark_case_processed(self, case_number: str):
        """Отметить дело как обработанное."""
        if case_number not in self.data['processed_cases']:
            self.data['processed_cases'].append(case_number)
            self.save()

    def mark_case_failed(self, case_number: str, error: str):
        """Отметить дело как проваленное."""
        self.data['failed_cases'].append({
            'case_number': case_number,
            'error': str(error),
            'timestamp': datetime.now().isoformat()
        })
        self.save()

    def is_case_processed(self, case_number: str) -> bool:
        """Проверить, обработано ли дело."""
        return case_number in self.data['processed_cases']

    def update_stats(self, **kwargs):
        """Обновить статистику."""
        for key, value in kwargs.items():
            if key in self.data['stats']:
                self.data['stats'][key] += value
        self.save()


class CasePipeline:
    """Главный класс pipeline для обработки дел."""

    def __init__(self, checkpoint: PipelineCheckpoint, db_path: str,
                 download_dir: str = "downloads",
                 documents_dir: str = "documents"):
        self.checkpoint = checkpoint
        self.db_path = Path(db_path)
        self.download_dir = Path(download_dir)
        self.documents_dir = Path(documents_dir)

        # Создать директории
        self.download_dir.mkdir(exist_ok=True)
        self.documents_dir.mkdir(exist_ok=True)

    async def stage_1_parse_metadata(self, month: str, json_path: Optional[str] = None):
        """
        ЭТАП 1: Парсинг метаданных месяца.

        Args:
            month: Месяц в формате YYYY-MM
            json_path: Путь к готовому JSON (если уже спарсено)
        """
        logger.info("=" * 80)
        logger.info("ЭТАП 1: Парсинг метаданных месяца")
        logger.info("=" * 80)

        self.checkpoint.update_stage('parsing')
        self.checkpoint.data['month'] = month

        if json_path and Path(json_path).exists():
            logger.info(f"Используем готовый JSON: {json_path}")
            with open(json_path, 'r', encoding='utf-8') as f:
                cases = json.load(f)

            self.checkpoint.update_stats(total_cases=len(cases))
            logger.info(f"Загружено дел из JSON: {len(cases)}")
            return cases

        logger.warning("JSON файл не предоставлен. Пропускаем этап парсинга.")
        logger.warning("Используйте существующий парсер для создания JSON файла.")
        return []

    def stage_2_import_to_db(self, cases: List[Dict[str, Any]]):
        """
        ЭТАП 2: Импорт метаданных в SQL базу.

        Args:
            cases: Список дел из JSON
        """
        logger.info("=" * 80)
        logger.info("ЭТАП 2: Импорт в SQL базу")
        logger.info("=" * 80)

        self.checkpoint.update_stage('importing')

        try:
            with SQLiteManager(str(self.db_path)) as db:
                # Импорт с дедупликацией (INSERT OR IGNORE)
                imported = db.bulk_insert_cases(cases)
                duplicates = len(cases) - imported

                self.checkpoint.update_stats(imported_cases=imported)

                logger.info(f"Импортировано новых дел: {imported}")
                logger.info(f"Дубликатов (пропущено): {duplicates}")
                logger.info(f"Всего дел в базе: {db.get_stats()['total_cases']}")

                return imported

        except Exception as e:
            logger.error(f"Ошибка при импорте в БД: {e}")
            raise

    async def stage_3_download_and_convert(self, cases: List[Dict[str, Any]],
                                           scraper: PlaywrightScraper):
        """
        ЭТАП 3: Скачивание документов и конвертация в MD.

        Args:
            cases: Список дел для обработки
            scraper: Playwright scraper с CDP подключением
        """
        logger.info("=" * 80)
        logger.info("ЭТАП 3: Скачивание и конвертация документов")
        logger.info("=" * 80)

        self.checkpoint.update_stage('downloading_converting')

        downloader = DocumentDownloader(
            scraper,
            download_dir=str(self.download_dir),
            rate_limit_delay=5.0
        )

        # Обработка каждого дела
        for i, case in enumerate(cases, 1):
            case_number = case.get('case_number')

            if not case_number:
                logger.warning(f"Дело без номера, пропускаем: {case}")
                continue

            # Пропустить уже обработанные дела
            if self.checkpoint.is_case_processed(case_number):
                logger.debug(f"Дело уже обработано, пропускаем: {case_number}")
                continue

            logger.info(f"[{i}/{len(cases)}] Обработка дела: {case_number}")

            try:
                # Скачать документы
                case_url = case.get('url')  # URL из JSON (если есть)
                result = await self._download_case_documents(
                    downloader, case_number, case_url
                )

                if result['downloaded'] > 0:
                    # Конвертировать PDF → MD
                    await self._convert_case_documents(case_number)

                    # Обновить БД (md_path)
                    self._update_db_with_md_paths(case_number)

                    # Удалить PDF (экономия места)
                    self._cleanup_pdfs(case_number)

                # Обновить статистику
                self.checkpoint.update_stats(
                    downloaded_documents=result['downloaded'],
                    failed_downloads=result['failed']
                )

                # Отметить как обработанное
                self.checkpoint.mark_case_processed(case_number)

                logger.info(f"✓ Дело {case_number} обработано успешно")
                logger.info(f"  Скачано: {result['downloaded']}, Провалено: {result['failed']}")

            except Exception as e:
                logger.error(f"✗ Ошибка при обработке дела {case_number}: {e}")
                self.checkpoint.mark_case_failed(case_number, str(e))
                continue

            # Пауза между делами (rate limiting)
            await asyncio.sleep(2.0)

    async def _download_case_documents(self, downloader: DocumentDownloader,
                                      case_number: str, case_url: str = None) -> Dict[str, Any]:
        """Скачать документы дела."""
        try:
            result = await downloader.download_case_documents(
                case_number,
                case_url=case_url,
                filter_important=True
            )
            return result

        except Exception as e:
            logger.error(f"Ошибка скачивания документов для {case_number}: {e}")
            return {
                'total': 0,
                'filtered': 0,
                'downloaded': 0,
                'failed': 1,
                'documents': []
            }

    async def _convert_case_documents(self, case_number: str):
        """Конвертировать PDF → MD для дела."""
        # Извлечь год из номера дела
        parts = case_number.split("-")
        year = parts[-1] if len(parts) >= 3 else "unknown"

        # Путь к PDF файлам
        pdf_dir = self.download_dir / year / case_number

        if not pdf_dir.exists():
            logger.debug(f"Директория PDF не найдена: {pdf_dir}")
            return

        # Найти все PDF
        pdf_files = list(pdf_dir.glob("*.pdf"))

        if not pdf_files:
            logger.debug(f"PDF файлы не найдены в: {pdf_dir}")
            return

        # Создать директорию для MD
        md_dir = self.documents_dir / year / case_number
        md_dir.mkdir(parents=True, exist_ok=True)

        # Конвертировать batch'ем
        try:
            success, failed = batch_convert(
                [str(f) for f in pdf_files],
                str(md_dir),
                num_workers=4
            )

            self.checkpoint.update_stats(
                converted_documents=success,
                failed_conversions=failed
            )

            logger.info(f"  Конвертировано: {success}, Провалено: {failed}")

        except Exception as e:
            logger.error(f"Ошибка конвертации для {case_number}: {e}")
            self.checkpoint.update_stats(failed_conversions=len(pdf_files))

    def _update_db_with_md_paths(self, case_number: str):
        """Обновить БД путями к MD файлам."""
        parts = case_number.split("-")
        year = parts[-1] if len(parts) >= 3 else "unknown"

        md_dir = self.documents_dir / year / case_number

        if not md_dir.exists():
            return

        md_files = list(md_dir.glob("*.md"))

        try:
            with SQLiteManager(str(self.db_path)) as db:
                for md_file in md_files:
                    # Создать запись в таблице documents
                    db.insert_document({
                        'case_number': case_number,
                        'doc_type': md_file.stem,
                        'md_path': str(md_file.relative_to(self.documents_dir)),
                        'file_size': md_file.stat().st_size
                    })

        except Exception as e:
            logger.error(f"Ошибка обновления БД для {case_number}: {e}")

    def _cleanup_pdfs(self, case_number: str):
        """Удалить PDF файлы после конвертации."""
        parts = case_number.split("-")
        year = parts[-1] if len(parts) >= 3 else "unknown"

        pdf_dir = self.download_dir / year / case_number

        if pdf_dir.exists():
            try:
                import shutil
                shutil.rmtree(pdf_dir)
                logger.debug(f"PDF удалены: {pdf_dir}")
            except Exception as e:
                logger.warning(f"Не удалось удалить PDF: {e}")

    def print_final_report(self):
        """Вывести финальный отчет."""
        logger.info("=" * 80)
        logger.info("ФИНАЛЬНЫЙ ОТЧЕТ")
        logger.info("=" * 80)

        stats = self.checkpoint.data['stats']

        logger.info(f"Месяц: {self.checkpoint.data['month']}")
        logger.info(f"База данных: {self.db_path}")
        logger.info("")
        logger.info(f"Всего дел: {stats['total_cases']}")
        logger.info(f"Импортировано в БД: {stats['imported_cases']}")
        logger.info(f"Обработано дел: {len(self.checkpoint.data['processed_cases'])}")
        logger.info(f"Провалено дел: {len(self.checkpoint.data['failed_cases'])}")
        logger.info("")
        logger.info(f"Скачано документов: {stats['downloaded_documents']}")
        logger.info(f"Конвертировано в MD: {stats['converted_documents']}")
        logger.info(f"Провалено скачиваний: {stats['failed_downloads']}")
        logger.info(f"Провалено конвертаций: {stats['failed_conversions']}")
        logger.info("")

        if self.checkpoint.data['started_at']:
            started = datetime.fromisoformat(self.checkpoint.data['started_at'])
            duration = datetime.now() - started
            logger.info(f"Время выполнения: {duration}")

        logger.info("=" * 80)


async def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(
        description='Интеграционный pipeline для обработки дел КАД Арбитр'
    )

    # Режим запуска
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--month', help='Месяц для парсинга (YYYY-MM)')
    group.add_argument('--resume', help='Возобновить из checkpoint файла')

    # Параметры
    parser.add_argument('--db', help='Путь к базе данных SQLite')
    parser.add_argument('--json', help='Путь к JSON файлу с метаданными')
    parser.add_argument('--download-dir', default='downloads',
                       help='Директория для временных PDF')
    parser.add_argument('--documents-dir', default='documents',
                       help='Директория для MD документов')
    parser.add_argument('--cdp-url', default='http://localhost:9222',
                       help='URL для Chrome DevTools Protocol')

    args = parser.parse_args()

    # Определить checkpoint файл
    if args.resume:
        checkpoint_path = args.resume
    else:
        checkpoint_path = f"checkpoint_{args.month}.json"

    # Создать checkpoint
    checkpoint = PipelineCheckpoint(checkpoint_path)

    # Установить начальные параметры
    if not checkpoint.data['started_at']:
        checkpoint.data['started_at'] = datetime.now().isoformat()

    if args.month:
        checkpoint.data['month'] = args.month

    if args.db:
        checkpoint.data['db_path'] = args.db

    # Проверить обязательные параметры
    if not checkpoint.data['db_path']:
        logger.error("Не указан путь к базе данных (--db)")
        sys.exit(1)

    # Создать pipeline
    pipeline = CasePipeline(
        checkpoint,
        db_path=checkpoint.data['db_path'],
        download_dir=args.download_dir,
        documents_dir=args.documents_dir
    )

    try:
        # ЭТАП 1: Парсинг метаданных
        cases = await pipeline.stage_1_parse_metadata(
            checkpoint.data['month'],
            json_path=args.json
        )

        if not cases:
            logger.error("Нет дел для обработки. Укажите --json с файлом метаданных.")
            sys.exit(1)

        # ЭТАП 2: Импорт в БД
        pipeline.stage_2_import_to_db(cases)

        # ЭТАП 3: Скачивание и конвертация
        logger.info(f"Подключение к Chrome (CDP: {args.cdp_url})...")

        async with PlaywrightScraper(use_cdp=True, cdp_url=args.cdp_url) as scraper:
            logger.info("✓ Подключено к Chrome")
            await pipeline.stage_3_download_and_convert(cases, scraper)

        # Финальный отчет
        checkpoint.update_stage('completed')
        pipeline.print_final_report()

        logger.info("✓ Pipeline завершен успешно!")

    except KeyboardInterrupt:
        logger.warning("Pipeline прерван пользователем")
        checkpoint.update_stage('interrupted')
        pipeline.print_final_report()
        sys.exit(1)

    except Exception as e:
        logger.error(f"Критическая ошибка pipeline: {e}")
        checkpoint.update_stage('failed')
        pipeline.print_final_report()
        raise


if __name__ == "__main__":
    asyncio.run(main())
