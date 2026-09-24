import asyncio
from playwright.async_api import async_playwright

async def navigate():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        contexts = browser.contexts
        if not contexts:
            print("No contexts found")
            return
        page = contexts[0].pages[0] if contexts[0].pages else await contexts[0].new_page()
        print(f"Current page: {page.url}")
        await page.goto("https://bi.keetapp.com/dashboard/300001446", wait_until="networkidle", timeout=60000)
        print(f"Navigated to: {page.url}")
        await asyncio.sleep(3)
        print("Ready for data fetch")

asyncio.run(navigate())
