#!/usr/bin/env python3
"""Refresh BI page and fetch data for 2026-08-20"""
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

        # Refresh the page
        print("Refreshing page...")
        await send_cmd(ws, 3, "Page.reload", {"ignoreCache": True})
        await asyncio.sleep(8)
        
        # Drain events
        for _ in range(10):
            try:
                await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError:
                break

        await send_cmd(ws, 10, "Runtime.evaluate", {"expression": "location.href", "returnByValue": True})
        resp = await recv_until(ws, 10, timeout=10)
        url = resp.get("result",{}).get("result",{}).get("value","") if resp else ""
        print(f"URL after refresh: {url}")
        if "login" in url.lower():
            print("SSO expired after refresh")
            return {"error": "SSO expired"}

        # Wait for DashboardController
        for attempt in range(40):
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
            return {"error": "DashboardController not ready"}

        # Give extra time for data to load
        await asyncio.sleep(5)

        # Query BP first to check date
        await send_cmd(ws, 100, "Runtime.evaluate", {
            "expression": '''
                new Promise((resolve) => {
                    try {
                        window.DashboardController.executeQueryAndGetCHNResult("chart-6kwer-1357d")
                            .then(res => resolve({ok:true, data:JSON.stringify(res)}))
                            .catch(err => resolve({ok:false, error:err.message || String(err)}));
                    } catch(e) {
                        resolve({ok:false, error: "exception: " + e.message});
                    }
                })
            ''',
            "awaitPromise": True,
            "returnByValue": True,
            "timeout": 60000
        })
        resp = await recv_until(ws, 100, timeout=70)
        if resp:
            val = resp.get("result",{}).get("result",{}).get("value",{})
            if val and val.get("ok"):
                data = json.loads(val["data"])
                rows = data.get("data",{}).get("data",[])
                dates = set(r[0] for r in rows)
                print(f"BP dates after refresh: {dates}")
                if "20260820" in dates:
                    print("Aug 20 data is available!")
                else:
                    print("Aug 20 data NOT available, using latest available")

        # Query all charts
        charts = [
            ("Business Performance", "chart-6kwer-1357d"),
            ("New Signs", "chart-e8ns5-c9347"),
            ("Operation Performance", "chart-sqalg-1f515"),
            ("Promotion", "chart-iyhbp-a03a1"),
            ("User Experience", "chart-ltuz6-6cbdc"),
        ]

        results = {}
        cmd_id = 200
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
                        dates = set(r[0] for r in rows[:5])
                        print(f"  -> OK {len(rows)} rows, dates: {list(dates)[:3]}")
                    else:
                        print(f"  -> Response code: {data.get('code', 'N/A')}")
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
                json.dump({"date": "2026-08-20", "data_source":"dom", "results":results}, f, ensure_ascii=False, indent=2)
            print(f"Saved to {out}")
            return {"has_data": has_data, "results": results, "data_source": "dom"}

        return {"error": "no data extracted"}

if __name__ == "__main__":
    res = asyncio.run(cdp_fetch())
    print(json.dumps(res, ensure_ascii=False, indent=2)[:500])
