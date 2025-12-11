#!/usr/bin/env python3
"""
Анализ вкладки "Электронное дело" на странице дела КАД Арбитр.
Цель: найти все документы и понять структуру пагинации.
"""

import asyncio
import json
from pathlib import Path

from src.scraper.playwright_scraper import PlaywrightScraper


async def analyze_electronic_case_tab():
    """Анализ вкладки Электронное дело."""

    print("=" * 80)
    print("АНАЛИЗ ВКЛАДКИ 'ЭЛЕКТРОННОЕ ДЕЛО'")
    print("=" * 80)
    print()

    # Загрузить тестовое дело
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

    async with PlaywrightScraper(use_cdp=True, cdp_url="http://localhost:9222") as scraper:
        await scraper.page.goto(case_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        print("✅ Страница дела загружена\n")

        # ================================================================
        # 1. НАЙТИ И ИЗУЧИТЬ ВКЛАДКИ
        # ================================================================

        print("=" * 80)
        print("1. ПОИСК ВКЛАДОК")
        print("=" * 80)
        print()

        # ПРАВИЛЬНЫЙ СЕЛЕКТОР: .js-case-chrono-button--ed
        # Структура:
        # <div class="b-case-chrono-button js-case-chrono-button js-case-chrono-button--ed">
        #     <div class="b-case-chrono-button-text">Электронное дело</div>
        # </div>

        electronic_tab = await scraper.page.query_selector(".js-case-chrono-button--ed")

        if electronic_tab:
            tag = await electronic_tab.evaluate("el => el.tagName")
            classes = await electronic_tab.get_attribute("class") or ""
            text = await electronic_tab.inner_text()
            print(f"✅ Найдена вкладка 'Электронное дело'")
            print(f"   Tag: <{tag}>")
            print(f"   Class: {classes}")
            print(f"   Text: {text.strip()}")
            print()
        else:
            print("❌ Вкладка 'Электронное дело' не найдена!")
            print("   Давайте посмотрим все вкладки на странице:\n")

            # Найти все возможные вкладки
            all_tabs = await scraper.page.query_selector_all("a, button, [role='tab'], .tab, li")
            print(f"Всего элементов похожих на вкладки: {len(all_tabs)}\n")

            for i, tab in enumerate(all_tabs[:20], 1):
                try:
                    text = await tab.inner_text()
                    if text.strip() and len(text) < 100:
                        tag = await tab.evaluate("el => el.tagName")
                        classes = await tab.get_attribute("class") or ""
                        print(f"{i}. <{tag}> class='{classes[:40]}': {text.strip()[:50]}")
                except:
                    pass

            return

        # ================================================================
        # 2. КЛИКНУТЬ НА ВКЛАДКУ "ЭЛЕКТРОННОЕ ДЕЛО"
        # ================================================================

        print("=" * 80)
        print("2. ПЕРЕХОД НА ВКЛАДКУ 'ЭЛЕКТРОННОЕ ДЕЛО'")
        print("=" * 80)
        print()

        try:
            await electronic_tab.click()
            print("✅ Кликнули на вкладку")
            await asyncio.sleep(3)  # Ждем загрузки содержимого вкладки
            print("✅ Вкладка загружена\n")
        except Exception as e:
            print(f"❌ Ошибка при клике: {e}\n")
            return

        # ================================================================
        # 3. НАЙТИ ВСЕ PDF ДОКУМЕНТЫ НА ВКЛАДКЕ
        # ================================================================

        print("=" * 80)
        print("3. ПОИСК PDF ДОКУМЕНТОВ")
        print("=" * 80)
        print()

        # Найти все PDF ссылки
        pdf_links = await scraper.page.query_selector_all('a[href$=".pdf"]')
        print(f"📄 Найдено PDF ссылок: {len(pdf_links)}\n")

        if pdf_links:
            print("Первые 10 документов:")
            for i, link in enumerate(pdf_links[:10], 1):
                try:
                    text = await link.inner_text()
                    href = await link.get_attribute("href")
                    print(f"  {i}. {text.strip()[:60]}")
                    print(f"     URL: {href[:80]}")
                except:
                    pass
            print()

        # ================================================================
        # 4. ПОИСК ПАГИНАЦИИ
        # ================================================================

        print("=" * 80)
        print("4. ПОИСК ПАГИНАЦИИ")
        print("=" * 80)
        print()

        # Искать элементы пагинации
        pagination_selectors = [
            ".pagination",
            "[class*='pag']",
            "a:has-text('Следующая')",
            "button:has-text('Следующая')",
            "a:has-text('>')",
            "[class*='next']",
            "[class*='page']",
        ]

        pagination_found = False
        for selector in pagination_selectors:
            try:
                elements = await scraper.page.query_selector_all(selector)
                if elements:
                    print(f"✓ Найдено элементов пагинации ({selector}): {len(elements)}")

                    for i, elem in enumerate(elements[:5], 1):
                        try:
                            tag = await elem.evaluate("el => el.tagName")
                            text = await elem.inner_text()
                            classes = await elem.get_attribute("class") or ""
                            href = await elem.get_attribute("href") or ""

                            print(f"   {i}. <{tag}> class='{classes[:40]}'")
                            print(f"      Text: {text.strip()[:40]}")
                            if href:
                                print(f"      Href: {href[:60]}")
                        except:
                            pass
                    print()
                    pagination_found = True
            except:
                pass

        if not pagination_found:
            print("❌ Элементы пагинации не найдены")
            print("   Возможно все документы на одной странице\n")

        # ================================================================
        # 5. СОХРАНИТЬ HTML ВКЛАДКИ ДЛЯ АНАЛИЗА
        # ================================================================

        print("=" * 80)
        print("5. СОХРАНЕНИЕ HTML")
        print("=" * 80)
        print()

        # Найти контейнер с содержимым вкладки
        # Обычно это div с id или class содержащим "electronic", "documents", "files" и т.д.
        tab_content = await scraper.page.query_selector("#electronic_case, .electronic-case, #documents, .documents, .tab-content, [role='tabpanel']")

        if tab_content:
            html = await tab_content.inner_html()
        else:
            # Если не нашли контейнер, берем весь body
            html = await scraper.page.content()

        html_file = Path("data/electronic_case_tab.html")
        html_file.write_text(html, encoding="utf-8")
        print(f"💾 HTML вкладки сохранен: {html_file}")
        print(f"   Размер: {len(html)} байт\n")

        print("=" * 80)
        print("✅ АНАЛИЗ ЗАВЕРШЕН")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(analyze_electronic_case_tab())
