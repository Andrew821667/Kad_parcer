#!/usr/bin/env python3
"""
Test pagination on kad.arbitr.ru to understand how to navigate pages.
"""

import asyncio

from playwright.async_api import async_playwright


async def main():
    """Test pagination."""
    print("🔗 Подключаюсь к реальному Chrome через CDP...")

    async with async_playwright() as p:
        # Connect to existing Chrome
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")

        contexts = browser.contexts
        if contexts:
            context = contexts[0]
            pages = context.pages
            if pages:
                page = pages[0]
            else:
                page = await context.new_page()
        else:
            page = await browser.new_page()

        print("✅ Подключено к реальному Chrome!")
        print("\n" + "=" * 80)
        print("ТЕСТ ПАГИНАЦИИ")
        print("=" * 80)

        # Check current URL
        url = page.url
        print(f"\n1. Текущий URL: {url}")

        # Check table
        table = await page.query_selector("table#b-cases")
        if not table:
            print("\n❌ Таблица #b-cases не найдена. Сначала выполните поиск!")
            return

        rows = await table.query_selector_all("tr")
        print(f"2. Строк в таблице: {len(rows)}")

        # Get first row data (to compare after pagination)
        if len(rows) > 1:
            first_row = rows[1]
            cells = await first_row.query_selector_all("td")
            if cells and len(cells) > 0:
                first_case_text = await cells[0].inner_text()
                print(f"3. Первое дело на странице 1: {first_case_text[:50]}")

        # Find pagination elements
        print("\n4. Ищу элементы пагинации...")

        # Common pagination patterns
        pagination_selectors = [
            ".pagination",
            ".pager",
            ".pages",
            "ul.pagination",
            "div.pagination",
            "[class*='paginat']",
            "[id*='paginat']",
            "[class*='pager']",
            "[id*='pager']",
        ]

        pagination_found = False
        pagination_element = None

        for selector in pagination_selectors:
            element = await page.query_selector(selector)
            if element:
                html = await element.inner_html()
                if html:
                    print(f"   ✅ Найден элемент пагинации: {selector}")
                    print(f"   HTML: {html[:200]}...")
                    pagination_element = element
                    pagination_found = True
                    break

        if not pagination_found:
            print("   ❌ Стандартные элементы пагинации не найдены")
            print("   Ищу ссылки/кнопки со словами 'след', 'next', '2', '>'...")

            # Try to find next page link
            next_links = await page.query_selector_all("a, button")
            for link in next_links[:50]:  # Check first 50 links
                text = await link.inner_text()
                text = text.strip().lower()
                if any(
                    word in text
                    for word in ["след", "next", "далее", ">", "»", "вперед"]
                ):
                    href = await link.get_attribute("href")
                    onclick = await link.get_attribute("onclick")
                    print(
                        f"   Возможная кнопка 'Далее': text='{text}', href='{href}', onclick='{onclick}'"
                    )

        # Try to find page input field (like "Страница ___ из 5200")
        print("\n5. Ищу поле ввода номера страницы...")
        page_inputs = await page.query_selector_all("input[type='text'], input:not([type])")

        for inp in page_inputs:
            placeholder = await inp.get_attribute("placeholder")
            value = await inp.get_attribute("value")
            name = await inp.get_attribute("name")
            inp_id = await inp.get_attribute("id")

            # Look for page-related inputs
            if any(
                word in str(placeholder).lower() + str(name).lower() + str(inp_id).lower()
                for word in ["page", "страниц", "стр"]
            ):
                print(
                    f"   Найден input: id='{inp_id}', name='{name}', placeholder='{placeholder}', value='{value}'"
                )

        # Try to find "из X страниц" text
        print("\n6. Ищу текст 'из X страниц'...")
        page_text = await page.content()
        import re

        matches = re.findall(r"(из\s+\d+\s*страниц|страниц[аы]?\s*\d+|page\s+\d+\s+of\s+\d+)", page_text, re.IGNORECASE)
        if matches:
            print(f"   Найдено: {matches[:5]}")

        # Look for specific kad.arbitr.ru pagination
        print("\n7. Проверяю специфичные для КАД элементы...")

        # Check for input#documentsPageNumber
        page_number_input = await page.query_selector("input#documentsPageNumber")
        if page_number_input:
            value = await page_number_input.get_attribute("value")
            print(f"   ✅ Найден input#documentsPageNumber, value='{value}'")

        # Check for input#documentsPagesCount
        pages_count_input = await page.query_selector("input#documentsPagesCount")
        if pages_count_input:
            value = await pages_count_input.get_attribute("value")
            print(f"   ✅ Найден input#documentsPagesCount, value='{value}'")

        # Check for navigation buttons
        nav_buttons = ["#nextPage", "#previousPage", ".nextPage", ".previousPage"]
        for btn_selector in nav_buttons:
            btn = await page.query_selector(btn_selector)
            if btn:
                print(f"   ✅ Найдена кнопка навигации: {btn_selector}")

        print("\n" + "=" * 80)
        print("Анализ пагинации завершен!")
        print("=" * 80)

        input("\nНажмите Enter чтобы закрыть...")


if __name__ == "__main__":
    asyncio.run(main())
