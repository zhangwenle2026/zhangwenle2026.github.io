import asyncio
import json
from playwright.async_api import async_playwright

DASHBOARD_ID = "300001446"
HOST = "bi.keetapp.com"
CONTROLLER_URL = f"https://{HOST}/v2/dashboard/dashboard-controller?dashboardId={DASHBOARD_ID}"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        contexts = browser.contexts
        if not contexts:
            print("ERROR: No browser contexts")
            return
        
        page = contexts[0].pages[0]
        print(f"Current: {page.url}")
        
        # Navigate to controller page
        print(f"Navigating to controller: {CONTROLLER_URL}")
        await page.goto(CONTROLLER_URL, wait_until="networkidle", timeout=60000)
        print(f"Navigated: {page.url}")
        
        # Wait for DashboardController
        print("Waiting for DashboardController...")
        await page.wait_for_function("window.DashboardController !== undefined", timeout=30000)
        print("DashboardController ready!")
        
        # Step 1: Get all components
        print("\n=== Getting components ===")
        components = await page.evaluate("window.DashboardController.getComponents().then(res => res)")
        print(json.dumps(components, ensure_ascii=False, indent=2)[:3000])
        
        # Save components for analysis
        with open("/mnt/openclaw/.openclaw/workspace/bi_components.json", "w") as f:
            json.dump(components, f, ensure_ascii=False, indent=2)
        
        # Step 2: Get filters info
        print("\n=== Getting filters ===")
        # First find filter IDs
        if components.get("code") == 0:
            filters = [c for c in components["data"] if c.get("componentType") == "filter"]
            charts = [c for c in components["data"] if c.get("componentType") == "chart"]
            tabs = [c for c in components["data"] if c.get("componentType") == "tab"]
            
            print(f"Found {len(filters)} filters, {len(charts)} charts, {len(tabs)} tabs")
            print("\nFilters:")
            for f_item in filters:
                print(f"  - {f_item.get('componentName')} ({f_item.get('componentId')})")
            print("\nCharts:")
            for c_item in charts[:20]:
                print(f"  - {c_item.get('componentName')} ({c_item.get('componentId')})")
            print("\nTabs:")
            for t_item in tabs:
                print(f"  - {t_item.get('componentName')} ({t_item.get('componentId')})")
                children = t_item.get("childrenComponents", [])
                if children:
                    print(f"    Children: {children[:5]}")
            
            # Get filter values
            if filters:
                filter_ids = [f_item["componentId"] for f_item in filters]
                filter_info = await page.evaluate(
                    f'window.DashboardController.getFiltersInfo({json.dumps(filter_ids)}).then(res => res)'
                )
                print("\nFilter values:")
                print(json.dumps(filter_info, ensure_ascii=False, indent=2)[:2000])
                
                with open("/mnt/openclaw/.openclaw/workspace/bi_filters.json", "w") as f:
                    json.dump(filter_info, f, ensure_ascii=False, indent=2)

asyncio.run(main())
