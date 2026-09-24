#!/usr/bin/env python3
"""Intercept BI dashboard API calls via CDP to capture chart data"""
import asyncio, json, urllib.request, websockets
from datetime import datetime

CDP_URL = "http://127.0.0.1:9222"
DASHBOARD_URL = "https://bi.keetapp.com/v2/dashboard/300001446"
OUTPUT = "/mnt/openclaw/.openclaw/workspace/bi_raw_data.json"

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

def save_results(results):
    with open(OUTPUT, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

async def main():
    info = json.loads(urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=5).read())
    ws_url = info["webSocketDebuggerUrl"]
    print(f"Browser: {ws_url[:50]}...")

    async with websockets.connect(ws_url) as ws:
        # Create a new tab
        resp = await cdp_send(ws, None, "Target.createTarget", {"url": DASHBOARD_URL})
        target_id = resp["result"]["targetId"]
        print(f"Created new tab: {target_id}")
        await asyncio.sleep(8)

        resp = await cdp_send(ws, None, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
        session_id = resp["result"]["sessionId"]

        # Enable Runtime, Network, and Fetch domains
        await cdp_send(ws, session_id, "Runtime.enable")
        await cdp_send(ws, session_id, "Network.enable")

        captured_responses = {}

        # Define chart lid mapping based on known chart names
        # We'll capture ALL /data API responses and map them later

        # Wait for page load
        for i in range(30):
            loaded = await eval_js(ws, session_id, "document.readyState")
            if loaded == "complete":
                print(f"Page loaded after {i+1}s")
                break
            await asyncio.sleep(1)

        # Give time for initial API calls
        await asyncio.sleep(5)

        # Get tabs info
        tabs_info = await eval_js(ws, session_id, """
        (() => {
            const tabs = document.querySelectorAll('.tab-nav-item');
            return Array.from(tabs).map((t, i) => ({
                index: i,
                title: t.querySelector('.tab-title')?.textContent?.trim() || ''
            }));
        })()
        """)
        print(f"Tabs: {len(tabs_info) if tabs_info else 0}")
        for t in (tabs_info or []):
            print(f"  [{t['index']}] {t['title']}")

        # Click through each tab to trigger API calls
        # We'll listen for network responses
        for tab_info in (tabs_info or []):
            tab_title = tab_info['title']
            tab_idx = tab_info['index']

            # Skip non-data tabs
            if tab_title in ['DBR Information', '指标说明']:
                continue

            print(f"\nClicking tab: {tab_title}")
            await eval_js(ws, session_id, f"""
            (() => {{
                const tabs = document.querySelectorAll('.tab-nav-item');
                if ({tab_idx} < tabs.length) tabs[{tab_idx}].click();
            }})()
            """)

            # Listen for responses for 8 seconds after each tab click
            end_time = asyncio.get_event_loop().time() + 8
            while asyncio.get_event_loop().time() < end_time:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    msg_obj = json.loads(msg)

                    # Check for Network.responseReceived
                    if msg_obj.get("method") == "Network.responseReceived":
                        resp = msg_obj.get("params", {}).get("response", {})
                        url = resp.get("url", "")
                        if "/api/mtbi/bi/" in url and "/data" in url:
                            # Extract lid from URL
                            import re
                            lid_match = re.search(r'/bi/(\d+)/data', url)
                            lid = lid_match.group(1) if lid_match else "unknown"
                            print(f"  Captured data API: lid={lid}, status={resp.get('status')}")

                    # Check for Network.loadingFinished
                    if msg_obj.get("method") == "Network.loadingFinished":
                        req_id = msg_obj.get("params", {}).get("requestId")
                        # We'd need to get response body here, but it's complex

                except asyncio.TimeoutError:
                    pass

            # Alternative: try to extract data from the page's data stores
            # Many BI frameworks store data in window.__INITIAL_STATE__ or similar
            await asyncio.sleep(2)

        # Try to find data in various window properties
        print("\n=== Searching for data in window object ===")
        data_sources = await eval_js(ws, session_id, """
        (() => {
            const results = {};
            // Common data storage patterns
            const patterns = [
                '__INITIAL_STATE__', '__DATA__', '__APP_DATA__',
                '__dashboard_data__', '__chart_data__', '__table_data__',
                '_store', '_data', 'store', 'data'
            ];
            for (const p of patterns) {
                if (window[p] && typeof window[p] === 'object') {
                    const str = JSON.stringify(window[p]);
                    if (str.length > 500) {
                        results[p] = str.length;
                    }
                }
            }
            return results;
        })()
        """)
        print(f"Data sources: {data_sources}")

        # Save whatever we captured
        captured_responses['_meta'] = {
            'timestamp': datetime.now().isoformat(),
            'tabs': tabs_info,
            'data_sources': data_sources
        }
        save_results(captured_responses)

        # Close tab
        await cdp_send(ws, None, "Target.closeTarget", {"targetId": target_id})

asyncio.run(main())
