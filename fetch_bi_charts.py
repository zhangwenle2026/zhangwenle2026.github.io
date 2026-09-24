import asyncio
import json
from playwright.async_api import async_playwright

CHARTS_TO_QUERY = [
    ("CM - Business Performance", "chart-6kwer-1357d"),
    ("Last 10 Days - Order Performance", "dashboard-chart-container-7p18g-b0ef9"),
    ("Last 10 days - New Signs", "chart-e8ns5-c9347"),
    ("CM - Promotion", "chart-0xw88-29243"),
    ("Last 10 days - Promotion", "chart-iyhbp-a03a1"),
    ("Last 10 days - User Experience", "chart-ltuz6-6cbdc"),
    ("Main Metrics", "dashboard-chart-container-ga9na-72528"),
    ("Performance (RM - CM Level)", "dashboard-chart-container-8wn9t-b35f3"),
    ("CM - Operating Merchants", "chart-xu3l7-21399"),
    ("Last 10 days - Operation Performance", "chart-sqalg-1f515"),
]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        contexts = browser.contexts
        page = contexts[0].pages[0]
        
        # Verify we're on the controller page
        print(f"Current: {page.url}")
        if "dashboard-controller" not in page.url:
            print("Need to navigate to controller page...")
            await page.goto(
                "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446",
                wait_until="networkidle", timeout=60000
            )
            await page.wait_for_function("window.DashboardController !== undefined", timeout=30000)
        
        print("DashboardController ready, querying charts...")
        
        results = {}
        for name, chart_id in CHARTS_TO_QUERY:
            print(f"\n--- Querying: {name} ({chart_id}) ---")
            try:
                # Execute query and get result
                data = await page.evaluate(
                    f'window.DashboardController.executeQueryAndGetCHNResult("{chart_id}").then(res => res)'
                )
                results[name] = data
                # Print summary
                if isinstance(data, dict) and data.get("code") == 0:
                    d = data.get("data", {})
                    if isinstance(d, dict):
                        titles = d.get("titles", [])
                        rows = d.get("data", [])
                        print(f"  OK: {len(titles)} cols, {len(rows)} rows")
                        if titles:
                            print(f"  Columns: {[t.get('name','') for t in titles[:10]]}")
                        if rows:
                            print(f"  First row: {rows[0][:8] if isinstance(rows[0], list) else rows[0]}")
                    elif isinstance(d, list):
                        print(f"  OK: list with {len(d)} items")
                else:
                    print(f"  Response: {json.dumps(data, ensure_ascii=False)[:200]}")
            except Exception as e:
                print(f"  ERROR: {e}")
                results[name] = {"error": str(e)}
        
        # Save all results
        output_path = "/mnt/openclaw/.openclaw/workspace/bi_raw_data.json"
        with open(output_path, "w") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n\nAll data saved to {output_path}")

asyncio.run(main())
