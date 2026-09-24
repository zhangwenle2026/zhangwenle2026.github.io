#!/usr/bin/env python3
"""Fetch BP dashboard data using CDP browser-level WS (per skill spec)"""
import asyncio
import json
import urllib.request
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

CDP_HTTP = "http://127.0.0.1:9222"
DASHBOARD_URL = "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446"

async def cdp_send(ws, session_id, method, params=None, req_id=None):
    cmd = {
        "id": req_id or int(asyncio.get_event_loop().time() * 1000) % 100000,
        "sessionId": session_id,
        "method": method,
        "params": params or {}
    }
    await ws.send(json.dumps(cmd))
    resp = json.loads(await ws.recv())
    return resp

async def eval_js(ws, session_id, js_code):
    resp = await cdp_send(ws, session_id, "Runtime.evaluate", {
        "expression": js_code,
        "returnByValue": True,
        "awaitPromise": True
    })
    result = resp.get("result", {}).get("result", {})
    if result.get("type") == "string":
        return result.get("value", "")
    return result.get("value")

async def fetch():
    print(f"[{datetime.now()}] Getting browser WS URL...")
    info = json.loads(urllib.request.urlopen(f"{CDP_HTTP}/json/version", timeout=5).read())
    ws_url = info["webSocketDebuggerUrl"]
    print(f"Browser WS: {ws_url[:60]}...")
    
    import websockets
    async with websockets.connect(ws_url) as ws:
        # Get targets
        resp = await cdp_send(ws, None, "Target.getTargets", req_id=1)
        targets = resp.get("result", {}).get("targetInfos", [])
        print(f"Found {len(targets)} targets")
        
        # Find or create BI page
        bi_target = None
        for t in targets:
            if "bi.keetapp" in t.get("url", "") and "300001446" in t.get("url", ""):
                bi_target = t
                print(f"Found existing BI page: {t['targetId']}")
                break
        
        if bi_target:
            target_id = bi_target["targetId"]
        else:
            # Create new target
            print("Creating new target...")
            resp = await cdp_send(ws, None, "Target.createTarget", {"url": "about:blank"}, req_id=2)
            target_id = resp.get("result", {}).get("targetId")
            print(f"New target: {target_id}")
        
        # Attach to target
        print("Attaching to target...")
        resp = await cdp_send(ws, None, "Target.attachToTarget", {"targetId": target_id, "flatten": True}, req_id=3)
        session_id = resp.get("result", {}).get("sessionId")
        print(f"Session: {session_id}")
        
        # Enable domains
        await cdp_send(ws, session_id, "Runtime.enable", req_id=4)
        await cdp_send(ws, session_id, "Page.enable", req_id=5)
        
        # Navigate to dashboard
        print(f"Navigating to dashboard...")
        await cdp_send(ws, session_id, "Page.navigate", {"url": DASHBOARD_URL}, req_id=6)
        
        # Wait for load
        print("Waiting 15s for page load...")
        await asyncio.sleep(15)
        
        # Check DashboardController
        print("Checking DashboardController...")
        for i in range(20):
            has_dc = await eval_js(ws, session_id, "typeof window.DashboardController !== 'undefined'")
            if has_dc:
                print("DashboardController ready!")
                break
            await asyncio.sleep(2)
        else:
            print("DashboardController timeout")
            url = await eval_js(ws, session_id, "window.location.href")
            print(f"Current URL: {url}")
            return {}
        
        # Set date filters
        end_date = datetime.now()
        start = (end_date - timedelta(days=9)).strftime('%Y-%m-%d')
        end = end_date.strftime('%Y-%m-%d')
        print(f"Date range: {start} ~ {end}")
        
        filters_raw = await eval_js(ws, session_id, """
        (async () => {
            const res = await window.DashboardController.getFiltersInfo();
            return JSON.stringify(res);
        })()
        """)
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
            set_raw = await eval_js(ws, session_id, f"""
            (async () => {{
                const res = await window.DashboardController.setFiltersValues({json.dumps(date_filter_updates)});
                return JSON.stringify(res);
            }})()
            """)
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
                data_raw = await asyncio.wait_for(
                    eval_js(ws, session_id, query_expr),
                    timeout=45
                )
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
