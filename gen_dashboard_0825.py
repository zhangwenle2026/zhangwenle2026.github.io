import json, html

D = json.load(open('order_penetration_data_0825_final.json'))
R = D['regional_summary']; P = D['previous']; C = D['city_summary']

def cls(v): return 'dod-up' if v > 0 else ('dod-down' if v < 0 else 'dod-flat')
def arrow(v): return f'↑+{v}' if v > 0 else (f'↓{v}' if v < 0 else '→ 0')
def pct(a, b): return round(a/b*100, 1) if b else 0

dod = {k: R[k] - P[k] for k in ['total_operating','total_score','ns_op','no_op','nop_op']}
assigned_total = sum(v['assigned'] for v in C.values())
prev_assigned = sum(v['assigned'] for v in P['cities'].values())
dod_assigned = assigned_total - prev_assigned
assigned_pct = pct(assigned_total, R['total_target'])
op_pct = pct(R['total_operating'], R['total_target'])

city_dod = {}
for c, v in C.items():
    pv = P['cities'].get(c, {})
    city_dod[c] = {
        'assigned': v['assigned'] - pv.get('assigned', v['assigned']),
        'operating': v['operating'] - pv.get('operating', 0),
        'score': v['score'] - pv.get('score', 0),
        'ns_op': v['ns_op'] - pv.get('ns_op', 0),
        'no_op': v['no_op'] - pv.get('no_op', 0),
        'nop_op': v['nop_op'] - pv.get('nop_op', 0),
    }

parts = []
parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Order Penetration Incentive Race Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #1a1d2e; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #e0e0e0; padding: 20px; }
.container { max-width: 1400px; margin: 0 auto; }
.header { text-align: center; padding: 30px 20px; margin-bottom: 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px; color: white; }
.header h1 { font-size: 28px; margin-bottom: 4px; }
.header .subtitle { font-size: 16px; opacity: 0.9; }
.header .date { font-size: 13px; opacity: 0.75; margin-top: 8px; }
.section-title { font-size: 20px; font-weight: 700; margin: 32px 0 16px; padding-left: 12px; border-left: 4px solid #667eea; color: #e0e0e0; }
.section-subtitle { font-size: 13px; color: #95a5a6; margin-top: -12px; margin-bottom: 16px; padding-left: 16px; }
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.kpi-card { background: #252840; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); text-align: center; }
.kpi-value { font-size: 36px; font-weight: 800; color: #e0e0e0; }
.kpi-value small { font-size: 16px; color: #95a5a6; font-weight: 400; }
.kpi-label { font-size: 13px; color: #95a5a6; margin-top: 4px; }
.kpi-dod { font-size: 13px; margin-top: 6px; }
.dod-up { color: #2ecc71; font-weight: 600; }
.dod-down { color: #e74c3c; font-weight: 600; }
.dod-flat { color: #95a5a6; }
.dod-card { background: #252840; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); margin-bottom: 24px; }
.dod-card h3 { font-size: 16px; margin-bottom: 16px; color: #bdc3c7; }
.dod-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.dod-item { display: flex; flex-direction: column; gap: 4px; padding: 12px; background: #1a1d2e; border-radius: 8px; }
.dod-label { font-size: 13px; font-weight: 600; color: #bdc3c7; margin-bottom: 4px; }
.dir-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
.dir-card { background: #252840; border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); }
.dir-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; padding: 8px; border-radius: 8px; background: #1a1d2e; }
.dir-icon { font-size: 20px; }
.dir-title { font-size: 15px; font-weight: 600; }
.dir-subtitle { font-size: 11px; color: #95a5a6; }
.dir-stats { display: flex; justify-content: space-between; margin-bottom: 10px; }
.dir-stat { text-align: center; }
.dir-stat-label { display: block; font-size: 11px; color: #95a5a6; }
.dir-stat-value { display: block; font-size: 20px; font-weight: 700; }
.dir-pct { text-align: right; font-size: 12px; color: #95a5a6; margin-top: 4px; }
.progress-bar-wrap { background: #1a1d2e; border-radius: 6px; height: 8px; overflow: hidden; }
.progress-bar-wrap.small { height: 5px; margin-top: 4px; }
.progress-bar { height: 100%; border-radius: 6px; transition: width 0.6s ease; min-width: 2px; }
.city-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
.city-card { background: #252840; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); }
.city-card h3 { font-size: 18px; font-weight: 700; margin-bottom: 12px; color: #bdc3c7; }
.city-pool { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 12px; }
.city-stat { display: flex; justify-content: space-between; padding: 4px 0; }
.city-stat-label { font-size: 12px; color: #95a5a6; }
.city-stat-value { font-size: 14px; font-weight: 600; color: #e0e0e0; }
.city-stat-value.highlight { color: #e74c3c; font-size: 16px; }
.city-stat-value small { font-size: 11px; color: #95a5a6; font-weight: 400; }
.city-directions { margin-top: 16px; }
.city-dir { margin-bottom: 10px; padding: 8px; background: #1a1d2e; border-radius: 8px; }
.city-dir-label { font-size: 13px; font-weight: 600; margin-bottom: 4px; color: #bdc3c7; }
.city-dir-stats { font-size: 12px; color: #bdc3c7; display: flex; gap: 12px; }
.tabs { display: flex; gap: 0; margin-bottom: 0; }
.tab { padding: 10px 24px; background: #1a1d2e; border: none; cursor: pointer; font-size: 14px; font-weight: 600; color: #95a5a6; border-radius: 8px 8px 0 0; }
.tab.active { background: #252840; color: #e0e0e0; box-shadow: 0 -2px 8px rgba(0,0,0,0.3); }
.tab-content { display: none; }
.tab-content.active { display: block; }
.table-wrap { background: #252840; border-radius: 0 12px 12px 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); overflow-x: auto; margin-bottom: 24px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th { background: #1a1d2e; padding: 10px 8px; text-align: left; font-weight: 600; font-size: 12px; color: #bdc3c7; border-bottom: 2px solid #2c3e50; white-space: nowrap; }
tbody td { padding: 8px; border-bottom: 1px solid #2c3e50; vertical-align: middle; color: #e0e0e0; }
tbody tr:hover { background: #2c3e50; }
.score-ns { color: #e74c3c; font-weight: 600; }
.score-no { color: #f39c12; font-weight: 600; }
.score-nop { color: #2ecc71; font-weight: 600; }
.score-hv { color: #9b59b6; font-weight: 600; }
.score-total { font-size: 15px; }
.status-ok { color: #2ecc71; font-weight: 600; font-size: 12px; }
.status-gap { color: #e74c3c; font-weight: 600; font-size: 12px; }
.prize { color: #D4A017; font-weight: 700; white-space: nowrap; }
.zero-row { opacity: 0.4; }
.gold { background: linear-gradient(90deg, rgba(212,160,23,0.08) 0%, transparent 100%); }
.silver { background: linear-gradient(90deg, rgba(160,160,160,0.08) 0%, transparent 100%); }
.bronze { background: linear-gradient(90deg, rgba(205,127,50,0.08) 0%, transparent 100%); }
.detail-row td { padding: 0 !important; background: #1a1d2e; }
.detail-table-wrap { padding: 8px 16px 8px 40px; }
.detail-table { width: auto; min-width: 400px; font-size: 12px; }
.detail-table th { background: #252840; font-size: 11px; padding: 6px 10px; color: #bdc3c7; }
.detail-table td { padding: 5px 10px; border-bottom: 1px solid #2c3e50; color: #e0e0e0; }
.rules-card { background: #252840; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); margin-bottom: 24px; }
.rules-table { width: 100%; }
.rules-table th { background: #667eea; color: white; padding: 10px; text-align: left; }
.rules-table td { padding: 10px; border-bottom: 1px solid #2c3e50; color: #e0e0e0; }
.rules-table tr:nth-child(even) td { background: #1a1d2e; }
.stats-bar { margin-top: 16px; padding: 12px; background: #1a1d2e; border-radius: 8px; font-size: 12px; color: #bdc3c7; display: flex; flex-wrap: wrap; gap: 12px; }
@media (max-width: 900px) {
    .kpi-grid { grid-template-columns: repeat(2, 1fr); }
    .dir-grid { grid-template-columns: 1fr; }
    .city-grid { grid-template-columns: 1fr; }
    .dod-grid { grid-template-columns: 1fr; }
    .header h1 { font-size: 20px; }
}
@media (max-width: 600px) {
    .kpi-grid { grid-template-columns: 1fr; }
    body { padding: 10px; }
}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>🏆 Order Penetration Incentive Race Dashboard</h1>
<div class="subtitle">订单渗透激励赛看板 / Painel de Corrida de Incentivo à Penetração</div>
<div class="date">Data as of 数据截至: 2026-08-25 (BRT) | Metropolitan Region | Operating Period: 0819-0825</div>
</div>
""")

# ===== MODULE 1 =====
parts.append('<div class="section-title">📊 MODULE 1: Regional Overview 区域总览 Visão Regional</div>')
parts.append('<div class="section-subtitle">Battle Pool 作战池 Piscina de Batalha</div>')
parts.append('<div class="kpi-grid">')
parts.append(f'<div class="kpi-card"><div class="kpi-value">{R["total_target"]}</div><div class="kpi-label">Target Merchants 目标商家 Alvos</div><div class="kpi-dod"><span class="dod-flat">→ 0</span></div></div>')
parts.append(f'<div class="kpi-card"><div class="kpi-value">{assigned_total} <small>({assigned_pct}%)</small></div><div class="kpi-label">Assigned to BD 已分配BD Atribuído</div><div class="kpi-dod"><span class="{cls(dod_assigned)}">{arrow(dod_assigned)}</span></div></div>')
parts.append(f'<div class="kpi-card"><div class="kpi-value">{R["total_operating"]} <small>({op_pct}%)</small></div><div class="kpi-label">Operating 有效营业 Operando</div><div class="kpi-dod"><span class="{cls(dod["total_operating"])}">{arrow(dod["total_operating"])}</span></div></div>')
parts.append(f'<div class="kpi-card"><div class="kpi-value" style="color:#e74c3c">{R["total_score"]}</div><div class="kpi-label">Total Score 总积分 Pontuação Total</div><div class="kpi-dod"><span class="{cls(dod["total_score"])}">{arrow(dod["total_score"])}</span></div></div>')
parts.append('</div>')

parts.append(f'<div class="dod-card"><h3>📈 Day-over-Day Changes 日环比变化 (vs 08-23)</h3><div class="dod-grid">')
parts.append(f'<div class="dod-item"><span class="dod-label">📊 Overall 总体</span><span class="{cls(dod["total_operating"])}">Operating: {dod["total_operating"]:+d}</span><span class="{cls(dod["total_score"])}">Score: {dod["total_score"]:+d}</span></div>')
parts.append(f'<div class="dod-item"><span class="dod-label">🔴 Not Sign</span><span class="{cls(dod["ns_op"])}">Operating {dod["ns_op"]:+d}</span><span class="{cls(dod["ns_op"]*6)}">Score {dod["ns_op"]*6:+d}</span></div>')
parts.append(f'<div class="dod-item"><span class="dod-label">🟡 Not Online</span><span class="{cls(dod["no_op"])}">Operating {dod["no_op"]:+d}</span><span class="{cls(dod["no_op"]*4)}">Score {dod["no_op"]*4:+d}</span></div>')
parts.append(f'<div class="dod-item"><span class="dod-label">🟢 Not Oper.</span><span class="{cls(dod["nop_op"])}">Operating {dod["nop_op"]:+d}</span><span class="{cls(dod["nop_op"]*3)}">Score {dod["nop_op"]*3:+d}</span></div>')
parts.append('</div></div>')

parts.append('<div class="section-subtitle">Three Attack Directions 三大攻坚方向 Três Direções de Ataque</div><div class="dir-grid">')
for key, icon, color, title, sub in [
    ('ns', '🔴', '#e74c3c', 'Not Signed', '未签约 / Não Assinado'),
    ('no', '🟡', '#f39c12', 'Not Online', '未上线 / Não Online'),
    ('nop', '🟢', '#27ae60', 'Not Operating', '未营业 / Não Operando'),
]:
    t, op, sc = R[f'{key}_target'], R[f'{key}_op'], R[f'{key}_score']
    d = dod[f'{key}_op']
    parts.append(f'''<div class="dir-card">
<div class="dir-header" style="border-left:4px solid {color}">
<span class="dir-icon">{icon}</span><div><div class="dir-title">{title}</div><div class="dir-subtitle">{sub}</div></div></div>
<div class="dir-stats"><div class="dir-stat"><span class="dir-stat-label">Target 目标</span><span class="dir-stat-value">{t}</span></div>
<div class="dir-stat"><span class="dir-stat-label">Operating 营业</span><span class="dir-stat-value">{op} <span class="{cls(d)}">{arrow(d)}</span></span></div>
<div class="dir-stat"><span class="dir-stat-label">Score 积分</span><span class="dir-stat-value">{sc} <span class="{cls(d*(6 if key=="ns" else 4 if key=="no" else 3))}">{arrow(d*(6 if key=="ns" else 4 if key=="no" else 3))}</span></span></div></div>
<div class="progress-bar-wrap"><div class="progress-bar" style="width:{pct(op,t)}%;background:{color}"></div></div>
<div class="dir-pct">{pct(op,t)}%</div></div>''')
parts.append('</div>')

# ===== MODULE 2 =====
parts.append('<div class="section-title">🏙️ MODULE 2: City Battle Overview 城市作战概况 Visão por Cidade</div><div class="city-grid">')
for city, color in [('Southern', '#3498db'), ('Western', '#3498db'), ('Santos', '#3498db')]:
    v = C[city]; dd = city_dod[city]
    parts.append(f'''<div class="city-card"><h3>{city}</h3>
<div class="city-pool">
<div class="city-stat"><span class="city-stat-label">Target 目标</span><span class="city-stat-value">{v["target"]}</span></div>
<div class="city-stat"><span class="city-stat-label">Assigned 已分配</span><span class="city-stat-value">{v["assigned"]} <small>({pct(v["assigned"], v["target"])}%)</small> <span class="{cls(dd["assigned"])}">{arrow(dd["assigned"])}</span></span></div>
<div class="city-stat"><span class="city-stat-label">Unassigned 未分配</span><span class="city-stat-value">{v["target"]-v["assigned"]}</span></div>
<div class="city-stat"><span class="city-stat-label">Operating 营业</span><span class="city-stat-value">{v["operating"]} <span class="{cls(dd["operating"])}">{arrow(dd["operating"])}</span></span></div>
<div class="city-stat"><span class="city-stat-label">Score 积分</span><span class="city-stat-value highlight">{v["score"]} <span class="{cls(dd["score"])}">{arrow(dd["score"])}</span></span></div>
</div>
<div class="progress-bar-wrap"><div class="progress-bar" style="width:{v["op_rate"]}%;background:{color}"></div></div>
<div class="dir-pct">Operating Rate: {v["op_rate"]}%</div>
<div class="city-directions">''')
    for key, icon, label, c in [('ns', '🔴', 'Not Sign 未签约', '#e74c3c'), ('no', '🟡', 'Not Online 未上线', '#f39c12'), ('nop', '🟢', 'Not Oper. 未营业', '#27ae60')]:
        parts.append(f'''<div class="city-dir"><div class="city-dir-label">{icon} {label}</div>
<div class="city-dir-stats"><span>Target: {v[f"{key}_target"]}</span><span>→ Operating: {v[f"{key}_op"]}</span><span>→ Score: {v[f"{key}_score"]}</span></div>
<div class="progress-bar-wrap small"><div class="progress-bar" style="width:{pct(v[f"{key}_op"], v[f"{key}_target"])}%;background:{c}"></div></div></div>''')
    parts.append('</div></div>')
parts.append('</div>')

# ===== MODULE 3: BD rankings =====
DIR_LABEL = {'not_signed': '🔴 Not Sign', 'not_online': '🟡 Not Online', 'not_operating': '🟢 Not Oper.'}

def bd_table_rows(bds, prefix):
    rows = []
    # dense ranking with shared ranks
    rank = 0
    prev_total = None
    position = 0
    for b in bds:
        position += 1
        if b['total'] != prev_total:
            rank = position
            prev_total = b['total']
        if b['total'] == 0:
            rank_disp = ' -'
            row_cls = 'zero-row'
            medal = ''
        else:
            medal = '🥇 ' if rank == 1 else ('🥈 ' if rank == 2 else ('🥉 ' if rank == 3 else ''))
            rank_disp = f'{medal}{rank}' if medal else str(rank)
            row_cls = 'medal-row ' + ('gold' if rank == 1 else 'silver' if rank == 2 else 'bronze' if rank == 3 else '')
        if b['total'] >= 15:
            status = '<span class="status-ok">✅ 达标</span>'
        else:
            status = f'<span class="status-gap">还差 {15 - b["total"]} 分</span>'
        hv_disp = f'+{b["hv_count"]}' if b['hv_count'] > 0 else '-'
        detail_id = f'{prefix}-{b["bd"]}'
        rows.append(f'''<tr class="{row_cls}" onclick="toggleDetail('{detail_id}')" style="cursor:pointer"><td>{rank_disp}</td><td>{b["bd"]} ▶</td><td>{b["bdm"]}</td><td>{b["city"]}</td><td class="score-ns">{b["not_signed"]}</td><td class="score-no">{b["not_online"]}</td><td class="score-nop">{b["not_operating"]}</td><td class="score-hv">{hv_disp}</td><td class="score-total"><b>{b["total"]}</b></td><td>{status}</td><td class="prize"></td></tr>''')
        # detail row
        detail = D['bd_scores_detail'].get(b['bd'], {})
        leads = detail.get('leads', [])
        lead_rows = ''
        for l in leads:
            hv_cell = '+1' if l['hv'] else '-'
            lead_rows += f'<tr><td>{html.escape(str(l["name"]))}</td><td>{DIR_LABEL[l["direction"]]}</td><td>{l["base"]}</td><td>{hv_cell}</td><td><b>{l["score"]}</b></td></tr>\n'
        if lead_rows:
            rows.append(f'''<tr class="detail-row" id="detail-{detail_id}" style="display:none"><td colspan="11"><div class="detail-table-wrap"><table class="detail-table"><thead><tr><th>Lead Name 商家</th><th>Direction 方向</th><th>Base 基础分</th><th>HV 高价值+2</th><th>Subtotal 小计</th></tr></thead><tbody>
{lead_rows}</tbody></table></div></td></tr>''')
    return '\n'.join(rows)

TH = '<table><thead><tr><th>Rank 排名</th><th>BD</th><th>BDM</th><th>City 城市</th><th>🔴 Not Sign 未签约</th><th>🟡 Not Online 未上线</th><th>🟢 Not Oper. 未营业</th><th>HV+2 高价值</th><th>Total 总分</th><th>Status 达标</th><th>Prize 奖金</th></tr></thead><tbody>'

parts.append('<div class="section-title">👤 MODULE 3: BD Personal Rankings BD个人排名 Ranking BD</div>')
parts.append('<div class="tabs"><button class="tab active" onclick="switchTab(\'ws\')">Western + Southern 联合赛区</button><button class="tab" onclick="switchTab(\'santos\')">Santos 赛区</button></div>')
parts.append(f'<div id="tab-ws" class="tab-content active"><div class="table-wrap">{TH}\n{bd_table_rows(D["ws_bds"], "ws")}\n</tbody></table></div></div>')
parts.append(f'<div id="tab-santos" class="tab-content"><div class="table-wrap">{TH}\n{bd_table_rows(D["santos_bds"], "santos")}\n</tbody></table></div></div>')

# ===== MODULE 4: BDM rankings =====
parts.append('<div class="section-title">👥 MODULE 4: BDM Team Rankings BDM团队排名 Ranking BDM</div>')
parts.append('<div class="table-wrap"><table><thead><tr><th>Rank 排名</th><th>BDM</th><th>City 城市</th><th>BD Count BD数</th><th>Team Score 团队总分</th><th>Avg 人均</th><th>Status 达标</th></tr></thead><tbody>')
sorted_bdm = sorted(D['bdm_summary'].items(), key=lambda x: -x[1]['avg'])
rank = 0; prev_avg = None; position = 0
for bdm, v in sorted_bdm:
    position += 1
    if v['avg'] != prev_avg:
        rank = position; prev_avg = v['avg']
    medal = '🥇 ' if rank == 1 else ('🥈 ' if rank == 2 else ('🥉 ' if rank == 3 else ''))
    rank_disp = f'{medal}{rank}' if medal else str(rank)
    row_cls = 'gold' if rank == 1 else ('silver' if rank == 2 else ('bronze' if rank == 3 else ''))
    status = '<span class="status-ok">✅ 达标</span>' if v['qualified'] else f'<span class="status-gap">还差 {round(15 - v["avg"], 2)}</span>'
    parts.append(f'<tr class="{row_cls}"><td>{rank_disp}</td><td>{bdm}</td><td>{v["city"]}</td><td>{v["bd_count"]}</td><td><b>{v["team_score"]}</b></td><td class="score-total"><b>{v["avg"]}</b></td><td>{status}</td></tr>')
parts.append('</tbody></table></div>')

# ===== MODULE 5 =====
parts.append('''<div class="section-title">📋 MODULE 5: Scoring Rules 得分规则 Regras de Pontuação</div>
<div class="rules-card">
<table class="rules-table">
<thead><tr><th>Direction 方向</th><th>Condition 条件</th><th>Base Score 基础分</th><th>HV Bonus 高价值加分</th></tr></thead>
<tbody>
<tr><td>🔴 Not Signed 未签约</td><td>未签约 → 有效营业</td><td>6</td><td>iFood ≥ 20: +2</td></tr>
<tr><td>🟡 Not Online 未上线</td><td>已签未上线 → 有效营业</td><td>4</td><td>iFood ≥ 20: +2</td></tr>
<tr><td>🟢 Not Operating 未营业</td><td>已签不营业 → 恢复营业</td><td>3</td><td>iFood ≥ 20: +2</td></tr>
</tbody></table>
<div class="stats-bar">
<span>有效营业判定: 最近7天营业≥15小时 + ≥1个订单</span>
<span>| BD达标: ≥15分</span>
<span>| BDM达标: 人均≥15分</span>
</div>
</div>
</div>
<script>
function switchTab(tab) {
    document.querySelectorAll('.tab-content').forEach(function(el) {
        if (el.id === 'tab-' + tab) { el.classList.add('active'); }
        else if (el.id.startsWith('tab-')) { el.classList.remove('active'); }
    });
    var tabs = document.querySelectorAll('.tabs')[0].querySelectorAll('.tab');
    tabs.forEach(function(t, i) {
        if ((tab === 'ws' && i === 0) || (tab === 'santos' && i === 1)) t.classList.add('active');
        else t.classList.remove('active');
    });
}
function toggleDetail(id) {
    var row = document.getElementById('detail-' + id);
    if (row) row.style.display = row.style.display === 'none' ? '' : 'none';
}
</script>
</body>
</html>''')

open('order_penetration_dashboard_v4.html', 'w').write('\n'.join(parts))
print('Dashboard written:', len('\n'.join(parts)), 'bytes')
# sanity checks
content = '\n'.join(parts)
assert content.count('</table>') == content.count('<table'), f"table mismatch: {content.count('<table')} vs {content.count('</table>')}"
assert '2026-08-25' in content and '0819-0825' in content
assert 'wanessasilva' in content and '51' in content
ws_rows = sum(1 for b in D['ws_bds']) + sum(1 for b in D['ws_bds'] if b['total'] > 0)
print('OK: tables balanced, WS BDs:', len(D['ws_bds']), 'Santos BDs:', len(D['santos_bds']))
