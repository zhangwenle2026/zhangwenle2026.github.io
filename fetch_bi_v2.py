import asyncio
import json
from playwright.async_api import async_playwright

# Priority charts - most important first
CHARTS = [
    ("Last 10 days - New Signs", "chart-e8ns5-c9347"),
    ("Last 10 Days - Order Performance", "dashboard-chart-container-7p18g-b0ef9"),
    ("Last 10 days - Promotion", "chart-iyhbp-a03a1"),
    ("Last 10 days - Operation Performance", "chart-sqalg-1f515"),
]

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
        
        results = {}
        for name, chart_id in CHARTS:
            print(f"Querying: {name}...")
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
                    print(f"  -> {len(rows)} rows")
                    for r in rows[:3]:
                        print(f"     {r}")
            except asyncio.TimeoutError:
                print(f"  -> TIMEOUT")
                results[name] = {"error": "timeout"}
            except Exception as e:
                print(f"  -> ERROR: {e}")
                results[name] = {"error": str(e)}
        
        # Now try User Experience separately with longer timeout
        print("Querying: Last 10 days - User Experience...")
        try:
            data = await asyncio.wait_for(
                page.evaluate(
                    'window.DashboardController.executeQueryAndGetCHNResult("chart-ltuz6-6cbdc").then(res => res)'
                ),
                timeout=60
            )
            results["Last 10 days - User Experience"] = data
            if isinstance(data, dict) and data.get("code") == 0:
                rows = data.get("data", {}).get("data", [])
                print(f"  -> {len(rows)} rows")
                for r in rows[:3]:
                    print(f"     {r}")
        except asyncio.TimeoutError:
            print("  -> TIMEOUT")
            results["Last 10 days - User Experience"] = {"error": "timeout"}
        except Exception as e:
            print(f"  -> ERROR: {e}")
        
        # Try CM-level data
        print("Querying: CM - Business Performance...")
        try:
            data = await asyncio.wait_for(
                page.evaluate(
                    'window.DashboardController.executeQueryAndGetCHNResult("chart-6kwer-1357d").then(res => res)'
                ),
                timeout=45
            )
            results["CM - Business Performance"] = data
            if isinstance(data, dict) and data.get("code") == 0:
                rows = data.get("data", {}).get("data", [])
                print(f"  -> {len(rows)} rows")
                for r in rows[:5]:
                    print(f"     {r}")
        except asyncio.TimeoutError:
            print("  -> TIMEOUT")
            results["CM - Business Performance"] = {"error": "timeout"}
        except Exception as e:
            print(f"  -> ERROR: {e}")
        
        with open("/mnt/openclaw/.openclaw/workspace/bi_raw_data.json", "w") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("\nDone! Data saved.")

asyncio.run(main())
