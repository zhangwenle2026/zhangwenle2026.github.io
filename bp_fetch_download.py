#!/usr/bin/env python3
"""Fetch BI data using executeDownload"""
import asyncio, json, urllib.request, websockets
from datetime import datetime

CDP_URL = "http://127.0.0.1:9222"
CONTROLLER_URL = "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446"
OUTPUT_DIR = "/mnt/openclaw/.openclaw/workspace"

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

        # Navigate to controller page
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
        for c in comps.get('data', []):
            if c['componentType'] == 'chart':
                chart_map[c['componentName']] = c['componentId']

        print(f"Found {len(chart_map)} charts")

        # Test executeDownload on a few charts
        test_charts = [
            "Last 10 Days - Order Performance",
            "CM - Business Performance",
            "Last 10 days - New Signs",
        ]

        for name in test_charts:
            cid = chart_map.get(name)
            if not cid:
                print(f"⚠️ Not found: {name}")
                continue

            print(f"\nTesting download: {name} ({cid[:30]}...)")

            # First trigger query
            print("  Triggering query...")
            res = await eval_js(ws, session_id, f"""
            (async () => {{
                const res = await window.DashboardController.executeQueryAndGetCHNResult("{cid}");
                return JSON.stringify({{code: res.code, message: res.message}});
            }})()
            """)
            print(f"  Query result: {res}")
            await asyncio.sleep(2)

            # Then download
            print("  Getting download link...")
            dl = await eval_js(ws, session_id, f"""
            (async () => {{
                const res = await window.DashboardController.executeDownload("{cid}", {{fileType: "CSV"}});
                return JSON.stringify(res);
            }})()
            """)
            print(f"  Download result: {dl}")

asyncio.run(main())
