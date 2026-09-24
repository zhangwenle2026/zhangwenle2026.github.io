#!/usr/bin/env python3
"""Check what's actually on the BI page"""
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

        if not bi_target:
            print("No BI tab")
            return

        target_id = bi_target["targetId"]
        resp = await cdp_send(ws, None, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
        session_id = resp["result"]["sessionId"]
        await cdp_send(ws, session_id, "Runtime.enable")

        # Page state
        url = await eval_js(ws, session_id, "window.location.href")
        print(f"URL: {url}")

        # Check body text for clues
        body_text = await eval_js(ws, session_id, "document.body ? document.body.innerText.substring(0,500) : 'NO BODY'")
        print(f"Body text (first 500 chars): {body_text}")

        # Check for common loading/auth indicators
        checks = [
            ("Loading spinner", "document.querySelector('.loading') !== null"),
            ("Skeleton screen", "document.querySelector('.skeleton') !== null"),
            ("Login form", "document.querySelector('input[type=password]') !== null"),
            ("SSO redirect", "document.body.innerText.includes('redirect')"),
            ("Error page", "document.body.innerText.includes('error') || document.body.innerText.includes('Error')"),
            ("Dashboard container", "document.querySelector('.dashboard-container') !== null"),
            ("App root", "document.querySelector('#app') !== null"),
            ("Has scripts", "document.querySelectorAll('script').length"),
        ]
        for name, js in checks:
            val = await eval_js(ws, session_id, js)
            print(f"  {name}: {val}")

        # Check network state
        has_dc = await eval_js(ws, session_id, "typeof window.DashboardController")
        print(f"DashboardController type: {has_dc}")

asyncio.run(main())
