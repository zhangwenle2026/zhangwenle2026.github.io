import asyncio
import json
from playwright.async_api import async_playwright

URL = "https://km.sankuai.com/xtable/2762258282?table=2762634988&view=1000"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        contexts = browser.contexts
        if not contexts:
            print("ERROR: No browser contexts")
            return
        
        context = contexts[0]
        page = await context.new_page()
        
        print(f"Navigating to: {URL}")
        await page.goto(URL, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(5)  # Wait for table to render
        
        print(f"Page title: {await page.title()}")
        
        # Try to extract table data from the page
        # xtable usually renders as a grid/table
        data = await page.evaluate("""
        () => {
            // Try to find table rows
            const rows = document.querySelectorAll('tr, .row, [class*="row"], [class*="Row"]');
            if (rows.length > 0) {
                const result = [];
                rows.forEach(row => {
                    const cells = row.querySelectorAll('td, th, .cell, [class*="cell"], [class*="Cell"]');
                    if (cells.length > 0) {
                        const rowData = [];
                        cells.forEach(cell => rowData.push(cell.textContent.trim()));
                        if (rowData.some(c => c)) result.push(rowData);
                    }
                });
                return {method: 'tr/td', count: result.length, data: result.slice(0, 100)};
            }
            
            // Try grid approach
            const grid = document.querySelector('[class*="grid"], [class*="Grid"], [class*="table"], [class*="Table"]');
            if (grid) {
                return {method: 'grid', text: grid.textContent.substring(0, 5000)};
            }
            
            // Fallback: get all visible text
            return {method: 'fallback', text: document.body.innerText.substring(0, 8000)};
        }
        """)
        
        print(f"Method: {data.get('method')}")
        if data.get('data'):
            print(f"Rows found: {data['count']}")
            for i, row in enumerate(data['data'][:30]):
                print(f"  Row {i}: {row[:8]}")
        elif data.get('text'):
            print(f"Text content (first 3000 chars):")
            print(data['text'][:3000])
        
        # Save full data
        with open("/tmp/xtable_data.json", "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        await page.close()

asyncio.run(main())
