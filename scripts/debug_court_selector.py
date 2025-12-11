#!/usr/bin/env python3
"""
Debug скрипт для изучения формы поиска и выпадающего списка судов.
"""

import asyncio
from pathlib import Path

from src.scraper.playwright_scraper import PlaywrightScraper


async def debug_court_selector():
    """Изучить структуру выпадающего списка судов."""

    print("=" * 80)
    print("DEBUG: ИЗУЧЕНИЕ ФОРМЫ ПОИСКА")
    print("=" * 80)
    print()

    async with PlaywrightScraper(use_cdp=True, cdp_url="http://localhost:9222") as scraper:
        # Открыть главную страницу
        await scraper.page.goto("https://kad.arbitr.ru", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # Закрыть popup
        try:
            await scraper.page.keyboard.press("Escape")
            await asyncio.sleep(1)
        except:
            pass

        print("✅ Страница загружена\n")

        # ====================================================================
        # 1. НАЙТИ ВСЕ INPUT ПОЛЯ НА ФОРМЕ
        # ====================================================================

        print("=" * 80)
        print("1. ВСЕ INPUT ПОЛЯ")
        print("=" * 80)
        print()

        all_inputs = await scraper.page.query_selector_all("input")
        print(f"Найдено input полей: {len(all_inputs)}\n")

        for i, inp in enumerate(all_inputs[:15], 1):
            try:
                tag_name = await inp.evaluate("el => el.tagName")
                input_type = await inp.get_attribute("type") or ""
                placeholder = await inp.get_attribute("placeholder") or ""
                input_id = await inp.get_attribute("id") or ""
                input_name = await inp.get_attribute("name") or ""
                input_class = await inp.get_attribute("class") or ""

                print(f"{i}. <{tag_name}>")
                if input_type:
                    print(f"   type: {input_type}")
                if placeholder:
                    print(f"   placeholder: {placeholder}")
                if input_id:
                    print(f"   id: {input_id}")
                if input_name:
                    print(f"   name: {input_name}")
                if input_class:
                    print(f"   class: {input_class[:60]}")
                print()
            except:
                pass

        # ====================================================================
        # 2. НАЙТИ ПОЛЕ "СУД" И КЛИКНУТЬ НА НЕГО
        # ====================================================================

        print("=" * 80)
        print("2. ПОИСК ПОЛЯ 'СУД'")
        print("=" * 80)
        print()

        # ВАЖНО: Ищем поле с name="court", НЕ поле судьи!
        court_selectors = [
            'input[name="court"]',           # Точное имя поля суда
            'input[name*="court"]',
            '#court',
        ]

        court_input = None
        for selector in court_selectors:
            try:
                inp = await scraper.page.query_selector(selector)
                if inp:
                    print(f"✓ Найдено поле: {selector}")
                    placeholder = await inp.get_attribute("placeholder") or ""
                    input_id = await inp.get_attribute("id") or ""
                    input_name = await inp.get_attribute("name") or ""
                    print(f"  name: {input_name}")
                    print(f"  placeholder: {placeholder}")
                    print(f"  id: {input_id}")
                    print()

                    if not court_input:
                        court_input = inp
                        break  # Нашли - выходим
            except:
                pass

        if not court_input:
            print("❌ Поле 'Суд' не найдено!\n")

            # Сохранить HTML формы для анализа
            form_html = await scraper.page.content()
            html_file = Path("data/kad_search_form.html")
            html_file.write_text(form_html, encoding="utf-8")
            print(f"💾 HTML страницы сохранен: {html_file}\n")
            return

        # ====================================================================
        # 3. НАЙТИ ИКОНКУ РАСКРЫТИЯ СПИСКА
        # ====================================================================

        print("=" * 80)
        print("3. ПОИСК ИКОНКИ ВЫПАДАЮЩЕГО СПИСКА")
        print("=" * 80)
        print()

        # Найти родительский контейнер поля
        parent = await court_input.evaluate_handle("el => el.parentElement")
        parent_element = parent.as_element()

        dropdown_icon = None

        if parent_element:
            # Показать структуру родительского элемента и его соседей
            context_html = await court_input.evaluate("""el => {
                const parent = el.parentElement;
                const grandparent = parent.parentElement;
                return grandparent ? grandparent.outerHTML.substring(0, 1500) : parent.outerHTML.substring(0, 1500);
            }""")
            print("Контекст вокруг поля (первые 1500 символов):")
            print(context_html)
            print()

            # Попробовать найти иконку в grandparent (более широкий контекст)
            grandparent = await court_input.evaluate_handle("el => el.parentElement.parentElement")
            search_element = grandparent.as_element() if grandparent else parent_element

            # ВАЖНО: Ищем иконку ПЛЮСА рядом с полем
            dropdown_selectors = [
                'i.b-icon.add',                            # Иконка плюса
                '.b-icon.add',                             # Класс иконки плюса
                'i[class*="b-icon"]',                      # Любая иконка b-icon
                'a.b-form-autocomplete-button',            # Альтернатива - кнопка autocomplete
                'a[onclick*="showAutocompleteList"]',      # Кнопка с onclick
            ]

            for selector in dropdown_selectors:
                try:
                    icon = await search_element.query_selector(selector)
                    if icon:
                        icon_class = await icon.get_attribute("class") or ""
                        icon_tag = await icon.evaluate("el => el.tagName")
                        icon_html = await icon.evaluate("el => el.outerHTML")
                        print(f"✓ Найдена иконка: {selector}")
                        print(f"  <{icon_tag}> class='{icon_class}'")
                        print(f"  HTML: {icon_html[:300]}")
                        print()

                        if not dropdown_icon:
                            dropdown_icon = icon
                except Exception as e:
                    pass

            # Если не нашли специфичные селекторы, ищем все ссылки и фильтруем
            if not dropdown_icon:
                print("⚠️  Специфичные селекторы не сработали")
                print("   Ищу все ссылки <a> в контексте...")
                print()

                all_links = await search_element.query_selector_all('a')
                for link in all_links:
                    try:
                        link_class = await link.get_attribute("class") or ""
                        link_onclick = await link.get_attribute("onclick") or ""

                        # Пропустить декоративные элементы
                        if any(x in link_class for x in ['lt', 'rt', 'lb', 'rb', 'corners']):
                            continue

                        # Искать кнопки автокомплита
                        if "autocomplete" in link_class.lower() or "autocomplete" in link_onclick.lower():
                            link_html = await link.evaluate("el => el.outerHTML")
                            print(f"✓ Найдена кнопка autocomplete:")
                            print(f"  class: {link_class}")
                            print(f"  onclick: {link_onclick[:100]}")
                            print(f"  HTML: {link_html[:300]}")
                            print()

                            if not dropdown_icon:
                                dropdown_icon = link
                                break
                    except:
                        pass

        # Если не нашли в родителе, поискать во всей форме
        if not dropdown_icon:
            print("⚠️  Иконка не найдена в родительском элементе")
            print("   Ищу во всей форме...")
            print()

            # Поискать все ссылки и кнопки рядом с полем суда
            all_buttons = await scraper.page.query_selector_all('a, button')
            for btn in all_buttons:
                try:
                    onclick = await btn.get_attribute("onclick") or ""
                    btn_class = await btn.get_attribute("class") or ""

                    if "autocomplete" in onclick.lower() or "autocomplete" in btn_class.lower():
                        print(f"✓ Найдена возможная кнопка:")
                        btn_html = await btn.evaluate("el => el.outerHTML")
                        print(f"  {btn_html[:200]}")
                        print()

                        if not dropdown_icon:
                            dropdown_icon = btn
                            break
                except:
                    pass

        # Кликнуть на иконку
        if dropdown_icon:
            print("✓ Кликаем на иконку раскрытия списка...")
            try:
                await dropdown_icon.click()
                await asyncio.sleep(3)
                print("✓ Кликнули, ждем 3 секунды...")
                print()
            except Exception as e:
                print(f"❌ Ошибка при клике: {e}")
                print()
        else:
            print("⚠️  Иконка не найдена НИГДЕ!")
            print("   Пробуем просто кликнуть на поле и ввести текст...")
            print()
            await court_input.click()
            await asyncio.sleep(1)
            await court_input.type("А", delay=100)
            await asyncio.sleep(3)

        # ====================================================================
        # 4. НАЙТИ ВЫПАДАЮЩИЙ СПИСОК
        # ====================================================================

        print("\n" + "=" * 80)
        print("4. ПОИСК ВЫПАДАЮЩЕГО СПИСКА")
        print("=" * 80)
        print()

        # Попробовать разные селекторы для списка
        list_selectors = [
            '.b-form-autocomplete-list',
            '.autocomplete-list',
            '.dropdown-menu',
            '[role="listbox"]',
            'ul.autocomplete',
            '.suggestions',
        ]

        for selector in list_selectors:
            try:
                list_elem = await scraper.page.query_selector(selector)
                if list_elem:
                    print(f"✓ Найден список: {selector}")

                    # Получить элементы списка
                    items = await list_elem.query_selector_all('li, [role="option"], .item')
                    print(f"  Элементов в списке: {len(items)}\n")

                    if items:
                        print("  Первые 10 элементов:")
                        for i, item in enumerate(items[:10], 1):
                            try:
                                text = await item.inner_text()
                                print(f"    {i}. {text.strip()}")
                            except:
                                pass
                        print()
                        break
            except:
                pass

        # Сохранить HTML после раскрытия списка
        page_html = await scraper.page.content()
        html_file = Path("data/kad_search_form_with_court_list.html")
        html_file.write_text(page_html, encoding="utf-8")
        print(f"💾 HTML с раскрытым списком сохранен: {html_file}\n")

        print("=" * 80)
        print("✅ DEBUG ЗАВЕРШЕН")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(debug_court_selector())
