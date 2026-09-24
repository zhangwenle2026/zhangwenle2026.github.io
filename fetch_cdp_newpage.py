import asyncio
import json
from playwright.async_api import async_playwright

async def fetch_via_cdp():
    async with async_playwright() as p:
        print("Connecting to CDP at 127.0.0.1:9222...")
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        print(f"Connected! Contexts: {len(browser.contexts)}")
        
        # Use a new page to avoid any hanging pages
        context = browser.contexts[0]
        print(f"Context pages: {len(context.pages)}")
        
        page = await context.new_page()
        print("New page created")
        
        # Navigate to the BI dashboard
        url = "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446"
        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="networkidle", timeout=90000)
        print(f"Page loaded: {page.url}")
        
        # Wait for DashboardController
        print("Waiting for DashboardController...")
        await page.wait_for_function(
            "() => typeof window.DashboardController !== 'undefined'",
            timeout=30000
        )
        print("DashboardController is ready!")
        
        # Query charts
        CHARTS = [
            ("Last 10 days - New Signs", "chart-e8ns5-c9347"),
            ("Last 10 Days - Order Performance", "dashboard-chart-container-7p18g-b0ef9"),
            ("Last 10 days - Promotion", "chart-iyhbp-a03a1"),
            ("Last 10 days - Operation Performance", "chart-sqalg-1f515"),
            ("Last 10 days - User Experience", "chart-ltuz6-6cbdc"),
            ("CM - Business Performance", "chart-6kwer-1357d"),
        ]
        
        results = {}
        for name, chart_id in CHARTS:
            print(f"\nQuerying: {name} ({chart_id})...")
            try:
                data = await asyncio.wait_for(
                    page.evaluate(
                        f'window.DashboardController.executeQueryAndGetCHNResult("{chart_id}").then(res => res)'
                    ),
                    timeout=45
                )
                results[name] = data
                if isinstance(data, dict) and data.get("code") == 0:
                    d = data.get("data", {})
                    rows = d.get("data", []) if isinstance(d, dict) else []
                    print(f"  -> OK: {len(rows)} rows")
                else:
                    print(f"  -> Response: {json.dumps(data, ensure_ascii=False)[:200]}")
            except asyncio.TimeoutError:
                print(f"  -> TIMEOUT")
                results[name] = {"error": "timeout"}
            except Exception as e:
                print(f"  -> ERROR: {e}")
                results[name] = {"error": str(e)}
        
        # Save results
        output_path = "/mnt/openclaw/.openclaw/workspace/bi_raw_data.json"
        with open(output_path, "w") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nData saved to {output_path}")
        
        await page.close()
        await browser.close()

asyncio.run(fetch_via_cdp())
