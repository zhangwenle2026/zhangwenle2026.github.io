#!/usr/bin/env python3
"""Check BI page status via CDP"""
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

        url = await eval_js(ws, sid, "window.location.href")
        print(f"URL: {url}")

        title = await eval_js(ws, sid, "document.title")
        print(f"Title: {title}")

        ready = await eval_js(ws, sid, "typeof window.DashboardController !== 'undefined'")
        print(f"DashboardController ready: {ready}")

        # Check for loading indicators
        loading = await eval_js(ws, sid, """
            document.querySelector('.ant-spin-dot, .loading, .ant-skeleton') !== null
        """)
        print(f"Loading indicators present: {loading}")

        # Check for error messages
        errors = await eval_js(ws, sid, """
            Array.from(document.querySelectorAll('*')).filter(e =>
                e.textContent && (e.textContent.includes('暂无数据') ||
                e.textContent.includes('无数据') ||
                e.textContent.includes('error') ||
                e.textContent.includes('Error'))
            ).map(e => e.textContent.trim()).slice(0, 5)
        """)
        print(f"Error/no-data messages: {errors}")

        # Check chart containers
        charts = await eval_js(ws, sid, """
            document.querySelectorAll('[id^="chart-"], [id^="dashboard-chart-container-"]').length
        """)
        print(f"Chart containers found: {charts}")

        # Get current filter values
        filters = await eval_js(ws, sid, """
            (async () => {
                if (!window.DashboardController) return null;
                const res = await window.DashboardController.getFiltersInfo();
                return JSON.stringify(res);
            })()
        """)
        print(f"Filters: {filters[:500] if filters else 'N/A'}...")

        await cdp_send(ws, None, "Target.detachFromTarget", {"sessionId": sid})

asyncio.run(main())
