#!/usr/bin/env python3
"""DBR Daily Report - CDP DashboardController data fetcher."""
import asyncio, json, urllib.request, urllib.parse, websockets, os, sys, time, datetime

DATA_DATE = "2026-08-24"
TARGET_TAB_ID = "C52CA7B272E499AF948CF8AAE789FD00"

async def cdp_send(ws, session_id, method, params=None, msg_id=None):
    msg_id = msg_id or int(time.time() * 1000)
    cmd = {"id": msg_id, "method": method}
    if params:
        cmd["params"] = params
    if session_id:
        cmd["sessionId"] = session_id
    await ws.send(json.dumps(cmd))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == msg_id:
            return resp
        # Skip notifications like Target.attachedToTarget

async def eval_js(ws, session_id, js_code, await_promise=True):
    resp = await cdp_send(ws, session_id, "Runtime.evaluate", {
        "expression": js_code,
        "returnByValue": True,
        "awaitPromise": await_promise
    })
    result = resp.get("result", {}).get("result", {})
    if result.get("type") == "undefined":
        return None
    if "value" in result:
        return result["value"]
    return result

async def main():
    version_info = json.loads(urllib.request.urlopen("http://localhost:9222/json/version").read())
    ws_url = version_info["webSocketDebuggerUrl"]
    print(f"[1] Browser WS: {ws_url}")

    async with websockets.connect(ws_url, open_timeout=5, close_timeout=5) as ws:
        # Attach to target - use auto-increment id
        msg_id = 10
        await ws.send(json.dumps({"id": msg_id, "method": "Target.attachToTarget",
            "params": {"targetId": TARGET_TAB_ID, "flatten": True}}))
        session_id = None
        # First message might be the Target.attachedToTarget notification
        while True:
            resp = json.loads(await ws.recv())
            if resp.get("id") == msg_id:
                if "error" in resp:
                    print(f"Attach error: {resp['error']}")
                    sys.exit(1)
                session_id = resp["result"]["sessionId"]
                break
            elif resp.get("method") == "Target.attachedToTarget":
                session_id = resp["params"]["sessionId"]
                break
        print(f"[2] Attached, sessionId={session_id}")

        # Wait for DashboardController
        print("[3] Waiting for DashboardController...")
        for _ in range(30):
            dc_exists = await eval_js(ws, session_id, "typeof window.DashboardController !== 'undefined'")
            if dc_exists:
                print("[3] ✅ DashboardController ready")
                break
            await asyncio.sleep(1)
        else:
            print("❌ DashboardController not mounted after 30s")
            sys.exit(1)

        # Get components
        print("[4] Getting components...")
        comps = await eval_js(ws, session_id,
            "window.DashboardController.getComponents().then(res => JSON.stringify(res))", await_promise=True)
        if isinstance(comps, str):
            comps = json.loads(comps)
        print(f"[4] Components code={comps.get('code')}, count={len(comps.get('data', []))}")

        with open("/mnt/openclaw/.openclaw/workspace/dbr_components.json", "w") as f:
            json.dump(comps, f, indent=2, ensure_ascii=False)

        charts = [c for c in comps.get("data", []) if c.get("componentType") == "chart"]
        filters = [c for c in comps.get("data", []) if c.get("componentType") == "filter"]
        tabs = [c for c in comps.get("data", []) if c.get("componentType") == "tab"]
        print(f"  Charts: {len(charts)}, Filters: {len(filters)}, Tabs: {len(tabs)}")
        for c in charts:
            print(f"    📊 {c['componentName']} -> {c['componentId']}")
        for f in filters:
            print(f"    🔍 {f['componentName']} -> {f['componentId']} ({f.get('extends',{}).get('filterType','')})")

        # Get filters info
        print("[5] Getting filters info...")
        filter_ids = [f["componentId"] for f in filters]
        filters_info = await eval_js(ws, session_id,
            f"window.DashboardController.getFiltersInfo({json.dumps(filter_ids)}).then(res => JSON.stringify(res))", await_promise=True)
        if isinstance(filters_info, str):
            filters_info = json.loads(filters_info)
        print(f"[5] Filters code={filters_info.get('code')}")
        for fd in filters_info.get("data", []):
            print(f"    🔍 {fd['name']}: type={fd.get('filterType')}, value={fd.get('filterValue')}")

        # Check date filter
        date_filter = next((f for f in filters_info.get("data", []) if f.get("filterType") == "time" and "date" in f.get("name","").lower()), None)
        if not date_filter:
            date_filter = next((f for f in filters_info.get("data", []) if f.get("filterType") == "time"), None)

        if date_filter:
            fv = date_filter.get("filterValue", [])
            needs_update = True
            if len(fv) == 2 and fv[0].get("offset") == -1 and fv[1].get("offset") == -1:
                needs_update = False
                print(f"[6] Date filter already set to yesterday (-1 to -1).")
            if needs_update:
                print(f"[6] Setting date filter to yesterday...")
                set_res = await eval_js(ws, session_id,
                    f"window.DashboardController.setFiltersValues([{{'id':'{date_filter['key']}','userInput':{{'value':[{{'offset':-1,'granularity':'DAY','type':'OFFSET'}},{{'offset':-1,'granularity':'DAY','type':'OFFSET'}}],'granularity':'DAY'}}}}]).then(res => JSON.stringify(res))", await_promise=True)
                if isinstance(set_res, str):
                    set_res = json.loads(set_res)
                print(f"[6] Set filter result: {set_res}")
        else:
            print("[6] ⚠️ No date filter found")

        # Check region filter
        region_filter = next((f for f in filters_info.get("data", []) if "region" in f.get("name","").lower() or "metropolitan" in f.get("name","").lower()), None)
        if region_filter:
            print(f"[7] Region filter: {region_filter['name']} = {region_filter.get('filterValue')}")

        # Trigger queries for all charts
        print("[8] Triggering queries for all charts...")
        query_results = {}
        for c in charts:
            cid = c["componentId"]
            cname = c["componentName"]
            try:
                res = await eval_js(ws, session_id,
                    f"window.DashboardController.executeQueryAndGetCHNResult('{cid}').then(res => JSON.stringify(res))", await_promise=True)
                if isinstance(res, str):
                    res = json.loads(res)
                query_results[cid] = {"name": cname, "code": res.get("code", -1), "has_data": bool(res.get("data"))}
                status = "✅" if res.get("code") == 0 else "❌"
                print(f"    {status} {cname}: code={res.get('code')}, has_data={bool(res.get('data'))}")
            except Exception as e:
                query_results[cid] = {"name": cname, "error": str(e)}
                print(f"    ❌ {cname}: ERROR {e}")

        # Get download links
        print("[9] Getting download links...")
        download_links = {}
        for c in charts:
            cid = c["componentId"]
            cname = c["componentName"]
            try:
                res = await eval_js(ws, session_id,
                    f"window.DashboardController.executeDownload('{cid}', {{'fileType':'CSV'}}).then(res => JSON.stringify(res))", await_promise=True)
                if isinstance(res, str):
                    res = json.loads(res)
                if res and res.get("code") == 0 and res.get("data"):
                    download_links[cid] = {"name": cname, "url": res["data"]}
                    print(f"    ✅ {cname}: {res['data'][:80]}...")
                else:
                    print(f"    ⚠️ {cname}: no download link (code={res.get('code') if res else 'null'})")
            except Exception as e:
                print(f"    ❌ {cname}: ERROR {e}")

        # Save JSON
        result = {
            "data_date": DATA_DATE,
            "dashboard_id": "300001446",
            "timestamp": datetime.datetime.now().isoformat(),
            "components": comps.get("data", []),
            "filters_info": filters_info.get("data", []),
            "query_results": query_results,
            "download_links": download_links
        }
        out_path = "/mnt/openclaw/.openclaw/workspace/dbr_data_20260824.json"
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[10] Results saved to {out_path}")

        # Download CSV files
        print("[11] Downloading CSV files...")
        download_dir = "/mnt/openclaw/.openclaw/workspace/dbr_csvs"
        os.makedirs(download_dir, exist_ok=True)
        for cid, info in download_links.items():
            url = info["url"]
            safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in info["name"])[:50]
            fname = f"{safe_name}_{cid.split('-')[-1]}.csv"
            fpath = os.path.join(download_dir, fname)
            try:
                urllib.request.urlretrieve(url, fpath)
                size = os.path.getsize(fpath)
                print(f"    ✅ {info['name']} -> {fname} ({size} bytes)")
            except Exception as e:
                print(f"    ❌ {info['name']}: download failed: {e}")

        print("[DONE] All steps completed.")

if __name__ == "__main__":
    asyncio.run(main())
