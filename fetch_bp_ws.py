#!/usr/bin/env python3
"""Fetch BP dashboard data using CDP with proper request/response matching"""
import asyncio
import json
import websockets
from datetime import datetime, timedelta

TARGET_CHARTS = [
    ("CM - Business Performance", "chart-6kwer-1357d"),
    ("BDM - Business Performance", "chart-stq7y-e6570"),
    ("BD - Business Performance", "dashboard-chart-container-fgaiv-e51fa"),
    ("SMB - MTD Merchant Ranking", "chart-budz2-630e8"),
    ("Last 10 Days - Order Performance", "dashboard-chart-container-7p18g-b0ef9"),
    ("Last 10 days - New Signs", "chart-e8ns5-c9347"),
    ("Last 10 days - Operation Performance", "chart-sqalg-1f515"),
    ("Last 10 days - User Experience", "chart-ltuz6-6cbdc"),
    ("Last 10 days - Promotion", "chart-iyhbp-a03a1"),
]

WS_URL = "ws://127.0.0.1:9222/devtools/page/47DD593784802B11FBF1348C3410BFF8"

class CDPClient:
    def __init__(self, ws):
        self.ws = ws
        self._id = 0
        self._pending = {}
        self._listener = None

    async def start(self):
        self._listener = asyncio.create_task(self._read_loop())

    async def stop(self):
        if self._listener:
            self._listener.cancel()
            try:
                await self._listener
            except asyncio.CancelledError:
                pass

    async def _read_loop(self):
        async for msg in self.ws:
            data = json.loads(msg)
            msg_id = data.get("id")
            if msg_id is not None and msg_id in self._pending:
                self._pending[msg_id].set_result(data)

    async def send(self, method, params=None):
        self._id += 1
        cmd_id = self._id
        future = asyncio.get_event_loop().create_future()
        self._pending[cmd_id] = future
        await self.ws.send(json.dumps({"id": cmd_id, "method": method, "params": params or {}}))
        return await asyncio.wait_for(future, timeout=30)

    async def evaluate(self, expression):
        await self.send("Runtime.enable")
        resp = await self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True
        })
        result = resp.get("result", {}).get("result", {})
        if result.get("type") == "string":
            return result.get("value", "")
        return result.get("value")

async def fetch():
    print(f"[{datetime.now()}] Connecting...")
    async with websockets.connect(WS_URL) as ws:
        client = CDPClient(ws)
        await client.start()
        
        print("Checking DashboardController...")
        has_dc = await client.evaluate("typeof window.DashboardController !== 'undefined'")
        print(f"DashboardController: {has_dc}")
        
        if not has_dc:
            for i in range(10):
                await asyncio.sleep(2)
                has_dc = await client.evaluate("typeof window.DashboardController !== 'undefined'")
                if has_dc:
                    print("DashboardController ready after wait")
                    break
            if not has_dc:
                print("Still not available")
                await client.stop()
                return {}
        
        # Set date filters
        end_date = datetime.now()
        start = (end_date - timedelta(days=9)).strftime('%Y-%m-%d')
        end = end_date.strftime('%Y-%m-%d')
        print(f"Date range: {start} ~ {end}")
        
        filters_raw = await client.evaluate("""
        (async () => {
            const res = await window.DashboardController.getFiltersInfo();
            return JSON.stringify(res);
        })()
        """)
        filters_data = json.loads(filters_raw)
        
        date_filter_updates = []
        for f in filters_data.get("data", []):
            if f.get("filterType") == "time":
                date_filter_updates.append({
                    "id": f["key"],
                    "userInput": {
                        "value": [start, end],
                        "granularity": "DAY"
                    }
                })
        
        if date_filter_updates:
            set_raw = await client.evaluate(f"""
            (async () => {{
                const res = await window.DashboardController.setFiltersValues({json.dumps(date_filter_updates)});
                return JSON.stringify(res);
            }})()
            """)
            print(f"Set filters: {json.loads(set_raw).get('code', '?')}")
            await asyncio.sleep(3)
        
        results = {}
        for name, cid in TARGET_CHARTS:
            print(f"Querying: {name}")
            try:
                data_raw = await asyncio.wait_for(
                    client.evaluate(f"""
                    (async () => {{
                        const res = await window.DashboardController.executeQueryAndGetCHNResult(['{cid}'], {{force: true}});
                        return JSON.stringify(res);
                    }})()
                    """),
                    timeout=45
                )
                data = json.loads(data_raw)
                results[name] = data
                rows = len(data.get("data", {}).get("data", [])) if data.get("code") == 0 else 0
                print(f"  -> {'OK' if data.get('code')==0 else 'ERR'}, {rows} rows")
            except asyncio.TimeoutError:
                print(f"  -> TIMEOUT")
                results[name] = {"code": -2, "message": "timeout"}
            except Exception as e:
                print(f"  -> Exception: {e}")
                results[name] = {"code": -1, "message": str(e)}
            await asyncio.sleep(1)
        
        await client.stop()
        return results

async def main():
    results = await fetch()
    output_path = "/mnt/openclaw/.openclaw/workspace/bi_raw_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {output_path}")
    for name, data in results.items():
        status = "OK" if data.get("code") == 0 else f"ERR({data.get('code')})"
        rows = len(data.get("data", {}).get("data", [])) if data.get("code") == 0 else 0
        print(f"  {name}: {status}, {rows} rows")

if __name__ == "__main__":
    asyncio.run(main())
