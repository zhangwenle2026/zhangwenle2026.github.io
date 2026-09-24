#!/usr/bin/env python3
"""Create new BI tab, load dashboard, click query, wait, screenshot each tab"""
import json, http.client, base64, time, asyncio, websockets, os
from datetime import datetime

CDP = ("127.0.0.1", 9222)
OUTPUT_DIR = "/mnt/openclaw/.openclaw/workspace"
TODAY = "20260918"
DASHBOARD_URL = "https://bi.keetapp.com/v2/dashboard/300001446"

async def eval_js(ws, js):
    await ws.send(json.dumps({"id": 99, "method": "Runtime.evaluate", "params": {"expression": js, "returnByValue": True, "awaitPromise": True}}))
    deadline = asyncio.get_event_loop().time() + 10
    while asyncio.get_event_loop().time() < deadline:
        try:
            r = await asyncio.wait_for(ws.recv(), timeout=1)
            msg = json.loads(r)
            if msg.get("id") == 99:
                return msg.get("result",{}).get("result",{}).get("value")
        except asyncio.TimeoutError:
            break
    return None

async def screenshot(ws, filename):
    await ws.send(json.dumps({"id": 88, "method": "Page.captureScreenshot", "params": {"format": "png", "fromSurface": True}}))
    deadline = asyncio.get_event_loop().time() + 15
    while asyncio.get_event_loop().time() < deadline:
        try:
            r = await asyncio.wait_for(ws.recv(), timeout=1)
            msg = json.loads(r)
            if msg.get("id") == 88:
                data = msg.get("result",{}).get("data","")
                if data:
                    path = os.path.join(OUTPUT_DIR, filename)
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(data))
                    print(f"  Screenshot: {path}")
                    return path
        except asyncio.TimeoutError:
            break
    return None

async def main():
    # Get browser WS
    c = http.client.HTTPConnection(*CDP)
    c.request("GET", "/json/version")
    version = json.loads(c.getresponse().read())
    browser_ws = version["webSocketDebuggerUrl"]
    
    async with websockets.connect(browser_ws) as ws:
        # Create new tab
        await ws.send(json.dumps({"id": 1, "method": "Target.createTarget", "params": {"url": DASHBOARD_URL}}))
        r = await asyncio.wait_for(ws.recv(), timeout=5)
        msg = json.loads(r)
        target_id = msg["result"]["targetId"]
        print(f"Created tab: {target_id}")
        
        # Wait for attachedToTarget event
        session_id = None
        for _ in range(10):
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=3)
                msg = json.loads(r)
                if msg.get("method") == "Target.attachedToTarget":
                    session_id = msg["params"]["sessionId"]
                    print(f"Session: {session_id}")
                    break
            except asyncio.TimeoutError:
                break
        
        if not session_id:
            print("No session received")
            return
        
        # Enable
        await ws.send(json.dumps({"id": 3, "method": "Runtime.enable", "sessionId": session_id}))
        await ws.send(json.dumps({"id": 4, "method": "Page.enable", "sessionId": session_id}))
        await asyncio.sleep(3)
        for _ in range(10):
            try: await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError: break
        
        # Wait for page to be interactive
        print("Waiting for page load...")
        await asyncio.sleep(20)
        
        # Check URL
        url = await eval_js(ws, "window.location.href")
        print(f"URL: {url}")
        
        # Click query button
        print("Clicking query...")
        clicked = await eval_js(ws, """
        (() => {
            const btns = document.querySelectorAll('button, .ant-btn, [role="button"]');
            for (const b of btns) {
                const txt = b.textContent || b.innerText || '';
                if (txt.includes('查询') || txt.includes('Query') || txt.includes('搜')) {
                    b.click();
                    return 'clicked: ' + txt.slice(0, 20);
                }
            }
            return 'not found';
        })()
        """)
        print(f"  {clicked}")
        
        # Wait for data to load
        print("Waiting 60s for data...")
        await asyncio.sleep(60)
        
        # Screenshot Business Performance tab
        print("Screenshot: Business Performance")
        await screenshot(ws, f"dbr_bp_{TODAY}.png")
        
        # Find and click sub-tabs
        tabs_info = await eval_js(ws, """
        (() => {
            const tabs = document.querySelectorAll('.tab-nav-item, .ant-tabs-tab, [role="tab"]');
            return Array.from(tabs).map((t,i) => ({
                index: i,
                text: (t.textContent || t.innerText || '').trim().slice(0, 30),
                active: t.classList.contains('active-tab') || t.classList.contains('ant-tabs-tab-active')
            }));
        })()
        """)
        print(f"Tabs: {tabs_info}")
        
        # Click each tab and screenshot
        if tabs_info:
            for tab in tabs_info:
                idx = tab.get('index', 0)
                text = tab.get('text', '')
                if tab.get('active'):
                    continue  # Already screenshot
                
                print(f"Clicking tab {idx}: {text}")
                await eval_js(ws, f"""
                (() => {{
                    const tabs = document.querySelectorAll('.tab-nav-item, .ant-tabs-tab, [role="tab"]');
                    if ({idx} < tabs.length) {{
                        tabs[{idx}].click();
                        return 'clicked';
                    }}
                    return 'not found';
                }})()
                """)
                
                await asyncio.sleep(15)
                safe_name = text.replace(' ', '_').replace('/', '_')[:20] or f"tab{idx}"
                await screenshot(ws, f"dbr_{safe_name}_{TODAY}.png")
        
        # Close tab
        await ws.send(json.dumps({"id": 50, "method": "Target.closeTarget", "params": {"targetId": target_id}}))
        print("Done")

asyncio.run(main())
