#!/usr/bin/env python3
"""Generate order_penetration_dashboard_v4.html from JSON data."""
import json, html

with open("order_penetration_data_0817_final.json", "r", encoding="utf-8") as f:
    data = json.load(f)

rs = data["regional_summary"]
cs = data["city_summary"]
ws_bds = data["ws_bds"]
santos_bds = data["santos_bds"]
bdm = data["bdm_summary"]
prev = data["previous"]

def dir_label(d):
    return {"not_signed": "NS", "not_online": "NO", "not_operating": "NOP"}.get(d, d)

def hv_disp(hv):
    return f"+{hv}" if hv > 0 else "-"

def hv_det(hv):
    return f"+{hv*2}" if hv else "+0"

def status_disp(total):
    if total >= 15:
        return '<span class="status-ok">✅ 达标</span>'
    return f'<span class="status-gap">还差 {15-total} 分</span>'

def gen_bd_row(bd_data, rank, prefix):
    bd = bd_data["bd"]
    bdm_name = bd_data["bdm"]
    city = bd_data["city"]
    ns = bd_data["not_signed"]
    no = bd_data["not_online"]
    nop = bd_data["not_operating"]
    hv = bd_data["hv_bonus"]
    total = bd_data["total"]
    leads = bd_data.get("leads", [])
    
    medal_cls = ""
    medal_pre = ""
    if rank == 1: medal_cls, medal_pre = "gold", "🥇 "
    elif rank == 2: medal_cls, medal_pre = "silver", "🥈 "
    elif rank == 3: medal_cls, medal_pre = "bronze", "🥉 "
    
    if total == 0:
        return (f'<tr class="zero-row" >\n<td>{rank}</td>\n'
                f'<td>{html.escape(bd)} </td>\n<td>{html.escape(bdm_name)}</td>\n'
                f'<td>{city}</td>\n<td class="score-ns">0</td>\n<td class="score-no">0</td>\n'
                f'<td class="score-nop">0</td>\n<td class="score-hv">-</td>\n'
                f'<td class="score-total"><b>0</b></td>\n'
                f'<td><span class="status-gap">还差 15 分</span></td>\n<td class="prize"></td>\n</tr>\n')
    
    cls = f"medal-row {medal_cls}".strip()
    arrow = " ▶"
    
    row = (f'<tr class="{cls}" onclick="toggleDetail(\'{prefix}-{bd}\')" style="cursor:pointer">\n'
           f'<td>{medal_pre}{rank}</td>\n'
           f'<td>{html.escape(bd)}{arrow}</td>\n'
           f'<td>{html.escape(bdm_name)}</td>\n<td>{city}</td>\n'
           f'<td class="score-ns">{ns}</td>\n<td class="score-no">{no}</td>\n'
           f'<td class="score-nop">{nop}</td>\n<td class="score-hv">{hv_disp(hv)}</td>\n'
           f'<td class="score-total"><b>{total}</b></td>\n'
           f'<td>{status_disp(total)}</td>\n<td class="prize"></td>\n</tr>\n')
    
    if leads:
        row += (f'<tr class="detail-row" id="detail-{prefix}-{bd}" style="display:none">'
                f'<td colspan="11"><div class="detail-table-wrap">'
                f'<table class="detail-table"><thead><tr>'
                f'<th>Lead Name</th><th>Direction</th><th>Base</th><th>HV</th><th>Subtotal</th>'
                f'</tr></thead><tbody>\n')
        for lead in leads:
            ln = lead.get("name") or "(unknown)"
            row += (f'<tr><td>{html.escape(str(ln))}</td>'
                    f'<td>{dir_label(lead["direction"])}</td>'
                    f'<td>{lead["base"]}</td>'
                    f'<td>{hv_det(lead.get("hv",0))}</td>'
                    f'<td><b>{lead["score"]}</b></td></tr>\n')
        row += '</tbody></table></div></td></tr>\n'
    
    return row

# Build rows
ws_rows = "".join(gen_bd_row(bd_data, i+1, "ws") for i, bd_data in enumerate(ws_bds))
santos_rows = "".join(gen_bd_row(bd_data, i+1, "santos") for i, bd_data in enumerate(santos_bds))

# BDM rows
bdm_sorted = sorted(bdm.items(), key=lambda x: -x[1]["avg"])
bdm_rows = []
for i, (name, info) in enumerate(bdm_sorted):
    rank = i + 1
    medal_cls = ""
    medal_pre = ""
    if rank == 1: medal_cls, medal_pre = "gold", "🥇 "
    elif rank == 2: medal_cls, medal_pre = "silver", "🥈 "
    elif rank == 3: medal_cls, medal_pre = "bronze", "🥉 "
    
    avg = info["avg"]
    gap = 15 - avg
    status = f'<span class="status-gap">⏳ 还差 {gap:.1f}</span>'
    
    cls = f"medal-row {medal_cls}".strip() if medal_cls else ""
    bdm_rows.append(
        f'<tr class="{cls}"><td>{medal_pre}{rank}</td><td>{name}</td>'
        f'<td>{info["city"]}</td><td>{info["bd_count"]}</td>'
        f'<td><b>{info["team_score"]}</b></td>'
        f'<td class="score-total"><b>{avg:.2f}</b></td><td>{status}</td></tr>'
    )
bdm_rows_str = "\n".join(bdm_rows)

# Calculations
dod_op = rs["total_operating"] - prev["total_operating"]
dod_op_pct = dod_op / prev["total_operating"] * 100
dod_score = rs["total_score"] - prev["total_score"]
dod_score_pct = dod_score / prev["total_score"] * 100
dod_bd = rs["bd_level_score"] - prev["bd_level_score"]
dod_ns_op = rs["ns_op"] - prev["ns_op"]
dod_no_op = rs["no_op"] - prev["no_op"]

ns_comp = rs["ns_score"] / rs["ns_target"] * 100
no_comp = rs["no_score"] / rs["no_target"] * 100
nop_comp = rs["nop_score"] / rs["nop_target"] * 100

s = cs["Southern"]
w = cs["Western"]
st = cs["Santos"]

s_sp = s["signed"]/s["target"]*100
w_sp = w["signed"]/w["target"]*100
st_sp = st["signed"]/st["target"]*100

s_nsp = s["ns_score"]/s["ns_target"]*100 if s["ns_target"] else 0
w_nsp = w["ns_score"]/w["ns_target"]*100 if w["ns_target"] else 0
st_nsp = st["ns_score"]/st["ns_target"]*100 if st["ns_target"] else 0

s_nop = s["no_score"]/s["no_target"]*100 if s["no_target"] else 0
w_nop = w["no_score"]/w["no_target"]*100 if w["no_target"] else 0
st_nop = st["no_score"]/st["no_target"]*100 if st["no_target"] else 0

s_nopp = s["nop_score"]/s["nop_target"]*100 if s["nop_target"] else 0
w_nopp = w["nop_score"]/w["nop_target"]*100 if w["nop_target"] else 0
st_nopp = st["nop_score"]/st["nop_target"]*100 if st["nop_target"] else 0

signed_pct = rs["total_signed"]/rs["total_target"]*100
op_pct = rs["total_operating"]/rs["total_target"]*100

# Write context for part2
ctx = {
    "rs": rs, "prev": prev, "s": s, "w": w, "st": st,
    "dod_op": dod_op, "dod_op_pct": dod_op_pct,
    "dod_score": dod_score, "dod_score_pct": dod_score_pct,
    "dod_bd": dod_bd, "dod_ns_op": dod_ns_op, "dod_no_op": dod_no_op,
    "ns_comp": ns_comp, "no_comp": no_comp, "nop_comp": nop_comp,
    "s_sp": s_sp, "w_sp": w_sp, "st_sp": st_sp,
    "s_nsp": s_nsp, "w_nsp": w_nsp, "st_nsp": st_nsp,
    "s_nop": s_nop, "w_nop": w_nop, "st_nop": st_nop,
    "s_nopp": s_nopp, "w_nopp": w_nopp, "st_nopp": st_nopp,
    "signed_pct": signed_pct, "op_pct": op_pct,
    "ws_rows": ws_rows, "santos_rows": santos_rows, "bdm_rows": bdm_rows_str,
}

with open("_gen_ctx.json", "w") as f:
    json.dump(ctx, f)

print("Part 1 done. Context written.")
print(f"WS BDs: {len(ws_bds)}, Santos BDs: {len(santos_bds)}, BDMs: {len(bdm_sorted)}")
print(f"Total score: {rs['ns_score']}+{rs['no_score']}+{rs['nop_score']}+{rs['hv_bonus']}={rs['total_score']}")
