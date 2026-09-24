#!/usr/bin/env python3
"""Diagnostic: check controller page state"""
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

        # Page state
        url = await eval_js(ws, session_id, "window.location.href")
        print(f"URL: {url}")

        # Wait a bit for any async loading
        await asyncio.sleep(5)

        # Check body
        body_text = await eval_js(ws, session_id, "document.body ? document.body.innerText.substring(0,800) : 'NO BODY'")
        print(f"Body: {body_text}")

        # Check for loading indicators
        loading = await eval_js(ws, session_id, "document.querySelectorAll('.loading, .spin, .ant-spin').length")
        print(f"Loading spinners: {loading}")

        # Check DashboardController
        dc_type = await eval_js(ws, session_id, "typeof window.DashboardController")
        print(f"DashboardController type: {dc_type}")

        if dc_type == 'object':
            # Try getComponents
            comps_raw = await eval_js(ws, session_id, """
            (async () => {
                const res = await window.DashboardController.getComponents();
                return JSON.stringify(res);
            })()
            """)
            comps = json.loads(comps_raw or '{}')
            print(f"getComponents code: {comps.get('code')}")

            # Try executeQueryAndGetCHNResult on first chart
            charts = [c for c in comps.get('data', []) if c['componentType'] == 'chart']
            if charts:
                first_chart = charts[0]
                print(f"Testing chart: {first_chart['componentName']} ({first_chart['componentId'][:20]}...)")

                res = await eval_js(ws, session_id, f"""
                (async () => {{
                    const res = await window.DashboardController.executeQueryAndGetCHNResult("{first_chart['componentId']}");
                    return JSON.stringify(res);
                }})()
                """)
                data = json.loads(res or '{}')
                print(f"Query result code: {data.get('code')}")
                print(f"Query result keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
                inner = data.get('data', {})
                print(f"Inner data keys: {list(inner.keys()) if isinstance(inner, dict) else 'N/A'}")
                rows = inner.get('data', [])
                print(f"Rows: {len(rows)}")
                if rows:
                    print(f"First row: {rows[0]}")

                # Try with force
                print("Trying with force...")
                res2 = await eval_js(ws, session_id, f"""
                (async () => {{
                    const res = await window.DashboardController.executeQueryAndGetCHNResult("{first_chart['componentId']}", {{force: true}});
                    return JSON.stringify(res);
                }})()
                """)
                data2 = json.loads(res2 or '{}')
                rows2 = data2.get('data', {}).get('data', [])
                print(f"Force query rows: {len(rows2)}")

asyncio.run(main())
