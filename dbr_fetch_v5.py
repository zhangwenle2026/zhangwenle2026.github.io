import asyncio, json, websockets, base64, datetime

PAGE_WS = "ws://localhost:9222/devtools/page/30B89CE186B7DF4D7EB7A5EDBC8C0412"

brt_now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
brt_yesterday = (brt_now - datetime.timedelta(days=1)).strftime("%Y%m%d")
DATA_DATE = brt_yesterday

TARGET_CHARTS = {
    "Business Performance": "chart-6kwer-1357d",
    "New Signs": "chart-e8ns5-c9347",
    "Operation Performance": "chart-sqalg-1f515",
    "Promotion": "chart-iyhbp-a03a1",
    "User Experience": "chart-ltuz6-6cbdc",
}

# Org filter IDs from historical data
ORG_2_ID = "65280006_zhangwenle"

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

        # Check URL
        await send_cmd(ws, 5, "Runtime.evaluate", {"expression": "location.href", "returnByValue": True})
        resp = await recv_until(ws, 5, timeout=10)
        url = resp.get("result",{}).get("result",{}).get("value","") if resp else ""
        print(f"Current URL: {url}")

        if "login" in url.lower():
            print("SSO expired!")
            return {"error": "SSO expired"}

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

        # Get all filter IDs first
        print("\nGetting filter IDs...")
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
        filter_map = {}
        if resp:
            result_obj = resp.get("result",{}).get("result",{})
            val = result_obj.get("value",{})
            if val and val.get("ok"):
                filters = json.loads(val["data"])
                for f in filters.get("data",[]):
                    filter_map[f.get("name","")] = f.get("key")
                    print(f"  Filter: {f.get('name')} = {f.get('key')} (type={f.get('filterType')})")

        # Build filter settings
        date_key = filter_map.get("Date")
        org2_key = None
        for k, v in filter_map.items():
            if "二级" in k or "org_2" in k.lower():
                org2_key = v
                break

        # Set date and org filters
        filter_settings = []
        if date_key:
            filter_settings.append({
                "id": date_key,
                "userInput": {
                    "value": [DATA_DATE, DATA_DATE],
                    "granularity": "DAY"
                }
            })

        # Also set org filter if we can find it
        if org2_key:
            filter_settings.append({
                "id": org2_key,
                "userInput": {
                    "value": [ORG_2_ID],
                    "isEmpty": False,
                    "isNoFilter": False,
                    "isSelectDummyAll": False,
                    "selectAllFlag": False
                }
            })

        if filter_settings:
            print(f"\nSetting {len(filter_settings)} filters...")
            expr = f"""
                new Promise((resolve) => {{
                    try {{
                        window.DashboardController.setFiltersValues({json.dumps(filter_settings)})
                            .then(res => resolve({{ok:true, data:JSON.stringify(res)}}))
                            .catch(err => resolve({{ok:false, error:err.message || String(err)}}));
                    }} catch(e) {{
                        resolve({{ok:false, error: "exception: " + e.message}});
                    }}
                }})
            """
            await send_cmd(ws, 70, "Runtime.evaluate", {
                "expression": expr,
                "awaitPromise": True,
                "returnByValue": True
            })
            resp = await recv_until(ws, 70, timeout=30)
            if resp:
                result_obj = resp.get("result",{}).get("result",{})
                val = result_obj.get("value",{})
                if val and val.get("ok"):
                    data = json.loads(val["data"])
                    print(f"Set filters: code={data.get('code')} msg={data.get('message','')}")

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

        # Save results
        has_data = sum(1 for v in results.values() if isinstance(v, dict) and v.get("code") == 0 and len(v.get("data",{}).get("data",[])) > 0)
        total_rows = sum(len(v.get("data",{}).get("data",[])) for v in results.values() if isinstance(v, dict) and v.get("code") == 0)
        print(f"\nTotal charts with data: {has_data}/{len(results)}, total rows: {total_rows}")

        if has_data >= 1:
            out = f"/mnt/openclaw/.openclaw/workspace/dbr_data_{DATA_DATE}.json"
            with open(out, "w") as f:
                json.dump({"date": DATA_DATE, "data_source":"dom", "results":results}, f, ensure_ascii=False, indent=2)
            print(f"Saved to {out}")
            return {"has_data": has_data, "total_rows": total_rows, "results": results, "date": DATA_DATE}

        # Screenshot fallback
        print("DOM insufficient, taking screenshot...")
        await send_cmd(ws, 200, "Page.captureScreenshot", {"format": "png", "fromSurface": True})
        resp = await recv_until(ws, 200, timeout=30)
        if resp:
            data = resp.get("result",{}).get("data","")
            if data:
                out = f"/mnt/openclaw/.openclaw/workspace/dbr_screenshot_{DATA_DATE}.png"
                with open(out, "wb") as f:
                    f.write(base64.b64decode(data))
                print(f"Screenshot saved: {out}")
                return {"data_source": "screenshot", "screenshot": out}

        return {"error": "no data extracted"}

result = asyncio.run(main())
print(json.dumps(result, ensure_ascii=False, indent=2)[:500])
