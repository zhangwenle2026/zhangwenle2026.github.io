#!/usr/bin/env python3
"""Fetch BI data via CDP network interception"""
import asyncio, json, urllib.request, websockets
from datetime import datetime
import http.client

CDP_URL = "http://127.0.0.1:9222"
DASHBOARD_URL = "https://bi.keetapp.com/v2/dashboard/300001446"

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
    print(f"Browser: {ws_url[:50]}...")

    async with websockets.connect(ws_url) as ws:
        # Create new tab
        resp = await cdp_send(ws, None, "Target.createTarget", {"url": DASHBOARD_URL})
        target_id = resp["result"]["targetId"]
        print(f"Created new tab: {target_id}")
        await asyncio.sleep(10)

        resp = await cdp_send(ws, None, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
        session_id = resp["result"]["sessionId"]
        print(f"Session: {session_id}")

        await cdp_send(ws, session_id, "Runtime.enable")
        await cdp_send(ws, session_id, "Network.enable")

        # Capture network responses
        captured = {}
        
        async def capture():
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1)
                    msg = json.loads(raw)
                    if msg.get("method") == "Network.responseReceived":
                        url = msg.get("params",{}).get("response",{}).get("url","")
                        if "keetapp" in url and ("query" in url or "data" in url or "chart" in url or "api" in url):
                            print(f"Network: {url[:100]}")
                    elif msg.get("method") == "Network.loadingFinished":
                        req_id = msg.get("params",{}).get("requestId","")
                        try:
                            body_resp = await cdp_send(ws, session_id, "Network.getResponseBody", {"requestId": req_id})
                            body = body_resp.get("result",{}).get("body","")
                            if body and len(body) > 500:
                                try:
                                    data = json.loads(body)
                                    if isinstance(data, dict) and ("data" in data or "result" in data):
                                        key = req_id[:10]
                                        captured[key] = {"size": len(body), "preview": str(data)[:200]}
                                        print(f"Captured {key}: {len(body)} bytes")
                                except:
                                    pass
                        except Exception as e:
                            pass
                except asyncio.TimeoutError:
                    break

        # Wait for page to load
        await asyncio.sleep(20)
        await capture()

        # Click query button
        print("\nClicking query button...")
        clicked = await eval_js(ws, session_id, """
        (() => {
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                if (b.textContent.includes('查询') || b.textContent.includes('Query')) {
                    b.click();
                    return true;
                }
            }
            return false;
        })()
        """)
        print(f"Clicked: {clicked}")

        await asyncio.sleep(30)
        await capture()

        # Check page
        url = await eval_js(ws, session_id, "window.location.href")
        title = await eval_js(ws, session_id, "document.title")
        print(f"\nPage: {title} | {url}")

        # Save captured data
        with open("/mnt/openclaw/.openclaw/workspace/dbr_network_captured.json", "w") as f:
            json.dump(captured, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(captured)} captures")

        # Close
        await cdp_send(ws, None, "Target.closeTarget", {"targetId": target_id})

asyncio.run(main())
