#!/usr/bin/env python3
"""
Inspect kad.arbitr.ru form fields to find correct selectors.
"""

import asyncio

from playwright.async_api import async_playwright


async def main():
    """Inspect form fields on kad.arbitr.ru."""
    print("🔍 Инспектирую форму на kad.arbitr.ru...\n")

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=False)
        page = await browser.new_page()

        # Navigate to site
        await page.goto("https://kad.arbitr.ru", wait_until="networkidle")
        await asyncio.sleep(2)

        # Close popup
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(1)
        except Exception:
            pass

        print("=" * 80)
        print("ВСЕ INPUT ПОЛЯ НА СТРАНИЦЕ:")
        print("=" * 80)

        # Get all input fields
        inputs = await page.query_selector_all("input")

        for i, input_elem in enumerate(inputs, 1):
            # Get attributes
            input_type = await input_elem.get_attribute("type")
            placeholder = await input_elem.get_attribute("placeholder")
            name = await input_elem.get_attribute("name")
            input_id = await input_elem.get_attribute("id")
            input_class = await input_elem.get_attribute("class")

            # Check if visible
            is_visible = await input_elem.is_visible()

            if is_visible:
                print(f"\n{i}. INPUT (visible):")
                print(f"   Type: {input_type}")
                print(f"   Placeholder: {placeholder}")
                print(f"   Name: {name}")
                print(f"   ID: {input_id}")
                print(f"   Class: {input_class}")

        print("\n" + "=" * 80)
        print("ВСЕ TEXTAREA ПОЛЯ НА СТРАНИЦЕ:")
        print("=" * 80)

        # Get all textarea fields
        textareas = await page.query_selector_all("textarea")

        for i, textarea in enumerate(textareas, 1):
            placeholder = await textarea.get_attribute("placeholder")
            name = await textarea.get_attribute("name")
            textarea_id = await textarea.get_attribute("id")
            is_visible = await textarea.is_visible()

            if is_visible:
                print(f"\n{i}. TEXTAREA (visible):")
                print(f"   Placeholder: {placeholder}")
                print(f"   Name: {name}")
                print(f"   ID: {textarea_id}")

        print("\n" + "=" * 80)
        print("КНОПКА ПОИСКА:")
        print("=" * 80)

        # Find submit button
        submit_button = await page.query_selector("#b-form-submit")
        if submit_button:
            text = await submit_button.text_content()
            print(f"   Text: {text}")
            print(f"   ID: b-form-submit ✓")

        print("\n" + "=" * 80)
        print("\nТеперь вы видите все поля формы!")
        print("Используйте эту информацию для правильных селекторов.")
        print("\nБраузер останется открытым - изучите форму вручную.")

        input("\nНажмите Enter чтобы закрыть...")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
