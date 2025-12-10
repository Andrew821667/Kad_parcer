#!/usr/bin/env python3
"""
Debug table row HTML structure to understand how to parse it correctly.
"""

import asyncio

from playwright.async_api import async_playwright


async def main():
    """Show HTML structure of first table row."""
    print("🔍 Анализ структуры строки таблицы\n")

    async with async_playwright() as p:
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

        print("✅ Подключено к Chrome\n")

        # Do search
        print("🔍 Выполняю поиск за январь 2024...\n")

        await page.goto("https://kad.arbitr.ru", wait_until="networkidle")
        await asyncio.sleep(2)

        # Close popup
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(1)
        except Exception:
            pass

        # Fill dates
        date_inputs = await page.query_selector_all('input[placeholder="дд.мм.гггг"]')
        if len(date_inputs) >= 2:
            await date_inputs[0].click()
            await asyncio.sleep(0.2)
            await date_inputs[0].fill("01.01.2024")
            await asyncio.sleep(0.5)

            await date_inputs[1].click()
            await asyncio.sleep(0.2)
            await date_inputs[1].fill("31.01.2024")
            await asyncio.sleep(0.5)

        await page.click("body")
        await asyncio.sleep(0.5)

        # Submit
        await page.click("#b-form-submit")
        await asyncio.sleep(5)

        print("✅ Поиск выполнен\n")

        # Get table
        table = await page.query_selector("table#b-cases")
        if not table:
            print("❌ Таблица не найдена!")
            return

        # Get first data row (skip header)
        rows = await table.query_selector_all("tr")
        if len(rows) < 2:
            print("❌ Нет строк данных в таблице")
            return

        first_data_row = rows[1]

        # Get row HTML
        row_html = await first_data_row.inner_html()

        print("=" * 80)
        print("HTML первой строки таблицы:")
        print("=" * 80)
        print(row_html)
        print("=" * 80)

        # Analyze each cell
        cells = await first_data_row.query_selector_all("td")

        print(f"\n📊 Найдено колонок: {len(cells)}\n")

        for i, cell in enumerate(cells, 1):
            class_name = await cell.get_attribute("class")
            inner_text = await cell.inner_text()
            inner_html = await cell.inner_html()

            print(f"Колонка {i} (class='{class_name}'):")
            print(f"  Текст:\n{inner_text}")
            print(f"  HTML (первые 300 символов):\n{inner_html[:300]}")
            print()

        input("\nНажмите Enter чтобы закрыть...")


if __name__ == "__main__":
    asyncio.run(main())
