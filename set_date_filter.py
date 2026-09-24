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
        print("Connected, enabling domains...")
        await send_cmd(ws, 1, "Runtime.enable")
        await send_cmd(ws, 2, "Page.enable")
        for _ in range(5):
            try:
                await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError:
                break
        
        # Get current filters
        print("Getting filters info...")
        await send_cmd(ws, 10, "Runtime.evaluate", {
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
        resp = await recv_until(ws, 10, timeout=30)
        if resp:
            result_obj = resp.get("result",{}).get("result",{})
            val = result_obj.get("value",{})
            if val and val.get("ok"):
                filters = json.loads(val["data"])
                print(f"Filters count: {len(filters)}")
                for f in filters[:10]:
                    print(f"  id={f.get('id')} name={f.get('name')} type={f.get('type')} value={str(f.get('value',''))[:80]}")
        
        # Try setting date filter
        print(f"\nSetting date filter to {DATA_DATE}...")
        await send_cmd(ws, 20, "Runtime.evaluate", {
            "expression": f"""
                new Promise((resolve) => {{
                    try {{
                        // Find date filter
                        var filters = window.DashboardController.getFiltersInfoSync ? window.DashboardController.getFiltersInfoSync() : [];
                        var dateFilter = filters.find(f => f.type === 'date' || (f.name && f.name.toLowerCase().includes('date')));
                        if (!dateFilter) {{
                            // Try all filters
                            resolve({{ok:false, error: 'No date filter found. Available: ' + filters.map(f=>f.name||f.id).join(', ')}});
                            return;
                        }}
                        window.DashboardController.setFiltersValues({{[dateFilter.id]: {{type: 'date', value: ['{DATA_DATE}', '{DATA_DATE}']}}}})
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
        resp = await recv_until(ws, 20, timeout=30)
        if resp:
            result_obj = resp.get("result",{}).get("result",{})
            val = result_obj.get("value",{})
            if val:
                print(f"Set filter result: ok={val.get('ok')} error={val.get('error','none')}")
            else:
                print(f"Set filter result: {result_obj}")
        
        # Wait for charts to refresh
        print("Waiting 15s for charts to refresh...")
        await asyncio.sleep(15)
        
        # Query Business Performance
        print("\nQuerying Business Performance...")
        await send_cmd(ws, 30, "Runtime.evaluate", {
            "expression": """
                new Promise((resolve) => {
                    try {
                        window.DashboardController.executeQueryAndGetCHNResult("chart-6kwer-1357d")
                            .then(res => resolve({ok:true, data:JSON.stringify(res)}))
                            .catch(err => resolve({ok:false, error:err.message || String(err)}));
                    } catch(e) {
                        resolve({ok:false, error: "exception: " + e.message});
                    }
                })
            """,
            "awaitPromise": True,
            "returnByValue": True,
            "timeout": 60000
        })
        resp = await recv_until(ws, 30, timeout=70)
        if resp:
            result_obj = resp.get("result",{}).get("result",{})
            val = result_obj.get("value",{})
            if val and val.get("ok"):
                data = json.loads(val["data"])
                rows = data.get("data",{}).get("data",[])
                print(f"  -> {len(rows)} rows")
                if rows:
                    print(f"  sample: {rows[0][:6]}")
            else:
                err = val.get("error", "unknown") if val else str(result_obj)
                print(f"  -> ERROR: {err}")

asyncio.run(main())
