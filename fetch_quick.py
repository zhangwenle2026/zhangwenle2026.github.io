import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        contexts = browser.contexts
        if not contexts:
            print("ERROR: No contexts")
            return
        page = contexts[0].pages[0]
        print(f"Page: {page.url}")
        
        # Check if DashboardController is available
        has_dc = await page.evaluate("typeof window.DashboardController !== 'undefined'")
        print(f"DashboardController: {has_dc}")
        if not has_dc:
            print("DashboardController not ready. Waiting 5s...")
            await asyncio.sleep(5)
            has_dc = await page.evaluate("typeof window.DashboardController !== 'undefined'")
            print(f"After wait: {has_dc}")
            if not has_dc:
                print("Still not ready. Exiting.")
                return
        
        # Get components
        print("\nGetting components...")
        components = await page.evaluate("window.DashboardController.getComponents().then(res => res)")
        with open("/mnt/openclaw/.openclaw/workspace/bi_components_fast.json", "w") as f:
            json.dump(components, f, ensure_ascii=False, indent=2)
        
        if components.get("code") == 0:
            filters = [c for c in components["data"] if c.get("componentType") == "filter"]
            charts = [c for c in components["data"] if c.get("componentType") == "chart"]
            tabs = [c for c in components["data"] if c.get("componentType") == "tab"]
            print(f"Filters: {len(filters)}, Charts: {len(charts)}, Tabs: {len(tabs)}")
            for f in filters[:5]:
                print(f"  Filter: {f.get('componentName')} ({f.get('componentId')})")
            for c in charts[:10]:
                print(f"  Chart: {c.get('componentName')} ({c.get('componentId')})")
            for t in tabs[:5]:
                print(f"  Tab: {t.get('componentName')} ({t.get('componentId')})")
        else:
            print(f"Components error: {components.get('code')}")

asyncio.run(main())
