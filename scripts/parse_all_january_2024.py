#!/usr/bin/env python3
"""
Полномасштабный парсинг января 2024: все 40 страниц + скачивание 100 PDF.

Результаты сохраняются в:
- data/january_2024_cases.json - все спарсенные дела
- data/january_2024_pdfs/ - 100 PDF для анализа
- data/january_2024_stats.json - статистика парсинга
"""

import asyncio
import json
import random
from pathlib import Path
from datetime import datetime
from typing import Any

import httpx
from structlog import get_logger

from src.scraper.playwright_scraper import PlaywrightScraper

logger = get_logger(__name__)


async def parse_all_january_2024():
    """Спарсить все 40 страниц января 2024 и скачать 100 PDF."""

    print("=" * 80)
    print("🚀 ПОЛНОМАСШТАБНЫЙ ПАРСИНГ ЯНВАРЯ 2024")
    print("=" * 80)
    print()

    # Создать директории для результатов
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    pdfs_dir = data_dir / "january_2024_pdfs"
    pdfs_dir.mkdir(exist_ok=True)

    # Подключение к Chrome через CDP
    async with PlaywrightScraper(
        use_cdp=True,
        cdp_url="http://localhost:9222",
    ) as scraper:
        print("✅ Подключено к Chrome через CDP\n")

        # ============================================================
        # ШАГ 1: Парсинг всех 40 страниц
        # ============================================================

        print("=" * 80)
        print("ШАГ 1: Парсинг всех 40 страниц (январь 2024)")
        print("=" * 80)
        print()

        # Открыть КАД Арбитр
        await scraper.page.goto("https://kad.arbitr.ru", wait_until="networkidle")
        await asyncio.sleep(2)

        # Закрыть popup если есть
        try:
            await scraper.page.keyboard.press("Escape")
            await asyncio.sleep(1)
        except Exception:
            pass

        # Заполнить форму поиска (январь 2024)
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
            print(f"📖 Парсинг страницы {page_num}/{total_pages}...")

            # Получить HTML таблицы
            table = await scraper.page.query_selector("table.b-cases")
            if not table:
                print(f"   ⚠️  Таблица не найдена на странице {page_num}")
                continue

            table_html = await table.inner_html()

            # Парсинг
            try:
                cases = scraper._parse_table_html(table_html)
                all_cases.extend(cases)
                print(f"   ✓ Найдено дел: {len(cases)} (всего: {len(all_cases)})")

                # Сохранять промежуточные результаты каждые 10 страниц
                if page_num % 10 == 0:
                    temp_file = data_dir / f"january_2024_cases_page_{page_num}.json"
                    temp_file.write_text(
                        json.dumps(all_cases, ensure_ascii=False, indent=2),
                        encoding="utf-8"
                    )
                    print(f"   💾 Промежуточное сохранение: {temp_file}")

            except Exception as e:
                print(f"   ❌ Ошибка парсинга: {e}")
                continue

            # Переход на следующую страницу
            if page_num < total_pages:
                try:
                    link = await scraper.page.query_selector(f'a[href="#page{page_num + 1}"]')
                    if link:
                        await link.click()
                        await asyncio.sleep(5)  # Ждем перезагрузку таблицы
                    else:
                        print(f"   ⚠️  Ссылка на страницу {page_num + 1} не найдена")
                        break
                except Exception as e:
                    print(f"   ❌ Ошибка перехода на страницу {page_num + 1}: {e}")
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
        # ШАГ 2: Скачивание 100 PDF для анализа
        # ============================================================

        print("=" * 80)
        print("ШАГ 2: Скачивание 100 PDF для анализа")
        print("=" * 80)
        print()

        # Выбрать 100 случайных дел
        NUM_PDFS = min(100, len(all_cases))
        selected_cases = random.sample(all_cases, NUM_PDFS)

        print(f"📋 Выбрано дел для скачивания PDF: {NUM_PDFS}")
        print()

        downloaded_count = 0
        download_errors = []
        pdf_metadata = []

        for i, case in enumerate(selected_cases, 1):
            print(f"📄 Дело {i}/{NUM_PDFS}: {case['case_number']}")

            try:
                # Открыть страницу дела
                case_url = f"https://kad.arbitr.ru{case['url']}"
                await scraper.page.goto(case_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)

                print(f"   ✓ Страница дела открыта")

                # Поиск прямых PDF ссылок
                doc_links = await scraper.page.query_selector_all('a[href$=".pdf"]')

                if not doc_links:
                    print(f"   ⚠️  PDF ссылки не найдены")
                    download_errors.append({
                        "case_number": case["case_number"],
                        "error": "no_pdf_links"
                    })
                    continue

                print(f"   Найдено PDF ссылок: {len(doc_links)}")

                # Получить первую ссылку
                first_link = doc_links[0]
                link_text = await first_link.inner_text()
                pdf_url = await first_link.get_attribute("href")

                print(f"   Документ: {link_text[:50]}")

                # Извлечь имя файла
                pdf_filename = pdf_url.split("/")[-1] if pdf_url else "document.pdf"

                # Скачать через HTTP с cookies
                try:
                    # Получить cookies из браузера
                    cookies = await scraper.page.context.cookies()
                    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

                    # Скачать PDF
                    async with httpx.AsyncClient(
                        cookies=cookie_dict,
                        timeout=30.0,
                        follow_redirects=True
                    ) as client:
                        response = await client.get(pdf_url)

                        if response.status_code == 200:
                            # Проверить что это PDF
                            content_type = response.headers.get('content-type', '')

                            if 'pdf' in content_type.lower() or pdf_url.endswith('.pdf'):
                                # Сохранить файл
                                filename = f"{case['case_number'].replace('/', '_')}_{pdf_filename}"
                                filepath = pdfs_dir / filename

                                filepath.write_bytes(response.content)

                                print(f"   ✅ Скачан: {filename} ({len(response.content)} bytes)")
                                downloaded_count += 1

                                # Сохранить метаданные
                                pdf_metadata.append({
                                    "case_number": case["case_number"],
                                    "case_date": case["case_date"],
                                    "judge": case.get("judge"),
                                    "court": case.get("court"),
                                    "pdf_filename": filename,
                                    "pdf_size": len(response.content),
                                    "pdf_url": pdf_url,
                                    "document_title": link_text[:100],
                                })
                            else:
                                print(f"   ⚠️  Не PDF файл (Content-Type: {content_type})")
                                download_errors.append({
                                    "case_number": case["case_number"],
                                    "error": f"wrong_content_type: {content_type}"
                                })
                        else:
                            print(f"   ❌ HTTP ошибка: {response.status_code}")
                            download_errors.append({
                                "case_number": case["case_number"],
                                "error": f"http_{response.status_code}"
                            })

                except Exception as download_error:
                    print(f"   ❌ Ошибка скачивания: {download_error}")
                    download_errors.append({
                        "case_number": case["case_number"],
                        "error": str(download_error)
                    })
                    continue

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
        print()

        # Сохранить метаданные PDF
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

        # Анализ категорий
        case_types = {}
        courts = {}
        judges = {}

        for case in all_cases:
            # Подсчет типов дел
            case_type = case.get("case_type", "unknown")
            case_types[case_type] = case_types.get(case_type, 0) + 1

            # Подсчет судов
            court = case.get("court", "unknown")
            courts[court] = courts.get(court, 0) + 1

            # Подсчет судей
            judge = case.get("judge", "unknown")
            judges[judge] = judges.get(judge, 0) + 1

        stats = {
            "parsing": {
                "total_cases": len(all_cases),
                "pages_parsed": total_pages,
                "parsing_time_sec": parsing_time,
                "avg_time_per_page": parsing_time / total_pages if total_pages > 0 else 0,
            },
            "downloading": {
                "pdfs_requested": NUM_PDFS,
                "pdfs_downloaded": downloaded_count,
                "success_rate": downloaded_count / NUM_PDFS if NUM_PDFS > 0 else 0,
                "errors": len(download_errors),
            },
            "categories": {
                "case_types": case_types,
                "courts": dict(sorted(courts.items(), key=lambda x: x[1], reverse=True)[:20]),
                "judges": dict(sorted(judges.items(), key=lambda x: x[1], reverse=True)[:20]),
            },
            "errors": download_errors,
        }

        # Сохранить статистику
        stats_file = data_dir / "january_2024_stats.json"
        stats_file.write_text(
            json.dumps(stats, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        print(f"📊 Всего дел спарсено: {len(all_cases)}")
        print(f"📊 PDF скачано: {downloaded_count}/{NUM_PDFS}")
        print(f"📊 Страниц обработано: {total_pages}")
        print(f"📊 Время парсинга: {parsing_time:.1f} сек ({parsing_time/60:.1f} мин)")
        print()

        print("📈 Топ-5 типов дел:")
        for case_type, count in sorted(case_types.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"   {case_type}: {count}")
        print()

        print("📈 Топ-5 судов:")
        for court, count in sorted(courts.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"   {court}: {count}")
        print()

        print("💾 Файлы результатов:")
        print(f"   - {cases_file}")
        print(f"   - {pdf_metadata_file}")
        print(f"   - {stats_file}")
        print(f"   - {pdfs_dir}/ ({downloaded_count} файлов)")
        print()

        print("=" * 80)
        print("🎉 ПАРСИНГ ЗАВЕРШЕН!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(parse_all_january_2024())
