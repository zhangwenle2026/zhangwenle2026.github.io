#!/usr/bin/env python3
"""Fetch BP dashboard data using CDP browser-level WS (reuse existing tab)"""
import asyncio
import json
import urllib.request
import websockets
from datetime import datetime, timedelta

CDP_HTTP = "http://localhost:9222"
DASHBOARD_URL = "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446"
OUTPUT = "/mnt/openclaw/.openclaw/workspace/bi_raw_data.json"

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

async def cdp_send(ws, sid, method, params=None):
    cmd_id = int(datetime.now().timestamp() * 1000000) % 1000000 + hash(method) % 10000
    cmd = {"id": cmd_id, "method": method, "params": params or {}}
    if sid:
        cmd["sessionId"] = sid
    await ws.send(json.dumps(cmd))
    while True:
        raw = await ws.recv()
        resp = json.loads(raw)
        if resp.get("id") == cmd_id:
            return resp

async def eval_js(ws, sid, js):
    resp = await cdp_send(ws, sid, "Runtime.evaluate", {
        "expression": js,
        "returnByValue": True,
        "awaitPromise": True
    })
    result = resp.get("result", {}).get("result", {})
    return result.get("value")

async def main():
    # Get browser-level WS URL
    info = json.loads(urllib.request.urlopen(f"{CDP_HTTP}/json/version", timeout=5).read())
    ws_url = info["webSocketDebuggerUrl"]
    print(f"Browser WS: {ws_url}")

    async with websockets.connect(ws_url) as ws:
        # Get targets
        resp = await cdp_send(ws, None, "Target.getTargets")
        targets = resp["result"]["targetInfos"]

        # Find existing BI tab
        bi_target = next((t for t in targets
                         if "bi.keetapp" in t.get("url", "")
                         and "300001446" in t.get("url", "")), None)

        if bi_target:
            target_id = bi_target["targetId"]
            print(f"Reusing existing BI tab: {target_id}")
            # Check if it needs reload (stale)
            url = bi_target.get("url", "")
            if "login" in url:
                print("ERROR: Tab is on login page, SSO expired!")
                return
        else:
            print("Creating new tab...")
            resp = await cdp_send(ws, None, "Target.createTarget", {"url": DASHBOARD_URL})
            target_id = resp["result"]["targetId"]
            await asyncio.sleep(8)

        # Attach to target
        resp = await cdp_send(ws, None, "Target.attachToTarget",
                             {"targetId": target_id, "flatten": True})
        sid = resp["result"]["sessionId"]
        await cdp_send(ws, sid, "Runtime.enable")

        # Wait for DashboardController
        print("Waiting for DashboardController...")
        for i in range(20):
            ready = await eval_js(ws, sid, "typeof window.DashboardController !== 'undefined'")
            if ready:
                print("DashboardController ready!")
                break
            await asyncio.sleep(1)
        else:
            # Check URL
            url = await eval_js(ws, sid, "window.location.href")
            print(f"Timeout. Current URL: {url}")
            return

        # Set date filters to last 10 days
        end_date = datetime.now()
        start = (end_date - timedelta(days=9)).strftime('%Y-%m-%d')
        end = end_date.strftime('%Y-%m-%d')
        print(f"Date range: {start} ~ {end}")

        filters_raw = await eval_js(ws, sid, """
        (async () => {
            const res = await window.DashboardController.getFiltersInfo();
            return JSON.stringify(res);
        })()
        """)
        filters_data = json.loads(filters_raw or '{}')

        date_filter_updates = []
        for f in filters_data.get('data', []):
            if f.get('filterType') == 'time':
                date_filter_updates.append({
                    'id': f['key'],
                    'userInput': {
                        'value': [start, end],
                        'granularity': 'DAY'
                    }
                })

        if date_filter_updates:
            set_expr = f"""
            (async () => {{
                const res = await window.DashboardController.setFiltersValues({json.dumps(date_filter_updates)});
                return JSON.stringify(res);
            }})()
            """
            set_raw = await eval_js(ws, sid, set_expr)
            set_data = json.loads(set_raw or '{}')
            print(f"Set filters: code={set_data.get('code', '?')}")
            await asyncio.sleep(3)

        # Query all charts
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
                data_raw = await eval_js(ws, sid, query_expr)
                data = json.loads(data_raw or '{}')
                results[name] = data
                rows = len(data.get('data', {}).get('data', [])) if data.get('code') == 0 else 0
                code = data.get('code', '?')
                status = 'OK' if code == 0 else f'ERR({code})'
                print(f"  -> {status}, {rows} rows")
            except Exception as e:
                print(f"  -> Exception: {e}")
                results[name] = {"code": -1, "message": str(e)}
            await asyncio.sleep(0.5)

        # Save results
        with open(OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n=== Saved to {OUTPUT} ===")
        ok_count = sum(1 for d in results.values() if d.get('code') == 0)
        total_rows = sum(len(d.get('data', {}).get('data', [])) for d in results.values() if d.get('code') == 0)
        print(f"Charts: {ok_count}/{len(TARGET_CHARTS)} OK, {total_rows} total rows")

        # Detach
        await cdp_send(ws, None, "Target.detachFromTarget", {"sessionId": sid})

if __name__ == "__main__":
    asyncio.run(main())
