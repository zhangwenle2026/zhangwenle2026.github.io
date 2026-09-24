#!/usr/bin/env python3
"""Fetch BP dashboard data using direct CDP WebSocket"""
import asyncio
import json
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

WS_URL = "ws://127.0.0.1:9222/devtools/page/47DD593784802B11FBF1348C3410BFF8"

async def send_cmd(ws, method, params=None):
    cmd = {"id": 1, "method": method, "params": params or {}}
    await ws.send(json.dumps(cmd))
    resp = await ws.recv()
    return json.loads(resp)

async def evaluate(ws, expression):
    # Enable runtime first
    await send_cmd(ws, "Runtime.enable")
    result = await send_cmd(ws, "Runtime.evaluate", {
        "expression": expression,
        "returnByValue": True,
        "awaitPromise": True
    })
    return result

async def fetch():
    print(f"[{datetime.now()}] Connecting to page WS...")
    async with websockets.connect(WS_URL) as ws:
        print("Connected, enabling Runtime...")
        await send_cmd(ws, "Runtime.enable")
        
        # Check DashboardController
        print("Checking DashboardController...")
        res = await evaluate(ws, "typeof window.DashboardController !== 'undefined'")
        has_dc = res.get("result", {}).get("result", {}).get("value", False)
        print(f"DashboardController: {has_dc}")
        
        if not has_dc:
            print("Not available, waiting...")
            for i in range(10):
                await asyncio.sleep(2)
                res = await evaluate(ws, "typeof window.DashboardController !== 'undefined'")
                has_dc = res.get("result", {}).get("result", {}).get("value", False)
                if has_dc:
                    break
            if not has_dc:
                print("Still not available")
                return {}
        
        # Set date filters
        end_date = datetime.now()
        start = (end_date - timedelta(days=9)).strftime('%Y-%m-%d')
        end = end_date.strftime('%Y-%m-%d')
        print(f"Setting date range: {start} ~ {end}")
        
        # Get filters info
        filters_expr = """
        (async () => {
            const res = await window.DashboardController.getFiltersInfo();
            return JSON.stringify(res);
        })()
        """
        res = await evaluate(ws, filters_expr)
        filters_raw = res.get("result", {}).get("result", {}).get("value", "{}")
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
            res = await evaluate(ws, set_expr)
            set_raw = res.get("result", {}).get("result", {}).get("value", "{}")
            print(f"Set filters: {json.loads(set_raw).get('code', '?')}")
            await asyncio.sleep(3)
        
        results = {}
        for name, cid in TARGET_CHARTS:
            print(f"Querying: {name}")
            query_expr = f"""
            (async () => {{
                const res = await window.DashboardController.executeQueryAndGetCHNResult(['{cid}'], {{force: true}});
                return JSON.stringify(res);
            }})()
            """
            try:
                res = await asyncio.wait_for(evaluate(ws, query_expr), timeout=45)
                data_raw = res.get("result", {}).get("result", {}).get("value", "{}")
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
