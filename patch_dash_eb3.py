# -*- coding: utf-8 -*-
src = open('gen_dashboard_0830.py', encoding='utf-8').read()

# 1. eb_disp line
old = "        hv_disp = f'+{b[\"hv_count\"]}' if b['hv_count'] > 0 else '-'\n"
if 'eb_disp' not in src:
    assert old in src
    src = src.replace(old, old + "        eb_disp = f'+{b[\"early\"]}' if b.get('early', 0) > 0 else '-'\n")

# 2. BD row cell
old_cell = '<td class="score-hv">{hv_disp}</td><td class="score-total"><b>{b["total"]}</b></td>'
if 'score-eb' not in src:
    assert old_cell in src
    src = src.replace(old_cell, '<td class="score-hv">{hv_disp}</td><td class="score-eb">{eb_disp}</td><td class="score-total"><b>{b["total"]}</b></td>')

# 3. TH header
src = src.replace('<th>HV+2 高价值</th><th>Total 总分</th>', '<th>HV+2 高价值</th><th>EB+1 早鸟</th><th>Total 总分</th>')

# 4. colspan 11 -> 12
src = src.replace('colspan="11"', 'colspan="12"')

# 5. note under Module 3 title (idempotent)
if '早鸟分: 8月15日前' not in src:
    old_m3 = "parts.append('<div class=\"section-title\">👤 MODULE 3: BD Personal Rankings BD个人排名 Ranking BD</div>')"
    assert old_m3 in src
    src = src.replace(old_m3, old_m3 + "\nparts.append('<div style=\"font-size:12px;color:#888;margin-bottom:8px\">EB+1 早鸟分: 8月15日前已营业(8/5快照验证)的转化商户 +1分/家 · 另有52家(0817窗口首次营业)待证据核实后补录</div>')")

open('gen_dashboard_0830.py', 'w', encoding='utf-8').write(src)
print('OK')
