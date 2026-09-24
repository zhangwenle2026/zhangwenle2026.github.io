#!/usr/bin/env python3
"""Fetch BP dashboard data using existing logged-in page via CDP"""
import asyncio
import json
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

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

async def fetch():
    print(f"[{datetime.now()}] Connecting to CDP...")
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0] if browser.contexts else None
        if not context:
            print("No browser context found")
            return {}
        
        # Find page with BI dashboard
        target_page = None
        for page in context.pages:
            if "dashboard-controller" in page.url and "300001446" in page.url:
                target_page = page
                print(f"Found existing page: {page.url}")
                break
        
        if not target_page:
            print("No existing BI page found, using first page")
            target_page = context.pages[0] if context.pages else None
            if not target_page:
                print("No pages at all")
                return {}
        
        # Wait for DashboardController
        for i in range(20):
            has_dc = await target_page.evaluate("typeof window.DashboardController !== 'undefined'")
            if has_dc:
                print("DashboardController ready")
                break
            await asyncio.sleep(1)
        else:
            print("DashboardController not available")
            return {}
        
        # Set date range to last 10 days
        end_date = datetime.now()
        start = (end_date - timedelta(days=9)).strftime('%Y-%m-%d')
        end = end_date.strftime('%Y-%m-%d')
        print(f"Setting date range: {start} ~ {end}")
        
        filters_res = await target_page.evaluate("""
            async () => {
                const res = await window.DashboardController.getFiltersInfo();
                return JSON.stringify(res);
            }
        """)
        filters_data = json.loads(filters_res)
        
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
            set_res = await target_page.evaluate(f"""
                async () => {{
                    const res = await window.DashboardController.setFiltersValues({json.dumps(date_filter_updates)});
                    return JSON.stringify(res);
                }}
            """)
            print(f"Set filters: {json.loads(set_res).get('code', '?')}")
            await asyncio.sleep(2)
        
        results = {}
        for name, cid in TARGET_CHARTS:
            print(f"Querying: {name}")
            try:
                res = await asyncio.wait_for(
                    target_page.evaluate(f"""
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
                print(f"  -> TIMEOUT")
                results[name] = {"code": -2, "message": "timeout", "data": {"data": [], "columns": []}}
            except Exception as e:
                print(f"  -> Exception: {e}")
                results[name] = {"code": -1, "message": str(e), "data": {"data": [], "columns": []}}
            await asyncio.sleep(0.5)
        
        return results

async def main():
    results = await fetch()
    output_path = "/mnt/openclaw/.openclaw/workspace/bi_raw_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {output_path}")
    for name, data in results.items():
        status = "OK" if data.get("code") == 0 else f"ERR({data.get('code')})"
        rows = len(data.get("data", {}).get("data", [])) if data.get("code") == 0 else 0
        print(f"  {name}: {status}, {rows} rows")

if __name__ == "__main__":
    asyncio.run(main())
