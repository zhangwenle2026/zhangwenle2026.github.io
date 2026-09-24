#!/usr/bin/env python3
"""Diagnostic for BI dashboard fetch"""
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
    print(f"Browser WS: {ws_url[:60]}...")

    async with websockets.connect(ws_url) as ws:
        resp = await cdp_send(ws, None, "Target.getTargets")
        targets = resp["result"]["targetInfos"]
        bi_target = next((t for t in targets if "bi.keetapp" in t.get("url","") and "300001446" in t.get("url","")), None)

        if not bi_target:
            print("❌ No BI tab found")
            return

        print(f"Found BI tab: {bi_target['title']}")
        print(f"URL: {bi_target['url']}")

        target_id = bi_target["targetId"]
        resp = await cdp_send(ws, None, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
        session_id = resp["result"]["sessionId"]
        await cdp_send(ws, session_id, "Runtime.enable")

        # Check page state
        url = await eval_js(ws, session_id, "window.location.href")
        title = await eval_js(ws, session_id, "document.title")
        print(f"Page URL: {url}")
        print(f"Page title: {title}")

        # Check if logged in
        has_login = await eval_js(ws, session_id, "document.querySelector('input[type=password]') !== null")
        print(f"Has login form: {has_login}")

        # Check DashboardController
        for i in range(20):
            ready = await eval_js(ws, session_id, "typeof window.DashboardController !== 'undefined'")
            if ready:
                print(f"✅ DashboardController ready after {i+1}s")
                break
            await asyncio.sleep(1)
        else:
            print("❌ DashboardController timeout")
            return

        # Try getComponents
        comps_raw = await eval_js(ws, session_id, """
        (async () => {
            const res = await window.DashboardController.getComponents();
            return JSON.stringify(res);
        })()
        """)
        comps = json.loads(comps_raw or '{}')
        if comps.get('code') == 0:
            charts = [c['componentName'] for c in comps.get('data',[]) if c['componentType'] == 'chart']
            tabs = [c['componentName'] for c in comps.get('data',[]) if c['componentType'] == 'tab']
            print(f"Charts: {len(charts)}")
            print(f"Tabs: {len(tabs)}")
            for c in charts:
                print(f"  - {c}")
            for t in tabs:
                print(f"  [Tab] {t}")
        else:
            print(f"❌ getComponents failed: {comps}")

asyncio.run(main())
