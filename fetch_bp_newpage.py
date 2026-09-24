#!/usr/bin/env python3
"""Fetch BP dashboard data by creating a fresh page via CDP"""
import asyncio
import json
import urllib.request
import websockets
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

DASHBOARD_URL = "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446"
CDP_URL = "http://127.0.0.1:9222"

async def cdp_send(ws, method, params=None):
    req_id = getattr(cdp_send, 'req_id', 0) + 1
    cdp_send.req_id = req_id
    await ws.send(json.dumps({"id": req_id, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(await ws.recv())
        if msg.get("id") == req_id:
            return msg

async def fetch():
    print(f"[{datetime.now()}] Creating new page...")
    req = urllib.request.Request(f"{CDP_URL}/json/new?about:blank", method="PUT")
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    ws_url = resp["webSocketDebuggerUrl"]
    page_id = resp["id"]
    print(f"New page: {page_id}")
    
    async with websockets.connect(ws_url) as ws:
        print("Connected to page WS")
        
        # Enable runtime
        await cdp_send(ws, "Runtime.enable")
        print("Runtime enabled")
        
        # Navigate to dashboard
        print(f"Navigating to {DASHBOARD_URL}")
        nav_resp = await cdp_send(ws, "Page.navigate", {"url": DASHBOARD_URL})
        print(f"Navigation started: {nav_resp.get('result', {}).get('frameId', '?')}")
        
        # Wait for page to load
        print("Waiting for page load...")
        await asyncio.sleep(10)
        
        # Wait for DashboardController
        print("Checking DashboardController...")
        for i in range(30):
            eval_resp = await cdp_send(ws, "Runtime.evaluate", {
                "expression": "typeof window.DashboardController !== 'undefined'",
                "returnByValue": True
            })
            has_dc = eval_resp.get("result", {}).get("result", {}).get("value", False)
            if has_dc:
                print("DashboardController ready!")
                break
            await asyncio.sleep(2)
        else:
            print("DashboardController timeout")
            # Get page URL for debug
            eval_resp = await cdp_send(ws, "Runtime.evaluate", {
                "expression": "window.location.href",
                "returnByValue": True
            })
            url = eval_resp.get("result", {}).get("result", {}).get("value", "unknown")
            print(f"Current URL: {url}")
            return {}
        
        # Set date range
        end_date = datetime.now()
        start = (end_date - timedelta(days=9)).strftime('%Y-%m-%d')
        end = end_date.strftime('%Y-%m-%d')
        print(f"Date range: {start} ~ {end}")
        
        filters_expr = """
        (async () => {
            const res = await window.DashboardController.getFiltersInfo();
            return JSON.stringify(res);
        })()
        """
        eval_resp = await cdp_send(ws, "Runtime.evaluate", {
            "expression": filters_expr,
            "returnByValue": True,
            "awaitPromise": True
        })
        filters_raw = eval_resp.get("result", {}).get("result", {}).get("value", "{}")
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
            set_expr = f"""
            (async () => {{
                const res = await window.DashboardController.setFiltersValues({json.dumps(date_filter_updates)});
                return JSON.stringify(res);
            }})()
            """
            eval_resp = await cdp_send(ws, "Runtime.evaluate", {
                "expression": set_expr,
                "returnByValue": True,
                "awaitPromise": True
            })
            set_raw = eval_resp.get("result", {}).get("result", {}).get("value", "{}")
            print(f"Set filters: {json.loads(set_raw).get('code', '?')}")
            await asyncio.sleep(3)
        
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
                eval_resp = await asyncio.wait_for(
                    cdp_send(ws, "Runtime.evaluate", {
                        "expression": query_expr,
                        "returnByValue": True,
                        "awaitPromise": True
                    }),
                    timeout=45
                )
                data_raw = eval_resp.get("result", {}).get("result", {}).get("value", "{}")
                data = json.loads(data_raw)
                results[name] = data
                rows = len(data.get("data", {}).get("data", [])) if data.get("code") == 0 else 0
                print(f"  -> {'OK' if data.get('code')==0 else 'ERR'}, {rows} rows")
            except asyncio.TimeoutError:
                print(f"  -> TIMEOUT")
                results[name] = {"code": -2, "message": "timeout"}
            except Exception as e:
                print(f"  -> Exception: {e}")
                results[name] = {"code": -1, "message": str(e)}
            await asyncio.sleep(1)
        
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
