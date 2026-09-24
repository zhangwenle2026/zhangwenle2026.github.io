import asyncio
import json
from playwright.async_api import async_playwright

URL = "https://km.sankuai.com/xtable/2762258282?table=2762634988&view=1000"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        contexts = browser.contexts
        context = contexts[0]
        page = await context.new_page()
        
        print(f"Navigating to: {URL}")
        await page.goto(URL, wait_until="networkidle", timeout=90000)
        await asyncio.sleep(12)
        
        # Simple extraction: just get all text
        text = await page.evaluate("() => document.body.innerText")
        print(f"Text length: {len(text)}")
        print("--- Full text ---")
        print(text[:8000])
        
        with open("/tmp/xtable_text.txt", "w") as f:
            f.write(text)
        
        await page.close()

asyncio.run(main())
