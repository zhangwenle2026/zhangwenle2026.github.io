#!/usr/bin/env python3
"""Check BI page visual state via CDP"""
import asyncio
import json
import urllib.request
import websockets

CDP_HTTP = "http://localhost:9222"
TARGET_ID = "E2A43146D6A56C04A0CAA6A454EA4C5A"

async def cdp_send(ws, sid, method, params=None):
    cmd_id = int(asyncio.get_event_loop().time() * 1000000) % 1000000
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
    info = json.loads(urllib.request.urlopen(f"{CDP_HTTP}/json/version", timeout=5).read())
    ws_url = info["webSocketDebuggerUrl"]
    async with websockets.connect(ws_url) as ws:
        resp = await cdp_send(ws, None, "Target.attachToTarget",
                             {"targetId": TARGET_ID, "flatten": True})
        sid = resp["result"]["sessionId"]
        await cdp_send(ws, sid, "Runtime.enable")
        await cdp_send(ws, sid, "Page.enable")

        # Take a screenshot to see visual state
        await cdp_send(ws, sid, "Page.captureScreenshot")
        # Wait for screenshot
        for _ in range(10):
            raw = await asyncio.wait_for(ws.recv(), timeout=2)
            resp = json.loads(raw)
            if resp.get("method") == "Page.screencastFrame":
                print("Got screencast frame")
                break
            if "result" in resp and "data" in resp.get("result", {}):
                print("Got screenshot data")
                break

        # Check page dimensions
        dims = await eval_js(ws, sid, """
            JSON.stringify({
                width: document.documentElement.scrollWidth,
                height: document.documentElement.scrollHeight,
                bodyHeight: document.body.scrollHeight,
                innerWidth: window.innerWidth,
                innerHeight: window.innerHeight
            })
        """)
        print(f"Page dims: {dims}")

        # Check visible content
        content_check = await eval_js(ws, sid, """
            JSON.stringify({
                appExists: document.querySelector('#app') !== null,
                appChildren: document.querySelector('#app')?.children?.length || 0,
                dashboardContainers: document.querySelectorAll('.dashboard-container, .dashboard-content, .vgl-layout').length,
                loadingSpinners: document.querySelectorAll('.ant-spin, .loading, .ant-skeleton').length,
                errorMessages: Array.from(document.querySelectorAll('*')).filter(e => 
                    e.textContent && (e.textContent.includes('error') || e.textContent.includes('Error') || e.textContent.includes('failed'))
                ).length
            })
        """)
        print(f"Content check: {content_check}")

        # Try scrolling to trigger lazy loading
        print("Scrolling to trigger rendering...")
        await eval_js(ws, sid, "window.scrollTo(0, 0)")
        await asyncio.sleep(2)
        await eval_js(ws, sid, "window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)
        await eval_js(ws, sid, "window.scrollTo(0, 0)")
        await asyncio.sleep(2)

        # Check again
        charts_after = await eval_js(ws, sid, "document.querySelectorAll('[id^=\"chart-\"]').length")
        print(f"Charts after scroll: {charts_after}")

        await cdp_send(ws, None, "Target.detachFromTarget", {"sessionId": sid})

asyncio.run(main())
