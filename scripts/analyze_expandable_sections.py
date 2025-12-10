#!/usr/bin/env python3
"""
Анализ раскрывающихся блоков инстанций на странице дела.

Находит все раскрывающиеся секции, раскрывает их и анализирует содержимое.
"""

import asyncio
import json
from pathlib import Path

from src.scraper.playwright_scraper import PlaywrightScraper


async def analyze_expandable_sections():
    """Анализ раскрывающихся блоков на странице дела."""

    print("=" * 80)
    print("АНАЛИЗ РАСКРЫВАЮЩИХСЯ БЛОКОВ НА СТРАНИЦЕ ДЕЛА")
    print("=" * 80)
    print()

    # Загрузить одно дело
    cases_file = Path("data/january_2024_cases.json")
    if not cases_file.exists():
        print("❌ Файл не найден. Запустите сначала парсинг.")
        return

    with open(cases_file, encoding="utf-8") as f:
        all_cases = json.load(f)

    # Взять первое дело с несколькими актами
    case = all_cases[0]
    case_url = f"https://kad.arbitr.ru{case['url']}"

    print(f"📋 Дело: {case['case_number']}")
    print(f"🔗 URL: {case_url}")
    print()

    async with PlaywrightScraper(use_cdp=True, cdp_url="http://localhost:9222") as scraper:
        print("✅ Подключено к Chrome\n")

        # Открыть страницу дела
        await scraper.page.goto(case_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)
        print("✅ Страница дела загружена\n")

        # ================================================================
        # 1. ПОИСК РАСКРЫВАЮЩИХСЯ ЭЛЕМЕНТОВ
        # ================================================================

        print("=" * 80)
        print("1. ПОИСК РАСКРЫВАЮЩИХСЯ ЭЛЕМЕНТОВ")
        print("=" * 80)
        print()

        # Возможные селекторы для раскрывающихся блоков
        selectors = [
            "button.toggle",
            "button.expand",
            "a.toggle",
            "div.collapsible",
            ".accordion",
            "[data-toggle]",
            "button:has-text('Первая инстанция')",
            "button:has-text('Апелляция')",
            "button:has-text('Кассация')",
            "div:has-text('Первая инстанция') button",
            "div:has-text('Апелляция') button",
        ]

        found_expandable = []

        for selector in selectors:
            elements = await scraper.page.query_selector_all(selector)
            if elements:
                print(f"✓ Найдено: {selector} ({len(elements)} шт.)")
                for el in elements[:3]:
                    text = await el.inner_text()
                    tag = await el.evaluate("el => el.tagName")
                    class_name = await el.get_attribute("class")
                    found_expandable.append({
                        "selector": selector,
                        "tag": tag,
                        "text": text.strip()[:50],
                        "class": class_name,
                        "element": el,
                    })

        print(f"\n📊 Всего найдено потенциальных раскрывающихся элементов: {len(found_expandable)}\n")

        # ================================================================
        # 2. ПОПЫТКА РАСКРЫТЬ БЛОКИ
        # ================================================================

        print("=" * 80)
        print("2. РАСКРЫТИЕ БЛОКОВ")
        print("=" * 80)
        print()

        # Попробовать кликнуть на первые 3 элемента
        for i, item in enumerate(found_expandable[:3], 1):
            print(f"[{i}] Пробую раскрыть: {item['text'][:40]}")
            try:
                # Скролл к элементу
                await item['element'].scroll_into_view_if_needed()
                await asyncio.sleep(0.5)

                # Клик
                await item['element'].click()
                await asyncio.sleep(2)

                print(f"    ✅ Кликнул")

                # Проверить, появились ли новые PDF ссылки
                pdf_links = await scraper.page.query_selector_all('a[href$=".pdf"]')
                print(f"    PDF ссылок на странице: {len(pdf_links)}")

            except Exception as e:
                print(f"    ⚠️  Ошибка: {e}")

        # ================================================================
        # 3. ПОИСК ТАБЛИЦ С ИСТОРИЕЙ
        # ================================================================

        print("\n" + "=" * 80)
        print("3. ПОИСК ТАБЛИЦ С ИСТОРИЕЙ ДЕЛА")
        print("=" * 80)
        print()

        tables = await scraper.page.query_selector_all("table")
        print(f"📊 Всего таблиц: {len(tables)}\n")

        for i, table in enumerate(tables, 1):
            table_id = await table.get_attribute("id")
            table_class = await table.get_attribute("class")

            print(f"Таблица {i}:")
            print(f"   ID: {table_id or 'N/A'}")
            print(f"   Class: {table_class or 'N/A'}")

            # Первая строка (заголовки)
            rows = await table.query_selector_all("tr")
            if rows:
                first_row = rows[0]
                headers = await first_row.query_selector_all("th, td")
                if headers:
                    header_texts = []
                    for h in headers[:5]:
                        text = await h.inner_text()
                        header_texts.append(text.strip()[:20])
                    print(f"   Заголовки: {' | '.join(header_texts)}")

            print(f"   Строк: {len(rows)}\n")

        # ================================================================
        # 4. ВСЕ PDF НА СТРАНИЦЕ
        # ================================================================

        print("=" * 80)
        print("4. ВСЕ PDF ССЫЛКИ ПОСЛЕ РАСКРЫТИЯ")
        print("=" * 80)
        print()

        all_pdfs = await scraper.page.query_selector_all('a[href$=".pdf"]')
        print(f"📄 Всего PDF ссылок: {len(all_pdfs)}\n")

        for i, link in enumerate(all_pdfs[:15], 1):
            text = await link.inner_text()
            href = await link.get_attribute("href")
            print(f"{i}. {text.strip()[:60]}")

        # ================================================================
        # 5. СОХРАНИТЬ HTML
        # ================================================================

        print("\n" + "=" * 80)
        print("5. СОХРАНЕНИЕ HTML")
        print("=" * 80)
        print()

        html = await scraper.page.content()
        html_file = Path("data/case_page_expanded.html")
        html_file.write_text(html, encoding="utf-8")
        print(f"💾 Сохранено: {html_file}")
        print(f"   Размер: {len(html)} байт")

        print("\n" + "=" * 80)
        print("✅ АНАЛИЗ ЗАВЕРШЕН")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(analyze_expandable_sections())
