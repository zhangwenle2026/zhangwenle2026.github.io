import json
with open('/mnt/openclaw/.openclaw/workspace/dbr_data_20260828.json') as f:
    data = json.load(f)

for name, v in data.get('results',{}).items():
    if isinstance(v, dict) and v.get('code') == 0:
        rows = v.get('data',{}).get('data',[])
        cols = v.get('data',{}).get('columns',[])
        print(f"\n=== {name} ({len(rows)} rows) ===")
        print(f"Columns: {cols[:8]}")
        for r in rows[:4]:
            print(r[:6])
