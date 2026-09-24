import json

# Compare data freshness across files
files = [
    '/mnt/openclaw/.openclaw/workspace/bi_raw_data.json',
    '/mnt/openclaw/.openclaw/workspace/dbr_data_20260728.json',
    '/mnt/openclaw/.openclaw/workspace/dbr_data_latest.json',
]

for f in files:
    try:
        with open(f) as fh:
            data = json.load(fh)
        
        # Try to find date
        date = data.get('date', 'N/A')
        
        # Check Order Performance dates
        op = data.get('Last 10 Days - Order Performance', {})
        if not op and 'results' in data:
            op = data['results'].get('Business Performance', {})
        
        if isinstance(op, dict) and op.get('code') == 0:
            rows = op.get('data', {}).get('data', [])
            if rows:
                dates = [r[0] for r in rows if isinstance(r[0], str) and r[0].startswith('2026')]
                latest = max(dates) if dates else 'N/A'
            else:
                latest = 'N/A'
        else:
            latest = 'N/A'
        
        print(f"{f.split('/')[-1]}: file_date={date}, latest_data={latest}")
    except Exception as e:
        print(f"{f}: ERROR {e}")
