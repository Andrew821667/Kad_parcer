#!/usr/bin/env python3
"""
Test clicking "Next Page" to understand pagination navigation.
"""

import asyncio

from playwright.async_api import async_playwright


async def main():
    """Test next page navigation."""
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
        print("ТЕСТ ПЕРЕХОДА НА СЛЕДУЮЩУЮ СТРАНИЦУ")
        print("=" * 80)

        # Check table on page 1
        table = await page.query_selector("table#b-cases")
        if not table:
            print("\n❌ Таблица не найдена. Сначала выполните поиск!")
            return

        rows = await table.query_selector_all("tr")
        print(f"\n1. СТРАНИЦА 1: Строк в таблице = {len(rows)}")

        if len(rows) > 1:
            first_row = rows[1]
            cells = await first_row.query_selector_all("td")
            if cells and len(cells) > 0:
                first_case_page1 = await cells[0].inner_text()
                print(f"   Первое дело: {first_case_page1[:80]}")

        # Analyze pagination footer
        print("\n2. Анализ элементов пагинации...")
        footer = await page.query_selector("div#b-footer-pages")

        if footer:
            # Get all links and buttons in footer
            links = await footer.query_selector_all("a")
            print(f"   Найдено ссылок в футере: {len(links)}")

            for i, link in enumerate(links[:10], 1):  # Show first 10 links
                text = await link.inner_text()
                href = await link.get_attribute("href")
                link_id = await link.get_attribute("id")
                class_name = await link.get_attribute("class")
                print(
                    f"   Link {i}: text='{text.strip()}', id='{link_id}', class='{class_name}', href='{href}'"
                )

            # Get all buttons
            buttons = await footer.query_selector_all("button")
            print(f"\n   Найдено кнопок в футере: {len(buttons)}")

            for i, btn in enumerate(buttons, 1):
                text = await btn.inner_text()
                btn_id = await btn.get_attribute("id")
                onclick = await btn.get_attribute("onclick")
                class_name = await btn.get_attribute("class")
                print(
                    f"   Button {i}: text='{text.strip()}', id='{btn_id}', class='{class_name}', onclick='{onclick}'"
                )

            # Get all inputs
            inputs = await footer.query_selector_all("input")
            print(f"\n   Найдено input'ов в футере: {len(inputs)}")

            for i, inp in enumerate(inputs, 1):
                inp_id = await inp.get_attribute("id")
                inp_name = await inp.get_attribute("name")
                inp_value = await inp.get_attribute("value")
                inp_type = await inp.get_attribute("type")
                print(
                    f"   Input {i}: id='{inp_id}', name='{inp_name}', type='{inp_type}', value='{inp_value}'"
                )

        # Try different methods to go to next page
        print("\n3. Пробую перейти на страницу 2...")

        success = False

        # Method 1: Try input#documentsPageNumber
        page_input = await page.query_selector("input#documentsPageNumber")
        if page_input:
            print("   Метод 1: Ввод номера страницы в input#documentsPageNumber")
            await page_input.fill("2")
            await asyncio.sleep(0.5)

            # Look for submit/go button
            go_button = await page.query_selector(
                "button[onclick*='loadDocumentsCalendar'], button.b-go-page, #goToPage"
            )
            if go_button:
                print("   Найдена кнопка перехода, кликаю...")
                await go_button.click()
                await asyncio.sleep(3)
                success = True
            else:
                # Try pressing Enter
                print("   Кнопка не найдена, пробую Enter...")
                await page_input.press("Enter")
                await asyncio.sleep(3)
                success = True

        # Method 2: Look for "next" link/button
        if not success:
            print("   Метод 2: Поиск ссылки/кнопки 'Следующая'")
            next_selectors = [
                "a:has-text('›')",
                "a:has-text('»')",
                "a:has-text('Следующая')",
                "button:has-text('›')",
                ".next-page",
                "#nextPage",
            ]

            for selector in next_selectors:
                next_btn = await page.query_selector(selector)
                if next_btn:
                    print(f"   Найден элемент: {selector}")
                    await next_btn.click()
                    await asyncio.sleep(3)
                    success = True
                    break

        # Method 3: Click on link with text "2"
        if not success:
            print("   Метод 3: Клик по ссылке с текстом '2'")
            link_2 = await page.query_selector("a:has-text('2')")
            if link_2:
                print("   Найдена ссылка '2', кликаю...")
                await link_2.click()
                await asyncio.sleep(3)
                success = True

        # Check if we moved to page 2
        print("\n4. Проверяю результат...")

        table = await page.query_selector("table#b-cases")
        if table:
            rows = await table.query_selector_all("tr")
            print(f"   СТРАНИЦА 2 (?): Строк в таблице = {len(rows)}")

            if len(rows) > 1:
                first_row = rows[1]
                cells = await first_row.query_selector_all("td")
                if cells and len(cells) > 0:
                    first_case_page2 = await cells[0].inner_text()
                    print(f"   Первое дело: {first_case_page2[:80]}")

                    if first_case_page2 != first_case_page1:
                        print("\n   ✅ УСПЕХ! Перешли на страницу 2 (дела изменились)")
                    else:
                        print("\n   ❌ Дела не изменились, всё ещё на странице 1")

        # Check current page number
        page_input = await page.query_selector("input#documentsPageNumber")
        if page_input:
            current_page = await page_input.get_attribute("value")
            print(f"   Текущая страница (по input): {current_page}")

        print("\n" + "=" * 80)
        print("Тест завершен!")
        print("=" * 80)

        input("\nНажмите Enter чтобы закрыть...")


if __name__ == "__main__":
    asyncio.run(main())
