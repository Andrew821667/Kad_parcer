#!/usr/bin/env python3
"""
Интеграционный pipeline - связывает существующий workflow с новыми модулями.

WORKFLOW:
1. Парсинг: parse_january_by_day_and_court.py → JSON
2. Скачивание: download_all_electronic_case_docs.py → PDFs
3. Конвертация: converter → Markdown
4. База данных: sqlite_manager → metadata storage

Usage:
    python scripts/integrate_pipeline.py \
        --json data/january_2024_cases.json \
        --db data/kad_2024.db \
        --downloads downloads/ \
        --documents documents/
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
import shutil

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scraper.playwright_scraper import PlaywrightScraper
from src.database import SQLiteManager
from src.converter import convert_pdf_to_md, batch_convert
import httpx


async def download_case_documents(scraper, case: dict, downloads_dir: Path):
    """
    Скачивает документы для одного дела (логика из download_all_electronic_case_docs.py).

    Args:
        scraper: PlaywrightScraper instance
        case: Case data dict with 'case_number' and 'url'
        downloads_dir: Directory for downloads

    Returns:
        List of downloaded PDF paths
    """
    case_number = case['case_number']
    case_url = case['url']

    # Нормализация URL
    case_url = case_url.replace('https//kad.arbitr.ru', '').replace('http//kad.arbitr.ru', '').replace('//kad.arbitr.ru', '').replace('https://kad.arbitr.ru', '').replace('http://kad.arbitr.ru', '').replace('https:/', '').replace('http:/', '')
    if not case_url.startswith('/'):
        case_url = '/' + case_url
    case_url = f"https://kad.arbitr.ru{case_url}"

    print(f"\n📋 Дело: {case_number}")
    print(f"🔗 URL: {case_url}")

    # Создать папку для скачивания
    case_folder = downloads_dir / case_number.replace('/', '_')
    case_folder.mkdir(parents=True, exist_ok=True)

    # Открыть страницу дела
    await scraper.page.goto(case_url, wait_until="networkidle", timeout=30000)
    await asyncio.sleep(2)

    # Переход на вкладку "Электронное дело"
    electronic_tab = await scraper.page.query_selector(".js-case-chrono-button--ed")

    if not electronic_tab:
        print("❌ Вкладка 'Электронное дело' не найдена")
        return []

    await electronic_tab.click()
    await asyncio.sleep(3)

    # Получить cookies для скачивания
    cookies = await scraper.page.context.cookies()
    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

    # Скачивание документов со всех страниц
    page_num = 1
    downloaded_files = []
    downloaded_urls = set()

    while True:
        # Найти все PDF на текущей странице
        pdf_links = await scraper.page.query_selector_all('a[href$=".pdf"]')

        if not pdf_links:
            break

        # Скачать каждый PDF
        for i, link in enumerate(pdf_links, 1):
            try:
                href = await link.get_attribute("href")

                # Пропустить если уже скачивали
                if href in downloaded_urls:
                    continue

                downloaded_urls.add(href)

                # Скачать PDF через HTTP с retry
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        async with httpx.AsyncClient(
                            cookies=cookie_dict,
                            timeout=30.0,
                            follow_redirects=True
                        ) as client:
                            response = await client.get(href)

                            if response.status_code == 200:
                                content_type = response.headers.get('content-type', '')

                                if 'pdf' in content_type.lower() or href.endswith('.pdf'):
                                    # Извлечь имя файла из URL
                                    filename = href.split("/")[-1]
                                    if not filename.endswith('.pdf'):
                                        filename += '.pdf'

                                    # Добавить номер для уникальности
                                    filepath = case_folder / f"{len(downloaded_files) + 1:03d}_{filename}"

                                    filepath.write_bytes(response.content)
                                    downloaded_files.append(filepath)

                                    print(f"   ✅ {len(response.content)//1024} KB → {filepath.name}")
                                    break

                            else:
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(2)

                    except Exception as e:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2)
                        else:
                            print(f"   ❌ Ошибка после {max_retries} попыток: {str(e)[:60]}")

            except Exception as e:
                print(f"   ❌ Критическая ошибка: {str(e)[:60]}")

        # Проверка наличия следующей страницы
        next_button = await scraper.page.query_selector(".js-chrono-pagination-pager-item--arrow.next")

        if not next_button:
            next_button = await scraper.page.query_selector(".js-card-list_paginator-item.next")

        if not next_button:
            break

        # Проверить что кнопка активна
        try:
            is_disabled = await next_button.evaluate("el => el.classList.contains('disabled') || el.hasAttribute('disabled')")
            if is_disabled:
                break
        except:
            pass

        # Кликнуть на следующую страницу
        try:
            await next_button.click()
            await asyncio.sleep(3)
            page_num += 1
        except:
            break

    print(f"✅ Скачано документов: {len(downloaded_files)}")
    return downloaded_files


def convert_pdfs_to_markdown(pdf_files: list, documents_dir: Path, case_number: str):
    """
    Конвертирует PDF → Markdown.

    Args:
        pdf_files: List of PDF file paths
        documents_dir: Base documents directory
        case_number: Case number

    Returns:
        List of created MD file paths
    """
    if not pdf_files:
        return []

    print(f"\n🔄 Конвертация {len(pdf_files)} PDF → Markdown...")

    # Создать папку для MD файлов
    # Извлечь год из номера дела (например, А40-12345-2024 → 2024)
    parts = case_number.split('-')
    year = parts[-1] if len(parts) >= 3 else "unknown"

    case_md_dir = documents_dir / year / case_number.replace('/', '_')
    case_md_dir.mkdir(parents=True, exist_ok=True)

    md_files = []
    success_count = 0
    failed_count = 0

    for pdf_path in pdf_files:
        try:
            # Создать MD путь
            md_filename = pdf_path.stem + '.md'
            md_path = case_md_dir / md_filename

            # Конвертировать
            success = convert_pdf_to_md(str(pdf_path), str(md_path))

            if success:
                md_files.append(md_path)
                success_count += 1
                print(f"   ✅ {pdf_path.name} → {md_filename}")
            else:
                failed_count += 1
                print(f"   ❌ Ошибка конвертации: {pdf_path.name}")

        except Exception as e:
            failed_count += 1
            print(f"   ❌ Ошибка: {pdf_path.name} - {str(e)[:60]}")

    print(f"\n📊 Конвертация завершена: {success_count} успешно, {failed_count} ошибок")
    return md_files


def store_in_database(db: SQLiteManager, case: dict, md_files: list):
    """
    Сохраняет метаданные дела и документов в БД.

    Args:
        db: SQLiteManager instance
        case: Case data dict
        md_files: List of Markdown file paths
    """
    print(f"\n💾 Сохранение в БД...")

    # Вставить дело (если еще нет)
    if not db.case_exists(case['case_number']):
        db.insert_case({
            'case_number': case['case_number'],
            'court': case.get('court', ''),
            'registration_date': case.get('case_date', ''),
            'status': '',
            'parties': ''
        })
        print(f"   ✅ Дело добавлено: {case['case_number']}")
    else:
        print(f"   ℹ️  Дело уже существует: {case['case_number']}")

    # Вставить документы
    for md_path in md_files:
        doc_data = {
            'case_number': case['case_number'],
            'doc_type': md_path.stem,  # Имя файла как тип
            'instance': '',
            'is_final': False,
            'pdf_url': '',
            'md_path': str(md_path),
            'file_size': md_path.stat().st_size if md_path.exists() else 0
        }

        db.insert_document(doc_data)

    print(f"   ✅ Документов добавлено: {len(md_files)}")


async def process_single_case(scraper, db: SQLiteManager, case: dict, downloads_dir: Path, documents_dir: Path, cleanup_pdfs: bool = True):
    """
    Обрабатывает одно дело: скачивание → конвертация → БД.

    Args:
        scraper: PlaywrightScraper instance
        db: SQLiteManager instance
        case: Case data dict
        downloads_dir: Directory for PDF downloads
        documents_dir: Directory for MD documents
        cleanup_pdfs: Delete PDFs after conversion (default: True)
    """
    case_number = case['case_number']

    print("\n" + "=" * 80)
    print(f"ОБРАБОТКА ДЕЛА: {case_number}")
    print("=" * 80)

    try:
        # 1. Скачивание PDF
        pdf_files = await download_case_documents(scraper, case, downloads_dir)

        if not pdf_files:
            print(f"⚠️  Нет документов для скачивания")
            return

        # 2. Конвертация PDF → MD
        md_files = convert_pdfs_to_markdown(pdf_files, documents_dir, case_number)

        # 3. Сохранение в БД
        store_in_database(db, case, md_files)

        # 4. Очистка PDF (опционально)
        if cleanup_pdfs and pdf_files:
            case_folder = pdf_files[0].parent
            try:
                shutil.rmtree(case_folder)
                print(f"\n🗑️  PDF удалены (экономия места)")
            except:
                pass

        print(f"\n✅ ДЕЛО ОБРАБОТАНО: {case_number}")

    except Exception as e:
        print(f"\n❌ ОШИБКА ПРИ ОБРАБОТКЕ ДЕЛА {case_number}: {str(e)}")
        import traceback
        traceback.print_exc()


async def process_multiple_cases(json_path: str, db_path: str, downloads_dir: str = "downloads", documents_dir: str = "documents", start_index: int = 0, max_cases: int = None, cdp_url: str = "http://localhost:9222"):
    """
    Обрабатывает несколько дел из JSON файла.

    Args:
        json_path: Path to JSON file with cases
        db_path: Path to SQLite database
        downloads_dir: Directory for PDF downloads
        documents_dir: Directory for MD documents
        start_index: Start from this case index (for resuming)
        max_cases: Maximum number of cases to process (None = all)
        cdp_url: Chrome CDP URL (default: http://localhost:9222)
    """
    print("=" * 80)
    print("🚀 ИНТЕГРАЦИОННЫЙ PIPELINE")
    print("=" * 80)
    print()

    # Загрузить дела из JSON
    json_file = Path(json_path)
    if not json_file.exists():
        print(f"❌ Файл не найден: {json_path}")
        return

    with open(json_file, encoding='utf-8') as f:
        all_cases = json.load(f)

    # Фильтрация диапазона
    cases_to_process = all_cases[start_index:]
    if max_cases:
        cases_to_process = cases_to_process[:max_cases]

    print(f"📂 JSON файл: {json_path}")
    print(f"📊 Всего дел в файле: {len(all_cases)}")
    print(f"📊 Дел к обработке: {len(cases_to_process)} (индекс {start_index} - {start_index + len(cases_to_process) - 1})")
    print()

    # Создать директории
    downloads_path = Path(downloads_dir)
    documents_path = Path(documents_dir)
    downloads_path.mkdir(exist_ok=True)
    documents_path.mkdir(exist_ok=True)

    # Подключиться к БД
    db = SQLiteManager(db_path)
    print(f"✅ База данных: {db_path}")

    # Статистика
    stats = db.get_stats()
    print(f"   Дел в БД: {stats['total_cases']}")
    print(f"   Документов в БД: {stats['total_documents']}")
    print()

    # Подключиться к Chrome через CDP
    print(f"🔌 Подключение к Chrome (CDP: {cdp_url})...")
    async with PlaywrightScraper(use_cdp=True, cdp_url=cdp_url) as scraper:
        print("✅ Подключено к Chrome")
        print()

        start_time = datetime.now()

        # Обработать каждое дело
        for idx, case in enumerate(cases_to_process, start=start_index + 1):
            print(f"\n[{idx}/{len(all_cases)}] ", end="")

            try:
                await process_single_case(
                    scraper,
                    db,
                    case,
                    downloads_path,
                    documents_path,
                    cleanup_pdfs=True
                )

                # Пауза между делами
                if idx < len(cases_to_process):
                    await asyncio.sleep(3.0)

            except Exception as e:
                print(f"❌ Критическая ошибка: {str(e)}")
                continue

        elapsed = (datetime.now() - start_time).total_seconds()

        # Финальная статистика
        print("\n" + "=" * 80)
        print("🎉 ОБРАБОТКА ЗАВЕРШЕНА")
        print("=" * 80)
        print()

        final_stats = db.get_stats()
        print(f"📊 Дел в БД: {final_stats['total_cases']}")
        print(f"📊 Документов в БД: {final_stats['total_documents']}")
        print(f"⏱️  Время: {elapsed/60:.1f} минут")
        print()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Интеграционный pipeline для обработки дел")
    parser.add_argument('--json', required=True, help='Path to JSON file with cases')
    parser.add_argument('--db', required=True, help='Path to SQLite database')
    parser.add_argument('--downloads', default='downloads', help='Directory for PDF downloads')
    parser.add_argument('--documents', default='documents', help='Directory for MD documents')
    parser.add_argument('--start-index', type=int, default=0, help='Start from case index (for resuming)')
    parser.add_argument('--max-cases', type=int, help='Maximum number of cases to process')
    parser.add_argument('--cdp-url', default='http://localhost:9222', help='Chrome CDP URL (default: http://localhost:9222)')

    args = parser.parse_args()

    asyncio.run(process_multiple_cases(
        json_path=args.json,
        db_path=args.db,
        downloads_dir=args.downloads,
        documents_dir=args.documents,
        start_index=args.start_index,
        max_cases=args.max_cases,
        cdp_url=args.cdp_url
    ))


if __name__ == "__main__":
    main()
