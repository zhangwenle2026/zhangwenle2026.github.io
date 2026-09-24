import json

with open('/tmp/dashboard_data.json') as f:
    data = json.load(f)

# Previous data (v3, 0804)
prev = {
    'region': {'total': 818, 'assigned': 370, 'operating': 53, 'score': 233},
    'directions': {
        'not sign': {'target': 553, 'operating': 16, 'score': 98},
        'not online': {'target': 46, 'operating': 6, 'score': 28},
        'not operating': {'target': 219, 'operating': 31, 'score': 107}
    },
    'cities': {
        'Southern': {'target': 413, 'assigned': 186, 'operating': 18, 'score': 72},
        'Western': {'target': 331, 'assigned': 158, 'operating': 32, 'score': 148},
        'Santos': {'target': 74, 'assigned': 26, 'operating': 3, 'score': 13}
    }
}

def dod(new, old):
    diff = new - old
    if diff > 0:
        return f'<span class="dod-up">\u2191+{diff}</span>'
    elif diff < 0:
        return f'<span class="dod-down">\u2193{diff}</span>'
    else:
        return f'<span class="dod-flat">\u2192 0</span>'

def dod_pct(new_val, new_total, old_val, old_total):
    new_p = round(new_val/new_total*100, 1) if new_total > 0 else 0
    old_p = round(old_val/old_total*100, 1) if old_total > 0 else 0
    diff = round(new_p - old_p, 1)
    if diff > 0:
        return f'<span class="dod-up">\u2191+{diff}pp</span>'
    elif diff < 0:
        return f'<span class="dod-down">\u2193{diff}pp</span>'
    else:
        return f'<span class="dod-flat">\u2192 0</span>'

r = data['region']
pr = prev['region']

# Direction data
dirs = data['directions']
pdirs = prev['directions']

# City data
cities = data['cities']
pcities = prev['cities']

# BD detail rows generator
def bd_detail_html(bd_entry, idx_prefix):
    bd_id = f"{idx_prefix}-{bd_entry['bd'].replace(' ', '')}"
    details = bd_entry['details']
    if not details:
        return ''
    rows = ''
    dir_icons = {'not sign': '\U0001f534 Not Sign', 'not online': '\U0001f7e1 Not Online', 'not operating': '\U0001f7e2 Not Oper.'}
    for d in details:
        hv_str = f'+{d["hv"]}' if d['hv'] > 0 else '-'
        rows += f'<tr><td>{d["name"]}</td><td>{dir_icons.get(d["dir"], d["dir"])}</td><td>{d["base"]}</td><td>{hv_str}</td><td><b>{d["sub"]}</b></td></tr>\n'
    return f'''<tr class="detail-row" id="detail-{bd_id}" style="display:none"><td colspan="11"><div class="detail-table-wrap"><table class="detail-table"><thead><tr><th>Lead Name \u5546\u5bb6</th><th>Direction \u65b9\u5411</th><th>Base \u57fa\u7840\u5206</th><th>HV \u9ad8\u4ef7\u503c+2</th><th>Subtotal \u5c0f\u8ba1</th></tr></thead><tbody>{rows}</tbody></table></div></td></tr>'''

def bd_table_rows(bd_list, prefix):
    html = ''
    # Assign ranks
    ranked = []
    cur_rank = 0
    prev_score = -1
    for i, b in enumerate(bd_list):
        if b['total'] > 0:
            if b['total'] != prev_score:
                cur_rank = i + 1
                prev_score = b['total']
            ranked.append((cur_rank, b))
        else:
            ranked.append((0, b))

    for rank, b in ranked:
        bd_id = f"{prefix}-{b['bd'].replace(' ', '')}"
        medal = ''
        row_class = ''
        if b['total'] == 0:
            row_class = 'zero-row'
            rank_str = ' -'
        else:
            if rank == 1: medal = '\U0001f947 '; row_class = 'medal-row gold'
            elif rank == 2: medal = '\U0001f948 '; row_class = 'medal-row silver'
            elif rank == 3: medal = '\U0001f949 '; row_class = 'medal-row bronze'
            rank_str = f'{medal}{rank}'

        hv_str = f'+{b["hv"]}' if b['hv'] > 0 else '-'
        gap = 15 - b['total']
        if gap <= 0:
            status = '<span class="status-ok">\u2705 \u8fbe\u6807</span>'
        else:
            status = f'<span class="status-gap">\u8fd8\u5dee {gap} \u5206</span>'

        has_details = len(b['details']) > 0
        click_attr = f' onclick="toggleDetail(\'{bd_id}\')" style="cursor:pointer"' if has_details else ''
        arrow = ' \u25b6' if has_details else ''

        html += f'<tr class="{row_class}"{click_attr}><td>{rank_str}</td><td>{b["bd"]}{arrow}</td><td>{b["bdm"]}</td><td>{b["city"]}</td><td class="score-ns">{b["ns"]}</td><td class="score-no">{b["no"]}</td><td class="score-nop">{b["nop"]}</td><td class="score-hv">{hv_str}</td><td class="score-total"><b>{b["total"]}</b></td><td>{status}</td><td class="prize"></td></tr>\n'
        if has_details:
            html += bd_detail_html(b, prefix)
    return html

def bdm_table_rows(bdm_list):
    html = ''
    for i, b in enumerate(bdm_list):
        rank = i + 1
        medal = ''
        row_class = ''
        if b['avg'] == 0:
            row_class = 'zero-row'
            rank_str = ' -'
        else:
            if rank == 1: medal = '\U0001f947 '; row_class = 'gold'
            elif rank == 2: medal = '\U0001f948 '; row_class = 'silver'
            elif rank == 3: medal = '\U0001f949 '; row_class = 'bronze'
            rank_str = f'{medal}{rank}'
        gap = 15 - b['avg']
        if gap <= 0:
            status = '<span class="status-ok">\u2705 \u8fbe\u6807</span>'
        else:
            status = f'<span class="status-gap">\u8fd8\u5dee {gap:.1f}</span>'
        html += f'<tr class="{row_class}"><td>{rank_str}</td><td>{b["bdm"]}</td><td>{b["city"]}</td><td>{b["bd_count"]}</td><td><b>{b["score"]}</b></td><td class="score-total"><b>{b["avg"]}</b></td><td>{status}</td></tr>\n'
    return html

# DOD summary for directions
dod_summary = ''
for tt_key, tt_label in [('not sign', '\U0001f534 Not Sign'), ('not online', '\U0001f7e1 Not Online'), ('not operating', '\U0001f7e2 Not Oper.')]:
    d_new = dirs[tt_key]
    d_old = pdirs[tt_key]
    op_diff = d_new['operating'] - d_old['operating']
    sc_diff = d_new['score'] - d_old['score']
    op_cls = 'dod-up' if op_diff > 0 else ('dod-down' if op_diff < 0 else 'dod-flat')
    sc_cls = 'dod-up' if sc_diff > 0 else ('dod-down' if sc_diff < 0 else 'dod-flat')
    op_sign = '+' if op_diff > 0 else ''
    sc_sign = '+' if sc_diff > 0 else ''
    dod_summary += f'<div class="dod-item"><span class="dod-label">{tt_label}</span><span class="{op_cls}">Operating {op_sign}{op_diff}</span><span class="{sc_cls}">Score {sc_sign}{sc_diff}</span></div>'

# City direction HTML
def city_card(city_name):
    c = cities[city_name]
    pc = pcities[city_name]
    dirs_html = ''
    for tt_key, tt_label, color in [('not sign', '\U0001f534 Not Sign \u672a\u7b7e\u7ea6', '#e74c3c'),
                                     ('not online', '\U0001f7e1 Not Online \u672a\u4e0a\u7ebf', '#f39c12'),
                                     ('not operating', '\U0001f7e2 Not Oper. \u672a\u8425\u4e1a', '#27ae60')]:
        d = c['directions'][tt_key]
        dirs_html += f'''<div class="city-dir"><div class="city-dir-label">{tt_label}</div>
<div class="city-dir-stats"><span>Target: {d['target']}</span><span>\u2192 Operating: {d['operating']}</span><span>\u2192 Score: {d['score']}</span></div>
<div class="progress-bar-wrap small"><div class="progress-bar" style="width:{d['pct']}%;background:{color}"></div></div></div>'''

    return f'''<div class="city-card"><h3>{city_name}</h3>
<div class="city-pool">
<div class="city-stat"><span class="city-stat-label">Target \u76ee\u6807</span><span class="city-stat-value">{c['target']}</span></div>
<div class="city-stat"><span class="city-stat-label">Assigned \u5df2\u5206\u914d</span><span class="city-stat-value">{c['assigned']} <small>({c['assigned_pct']}%)</small> {dod(c['assigned'], pc['assigned'])}</span></div>
<div class="city-stat"><span class="city-stat-label">Unassigned \u672a\u5206\u914d</span><span class="city-stat-value">{c['unassigned']}</span></div>
<div class="city-stat"><span class="city-stat-label">Operating \u8425\u4e1a</span><span class="city-stat-value">{c['operating']} {dod(c['operating'], pc['operating'])}</span></div>
<div class="city-stat"><span class="city-stat-label">Score \u79ef\u5206</span><span class="city-stat-value highlight">{c['score']} {dod(c['score'], pc['score'])}</span></div>
</div>
<div class="progress-bar-wrap"><div class="progress-bar" style="width:{c['operating_pct']}%;background:#3498db"></div></div>
<div class="dir-pct">Operating Rate: {c['operating_pct']}%</div>
<div class="city-directions">{dirs_html}</div></div>'''

# Build full HTML
html = f'''<!DOCTYPE html>
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
.section-title {{ font-size: 20px; font-weight: 700; margin: 32px 0 16px; padding-left: 12px; border-left: 4px solid #667eea; }}
.section-subtitle {{ font-size: 13px; color: #7f8c8d; margin-top: -12px; margin-bottom: 16px; padding-left: 16px; }}
.kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
.kpi-card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); text-align: center; }}
.kpi-value {{ font-size: 36px; font-weight: 800; color: #2c3e50; }}
.kpi-value small {{ font-size: 16px; color: #95a5a6; font-weight: 400; }}
.kpi-label {{ font-size: 13px; color: #7f8c8d; margin-top: 4px; }}
.kpi-dod {{ font-size: 13px; margin-top: 6px; }}
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
@media (max-width: 900px) {{
    .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .dir-grid {{ grid-template-columns: 1fr; }}
    .city-grid {{ grid-template-columns: 1fr; }}
    .dod-grid {{ grid-template-columns: 1fr; }}
    .header h1 {{ font-size: 20px; }}
}}
@media (max-width: 600px) {{
    .kpi-grid {{ grid-template-columns: 1fr; }}
    body {{ padding: 10px; }}
}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>\U0001f3c6 Order Penetration Incentive Race Dashboard</h1>
<div class="subtitle">\u8ba2\u5355\u6e17\u900f\u6fc0\u52b1\u8d5b\u770b\u677f / Painel de Corrida de Incentivo \u00e0 Penetra\u00e7\u00e3o</div>
<div class="date">Data as of \u6570\u636e\u622a\u81f3: 2026-08-05 (BRT) | Metropolitan Region</div>
</div>

<div class="section-title">\U0001f4ca MODULE 1: Regional Overview \u533a\u57df\u603b\u89c8 Vis\u00e3o Regional</div>
<div class="section-subtitle">Battle Pool \u4f5c\u6218\u6c60 Piscina de Batalha</div>
<div class="kpi-grid">
<div class="kpi-card"><div class="kpi-value">{r['total']}</div><div class="kpi-label">Target Merchants \u76ee\u6807\u5546\u5bb6 Alvos</div><div class="kpi-dod">{dod(r['total'], pr['total'])}</div></div>
<div class="kpi-card"><div class="kpi-value">{r['assigned']} <small>({r['assigned_pct']}%)</small></div><div class="kpi-label">Assigned to BD \u5df2\u5206\u914dBD Atribu\u00eddo</div><div class="kpi-dod">{dod(r['assigned'], pr['assigned'])}</div></div>
<div class="kpi-card"><div class="kpi-value">{r['operating']} <small>({r['operating_pct']}%)</small></div><div class="kpi-label">Operating \u6709\u6548\u8425\u4e1a Operando</div><div class="kpi-dod">{dod(r['operating'], pr['operating'])}</div></div>
<div class="kpi-card"><div class="kpi-value" style="color:#e74c3c">{r['score']}</div><div class="kpi-label">Total Score \u603b\u79ef\u5206 Pontua\u00e7\u00e3o Total</div><div class="kpi-dod">{dod(r['score'], pr['score'])}</div></div>
</div>

<div class="dod-card">
<h3>\U0001f4c8 Day-over-Day Changes \u65e5\u73af\u6bd4\u53d8\u5316 (vs 08-04)</h3>
<div class="dod-grid">
<div class="dod-item"><span class="dod-label">\U0001f4ca Overall \u603b\u4f53</span><span class="{('dod-up' if r['operating']-pr['operating']>0 else 'dod-down' if r['operating']-pr['operating']<0 else 'dod-flat')}">Operating: {r['operating']-pr['operating']:+d}</span><span class="{('dod-up' if r['score']-pr['score']>0 else 'dod-down' if r['score']-pr['score']<0 else 'dod-flat')}">Score: {r['score']-pr['score']:+d}</span></div>
{dod_summary}
</div>
</div>

<div class="section-subtitle">Three Attack Directions \u4e09\u5927\u653b\u575a\u65b9\u5411 Tr\u00eas Dire\u00e7\u00f5es de Ataque</div>
<div class="dir-grid">'''

# Direction cards
dir_configs = [
    ('not sign', '\U0001f534', 'Not Signed', '\u672a\u7b7e\u7ea6 / N\u00e3o Assinado', '#e74c3c'),
    ('not online', '\U0001f7e1', 'Not Online', '\u672a\u4e0a\u7ebf / N\u00e3o Online', '#f39c12'),
    ('not operating', '\U0001f7e2', 'Not Operating', '\u672a\u8425\u4e1a / N\u00e3o Operando', '#27ae60'),
]
for tt_key, icon, title, subtitle, color in dir_configs:
    d = dirs[tt_key]
    pd2 = pdirs[tt_key]
    html += f'''<div class="dir-card">
<div class="dir-header" style="border-left:4px solid {color}">
<span class="dir-icon">{icon}</span><div><div class="dir-title">{title}</div><div class="dir-subtitle">{subtitle}</div></div></div>
<div class="dir-stats"><div class="dir-stat"><span class="dir-stat-label">Target \u76ee\u6807</span><span class="dir-stat-value">{d['target']}</span></div>
<div class="dir-stat"><span class="dir-stat-label">Operating \u8425\u4e1a</span><span class="dir-stat-value">{d['operating']} {dod(d['operating'], pd2['operating'])}</span></div>
<div class="dir-stat"><span class="dir-stat-label">Score \u79ef\u5206</span><span class="dir-stat-value">{d['score']} {dod(d['score'], pd2['score'])}</span></div></div>
<div class="progress-bar-wrap"><div class="progress-bar" style="width:{d['pct']}%;background:{color}"></div></div>
<div class="dir-pct">{d['pct']}%</div></div>'''

html += '</div>'

# City section
html += '''
<div class="section-title">\U0001f3d9\ufe0f MODULE 2: City Battle Overview \u57ce\u5e02\u4f5c\u6218\u6982\u51b5 Vis\u00e3o por Cidade</div>
<div class="city-grid">'''
for c in ['Southern', 'Western', 'Santos']:
    html += city_card(c)
html += '</div>'

# BD Rankings
html += '''
<div class="section-title">\U0001f464 MODULE 3: BD Personal Rankings BD\u4e2a\u4eba\u6392\u540d Ranking BD</div>
<div class="tabs">
<button class="tab active" onclick="switchTab('ws')">Western + Southern \u8054\u5408\u8d5b\u533a</button>
<button class="tab" onclick="switchTab('santos')">Santos \u8d5b\u533a</button>
</div>'''

bd_header = '<thead><tr><th>Rank \u6392\u540d</th><th>BD</th><th>BDM</th><th>City \u57ce\u5e02</th><th>\U0001f534 Not Sign \u672a\u7b7e\u7ea6</th><th>\U0001f7e1 Not Online \u672a\u4e0a\u7ebf</th><th>\U0001f7e2 Not Oper. \u672a\u8425\u4e1a</th><th>HV+2 \u9ad8\u4ef7\u503c</th><th>Total \u603b\u5206</th><th>Status \u8fbe\u6807</th><th>Prize \u5956\u91d1</th></tr></thead>'

html += f'''
<div id="tab-ws" class="tab-content active"><div class="table-wrap">
<table>{bd_header}<tbody>
{bd_table_rows(data['ws_bds'], 'ws')}
</tbody></table></div></div>
<div id="tab-santos" class="tab-content"><div class="table-wrap">
<table>{bd_header}<tbody>
{bd_table_rows(data['santos_bds'], 'santos')}
</tbody></table></div></div>'''

# BDM Rankings
html += '''
<div class="section-title">\U0001f465 MODULE 4: BDM Team Rankings BDM\u56e2\u961f\u6392\u540d Ranking BDM</div>
<div class="tabs">
<button class="tab active" onclick="switchBdmTab('bdm-ws')">Western + Southern \u8054\u5408\u8d5b\u533a</button>
<button class="tab" onclick="switchBdmTab('bdm-santos')">Santos \u8d5b\u533a</button>
</div>'''

bdm_header = '<thead><tr><th>Rank \u6392\u540d</th><th>BDM</th><th>City \u57ce\u5e02</th><th>BD Count BD\u6570</th><th>Team Score \u56e2\u961f\u603b\u5206</th><th>Avg \u4eba\u5747</th><th>Status \u8fbe\u6807</th></tr></thead>'

html += f'''
<div id="tab-bdm-ws" class="tab-content active"><div class="table-wrap">
<table>{bdm_header}<tbody>
{bdm_table_rows(data['ws_bdms'])}
</tbody></table></div></div>
<div id="tab-bdm-santos" class="tab-content"><div class="table-wrap">
<table>{bdm_header}<tbody>
{bdm_table_rows(data['santos_bdms'])}
</tbody></table></div></div>'''

# Rules
html += '''
<div class="section-title">\U0001f4cb MODULE 5: Scoring Rules \u5f97\u5206\u89c4\u5219 Regras de Pontua\u00e7\u00e3o</div>
<div class="rules-card">
<table class="rules-table">
<thead><tr><th>Direction \u65b9\u5411</th><th>Condition \u6761\u4ef6</th><th>Base Score \u57fa\u7840\u5206</th><th>HV Bonus \u9ad8\u4ef7\u503c\u52a0\u5206</th></tr></thead>
<tbody>
<tr><td>\U0001f534 Not Signed \u672a\u7b7e\u7ea6</td><td>\u672a\u7b7e\u7ea6 \u2192 \u6709\u6548\u8425\u4e1a</td><td>6</td><td>iFood\u2265 20: +2</td></tr>
<tr><td>\U0001f7e1 Not Online \u672a\u4e0a\u7ebf</td><td>\u5df2\u7b7e\u672a\u4e0a\u7ebf \u2192 \u6709\u6548\u8425\u4e1a</td><td>4</td><td>iFood\u2265 20: +2</td></tr>
<tr><td>\U0001f7e2 Not Operating \u672a\u8425\u4e1a</td><td>\u5df2\u7b7e\u4e0d\u8425\u4e1a \u2192 \u6062\u590d\u8425\u4e1a</td><td>3</td><td>iFood\u2265 20: +2</td></tr>
</tbody></table>
<div class="stats-bar">
<span>\u6709\u6548\u8425\u4e1a\u5224\u5b9a: \u6700\u8fd17\u5929\u8425\u4e1a\u226515\u5c0f\u65f6 + \u22651\u4e2a\u8ba2\u5355</span>
<span>|\u00a0BD\u8fbe\u6807: \u226515\u5206</span>
<span>|\u00a0BDM\u8fbe\u6807: \u4eba\u5747\u226515\u5206</span>
</div>
</div>'''

# Footer + JS
html += '''
</div>
<script>
function switchTab(tab) {
    document.querySelectorAll('.tab-content').forEach(function(el) {
        if (el.id === 'tab-' + tab) { el.classList.add('active'); }
        else if (el.id.startsWith('tab-') && !el.id.startsWith('tab-bdm-')) { el.classList.remove('active'); }
    });
    var tabs = document.querySelectorAll('.tabs')[0].querySelectorAll('.tab');
    tabs.forEach(function(t, i) {
        if ((tab === 'ws' && i === 0) || (tab === 'santos' && i === 1)) t.classList.add('active');
        else t.classList.remove('active');
    });
}
function switchBdmTab(tab) {
    document.querySelectorAll('.tab-content').forEach(function(el) {
        if (el.id === tab) { el.classList.add('active'); }
        else if (el.id.startsWith('tab-bdm-')) { el.classList.remove('active'); }
    });
    var tabs = document.querySelectorAll('.tabs')[1].querySelectorAll('.tab');
    tabs.forEach(function(t, i) {
        if ((tab === 'bdm-ws' && i === 0) || (tab === 'bdm-santos' && i === 1)) t.classList.add('active');
        else t.classList.remove('active');
    });
}
function toggleDetail(id) {
    var row = document.getElementById('detail-' + id);
    if (row) row.style.display = row.style.display === 'none' ? '' : 'none';
}
</script>
</body>
</html>'''

with open('order_penetration_dashboard_v4.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Generated: {len(html)} bytes")
print("DONE")
