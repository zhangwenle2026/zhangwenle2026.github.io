import asyncio, json, websockets

PAGE_WS = "ws://localhost:9222/devtools/page/30B89CE186B7DF4D7EB7A5EDBC8C0412"

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

        # Get filters with full details
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
        if resp:
            result_obj = resp.get("result",{}).get("result",{})
            val = result_obj.get("value",{})
            if val and val.get("ok"):
                filters = json.loads(val["data"])
                for f in filters.get("data",[]):
                    print(f"\nFilter: {f.get('name')} ({f.get('key')})")
                    print(f"  type: {f.get('filterType')}")
                    print(f"  current value: {json.dumps(f.get('filterValue'), ensure_ascii=False)}")
                    opts = f.get('options',[])
                    if opts:
                        print(f"  options ({len(opts)}): {[o.get('value') for o in opts[:10]]}")

        # Try to set org filter with historical value
        print("\n\nSetting org filter to Metropolitan Region...")
        await send_cmd(ws, 70, "Runtime.evaluate", {
            "expression": """
                new Promise((resolve) => {
                    try {
                        // First get all filters to find org-related ones
                        window.DashboardController.getFiltersInfo()
                            .then(filters => {
                                var orgFilter = filters.data.find(f => f.name && f.name.includes('Region'));
                                if (!orgFilter) {
                                    resolve({ok:false, error: 'No Region filter found'});
                                    return;
                                }
                                window.DashboardController.setFiltersValues([
                                    {
                                        "id": orgFilter.key,
                                        "userInput": {
                                            "value": ["Metropolitan Region"],
                                            "isEmpty": false,
                                            "isNoFilter": false,
                                            "isSelectDummyAll": false,
                                            "selectAllFlag": false
                                        }
                                    }
                                ])
                                .then(res => resolve({ok:true, data:JSON.stringify(res)}))
                                .catch(err => resolve({ok:false, error:err.message || String(err)}));
                            })
                            .catch(err => resolve({ok:false, error:err.message || String(err)}));
                    } catch(e) {
                        resolve({ok:false, error: "exception: " + e.message});
                    }
                })
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
                print(f"Set org filter: code={data.get('code')} msg={data.get('message','')}")

        # Wait and query Business Performance
        await asyncio.sleep(10)
        print("\nQuerying Business Performance...")
        await send_cmd(ws, 80, "Runtime.evaluate", {
            "expression": """
                new Promise((resolve) => {
                    try {
                        window.DashboardController.executeQueryAndGetCHNResult(["chart-6kwer-1357d"])
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
        resp = await recv_until(ws, 80, timeout=70)
        if resp:
            result_obj = resp.get("result",{}).get("result",{})
            val = result_obj.get("value",{})
            if val and val.get("ok"):
                data = json.loads(val["data"])
                rows = data.get("data",{}).get("data",[])
                print(f"  -> {len(rows)} rows")
                if rows:
                    print(f"  sample: {rows[0]}")

asyncio.run(main())
