import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        contexts = browser.contexts
        page = contexts[0].pages[0]
        
        if "dashboard-controller" not in page.url:
            await page.goto(
                "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446",
                wait_until="networkidle", timeout=60000
            )
        await page.wait_for_function("window.DashboardController !== undefined", timeout=30000)
        print("Ready!")
        
        # Load existing data
        with open("/mnt/openclaw/.openclaw/workspace/bi_raw_data.json", "r") as f:
            results = json.load(f)
        
        # Retry Operation Performance with 120s timeout
        print("Querying: Last 10 days - Operation Performance...")
        try:
            data = await asyncio.wait_for(
                page.evaluate(
                    'window.DashboardController.executeQueryAndGetCHNResult("chart-sqalg-1f515").then(res => res)'
                ),
                timeout=120
            )
            results["Last 10 days - Operation Performance"] = data
            if isinstance(data, dict) and data.get("code") == 0:
                rows = data.get("data", {}).get("data", [])
                print(f"  -> {len(rows)} rows")
                for r in rows[:3]:
                    print(f"     {r}")
            else:
                print(f"  -> code={data.get('code')}")
        except asyncio.TimeoutError:
            print("  -> TIMEOUT")
            results["Last 10 days - Operation Performance"] = {"error": "timeout"}
        except Exception as e:
            print(f"  -> ERROR: {e}")
        
        # Retry User Experience with 90s timeout
        print("Querying: Last 10 days - User Experience...")
        try:
            data = await asyncio.wait_for(
                page.evaluate(
                    'window.DashboardController.executeQueryAndGetCHNResult("chart-ltuz6-6cbdc").then(res => res)'
                ),
                timeout=90
            )
            results["Last 10 days - User Experience"] = data
            if isinstance(data, dict) and data.get("code") == 0:
                rows = data.get("data", {}).get("data", [])
                print(f"  -> {len(rows)} rows")
                for r in rows[:3]:
                    print(f"     {r}")
            else:
                print(f"  -> code={data.get('code')}")
        except asyncio.TimeoutError:
            print("  -> TIMEOUT")
            results["Last 10 days - User Experience"] = {"error": "timeout"}
        except Exception as e:
            print(f"  -> ERROR: {e}")
        
        with open("/mnt/openclaw/.openclaw/workspace/bi_raw_data.json", "w") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("\nDone! Data saved.")

asyncio.run(main())
