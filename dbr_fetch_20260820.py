#!/usr/bin/env python3
"""DBR data fetch for 2026-08-20 - using current BI tab via CDP"""
import asyncio
import json
import websockets

PAGE_WS = "ws://localhost:9222/devtools/page/C52CA7B272E499AF948CF8AAE789FD00"

async def send_cmd(ws, cmd_id, method, params=None):
    msg = {"id": cmd_id, "method": method}
    if params:
        msg["params"] = params
    await ws.send(json.dumps(msg))
    return msg["id"]

async def recv_until(ws, cmd_id, timeout=30):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            r = await asyncio.wait_for(ws.recv(), timeout=deadline - asyncio.get_event_loop().time())
            msg = json.loads(r)
            if msg.get("id") == cmd_id:
                return msg
        except asyncio.TimeoutError:
            break
    return None

async def cdp_fetch():
    async with websockets.connect(PAGE_WS) as ws:
        print("Connected to BI tab")
        await send_cmd(ws, 1, "Runtime.enable")
        await send_cmd(ws, 2, "Page.enable")
        for _ in range(5):
            try:
                await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError:
                break

        await send_cmd(ws, 10, "Runtime.evaluate", {"expression": "location.href", "returnByValue": True})
        resp = await recv_until(ws, 10, timeout=10)
        url = resp.get("result",{}).get("result",{}).get("value","") if resp else ""
        print(f"URL: {url}")
        if "login" in url.lower() or not url:
            print("SSO expired or page not loaded")
            return {"error": "SSO expired"}

        for attempt in range(30):
            await send_cmd(ws, 20+attempt, "Runtime.evaluate", {
                "expression": "typeof window.DashboardController",
                "returnByValue": True
            })
            resp = await recv_until(ws, 20+attempt, timeout=5)
            dc = resp.get("result",{}).get("result",{}).get("value","") if resp else ""
            if dc == "object":
                print(f"DashboardController ready at attempt {attempt+1}")
                break
            await asyncio.sleep(1)
        else:
            print("DashboardController not ready")
            return {"error": "DashboardController not ready"}

        # First, check what date the dashboard is showing
        await send_cmd(ws, 60, "Runtime.evaluate", {
            "expression": """
                (function(){
                    var els = document.querySelectorAll('[class*="date"], [class*="time"], .ant-picker-input input');
                    var texts = [];
                    for(var i=0;i<els.length;i++){
                        var t = els[i].textContent || els[i].value || '';
                        if(t && t.length > 4) texts.push(t);
                    }
                    return texts.slice(0,5);
                })()
            """,
            "returnByValue": True
        })
        resp = await recv_until(ws, 60, timeout=10)
        date_texts = resp.get("result",{}).get("result",{}).get("value",[]) if resp else []
        print(f"Date indicators on page: {date_texts}")

        # Check if Metropolitan filter is applied
        await send_cmd(ws, 61, "Runtime.evaluate", {
            "expression": """
                (function(){
                    var els = document.querySelectorAll('*');
                    for(var i=0;i<els.length;i++){
                        var t = els[i].textContent || '';
                        if(t.includes('Metropolitan') || t.includes('São Paulo')) return t.trim().substring(0,100);
                    }
                    return 'not found';
                })()
            """,
            "returnByValue": True
        })
        resp = await recv_until(ws, 61, timeout=10)
        metro_text = resp.get("result",{}).get("result",{}).get("value","") if resp else ""
        print(f"Metropolitan filter check: {metro_text[:100]}")

        charts = [
            ("Business Performance", "chart-6kwer-1357d"),
            ("New Signs", "chart-e8ns5-c9347"),
            ("Operation Performance", "chart-sqalg-1f515"),
            ("Promotion", "chart-iyhbp-a03a1"),
            ("User Experience", "chart-ltuz6-6cbdc"),
        ]

        results = {}
        cmd_id = 100
        for name, chart_id in charts:
            print(f"Querying {name} ({chart_id})...")
            expr = f'''
                new Promise((resolve) => {{
                    try {{
                        window.DashboardController.executeQueryAndGetCHNResult("{chart_id}")
                            .then(res => resolve({{ok:true, data:JSON.stringify(res)}}))
                            .catch(err => resolve({{ok:false, error:err.message || String(err)}}));
                    }} catch(e) {{
                        resolve({{ok:false, error: "exception: " + e.message}});
                    }}
                }})
            '''
            await send_cmd(ws, cmd_id, "Runtime.evaluate", {
                "expression": expr,
                "awaitPromise": True,
                "returnByValue": True,
                "timeout": 60000
            })
            resp = await recv_until(ws, cmd_id, timeout=70)
            cmd_id += 1
            if not resp:
                print(f"  -> TIMEOUT")
                results[name] = {"error": "timeout"}
                await asyncio.sleep(2)
                continue

            result_obj = resp.get("result",{}).get("result",{})
            val = result_obj.get("value",{})

            if val and val.get("ok"):
                try:
                    data = json.loads(val["data"])
                    results[name] = data
                    if isinstance(data, dict) and data.get("code") == 0:
                        rows = data.get("data",{}).get("data",[])
                        print(f"  -> OK {len(rows)} rows")
                    else:
                        print(f"  -> Response code: {data.get('code', 'N/A')}, msg={data.get('message','')}")
                except Exception as e:
                    print(f"  -> Parse error: {e}")
                    results[name] = {"error": f"parse: {e}"}
            else:
                err = val.get("error", "unknown") if val else str(result_obj)
                print(f"  -> ERROR: {err}")
                results[name] = {"error": err}

            await asyncio.sleep(2)

        has_data = sum(1 for v in results.values() if isinstance(v, dict) and v.get("code") == 0)
        print(f"Charts with data: {has_data}/{len(charts)}")

        if has_data >= 2:
            out = "/mnt/openclaw/.openclaw/workspace/dbr_data_20260820.json"
            with open(out, "w") as f:
                json.dump({"date": "2026-08-20", "data_source":"dom", "results":results, "page_date_indicators": date_texts, "metro_filter": metro_text}, f, ensure_ascii=False, indent=2)
            print(f"Saved to {out}")
            return {"has_data": has_data, "results": results, "data_source": "dom", "date_indicators": date_texts}

        print("DOM insufficient, taking screenshot fallback...")
        await send_cmd(ws, 200, "Page.captureScreenshot", {"format": "png", "fromSurface": True})
        resp = await recv_until(ws, 200, timeout=30)
        if resp:
            data = resp.get("result",{}).get("data","")
            if data:
                import os, base64
                out = "/mnt/openclaw/.openclaw/workspace/dbr_screenshot_20260820.png"
                with open(out, "wb") as f:
                    f.write(base64.b64decode(data))
                print(f"Screenshot saved: {out}")
                return {"data_source": "screenshot", "screenshot": out}

        return {"error": "no data extracted"}

if __name__ == "__main__":
    res = asyncio.run(cdp_fetch())
    print(json.dumps(res, ensure_ascii=False, indent=2)[:500])
