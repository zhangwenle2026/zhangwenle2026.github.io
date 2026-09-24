#!/usr/bin/env python3
"""BP Dashboard fetch fix - manually scroll all tabs and trigger charts"""
import asyncio
import json
import urllib.request
import websockets
from datetime import datetime

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

async def eval_js(ws, sid, js, await_promise=True):
    resp = await cdp_send(ws, sid, "Runtime.evaluate", {
        "expression": js,
        "returnByValue": True,
        "awaitPromise": await_promise
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
        
        # Get all tabs
        tabs = await eval_js(ws, sid, """
            Array.from(document.querySelectorAll('.tab-nav-item')).map((t, i) => ({
                index: i,
                title: t.querySelector('.tab-title')?.textContent?.trim() || '',
                active: t.classList.contains('active-tab')
            }))
        """)
        print(f"Tabs: {json.dumps(tabs, ensure_ascii=False)}")
        
        # Click each tab and wait
        for tab_info in tabs:
            idx = tab_info['index']
            title = tab_info['title']
            print(f"\nClicking tab {idx}: {title}")
            
            await eval_js(ws, sid, f"""
                (() => {{
                    const tabs = document.querySelectorAll('.tab-nav-item');
                    if (tabs[{idx}]) {{
                        tabs[{idx}].click();
                        return 'clicked';
                    }}
                    return 'not found';
                }})()
            "", await_promise=False)
            
            await asyncio.sleep(5)
            
            # Scroll to all charts
            charts = await eval_js(ws, sid, """
                (() => {
                    const charts = document.querySelectorAll('.chart-edit-view');
                    charts.forEach(c => c.scrollIntoView({behavior: 'instant', block: 'center'}));
                    return charts.length;
                })()
            """, await_promise=False)
            print(f"  Scrolled {charts} charts")
            
            await asyncio.sleep(3)
            
            # Check if any data loaded
            chart_ids = await eval_js(ws, sid, """
                Array.from(document.querySelectorAll('[id^="chart-"], [id^="dashboard-chart-container-"]')).map(e => e.id)
            """)
            print(f"  Chart IDs found: {chart_ids[:10] if chart_ids else 'none'}")
        
        await cdp_send(ws, None, "Target.detachFromTarget", {"sessionId": sid})

asyncio.run(main())
