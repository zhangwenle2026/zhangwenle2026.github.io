#!/usr/bin/env python3
"""Fetch BP dashboard data using direct CDP HTTP API"""
import json
import urllib.request
import time
from datetime import datetime, timedelta

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
DASHBOARD_URL = "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446"

def cdp_send(page_ws_url, method, params=None):
    """Send CDP command via WebSocket using curl"""
    import subprocess
    cmd = {
        "id": int(time.time() * 1000) % 100000,
        "method": method,
        "params": params or {}
    }
    ws_cmd = f'echo \'{json.dumps(cmd)}\' | websocat -1 - "{page_ws_url}"'
    result = subprocess.run(ws_cmd, shell=True, capture_output=True, text=True, timeout=30)
    if result.returncode == 0 and result.stdout:
        return json.loads(result.stdout)
    return {"error": result.stderr}

def cdp_eval(page_ws_url, expression, await_promise=False):
    """Evaluate expression on page"""
    result = cdp_send(page_ws_url, "Runtime.evaluate", {
        "expression": expression,
        "returnByValue": True,
        "awaitPromise": await_promise
    })
    return result

def fetch():
    print(f"[{datetime.now()}] Creating new page...")
    req = urllib.request.Request(f"{CDP_URL}/json/new?about:blank", method="PUT")
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    page_id = resp["id"]
    ws_url = resp["webSocketDebuggerUrl"]
    print(f"New page: {page_id}")
    print(f"WS URL: {ws_url[:60]}...")
    
    # Check if websocat exists
    import shutil
    if not shutil.which("websocat"):
        print("websocat not found, trying alternative...")
        return fetch_with_playwright()
    
    # Enable runtime
    print("Enabling Runtime...")
    cdp_send(ws_url, "Runtime.enable")
    time.sleep(1)
    
    # Navigate
    print(f"Navigating to dashboard...")
    cdp_send(ws_url, "Page.navigate", {"url": DASHBOARD_URL})
    
    # Wait for load
    print("Waiting 15s for page load...")
    time.sleep(15)
    
    # Check DashboardController
    print("Checking DashboardController...")
    for i in range(20):
        result = cdp_eval(ws_url, "typeof window.DashboardController !== 'undefined'")
        has_dc = result.get("result", {}).get("result", {}).get("value", False)
        if has_dc:
            print("DashboardController ready!")
            break
        time.sleep(2)
    else:
        print("DashboardController timeout")
        result = cdp_eval(ws_url, "window.location.href")
        print(f"Current URL: {result}")
        return {}
    
    # Set date filters
    end_date = datetime.now()
    start = (end_date - timedelta(days=9)).strftime('%Y-%m-%d')
    end = end_date.strftime('%Y-%m-%d')
    print(f"Date range: {start} ~ {end}")
    
    filters_result = cdp_eval(ws_url, """
    (async () => {
        const res = await window.DashboardController.getFiltersInfo();
        return JSON.stringify(res);
    })()
    """, await_promise=True)
    filters_raw = filters_result.get("result", {}).get("result", {}).get("value", "{}")
    filters_data = json.loads(filters_raw)
    
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
        set_result = cdp_eval(ws_url, f"""
        (async () => {{
            const res = await window.DashboardController.setFiltersValues({json.dumps(date_filter_updates)});
            return JSON.stringify(res);
        }})()
        """, await_promise=True)
        set_raw = set_result.get("result", {}).get("result", {}).get("value", "{}")
        print(f"Set filters: {json.loads(set_raw).get('code', '?')}")
        time.sleep(3)
    
    results = {}
    for name, cid in TARGET_CHARTS:
        print(f"Querying: {name}")
        try:
            query_expr = f"""
            (async () => {{
                const res = await window.DashboardController.executeQueryAndGetCHNResult(['{cid}'], {{force: true}});
                return JSON.stringify(res);
            }})()
            """
            result = cdp_eval(ws_url, query_expr, await_promise=True)
            data_raw = result.get("result", {}).get("result", {}).get("value", "{}")
            data = json.loads(data_raw)
            results[name] = data
            rows = len(data.get("data", {}).get("data", [])) if data.get("code") == 0 else 0
            print(f"  -> {'OK' if data.get('code')==0 else 'ERR'}, {rows} rows")
        except Exception as e:
            print(f"  -> Exception: {e}")
            results[name] = {"code": -1, "message": str(e)}
        time.sleep(1)
    
    return results

def fetch_with_playwright():
    """Fallback to playwright if websocat not available"""
    import asyncio
    from playwright.async_api import async_playwright
    
    async def _fetch():
        print("Using Playwright fallback...")
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0]
            page = await context.new_page()
            
            print("Navigating...")
            await page.goto(DASHBOARD_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)
            
            for i in range(30):
                ready = await page.evaluate("typeof window.DashboardController !== 'undefined'")
                if ready:
                    print("DashboardController ready!")
                    break
                await asyncio.sleep(1)
            else:
                print("Timeout")
                return {}
            
            end_date = datetime.now()
            start = (end_date - timedelta(days=9)).strftime('%Y-%m-%d')
            end = end_date.strftime('%Y-%m-%d')
            
            filters_res = await page.evaluate("""
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
                await page.evaluate(f"""
                    async () => {{
                        await window.DashboardController.setFiltersValues({json.dumps(date_filter_updates)});
                    }}
                """)
                await asyncio.sleep(3)
            
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
                    print(f"  -> TIMEOUT")
                    results[name] = {"code": -2, "message": "timeout"}
                await asyncio.sleep(0.5)
            
            await page.close()
            return results
    
    return asyncio.run(_fetch())

def main():
    results = fetch()
    output_path = "/mnt/openclaw/.openclaw/workspace/bi_raw_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {output_path}")
    for name, data in results.items():
        status = "OK" if data.get("code") == 0 else f"ERR({data.get('code')})"
        rows = len(data.get("data", {}).get("data", [])) if data.get("code") == 0 else 0
        print(f"  {name}: {status}, {rows} rows")

if __name__ == "__main__":
    main()
