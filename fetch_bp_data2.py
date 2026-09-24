#!/usr/bin/env python3
"""Fetch Business Platform dashboard data via CDP + Playwright - optimized"""
import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from playwright.async_api import async_playwright

DASHBOARD_ID = 300001446
TARGET_CHARTS = [
    ("CM - Business Performance", "chart-6kwer-1357d"),
    ("BDM - Business Performance", "chart-stq7y-e6570"),
    ("BD - Business Performance", "dashboard-chart-container-fgaiv-e51fa"),
    ("SMB - MTD Merchant Ranking", "chart-budz2-630e8"),
    ("Last 10 Days - Order Performance", "dashboard-chart-container-7p18g-b0ef9"),
    ("Last 10 days - New Signs", "chart-e8ns5-c9347"),
    ("Last 10 days - Operation Performance", "chart-sqalg-1f515"),
    ("Last 10 days - User Experience", "chart-ltuz6-6cbdc"),
    ("Last 10 days - Promotion", "chart-iyhbp-a03a1"),
]

CDP_URL = "http://127.0.0.1:9222"
CONTROLLER_URL = f"https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId={DASHBOARD_ID}"

async def fetch():
    print(f"[{datetime.now()}] Starting fetch")
    playwright = await async_playwright().start()
    try:
        import urllib.request
        version = json.loads(urllib.request.urlopen(CDP_URL + "/json/version", timeout=5).read())
        browser = await playwright.chromium.connect_over_cdp(version["webSocketDebuggerUrl"])
        context = browser.contexts[0]
        page = await context.new_page()
        print(f"Navigating...")
        await page.goto(CONTROLLER_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)

        # Wait for controller
        for i in range(30):
            if await page.evaluate("() => typeof window.DashboardController !== 'undefined'"):
                print("Controller ready")
                break
            await asyncio.sleep(1)
        else:
            print("Controller timeout")
            return {}

        # Set date filters to get latest data (2026-07-23)
        # Find date filter IDs
        filters_res = await page.evaluate("""
            async () => {
                const res = await window.DashboardController.getFiltersInfo();
                return JSON.stringify(res);
            }
        """)
        filters_data = json.loads(filters_res)
        print(f"Filters: {json.dumps(filters_data.get('data', []), indent=2)[:500]}")

        # Set all date filters to BRT today (last 10 days)
        end_date = datetime.now()
        start = (end_date - timedelta(days=9)).strftime('%Y-%m-%d')
        end = end_date.strftime('%Y-%m-%d')
        date_filter_updates = []
        for f in filters_data.get("data", []):
            if f.get("filterType") == "time":
                date_filter_updates.append({
                    "id": f["key"],
                    "userInput": {
                        "value": [start, end],
                        "granularity": "DAY"
                    }
                })

        if date_filter_updates:
            print(f"Setting {len(date_filter_updates)} date filters to {start} ~ {end}")
            set_res = await page.evaluate(f"""
                async () => {{
                    const res = await window.DashboardController.setFiltersValues({json.dumps(date_filter_updates)});
                    return JSON.stringify(res);
                }}
            """)
            print(f"Set filters result: {set_res}")
            await asyncio.sleep(2)

        results = {}
        for name, cid in TARGET_CHARTS:
            print(f"Querying: {name}")
            try:
                res = await asyncio.wait_for(
                    page.evaluate(f"""
                        async () => {{
                            const res = await window.DashboardController.executeQueryAndGetCHNResult(['{cid}'], {{force: true}});
                            return JSON.stringify(res);
                        }}
                    """),
                    timeout=45
                )
                data = json.loads(res)
                results[name] = data
                rows = len(data.get("data", {}).get("data", [])) if data.get("code") == 0 else 0
                print(f"  -> {'OK' if data.get('code')==0 else 'ERR'}, {rows} rows")
            except asyncio.TimeoutError:
                print(f"  -> TIMEOUT after 45s")
                results[name] = {"code": -2, "message": "timeout", "data": {"data": [], "columns": []}}
            except Exception as e:
                print(f"  -> Exception: {e}")
                results[name] = {"code": -1, "message": str(e), "data": {"data": [], "columns": []}}
            await asyncio.sleep(0.3)

        await page.close()
        return results
    finally:
        await playwright.stop()

async def main():
    results = await fetch()
    output_path = Path("/mnt/openclaw/.openclaw/workspace/bi_raw_data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(results)} charts to {output_path}")
    for name, data in results.items():
        status = "OK" if data.get("code") == 0 else f"ERR({data.get('code')})"
        rows = len(data.get("data", {}).get("data", [])) if data.get("code") == 0 else 0
        print(f"  {name}: {status}, {rows} rows")

if __name__ == "__main__":
    asyncio.run(main())
