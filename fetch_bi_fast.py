#!/usr/bin/env python3
"""Fast BI data fetch - query all charts efficiently"""
import asyncio, json, urllib.request, websockets
from datetime import datetime

CDP_URL = "http://127.0.0.1:9222"
DASHBOARD_URL = "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446"

async def cdp_send(ws, session_id, method, params=None):
    cmd_id = int(datetime.now().timestamp() * 1000000) % 1000000 + hash(method) % 10000
    cmd = {"id": cmd_id, "method": method, "params": params or {}}
    if session_id:
        cmd["sessionId"] = session_id
    await ws.send(json.dumps(cmd))
    while True:
        raw = await ws.recv()
        resp = json.loads(raw)
        if resp.get("id") == cmd_id:
            return resp

async def eval_js(ws, session_id, js):
    resp = await cdp_send(ws, session_id, "Runtime.evaluate", {
        "expression": js, "returnByValue": True, "awaitPromise": True
    })
    return resp.get("result", {}).get("result", {}).get("value")

async def query_chart(ws, sid, name, cid):
    res = await eval_js(ws, sid, f"""
    (async () => {{
        const res = await window.DashboardController.executeQueryAndGetCHNResult("{cid}");
        return JSON.stringify(res);
    }})()
    """)
    data = json.loads(res or '{}')
    rows = len(data.get('data', {}).get('data', [])) if data.get('code') == 0 else 0
    if rows > 0 and isinstance(data['data']['data'][0], list):
        first = data['data']['data'][0]
        last = data['data']['data'][-1]
        print(f"  {name}: {rows} rows, first={first[:3]}, last={last[:3]}")
    else:
        print(f"  {name}: {rows} rows, code={data.get('code')}")
    return data

async def main():
    info = json.loads(urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=5).read())
    ws_url = info["webSocketDebuggerUrl"]

    async with websockets.connect(ws_url) as ws:
        # Find existing BI tab or create new
        resp = await cdp_send(ws, None, "Target.getTargets")
        targets = resp["result"]["targetInfos"]
        bi_target = next((t for t in targets if "bi.keetapp" in t.get("url","") and "300001446" in t.get("url","")), None)

        if bi_target:
            target_id = bi_target["targetId"]
            print(f"Using existing BI tab")
        else:
            resp = await cdp_send(ws, None, "Target.createTarget", {"url": DASHBOARD_URL})
            target_id = resp["result"]["targetId"]
            print(f"Created new tab")
            await asyncio.sleep(8)

        resp = await cdp_send(ws, None, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
        session_id = resp["result"]["sessionId"]
        await cdp_send(ws, session_id, "Runtime.enable")

        # Wait for DashboardController
        for i in range(15):
            ready = await eval_js(ws, session_id, "typeof window.DashboardController !== 'undefined'")
            if ready:
                print("DashboardController ready!")
                break
            await asyncio.sleep(1)
        else:
            print("Timeout waiting for DashboardController")
            return

        # Get components
        comps_raw = await eval_js(ws, session_id, """
        (async () => {
            const res = await window.DashboardController.getComponents();
            return JSON.stringify(res);
        })()
        """)
        comps = json.loads(comps_raw or '{}')

        chart_map = {}
        tab_map = {}
        for c in comps.get('data', []):
            if c['componentType'] == 'chart':
                chart_map[c['componentName']] = c['componentId']
            elif c['componentType'] == 'tab':
                tab_map[c['componentName']] = c['componentId']

        print(f"Charts: {len(chart_map)}, Tabs: {len(tab_map)}")

        results = {}

        # Query main tab charts
        main_charts = [
            "Last 10 Days - Order Performance",
            "Last 10 days - New Signs",
            "Last 10 days - Promotion",
            "CM - Business Performance",
        ]
        for name in main_charts:
            cid = chart_map.get(name)
            if cid:
                results[name] = await query_chart(ws, session_id, name, cid)
                await asyncio.sleep(0.5)

        # Switch to Operating Performance tab
        for tab_name in ['Operating Performance', 'User Experience']:
            await eval_js(ws, session_id, f"""
            (() => {{
                const tabs = document.querySelectorAll('.tab-nav-item');
                for (const t of tabs) {{
                    const title = t.querySelector('.tab-title')?.textContent?.trim();
                    if (title === '{tab_name}') {{ t.click(); return true; }}
                }}
                return false;
            }})()
            """)
            await asyncio.sleep(2)

            # Query tab-specific charts
            tab_charts = {
                'Operating Performance': ['Last 10 days - Operation Performance'],
                'User Experience': ['Last 10 days - User Experience'],
            }
            for name in tab_charts.get(tab_name, []):
                cid = chart_map.get(name)
                if cid:
                    results[name] = await query_chart(ws, session_id, name, cid)
                    await asyncio.sleep(0.5)

        # Save
        with open('/mnt/openclaw/.openclaw/workspace/bi_raw_data.json', 'w') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n=== Summary ===")
        for name, data in results.items():
            if isinstance(data, dict) and data.get('code') == 0:
                rows = data.get('data', {}).get('data', [])
                if rows and isinstance(rows[0], list):
                    dates = sorted(set(r[0] for r in rows if r and r[0]))
                    if dates:
                        print(f"  {name}: {len(rows)} rows, {dates[0]}~{dates[-1]}")
                else:
                    print(f"  {name}: {len(rows)} rows")
            else:
                print(f"  {name}: error")
        print(f"\nSaved {len(results)} charts to bi_raw_data.json")

asyncio.run(main())
