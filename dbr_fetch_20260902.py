#!/usr/bin/env python3
"""DBR data fetch for 2026-09-02 (BRT) - using current BI tab via CDP"""
import asyncio
import json
import websockets
import datetime

DATA_DATE = "20260902"

# Get the correct tab ID from CDP
import subprocess
result = subprocess.run(
    ["curl", "-s", "http://localhost:9222/json/list"],
    capture_output=True, text=True
)
tabs = json.loads(result.stdout)
PAGE_WS = None
for t in tabs:
    if "bi.keetapp" in t.get("url", ""):
        PAGE_WS = t.get("webSocketDebuggerUrl")
        break

if not PAGE_WS:
    print("ERROR: No BI tab found")
    exit(1)

print(f"Using CDP: {PAGE_WS}")

charts = [
    ("Business Performance", "chart-6kwer-1357d"),
    ("New Signs", "chart-e8ns5-c9347"),
    ("Operation Performance", "chart-sqalg-1f515"),
    ("Promotion", "chart-iyhbp-a03a1"),
    ("User Experience", "chart-ltuz6-6cbdc"),
]

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

        # Give extra time for data to load
        await asyncio.sleep(5)

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
            out = f"/mnt/openclaw/.openclaw/workspace/dbr_data_{DATA_DATE}.json"
            with open(out, "w") as f:
                json.dump({"date": DATA_DATE, "data_source":"dom", "results":results}, f, ensure_ascii=False, indent=2)
            print(f"Saved to {out}")
            return {"has_data": has_data, "results": results, "data_source": "dom", "date": DATA_DATE}

        return {"error": "no data extracted"}

if __name__ == "__main__":
    res = asyncio.run(cdp_fetch())
    print(json.dumps(res, ensure_ascii=False, indent=2)[:500])
