#!/usr/bin/env python3
"""
Детальный анализ HTML структуры страницы дела.
Ищет все возможные раскрывающиеся элементы и группировки по инстанциям.
"""

import asyncio
import json
from pathlib import Path

from src.scraper.playwright_scraper import PlaywrightScraper


async def deep_html_analysis():
    """Глубокий анализ HTML структуры."""

    print("=" * 80)
    print("ГЛУБОКИЙ АНАЛИЗ HTML СТРУКТУРЫ СТРАНИЦЫ ДЕЛА")
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

        # ================================================================
        # 1. ПОИСК ВСЕХ ЭЛЕМЕНТОВ С ТЕКСТОМ "ИНСТАНЦИЯ"
        # ================================================================

        print("=" * 80)
        print("1. ЭЛЕМЕНТЫ С ТЕКСТОМ 'ИНСТАНЦИЯ'")
        print("=" * 80)
        print()

        elements = await scraper.page.query_selector_all("*")
        instance_elements = []

        for el in elements[:500]:  # Первые 500 элементов
            try:
                text = await el.inner_text()
                if 'инстанц' in text.lower():
                    tag = await el.evaluate("el => el.tagName")
                    classes = await el.get_attribute("class") or ""
                    element_id = await el.get_attribute("id") or ""

                    instance_elements.append({
                        "tag": tag,
                        "id": element_id,
                        "class": classes,
                        "text": text[:100],
                    })
            except:
                pass

        print(f"Найдено элементов: {len(instance_elements)}\n")
        for i, el in enumerate(instance_elements[:10], 1):
            print(f"{i}. <{el['tag']}> id='{el['id']}' class='{el['class']}'")
            print(f"   Текст: {el['text'][:80]}")
            print()

        # ================================================================
        # 2. ВСЕ КЛИКАБЕЛЬНЫЕ ЭЛЕМЕНТЫ
        # ================================================================

        print("=" * 80)
        print("2. КЛИКАБЕЛЬНЫЕ ЭЛЕМЕНТЫ (КНОПКИ/ССЫЛКИ)")
        print("=" * 80)
        print()

        buttons = await scraper.page.query_selector_all("button, a.toggle, [role='button'], [onclick]")
        print(f"Всего кнопок/ссылок: {len(buttons)}\n")

        for i, btn in enumerate(buttons[:15], 1):
            try:
                text = await btn.inner_text()
                tag = await btn.evaluate("el => el.tagName")
                classes = await btn.get_attribute("class") or ""

                if text.strip():
                    print(f"{i}. <{tag}> class='{classes[:50]}'")
                    print(f"   Текст: {text.strip()[:60]}")
                    print()
            except:
                pass

        # ================================================================
        # 3. СТРУКТУРА ДОКУМЕНТОВ
        # ================================================================

        print("=" * 80)
        print("3. СТРУКТУРА БЛОКОВ С ДОКУМЕНТАМИ")
        print("=" * 80)
        print()

        # Поиск контейнеров с PDF
        pdf_containers = await scraper.page.query_selector_all("div:has(a[href$='.pdf']), ul:has(a[href$='.pdf']), section:has(a[href$='.pdf'])")

        print(f"Контейнеров с PDF: {len(pdf_containers)}\n")

        for i, container in enumerate(pdf_containers[:5], 1):
            tag = await container.evaluate("el => el.tagName")
            classes = await container.get_attribute("class") or ""

            # Сколько PDF внутри
            pdfs = await container.query_selector_all('a[href$=".pdf"]')

            print(f"{i}. <{tag}> class='{classes[:60]}'")
            print(f"   PDF внутри: {len(pdfs)}")

            # Показать первые 3 PDF
            for j, pdf in enumerate(pdfs[:3], 1):
                try:
                    pdf_text = await pdf.inner_text()
                    print(f"      {j}. {pdf_text.strip()[:50]}")
                except:
                    pass
            print()

        # ================================================================
        # 4. JAVASCRIPT EVENTS
        # ================================================================

        print("=" * 80)
        print("4. ЭЛЕМЕНТЫ С JAVASCRIPT EVENTS")
        print("=" * 80)
        print()

        js_elements = await scraper.page.query_selector_all("[onclick], [data-toggle], [data-target]")
        print(f"Элементов с JS events: {len(js_elements)}\n")

        for i, el in enumerate(js_elements[:10], 1):
            tag = await el.evaluate("el => el.tagName")
            onclick = await el.get_attribute("onclick") or ""
            data_toggle = await el.get_attribute("data-toggle") or ""
            data_target = await el.get_attribute("data-target") or ""

            print(f"{i}. <{tag}>")
            if onclick:
                print(f"   onclick: {onclick[:80]}")
            if data_toggle:
                print(f"   data-toggle: {data_toggle}")
            if data_target:
                print(f"   data-target: {data_target}")
            print()

        # ================================================================
        # 5. СОХРАНИТЬ ДЕТАЛЬНЫЙ HTML ФРАГМЕНТ
        # ================================================================

        print("=" * 80)
        print("5. СОХРАНЕНИЕ HTML")
        print("=" * 80)
        print()

        # Найти главный контейнер с делом
        main_content = await scraper.page.query_selector("main, #content, .content, .case-content")
        if main_content:
            html_fragment = await main_content.inner_html()

            fragment_file = Path("data/case_main_content.html")
            fragment_file.write_text(html_fragment, encoding="utf-8")
            print(f"💾 Основной контент сохранен: {fragment_file}")
            print(f"   Размер: {len(html_fragment)} байт\n")

        full_html = await scraper.page.content()
        full_file = Path("data/case_full_page.html")
        full_file.write_text(full_html, encoding="utf-8")
        print(f"💾 Полная страница сохранена: {full_file}")
        print(f"   Размер: {len(full_html)} байт")

        print("\n" + "=" * 80)
        print("✅ АНАЛИЗ ЗАВЕРШЕН")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(deep_html_analysis())
