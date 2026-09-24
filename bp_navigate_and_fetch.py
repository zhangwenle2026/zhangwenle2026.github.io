#!/usr/bin/env python3
"""Navigate BI tab to controller page and fetch data"""
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

async def query_and_save(ws, sid, results, name, cid):
    res = await eval_js(ws, sid, f"""
    (async () => {{
        const res = await window.DashboardController.executeQueryAndGetCHNResult("{cid}");
        return JSON.stringify(res);
    }})()
    """)
    data = json.loads(res or '{}')
    results[name] = data
    save_results(results)
    rows = len(data.get('data', {}).get('data', [])) if data.get('code') == 0 else 0
    print(f"  {name}: {rows} rows, code={data.get('code')}")
    return data

async def main():
    info = json.loads(urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=5).read())
    ws_url = info["webSocketDebuggerUrl"]
    print(f"Browser: {ws_url[:50]}...")

    async with websockets.connect(ws_url) as ws:
        resp = await cdp_send(ws, None, "Target.getTargets")
        targets = resp["result"]["targetInfos"]
        bi_target = next((t for t in targets if "bi.keetapp" in t.get("url","") and "300001446" in t.get("url","")), None)

        if not bi_target:
            print("No BI tab found")
            return

        target_id = bi_target["targetId"]
        print(f"Found tab: {bi_target['url']}")

        resp = await cdp_send(ws, None, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
        session_id = resp["result"]["sessionId"]
        await cdp_send(ws, session_id, "Runtime.enable")

        # Navigate to controller page
        current_url = await eval_js(ws, session_id, "window.location.href")
        print(f"Current URL: {current_url}")

        if "dashboard-controller" not in current_url:
            print("Navigating to controller page...")
            await cdp_send(ws, session_id, "Page.navigate", {"url": CONTROLLER_URL})
            await asyncio.sleep(10)
        else:
            print("Already on controller page")

        # Wait for DashboardController
        for i in range(30):
            ready = await eval_js(ws, session_id, "typeof window.DashboardController !== 'undefined'")
            if ready:
                print(f"DashboardController ready after {i+1}s")
                break
            await asyncio.sleep(1)
        else:
            print("DashboardController timeout")
            return

        # Get components
        comps_raw = await eval_js(ws, session_id, """
        (async () => {
            const res = await window.DashboardController.getComponents();
            return JSON.stringify(res);
        })()
        """)
        comps = json.loads(comps_raw or '{}')

        if comps.get('code') != 0:
            print(f"getComponents failed: {comps}")
            return

        chart_map = {}
        for c in comps.get('data', []):
            if c['componentType'] == 'chart':
                chart_map[c['componentName']] = c['componentId']
            elif c['componentType'] == 'tab':
                print(f"  Tab: {c['componentName']}")

        print(f"Found {len(chart_map)} charts")
        for name in chart_map:
            print(f"  - {name}")

        results = {}

        # Fetch main tab charts
        main_charts = ["Last 10 Days - Order Performance", "Last 10 days - New Signs", "Last 10 days - Promotion", "CM - Business Performance"]
        for name in main_charts:
            cid = chart_map.get(name)
            if cid:
                await query_and_save(ws, session_id, results, name, cid)
                await asyncio.sleep(0.5)
            else:
                print(f"  ⚠️ Chart not found: {name}")

        # Operating Performance tab
        print("Switching to Operating Performance tab...")
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
        cid = chart_map.get("Last 10 days - Operation Performance")
        if cid:
            await query_and_save(ws, session_id, results, "Last 10 days - Operation Performance", cid)

        # User Experience tab
        print("Switching to User Experience tab...")
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
        cid = chart_map.get("Last 10 days - User Experience")
        if cid:
            await query_and_save(ws, session_id, results, "Last 10 days - User Experience", cid)

        print(f"\n=== Done! Saved {len(results)} charts ===")
        for name, data in results.items():
            if isinstance(data, dict) and data.get('code') == 0:
                rows = data.get('data', {}).get('data', [])
                print(f"  {name}: {len(rows)} rows")

asyncio.run(main())
