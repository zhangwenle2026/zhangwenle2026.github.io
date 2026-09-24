import asyncio, json, websockets, base64, datetime

PAGE_WS = "ws://localhost:9222/devtools/page/30B89CE186B7DF4D7EB7A5EDBC8C0412"

brt_now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
brt_yesterday = (brt_now - datetime.timedelta(days=1)).strftime("%Y%m%d")
brt_2days_ago = (brt_now - datetime.timedelta(days=2)).strftime("%Y%m%d")

TARGET_CHARTS = {
    "Business Performance": "chart-6kwer-1357d",
    "New Signs": "chart-e8ns5-c9347",
    "Operation Performance": "chart-sqalg-1f515",
    "Promotion": "chart-iyhbp-a03a1",
    "User Experience": "chart-ltuz6-6cbdc",
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

async def fetch_data_for_date(ws, date_str):
    """Fetch all target charts for a specific date."""
    # Get date filter key
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
                    break

    if not date_filter_key:
        return {"error": "No date filter found"}

    # Set date filter
    await send_cmd(ws, 70, "Runtime.evaluate", {
        "expression": f"""
            new Promise((resolve) => {{
                try {{
                    window.DashboardController.setFiltersValues([
                        {{
                            "id": "{date_filter_key}",
                            "userInput": {{
                                "value": ["{date_str}", "{date_str}"],
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
            print(f"Set date {date_str}: code={data.get('code')} msg={data.get('message','')}")

    # Wait for charts to refresh
    await asyncio.sleep(15)

    # Query target charts
    results = {}
    cmd_id = 100
    for name, chart_id in TARGET_CHARTS.items():
        print(f"  Querying {name}...")
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
                    print(f"    -> {len(rows)} rows")
                else:
                    print(f"    -> code={data.get('code', 'N/A')}")
            except Exception as e:
                results[name] = {"error": f"parse: {e}"}
        else:
            err = val.get("error", "unknown") if val else str(result_obj)
            results[name] = {"error": err}

        await asyncio.sleep(1)

    has_data = sum(1 for v in results.values() if isinstance(v, dict) and v.get("code") == 0 and len(v.get("data",{}).get("data",[])) > 0)
    total_rows = sum(len(v.get("data",{}).get("data",[])) for v in results.values() if isinstance(v, dict) and v.get("code") == 0)
    print(f"  Total: {has_data}/{len(results)} charts with data, {total_rows} rows")
    return {"has_data": has_data, "total_rows": total_rows, "results": results}

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
            return {"error": "DashboardController not ready"}

        # Try yesterday first
        print(f"\n=== Trying {brt_yesterday} (yesterday) ===")
        result_yesterday = await fetch_data_for_date(ws, brt_yesterday)

        if result_yesterday.get("has_data", 0) >= 2:
            out = f"/mnt/openclaw/.openclaw/workspace/dbr_data_{brt_yesterday}.json"
            with open(out, "w") as f:
                json.dump({"date": brt_yesterday, "data_source":"dom", "results":result_yesterday["results"]}, f, ensure_ascii=False, indent=2)
            print(f"\nSaved to {out}")
            return {"date": brt_yesterday, "has_data": result_yesterday["has_data"], "total_rows": result_yesterday["total_rows"]}

        # Fallback to 2 days ago
        print(f"\n=== Trying {brt_2days_ago} (2 days ago) ===")
        result_2days = await fetch_data_for_date(ws, brt_2days_ago)

        if result_2days.get("has_data", 0) >= 2:
            out = f"/mnt/openclaw/.openclaw/workspace/dbr_data_{brt_2days_ago}.json"
            with open(out, "w") as f:
                json.dump({"date": brt_2days_ago, "data_source":"dom", "results":result_2days["results"]}, f, ensure_ascii=False, indent=2)
            print(f"\nSaved to {out}")
            return {"date": brt_2days_ago, "has_data": result_2days["has_data"], "total_rows": result_2days["total_rows"], "fallback": True}

        return {"error": "No data available for yesterday or 2 days ago"}

result = asyncio.run(main())
print(json.dumps(result, ensure_ascii=False, indent=2))
