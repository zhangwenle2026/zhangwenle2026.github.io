#!/usr/bin/env python3
"""Fetch BI data via CDP network interception on regular dashboard page"""
import asyncio, json, urllib.request, websockets
from datetime import datetime

CDP_URL = "http://127.0.0.1:9222"
DASHBOARD_URL = "https://bi.keetapp.com/v2/dashboard/300001446"
OUTPUT = "/mnt/openclaw/.openclaw/workspace/bi_raw_data.json"

# Store captured data
captured_data = {}

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

def save_results():
    with open(OUTPUT, 'w') as f:
        json.dump(captured_data, f, ensure_ascii=False, indent=2)

async def main():
    info = json.loads(urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=5).read())
    ws_url = info["webSocketDebuggerUrl"]
    print(f"Browser: {ws_url[:50]}...")

    async with websockets.connect(ws_url) as ws:
        # Create a new tab for the regular dashboard page
        resp = await cdp_send(ws, None, "Target.createTarget", {"url": DASHBOARD_URL})
        target_id = resp["result"]["targetId"]
        print(f"Created new tab: {target_id}")
        await asyncio.sleep(8)

        resp = await cdp_send(ws, None, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
        session_id = resp["result"]["sessionId"]
        await cdp_send(ws, session_id, "Runtime.enable")

        # Enable network domain
        await cdp_send(ws, session_id, "Network.enable")

        # Set up response interception via Runtime.evaluate to install a fetch interceptor
        # Actually, let's just wait for the page to load and use the data from API calls
        await asyncio.sleep(5)

        # Check page state
        url = await eval_js(ws, session_id, "window.location.href")
        title = await eval_js(ws, session_id, "document.title")
        print(f"Page: {title} | {url}")

        # Wait for dashboard to load
        for i in range(30):
            has_content = await eval_js(ws, session_id, "document.querySelectorAll('.chart-edit-view, .mobile-layout-item').length > 0")
            if has_content:
                print(f"Dashboard loaded after {i+1}s")
                break
            await asyncio.sleep(1)
        else:
            print("Dashboard load timeout")

        # Click through all tabs to trigger data loading
        tabs_info = await eval_js(ws, session_id, """
        (() => {
            const tabs = document.querySelectorAll('.tab-nav-item');
            return Array.from(tabs).map(t => ({
                title: t.querySelector('.tab-title')?.textContent?.trim() || '',
                active: t.classList.contains('active-tab')
            }));
        })()
        """)
        print(f"Tabs found: {len(tabs_info) if tabs_info else 0}")
        for t in (tabs_info or []):
            print(f"  - {t.get('title', '?')} {'(active)' if t.get('active') else ''}")

        # Click each tab and wait for data
        for i in range(len(tabs_info or [])):
            tab_title = tabs_info[i].get('title', '')
            print(f"\nClicking tab: {tab_title}")

            await eval_js(ws, session_id, f"""
            (() => {{
                const tabs = document.querySelectorAll('.tab-nav-item');
                if ({i} < tabs.length) {{
                    tabs[{i}].click();
                    return true;
                }}
                return false;
            }})()
            """)
            await asyncio.sleep(5)  # Wait for API calls

            # Scroll to trigger lazy loading
            await eval_js(ws, session_id, """
            (() => {
                const items = document.querySelectorAll('.chart-edit-view, .mobile-layout-item');
                if (items.length > 0) {
                    items[items.length - 1].scrollIntoView();
                    return items.length;
                }
                return 0;
            })()
            """)
            await asyncio.sleep(2)

        # Try to get data from window.__dashboard_data or similar
        print("\nChecking for dashboard data in window object...")
        data_keys = await eval_js(ws, session_id, """
        (() => {
            const keys = [];
            for (const k of Object.keys(window)) {
                if (k.includes('dashboard') || k.includes('Dashboard') || k.includes('data') || k.includes('Data')) {
                    const v = window[k];
                    if (v && typeof v === 'object') {
                        const size = JSON.stringify(v).length;
                        if (size > 1000) {
                            keys.push({key: k, size: size});
                        }
                    }
                }
            }
            return keys;
        })()
        """)
        print(f"Found potential data keys: {data_keys}")

        # Try extracting data from Vue/React internal state
        print("\nTrying to extract from Vue/React internals...")
        vue_data = await eval_js(ws, session_id, """
        (() => {
            // Try to find Vue instances on chart elements
            const charts = document.querySelectorAll('.chart-edit-view');
            const results = [];
            for (const chart of charts) {
                const vue = chart.__vue__ || chart.__VUE__;
                if (vue) {
                    results.push({id: chart.id || '', hasVue: true, keys: Object.keys(vue).slice(0, 10)});
                }
                // Try React
                const keys = Object.keys(chart);
                for (const k of keys) {
                    if (k.startsWith('__react')) {
                        results.push({id: chart.id || '', hasReact: true});
                        break;
                    }
                }
            }
            return results;
        })()
        """)
        print(f"Vue/React check: {vue_data}")

        # Save whatever we have
        captured_data['_meta'] = {
            'timestamp': datetime.now().isoformat(),
            'url': url,
            'tabs': tabs_info
        }
        save_results()
        print(f"\nSaved meta data to {OUTPUT}")

        # Close the tab
        await cdp_send(ws, None, "Target.closeTarget", {"targetId": target_id})

asyncio.run(main())
