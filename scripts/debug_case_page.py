#!/usr/bin/env python3
"""
Debug case page to find PDF download links.
"""

import asyncio

from playwright.async_api import async_playwright


async def main():
    """Analyze case page structure."""
    print("🔍 Анализ страницы дела\n")

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

        # Use a known case URL
        case_url = "https://kad.arbitr.ru/Card/d9cd0693-51cd-47c5-bed6-49a7546cce3c"

        print(f"Открываю страницу дела: {case_url}\n")
        await page.goto(case_url, wait_until="networkidle")
        await asyncio.sleep(2)

        print("=" * 80)
        print("ВСЕ ССЫЛКИ НА СТРАНИЦЕ")
        print("=" * 80)

        # Get all links
        all_links = await page.query_selector_all("a")

        print(f"\nНайдено ссылок: {len(all_links)}\n")

        pdf_related = []
        for i, link in enumerate(all_links):
            href = await link.get_attribute("href")
            text = await link.inner_text()
            classes = await link.get_attribute("class")
            target = await link.get_attribute("target")

            # Filter PDF-related links
            if href and (
                "pdf" in href.lower()
                or "document" in href.lower()
                or "download" in href.lower()
                or "скачать" in text.lower()
                or "акт" in text.lower()
            ):
                pdf_related.append(
                    {
                        "index": i,
                        "text": text[:80],
                        "href": href,
                        "classes": classes,
                        "target": target,
                    }
                )

        print(f"PDF-связанных ссылок: {len(pdf_related)}\n")

        for link_info in pdf_related:
            print(f"{link_info['index']}. {link_info['text']}")
            print(f"   href: {link_info['href']}")
            print(f"   class: {link_info['classes']}")
            print(f"   target: {link_info['target']}")
            print()

        # Look for iframes
        print("=" * 80)
        print("IFRAMES")
        print("=" * 80)

        iframes = await page.query_selector_all("iframe")
        print(f"\nНайдено iframe'ов: {len(iframes)}\n")

        for i, iframe in enumerate(iframes):
            src = await iframe.get_attribute("src")
            iframe_id = await iframe.get_attribute("id")
            print(f"{i}. id={iframe_id}, src={src}")

        # Look for buttons
        print("\n" + "=" * 80)
        print("КНОПКИ")
        print("=" * 80)

        buttons = await page.query_selector_all("button")
        print(f"\nНайдено кнопок: {len(buttons)}\n")

        for i, button in enumerate(buttons[:20]):  # First 20 buttons
            text = await button.inner_text()
            btn_id = await button.get_attribute("id")
            classes = await button.get_attribute("class")
            onclick = await button.get_attribute("onclick")

            if text or onclick:
                print(f"{i}. text='{text[:50]}'")
                print(f"   id={btn_id}, class={classes}")
                print(f"   onclick={onclick[:80] if onclick else 'none'}")
                print()

        # Save full HTML for analysis
        html = await page.content()
        html_path = "/tmp/case_page_debug.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        print("=" * 80)
        print(f"✅ HTML сохранён: {html_path}")
        print("=" * 80)

        input("\nНажмите Enter чтобы закрыть...")


if __name__ == "__main__":
    asyncio.run(main())
