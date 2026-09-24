import asyncio
import json
from playwright.async_api import async_playwright

URL = "https://km.sankuai.com/xtable/2762258282?table=2762634988&view=1000"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        contexts = browser.contexts
        context = contexts[0]
        page = await context.new_page()
        
        print(f"Navigating to: {URL}")
        await page.goto(URL, wait_until="networkidle", timeout=90000)
        
        # Wait longer for data to load
        print("Waiting for table content...")
        await asyncio.sleep(10)
        
        # Try multiple extraction strategies
        data = await page.evaluate("""
        () => {
            const results = {};
            
            // Strategy 1: Look for xtable specific elements
            const cells = document.querySelectorAll('[class*="xtable"] [class*="cell"], [class*="XTable"] [class*="Cell"]');
            if (cells.length > 0) {
                results.xtable_cells = cells.length;
                results.sample_cells = Array.from(cells).slice(0, 50).map(c => c.textContent.trim());
            }
            
            // Strategy 2: Any div/span with data content
            const allText = document.body.innerText;
            results.full_text = allText.substring(0, 10000);
            results.text_length = allText.length;
            
            // Strategy 3: Check for iframes
            const iframes = document.querySelectorAll('iframe');
            results.iframe_count = iframes.length;
            if (iframes.length > 0) {
                results.iframe_srcs = Array.from(iframes).map(f => f.src);
            }
            
            // Strategy 4: Check class names on page
            const allClasses = new Set();
            document.querySelectorAll('[class]').forEach(el => {
                el.className.split(' ').forEach(c => {
                    if (c && (c.includes('table') || c.includes('Table') || c.includes('grid') || c.includes('Grid') || c.includes('row') || c.includes('Row') || c.includes('cell') || c.includes('Cell') || c.includes('record') || c.includes('Record'))) {
                        allClasses.add(c);
                    }
                });
            });
            results.relevant_classes = Array.from(allClasses).slice(0, 30);
            
            return results;
        }
        """)
        
        print(f"Text length: {data.get('text_length')}")
        print(f"Iframe count: {data.get('iframe_count')}")
        if data.get('iframe_srcs'):
            print(f"Iframe sources: {data['iframe_srcs']}")
        print(f"Relevant classes: {data.get('relevant_classes', [])[:20]}")
        print(f"XTable cells: {data.get('xtable_cells', 0)}")
        
        if data.get('full_text'):
            text = data['full_text']
            print(f"\n--- Page text (first 4000 chars) ---")
            print(text[:4000])
        
        with open("/tmp/xtable_data2.json", "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        await page.close()

asyncio.run(main())
