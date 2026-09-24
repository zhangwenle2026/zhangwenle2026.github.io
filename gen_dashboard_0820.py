#!/usr/bin/env python3
"""
Generate order penetration dashboard HTML from order_penetration_data_0820_final.json
Based on gen_dashboard_0819.py structure with dark theme.
"""
import json

# Load the final data
with open('order_penetration_data_0820_final.json') as f:
    data = json.load(f)

# Build dashboard data structure from the final JSON
rs = data['regional_summary']
prev = data['previous']

total_target = rs['total_target']
total_assigned = sum(data['city_summary'][c].get('assigned', 0) for c in data['city_summary'])
total_operating = rs['total_operating']
total_score = rs['total_score']

region = {
    'total': total_target,
    'assigned': total_assigned,
    'assigned_pct': round(total_assigned / total_target * 100, 1) if total_target else 0,
    'operating': total_operating,
    'operating_pct': round(total_operating / total_target * 100, 1) if total_target else 0,
    'score': total_score,
}

directions = {
    'not sign': {
        'target': rs['ns_target'], 'operating': rs['ns_op'], 'score': rs['ns_score'],
        'pct': round(rs['ns_op'] / rs['ns_target'] * 100, 1) if rs['ns_target'] else 0,
    },
    'not online': {
        'target': rs['no_target'], 'operating': rs['no_op'], 'score': rs['no_score'],
        'pct': round(rs['no_op'] / rs['no_target'] * 100, 1) if rs['no_target'] else 0,
    },
    'not operating': {
        'target': rs['nop_target'], 'operating': rs['nop_op'], 'score': rs['nop_score'],
        'pct': round(rs['nop_op'] / rs['nop_target'] * 100, 1) if rs['nop_target'] else 0,
    },
}

cities = {}
for c in ['Southern', 'Western', 'Santos']:
    cd = data['city_summary'][c]
    cities[c] = {
        'target': cd['target'],
        'assigned': cd.get('assigned', 0),
        'assigned_pct': round(cd.get('assigned', 0) / cd['target'] * 100, 1) if cd['target'] else 0,
        'unassigned': cd['target'] - cd.get('assigned', 0),
        'operating': cd['operating'],
        'operating_pct': round(cd['operating'] / cd['target'] * 100, 1) if cd['target'] else 0,
        'score': cd['score'],
        'directions': {
            'not sign': {
                'target': cd['ns_target'], 'operating': cd['ns_op'], 'score': cd['ns_score'],
                'pct': round(cd['ns_op'] / cd['ns_target'] * 100, 1) if cd['ns_target'] else 0,
            },
            'not online': {
                'target': cd['no_target'], 'operating': cd['no_op'], 'score': cd['no_score'],
                'pct': round(cd['no_op'] / cd['no_target'] * 100, 1) if cd['no_target'] else 0,
            },
            'not operating': {
                'target': cd['nop_target'], 'operating': cd['nop_op'], 'score': cd['nop_score'],
                'pct': round(cd['nop_op'] / cd['nop_target'] * 100, 1) if cd['nop_target'] else 0,
            },
        },
    }

# Build BD lists with dashboard format
dir_label_map = {'not_signed': 'not sign', 'not_online': 'not online', 'not_operating': 'not operating'}

ws_bds = []
santos_bds = []
for bd_entry in data['ws_bds']:
    details = []
    for lead in bd_entry.get('leads', []):
        details.append({
            'name': lead['name'],
            'dir': dir_label_map.get(lead['direction'], lead['direction']),
            'base': lead['base'],
            'hv': lead['hv'],
            'sub': lead['score'],
        })
    hv_count = bd_entry['hv_bonus'] // 2
    entry = {
        'bd': bd_entry['bd'], 'bdm': bd_entry['bdm'], 'city': bd_entry['city'],
        'ns': bd_entry['not_signed'], 'no': bd_entry['not_online'], 'nop': bd_entry['not_operating'],
        'hv': hv_count, 'total': bd_entry['total'], 'details': details,
    }
    ws_bds.append(entry)

for bd_entry in data['santos_bds']:
    details = []
    for lead in bd_entry.get('leads', []):
        details.append({
            'name': lead['name'],
            'dir': dir_label_map.get(lead['direction'], lead['direction']),
            'base': lead['base'], 'hv': lead['hv'], 'sub': lead['score'],
        })
    hv_count = bd_entry['hv_bonus'] // 2
    entry = {
        'bd': bd_entry['bd'], 'bdm': bd_entry['bdm'], 'city': bd_entry['city'],
        'ns': bd_entry['not_signed'], 'no': bd_entry['not_online'], 'nop': bd_entry['not_operating'],
        'hv': hv_count, 'total': bd_entry['total'], 'details': details,
    }
    santos_bds.append(entry)

# Build BDM list - ALL 12 unified
all_bdms = []
for bdm_name, d in data['bdm_summary'].items():
    all_bdms.append({
        'bdm': bdm_name, 'city': d['city'], 'bd_count': d['bd_count'],
        'score': d['team_score'], 'avg': d['avg'],
    })
all_bdms.sort(key=lambda x: -x['avg'])

# Previous data for DOD
prev_region = {
    'total': total_target,
    'assigned': sum(prev['cities'][c].get('assigned', 0) for c in prev['cities']),
    'operating': prev['total_operating'],
    'score': prev['total_score'],
}
prev_directions = {
    'not sign': {'target': rs['ns_target'], 'operating': prev['ns_op'], 'score': prev['ns_op'] * 6},
    'not online': {'target': rs['no_target'], 'operating': prev['no_op'], 'score': prev['no_op'] * 4},
    'not operating': {'target': rs['nop_target'], 'operating': prev['nop_op'], 'score': prev['nop_op'] * 3},
}
prev_cities = {}
for c in ['Southern', 'Western', 'Santos']:
    pc = prev['cities'].get(c, {})
    prev_cities[c] = {
        'target': pc.get('target', 0), 'assigned': pc.get('assigned', 0),
        'operating': pc.get('operating', 0), 'score': pc.get('score', 0),
    }

# ===== DOD HELPERS =====
def dod(new, old):
    diff = new - old
    if diff > 0:
        return f'<span class="dod-up">\u2191+{diff}</span>'
    elif diff < 0:
        return f'<span class="dod-down">\u2193{diff}</span>'
    else:
        return f'<span class="dod-flat">\u2192 0</span>'

r = region
pr = prev_region
dirs = directions
pdirs = prev_directions

# ===== HTML BUILDING BLOCKS =====
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
    return f'<tr class="detail-row" id="detail-{bd_id}" style="display:none"><td colspan="11"><div class="detail-table-wrap"><table class="detail-table"><thead><tr><th>Lead Name \u5546\u5bb6</th><th>Direction \u65b9\u5411</th><th>Base \u57fa\u7840\u5206</th><th>HV \u9ad8\u4ef7\u503c+2</th><th>Subtotal \u5c0f\u8ba1</th></tr></thead><tbody>{rows}</tbody></table></div></td></tr>'

def bd_table_rows(bd_list, prefix):
    html = ''
    cur_rank = 0
    prev_score = -1
    for i, b in enumerate(bd_list):
        if b['total'] > 0:
            if b['total'] != prev_score:
                cur_rank = i + 1
                prev_score = b['total']
        else:
            cur_rank = 0
        rank = cur_rank
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
        click_attr = f" onclick=\"toggleDetail('{bd_id}')\" style=\"cursor:pointer\"" if has_details else ''
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

def city_card(city_name):
    c = cities[city_name]
    pc = prev_cities[city_name]
    dirs_html = ''
    for tt_key, tt_label, color in [('not sign', '\U0001f534 Not Sign \u672a\u7b7e\u7ea6', '#e74c3c'),
                                     ('not online', '\U0001f7e1 Not Online \u672a\u4e0a\u7ebf', '#f39c12'),
                                     ('not operating', '\U0001f7e2 Not Oper. \u672a\u8425\u4e1a', '#27ae60')]:
        d = c['directions'][tt_key]
        dirs_html += f'<div class="city-dir"><div class="city-dir-label">{tt_label}</div>\n<div class="city-dir-stats"><span>Target: {d["target"]}</span><span>\u2192 Operating: {d["operating"]}</span><span>\u2192 Score: {d["score"]}</span></div>\n<div class="progress-bar-wrap small"><div class="progress-bar" style="width:{d["pct"]}%;background:{color}"></div></div></div>'
    return f'<div class="city-card"><h3>{city_name}</h3>\n<div class="city-pool">\n<div class="city-stat"><span class="city-stat-label">Target \u76ee\u6807</span><span class="city-stat-value">{c["target"]}</span></div>\n<div class="city-stat"><span class="city-stat-label">Assigned \u5df2\u5206\u914d</span><span class="city-stat-value">{c["assigned"]} <small>({c["assigned_pct"]}%)</small> {dod(c["assigned"], pc["assigned"])}</span></div>\n<div class="city-stat"><span class="city-stat-label">Unassigned \u672a\u5206\u914d</span><span class="city-stat-value">{c["unassigned"]}</span></div>\n<div class="city-stat"><span class="city-stat-label">Operating \u8425\u4e1a</span><span class="city-stat-value">{c["operating"]} {dod(c["operating"], pc["operating"])}</span></div>\n<div class="city-stat"><span class="city-stat-label">Score \u79ef\u5206</span><span class="city-stat-value highlight">{c["score"]} {dod(c["score"], pc["score"])}</span></div>\n</div>\n<div class="progress-bar-wrap"><div class="progress-bar" style="width:{c["operating_pct"]}%;background:#3498db"></div></div>\n<div class="dir-pct">Operating Rate: {c["operating_pct"]}%</div>\n<div class="city-directions">{dirs_html}</div></div>'

# ===== BUILD FULL HTML =====
html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Order Penetration Incentive Race Dashboard</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #1a1d2e; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #e0e0e0; padding: 20px; }}
.container {{ max-width: 1400px; margin: 0 auto; }}
.header {{ text-align: center; padding: 30px 20px; margin-bottom: 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px; color: white; }}
.header h1 {{ font-size: 28px; margin-bottom: 4px; }}
.header .subtitle {{ font-size: 16px; opacity: 0.9; }}
.header .date {{ font-size: 13px; opacity: 0.75; margin-top: 8px; }}
.section-title {{ font-size: 20px; font-weight: 700; margin: 32px 0 16px; padding-left: 12px; border-left: 4px solid #667eea; color: #e0e0e0; }}
.section-subtitle {{ font-size: 13px; color: #95a5a6; margin-top: -12px; margin-bottom: 16px; padding-left: 16px; }}
.kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
.kpi-card {{ background: #252840; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); text-align: center; }}
.kpi-value {{ font-size: 36px; font-weight: 800; color: #e0e0e0; }}
.kpi-value small {{ font-size: 16px; color: #95a5a6; font-weight: 400; }}
.kpi-label {{ font-size: 13px; color: #95a5a6; margin-top: 4px; }}
.kpi-dod {{ font-size: 13px; margin-top: 6px; }}
.dod-up {{ color: #2ecc71; font-weight: 600; }}
.dod-down {{ color: #e74c3c; font-weight: 600; }}
.dod-flat {{ color: #95a5a6; }}
.dod-card {{ background: #252840; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); margin-bottom: 24px; }}
.dod-card h3 {{ font-size: 16px; margin-bottom: 16px; color: #bdc3c7; }}
.dod-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
.dod-item {{ display: flex; flex-direction: column; gap: 4px; padding: 12px; background: #1a1d2e; border-radius: 8px; }}
.dod-label {{ font-size: 13px; font-weight: 600; color: #bdc3c7; margin-bottom: 4px; }}
.dir-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }}
.dir-card {{ background: #252840; border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); }}
.dir-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 12px; padding: 8px; border-radius: 8px; background: #1a1d2e; }}
.dir-icon {{ font-size: 20px; }}
.dir-title {{ font-size: 15px; font-weight: 600; }}
.dir-subtitle {{ font-size: 11px; color: #95a5a6; }}
.dir-stats {{ display: flex; justify-content: space-between; margin-bottom: 10px; }}
.dir-stat {{ text-align: center; }}
.dir-stat-label {{ display: block; font-size: 11px; color: #95a5a6; }}
.dir-stat-value {{ display: block; font-size: 20px; font-weight: 700; }}
.dir-pct {{ text-align: right; font-size: 12px; color: #95a5a6; margin-top: 4px; }}
.progress-bar-wrap {{ background: #1a1d2e; border-radius: 6px; height: 8px; overflow: hidden; }}
.progress-bar-wrap.small {{ height: 5px; margin-top: 4px; }}
.progress-bar {{ height: 100%; border-radius: 6px; transition: width 0.6s ease; min-width: 2px; }}
.city-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }}
.city-card {{ background: #252840; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); }}
.city-card h3 {{ font-size: 18px; font-weight: 700; margin-bottom: 12px; color: #bdc3c7; }}
.city-pool {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 12px; }}
.city-stat {{ display: flex; justify-content: space-between; padding: 4px 0; }}
.city-stat-label {{ font-size: 12px; color: #95a5a6; }}
.city-stat-value {{ font-size: 14px; font-weight: 600; color: #e0e0e0; }}
.city-stat-value.highlight {{ color: #e74c3c; font-size: 16px; }}
.city-stat-value small {{ font-size: 11px; color: #95a5a6; font-weight: 400; }}
.city-directions {{ margin-top: 16px; }}
.city-dir {{ margin-bottom: 10px; padding: 8px; background: #1a1d2e; border-radius: 8px; }}
.city-dir-label {{ font-size: 13px; font-weight: 600; margin-bottom: 4px; color: #bdc3c7; }}
.city-dir-stats {{ font-size: 12px; color: #bdc3c7; display: flex; gap: 12px; }}
.tabs {{ display: flex; gap: 0; margin-bottom: 0; }}
.tab {{ padding: 10px 24px; background: #1a1d2e; border: none; cursor: pointer; font-size: 14px; font-weight: 600; color: #95a5a6; border-radius: 8px 8px 0 0; }}
.tab.active {{ background: #252840; color: #e0e0e0; box-shadow: 0 -2px 8px rgba(0,0,0,0.3); }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}
.table-wrap {{ background: #252840; border-radius: 0 12px 12px 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); overflow-x: auto; margin-bottom: 24px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
thead th {{ background: #1a1d2e; padding: 10px 8px; text-align: left; font-weight: 600; font-size: 12px; color: #bdc3c7; border-bottom: 2px solid #2c3e50; white-space: nowrap; }}
tbody td {{ padding: 8px; border-bottom: 1px solid #2c3e50; vertical-align: middle; color: #e0e0e0; }}
tbody tr:hover {{ background: #2c3e50; }}
.score-ns {{ color: #e74c3c; font-weight: 600; }}
.score-no {{ color: #f39c12; font-weight: 600; }}
.score-nop {{ color: #2ecc71; font-weight: 600; }}
.score-hv {{ color: #9b59b6; font-weight: 600; }}
.score-total {{ font-size: 15px; }}
.status-ok {{ color: #2ecc71; font-weight: 600; font-size: 12px; }}
.status-gap {{ color: #e74c3c; font-weight: 600; font-size: 12px; }}
.prize {{ color: #D4A017; font-weight: 700; white-space: nowrap; }}
.zero-row {{ opacity: 0.4; }}
.gold {{ background: linear-gradient(90deg, rgba(212,160,23,0.08) 0%, transparent 100%); }}
.silver {{ background: linear-gradient(90deg, rgba(160,160,160,0.08) 0%, transparent 100%); }}
.bronze {{ background: linear-gradient(90deg, rgba(205,127,50,0.08) 0%, transparent 100%); }}
.detail-row td {{ padding: 0 !important; background: #1a1d2e; }}
.detail-table-wrap {{ padding: 8px 16px 8px 40px; }}
.detail-table {{ width: auto; min-width: 400px; font-size: 12px; }}
.detail-table th {{ background: #252840; font-size: 11px; padding: 6px 10px; color: #bdc3c7; }}
.detail-table td {{ padding: 5px 10px; border-bottom: 1px solid #2c3e50; color: #e0e0e0; }}
.rules-card {{ background: #252840; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); margin-bottom: 24px; }}
.rules-table {{ width: 100%; }}
.rules-table th {{ background: #667eea; color: white; padding: 10px; text-align: left; }}
.rules-table td {{ padding: 10px; border-bottom: 1px solid #2c3e50; color: #e0e0e0; }}
.rules-table tr:nth-child(even) td {{ background: #1a1d2e; }}
.stats-bar {{ margin-top: 16px; padding: 12px; background: #1a1d2e; border-radius: 8px; font-size: 12px; color: #bdc3c7; display: flex; flex-wrap: wrap; gap: 12px; }}
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
<div class="date">Data as of \u6570\u636e\u622a\u81f3: 2026-08-20 (BRT) | Metropolitan Region | Operating Period: 0814-0820</div>
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
<h3>\U0001f4c8 Day-over-Day Changes \u65e5\u73af\u6bd4\u53d8\u5316 (vs 08-19)</h3>
<div class="dod-grid">
<div class="dod-item"><span class="dod-label">\U0001f4ca Overall \u603b\u4f53</span><span class="{('dod-up' if r['operating']-pr['operating']>0 else 'dod-down' if r['operating']-pr['operating']<0 else 'dod-flat')}">Operating: {r['operating']-pr['operating']:+d}</span><span class="{('dod-up' if r['score']-pr['score']>0 else 'dod-down' if r['score']-pr['score']<0 else 'dod-flat')}">Score: {r['score']-pr['score']:+d}</span></div>
{dod_summary}
</div>
</div>

<div class="section-subtitle">Three Attack Directions \u4e09\u5927\u653b\u575a\u65b9\u5411 Tr\u00eas Dire\u00e7\u00f5es de Ataque</div>
<div class="dir-grid">'''

dir_configs = [
    ('not sign', '\U0001f534', 'Not Signed', '\u672a\u7b7e\u7ea6 / N\u00e3o Assinado', '#e74c3c'),
    ('not online', '\U0001f7e1', 'Not Online', '\u672a\u4e0a\u7ebf / N\u00e3o Online', '#f39c12'),
    ('not operating', '\U0001f7e2', 'Not Operating', '\u672a\u8425\u4e1a / N\u00e3o Operando', '#27ae60'),
]
for tt_key, icon, title, subtitle, color in dir_configs:
    d = dirs[tt_key]
    pd2 = pdirs[tt_key]
    html += f'<div class="dir-card">\n<div class="dir-header" style="border-left:4px solid {color}">\n<span class="dir-icon">{icon}</span><div><div class="dir-title">{title}</div><div class="dir-subtitle">{subtitle}</div></div></div>\n<div class="dir-stats"><div class="dir-stat"><span class="dir-stat-label">Target \u76ee\u6807</span><span class="dir-stat-value">{d["target"]}</span></div>\n<div class="dir-stat"><span class="dir-stat-label">Operating \u8425\u4e1a</span><span class="dir-stat-value">{d["operating"]} {dod(d["operating"], pd2["operating"])}</span></div>\n<div class="dir-stat"><span class="dir-stat-label">Score \u79ef\u5206</span><span class="dir-stat-value">{d["score"]} {dod(d["score"], pd2["score"])}</span></div></div>\n<div class="progress-bar-wrap"><div class="progress-bar" style="width:{d["pct"]}%;background:{color}"></div></div>\n<div class="dir-pct">{d["pct"]}%</div></div>'

html += '</div>'

# City section
html += '\n<div class="section-title">\U0001f3d9\ufe0f MODULE 2: City Battle Overview \u57ce\u5e02\u4f5c\u6218\u6982\u51b5 Vis\u00e3o por Cidade</div>\n<div class="city-grid">'
for c in ['Southern', 'Western', 'Santos']:
    html += city_card(c)
html += '</div>'

bd_header = '<thead><tr><th>Rank \u6392\u540d</th><th>BD</th><th>BDM</th><th>City \u57ce\u5e02</th><th>\U0001f534 Not Sign \u672a\u7b7e\u7ea6</th><th>\U0001f7e1 Not Online \u672a\u4e0a\u7ebf</th><th>\U0001f7e2 Not Oper. \u672a\u8425\u4e1a</th><th>HV+2 \u9ad8\u4ef7\u503c</th><th>Total \u603b\u5206</th><th>Status \u8fbe\u6807</th><th>Prize \u5956\u91d1</th></tr></thead>'

html += '''
<div class="section-title">\U0001f464 MODULE 3: BD Personal Rankings BD\u4e2a\u4eba\u6392\u540d Ranking BD</div>
<div class="tabs">
<button class="tab active" onclick="switchTab('ws')">Western + Southern \u8054\u5408\u8d5b\u533a</button>
<button class="tab" onclick="switchTab('santos')">Santos \u8d5b\u533a</button>
</div>
<div id="tab-ws" class="tab-content active"><div class="table-wrap">
<table>''' + bd_header + '''<tbody>
''' + bd_table_rows(ws_bds, 'ws') + '''
</tbody></table></div></div>
<div id="tab-santos" class="tab-content"><div class="table-wrap">
<table>''' + bd_header + '''<tbody>
''' + bd_table_rows(santos_bds, 'santos') + '''
</tbody></table></div></div>'''

# BDM Rankings - ALL 12 unified, no tabs
html += '''
<div class="section-title">\U0001f465 MODULE 4: BDM Team Rankings BDM\u56e2\u961f\u6392\u540d Ranking BDM</div>
<div class="table-wrap">
<table><thead><tr><th>Rank \u6392\u540d</th><th>BDM</th><th>City \u57ce\u5e02</th><th>BD Count BD\u6570</th><th>Team Score \u56e2\u961f\u603b\u5206</th><th>Avg \u4eba\u5747</th><th>Status \u8fbe\u6807</th></tr></thead><tbody>
''' + bdm_table_rows(all_bdms) + '''
</tbody></table></div>'''

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
<span>| BD\u8fbe\u6807: \u226515\u5206</span>
<span>| BDM\u8fbe\u6807: \u4eba\u5747\u226515\u5206</span>
</div>
</div>'''

html += '''
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
</html>'''

with open('order_penetration_dashboard_v4.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Generated HTML: {len(html)} bytes")
print("DONE")
print(f"WS BDs: {len(ws_bds)}, Santos BDs: {len(santos_bds)}, BDMs: {len(all_bdms)}")
qualified_ws = [b for b in ws_bds if b['total'] >= 15]
qualified_santos = [b for b in santos_bds if b['total'] >= 15]
qualified_bdms = [b for b in all_bdms if b['avg'] >= 15]
print(f"Qualified BDs (WS): {len(qualified_ws)}, Santos: {len(qualified_santos)}, Total: {len(qualified_ws)+len(qualified_santos)}")
print(f"Qualified BDMs: {len(qualified_bdms)}")
print(f"Region: target={r['total']}, assigned={r['assigned']}, operating={r['operating']}, score={r['score']}")
