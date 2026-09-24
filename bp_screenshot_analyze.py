#!/usr/bin/env python3
"""Take screenshots of each tab and analyze them"""
import asyncio, json, urllib.request, websockets, base64
from datetime import datetime

CDP_URL = "http://127.0.0.1:9222"
DASHBOARD_URL = "https://bi.keetapp.com/v2/dashboard/300001446"
OUTPUT_DIR = "/mnt/openclaw/.openclaw/workspace/screenshots"

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

async def screenshot(ws, session_id, path):
    resp = await cdp_send(ws, session_id, "Page.captureScreenshot", {"format": "png"})
    data = base64.b64decode(resp["result"]["data"])
    with open(path, "wb") as f:
        f.write(data)
    return path

async def main():
    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    info = json.loads(urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=5).read())
    ws_url = info["webSocketDebuggerUrl"]

    async with websockets.connect(ws_url) as ws:
        # Create new tab
        resp = await cdp_send(ws, None, "Target.createTarget", {"url": DASHBOARD_URL})
        target_id = resp["result"]["targetId"]
        print(f"Created tab: {target_id}")
        await asyncio.sleep(10)

        resp = await cdp_send(ws, None, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
        session_id = resp["result"]["sessionId"]
        await cdp_send(ws, session_id, "Runtime.enable")
        await cdp_send(ws, session_id, "Page.enable")

        # Wait for charts
        for i in range(30):
            has_charts = await eval_js(ws, session_id, "document.querySelectorAll('.chart-edit-view, .mobile-layout-item').length > 0")
            if has_charts:
                print(f"Dashboard loaded after {i+1}s")
                break
            await asyncio.sleep(1)

        # Get tabs
        tabs = await eval_js(ws, session_id, """
        (() => {
            const tabs = document.querySelectorAll('.tab-nav-item');
            return Array.from(tabs).map((t, i) => ({
                index: i,
                title: t.querySelector('.tab-title')?.textContent?.trim() || ''
            }));
        })()
        """)

        print(f"Tabs: {len(tabs) if tabs else 0}")

        # Screenshot each tab
        for tab_info in (tabs or []):
            tab_title = tab_info['title']
            tab_idx = tab_info['index']

            # Click tab
            await eval_js(ws, session_id, f"""
            (() => {{
                const tabs = document.querySelectorAll('.tab-nav-item');
                if ({tab_idx} < tabs.length) tabs[{tab_idx}].click();
            }})()
            """)
            await asyncio.sleep(5)

            # Scroll down to load all charts
            for _ in range(5):
                await eval_js(ws, session_id, "window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)

            # Screenshot
            safe_name = tab_title.replace(' ', '_').replace('/', '_')
            path = f"{OUTPUT_DIR}/tab_{tab_idx}_{safe_name}.png"
            await screenshot(ws, session_id, path)
            print(f"  Screenshot: {path}")

        # Close tab
        await cdp_send(ws, None, "Target.closeTarget", {"targetId": target_id})
        print("Done!")

asyncio.run(main())
