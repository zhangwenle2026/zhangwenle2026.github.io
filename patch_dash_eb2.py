# -*- coding: utf-8 -*-
# simple line-based patch for detail rows (idempotent)
lines = open('gen_dashboard_0830.py', encoding='utf-8').readlines()
out = []
patched = False
for ln in lines:
    if 'lead_rows += ' in ln and 'hv_cell' in ln and 'eb_cell' not in ln:
        out.append("            eb_cell = '+1' if l.get('early') else '-'\n")
        ln = ln.replace('<td>{hv_cell}</td>', '<td>{hv_cell}</td><td>{eb_cell}</td>')
        patched = True
    out.append(ln)
src = ''.join(out)
src = src.replace('<th>HV 高价值+2</th><th>Subtotal 小计</th>', '<th>HV 高价值+2</th><th>EB 早鸟+1</th><th>Subtotal 小计</th>')
open('gen_dashboard_0830.py', 'w', encoding='utf-8').write(src)
print('patched detail rows:', patched)
