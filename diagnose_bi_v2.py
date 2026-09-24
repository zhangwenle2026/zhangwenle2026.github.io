
import asyncio
import json
from playwright.async_api import async_playwright

async def diagnose():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        contexts = browser.contexts
        if not contexts:
            print("ERROR: No browser contexts")
            return
        
        context = contexts[0]
        page = await context.new_page()
        
        print("Navigating to bi.keetapp.com dashboard...")
        try:
            await page.goto(
                "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446",
                wait_until="networkidle",
                timeout=60000
            )
            print(f"URL after nav: {page.url}")
            print(f"Title: {await page.title()}")
            
            # Check for login redirect
            if "login" in page.url.lower() or "auth" in page.url.lower() or "sso" in page.url.lower():
                print("WARNING: Redirected to login/auth page. Need authentication.")
                body = await page.content()
                print(f"Page body snippet: {body[:500]}")
                return
            
            # Wait for DashboardController with retries
            print("Waiting for DashboardController (with retries)...")
            for i in range(10):
                ready = await page.evaluate("typeof window.DashboardController !== 'undefined'")
                print(f"  Attempt {i+1}: DashboardController ready = {ready}")
                if ready:
                    print("SUCCESS: DashboardController is available!")
                    break
                await asyncio.sleep(2)
            else:
                print("DashboardController not available after all retries")
                body = await page.content()
                print(f"Page body snippet: {body[:500]}")
                
        except Exception as e:
            print(f"ERROR: {e}")
        finally:
            await page.close()

asyncio.run(diagnose())
