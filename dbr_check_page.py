#!/usr/bin/env python3
"""Check BI page status and refresh if needed"""
import asyncio
import json
import websockets
import subprocess

r = subprocess.run(["curl", "-s", "http://localhost:9222/json/list"], capture_output=True, text=True)
tabs = json.loads(r.stdout)
PAGE_WS = None
for t in tabs:
    if "bi.keetapp" in t.get("url", ""):
        PAGE_WS = t.get("webSocketDebuggerUrl")
        break
if not PAGE_WS:
    print("ERROR: No BI tab found")
    exit(1)

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

async def check_page():
    async with websockets.connect(PAGE_WS) as ws:
        await send_cmd(ws, 1, "Runtime.enable")
        for _ in range(5):
            try:
                await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError:
                break

        # Check current filter values
        expr = """
        (() => {
            try {
                const dc = window.DashboardController;
                if (!dc) return {error: "no DashboardController"};
                const filters = dc.dashboardModel?.filters || dc._dashboardModel?.filters || {};
                const filterList = [];
                for (const [k, v] of Object.entries(filters)) {
                    filterList.push({key: k, value: typeof v === 'object' ? JSON.stringify(v).slice(0,200) : String(v).slice(0,200)});
                }
                return {filters: filterList};
            } catch(e) {
                return {error: e.message};
            }
        })()
        """
        await send_cmd(ws, 100, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
        resp = await recv_until(ws, 100, timeout=15)
        val = resp.get("result",{}).get("result",{}).get("value",{}) if resp else {}
        print("Filters:", json.dumps(val, indent=2, ensure_ascii=False))

        # Try to trigger dashboard refresh
        expr2 = """
        new Promise((resolve) => {
            try {
                const dc = window.DashboardController;
                if (!dc) { resolve({error:"no dc"}); return; }
                if (dc.refreshDashboard) {
                    dc.refreshDashboard().then(() => resolve({ok:"refreshed"})).catch(e => resolve({error:e.message}));
                } else if (dc.refresh) {
                    dc.refresh().then(() => resolve({ok:"refreshed"})).catch(e => resolve({error:e.message}));
                } else {
                    resolve({error:"no refresh method"});
                }
            } catch(e) {
                resolve({error: e.message});
            }
        })
        """
        await send_cmd(ws, 101, "Runtime.evaluate", {"expression": expr2, "awaitPromise": True, "returnByValue": True, "timeout": 60000})
        resp2 = await recv_until(ws, 101, timeout=70)
        val2 = resp2.get("result",{}).get("result",{}).get("value",{}) if resp2 else {}
        print("Refresh:", json.dumps(val2, indent=2, ensure_ascii=False))

        # Wait for data to load
        await asyncio.sleep(10)

        # Check Business Performance data
        expr3 = """
        new Promise((resolve) => {
            window.DashboardController.executeQueryAndGetCHNResult("chart-6kwer-1357d")
                .then(res => resolve({ok:true, count: (res.data?.data?.length || 0), sample: JSON.stringify(res.data?.data?.[0] || {}).slice(0,300)}))
                .catch(err => resolve({ok:false, error: err.message}));
        })
        """
        await send_cmd(ws, 102, "Runtime.evaluate", {"expression": expr3, "awaitPromise": True, "returnByValue": True, "timeout": 60000})
        resp3 = await recv_until(ws, 102, timeout=70)
        val3 = resp3.get("result",{}).get("result",{}).get("value",{}) if resp3 else {}
        print("BP data:", json.dumps(val3, indent=2, ensure_ascii=False))

asyncio.run(check_page())
