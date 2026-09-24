#!/usr/bin/env python3
"""Fetch all BI chart data via executeDownload"""
import asyncio, json, urllib.request, websockets
from datetime import datetime

CDP_URL = "http://127.0.0.1:9222"
CONTROLLER_URL = "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446"
OUTPUT_DIR = "/mnt/openclaw/.openclaw/workspace"

# Charts to fetch
TARGET_CHARTS = [
    "Last 10 Days - Order Performance",
    "Last 10 days - New Signs",
    "Last 10 days - Promotion",
    "CM - Business Performance",
    "Last 10 days - Operation Performance",
    "Last 10 days - User Experience",
]

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

def download_csv(url, output_path):
    """Download CSV from wenshu URL"""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read()
            with open(output_path, 'wb') as f:
                f.write(data)
        return True
    except Exception as e:
        print(f"    Download error: {e}")
        return False

async def main():
    info = json.loads(urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=5).read())
    ws_url = info["webSocketDebuggerUrl"]

    async with websockets.connect(ws_url) as ws:
        resp = await cdp_send(ws, None, "Target.getTargets")
        targets = resp["result"]["targetInfos"]
        bi_target = next((t for t in targets if "bi.keetapp" in t.get("url","") and "300001446" in t.get("url","")), None)

        target_id = bi_target["targetId"]
        resp = await cdp_send(ws, None, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
        session_id = resp["result"]["sessionId"]
        await cdp_send(ws, session_id, "Runtime.enable")

        # Navigate to controller page
        current_url = await eval_js(ws, session_id, "window.location.href")
        if "dashboard-controller" not in current_url:
            print("Navigating to controller page...")
            await cdp_send(ws, session_id, "Page.navigate", {"url": CONTROLLER_URL})
            await asyncio.sleep(10)
            for i in range(30):
                ready = await eval_js(ws, session_id, "typeof window.DashboardController !== 'undefined'")
                if ready:
                    print(f"DashboardController ready after {i+1}s")
                    break
                await asyncio.sleep(1)
            else:
                print("Timeout waiting for DashboardController")
                return

        # Get components
        comps_raw = await eval_js(ws, session_id, """
        (async () => {
            const res = await window.DashboardController.getComponents();
            return JSON.stringify(res);
        })()
        """)
        comps = json.loads(comps_raw or '{}')

        chart_map = {}
        tab_map = {}
        for c in comps.get('data', []):
            if c['componentType'] == 'chart':
                chart_map[c['componentName']] = c['componentId']
            elif c['componentType'] == 'tab':
                tab_map[c['componentName']] = c['componentId']

        print(f"Found {len(chart_map)} charts, {len(tab_map)} tabs")

        results = {}
        download_links = {}

        # === Main tab charts ===
        for name in ["Last 10 Days - Order Performance", "Last 10 days - New Signs", "Last 10 days - Promotion", "CM - Business Performance"]:
            cid = chart_map.get(name)
            if not cid:
                print(f"⚠️ Not found: {name}")
                continue

            print(f"\nProcessing: {name}")

            # Trigger query
            res = await eval_js(ws, session_id, f"""
            (async () => {{
                const res = await window.DashboardController.executeQueryAndGetCHNResult("{cid}");
                return JSON.stringify({{code: res.code}});
            }})()
            """)
            await asyncio.sleep(1)

            # Download
            dl = await eval_js(ws, session_id, f"""
            (async () => {{
                const res = await window.DashboardController.executeDownload("{cid}", {{fileType: "CSV"}});
                return JSON.stringify(res);
            }})()
            """)
            dl_data = json.loads(dl or '{}')
            if dl_data.get('code') == 0 and dl_data.get('data', {}).get('fileUrl'):
                url = dl_data['data']['fileUrl']
                download_links[name] = url
                print(f"  ✓ Download URL: {url[:80]}...")

                # Download file
                safe_name = name.replace(' ', '_').replace('-', '_')
                output_path = f"{OUTPUT_DIR}/bp_{safe_name}.csv"
                if download_csv(url, output_path):
                    print(f"  ✓ Saved to: {output_path}")
                else:
                    print(f"  ✗ Download failed")
            else:
                print(f"  ✗ No download link: {dl_data}")

            await asyncio.sleep(0.5)

        # === Operating Performance tab ===
        print("\nSwitching to Operating Performance...")
        await eval_js(ws, session_id, """
        (() => {
            const tabs = document.querySelectorAll('.tab-nav-item');
            for (const t of tabs) {
                const title = t.querySelector('.tab-title')?.textContent?.trim();
                if (title === 'Operating Performance') { t.click(); return true; }
            }
            return false;
        })()
        """)
        await asyncio.sleep(3)

        cid = chart_map.get("Last 10 days - Operation Performance")
        if cid:
            print(f"\nProcessing: Last 10 days - Operation Performance")
            res = await eval_js(ws, session_id, f"""
            (async () => {{
                const res = await window.DashboardController.executeQueryAndGetCHNResult("{cid}");
                return JSON.stringify({{code: res.code}});
            }})()
            """)
            await asyncio.sleep(1)
            dl = await eval_js(ws, session_id, f"""
            (async () => {{
                const res = await window.DashboardController.executeDownload("{cid}", {{fileType: "CSV"}});
                return JSON.stringify(res);
            }})()
            """)
            dl_data = json.loads(dl or '{}')
            if dl_data.get('code') == 0 and dl_data.get('data', {}).get('fileUrl'):
                url = dl_data['data']['fileUrl']
                download_links["Last 10 days - Operation Performance"] = url
                output_path = f"{OUTPUT_DIR}/bp_Last_10_days_Operation_Performance.csv"
                if download_csv(url, output_path):
                    print(f"  ✓ Saved to: {output_path}")

        # === User Experience tab ===
        print("\nSwitching to User Experience...")
        await eval_js(ws, session_id, """
        (() => {
            const tabs = document.querySelectorAll('.tab-nav-item');
            for (const t of tabs) {
                const title = t.querySelector('.tab-title')?.textContent?.trim();
                if (title === 'User Experience') { t.click(); return true; }
            }
            return false;
        })()
        """)
        await asyncio.sleep(3)

        cid = chart_map.get("Last 10 days - User Experience")
        if cid:
            print(f"\nProcessing: Last 10 days - User Experience")
            res = await eval_js(ws, session_id, f"""
            (async () => {{
                const res = await window.DashboardController.executeQueryAndGetCHNResult("{cid}");
                return JSON.stringify({{code: res.code}});
            }})()
            """)
            await asyncio.sleep(1)
            dl = await eval_js(ws, session_id, f"""
            (async () => {{
                const res = await window.DashboardController.executeDownload("{cid}", {{fileType: "CSV"}});
                return JSON.stringify(res);
            }})()
            """)
            dl_data = json.loads(dl or '{}')
            if dl_data.get('code') == 0 and dl_data.get('data', {}).get('fileUrl'):
                url = dl_data['data']['fileUrl']
                download_links["Last 10 days - User Experience"] = url
                output_path = f"{OUTPUT_DIR}/bp_Last_10_days_User_Experience.csv"
                if download_csv(url, output_path):
                    print(f"  ✓ Saved to: {output_path}")

        # Save download links
        with open(f"{OUTPUT_DIR}/bp_download_links.json", 'w') as f:
            json.dump(download_links, f, indent=2)

        print(f"\n=== Done! Downloaded {len(download_links)} files ===")
        for name, url in download_links.items():
            print(f"  {name}")

asyncio.run(main())
