import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        
        # Create a new context and page for clean state
        context = browser.contexts[0]
        page = await context.new_page()
        
        print("Loading dashboard page...")
        await page.goto(
            "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446",
            wait_until="networkidle", timeout=90000
        )
        
        # Wait extra time for all charts to stabilize
        await page.wait_for_function("window.DashboardController !== undefined", timeout=60000)
        print("DashboardController ready!")
        
        # Wait additional 5s for charts to finish initial loading
        await asyncio.sleep(5)
        
        # Load existing data
        with open("/mnt/openclaw/.openclaw/workspace/bi_raw_data.json", "r") as f:
            results = json.load(f)
        
        # Query Operation Performance with 180s timeout
        print("Querying: Last 10 days - Operation Performance...")
        try:
            data = await asyncio.wait_for(
                page.evaluate(
                    'window.DashboardController.executeQueryAndGetCHNResult("chart-sqalg-1f515").then(res => res)'
                ),
                timeout=180
            )
            results["Last 10 days - Operation Performance"] = data
            if isinstance(data, dict) and data.get("code") == 0:
                rows = data.get("data", {}).get("data", [])
                print(f"  -> {len(rows)} rows")
                for r in rows[:3]:
                    print(f"     {r}")
            else:
                print(f"  -> code={data.get('code')}, msg={data.get('message')}")
        except asyncio.TimeoutError:
            print("  -> TIMEOUT (180s)")
            results["Last 10 days - Operation Performance"] = {"error": "timeout_180s"}
        except Exception as e:
            print(f"  -> ERROR: {e}")
        
        with open("/mnt/openclaw/.openclaw/workspace/bi_raw_data.json", "w") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("Done! Data saved.")
        
        await page.close()

asyncio.run(main())
