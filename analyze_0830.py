import openpyxl
import json
from collections import defaultdict

# ===== CONFIG =====
NEW_FILE = "redtop2000merchantsstatus-0830.xlsx"
NEW_DATE = "0830"
NEW_PERIOD = "0824-0830"
PREV_FILE = "order_penetration_data_0827_final.json"
OUT_FILE = "order_penetration_data_0830_final.json"

# Find columns by prefix
wb = openpyxl.load_workbook(NEW_FILE, data_only=True)
ws = wb['Sheet1']
headers = [ws.cell(1, c).value for c in range(1, ws.max_column+1)]
cols = {h: i+1 for i, h in enumerate(headers) if h}
sign_col = next(cols[h] for h in headers if h and h.startswith('sign-'))
op_col = next(cols[h] for h in headers if h and 'operating' in str(h))
print(f"sign col: {sign_col} ({headers[sign_col-1]}), operating col: {op_col} ({headers[op_col-1]})")

metro_cities = {'Southern São Paulo Metropolitan', 'Western São Paulo Metropolitan', 'Santos City'}

ROSTER = {
    'Southern São Paulo Metropolitan': {
        'adriananaves': ['brunacrelien', 'elisangelasouza', 'evaldosilva', 'ivanfelizardo', 'josenascimento', 'murilosilva', 'rodrigoalmeida', 'tiagodangelo', 'wanessasilva'],
        'fernandooliveira': ['brunapadilha', 'carlosmotta', 'cristianedasilva', 'erikboilesen', 'felipesanches', 'pedrosaccone', 'wainnergonzales', 'wellingtonsantos'],
        'eduardoalbuquerque': ['allanmaalouli', 'felipesilva', 'fernandoquintiliano', 'joycepurificacao', 'otaviomazzega', 'thaisvasconcelos'],
        'alisaeed': ['camilabatista', 'davidcaramaschi', 'eduardosantos', 'marciajesuino', 'ricardoaraujo', 'rodrigocorreia'],
        'tadeumoraes': ['leandroresende', 'lucasreis', 'matheuscoelho', 'paulosantos', 'paulosilva', 'ricardoalmeida'],
    },
    'Western São Paulo Metropolitan': {
        'biancaceotto': ['caiolorencato', 'karinacolomina', 'luizmoreira', 'nayannedias', 'nicolemenezes', 'nilmaxfranca', 'rodrigopoli'],
        'cesararraes': ['guilhermesantos', 'jadycarvalho', 'johnataguimaraes', 'kevinberti', 'renansilva', 'williamhenrique'],
        'thiagoscavazini': ['barbaraoliveira', 'claudiareis', 'felipecruz', 'heloisamagnani', 'marialisboa', 'milenasantana'],
        'igorfeitosa': ['alexlima', 'igorsouza', 'marcelofeitosa', 'tamirislopes', 'tatianarodrigues'],
        'lucasferreira': ['clebersoares', 'lucasnada', 'tatianeribeiro', 'valeriachacon'],
    },
    'Santos City': {
        'sabrinafernandes': ['brunosalmaso', 'ericabarbosa', 'felipebarbosa', 'giovanabareno'],
        'renataleite': ['jessicarossi', 'joaocastro', 'luizmarques', 'nathaliabernardino'],
    },
}

all_roster_bds = set()
bd_to_bdm = {}
bd_to_city = {}
for city_full, bdm_map in ROSTER.items():
    city_short = city_full.split(' São Paulo')[0] if 'São Paulo' in city_full else city_full.replace(' City','')
    for bdm, bd_list in bdm_map.items():
        for bd in bd_list:
            all_roster_bds.add(bd)
            bd_to_bdm[bd] = bdm
            bd_to_city[bd] = city_short

all_rows = []
for r in range(2, ws.max_row+1):
    region = ws.cell(r, cols['region']).value
    city = ws.cell(r, cols['city']).value
    if region == 'Metropolitan Region' and city in metro_cities:
        all_rows.append({
            'lead_name': ws.cell(r, cols['Lead Name']).value,
            'red_order': ws.cell(r, cols['red order']).value,
            'city': city,
            'target_type': ws.cell(r, cols['target type']).value,
            'bd': ws.cell(r, cols['BD']).value,
            'bdm': ws.cell(r, cols['BDM']).value,
            'sign': ws.cell(r, sign_col).value,
            'operating': ws.cell(r, op_col).value,
        })

dir_map = {
    'not sign': ('not_signed', 6),
    'not online': ('not_online', 4),
    'not operating': ('not_operating', 3),
}

# ===== BD-LEVEL SCORES (roster BDs only) =====
bd_scores = defaultdict(lambda: {'not_signed': 0, 'not_online': 0, 'not_operating': 0, 'hv_bonus': 0, 'hv_count': 0, 'total': 0, 'leads': []})
for r in all_rows:
    bd = r['bd']
    if bd not in all_roster_bds:
        continue
    tt = r['target_type']
    if tt not in dir_map:
        continue
    if r['operating'] != 1:
        continue
    direction, base = dir_map[tt]
    hv = 1 if (r['red_order'] and r['red_order'] >= 20) else 0
    score = base + (2 if hv else 0)
    bd_scores[bd][direction] += 1
    bd_scores[bd]['hv_bonus'] += (2 if hv else 0)
    bd_scores[bd]['hv_count'] += hv
    bd_scores[bd]['total'] += score
    bd_scores[bd]['leads'].append({
        'name': r['lead_name'],
        'direction': direction,
        'base': base,
        'hv': hv,
        'score': score,
    })

# ===== BDM SCORES =====
bdm_data = {}
for city_full, bdm_map in ROSTER.items():
    city_short = city_full.split(' São Paulo')[0] if 'São Paulo' in city_full else city_full.replace(' City','')
    for bdm, bd_list in bdm_map.items():
        team_score = sum(bd_scores[bd]['total'] for bd in bd_list if bd in bd_scores)
        bd_count = len(bd_list)
        avg = team_score / bd_count if bd_count > 0 else 0
        bdm_data[bdm] = {
            'city': city_short, 'bd_count': bd_count, 'team_score': team_score,
            'avg': round(avg, 2), 'qualified': avg >= 15,
        }

# ===== BD LISTS =====
ws_bds, santos_bds = [], []
for bd in all_roster_bds:
    sc = bd_scores.get(bd, {'not_signed': 0, 'not_online': 0, 'not_operating': 0, 'hv_bonus': 0, 'hv_count': 0, 'total': 0, 'leads': []})
    entry = {'bd': bd, 'bdm': bd_to_bdm[bd], 'city': bd_to_city[bd], **sc}
    (santos_bds if bd_to_city[bd] == 'Santos' else ws_bds).append(entry)
ws_bds.sort(key=lambda x: -x['total'])
santos_bds.sort(key=lambda x: -x['total'])

# ===== REGIONAL OVERVIEW =====
total_target = len(all_rows)
total_signed = sum(1 for r in all_rows if r['sign'] == 1)
total_operating = sum(1 for r in all_rows if r['operating'] == 1)
ns_t = sum(1 for r in all_rows if r['target_type'] == 'not sign')
no_t = sum(1 for r in all_rows if r['target_type'] == 'not online')
nop_t = sum(1 for r in all_rows if r['target_type'] == 'not operating')
ns_op = sum(1 for r in all_rows if r['target_type'] == 'not sign' and r['operating'] == 1)
no_op = sum(1 for r in all_rows if r['target_type'] == 'not online' and r['operating'] == 1)
nop_op = sum(1 for r in all_rows if r['target_type'] == 'not operating' and r['operating'] == 1)

total_score_all = 0
hv_count_all = 0
for r in all_rows:
    if r['target_type'] not in dir_map or r['operating'] != 1:
        continue
    direction, base = dir_map[r['target_type']]
    hv = 1 if (r['red_order'] and r['red_order'] >= 20) else 0
    total_score_all += base + (2 if hv else 0)
    hv_count_all += hv

bd_level_score = sum(sc['total'] for sc in bd_scores.values())

# ===== CITY OVERVIEW =====
city_data = {}
for city_full in ['Southern São Paulo Metropolitan', 'Western São Paulo Metropolitan', 'Santos City']:
    city_short = city_full.split(' São Paulo')[0] if 'São Paulo' in city_full else city_full.replace(' City','')
    c_rows = [r for r in all_rows if r['city'] == city_full]
    c_op = sum(1 for r in c_rows if r['operating'] == 1)
    c_ns_t = sum(1 for r in c_rows if r['target_type'] == 'not sign')
    c_no_t = sum(1 for r in c_rows if r['target_type'] == 'not online')
    c_nop_t = sum(1 for r in c_rows if r['target_type'] == 'not operating')
    c_ns_op = sum(1 for r in c_rows if r['target_type'] == 'not sign' and r['operating'] == 1)
    c_no_op = sum(1 for r in c_rows if r['target_type'] == 'not online' and r['operating'] == 1)
    c_nop_op = sum(1 for r in c_rows if r['target_type'] == 'not operating' and r['operating'] == 1)
    c_hv = sum(1 for r in c_rows if r['operating'] == 1 and r['red_order'] and r['red_order'] >= 20)
    c_score = c_ns_op*6 + c_no_op*4 + c_nop_op*3 + c_hv*2
    c_assigned = sum(1 for r in c_rows if r['bd'] in all_roster_bds)
    city_data[city_short] = {
        'target': len(c_rows), 'signed': sum(1 for r in c_rows if r['sign'] == 1),
        'operating': c_op, 'score': c_score, 'op_rate': round(c_op/len(c_rows)*100, 1) if c_rows else 0,
        'ns_target': c_ns_t, 'no_target': c_no_t, 'nop_target': c_nop_t,
        'ns_op': c_ns_op, 'no_op': c_no_op, 'nop_op': c_nop_op,
        'ns_score': c_ns_op*6, 'no_score': c_no_op*4, 'nop_score': c_nop_op*3,
        'hv_count': c_hv, 'hv_bonus': c_hv*2, 'assigned': c_assigned,
    }

# ===== PRINT =====
print(f"\n===== REGIONAL ({NEW_DATE}) =====")
print(f"Target: {total_target}, Signed: {total_signed}, Operating: {total_operating}")
print(f"Total Score: {total_score_all}, BD-Level: {bd_level_score}")
print(f"NS: {ns_op}/{ns_t}, NO: {no_op}/{no_t}, NOP: {nop_op}/{nop_t}, HV: {hv_count_all}")

prev = json.load(open(PREV_FILE))
p = prev['regional_summary']
print(f"\nDOD vs {prev['data_date']}: op {total_operating-p['total_operating']:+d}, score {total_score_all-p['total_score']:+d}, ns_op {ns_op-p['ns_op']:+d}, no_op {no_op-p['no_op']:+d}, nop_op {nop_op-p['nop_op']:+d}, signed {total_signed-p['total_signed']:+d}")

print("\n===== BDM RANKING =====")
for i, (bdm, d) in enumerate(sorted(bdm_data.items(), key=lambda x: -x[1]['avg']), 1):
    print(f"  {i}. {bdm} ({d['city']}): score={d['team_score']}, avg={d['avg']}, qualified={d['qualified']}")

print("\n===== WS BD TOP15 =====")
for i, b in enumerate(ws_bds[:16], 1):
    print(f"  {i}. {b['bd']} ({b['bdm']}, {b['city']}): NS={b['not_signed']} NO={b['not_online']} NOP={b['not_operating']} HV={b['hv_count']}(+{b['hv_bonus']}) Total={b['total']}")

print("\n===== SANTOS BD =====")
for i, b in enumerate(santos_bds, 1):
    print(f"  {i}. {b['bd']} ({b['bdm']}): Total={b['total']}")

q = [b for b in ws_bds+santos_bds if b['total'] >= 15]
print(f"\nQualified BDs: {len(q)}/71 | Qualified BDMs: {sum(1 for d in bdm_data.values() if d['qualified'])}/12")

# ===== SAVE =====
output = {
    'data_date': NEW_DATE, 'operating_period': NEW_PERIOD,
    'previous': {'date': prev['data_date'], 'total_operating': p['total_operating'], 'total_score': p['total_score'],
                 'bd_level_score': p.get('bd_level_score', p['total_score']), 'ns_op': p['ns_op'], 'no_op': p['no_op'], 'nop_op': p['nop_op'],
                 'signed': p['total_signed'], 'cities': prev['city_summary']},
    'regional_summary': {
        'total_target': total_target, 'total_signed': total_signed, 'total_operating': total_operating,
        'total_score': total_score_all, 'bd_level_score': bd_level_score,
        'ns_target': ns_t, 'no_target': no_t, 'nop_target': nop_t,
        'ns_op': ns_op, 'no_op': no_op, 'nop_op': nop_op,
        'ns_score': ns_op*6, 'no_score': no_op*4, 'nop_score': nop_op*3,
        'hv_count': hv_count_all, 'hv_bonus': hv_count_all*2,
    },
    'city_summary': city_data, 'bdm_summary': bdm_data,
    'ws_bds': ws_bds, 'santos_bds': santos_bds,
    'bd_scores_detail': {bd: {'leads': sc['leads'], 'not_signed': sc['not_signed'], 'not_online': sc['not_online'],
                              'not_operating': sc['not_operating'], 'hv_bonus': sc['hv_bonus'], 'hv_count': sc['hv_count'],
                              'total': sc['total']} for bd, sc in bd_scores.items()},
}
json.dump(output, open(OUT_FILE, 'w'), indent=2, default=str, ensure_ascii=False)
print(f"\nSaved {OUT_FILE}")
