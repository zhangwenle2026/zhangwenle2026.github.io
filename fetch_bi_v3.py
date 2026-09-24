import asyncio
import json
from playwright.async_api import async_playwright

DASHBOARD_ID = "300001446"
HOST = "bi.keetapp.com"
CONTROLLER_URL = f"https://{HOST}/v2/dashboard/dashboard-controller?dashboardId={DASHBOARD_ID}"

# Charts we need
CHARTS = {
    "Last 10 days - New Signs": "chart-e8ns5-c9347",
    "Last 10 Days - Order Performance": "dashboard-chart-container-7p18g-b0ef9",
    "Last 10 days - Promotion": "chart-iyhbp-a03a1",
    "Last 10 days - Operation Performance": "chart-sqalg-1f515",
    "Last 10 days - User Experience": "chart-ltuz6-6cbdc",
    "CM - Business Performance": "chart-6kwer-1357d",
}

TAB_IDS = {
    "Operating Performance": "childTab-s99jd-be3dd",
    "Total Coverage": "tab-pane-vrlaw-cd1f4",
    "User Experience": "childTab-3cpk9-01e57",
}

async def query_chart(page, name, chart_id, timeout_sec=60):
    """Query a single chart with retry on timeout."""
    for attempt in range(2):
        try:
            print(f"Querying: {name} (attempt {attempt+1})...")
            data = await asyncio.wait_for(
                page.evaluate(
                    f'window.DashboardController.executeQueryAndGetCHNResult("{chart_id}").then(res => res)'
                ),
                timeout=timeout_sec
            )
            if isinstance(data, dict) and data.get("code") == 0:
                rows = data.get("data", {}).get("data", [])
                print(f"  -> {len(rows)} rows")
                return data
            else:
                print(f"  -> code={data.get('code') if isinstance(data, dict) else 'unknown'}")
                return data
        except asyncio.TimeoutError:
            print(f"  -> TIMEOUT (attempt {attempt+1})")
            if attempt == 0:
                await asyncio.sleep(3)
            else:
                return {"error": "timeout", "code": -1}
        except Exception as e:
            print(f"  -> ERROR: {e}")
            return {"error": str(e), "code": -1}

async def switch_tab(page, tab_id):
    """Switch to a tab by ID."""
    try:
        print(f"Switching to tab {tab_id}...")
        await page.evaluate(
            f'window.DashboardController.setTabActive("{tab_id}").then(res => res)'
        )
        await asyncio.sleep(2)
        return True
    except Exception as e:
        print(f"  Tab switch error: {e}")
        return False

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        contexts = browser.contexts
        page = contexts[0].pages[0]
        
        if "dashboard-controller" not in page.url:
            await page.goto(CONTROLLER_URL, wait_until="networkidle", timeout=60000)
        
        await page.wait_for_function("window.DashboardController !== undefined", timeout=30000)
        print("DashboardController ready!\n")
        
        results = {}
        
        # Charts that don't need tab switching
        for name, chart_id in [
            ("Last 10 days - New Signs", CHARTS["Last 10 days - New Signs"]),
            ("Last 10 Days - Order Performance", CHARTS["Last 10 Days - Order Performance"]),
            ("Last 10 days - Promotion", CHARTS["Last 10 days - Promotion"]),
            ("CM - Business Performance", CHARTS["CM - Business Performance"]),
        ]:
            results[name] = await query_chart(page, name, chart_id, timeout_sec=60)
        
        # Operation Performance - switch tab first
        await switch_tab(page, TAB_IDS["Operating Performance"])
        results["Last 10 days - Operation Performance"] = await query_chart(
            page, "Last 10 days - Operation Performance", 
            CHARTS["Last 10 days - Operation Performance"], timeout_sec=90
        )
        
        # User Experience - switch tab first  
        await switch_tab(page, TAB_IDS["User Experience"])
        results["Last 10 days - User Experience"] = await query_chart(
            page, "Last 10 days - User Experience",
            CHARTS["Last 10 days - User Experience"], timeout_sec=90
        )
        
        with open("/mnt/openclaw/.openclaw/workspace/bi_raw_data.json", "w") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print("\n=== Summary ===")
        for name, data in results.items():
            if isinstance(data, dict) and data.get("code") == 0:
                rows = data.get("data", {}).get("data", [])
                print(f"  {name}: {len(rows)} rows")
            elif "error" in data:
                print(f"  {name}: ERROR - {data['error']}")
            else:
                print(f"  {name}: code={data.get('code')}")
        print("\nDone! Data saved.")

asyncio.run(main())
