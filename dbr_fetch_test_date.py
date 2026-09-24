import asyncio, json, websockets, datetime

PAGE_WS = "ws://localhost:9222/devtools/page/30B89CE186B7DF4D7EB7A5EDBC8C0412"

TEST_DATE = "20260828"

TARGET_CHARTS = {
    "Business Performance": "chart-6kwer-1357d",
    "New Signs": "chart-e8ns5-c9347",
}

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

async def main():
    async with websockets.connect(PAGE_WS) as ws:
        print("Connected")
        await send_cmd(ws, 1, "Runtime.enable")
        await send_cmd(ws, 2, "Page.enable")
        for _ in range(5):
            try:
                await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError:
                break

        # Reload the page completely
        print("Reloading page...")
        await send_cmd(ws, 10, "Page.reload", {"ignoreCache": True})
        await asyncio.sleep(15)

        # Wait for DashboardController
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

        # Check URL
        await send_cmd(ws, 55, "Runtime.evaluate", {"expression": "location.href", "returnByValue": True})
        resp = await recv_until(ws, 55, timeout=10)
        url = resp.get("result",{}).get("result",{}).get("value","") if resp else ""
        print(f"Current URL: {url}")

        if "login" in url.lower():
            print("SSO expired!")
            return {"error": "SSO expired"}

        # Get filters
        print("\nGetting filters...")
        await send_cmd(ws, 60, "Runtime.evaluate", {
            "expression": """
                new Promise((resolve) => {
                    try {
                        window.DashboardController.getFiltersInfo()
                            .then(res => resolve({ok:true, data:JSON.stringify(res)}))
                            .catch(err => resolve({ok:false, error:err.message || String(err)}));
                    } catch(e) {
                        resolve({ok:false, error: "exception: " + e.message});
                    }
                })
            """,
            "awaitPromise": True,
            "returnByValue": True
        })
        resp = await recv_until(ws, 60, timeout=30)
        date_filter_key = None
        if resp:
            result_obj = resp.get("result",{}).get("result",{})
            val = result_obj.get("value",{})
            if val and val.get("ok"):
                filters = json.loads(val["data"])
                for f in filters.get("data",[]):
                    if f.get("filterType") == "time":
                        date_filter_key = f.get("key")
                        print(f"Date filter: {f.get('key')} current={f.get('filterValue')}")
                        break

        # Set date filter to test date (2026-08-28)
        if date_filter_key:
            print(f"\nSetting date filter to {TEST_DATE}...")
            await send_cmd(ws, 70, "Runtime.evaluate", {
                "expression": f"""
                    new Promise((resolve) => {{
                        try {{
                            window.DashboardController.setFiltersValues([
                                {{
                                    "id": "{date_filter_key}",
                                    "userInput": {{
                                        "value": ["{TEST_DATE}", "{TEST_DATE}"],
                                        "granularity": "DAY"
                                    }}
                                }}
                            ])
                            .then(res => resolve({{ok:true, data:JSON.stringify(res)}}))
                            .catch(err => resolve({{ok:false, error:err.message || String(err)}}));
                        }} catch(e) {{
                            resolve({{ok:false, error: "exception: " + e.message}});
                        }}
                    }})
                """,
                "awaitPromise": True,
                "returnByValue": True
            })
            resp = await recv_until(ws, 70, timeout=30)
            if resp:
                result_obj = resp.get("result",{}).get("result",{})
                val = result_obj.get("value",{})
                if val and val.get("ok"):
                    data = json.loads(val["data"])
                    print(f"Set filter: code={data.get('code')} msg={data.get('message','')}")

        # Wait for charts to refresh
        print("\nWaiting 20s for charts to refresh...")
        await asyncio.sleep(20)

        # Query target charts
        results = {}
        cmd_id = 100
        for name, chart_id in TARGET_CHARTS.items():
            print(f"\nQuerying {name} ({chart_id})...")
            expr = f'''
                new Promise((resolve) => {{
                    try {{
                        window.DashboardController.executeQueryAndGetCHNResult(["{chart_id}"])
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
                continue

            result_obj = resp.get("result",{}).get("result",{})
            val = result_obj.get("value",{})

            if val and val.get("ok"):
                try:
                    data = json.loads(val["data"])
                    results[name] = data
                    if isinstance(data, dict) and data.get("code") == 0:
                        rows = data.get("data",{}).get("data",[])
                        cols = data.get("data",{}).get("columns",[])
                        print(f"  -> OK {len(rows)} rows, cols: {cols[:5]}")
                        if rows:
                            print(f"  sample: {str(rows[0])[:150]}")
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

        has_data = sum(1 for v in results.values() if isinstance(v, dict) and v.get("code") == 0 and len(v.get("data",{}).get("data",[])) > 0)
        print(f"\nTotal charts with data: {has_data}/{len(results)}")
        return results

result = asyncio.run(main())
print(json.dumps(result, ensure_ascii=False, indent=2)[:500])
