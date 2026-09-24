# -*- coding: utf-8 -*-
# patch gen_dashboard_0830.py: add Early Bird column
src = open('gen_dashboard_0830.py', encoding='utf-8').read()

Q = chr(39)  # single quote
DQ = chr(34) # double quote
BS = chr(92)

# 1. add eb_disp after hv_disp line (line-level replace)
old_line = "        hv_disp = f'+{b[\"hv_count\"]}' if b['hv_count'] > 0 else '-'"
new_line = old_line + "\n        eb_disp = f'+{b[\"early\"]}' if b.get('early', 0) > 0 else '-'"
assert old_line in src, 'hv_disp line not found'
src = src.replace(old_line, new_line)

# 2. BD row: insert eb cell
old_cell = '<td class="score-hv">{hv_disp}</td><td class="score-total"><b>{b["total"]}</b></td>'
new_cell = '<td class="score-hv">{hv_disp}</td><td class="score-eb">{eb_disp}</td><td class="score-total"><b>{b["total"]}</b></td>'
assert old_cell in src, 'bd cell not found'
src = src.replace(old_cell, new_cell)

# 3. table header
src = src.replace('<th>HV+2 高价值</th><th>Total 总分</th>', '<th>HV+2 高价值</th><th>EB+1 早鸟</th><th>Total 总分</th>')

# 4. detail lead rows: early cell
old_d = "            lead_rows += f'<tr><td>{html.escape(str(l[\"name\"]))}</td><td>{DIR_LABEL[l[\"direction\"]]}</td><td>{l[\"base\"]}</td><td>{hv_cell}</td><td><b>{l[\"score\"]}</b></td></tr>\n'"
new_d = "            eb_cell = '+1' if l.get('early') else '-'\n            lead_rows += f'<tr><td>{html.escape(str(l[\"name\"]))}</td><td>{DIR_LABEL[l[\"direction\"]]}</td><td>{l[\"base\"]}</td><td>{hv_cell}</td><td>{eb_cell}</td><td><b>{l[\"score\"]}</b></td></tr>" + Q + BS + "n'"
assert old_d in src, 'detail row not found'
src = src.replace(old_d, new_d)

# 5. detail table header
src = src.replace('<th>HV 高价值+2</th><th>Subtotal 小计</th>', '<th>HV 高价值+2</th><th>EB 早鸟+1</th><th>Subtotal 小计</th>')

# 6. colspan 11 -> 12
src = src.replace('colspan="11"', 'colspan="12"')

# 7. note under module 3
old_m3 = "parts.append('<div class=\"section-title\">👤 MODULE 3: BD Personal Rankings BD个人排名 Ranking BD</div>')"
new_m3 = old_m3 + "\nparts.append('<div style=\"font-size:12px;color:#888;margin-bottom:8px\">EB+1 早鸟分: 8月15日前已营业(8/5快照验证)的转化商户 +1分/家 · 另有52家(0817窗口首次营业)待证据核实后补录</div>')"
assert old_m3 in src, 'module3 title not found'
src = src.replace(old_m3, new_m3)

open('gen_dashboard_0830.py', 'w', encoding='utf-8').write(src)
print('patched OK')
