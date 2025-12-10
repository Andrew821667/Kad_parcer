#!/usr/bin/env python3
"""
Test AJAX-based pagination on kad.arbitr.ru.
"""

import asyncio

from playwright.async_api import async_playwright


async def main():
    """Test AJAX pagination."""
    print("🔗 Подключаюсь к реальному Chrome через CDP...")

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

        print("✅ Подключено к реальному Chrome!")
        print("\n" + "=" * 80)
        print("ТЕСТ AJAX ПАГИНАЦИИ")
        print("=" * 80)

        # Get first case on page 1
        table = await page.query_selector("table#b-cases")
        if not table:
            print("\n❌ Таблица не найдена!")
            return

        rows = await table.query_selector_all("tr")
        first_case_page1 = ""
        if len(rows) > 1:
            cells = await rows[1].query_selector_all("td")
            if cells:
                first_case_page1 = await cells[0].inner_text()
                print(f"\n1. Страница 1, первое дело:\n{first_case_page1[:80]}")

        # Analyze link onclick/event handlers
        print("\n2. Анализ JavaScript обработчиков на ссылках...")
        link2 = await page.query_selector("a[href='#page2']")

        if link2:
            # Check onclick
            onclick = await link2.get_attribute("onclick")
            print(f"   onclick атрибут: {onclick}")

            # Check all attributes
            attrs = await page.evaluate(
                """(link) => {
                const attrs = {};
                for (let attr of link.attributes) {
                    attrs[attr.name] = attr.value;
                }
                return attrs;
            }""",
                link2,
            )
            print(f"   Все атрибуты ссылки: {attrs}")

            # Check event listeners (might not work due to security)
            print("\n3. Пробую разные способы перехода на страницу 2...")

            # Method 1: Direct click with wait for response
            print("\n   Метод 1: Клик + ожидание AJAX запроса")

            # Set up request interception to catch AJAX
            requests_made = []

            async def handle_request(request):
                if "calendar" in request.url.lower() or "page" in request.url.lower():
                    requests_made.append(request.url)
                    print(f"      → AJAX запрос: {request.url}")

            page.on("request", handle_request)

            # Click and wait
            await link2.click()
            print("      Клик выполнен, жду 5 секунд...")
            await asyncio.sleep(5)

            # Remove listener
            page.remove_listener("request", handle_request)

            if requests_made:
                print(f"      Обнаружено {len(requests_made)} AJAX запросов")
            else:
                print("      AJAX запросов не обнаружено")

            # Check if page changed
            table = await page.query_selector("table#b-cases")
            if table:
                rows = await table.query_selector_all("tr")
                if len(rows) > 1:
                    cells = await rows[1].query_selector_all("td")
                    if cells:
                        first_case_after = await cells[0].inner_text()
                        if first_case_after != first_case_page1:
                            print(f"\n   ✅ УСПЕХ! Страница изменилась!")
                            print(f"   Новое первое дело:\n{first_case_after[:80]}")
                            return
                        else:
                            print("      ❌ Дела не изменились")

            # Method 2: Execute hash navigation
            print("\n   Метод 2: JavaScript window.location.hash")
            await page.evaluate("window.location.hash = 'page2'")
            await asyncio.sleep(3)

            # Check again
            table = await page.query_selector("table#b-cases")
            if table:
                rows = await table.query_selector_all("tr")
                if len(rows) > 1:
                    cells = await rows[1].query_selector_all("td")
                    if cells:
                        first_case_after = await cells[0].inner_text()
                        if first_case_after != first_case_page1:
                            print(f"\n   ✅ УСПЕХ! Страница изменилась!")
                            print(f"   Новое первое дело:\n{first_case_after[:80]}")
                            return

            # Method 3: Look for KAD-specific functions
            print("\n   Метод 3: Поиск КАД-специфичных функций...")

            # Try common function names
            functions_to_try = [
                "loadDocumentsCalendar(2)",
                "goToPage(2)",
                "showPage(2)",
                "loadPage(2)",
                "changePage(2)",
            ]

            for func in functions_to_try:
                try:
                    result = await page.evaluate(f"typeof {func.split('(')[0]}")
                    if result == "function":
                        print(f"      Найдена функция: {func.split('(')[0]}")
                        await page.evaluate(func)
                        await asyncio.sleep(3)

                        # Check if worked
                        table = await page.query_selector("table#b-cases")
                        if table:
                            rows = await table.query_selector_all("tr")
                            if len(rows) > 1:
                                cells = await rows[1].query_selector_all("td")
                                if cells:
                                    first_case_after = await cells[0].inner_text()
                                    if first_case_after != first_case_page1:
                                        print(f"\n   ✅ УСПЕХ! Функция {func} работает!")
                                        print(
                                            f"   Новое первое дело:\n{first_case_after[:80]}"
                                        )
                                        return
                except Exception as e:
                    pass  # Function doesn't exist

            # Method 4: Check if table reloads dynamically
            print("\n   Метод 4: Проверка динамической загрузки таблицы...")

            # Click on link again and watch for DOM changes
            await link2.click()

            # Wait for table to potentially reload
            try:
                await page.wait_for_function(
                    """() => {
                    const table = document.querySelector('table#b-cases');
                    return table && table.querySelectorAll('tr').length > 1;
                }""",
                    timeout=5000,
                )
                print("      Таблица перезагружена!")

                await asyncio.sleep(2)

                table = await page.query_selector("table#b-cases")
                if table:
                    rows = await table.query_selector_all("tr")
                    if len(rows) > 1:
                        cells = await rows[1].query_selector_all("td")
                        if cells:
                            first_case_after = await cells[0].inner_text()
                            if first_case_after != first_case_page1:
                                print(f"\n   ✅ УСПЕХ!")
                                print(f"   Новое первое дело:\n{first_case_after[:80]}")
                                return
            except Exception as e:
                print(f"      Timeout: {e}")

        print("\n❌ Не удалось найти рабочий метод пагинации")
        print("Возможно, нужно изучить JavaScript код сайта детальнее")

        print("\n" + "=" * 80)
        input("\nНажмите Enter чтобы закрыть...")


if __name__ == "__main__":
    asyncio.run(main())
