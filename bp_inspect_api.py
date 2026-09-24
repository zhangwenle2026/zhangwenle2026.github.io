#!/usr/bin/env python3
"""Inspect DashboardController API"""
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

        # List all methods on DashboardController
        methods = await eval_js(ws, session_id, "Object.keys(window.DashboardController)")
        print(f"DashboardController methods: {methods}")

        # Check if there's a ready state
        ready = await eval_js(ws, session_id, "window.DashboardController.ready")
        print(f"ready: {ready}")

        # Try getting a chart's data via different approaches
        comps_raw = await eval_js(ws, session_id, """
        (async () => {
            const res = await window.DashboardController.getComponents();
            return JSON.stringify(res);
        })()
        """)
        comps = json.loads(comps_raw or '{}')
        charts = [c for c in comps.get('data', []) if c['componentType'] == 'chart']
        if charts:
            cid = charts[0]['componentId']
            cname = charts[0]['componentName']
            print(f"\nTesting chart: {cname}")

            # Try executeQueryAndGetCHNResult without awaitPromise (fire and forget, then wait)
            print("\n1. Fire query without awaitPromise, wait 5s, then check...")
            await cdp_send(ws, session_id, "Runtime.evaluate", {
                "expression": f"window.DashboardController.executeQueryAndGetCHNResult('{cid}')",
                "returnByValue": False,
                "awaitPromise": False
            })
            await asyncio.sleep(5)

            # Check if data appeared somewhere
            has_data = await eval_js(ws, session_id, f"""
            (() => {{
                // Check various places data might be stored
                const dc = window.DashboardController;
                const results = [];
                if (dc._queryResults) results.push('_queryResults keys: ' + Object.keys(dc._queryResults || {{}}).length);
                if (dc.queryResults) results.push('queryResults keys: ' + Object.keys(dc.queryResults || {{}}).length);
                if (dc._results) results.push('_results keys: ' + Object.keys(dc._results || {{}}).length);
                return results.join(' | ');
            }})()
            """)
            print(f"  Storage check: {has_data}")

            # Try again with awaitPromise and check response more carefully
            print("\n2. Query with awaitPromise...")
            res = await eval_js(ws, session_id, f"""
            (async () => {{
                const res = await window.DashboardController.executeQueryAndGetCHNResult("{cid}");
                return JSON.stringify({{
                    code: res.code,
                    hasData: !!res.data,
                    dataKeys: res.data ? Object.keys(res.data) : [],
                    rowCount: res.data && res.data.data ? res.data.data.length : 0,
                    columns: res.data && res.data.columns ? res.data.columns : [],
                    message: res.message
                }});
            }})()
            """)
            print(f"  Result: {res}")

            # Try executeDownload
            print("\n3. Try executeDownload...")
            dl = await eval_js(ws, session_id, f"""
            (async () => {{
                const res = await window.DashboardController.executeDownload("{cid}", {{fileType: "CSV"}});
                return JSON.stringify(res);
            }})()
            """)
            print(f"  Download result: {dl}")

asyncio.run(main())
