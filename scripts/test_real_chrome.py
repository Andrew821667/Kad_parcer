#!/usr/bin/env python3
"""
Test using REAL Chrome browser via CDP (Chrome DevTools Protocol).
This bypasses ALL bot detection because we use a real browser.

BEFORE running this script:
1. Close all Chrome windows
2. Run Chrome with remote debugging:

   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
     --remote-debugging-port=9222 \
     --user-data-dir="/tmp/chrome-debug-profile"

3. Then run this script in another terminal
"""

import asyncio

from playwright.async_api import async_playwright


async def main():
    """Connect to real Chrome and test kad.arbitr.ru."""
    print("🔗 Подключаюсь к реальному Chrome через CDP...\n")

    async with async_playwright() as p:
        # Connect to existing Chrome instance
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")

        # Get existing context or create new one
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

        print("✅ Подключено к реальному Chrome!\n")

        # Navigate to kad.arbitr.ru
        print("🌐 Открываю kad.arbitr.ru...")
        await page.goto("https://kad.arbitr.ru", wait_until="networkidle")
        await asyncio.sleep(2)

        # Close popup
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(1)
        except Exception:
            pass

        print("\n" + "=" * 80)
        print("ТЕСТ: Поиск по дате (реальный Chrome)")
        print("=" * 80)

        # Fill dates
        print("\n1. Заполняю даты: 01.01.2024 - 31.01.2024")

        date_inputs = await page.query_selector_all('input[placeholder="дд.мм.гггг"]')
        if len(date_inputs) >= 2:
            # First date
            await date_inputs[0].click()
            await asyncio.sleep(0.2)
            await date_inputs[0].fill("01.01.2024")
            await asyncio.sleep(0.5)
            print("   ✓ Первая дата заполнена")

            # Second date
            await date_inputs[1].click()
            await asyncio.sleep(0.2)
            await date_inputs[1].fill("31.01.2024")
            await asyncio.sleep(0.5)
            print("   ✓ Вторая дата заполнена")

        # Close calendar
        print("\n2. Закрываю календарь...")
        await page.click("body")
        await asyncio.sleep(0.5)

        # Submit
        print("\n3. Нажимаю 'Найти'...")

        # Check form values before submit
        print("\n   Проверяю значения полей перед отправкой:")
        date_vals = await page.evaluate("""() => {
            const inputs = document.querySelectorAll('input[placeholder="дд.мм.гггг"]');
            return Array.from(inputs).map(inp => inp.value);
        }""")
        print(f"   Значения дат: {date_vals}")

        await page.click("#b-form-submit")

        # Wait for results
        print("\n4. Жду загрузки результатов...")
        await asyncio.sleep(10)

        # Check results
        print("\n5. Проверяю результаты...")
        url = page.url
        print(f"   URL: {url}")

        # Take screenshot
        screenshot_path = "/tmp/kad_chrome_results.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"   📸 Скриншот сохранён: {screenshot_path}")

        # Save HTML
        html = await page.content()
        html_path = "/tmp/kad_chrome_results.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"   💾 HTML сохранён: {html_path}")

        # Check for ANY tables on page
        all_tables = await page.query_selector_all("table")
        print(f"\n   Найдено таблиц на странице: {len(all_tables)}")

        table = await page.query_selector("table#b-cases")
        if table:
            rows = await table.query_selector_all("tr")
            print(f"   ✅ Таблица #b-cases найдена!")
            print(f"   Количество строк: {len(rows)}")

            if len(rows) > 1:
                print("\n   🎉 УСПЕХ! Дела найдены!")

                # Show first case
                first_row = rows[1] if len(rows) > 1 else None
                if first_row:
                    cells = await first_row.query_selector_all("td")
                    if cells:
                        print("\n   Первое дело:")
                        for i, cell in enumerate(cells[:5], 1):
                            text = await cell.inner_text()
                            print(f"     Колонка {i}: {text[:80]}")
            else:
                print("   ⚠️  Таблица пустая (0 строк)")
        else:
            print("   ❌ Таблица #b-cases НЕ найдена")

            # Try to find any table with data
            if len(all_tables) > 0:
                print(f"\n   Проверяю первую таблицу на странице...")
                first_table = all_tables[0]
                rows = await first_table.query_selector_all("tr")
                print(f"   Строк в первой таблице: {len(rows)}")

                if len(rows) > 0:
                    print("\n   Первая строка первой таблицы:")
                    first_row = rows[0]
                    cells = await first_row.query_selector_all("td, th")
                    for i, cell in enumerate(cells[:5], 1):
                        text = await cell.inner_text()
                        print(f"     Ячейка {i}: {text[:80]}")

        print("\n" + "=" * 80)
        print("Браузер останется открытым - проверьте результаты вручную!")
        print("=" * 80)

        input("\nНажмите Enter чтобы закрыть...")

        # Don't close browser - let user keep using it
        # await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
