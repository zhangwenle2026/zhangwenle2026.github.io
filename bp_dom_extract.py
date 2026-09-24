#!/usr/bin/env python3
"""Extract BI dashboard data from DOM tables"""
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

async def extract_table_data(ws, session_id, chart_selector):
    """Extract data from a table within a chart element"""
    return await eval_js(ws, session_id, f"""
    (() => {{
        const chart = document.querySelector('{chart_selector}');
        if (!chart) return {{error: 'Chart not found'}};
        const table = chart.querySelector('table');
        if (!table) return {{error: 'No table in chart'}};
        const rows = table.querySelectorAll('tr');
        const data = [];
        const headers = [];
        for (let i = 0; i < rows.length; i++) {{
            const cells = rows[i].querySelectorAll('th, td');
            const rowData = Array.from(cells).map(c => c.textContent.trim());
            if (i === 0) {{
                headers.push(...rowData);
            }} else {{
                data.push(rowData);
            }}
        }}
        return {{headers, data, rowCount: data.length}};
    }})()
    """)

async def extract_chart_by_title(ws, session_id, title_text):
    """Find chart by title and extract its table data"""
    return await eval_js(ws, session_id, f"""
    (() => {{
        const charts = document.querySelectorAll('.chart-edit-view, .mobile-layout-item');
        for (const chart of charts) {{
            const title = chart.querySelector('.chart-title, .title');
            if (title && title.textContent.includes('{title_text}')) {{
                const table = chart.querySelector('table');
                if (table) {{
                    const rows = table.querySelectorAll('tr');
                    const data = [];
                    const headers = [];
                    for (let i = 0; i < rows.length; i++) {{
                        const cells = rows[i].querySelectorAll('th, td');
                        const rowData = Array.from(cells).map(c => c.textContent.trim());
                        if (i === 0) {{
                            headers.push(...rowData);
                        }} else {{
                            data.push(rowData);
                        }}
                    }}
                    return {{found: true, headers, data, rowCount: data.length}};
                }}
                return {{found: true, error: 'No table'}};
            }}
        }}
        return {{found: false}};
    }})()
    """)

async def main():
    info = json.loads(urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=5).read())
    ws_url = info["webSocketDebuggerUrl"]

    async with websockets.connect(ws_url) as ws:
        # Create new tab with regular dashboard view
        resp = await cdp_send(ws, None, "Target.createTarget", {"url": DASHBOARD_URL})
        target_id = resp["result"]["targetId"]
        print(f"Created new tab: {target_id}")
        await asyncio.sleep(10)

        resp = await cdp_send(ws, None, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
        session_id = resp["result"]["sessionId"]
        await cdp_send(ws, session_id, "Runtime.enable")

        # Wait for page to load
        for i in range(30):
            has_charts = await eval_js(ws, session_id, "document.querySelectorAll('.chart-edit-view, .mobile-layout-item').length > 0")
            if has_charts:
                print(f"Dashboard loaded after {i+1}s")
                break
            await asyncio.sleep(1)
        else:
            print("Dashboard load timeout")
            return

        results = {}

        # Extract data from main tab
        print("\n=== Main Tab ===")

        charts_to_extract = [
            ("Last 10 Days - Order Performance", "Last 10 Days - Order Performance"),
            ("Last 10 days - New Signs", "Last 10 days - New Signs"),
            ("Last 10 days - Promotion", "Last 10 days - Promotion"),
            ("CM - Business Performance", "CM - Business Performance"),
        ]

        for key, title in charts_to_extract:
            print(f"\nExtracting: {title}")
            data = await extract_chart_by_title(ws, session_id, title)
            if data.get('found'):
                if data.get('data'):
                    print(f"  ✓ {data['rowCount']} rows, {len(data['headers'])} columns")
                    print(f"  Headers: {data['headers']}")
                    print(f"  First row: {data['data'][0] if data['data'] else 'N/A'}")
                    results[key] = {
                        'code': 0,
                        'data': {
                            'columns': data['headers'],
                            'data': data['data']
                        }
                    }
                else:
                    print(f"  ✗ {data.get('error', 'No data')}")
            else:
                print(f"  ✗ Chart not found")

        # Click through tabs
        tabs = await eval_js(ws, session_id, """
        (() => {
            const tabs = document.querySelectorAll('.tab-nav-item');
            return Array.from(tabs).map((t, i) => ({
                index: i,
                title: t.querySelector('.tab-title')?.textContent?.trim() || ''
            }));
        })()
        """)
        print(f"\n=== Tabs: {len(tabs) if tabs else 0} ===")
        for t in (tabs or []):
            print(f"  [{t['index']}] {t['title']}")

        # Extract from Operating Performance tab
        op_tab = next((t for t in (tabs or []) if t['title'] == 'Operating Performance'), None)
        if op_tab:
            print(f"\n=== Operating Performance Tab ===")
            await eval_js(ws, session_id, f"""
            (() => {{
                const tabs = document.querySelectorAll('.tab-nav-item');
                if ({op_tab['index']} < tabs.length) tabs[{op_tab['index']}].click();
            }})()
            """)
            await asyncio.sleep(5)

            data = await extract_chart_by_title(ws, session_id, "Last 10 days - Operation Performance")
            if data.get('found') and data.get('data'):
                print(f"  ✓ {data['rowCount']} rows")
                results["Last 10 days - Operation Performance"] = {
                    'code': 0,
                    'data': {
                        'columns': data['headers'],
                        'data': data['data']
                    }
                }
            else:
                print(f"  ✗ Not found or no data")

        # Extract from User Experience tab
        ux_tab = next((t for t in (tabs or []) if t['title'] == 'User Experience'), None)
        if ux_tab:
            print(f"\n=== User Experience Tab ===")
            await eval_js(ws, session_id, f"""
            (() => {{
                const tabs = document.querySelectorAll('.tab-nav-item');
                if ({ux_tab['index']} < tabs.length) tabs[{ux_tab['index']}].click();
            }})()
            """)
            await asyncio.sleep(5)

            data = await extract_chart_by_title(ws, session_id, "Last 10 days - User Experience")
            if data.get('found') and data.get('data'):
                print(f"  ✓ {data['rowCount']} rows")
                results["Last 10 days - User Experience"] = {
                    'code': 0,
                    'data': {
                        'columns': data['headers'],
                        'data': data['data']
                    }
                }
            else:
                print(f"  ✗ Not found or no data")

        # Save results
        save_results(results)
        print(f"\n=== Saved {len(results)} charts to {OUTPUT} ===")
        for name, data in results.items():
            rows = data.get('data', {}).get('data', [])
            print(f"  {name}: {len(rows)} rows")

        # Close tab
        await cdp_send(ws, None, "Target.closeTarget", {"targetId": target_id})

asyncio.run(main())
