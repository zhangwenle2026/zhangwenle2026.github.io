#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scrape all pages of exclusivity table via agent-browser, save fresh data."""
import json, subprocess, time

def ab(js, timeout=60):
    # base64 to avoid quoting issues
    import base64
    b64 = base64.b64encode(js.encode()).decode()
    r = subprocess.run(['agent-browser','eval','-b',b64], capture_output=True, text=True, timeout=timeout)
    out = r.stdout.strip()
    if out.startswith('"') and out.endswith('"'):
        out = json.loads(out)
    return out

get_rows = "JSON.stringify(Array.from(document.querySelectorAll('table tbody tr')).map(r=>Array.from(r.cells).map(c=>c.innerText.trim().replace(/\\n/g,' ~ '))))"
next_page = "(()=>{const b=Array.from(document.querySelectorAll('button')).filter(x=>/próxima/i.test(x.innerText)); b[0].click(); return 1})()"
page_info = "(document.body.innerText.match(/Página \\d+ de \\d+/)||['?'])[0]"

all_rows = []
for p in range(1, 4):
    raw = ab(get_rows)
    rows = json.loads(raw)
    all_rows.extend(rows)
    print(f'page {p}: {len(rows)} rows (total {len(all_rows)}), {ab(page_info)}')
    if p < 3:
        ab(next_page)
        time.sleep(2)

json.dump(all_rows, open('/tmp/excl_fresh.json','w'), ensure_ascii=False, indent=1)
print('saved', len(all_rows))
