#!/usr/bin/env python3
"""
Debug script to see what happens after form submission.
"""

import asyncio

from playwright.async_api import async_playwright


async def main():
    """Debug form submission and results page."""
    print("🔍 Отладка поиска на kad.arbitr.ru...\n")

    async with async_playwright() as p:
        # Launch browser with anti-detection
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=1000,  # Slow motion!
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        # Create context with realistic settings
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )

        # Create page from context
        page = await context.new_page()

        # Hide automation markers
        await page.add_init_script("""
            // Hide webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en']
            });

            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Mock chrome object
            if (!window.chrome) {
                window.chrome = {
                    runtime: {}
                };
            }
        """)

        # Navigate
        await page.goto("https://kad.arbitr.ru", wait_until="networkidle")
        await asyncio.sleep(2)

        # Close popup
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(1)
        except Exception:
            pass

        print("=" * 80)
        print("ТЕСТ: Поиск по дате (без фильтра по суду)")
        print("=" * 80)

        # Fill ONLY dates (no court, no case number)
        print("\n1. Заполняю только даты: 01.01.2024 - 31.01.2024")

        date_inputs = await page.query_selector_all('input[placeholder="дд.мм.гггг"]')
        if len(date_inputs) >= 2:
            # Fill first date: click -> fill -> wait
            await date_inputs[0].click()  # Focus on first field
            await asyncio.sleep(0.2)
            await date_inputs[0].fill("01.01.2024")
            await asyncio.sleep(0.5)
            print("   ✓ Первая дата заполнена")

            # Fill second date: click on second field (closes first calendar) -> fill -> wait
            await date_inputs[1].click()  # Focus on second field (closes first calendar)
            await asyncio.sleep(0.2)
            await date_inputs[1].fill("31.01.2024")
            await asyncio.sleep(0.5)
            print("   ✓ Вторая дата заполнена")

        # Close second calendar by clicking elsewhere
        print("\n2. Закрываю календарь кликом по body...")
        await page.click("body")  # Click somewhere safe to close second calendar
        await asyncio.sleep(0.5)

        # Click submit
        print("\n3. Нажимаю кнопку 'Найти'...")
        await page.click("#b-form-submit")

        # Wait for page to load
        print("\n4. Жду загрузки результатов (10 секунд)...")
        await asyncio.sleep(10)

        # Check URL
        current_url = page.url
        print(f"\n5. Текущий URL: {current_url}")

        # Check for results table
        print("\n6. Проверяю наличие таблицы результатов...")
        table = await page.query_selector("table#b-cases")
        if table:
            print("   ✓ Таблица найдена: table#b-cases")

            # Get first row
            rows = await table.query_selector_all("tr")
            print(f"   Количество строк в таблице: {len(rows)}")

            if len(rows) > 1:  # Skip header row
                print("\n   Первая строка данных:")
                first_row_html = await rows[1].inner_html()
                print(f"   {first_row_html[:200]}...")
        else:
            print("   ✗ Таблица НЕ найдена!")

        # Check for pagination
        print("\n7. Проверяю пагинацию...")
        pages_input = await page.query_selector("input#documentsPagesCount")
        if pages_input:
            value = await pages_input.get_attribute("value")
            print(f"   ✓ Найден input#documentsPagesCount: {value} страниц")
        else:
            print("   ✗ input#documentsPagesCount НЕ найден!")

            # Try alternative selectors
            print("\n   Ищу альтернативные элементы пагинации...")

            # Look for any pagination elements
            pagination = await page.query_selector(".b-paginat")
            if pagination:
                html = await pagination.inner_html()
                print(f"   ✓ Найдена пагинация (.b-paginat):")
                print(f"   {html[:200]}...")

        # Check for "no results" message
        print("\n8. Проверяю сообщение 'ничего не найдено'...")
        no_results = await page.query_selector(".no-result, .b-nothing-found")
        if no_results:
            text = await no_results.text_content()
            print(f"   ⚠️  Найдено сообщение: {text}")
        else:
            print("   ✓ Сообщения об отсутствии результатов нет")

        # Save HTML for inspection
        print("\n9. Сохраняю HTML страницы результатов...")
        html = await page.content()
        with open("/tmp/kad_search_results.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("   ✓ Сохранено в /tmp/kad_search_results.html")

        print("\n" + "=" * 80)
        print("Браузер останется открытым - изучите страницу!")
        print("=" * 80)

        input("\nНажмите Enter чтобы закрыть...")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
