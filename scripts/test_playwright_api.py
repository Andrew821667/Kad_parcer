#!/usr/bin/env python3
"""
API клиент на базе Playwright для обхода HTTP 451

Этот клиент использует настоящий браузер для выполнения API запросов,
что позволяет обойти продвинутую защиту от ботов.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page


class PlaywrightKadClient:
    """KAD Arbitr API клиент на базе Playwright (полная эмуляция браузера)"""

    def __init__(self, headless: bool = True):
        """
        Args:
            headless: Запускать браузер в headless режиме (без GUI)
        """
        self.headless = headless
        self.base_url = "https://kad.arbitr.ru"
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._playwright = None

    async def __aenter__(self):
        """Enter async context manager"""
        await self.start()
        return self

    async def __aexit__(self, *args):
        """Exit async context manager"""
        await self.close()

    async def start(self):
        """Запустить браузер и создать контекст"""
        self._playwright = await async_playwright().start()

        # Запускаем Chromium (наиболее совместимый)
        self.browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
            ]
        )

        # Создаем контекст с реалистичными параметрами
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            extra_http_headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "X-Requested-With": "XMLHttpRequest",
                "x-date-format": "iso",
            }
        )

        # Создаем страницу
        self.page = await self.context.new_page()

        # Открываем главную страницу для получения сессии
        print(f"📡 Открываю главную страницу...")
        response = await self.page.goto(self.base_url, wait_until="networkidle")
        print(f"✅ Статус: {response.status}")

        if response.status != 200:
            raise Exception(f"Не удалось открыть главную страницу: {response.status}")

    async def close(self):
        """Закрыть браузер"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def api_request(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Выполнить API запрос через браузер

        Args:
            endpoint: API endpoint (например, "/Kad/SearchInstances")
            payload: JSON payload

        Returns:
            JSON ответ от API
        """
        if not self.page:
            raise Exception("Браузер не запущен. Вызовите start() сначала.")

        url = f"{self.base_url}{endpoint}"

        print(f"\n📤 API запрос: POST {endpoint}")
        print(f"   Payload: {json.dumps(payload, ensure_ascii=False)[:100]}...")

        # Выполняем fetch через JavaScript в контексте страницы
        # Это гарантирует, что у нас есть все нужные cookies, headers, и browser fingerprint
        result = await self.page.evaluate("""
            async ({url, payload}) => {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json, text/javascript, */*; q=0.01',
                        'X-Requested-With': 'XMLHttpRequest',
                        'x-date-format': 'iso',
                    },
                    body: JSON.stringify(payload),
                    credentials: 'include',  // Включить cookies
                });

                const status = response.status;
                const text = await response.text();

                let data;
                try {
                    data = JSON.parse(text);
                } catch {
                    data = text;
                }

                return {
                    status: status,
                    data: data,
                    headers: Object.fromEntries(response.headers.entries()),
                };
            }
        """, {"url": url, "payload": payload})

        print(f"📥 Статус: {result['status']}")

        if result['status'] != 200:
            raise Exception(f"HTTP {result['status']}: {result.get('data', 'No data')}")

        return result['data']

    async def search_cases(
        self,
        case_number: Optional[str] = None,
        participant_name: Optional[str] = None,
        court: Optional[str] = None,
        page: int = 1,
        count: int = 25,
    ) -> dict[str, Any]:
        """
        Поиск дел

        Args:
            case_number: Номер дела (например, "А40-100000/2024")
            participant_name: Имя участника
            court: Код суда
            page: Номер страницы
            count: Количество результатов

        Returns:
            JSON ответ с результатами поиска
        """
        payload: dict[str, Any] = {
            "Page": page,
            "Count": count,
        }

        if case_number:
            payload["CaseNumbers"] = [case_number]

        if participant_name:
            payload["Participants"] = [{"Name": participant_name}]

        if court:
            payload["Courts"] = [court]

        return await self.api_request("/Kad/SearchInstances", payload)

    async def search_by_court_and_date(
        self,
        court_code: str,
        date_from: str,
        date_to: str,
        page: int = 1,
        count: int = 100,
    ) -> dict[str, Any]:
        """
        Поиск дел по суду и датам

        Args:
            court_code: Код суда (например, "А40")
            date_from: Дата начала (YYYY-MM-DD)
            date_to: Дата конца (YYYY-MM-DD)
            page: Номер страницы
            count: Количество результатов

        Returns:
            JSON ответ с результатами поиска
        """
        payload = {
            "Page": page,
            "Count": count,
            "Courts": [court_code],
            "DateFrom": date_from,
            "DateTo": date_to,
        }

        return await self.api_request("/Kad/SearchInstances", payload)


async def test_playwright_client():
    """Тест Playwright клиента"""
    print("\n" + "█" * 60)
    print("█" + " " * 58 + "█")
    print("█" + "   ТЕСТ PLAYWRIGHT API КЛИЕНТА".center(58) + "█")
    print("█" + " " * 58 + "█")
    print("█" * 60)

    async with PlaywrightKadClient(headless=False) as client:
        # Тест 1: Поиск по номеру дела
        print("\n" + "=" * 60)
        print("ТЕСТ 1: Поиск дела А54-927/2025")
        print("=" * 60)

        try:
            result = await client.search_cases(case_number="А54-927/2025")
            print("\n✅ УСПЕШНО!")
            print(f"   Найдено дел: {result.get('Result', {}).get('TotalCount', 0)}")

            # Сохраняем результат
            output_path = Path("/tmp/kad_playwright_search_result.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"💾 Результат сохранен: {output_path}")

            # Показываем первое дело
            items = result.get("Result", {}).get("Items", [])
            if items:
                first_case = items[0]
                print("\n📋 Первое дело:")
                print(f"   ID: {first_case.get('Id')}")
                print(f"   Номер: {first_case.get('CaseNumber')}")
                print(f"   Суд: {first_case.get('CourtName')}")
                print(f"   Категория: {first_case.get('CaseType')}")

        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return False

        # Тест 2: Массовый поиск
        print("\n" + "=" * 60)
        print("ТЕСТ 2: Поиск дел АС Москвы (декабрь 2024)")
        print("=" * 60)

        try:
            result = await client.search_by_court_and_date(
                court_code="А40",
                date_from="2024-12-01",
                date_to="2024-12-31",
                count=10,
            )
            print("\n✅ УСПЕШНО!")
            print(f"   Найдено дел: {result.get('Result', {}).get('TotalCount', 0)}")

            # Сохраняем результат
            output_path = Path("/tmp/kad_playwright_bulk_search_result.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"💾 Результат сохранен: {output_path}")

        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return False

    print("\n" + "=" * 60)
    print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    print("=" * 60)
    print("\n📊 Результаты:")
    print("   - /tmp/kad_playwright_search_result.json")
    print("   - /tmp/kad_playwright_bulk_search_result.json")
    print("\n" + "█" * 60 + "\n")

    return True


if __name__ == "__main__":
    asyncio.run(test_playwright_client())
