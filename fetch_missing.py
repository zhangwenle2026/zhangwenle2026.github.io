#!/usr/bin/env python3
import asyncio
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright

MISSING = [
    ("BDM - Business Performance", "chart-stq7y-e6570"),
    ("BD - Business Performance", "dashboard-chart-container-fgaiv-e51fa"),
    ("Merchant List - Business Performance", "dashboard-chart-container-si86e-77178"),
    ("SMB - MTD Merchant Ranking", "chart-budz2-630e8"),
]

CDP_URL = "http://127.0.0.1:9222"
CONTROLLER_URL = "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446"

async def fetch():
    playwright = await async_playwright().start()
    try:
        import urllib.request
        version = json.loads(urllib.request.urlopen(CDP_URL + "/json/version", timeout=5).read())
        browser = await playwright.chromium.connect_over_cdp(version["webSocketDebuggerUrl"])
        context = browser.contexts[0]
        page = await context.new_page()
        await page.goto(CONTROLLER_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        for i in range(30):
            if await page.evaluate("() => typeof window.DashboardController !== 'undefined'"):
                break
            await asyncio.sleep(1)
        else:
            print("Controller timeout")
            return {}

        # Load existing data
        existing_path = Path("/mnt/openclaw/.openclaw/workspace/bi_raw_data.json")
        with open(existing_path, encoding="utf-8") as f:
            results = json.load(f)

        for name, cid in MISSING:
            print(f"Querying: {name}")
            try:
                res = await asyncio.wait_for(
                    page.evaluate(f"""
                        async () => {{
                            const res = await window.DashboardController.executeQueryAndGetCHNResult(['{cid}']);
                            return JSON.stringify(res);
                        }}
                    """),
                    timeout=120
                )
                data = json.loads(res)
                results[name] = data
                rows = len(data.get("data", {}).get("data", [])) if data.get("code") == 0 else 0
                print(f"  -> {'OK' if data.get('code')==0 else 'ERR'}, {rows} rows")
            except asyncio.TimeoutError:
                print(f"  -> TIMEOUT")
            except Exception as e:
                print(f"  -> Exception: {e}")
            await asyncio.sleep(1)

        await page.close()
        return results
    finally:
        await playwright.stop()

async def main():
    results = await fetch()
    output_path = Path("/mnt/openclaw/.openclaw/workspace/bi_raw_data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {output_path}")
    for name, data in results.items():
        status = "OK" if data.get("code") == 0 else f"ERR({data.get('code')})"
        rows = len(data.get("data", {}).get("data", [])) if data.get("code") == 0 else 0
        print(f"  {name}: {status}, {rows} rows")

if __name__ == "__main__":
    asyncio.run(main())
