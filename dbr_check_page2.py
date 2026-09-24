#!/usr/bin/env python3
"""Deep check BI page state"""
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

async def check():
    async with websockets.connect(PAGE_WS) as ws:
        await send_cmd(ws, 1, "Runtime.enable")
        for _ in range(5):
            try:
                await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError:
                break

        # Check if page has data loading indicators
        expr = """
        (() => {
            const bodyText = document.body?.innerText || '';
            const hasLoading = bodyText.includes('加载') || bodyText.includes('loading') || bodyText.includes('Loading');
            const hasNoData = bodyText.includes('暂无数据') || bodyText.includes('No data') || bodyText.includes('empty');
            const charts = document.querySelectorAll('[class*="chart"], [class*="Chart"], canvas, .ant-table');
            const tables = document.querySelectorAll('table, .ant-table, .s2-table');
            return {
                bodyLength: bodyText.length,
                hasLoading: hasLoading,
                hasNoData: hasNoData,
                chartElements: charts.length,
                tableElements: tables.length,
                url: location.href
            };
        })()
        """
        await send_cmd(ws, 100, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
        resp = await recv_until(ws, 100, timeout=15)
        val = resp.get("result",{}).get("result",{}).get("value",{}) if resp else {}
        print("Page state:", json.dumps(val, indent=2, ensure_ascii=False))

        # Check DashboardController internals
        expr2 = """
        (() => {
            const dc = window.DashboardController;
            if (!dc) return {error: "no DashboardController"};
            const keys = Object.keys(dc);
            const proto = Object.getPrototypeOf(dc);
            const protoKeys = Object.getOwnPropertyNames(proto);
            return {
                keys: keys.slice(0, 30),
                protoKeys: protoKeys.slice(0, 30),
                hasQueryMgr: !!dc.queryManager,
                hasDashModel: !!dc.dashboardModel,
                hasModel: !!dc._dashboardModel,
                hasStore: !!dc.store
            };
        })()
        """
        await send_cmd(ws, 101, "Runtime.evaluate", {"expression": expr2, "returnByValue": True})
        resp2 = await recv_until(ws, 101, timeout=15)
        val2 = resp2.get("result",{}).get("result",{}).get("value",{}) if resp2 else {}
        print("DC internals:", json.dumps(val2, indent=2, ensure_ascii=False))

        # Try queryManager approach
        expr3 = """
        new Promise((resolve) => {
            try {
                const qm = window.DashboardController.queryManager;
                if (!qm) { resolve({error:"no queryManager"}); return; }
                const q = qm.getQuery("chart-6kwer-1357d");
                resolve({hasQuery: !!q, queryKeys: q ? Object.keys(q).slice(0,10) : []});
            } catch(e) {
                resolve({error: e.message});
            }
        })
        """
        await send_cmd(ws, 102, "Runtime.evaluate", {"expression": expr3, "awaitPromise": True, "returnByValue": True})
        resp3 = await recv_until(ws, 102, timeout=15)
        val3 = resp3.get("result",{}).get("result",{}).get("value",{}) if resp3 else {}
        print("Query manager:", json.dumps(val3, indent=2, ensure_ascii=False))

asyncio.run(check())
