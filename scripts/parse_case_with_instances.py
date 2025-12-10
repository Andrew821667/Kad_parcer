#!/usr/bin/env python3
"""
Полноценный парсинг страницы дела со всеми инстанциями.

Функционал:
1. Находит блок с хронологией (#chrono_list_content)
2. Извлекает все инстанции (первая, апелляция, кассация)
3. Раскрывает каждую инстанцию
4. Скачивает ВСЕ PDF документы из каждой инстанции
5. Парсит историю дела (хронологию)
6. Сохраняет структурированные метаданные
"""

import asyncio
import json
from pathlib import Path
from typing import Any, List, Dict

import httpx
from structlog import get_logger

from src.scraper.playwright_scraper import PlaywrightScraper

logger = get_logger(__name__)


async def parse_case_with_instances():
    """Парсинг дела со всеми инстанциями и документами."""

    print("=" * 80)
    print("ПОЛНОЦЕННЫЙ ПАРСИНГ ДЕЛА СО ВСЕМИ ИНСТАНЦИЯМИ")
    print("=" * 80)
    print()

    # Загрузить одно дело для теста
    cases_file = Path("data/january_2024_cases.json")
    with open(cases_file, encoding="utf-8") as f:
        all_cases = json.load(f)

    case = all_cases[0]
    case_url = case['url']

    # Нормализация URL
    case_url = case_url.replace('https//kad.arbitr.ru', '').replace('http//kad.arbitr.ru', '').replace('//kad.arbitr.ru', '').replace('https://kad.arbitr.ru', '').replace('http://kad.arbitr.ru', '').replace('https:/', '').replace('http:/', '')
    if not case_url.startswith('/'):
        case_url = '/' + case_url
    case_url = f"https://kad.arbitr.ru{case_url}"

    print(f"📋 Дело: {case['case_number']}")
    print(f"🔗 URL: {case_url}\n")

    # Создать папки для скачивания
    downloads_dir = Path("downloads") / case['case_number'].replace('/', '_')
    downloads_dir.mkdir(parents=True, exist_ok=True)

    async with PlaywrightScraper(use_cdp=True, cdp_url="http://localhost:9222") as scraper:
        await scraper.page.goto(case_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        print("✅ Страница дела загружена\n")

        # ================================================================
        # 1. НАЙТИ БЛОК С ХРОНОЛОГИЕЙ
        # ================================================================

        print("=" * 80)
        print("ШАГ 1: Поиск блока с хронологией и инстанциями")
        print("=" * 80)
        print()

        chrono_block = await scraper.page.query_selector("#chrono_list_content")
        if not chrono_block:
            print("❌ Блок #chrono_list_content не найден")
            return

        print("✅ Блок с хронологией найден\n")

        # ================================================================
        # 2. НАЙТИ ВСЕ ИНСТАНЦИИ
        # ================================================================

        print("=" * 80)
        print("ШАГ 2: Извлечение всех инстанций")
        print("=" * 80)
        print()

        # Поиск заголовков инстанций
        instance_headers = await chrono_block.query_selector_all("h2, h3, .instance-header, [class*='instance']")

        # Также искать по тексту
        all_divs = await chrono_block.query_selector_all("div")
        instance_blocks = []

        for div in all_divs[:50]:  # Первые 50 div'ов
            try:
                text = await div.inner_text()
                text_lower = text.lower()

                # Проверить, содержит ли текст название инстанции
                if any(keyword in text_lower for keyword in ['первая инстанция', 'апелляц', 'кассац', 'instance']):
                    classes = await div.get_attribute("class") or ""

                    # Найти все PDF внутри этого блока
                    pdfs_in_block = await div.query_selector_all('a[href$=".pdf"]')

                    if pdfs_in_block or len(text.strip()) < 200:  # Только если есть PDF или короткий текст (заголовок)
                        instance_blocks.append({
                            "element": div,
                            "text": text.strip()[:100],
                            "class": classes,
                            "pdf_count": len(pdfs_in_block),
                        })
            except:
                pass

        print(f"Найдено потенциальных блоков инстанций: {len(instance_blocks)}\n")

        for i, block in enumerate(instance_blocks[:10], 1):
            print(f"{i}. {block['text'][:60]}")
            print(f"   Class: {block['class'][:50]}")
            print(f"   PDF внутри: {block['pdf_count']}")
            print()

        # ================================================================
        # 3. РАСКРЫТЬ ВСЕ БЛОКИ (если они свернуты)
        # ================================================================

        print("=" * 80)
        print("ШАГ 3: Раскрытие всех блоков")
        print("=" * 80)
        print()

        # Найти все кликабельные заголовки/кнопки раскрытия
        expandable = await scraper.page.query_selector_all(
            "button.expand, button.toggle, a.toggle, [data-toggle], .collapsible-header, h2[onclick], h3[onclick]"
        )

        print(f"Найдено раскрывающихся элементов: {len(expandable)}")

        for i, el in enumerate(expandable, 1):
            try:
                text = await el.inner_text()
                print(f"  [{i}] Раскрываю: {text.strip()[:40]}")

                await el.scroll_into_view_if_needed()
                await asyncio.sleep(0.3)
                await el.click()
                await asyncio.sleep(1)

                print(f"      ✅ Раскрыто")
            except Exception as e:
                print(f"      ⚠️  Ошибка: {str(e)[:50]}")

        print()

        # ================================================================
        # 4. СКАЧАТЬ ВСЕ PDF ИЗ ВСЕХ ИНСТАНЦИЙ
        # ================================================================

        print("=" * 80)
        print("ШАГ 4: Скачивание всех PDF документов")
        print("=" * 80)
        print()

        # После раскрытия - найти ВСЕ PDF на странице
        all_pdf_links = await scraper.page.query_selector_all('a[href$=".pdf"]')
        print(f"📄 Всего PDF ссылок: {len(all_pdf_links)}\n")

        # Получить cookies для скачивания
        cookies = await scraper.page.context.cookies()
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

        downloaded_docs = []

        for i, link in enumerate(all_pdf_links, 1):
            try:
                link_text = await link.inner_text()
                pdf_url = await link.get_attribute("href")

                print(f"[{i}/{len(all_pdf_links)}] {link_text.strip()[:60]}")

                # Скачать PDF
                async with httpx.AsyncClient(
                    cookies=cookie_dict,
                    timeout=30.0,
                    follow_redirects=True
                ) as client:
                    response = await client.get(pdf_url)

                    if response.status_code == 200:
                        content_type = response.headers.get('content-type', '')

                        if 'pdf' in content_type.lower() or pdf_url.endswith('.pdf'):
                            # Имя файла
                            pdf_filename = pdf_url.split("/")[-1] if pdf_url else f"document_{i}.pdf"
                            filename = f"{i:03d}_{pdf_filename}"
                            filepath = downloads_dir / filename

                            filepath.write_bytes(response.content)

                            print(f"   ✅ {len(response.content)//1024} KB → {filename}")

                            downloaded_docs.append({
                                "index": i,
                                "title": link_text.strip(),
                                "filename": filename,
                                "url": pdf_url,
                                "size_bytes": len(response.content),
                            })
                        else:
                            print(f"   ⚠️  Не PDF (Content-Type: {content_type})")
                    else:
                        print(f"   ❌ HTTP {response.status_code}")

            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
                continue

        print()

        # ================================================================
        # 5. ПАРСИНГ ИСТОРИИ ДЕЛА
        # ================================================================

        print("=" * 80)
        print("ШАГ 5: Парсинг истории дела (хронология)")
        print("=" * 80)
        print()

        # Найти таблицы с хронологией
        chrono_tables = await chrono_block.query_selector_all("table")
        print(f"Таблиц в блоке хронологии: {len(chrono_tables)}\n")

        case_history = []

        for table_idx, table in enumerate(chrono_tables, 1):
            rows = await table.query_selector_all("tr")
            print(f"Таблица {table_idx}: {len(rows)} строк")

            for row in rows[:5]:  # Первые 5 строк для примера
                cells = await row.query_selector_all("td, th")
                row_data = []

                for cell in cells:
                    text = await cell.inner_text()
                    row_data.append(text.strip())

                if row_data:
                    print(f"   {' | '.join(row_data[:5])}")
                    case_history.append(row_data)

            print()

        # ================================================================
        # 6. СОХРАНИТЬ МЕТАДАННЫЕ
        # ================================================================

        print("=" * 80)
        print("ШАГ 6: Сохранение метаданных")
        print("=" * 80)
        print()

        metadata = {
            "case_number": case['case_number'],
            "case_url": case_url,
            "total_documents": len(downloaded_docs),
            "documents": downloaded_docs,
            "case_history": case_history[:20],  # Первые 20 записей
        }

        metadata_file = downloads_dir / "metadata.json"
        metadata_file.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        print(f"💾 Метаданные сохранены: {metadata_file}")
        print(f"💾 Документы сохранены: {downloads_dir}")
        print()

        # ================================================================
        # ИТОГИ
        # ================================================================

        print("=" * 80)
        print("ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 80)
        print()

        print(f"✅ Дело: {case['case_number']}")
        print(f"✅ Документов скачано: {len(downloaded_docs)}")
        print(f"✅ Записей истории: {len(case_history)}")
        print(f"✅ Папка: {downloads_dir}")
        print()

        print("=" * 80)
        print("🎉 ПАРСИНГ ЗАВЕРШЕН!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(parse_case_with_instances())
