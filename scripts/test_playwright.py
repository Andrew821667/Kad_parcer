#!/usr/bin/env python3
"""
Тест доступа к КАД Арбитр через Playwright (браузерная эмуляция)

Этот скрипт использует настоящий браузер для обхода защиты от ботов.
"""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

# Настройки
KAD_BASE_URL = "https://kad.arbitr.ru"
TEST_CASE_NUMBER = "А54-927/2025"
OUTPUT_DIR = Path("/tmp")


async def test_browser_access():
    """
    Тест 1: Проверка доступа к сайту через браузер
    """
    print("\n" + "=" * 60)
    print("ТЕСТ 1: Доступ к сайту kad.arbitr.ru")
    print("=" * 60)

    async with async_playwright() as p:
        # Запускаем браузер (Chromium - наиболее совместимый)
        browser = await p.chromium.launch(
            headless=False,  # Показываем браузер (для отладки)
            args=[
                '--disable-blink-features=AutomationControlled',  # Скрыть автоматизацию
            ]
        )

        # Создаем контекст с реалистичными параметрами
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )

        page = await context.new_page()

        try:
            print(f"\n📡 Переход на {KAD_BASE_URL}...")
            response = await page.goto(KAD_BASE_URL, wait_until="networkidle", timeout=30000)

            print(f"✅ Статус: {response.status}")
            print(f"✅ URL: {page.url}")
            print(f"✅ Title: {await page.title()}")

            if response.status == 451:
                print("\n❌ HTTP 451 - Геоблокировка!")
                print("Сайт недоступен из вашего региона.")
                return False

            if response.status == 200:
                print("\n✅ Сайт доступен!")

                # Сохраняем скриншот
                screenshot_path = OUTPUT_DIR / "kad_homepage.png"
                await page.screenshot(path=screenshot_path)
                print(f"📸 Скриншот сохранен: {screenshot_path}")

                # Извлекаем cookies
                cookies = await context.cookies()
                cookies_path = OUTPUT_DIR / "kad_cookies.json"
                with open(cookies_path, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, indent=2, ensure_ascii=False)
                print(f"🍪 Cookies сохранены: {cookies_path}")
                print(f"   Всего cookies: {len(cookies)}")

                return True

            print(f"\n⚠️ Неожиданный статус: {response.status}")
            return False

        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            return False
        finally:
            await browser.close()


async def test_search_via_browser():
    """
    Тест 2: Поиск дела через веб-интерфейс
    """
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Поиск дела через веб-интерфейс")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )

        page = await context.new_page()

        # Перехватываем API запросы
        api_requests = []
        api_responses = []

        async def handle_request(request):
            if "SearchInstances" in request.url:
                print(f"\n📤 API REQUEST: {request.method} {request.url}")
                print(f"   Headers: {request.headers}")
                if request.post_data:
                    print(f"   Payload: {request.post_data}")
                api_requests.append({
                    "url": request.url,
                    "method": request.method,
                    "headers": dict(request.headers),
                    "post_data": request.post_data,
                })

        async def handle_response(response):
            if "SearchInstances" in response.url:
                print(f"\n📥 API RESPONSE: {response.status} {response.url}")
                try:
                    body = await response.text()
                    print(f"   Body (first 500 chars): {body[:500]}")
                    api_responses.append({
                        "url": response.url,
                        "status": response.status,
                        "headers": dict(response.headers),
                        "body": body,
                    })
                except Exception as e:
                    print(f"   Не удалось прочитать body: {e}")

        page.on("request", handle_request)
        page.on("response", handle_response)

        try:
            print(f"\n📡 Переход на главную страницу...")
            await page.goto(KAD_BASE_URL, wait_until="networkidle", timeout=30000)

            print(f"\n🔍 Ищем форму поиска...")
            # Даем время странице загрузиться
            await page.wait_for_timeout(2000)

            # Пытаемся найти поле ввода номера дела
            # (селекторы нужно будет уточнить, изучив реальную страницу)
            print(f"   Пробуем найти элементы формы поиска...")

            # Сохраняем HTML главной страницы для анализа
            html_content = await page.content()
            html_path = OUTPUT_DIR / "kad_homepage.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"💾 HTML сохранен: {html_path}")

            print(f"\n⚠️ Для продолжения нужно изучить структуру страницы.")
            print(f"   Откройте {html_path} и найдите:")
            print(f"   1. Селектор поля ввода номера дела")
            print(f"   2. Селектор кнопки поиска")
            print(f"   3. Тип формы (обычная форма или AJAX)")

            # Ждем 5 секунд, чтобы можно было вручную кликнуть
            print(f"\n⏳ Ожидание 10 секунд...")
            print(f"   Попробуйте ВРУЧНУЮ ввести номер дела и нажать поиск!")
            print(f"   Это поможет перехватить реальный API запрос.")
            await page.wait_for_timeout(10000)

            # Сохраняем перехваченные запросы
            if api_requests:
                requests_path = OUTPUT_DIR / "kad_api_requests_captured.json"
                with open(requests_path, "w", encoding="utf-8") as f:
                    json.dump(api_requests, f, indent=2, ensure_ascii=False)
                print(f"\n✅ Перехвачено API запросов: {len(api_requests)}")
                print(f"   Сохранены в: {requests_path}")

            if api_responses:
                responses_path = OUTPUT_DIR / "kad_api_responses_captured.json"
                with open(responses_path, "w", encoding="utf-8") as f:
                    json.dump(api_responses, f, indent=2, ensure_ascii=False)
                print(f"✅ Перехвачено API ответов: {len(api_responses)}")
                print(f"   Сохранены в: {responses_path}")

        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
        finally:
            await browser.close()


async def main():
    """Главная функция"""
    print("\n" + "█" * 60)
    print("█" + " " * 58 + "█")
    print("█" + "   ТЕСТ ДОСТУПА К КАД АРБИТР ЧЕРЕЗ PLAYWRIGHT".center(58) + "█")
    print("█" + " " * 58 + "█")
    print("█" * 60)

    # Тест 1: Проверка доступа
    accessible = await test_browser_access()

    if not accessible:
        print("\n" + "=" * 60)
        print("⛔ Сайт недоступен. Дальнейшие тесты невозможны.")
        print("=" * 60)
        return

    # Тест 2: Поиск через веб-интерфейс
    await test_search_via_browser()

    print("\n" + "=" * 60)
    print("ИТОГИ")
    print("=" * 60)
    print("\nПроверьте файлы в /tmp/:")
    print("  - kad_homepage.png - скриншот главной страницы")
    print("  - kad_homepage.html - HTML для анализа структуры")
    print("  - kad_cookies.json - cookies для использования в API")
    print("  - kad_api_requests_captured.json - перехваченные запросы")
    print("  - kad_api_responses_captured.json - перехваченные ответы")
    print("\n" + "█" * 60 + "\n")


if __name__ == "__main__":
    # Установка Playwright браузеров, если еще не установлено
    print("\n⚠️ ВАЖНО: Если это первый запуск Playwright, выполните:")
    print("   python3.11 -m playwright install chromium")
    print()

    asyncio.run(main())
