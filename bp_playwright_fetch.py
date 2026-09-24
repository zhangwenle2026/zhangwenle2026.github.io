#!/usr/bin/env python3
"""Thorough BI data fetch using Playwright with CDP"""
import asyncio
import json
import os
import sys
import re
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".openclaw/skills/bi-query-dashboard-overseas/scripts"))

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("playwright not available")
    sys.exit(1)

DASHBOARD_URL = "https://bi.keetapp.com/v2/dashboard/300001446"
OUTPUT_DIR = Path("/mnt/openclaw/.openclaw/workspace")
OUTPUT_JSON = OUTPUT_DIR / "bi_raw_data.json"

# Map of tab name -> chart titles we want
target_charts = {
    "Business Performance": ["Last 10 Days - Order Performance", "Last 10 days - New Signs", "Last 10 days - Promotion", "CM - Business Performance"],
    "Operating Performance": ["Last 10 days - Operation Performance"],
    "User Experience": ["Last 10 days - User Experience"],
}

async def main():
    captured_data = {}

    async with async_playwright().start() as p:
        # Connect to existing browser via CDP
        version_info = json.loads(__import__('urllib.request').request.urlopen(
            "http://127.0.0.1:9222/json/version", timeout=5
        ).read())
        ws_url = version_info["webSocketDebuggerUrl"]

        browser = await p.chromium.connect_over_cdp(ws_url)
        contexts = browser.contexts
        if not contexts:
            print("No browser contexts found")
            return

        context = contexts[0]

        # Find existing BI page or create new one
        page = None
        for pg in context.pages:
            if "bi.keetapp" in pg.url and "300001446" in pg.url:
                page = pg
                break

        if page is None:
            page = await context.new_page()
            await page.goto(DASHBOARD_URL, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(5)
        else:
            print(f"Reusing page: {page.url}")
            # Navigate to regular dashboard page
            if "dashboard-controller" in page.url:
                await page.goto(DASHBOARD_URL, timeout=60000, wait_until="domcontentloaded")
                await asyncio.sleep(5)

        # Set up response capture
        async def handle_response(response):
            url = response.url
            if "/api/mtbi/bi/" in url and "/data" in url:
                match = re.search(r'/bi/(\d+)/data', url)
                if match:
                    lid = match.group(1)
                    try:
                        body = await response.json()
                        captured_data[lid] = body
                        print(f"  [API] lid={lid}, rows={len(body.get('data', {}).get('data', []))}")
                    except Exception as e:
                        print(f"  [API] lid={lid}, parse error: {e}")

        page.on("response", handle_response)

        # Wait for page to be ready
        await page.wait_for_selector(".tab-nav-item", timeout=30000)
        await asyncio.sleep(3)

        # Get all tabs
        tabs = await page.query_selector_all(".tab-nav-item")
        tab_info = []
        for i, tab in enumerate(tabs):
            title = await tab.eval("el => el.querySelector('.tab-title')?.textContent?.trim() || ''")
            tab_info.append({"index": i, "title": title})
            print(f"  Tab[{i}]: {title}")

        # Process each relevant tab
        for info in tab_info:
            title = info["title"]
            if title not in target_charts:
                continue

            print(f"\n=== Processing tab: {title} ===")

            # Click tab
            tabs = await page.query_selector_all(".tab-nav-item")
            if info["index"] < len(tabs):
                await tabs[info["index"]].click()
                await asyncio.sleep(5)

            # Get chart components on this tab
            charts = await page.query_selector_all(".chart-edit-view, .mobile-layout-item")
            print(f"  Found {len(charts)} chart containers")

            # Scroll through each chart to trigger lazy loading
            for i, chart in enumerate(charts):
                await chart.scroll_into_view_if_needed()
                await asyncio.sleep(2)

                # Get chart title
                chart_title = await chart.eval("el => el.querySelector('.chart-title, .title')?.textContent?.trim() || ''")
                if chart_title:
                    print(f"    Chart {i}: {chart_title}")

            # Extra wait for API calls to complete
            await asyncio.sleep(5)

        # Also capture from staticResourceInfo for column names
        print("\n=== Waiting for all API calls to settle ===")
        await asyncio.sleep(10)

        await browser.close()

    # Save captured data
    with open(OUTPUT_JSON, 'w') as f:
        json.dump(captured_data, f, ensure_ascii=False, indent=2)

    print(f"\n=== Captured {len(captured_data)} API responses ===")
    for lid, data in captured_data.items():
        rows = len(data.get('data', {}).get('data', [])) if isinstance(data, dict) else 0
        print(f"  lid={lid}: {rows} rows")

if __name__ == "__main__":
    asyncio.run(main())
