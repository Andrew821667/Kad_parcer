#!/usr/bin/env python3
"""
Полный pipeline: парсинг + скачивание PDF + конвертация в MD.

Этапы:
1. Парсинг 40 страниц января 2024
2. Скачивание 100 PDF судебных актов
3. Конвертация PDF в MD (для экономии места)
4. Сохранение статистики
"""

import asyncio
import json
import random
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Any

import httpx
from structlog import get_logger

from src.scraper.playwright_scraper import PlaywrightScraper

logger = get_logger(__name__)

# Попробуем импортировать pdfplumber для конвертации
try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    print("⚠️  pdfplumber не установлен. PDF→MD конвертация будет пропущена.")
    print("   Установите: pip install pdfplumber")
    PDF_SUPPORT = False


def pdf_to_markdown(pdf_path: Path) -> str:
    """
    Конвертировать PDF в Markdown.

    Извлекает текст со всех страниц и форматирует в MD.
    """
    if not PDF_SUPPORT:
        return ""

    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = []
            for i, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    pages_text.append(f"# Страница {i}\n\n{text}\n")

            return "\n---\n\n".join(pages_text)
    except Exception as e:
        logger.error("pdf_conversion_failed", path=str(pdf_path), error=str(e))
        return ""


def calculate_pdf_hash(pdf_bytes: bytes) -> str:
    """Вычислить SHA256 hash PDF для дедупликации."""
    return hashlib.sha256(pdf_bytes).hexdigest()


async def parse_and_download():
    """Полный pipeline парсинга и скачивания."""

    print("=" * 80)
    print("🚀 ПОЛНЫЙ PIPELINE: ПАРСИНГ + PDF + MD КОНВЕРТАЦИЯ")
    print("=" * 80)
    print()

    # Создать директории
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    pdfs_dir = data_dir / "january_2024_pdfs"
    pdfs_dir.mkdir(exist_ok=True)

    mds_dir = data_dir / "january_2024_mds"
    mds_dir.mkdir(exist_ok=True)

    # Запуск без CDP (работает в контейнерах)
    print("🌐 Запуск браузера (без CDP для совместимости)...")
    async with PlaywrightScraper(use_cdp=False) as scraper:
        print("✅ Браузер запущен\n")

        # ============================================================
        # ШАГ 1: Парсинг 40 страниц
        # ============================================================

        print("=" * 80)
        print("ШАГ 1: Парсинг всех 40 страниц (январь 2024)")
        print("=" * 80)
        print()

        # Открыть КАД Арбитр
        await scraper.page.goto("https://kad.arbitr.ru", wait_until="networkidle")
        await asyncio.sleep(2)

        # Закрыть popup
        try:
            await scraper.page.keyboard.press("Escape")
            await asyncio.sleep(1)
        except Exception:
            pass

        # Заполнить форму
        date_inputs = await scraper.page.query_selector_all('input[placeholder="дд.мм.гггг"]')
        if len(date_inputs) >= 2:
            await date_inputs[0].click()
            await asyncio.sleep(0.2)
            await date_inputs[0].fill("01.01.2024")
            await asyncio.sleep(0.5)

            await date_inputs[1].click()
            await asyncio.sleep(0.2)
            await date_inputs[1].fill("31.01.2024")
            await asyncio.sleep(0.5)

        await scraper.page.click("body")
        await asyncio.sleep(0.5)

        # Отправить форму
        await scraper.page.click("#b-form-submit")
        await asyncio.sleep(5)

        # Определить количество страниц
        total_pages_input = await scraper.page.query_selector("input#documentsPagesCount")
        if not total_pages_input:
            print("❌ Таблица результатов не найдена")
            return

        total_pages_str = await total_pages_input.get_attribute("value")
        total_pages = int(total_pages_str) if total_pages_str else 0

        print(f"📄 Найдено страниц: {total_pages}")
        print(f"📄 Будем парсить: ВСЕ {total_pages} страницы")
        print()

        # Парсинг всех страниц
        all_cases = []
        start_time = datetime.now()

        for page_num in range(1, total_pages + 1):
            print(f"📖 Страница {page_num}/{total_pages}...", end=" ")

            try:
                cases = await scraper._parse_current_page()
                all_cases.extend(cases)
                print(f"✓ {len(cases)} дел (всего: {len(all_cases)})")

                # Промежуточное сохранение каждые 10 страниц
                if page_num % 10 == 0:
                    temp_file = data_dir / f"january_2024_cases_page_{page_num}.json"
                    temp_file.write_text(
                        json.dumps(all_cases, ensure_ascii=False, indent=2),
                        encoding="utf-8"
                    )
                    print(f"   💾 Checkpoint: {len(all_cases)} дел")

            except Exception as e:
                print(f"❌ Ошибка: {e}")
                continue

            # Переход на следующую страницу
            if page_num < total_pages:
                try:
                    link = await scraper.page.query_selector(f'a[href="#page{page_num + 1}"]')
                    if link:
                        await link.click()
                        await asyncio.sleep(5)
                    else:
                        print(f"   ⚠️  Ссылка на страницу {page_num + 1} не найдена")
                        break
                except Exception as e:
                    print(f"   ❌ Ошибка навигации: {e}")
                    break

        parsing_time = (datetime.now() - start_time).total_seconds()

        print()
        print(f"✅ Парсинг завершен: {len(all_cases)} дел за {parsing_time:.1f} сек")
        print()

        # Сохранить все дела
        cases_file = data_dir / "january_2024_cases.json"
        cases_file.write_text(
            json.dumps(all_cases, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"💾 Сохранено: {cases_file}")
        print()

        # ============================================================
        # ШАГ 2: Скачивание 100 PDF
        # ============================================================

        print("=" * 80)
        print("ШАГ 2: Скачивание 100 PDF судебных актов")
        print("=" * 80)
        print()

        NUM_PDFS = min(100, len(all_cases))
        selected_cases = random.sample(all_cases, NUM_PDFS)

        print(f"📋 Выбрано дел для скачивания: {NUM_PDFS}")
        print()

        downloaded_count = 0
        converted_count = 0
        download_errors = []
        pdf_metadata = []

        for i, case in enumerate(selected_cases, 1):
            print(f"📄 [{i}/{NUM_PDFS}] {case['case_number']}")

            try:
                # Открыть страницу дела
                case_url = case['url']
                if not case_url.startswith('http'):
                    case_url = f"https://kad.arbitr.ru{case_url}"

                await scraper.page.goto(case_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)

                # Найти PDF ссылки
                doc_links = await scraper.page.query_selector_all('a[href$=".pdf"]')

                if not doc_links:
                    print(f"   ⚠️  PDF не найден")
                    download_errors.append({
                        "case_number": case["case_number"],
                        "error": "no_pdf_links"
                    })
                    continue

                # Взять первую ссылку
                first_link = doc_links[0]
                link_text = await first_link.inner_text()
                pdf_url = await first_link.get_attribute("href")

                # Скачать PDF
                cookies = await scraper.page.context.cookies()
                cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

                async with httpx.AsyncClient(
                    cookies=cookie_dict,
                    timeout=30.0,
                    follow_redirects=True
                ) as client:
                    response = await client.get(pdf_url)

                    if response.status_code == 200:
                        content_type = response.headers.get('content-type', '')

                        if 'pdf' in content_type.lower() or pdf_url.endswith('.pdf'):
                            pdf_content = response.content
                            pdf_hash = calculate_pdf_hash(pdf_content)

                            # Сохранить PDF
                            filename = f"{case['case_number'].replace('/', '_')}.pdf"
                            pdf_path = pdfs_dir / filename
                            pdf_path.write_bytes(pdf_content)

                            print(f"   ✅ PDF: {len(pdf_content)//1024} KB")
                            downloaded_count += 1

                            # Конвертация в MD
                            if PDF_SUPPORT:
                                md_content = pdf_to_markdown(pdf_path)
                                if md_content:
                                    md_filename = filename.replace('.pdf', '.md')
                                    md_path = mds_dir / md_filename
                                    md_path.write_text(md_content, encoding='utf-8')

                                    # Экономия места
                                    md_size = len(md_content.encode('utf-8'))
                                    savings_pct = (1 - md_size / len(pdf_content)) * 100

                                    print(f"   ✅ MD: {md_size//1024} KB (экономия: {savings_pct:.0f}%)")
                                    converted_count += 1

                            # Метаданные
                            pdf_metadata.append({
                                "case_number": case["case_number"],
                                "case_date": case["case_date"],
                                "judge": case.get("judge"),
                                "court": case.get("court"),
                                "pdf_filename": filename,
                                "pdf_size": len(pdf_content),
                                "pdf_hash": pdf_hash,
                                "pdf_url": pdf_url,
                                "document_title": link_text[:100],
                                "has_markdown": PDF_SUPPORT and md_content != "",
                            })
                        else:
                            print(f"   ⚠️  Не PDF (Content-Type: {content_type})")
                            download_errors.append({
                                "case_number": case["case_number"],
                                "error": f"wrong_content_type: {content_type}"
                            })
                    else:
                        print(f"   ❌ HTTP {response.status_code}")
                        download_errors.append({
                            "case_number": case["case_number"],
                            "error": f"http_{response.status_code}"
                        })

            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
                download_errors.append({
                    "case_number": case["case_number"],
                    "error": str(e)
                })
                continue

            # Пауза между запросами
            await asyncio.sleep(1)

        print()
        print(f"✅ Скачивание завершено: {downloaded_count}/{NUM_PDFS} PDF")
        if PDF_SUPPORT:
            print(f"✅ Конвертация завершена: {converted_count}/{downloaded_count} MD")
        print()

        # Сохранить метаданные
        pdf_metadata_file = data_dir / "january_2024_pdf_metadata.json"
        pdf_metadata_file.write_text(
            json.dumps(pdf_metadata, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        # ============================================================
        # СТАТИСТИКА
        # ============================================================

        print("=" * 80)
        print("ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 80)
        print()

        stats = {
            "parsing": {
                "total_cases": len(all_cases),
                "pages_parsed": total_pages,
                "parsing_time_sec": parsing_time,
            },
            "downloading": {
                "pdfs_requested": NUM_PDFS,
                "pdfs_downloaded": downloaded_count,
                "pdfs_converted_to_md": converted_count if PDF_SUPPORT else 0,
                "success_rate": downloaded_count / NUM_PDFS if NUM_PDFS > 0 else 0,
                "errors": len(download_errors),
            },
            "storage": {
                "pdf_dir": str(pdfs_dir),
                "md_dir": str(mds_dir) if PDF_SUPPORT else None,
                "total_pdf_size_mb": sum(m["pdf_size"] for m in pdf_metadata) / (1024 * 1024),
            }
        }

        stats_file = data_dir / "january_2024_stats.json"
        stats_file.write_text(
            json.dumps(stats, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        print(f"📊 Дел спарсено: {len(all_cases)}")
        print(f"📊 PDF скачано: {downloaded_count}/{NUM_PDFS}")
        if PDF_SUPPORT:
            print(f"📊 MD конвертировано: {converted_count}/{downloaded_count}")
        print(f"📊 Время парсинга: {parsing_time:.1f} сек")
        print()

        print("💾 Файлы результатов:")
        print(f"   - {cases_file}")
        print(f"   - {pdf_metadata_file}")
        print(f"   - {stats_file}")
        print(f"   - {pdfs_dir}/ ({downloaded_count} PDF)")
        if PDF_SUPPORT:
            print(f"   - {mds_dir}/ ({converted_count} MD)")
        print()

        print("=" * 80)
        print("🎉 PIPELINE ЗАВЕРШЕН!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(parse_and_download())
