#!/usr/bin/env python3
"""
Детальный анализ структуры раскрывающихся кнопок.
Сохраняет HTML и показывает структуру вокруг заголовков инстанций.
"""

import asyncio
import json
from pathlib import Path

from src.scraper.playwright_scraper import PlaywrightScraper


async def debug_expand_buttons():
    """Детальный анализ кнопок раскрытия."""

    print("=" * 80)
    print("ДЕТАЛЬНЫЙ АНАЛИЗ СТРУКТУРЫ РАСКРЫВАЮЩИХСЯ КНОПОК")
    print("=" * 80)
    print()

    # Загрузить дело
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
        await asyncio.sleep(3)

        print("✅ Страница загружена\n")

        # Найти блок хронологии
        chrono_block = await scraper.page.query_selector("#chrono_list_content")
        if not chrono_block:
            print("❌ Блок #chrono_list_content не найден")
            return

        # ================================================================
        # 1. СОХРАНИТЬ HTML БЛОКА ХРОНОЛОГИИ
        # ================================================================

        print("=" * 80)
        print("1. СОХРАНЕНИЕ HTML")
        print("=" * 80)
        print()

        chrono_html = await chrono_block.inner_html()
        html_file = Path("data/chrono_block.html")
        html_file.write_text(chrono_html, encoding="utf-8")
        print(f"💾 HTML блока сохранен: {html_file}")
        print(f"   Размер: {len(chrono_html)} байт\n")

        # ================================================================
        # 2. НАЙТИ ЗАГОЛОВКИ ИНСТАНЦИЙ
        # ================================================================

        print("=" * 80)
        print("2. АНАЛИЗ ЗАГОЛОВКОВ ИНСТАНЦИЙ")
        print("=" * 80)
        print()

        headers = await chrono_block.query_selector_all(".b-chrono-item-header")
        print(f"Найдено заголовков: {len(headers)}\n")

        for i, header in enumerate(headers, 1):
            print(f"Заголовок {i}:")

            # Текст заголовка
            text = await header.inner_text()
            print(f"   Текст: {text.strip()[:80]}")

            # HTML заголовка
            header_html = await header.inner_html()
            print(f"   HTML (первые 200 символов):")
            print(f"   {header_html[:200]}")

            # Родитель заголовка
            parent = await header.evaluate_handle("el => el.parentElement")
            parent_element = parent.as_element()
            if parent_element:
                parent_tag = await parent_element.evaluate("el => el.tagName")
                parent_class = await parent_element.get_attribute("class") or ""
                print(f"   Родитель: <{parent_tag}> class='{parent_class[:60]}'")

                # HTML родителя (для поиска кнопок рядом)
                parent_html = await parent_element.inner_html()
                print(f"   HTML родителя (первые 300 символов):")
                print(f"   {parent_html[:300]}")

            # Следующий элемент (sibling)
            next_sibling = await header.evaluate_handle("el => el.nextElementSibling")
            next_element = next_sibling.as_element()
            if next_element:
                next_tag = await next_element.evaluate("el => el.tagName")
                next_class = await next_element.get_attribute("class") or ""
                next_text = await next_element.inner_text()
                print(f"   Следующий элемент: <{next_tag}> class='{next_class[:60]}'")
                print(f"   Текст: {next_text.strip()[:80]}")

            print()

        # ================================================================
        # 3. ПОИСК ВСЕХ КЛИКАБЕЛЬНЫХ ЭЛЕМЕНТОВ В БЛОКЕ
        # ================================================================

        print("=" * 80)
        print("3. ВСЕ КЛИКАБЕЛЬНЫЕ ЭЛЕМЕНТЫ")
        print("=" * 80)
        print()

        clickable_selectors = [
            "button",
            "a[role='button']",
            "[onclick]",
            "svg",
            ".icon",
            "[class*='expand']",
            "[class*='toggle']",
            "[class*='plus']",
            "[class*='chevron']",
            "[class*='arrow']",
        ]

        for selector in clickable_selectors:
            elements = await chrono_block.query_selector_all(selector)
            if elements:
                print(f"✓ {selector}: {len(elements)} шт.")
                for j, el in enumerate(elements[:3], 1):
                    try:
                        tag = await el.evaluate("el => el.tagName")
                        classes = await el.get_attribute("class") or ""
                        text = await el.inner_text()
                        print(f"   {j}. <{tag}> class='{classes[:50]}' text='{text.strip()[:30]}'")
                    except:
                        pass
                print()

        # ================================================================
        # 4. JAVASCRIPT ВЫПОЛНЕНИЕ ДЛЯ ПОИСКА КНОПОК
        # ================================================================

        print("=" * 80)
        print("4. ПОИСК ЧЕРЕЗ JAVASCRIPT")
        print("=" * 80)
        print()

        # Выполнить JavaScript для поиска всех элементов с onclick или event listeners
        result = await chrono_block.evaluate("""
            (element) => {
                const allElements = element.querySelectorAll('*');
                const clickableElements = [];

                allElements.forEach((el, index) => {
                    // Проверить onclick
                    if (el.onclick || el.getAttribute('onclick')) {
                        clickableElements.push({
                            index: index,
                            tag: el.tagName,
                            class: el.className,
                            id: el.id,
                            text: el.textContent.substring(0, 50),
                            hasOnclick: true
                        });
                    }

                    // Проверить cursor pointer
                    const style = window.getComputedStyle(el);
                    if (style.cursor === 'pointer') {
                        clickableElements.push({
                            index: index,
                            tag: el.tagName,
                            class: el.className,
                            id: el.id,
                            text: el.textContent.substring(0, 50),
                            cursorPointer: true
                        });
                    }
                });

                return clickableElements.slice(0, 20); // Первые 20
            }
        """)

        if result:
            print(f"Найдено элементов через JS: {len(result)}\n")
            for item in result:
                print(f"<{item['tag']}> class='{item.get('class', '')[:50]}'")
                print(f"   Text: {item.get('text', '')[:60]}")
                if item.get('hasOnclick'):
                    print(f"   ✓ Имеет onclick")
                if item.get('cursorPointer'):
                    print(f"   ✓ Cursor: pointer")
                print()
        else:
            print("Не найдено элементов через JS\n")

        print("=" * 80)
        print("✅ АНАЛИЗ ЗАВЕРШЕН")
        print("=" * 80)
        print()
        print("📋 Следующие шаги:")
        print("   1. Изучите вывод выше")
        print("   2. Откройте data/chrono_block.html для изучения структуры")
        print("   3. Найдите точные селекторы для кнопок раскрытия")


if __name__ == "__main__":
    asyncio.run(debug_expand_buttons())
