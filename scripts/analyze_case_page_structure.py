#!/usr/bin/env python3
"""
Анализ структуры страницы дела КАД Арбитр.

Задача: найти вкладки инстанций и понять, как переключаться между ними.
"""

import asyncio
import json
from pathlib import Path

from src.scraper.playwright_scraper import PlaywrightScraper


async def analyze_case_page():
    """Анализ структуры страницы одного дела."""

    print("=" * 80)
    print("АНАЛИЗ СТРУКТУРЫ СТРАНИЦЫ ДЕЛА")
    print("=" * 80)
    print()

    # Загрузить спарсенные дела
    cases_file = Path("data/january_2024_cases.json")
    if not cases_file.exists():
        print("❌ Файл data/january_2024_cases.json не найден")
        print("   Запустите сначала парсинг страниц результатов")
        return

    with open(cases_file, encoding="utf-8") as f:
        all_cases = json.load(f)

    if not all_cases:
        print("❌ Нет данных о делах")
        return

    # Взять первое дело
    case = all_cases[0]
    print(f"📋 Анализируем дело: {case['case_number']}")
    print(f"   Суд: {case.get('court', 'N/A')}")
    print()

    # Очистить и нормализовать URL
    case_url = case['url']
    case_url = case_url.replace('https//kad.arbitr.ru', '')
    case_url = case_url.replace('http//kad.arbitr.ru', '')
    case_url = case_url.replace('//kad.arbitr.ru', '')
    case_url = case_url.replace('https://kad.arbitr.ru', '')
    case_url = case_url.replace('http://kad.arbitr.ru', '')

    if not case_url.startswith('/'):
        case_url = '/' + case_url

    case_url = f"https://kad.arbitr.ru{case_url}"

    print(f"🔗 URL: {case_url}")
    print()

    async with PlaywrightScraper(use_cdp=True, cdp_url="http://localhost:9222") as scraper:
        print("✅ Подключено к Chrome\n")

        # Открыть страницу дела
        print("⏳ Открываем страницу дела...")
        await scraper.page.goto(case_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)
        print("✅ Страница загружена\n")

        # ============================================================
        # 1. ПОИСК ВКЛАДОК / ТАБОВ
        # ============================================================

        print("=" * 80)
        print("1. ПОИСК ВКЛАДОК ИНСТАНЦИЙ")
        print("=" * 80)
        print()

        # Искать элементы с текстом про инстанции
        keywords = [
            "Первая инстанция",
            "Апелляция",
            "Кассация",
            "первая",
            "апелляц",
            "кассац",
        ]

        found_tabs = []

        for keyword in keywords:
            # Искать кнопки
            buttons = await scraper.page.query_selector_all(f"button:has-text('{keyword}')")
            for btn in buttons[:3]:  # Первые 3
                text = await btn.inner_text()
                visible = await btn.is_visible()
                found_tabs.append({
                    "type": "button",
                    "text": text.strip(),
                    "visible": visible,
                })

            # Искать ссылки
            links = await scraper.page.query_selector_all(f"a:has-text('{keyword}')")
            for link in links[:3]:
                text = await link.inner_text()
                visible = await link.is_visible()
                href = await link.get_attribute("href")
                found_tabs.append({
                    "type": "link",
                    "text": text.strip(),
                    "visible": visible,
                    "href": href,
                })

            # Искать div/span с классами tab, instance
            divs = await scraper.page.query_selector_all(
                f"div:has-text('{keyword}'), span:has-text('{keyword}')"
            )
            for div in divs[:3]:
                text = await div.inner_text()
                visible = await div.is_visible()
                class_name = await div.get_attribute("class")
                found_tabs.append({
                    "type": "div/span",
                    "text": text.strip()[:50],
                    "visible": visible,
                    "class": class_name,
                })

        if found_tabs:
            print(f"✅ Найдено элементов с упоминанием инстанций: {len(found_tabs)}\n")
            for i, tab in enumerate(found_tabs[:10], 1):  # Первые 10
                print(f"{i}. {tab}")
        else:
            print("⚠️  Не найдено явных вкладок с текстом про инстанции\n")

        # ============================================================
        # 2. ПОИСК ТАБЛИЦ С ДОКУМЕНТАМИ
        # ============================================================

        print("\n")
        print("=" * 80)
        print("2. ПОИСК ТАБЛИЦ С ДОКУМЕНТАМИ")
        print("=" * 80)
        print()

        # Искать таблицы
        all_tables = await scraper.page.query_selector_all("table")
        print(f"📊 Всего таблиц на странице: {len(all_tables)}\n")

        for i, table in enumerate(all_tables, 1):
            # Получить ID и класс
            table_id = await table.get_attribute("id")
            table_class = await table.get_attribute("class")

            print(f"Таблица {i}:")
            print(f"   ID: {table_id or 'N/A'}")
            print(f"   Class: {table_class or 'N/A'}")

            # Посчитать строки
            rows = await table.query_selector_all("tr")
            print(f"   Строк: {len(rows)}")

            # Найти PDF ссылки в таблице
            pdf_links = await table.query_selector_all('a[href$=".pdf"]')
            print(f"   PDF ссылок: {len(pdf_links)}")

            if pdf_links:
                print(f"   ✅ Это таблица с документами!")
                # Показать первые 3 ссылки
                for j, link in enumerate(pdf_links[:3], 1):
                    text = await link.inner_text()
                    href = await link.get_attribute("href")
                    print(f"      {j}. {text.strip()[:60]}")
                    print(f"         URL: {href[:80]}")

            print()

        # ============================================================
        # 3. ПОИСК ВСЕХ PDF ССЫЛОК
        # ============================================================

        print("=" * 80)
        print("3. ВСЕ PDF ССЫЛКИ НА СТРАНИЦЕ")
        print("=" * 80)
        print()

        all_pdf_links = await scraper.page.query_selector_all('a[href$=".pdf"]')
        print(f"📄 Всего PDF ссылок: {len(all_pdf_links)}\n")

        if all_pdf_links:
            print("Первые 10 документов:")
            for i, link in enumerate(all_pdf_links[:10], 1):
                text = await link.inner_text()
                href = await link.get_attribute("href")
                visible = await link.is_visible()
                print(f"{i}. [{('✓' if visible else '✗')}] {text.strip()[:60]}")
                print(f"   {href}")
                print()

        # ============================================================
        # 4. HTML СТРУКТУРА
        # ============================================================

        print("=" * 80)
        print("4. HTML СТРУКТУРА (для ручного анализа)")
        print("=" * 80)
        print()

        # Сохранить HTML страницы
        html_content = await scraper.page.content()
        html_file = Path("data/case_page_structure.html")
        html_file.write_text(html_content, encoding="utf-8")

        print(f"💾 HTML сохранен: {html_file}")
        print(f"   Размер: {len(html_content)} байт")
        print()

        print("=" * 80)
        print("✅ АНАЛИЗ ЗАВЕРШЕН")
        print("=" * 80)
        print()
        print("📋 Следующие шаги:")
        print("   1. Изучите вывод выше")
        print("   2. Откройте data/case_page_structure.html в браузере")
        print("   3. Найдите селекторы для вкладок инстанций")
        print("   4. Определите, как переключаться между вкладками")


if __name__ == "__main__":
    asyncio.run(analyze_case_page())
