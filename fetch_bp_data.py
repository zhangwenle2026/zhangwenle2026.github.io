#!/usr/bin/env python3
"""Fetch Business Platform dashboard data via CDP + Playwright"""
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

DASHBOARD_ID = 300001446
TARGET_CHARTS = [
    "CM - Business Performance",
    "BDM - Business Performance",
    "BD - Business Performance",
    "Merchant List - Business Performance",
    "SMB - MTD Merchant Ranking",
    "Last 10 Days - Order Performance",
    "Last 10 days - New Signs",
    "Last 10 days - Operation Performance",
    "Last 10 days - User Experience",
    "Last 10 days - Promotion",
]

CDP_URL = "http://127.0.0.1:9222"
CONTROLLER_URL = f"https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId={DASHBOARD_ID}"

class DashboardFetcher:
    def __init__(self):
        self.results = {}
        self.components = {}
        self.tab_components = {}

    async def run(self):
        print(f"[{datetime.now()}] Starting fetch for dashboard {DASHBOARD_ID}")
        playwright = await async_playwright().start()
        try:
            # Connect via CDP
            import urllib.request
            version = json.loads(urllib.request.urlopen(CDP_URL + "/json/version", timeout=5).read())
            ws_url = version["webSocketDebuggerUrl"]
            print(f"Connecting to CDP: {ws_url[:60]}...")
            browser = await playwright.chromium.connect_over_cdp(ws_url)
            contexts = browser.contexts
            if not contexts:
                print("No browser contexts found")
                return False
            context = contexts[0]
            print(f"Found {len(context.pages)} pages")

            # Create a new page
            page = await context.new_page()
            print(f"Navigating to {CONTROLLER_URL}")
            await page.goto(CONTROLLER_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3)

            # Wait for DashboardController
            for attempt in range(30):
                ready = await page.evaluate("() => typeof window.DashboardController !== 'undefined'")
                if ready:
                    print("DashboardController is ready")
                    break
                await asyncio.sleep(1)
            else:
                print("DashboardController not ready after 30s")
                return False

            # Get all components
            comps_res = await page.evaluate("""
                async () => {
                    const res = await window.DashboardController.getComponents();
                    return JSON.stringify(res);
                }
            """)
            comps = json.loads(comps_res)
            if comps.get("code") != 0:
                print(f"getComponents failed: {comps}")
                return False

            # Build component map
            for c in comps.get("data", []):
                self.components[c["componentName"]] = c
                if c["componentType"] == "tab":
                    self.tab_components[c["componentName"]] = c

            print(f"Found {len(self.components)} components")
            for name in TARGET_CHARTS:
                if name in self.components:
                    cid = self.components[name]["componentId"]
                    print(f"  {name} -> {cid}")
                else:
                    print(f"  {name} -> NOT FOUND")

            # Activate tabs that contain target charts
            tabs_to_activate = set()
            for name in TARGET_CHARTS:
                if name not in self.components:
                    continue
                chart = self.components[name]
                # Find which tab contains this chart
                for tab_name, tab in self.tab_components.items():
                    children = tab.get("childrenComponents", [])
                    child_ids = [ch["componentId"] if isinstance(ch, dict) else ch for ch in children]
                    if chart["componentId"] in child_ids:
                        tabs_to_activate.add(tab_name)
                        print(f"Chart '{name}' is in tab '{tab_name}'")
                        break

            # Activate each tab first, then query charts in that tab
            for tab_name in tabs_to_activate:
                tab = self.tab_components.get(tab_name)
                if not tab:
                    continue
                # Find and click the tab
                tab_clicked = await page.evaluate(f"""
                    async () => {{
                        const tabs = document.querySelectorAll('.tab-nav-item');
                        for (const t of tabs) {{
                            const title = t.querySelector('.tab-title')?.textContent?.trim();
                            if (title === '{tab_name}') {{
                                t.click();
                                return true;
                            }}
                        }}
                        return false;
                    }}
                """)
                print(f"Clicked tab '{tab_name}': {tab_clicked}")
                await asyncio.sleep(2)

            # Now query all target charts
            for chart_name in TARGET_CHARTS:
                if chart_name not in self.components:
                    print(f"Skipping {chart_name} - not found")
                    continue
                cid = self.components[chart_name]["componentId"]
                print(f"Querying: {chart_name} ({cid})")
                try:
                    res = await page.evaluate(f"""
                        async () => {{
                            const res = await window.DashboardController.executeQueryAndGetCHNResult(['{cid}']);
                            return JSON.stringify(res);
                        }}
                    """)
                    data = json.loads(res)
                    self.results[chart_name] = data
                    if data.get("code") == 0:
                        rows = len(data.get("data", {}).get("data", []))
                        print(f"  -> OK, {rows} rows")
                    else:
                        print(f"  -> Error: {data.get('message')}")
                except Exception as e:
                    print(f"  -> Exception: {e}")
                    self.results[chart_name] = {"code": -1, "message": str(e)}
                await asyncio.sleep(0.5)

            await page.close()
            return True
        finally:
            await playwright.stop()

async def main():
    fetcher = DashboardFetcher()
    ok = await fetcher.run()
    if not ok:
        sys.exit(1)

    # Save results
    output_path = Path("/mnt/openclaw/.openclaw/workspace/bi_raw_data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(fetcher.results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(fetcher.results)} charts to {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
