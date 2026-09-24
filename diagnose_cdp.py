import asyncio
import json
from playwright.async_api import async_playwright

async def diagnose():
    async with async_playwright() as p:
        print("Connecting to CDP...")
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        print(f"Connected. Contexts: {len(browser.contexts)}")
        contexts = browser.contexts
        if not contexts:
            print("No contexts")
            return
        for i, ctx in enumerate(contexts):
            print(f"  Context {i}: {len(ctx.pages)} pages")
            for j, page in enumerate(ctx.pages):
                print(f"    Page {j}: {page.url}")
        
        page = contexts[0].pages[0] if contexts[0].pages else await contexts[0].new_page()
        print(f"Using page: {page.url}")
        
        if "dashboard-controller" not in page.url and "300001446" not in page.url:
            print("Navigating to dashboard...")
            await page.goto(
                "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446",
                wait_until="networkidle", timeout=60000
            )
        
        print(f"Page URL: {page.url}")
        
        # Check if DashboardController exists
        has_dc = await page.evaluate("() => typeof window.DashboardController !== 'undefined'")
        print(f"DashboardController available: {has_dc}")
        
        if has_dc:
            # Try a quick query on one chart
            print("Testing query on New Signs chart...")
            try:
                data = await asyncio.wait_for(
                    page.evaluate(
                        'window.DashboardController.executeQueryAndGetCHNResult("chart-e8ns5-c9347").then(res => res)'
                    ),
                    timeout=30
                )
                print(f"Query result: {json.dumps(data, ensure_ascii=False)[:300]}")
            except asyncio.TimeoutError:
                print("Query timed out - DashboardController may be unresponsive")
            except Exception as e:
                print(f"Query error: {e}")
        
        await browser.close()
        print("Done")

asyncio.run(diagnose())
