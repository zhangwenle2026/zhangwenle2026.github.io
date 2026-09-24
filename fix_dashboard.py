import asyncio, json, websockets, datetime

PAGE_WS = "ws://localhost:9222/devtools/page/30B89CE186B7DF4D7EB7A5EDBC8C0412"

brt_now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
brt_yesterday = (brt_now - datetime.timedelta(days=1)).strftime("%Y%m%d")
DATA_DATE = brt_yesterday

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

        # Step 1: Navigate to the correct controller page
        print("Navigating to controller page...")
        target_url = "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446"
        await send_cmd(ws, 10, "Page.navigate", {"url": target_url})
        await asyncio.sleep(10)

        # Step 2: Wait for DashboardController
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

        # Step 3: Check URL
        await send_cmd(ws, 55, "Runtime.evaluate", {"expression": "location.href", "returnByValue": True})
        resp = await recv_until(ws, 55, timeout=10)
        url = resp.get("result",{}).get("result",{}).get("value","") if resp else ""
        print(f"Current URL: {url}")

        if "login" in url.lower():
            print("SSO expired!")
            return {"error": "SSO expired"}

        # Step 4: Get filters
        print("Getting filters...")
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
        filters = []
        if resp:
            result_obj = resp.get("result",{}).get("result",{})
            val = result_obj.get("value",{})
            if val and val.get("ok"):
                filters = json.loads(val["data"])
                print(f"Found {len(filters)} filters")
                for f in filters:
                    print(f"  id={f.get('key')} name={f.get('name')} type={f.get('filterType')} value={str(f.get('filterValue',''))[:60]}")

        # Step 5: Set date filter to yesterday
        date_filter = None
        for f in filters:
            if f.get('filterType') == 'time' or (f.get('name') and 'date' in f.get('name','').lower()):
                date_filter = f
                break

        if not date_filter and filters:
            date_filter = filters[0]  # fallback to first filter

        if date_filter:
            print(f"\nSetting date filter {date_filter.get('key')} to {DATA_DATE}...")
            await send_cmd(ws, 70, "Runtime.evaluate", {
                "expression": f"""
                    new Promise((resolve) => {{
                        try {{
                            window.DashboardController.setFiltersValues([
                                {{
                                    "id": "{date_filter.get('key')}",
                                    "userInput": {{
                                        "value": ["{DATA_DATE}", "{DATA_DATE}"],
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
                if val:
                    print(f"Set filter result: ok={val.get('ok')} error={val.get('error','none')}")
                    if val.get('ok'):
                        data = json.loads(val["data"])
                        print(f"  code={data.get('code')} msg={data.get('message','')}")

        # Step 6: Wait for charts to refresh
        print("\nWaiting 20s for charts to refresh...")
        await asyncio.sleep(20)

        # Step 7: Get components to find chart IDs
        print("\nGetting components...")
        await send_cmd(ws, 80, "Runtime.evaluate", {
            "expression": """
                new Promise((resolve) => {
                    try {
                        window.DashboardController.getComponents()
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
        resp = await recv_until(ws, 80, timeout=30)
        chart_ids = []
        if resp:
            result_obj = resp.get("result",{}).get("result",{})
            val = result_obj.get("value",{})
            if val and val.get("ok"):
                comps = json.loads(val["data"])
                for c in comps.get("data",[]):
                    if c.get("componentType") == "chart":
                        chart_ids.append((c.get("componentName","unnamed"), c.get("componentId")))
                print(f"Found {len(chart_ids)} charts")
                for name, cid in chart_ids[:10]:
                    print(f"  {name}: {cid}")

        # Step 8: Query all charts
        results = {}
        cmd_id = 100
        for name, chart_id in chart_ids[:10]:
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

        # Step 9: Save results
        has_data = sum(1 for v in results.values() if isinstance(v, dict) and v.get("code") == 0)
        print(f"\nTotal charts with data: {has_data}/{len(results)}")

        if has_data >= 1:
            out = f"/mnt/openclaw/.openclaw/workspace/dbr_data_{DATA_DATE}.json"
            with open(out, "w") as f:
                json.dump({"date": DATA_DATE, "data_source":"dom", "results":results}, f, ensure_ascii=False, indent=2)
            print(f"Saved to {out}")
            return {"has_data": has_data, "results": results, "date": DATA_DATE}

        return {"error": "no data extracted"}

result = asyncio.run(main())
print(json.dumps(result, ensure_ascii=False, indent=2)[:500])
