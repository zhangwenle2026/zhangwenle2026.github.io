#!/usr/bin/env python3
"""Check dashboard filters"""
import asyncio, json, urllib.request, websockets
from datetime import datetime

CDP_URL = "http://127.0.0.1:9222"

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

        # Get components to find filter IDs
        comps_raw = await eval_js(ws, session_id, """
        (async () => {
            const res = await window.DashboardController.getComponents();
            return JSON.stringify(res);
        })()
        """)
        comps = json.loads(comps_raw or '{}')

        filters = [c for c in comps.get('data', []) if c['componentType'] == 'filter']
        print(f"Found {len(filters)} filters")
        for f in filters:
            print(f"  - {f['componentName']} ({f['componentId'][:30]}...)")

        if filters:
            filter_ids = [f['componentId'] for f in filters]
            filters_info = await eval_js(ws, session_id, f"""
            (async () => {{
                const res = await window.DashboardController.getFiltersInfo({json.dumps(filter_ids)});
                return JSON.stringify(res);
            }})()
            """)
            info = json.loads(filters_info or '{}')
            print(f"\nFilter info code: {info.get('code')}")
            for fi in info.get('data', []):
                print(f"\nFilter: {fi.get('name')}")
                print(f"  Type: {fi.get('filterType')}")
                print(f"  Value: {json.dumps(fi.get('filterValue'), ensure_ascii=False)}")

asyncio.run(main())
