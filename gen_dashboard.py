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
    m = {"not_signed": "NS", "not_online": "NO", "not_operating": "NOP"}
    return m.get(d, d)

def hv_display(hv_bonus):
    if hv_bonus > 0:
        return f"+{hv_bonus}"
    return "-"

def hv_detail_display(hv):
    return f"+{hv*2}" if hv else "+0"

def status_display(total):
    if total >= 15:
        return '<span class="status-ok">✅ 达标</span>'
    else:
        gap = 15 - total
        return f'<span class="status-gap">还差 {gap} 分</span>'

def gen_bd_row(bd_data, rank, prefix, medal_class=""):
    bd = bd_data["bd"]
    bdm_name = bd_data["bdm"]
    city = bd_data["city"]
    ns = bd_data["not_signed"]
    no = bd_data["not_online"]
    nop = bd_data["not_operating"]
    hv = bd_data["hv_bonus"]
    total = bd_data["total"]
    leads = bd_data.get("leads", [])
    
    has_leads = total > 0 and len(leads) > 0
    
    medal_prefix = ""
    if rank == 1:
        medal_prefix = "🥇 "
        medal_class = "gold"
    elif rank == 2:
        medal_prefix = "🥈 "
        medal_class = "silver"
    elif rank == 3:
        medal_prefix = "🥉 "
        medal_class = "bronze"
    
    if total == 0:
        # Zero row - no click, no detail
        cls = "zero-row"
        arrow = ""
        row = f'''<tr class="{cls}" >
<td>{rank}</td>
<td>{html.escape(bd)} </td>
<td>{html.escape(bdm_name)}</td>
<td>{city}</td>
<td class="score-ns">{ns}</td>
<td class="score-no">{no}</td>
<td class="score-nop">{nop}</td>
<td class="score-hv">{hv_display(hv)}</td>
<td class="score-total"><b>{total}</b></td>
<td><span class="status-gap">还差 15 分</span></td>
<td class="prize"></td>
</tr>\n'''
        return row
    
    cls = f"medal-row {medal_class}".strip()
    arrow = " ▶"
    
    row = f'''<tr class="{cls}" onclick="toggleDetail('{prefix}-{bd}')" style="cursor:pointer">
<td>{medal_prefix}{rank}</td>
<td>{html.escape(bd)}{arrow}</td>
<td>{html.escape(bdm_name)}</td>
<td>{city}</td>
<td class="score-ns">{ns}</td>
<td class="score-no">{no}</td>
<td class="score-nop">{nop}</td>
<td class="score-hv">{hv_display(hv)}</td>
<td class="score-total"><b>{total}</b></td>
<td>{status_display(total)}</td>
<td class="prize"></td>
</tr>\n'''
    
    # Detail row
    if has_leads:
        row += f'''<tr class="detail-row" id="detail-{prefix}-{bd}" style="display:none"><td colspan="11"><div class="detail-table-wrap"><table class="detail-table"><thead><tr><th>Lead Name</th><th>Direction</th><th>Base</th><th>HV</th><th>Subtotal</th></tr></thead><tbody>\n'''
        for lead in leads:
            lname = lead.get("name") or "(unknown)"
            ldir = dir_label(lead["direction"])
            lbase = lead["base"]
            lhv = lead.get("hv", 0)
            lscore = lead["score"]
            row += f'<tr><td>{html.escape(str(lname))}</td><td>{ldir}</td><td>{lbase}</td><td>{hv_detail_display(lhv)}</td><td><b>{lscore}</b></td></tr>\n'
        row += '</tbody></table></div></td></tr>\n'
    
    return row

# Build BDM rows sorted by avg desc
bdm_sorted = sorted(bdm.items(), key=lambda x: -x[1]["avg"])
bdm_rows = []
for i, (name, info) in enumerate(bdm_sorted):
    rank = i + 1
    medal_cls = ""
    medal_prefix = ""
    if rank == 1:
        medal_cls = "gold"
        medal_prefix = "🥇 "
    elif rank == 2:
        medal_cls = "silver"
        medal_prefix = "🥈 "
    elif rank == 3:
        medal_cls = "bronze"
        medal_prefix = "🥉 "
    
    avg = info["avg"]
    if avg >= 15:
        status = '<span class="status-ok">✅ 达标</span>'
    elif avg >= 10:
        gap = 15 - avg
        status = f'<span class="status-gap">⏳ 还差 {gap:.1f}</span>'
    else:
        gap = 15 - avg
        status = f'<span class="status-gap">⏳ 还差 {gap:.1f}</span>'
    
    cls = f"medal-row {medal_cls}".strip() if medal_cls else ""
    bdm_rows.append(f'<tr class="{cls}"><td>{medal_prefix}{rank}</td><td>{name}</td><td>{info["city"]}</td><td>{info["bd_count"]}</td><td><b>{info["team_score"]}</b></td><td class="score-total"><b>{avg:.2f}</b></td><td>{status}</td></tr>')

# Build WS BD rows
ws_rows = ""
for i, bd_data in enumerate(ws_bds):
    ws_rows += gen_bd_row(bd_data, i + 1, "ws")

# Build Santos BD rows
santos_rows = ""
for i, bd_data in enumerate(santos_bds):
    santos_rows += gen_bd_row(bd_data, i + 1, "santos")

# Calculate DOD changes
dod_op = rs["total_operating"] - prev["total_operating"]
dod_op_pct = dod_op / prev["total_operating"] * 100
dod_score = rs["total_score"] - prev["total_score"]
dod_score_pct = dod_score / prev["total_score"] * 100
dod_bd = rs["bd_level_score"] - prev["bd_level_score"]
dod_ns_op = rs["ns_op"] - prev["ns_op"]
dod_no_op = rs["no_op"] - prev["no_op"]
dod_nop_op = rs["nop_op"] - prev["nop_op"]

ns_completion = rs["ns_score"] / rs["ns_target"] * 100
no_completion = rs["no_score"] / rs["no_target"] * 100
nop_completion = rs["nop_score"] / rs["nop_target"] * 100

# City data
south = cs["Southern"]
west = cs["Western"]
sant = cs["Santos"]

south_signed_pct = south["signed"] / south["target"] * 100
west_signed_pct = west["signed"] / west["target"] * 100
sant_signed_pct = sant["signed"] / sant["target"] * 100

south_ns_pct = south["ns_score"] / south["ns_target"] * 100 if south["ns_target"] else 0
west_ns_pct = west["ns_score"] / west["ns_target"] * 100 if west["ns_target"] else 0
sant_ns_pct = sant["ns_score"] / sant["ns_target"] * 100 if sant["ns_target"] else 0

south_no_pct = south["no_score"] / south["no_target"] * 100 if south["no_target"] else 0
west_no_pct = west["no_score"] / west["no_target"] * 100 if west["no_target"] else 0
sant_no_pct = sant["no_score"] / sant["no_target"] * 100 if sant["no_target"] else 0

south_nop_pct = south["nop_score"] / south["nop_target"] * 100 if south["nop_target"] else 0
west_nop_pct = west["nop_score"] / west["nop_target"] * 100 if west["nop_target"] else 0
sant_nop_pct = sant["nop_score"] / sant["nop_target"] * 100 if sant["nop_target"] else 0

signed_pct = rs["total_signed"] / rs["total_target"] * 100
op_pct = rs["total_operating"] / rs["total_target"] * 100

# BDM total
bdm_count = len(bdm_sorted)
ws_bd_count = len(ws_bds)
santos_bd_count = len(santos_bds)

html_out = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Order Penetration Incentive Race Dashboard</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #f5f7fa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #2c3e50; padding: 20px; }}
.container {{ max-width: 1400px; margin: 0 auto; }}
.header {{ text-align: center; padding: 30px 20px; margin-bottom: 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px; color: white; }}
.header h1 {{ font-size: 28px; margin-bottom: 4px; }}
.header .subtitle {{ font-size: 16px; opacity: 0.9; }}
.header .date {{ font-size: 13px; opacity: 0.75; margin-top: 8px; }}
.validity-banner {{ background: #fff3cd; border: 2px solid #ffc107; border-radius: 8px; padding: 12px 20px; margin-bottom: 24px; text-align: center; font-size: 14px; color: #856404; font-weight: 600; }}
.section-title {{ font-size: 20px; font-weight: 700; margin: 32px 0 16px; padding-left: 12px; border-left: 4px solid #667eea; }}
.section-subtitle {{ font-size: 13px; color: #7f8c8d; margin-top: -12px; margin-bottom: 16px; padding-left: 16px; }}
.kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
.kpi-card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); text-align: center; }}
.kpi-value {{ font-size: 36px; font-weight: 800; color: #2c3e50; }}
.kpi-value small {{ font-size: 16px; color: #95a5a6; font-weight: 400; }}
.kpi-label {{ font-size: 13px; color: #7f8c8d; margin-top: 4px; }}
.kpi-dod {{ font-size: 13px; margin-top: 6px; }}
.kpi-sub {{ font-size: 11px; color: #95a5a6; margin-top: 2px; }}
.dod-up {{ color: #27ae60; font-weight: 600; }}
.dod-down {{ color: #e74c3c; font-weight: 600; }}
.dod-flat {{ color: #95a5a6; }}
.dod-card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 24px; }}
.dod-card h3 {{ font-size: 16px; margin-bottom: 16px; color: #34495e; }}
.dod-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
.dod-item {{ display: flex; flex-direction: column; gap: 4px; padding: 12px; background: #f8f9fa; border-radius: 8px; }}
.dod-label {{ font-size: 13px; font-weight: 600; color: #555; margin-bottom: 4px; }}
.dir-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }}
.dir-card {{ background: white; border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
.dir-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 12px; padding: 8px; border-radius: 8px; background: #f8f9fa; }}
.dir-icon {{ font-size: 20px; }}
.dir-title {{ font-size: 15px; font-weight: 600; }}
.dir-subtitle {{ font-size: 11px; color: #95a5a6; }}
.dir-stats {{ display: flex; justify-content: space-between; margin-bottom: 10px; }}
.dir-stat {{ text-align: center; }}
.dir-stat-label {{ display: block; font-size: 11px; color: #95a5a6; }}
.dir-stat-value {{ display: block; font-size: 20px; font-weight: 700; }}
.dir-pct {{ text-align: right; font-size: 12px; color: #95a5a6; margin-top: 4px; }}
.progress-bar-wrap {{ background: #ecf0f1; border-radius: 6px; height: 8px; overflow: hidden; }}
.progress-bar-wrap.small {{ height: 5px; margin-top: 4px; }}
.progress-bar {{ height: 100%; border-radius: 6px; transition: width 0.6s ease; min-width: 2px; }}
.city-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }}
.city-card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
.city-card h3 {{ font-size: 18px; font-weight: 700; margin-bottom: 12px; color: #34495e; }}
.city-pool {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 12px; }}
.city-stat {{ display: flex; justify-content: space-between; padding: 4px 0; }}
.city-stat-label {{ font-size: 12px; color: #7f8c8d; }}
.city-stat-value {{ font-size: 14px; font-weight: 600; }}
.city-stat-value.highlight {{ color: #e74c3c; font-size: 16px; }}
.city-stat-value small {{ font-size: 11px; color: #95a5a6; font-weight: 400; }}
.city-directions {{ margin-top: 16px; }}
.city-dir {{ margin-bottom: 10px; padding: 8px; background: #f8f9fa; border-radius: 8px; }}
.city-dir-label {{ font-size: 13px; font-weight: 600; margin-bottom: 4px; }}
.city-dir-stats {{ font-size: 12px; color: #555; display: flex; gap: 12px; }}
.tabs {{ display: flex; gap: 0; margin-bottom: 0; }}
.tab {{ padding: 10px 24px; background: #ecf0f1; border: none; cursor: pointer; font-size: 14px; font-weight: 600; color: #7f8c8d; border-radius: 8px 8px 0 0; }}
.tab.active {{ background: white; color: #2c3e50; box-shadow: 0 -2px 8px rgba(0,0,0,0.06); }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}
.table-wrap {{ background: white; border-radius: 0 12px 12px 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow-x: auto; margin-bottom: 24px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
thead th {{ background: #f8f9fa; padding: 10px 8px; text-align: left; font-weight: 600; font-size: 12px; color: #555; border-bottom: 2px solid #ecf0f1; white-space: nowrap; }}
tbody td {{ padding: 8px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }}
tbody tr:hover {{ background: #fafbfc; }}
.score-ns {{ color: #e74c3c; font-weight: 600; }}
.score-no {{ color: #f39c12; font-weight: 600; }}
.score-nop {{ color: #27ae60; font-weight: 600; }}
.score-hv {{ color: #8e44ad; font-weight: 600; }}
.score-total {{ font-size: 15px; }}
.status-ok {{ color: #27ae60; font-weight: 600; font-size: 12px; }}
.status-gap {{ color: #e74c3c; font-weight: 600; font-size: 12px; }}
.prize {{ color: #D4A017; font-weight: 700; white-space: nowrap; }}
.zero-row {{ opacity: 0.4; }}
.gold {{ background: linear-gradient(90deg, rgba(212,160,23,0.08) 0%, transparent 100%); }}
.silver {{ background: linear-gradient(90deg, rgba(160,160,160,0.08) 0%, transparent 100%); }}
.bronze {{ background: linear-gradient(90deg, rgba(205,127,50,0.08) 0%, transparent 100%); }}
.detail-row td {{ padding: 0 !important; background: #f8f9fa; }}
.detail-table-wrap {{ padding: 8px 16px 8px 40px; }}
.detail-table {{ width: auto; min-width: 400px; font-size: 12px; }}
.detail-table th {{ background: #eef1f5; font-size: 11px; padding: 6px 10px; }}
.detail-table td {{ padding: 5px 10px; border-bottom: 1px solid #eee; }}
.rules-card {{ background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 24px; }}
.rules-table {{ width: 100%; }}
.rules-table th {{ background: #667eea; color: white; padding: 10px; text-align: left; }}
.rules-table td {{ padding: 10px; border-bottom: 1px solid #eee; }}
.rules-table tr:nth-child(even) td {{ background: #f8f9fa; }}
.stats-bar {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 16px; font-size: 12px; color: #7f8c8d; }}
.footnote {{ background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 8px; padding: 12px 16px; margin-bottom: 24px; font-size: 12px; color: #856404; }}
.footnote p {{ margin-bottom: 4px; }}
.early-bird {{ background: #e8f5e9; border-left: 4px solid #27ae60; border-radius: 8px; padding: 12px 16px; margin-top: 16px; font-size: 12px; color: #2e7d32; }}
.early-bird p {{ margin-bottom: 4px; }}
@media (max-width: 900px) {{ .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }} .dir-grid {{ grid-template-columns: 1fr; }} .city-grid {{ grid-template-columns: 1fr; }} .dod-grid {{ grid-template-columns: 1fr; }} .header h1 {{ font-size: 20px; }} }}
@media (max-width: 600px) {{ .kpi-grid {{ grid-template-columns: 1fr; }} body {{ padding: 10px; }} }}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>🏆 Order Penetration Incentive Race Dashboard</h1>
<div class="subtitle">Order Penetration Incentive Race / Painel de Corrida</div>
<div class="date">Data as of: 2026-08-17 (BRT) | Metropolitan Region</div>
</div>

<div class="validity-banner">
⚠️ Validity Standard: Operating ≥ 15h AND ≥ 1 order in last 7 days / 有效性标准：最近7天营业≥15小时且≥1订单
</div>

<div class="section-title">📊 MODULE 1: Regional Overview</div>
<div class="section-subtitle">Battle Pool — Full Coverage (All Merchants)</div>
<div class="kpi-grid">
<div class="kpi-card"><div class="kpi-value">{rs["total_target"]}</div><div class="kpi-label">Target Merchants</div></div>
<div class="kpi-card"><div class="kpi-value">{rs["total_signed"]} <small>({signed_pct:.1f}%)</small></div><div class="kpi-label">Signed</div></div>
<div class="kpi-card"><div class="kpi-value">{rs["total_operating"]} <small>({op_pct:.1f}%)</small></div><div class="kpi-label">Total Operating</div><div class="kpi-sub">BD-Assigned: 103</div></div>
<div class="kpi-card"><div class="kpi-value" style="color:#e74c3c">{rs["total_score"]}</div><div class="kpi-label">Total Score (with HV)</div><div class="kpi-sub">BD-Level: {rs["bd_level_score"]}</div></div>
</div>

<div class="dod-card">
<h3>📈 Day-over-Day Changes (8/16 → 8/17)</h3>
<div class="dod-grid">
<div class="dod-item"><span class="dod-label">Operating</span><span class="dod-up">{prev["total_operating"]} → {rs["total_operating"]} (+{dod_op}, +{dod_op_pct:.1f}%)</span></div>
<div class="dod-item"><span class="dod-label">Total Score</span><span class="dod-up">{prev["total_score"]} → {rs["total_score"]} (+{dod_score}, +{dod_score_pct:.1f}%)</span></div>
<div class="dod-item"><span class="dod-label">BD-Level Score</span><span class="dod-up">{prev["bd_level_score"]} → {rs["bd_level_score"]} (+{dod_bd})</span></div>
<div class="dod-item"><span class="dod-label">NS Score</span><span class="dod-up">→ {rs["ns_score"]} pts ({rs["ns_op"]} operating, {'+' if dod_ns_op >= 0 else ''}{dod_ns_op})</span></div>
<div class="dod-item"><span class="dod-label">NO Score</span><span class="dod-down">→ {rs["no_score"]} pts ({rs["no_op"]} operating, {dod_no_op})</span></div>
<div class="dod-item"><span class="dod-label">NOP + HV</span><span class="dod-up">→ {rs["nop_score"]} + {rs["hv_bonus"]} = {rs["nop_score"] + rs["hv_bonus"]} pts</span></div>
</div>
</div>

<div class="section-subtitle">Three Attack Directions (Full Coverage)</div>
<div class="dir-grid">
<div class="dir-card"><div class="dir-header" style="border-left:4px solid #e74c3c"><span class="dir-icon">🔴</span><div><div class="dir-title">Not Signed</div><div class="dir-subtitle">Not Signed → Operating</div></div></div><div class="dir-stats"><div class="dir-stat"><span class="dir-stat-label">Target</span><span class="dir-stat-value">{rs["ns_target"]}</span></div><div class="dir-stat"><span class="dir-stat-label">Score</span><span class="dir-stat-value">{rs["ns_score"]}</span></div></div><div class="progress-bar-wrap"><div class="progress-bar" style="width:{ns_completion:.1f}%;background:#e74c3c"></div></div><div class="dir-pct">{ns_completion:.1f}% completion ({rs["ns_op"]} operating)</div></div>
<div class="dir-card"><div class="dir-header" style="border-left:4px solid #f39c12"><span class="dir-icon">🟡</span><div><div class="dir-title">Not Online</div><div class="dir-subtitle">Signed Not Online → Operating</div></div></div><div class="dir-stats"><div class="dir-stat"><span class="dir-stat-label">Target</span><span class="dir-stat-value">{rs["no_target"]}</span></div><div class="dir-stat"><span class="dir-stat-label">Score</span><span class="dir-stat-value">{rs["no_score"]}</span></div></div><div class="progress-bar-wrap"><div class="progress-bar" style="width:{no_completion:.1f}%;background:#f39c12"></div></div><div class="dir-pct">{no_completion:.1f}% completion ({rs["no_op"]} operating)</div></div>
<div class="dir-card"><div class="dir-header" style="border-left:4px solid #27ae60"><span class="dir-icon">🟢</span><div><div class="dir-title">Not Operating</div><div class="dir-subtitle">Signed Not Operating → Recovered</div></div></div><div class="dir-stats"><div class="dir-stat"><span class="dir-stat-label">Target</span><span class="dir-stat-value">{rs["nop_target"]}</span></div><div class="dir-stat"><span class="dir-stat-label">Score</span><span class="dir-stat-value">{rs["nop_score"]}</span></div></div><div class="progress-bar-wrap"><div class="progress-bar" style="width:{nop_completion:.1f}%;background:#27ae60"></div></div><div class="dir-pct">{nop_completion:.1f}% completion ({rs["nop_op"]} operating)</div></div>
</div>

<div class="footnote">
<p>📊 <b>Score Breakdown:</b> NS {rs["ns_op"]}×6={rs["ns_score"]} + NO {rs["no_op"]}×4={rs["no_score"]} + NOP {rs["nop_op"]}×3={rs["nop_score"]} + HV {rs["hv_count"]}×2={rs["hv_bonus"]} = <b>{rs["total_score"]}</b></p>
<p>🏆 <b>HV Bonus:</b> {rs["hv_count"]} merchants with iFood orders ≥ 20, +2 pts each = {rs["hv_bonus"]} pts</p>
</div>

<div class="section-title">🏙️ MODULE 2: City Battle Overview</div>
<div class="city-grid">
<div class="city-card"><h3>Southern</h3><div class="city-pool"><div class="city-stat"><span class="city-stat-label">Target</span><span class="city-stat-value">{south["target"]}</span></div><div class="city-stat"><span class="city-stat-label">Signed</span><span class="city-stat-value">{south["signed"]} <small>({south_signed_pct:.1f}%)</small></span></div><div class="city-stat"><span class="city-stat-label">Operating</span><span class="city-stat-value">{south["operating"]} <small>({south["op_rate"]:.1f}%)</small></span></div><div class="city-stat"><span class="city-stat-label">Score</span><span class="city-stat-value highlight">{south["score"]}</span></div></div><div class="progress-bar-wrap"><div class="progress-bar" style="width:{south["op_rate"]:.1f}%;background:#3498db"></div></div><div class="dir-pct">Operating Rate: {south["op_rate"]:.1f}%</div><div class="city-directions"><div class="city-dir"><div class="city-dir-label">🔴 Not Sign</div><div class="city-dir-stats"><span>Target: {south["ns_target"]}</span><span>→ Op: {south["ns_op"]}</span><span>→ Score: {south["ns_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{south_ns_pct:.1f}%;background:#e74c3c"></div></div></div><div class="city-dir"><div class="city-dir-label">🟡 Not Online</div><div class="city-dir-stats"><span>Target: {south["no_target"]}</span><span>→ Op: {south["no_op"]}</span><span>→ Score: {south["no_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{south_no_pct:.1f}%;background:#f39c12"></div></div></div><div class="city-dir"><div class="city-dir-label">🟢 Not Oper.</div><div class="city-dir-stats"><span>Target: {south["nop_target"]}</span><span>→ Op: {south["nop_op"]}</span><span>→ Score: {south["nop_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{south_nop_pct:.1f}%;background:#27ae60"></div></div></div></div></div>
<div class="city-card"><h3>Western</h3><div class="city-pool"><div class="city-stat"><span class="city-stat-label">Target</span><span class="city-stat-value">{west["target"]}</span></div><div class="city-stat"><span class="city-stat-label">Signed</span><span class="city-stat-value">{west["signed"]} <small>({west_signed_pct:.1f}%)</small></span></div><div class="city-stat"><span class="city-stat-label">Operating</span><span class="city-stat-value">{west["operating"]} <small>({west["op_rate"]:.1f}%)</small></span></div><div class="city-stat"><span class="city-stat-label">Score</span><span class="city-stat-value highlight">{west["score"]}</span></div></div><div class="progress-bar-wrap"><div class="progress-bar" style="width:{west["op_rate"]:.1f}%;background:#3498db"></div></div><div class="dir-pct">Operating Rate: {west["op_rate"]:.1f}%</div><div class="city-directions"><div class="city-dir"><div class="city-dir-label">🔴 Not Sign</div><div class="city-dir-stats"><span>Target: {west["ns_target"]}</span><span>→ Op: {west["ns_op"]}</span><span>→ Score: {west["ns_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{west_ns_pct:.1f}%;background:#e74c3c"></div></div></div><div class="city-dir"><div class="city-dir-label">🟡 Not Online</div><div class="city-dir-stats"><span>Target: {west["no_target"]}</span><span>→ Op: {west["no_op"]}</span><span>→ Score: {west["no_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{west_no_pct:.1f}%;background:#f39c12"></div></div></div><div class="city-dir"><div class="city-dir-label">🟢 Not Oper.</div><div class="city-dir-stats"><span>Target: {west["nop_target"]}</span><span>→ Op: {west["nop_op"]}</span><span>→ Score: {west["nop_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{west_nop_pct:.1f}%;background:#27ae60"></div></div></div></div></div>
<div class="city-card"><h3>Santos</h3><div class="city-pool"><div class="city-stat"><span class="city-stat-label">Target</span><span class="city-stat-value">{sant["target"]}</span></div><div class="city-stat"><span class="city-stat-label">Signed</span><span class="city-stat-value">{sant["signed"]} <small>({sant_signed_pct:.1f}%)</small></span></div><div class="city-stat"><span class="city-stat-label">Operating</span><span class="city-stat-value">{sant["operating"]} <small>({sant["op_rate"]:.1f}%)</small></span></div><div class="city-stat"><span class="city-stat-label">Score</span><span class="city-stat-value highlight">{sant["score"]}</span></div></div><div class="progress-bar-wrap"><div class="progress-bar" style="width:{sant["op_rate"]:.1f}%;background:#3498db"></div></div><div class="dir-pct">Operating Rate: {sant["op_rate"]:.1f}%</div><div class="city-directions"><div class="city-dir"><div class="city-dir-label">🔴 Not Sign</div><div class="city-dir-stats"><span>Target: {sant["ns_target"]}</span><span>→ Op: {sant["ns_op"]}</span><span>→ Score: {sant["ns_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{sant_ns_pct:.1f}%;background:#e74c3c"></div></div></div><div class="city-dir"><div class="city-dir-label">🟡 Not Online</div><div class="city-dir-stats"><span>Target: {sant["no_target"]}</span><span>→ Op: {sant["no_op"]}</span><span>→ Score: {sant["no_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{sant_no_pct:.1f}%;background:#f39c12"></div></div></div><div class="city-dir"><div class="city-dir-label">🟢 Not Oper.</div><div class="city-dir-stats"><span