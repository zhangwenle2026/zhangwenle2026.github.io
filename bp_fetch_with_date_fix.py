#!/usr/bin/env python3
"""Fetch BI data with correct date range"""
import asyncio, json, urllib.request, websockets
from datetime import datetime

CDP_URL = "http://127.0.0.1:9222"
CONTROLLER_URL = "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446"
OUTPUT = "/mnt/openclaw/.openclaw/workspace/bi_raw_data.json"

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

def save_results(results):
    with open(OUTPUT, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

async def query_chart(ws, sid, cid, force=False):
    force_str = ", {force: true}" if force else ""
    res = await eval_js(ws, sid, f"""
    (async () => {{
        const res = await window.DashboardController.executeQueryAndGetCHNResult("{cid}"{force_str});
        return JSON.stringify(res);
    }})()
    """)
    return json.loads(res or '{}')

async def set_date_filter(ws, sid, filter_id, start_offset, end_offset):
    res = await eval_js(ws, sid, f"""
    (async () => {{
        const res = await window.DashboardController.setFiltersValues([{{
            "id": "{filter_id}",
            "userInput": {{
                "value": [
                    {{"offset": {start_offset}, "granularity": "DAY", "type": "OFFSET"}},
                    {{"offset": {end_offset}, "granularity": "DAY", "type": "OFFSET"}}
                ],
                "granularity": "DAY"
            }}
        }}]);
        return JSON.stringify(res);
    }})()
    """)
    return json.loads(res or '{}')

async def main():
    info = json.loads(urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=5).read())
    ws_url = info["webSocketDebuggerUrl"]

    async with websockets.connect(ws_url) as ws:
        resp = await cdp_send(ws, None, "Target.getTargets")
        targets = resp["result"]["targetInfos"]
        bi_target = next((t for t in targets if "bi.keetapp" in t.get("url","") and "300001446" in t.get("url","")), None)

        target_id = bi_target["targetId"]
        resp = await cdp_send(ws, None, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
        session_id = resp["result"]["sessionId"]
        await cdp_send(ws, session_id, "Runtime.enable")

        # Ensure we're on controller page
        current_url = await eval_js(ws, session_id, "window.location.href")
        if "dashboard-controller" not in current_url:
            await cdp_send(ws, session_id, "Page.navigate", {"url": CONTROLLER_URL})
            await asyncio.sleep(10)
            for i in range(30):
                ready = await eval_js(ws, session_id, "typeof window.DashboardController !== 'undefined'")
                if ready:
                    break
                await asyncio.sleep(1)

        # Get components
        comps_raw = await eval_js(ws, session_id, """
        (async () => {
            const res = await window.DashboardController.getComponents();
            return JSON.stringify(res);
        })()
        """)
        comps = json.loads(comps_raw or '{}')

        chart_map = {}
        filter_map = {}
        for c in comps.get('data', []):
            if c['componentType'] == 'chart':
                chart_map[c['componentName']] = c['componentId']
            elif c['componentType'] == 'filter':
                filter_map[c['componentName']] = c['componentId']

        print(f"Charts: {len(chart_map)}, Filters: {len(filter_map)}")

        results = {}

        # === Main Tab: Set date to last 10 days ===
        date_filter_id = filter_map.get('Date')
        if date_filter_id:
            print(f"Setting date filter to last 10 days...")
            res = await set_date_filter(ws, session_id, date_filter_id, -10, -1)
            print(f"  setFiltersValues: {res.get('code')} - {res.get('message', '')}")
            await asyncio.sleep(2)

        # Fetch main tab charts
        main_charts = ["Last 10 Days - Order Performance", "Last 10 days - New Signs", "Last 10 days - Promotion", "CM - Business Performance"]
        for name in main_charts:
            cid = chart_map.get(name)
            if cid:
                print(f"Fetching: {name}")
                data = await query_chart(ws, session_id, cid, force=True)
                results[name] = data
                save_results(results)
                rows = len(data.get('data', {}).get('data', [])) if data.get('code') == 0 else 0
                print(f"  {rows} rows")
                await asyncio.sleep(0.5)

        # === Operating Performance Tab ===
        print("Switching to Operating Performance...")
        await eval_js(ws, session_id, """
        (() => {
            const tabs = document.querySelectorAll('.tab-nav-item');
            for (const t of tabs) {
                const title = t.querySelector('.tab-title')?.textContent?.trim();
                if (title === 'Operating Performance') { t.click(); return true; }
            }
            return false;
        })()
        """)
        await asyncio.sleep(3)

        # Re-get components after tab switch (filters may be different)
        comps_raw2 = await eval_js(ws, session_id, """
        (async () => {
            const res = await window.DashboardController.getComponents();
            return JSON.stringify(res);
        })()
        """)
        comps2 = json.loads(comps_raw2 or '{}')
        chart_map2 = {}
        filter_map2 = {}
        for c in comps2.get('data', []):
            if c['componentType'] == 'chart':
                chart_map2[c['componentName']] = c['componentId']
            elif c['componentType'] == 'filter':
                filter_map2[c['componentName']] = c['componentId']

        date_filter2 = filter_map2.get('Date')
        if date_filter2:
            print(f"Setting OP date filter to last 10 days...")
            await set_date_filter(ws, session_id, date_filter2, -10, -1)
            await asyncio.sleep(2)

        cid = chart_map2.get("Last 10 days - Operation Performance")
        if cid:
            print("Fetching: Last 10 days - Operation Performance")
            data = await query_chart(ws, session_id, cid, force=True)
            results["Last 10 days - Operation Performance"] = data
            save_results(results)
            rows = len(data.get('data', {}).get('data', [])) if data.get('code') == 0 else 0
            print(f"  {rows} rows")

        # === User Experience Tab ===
        print("Switching to User Experience...")
        await eval_js(ws, session_id, """
        (() => {
            const tabs = document.querySelectorAll('.tab-nav-item');
            for (const t of tabs) {
                const title = t.querySelector('.tab-title')?.textContent?.trim();
                if (title === 'User Experience') { t.click(); return true; }
            }
            return false;
        })()
        """)
        await asyncio.sleep(3)

        comps_raw3 = await eval_js(ws, session_id, """
        (async () => {
            const res = await window.DashboardController.getComponents();
            return JSON.stringify(res);
        })()
        """)
        comps3 = json.loads(comps_raw3 or '{}')
        chart_map3 = {}
        filter_map3 = {}
        for c in comps3.get('data', []):
            if c['componentType'] == 'chart':
                chart_map3[c['componentName']] = c['componentId']
            elif c['componentType'] == 'filter':
                filter_map3[c['componentName']] = c['componentId']

        date_filter3 = filter_map3.get('Date')
        if date_filter3:
            print(f"Setting UX date filter to last 10 days...")
            await set_date_filter(ws, session_id, date_filter3, -10, -1)
            await asyncio.sleep(2)

        cid = chart_map3.get("Last 10 days - User Experience")
        if cid:
            print("Fetching: Last 10 days - User Experience")
            data = await query_chart(ws, session_id, cid, force=True)
            results["Last 10 days - User Experience"] = data
            save_results(results)
            rows = len(data.get('data', {}).get('data', [])) if data.get('code') == 0 else 0
            print(f"  {rows} rows")

        print(f"\n=== Done! Saved {len(results)} charts ===")
        for name, data in results.items():
            if isinstance(data, dict) and data.get('code') == 0:
                rows = data.get('data', {}).get('data', [])
                print(f"  {name}: {len(rows)} rows")

asyncio.run(main())
