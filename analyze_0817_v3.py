import openpyxl
import json
from collections import Counter, defaultdict

wb = openpyxl.load_workbook('redtop2000merchantsstatus-0817.xlsx', data_only=True)
ws = wb['Sheet1']
headers = [ws.cell(1, c).value for c in range(1, ws.max_column+1)]
cols = {h: i+1 for i, h in enumerate(headers) if h}

metro_cities = {'Southern São Paulo Metropolitan', 'Western São Paulo Metropolitan', 'Santos City'}

ROSTER = {
    'Southern São Paulo Metropolitan': {
        'adriananaves': ['brunacrelien', 'elisangelasouza', 'evaldosilva', 'ivanfelizardo', 'josenascimento', 'murilosilva', 'rodrigoalmeida', 'tiagodangelo', 'wanessasilva'],
        'fernandooliveira': ['brunapadilha', 'carlosmotta', 'erikboilesen', 'felipesanches', 'pedrosaccone', 'wainnergonzales', 'wellingtonsantos'],
        'eduardoalbuquerque': ['allanmaalouli', 'cristianedasilva', 'felipesilva', 'fernandoquintiliano', 'joycepurificacao', 'otaviomazzega', 'thaisvasconcelos'],
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

# Collect ALL metro rows (for regional/city overview) and roster rows (for BD rankings)
all_rows = []
for r in range(2, ws.max_row+1):
    region = ws.cell(r, cols['region']).value
    city = ws.cell(r, cols['city']).value
    if region == 'Metropolitan Region' and city in metro_cities:
        row = {
            'lead_name': ws.cell(r, cols['Lead Name']).value,
            'red_order': ws.cell(r, cols['red order']).value,
            'city': city,
            'target_type': ws.cell(r, cols['target type-删除offline，删除近30日签约']).value,
            'bd': ws.cell(r, cols['BD']).value,
            'bdm': ws.cell(r, cols['BDM']).value,
            'sign': ws.cell(r, cols['sign-0817']).value,
            'operating': ws.cell(r, cols['0811-0817 operating']).value,
        }
        all_rows.append(row)

# ===== REGIONAL OVERVIEW (ALL 818 merchants) =====
total_target = len(all_rows)
total_signed = sum(1 for r in all_rows if r['sign'] == 1)
total_operating = sum(1 for r in all_rows if r['operating'] == 1)

# Direction targets (all)
ns_target_all = sum(1 for r in all_rows if r['target_type'] == 'not sign')
no_target_all = sum(1 for r in all_rows if r['target_type'] == 'not online')
nop_target_all = sum(1 for r in all_rows if r['target_type'] == 'not operating')

# Direction operating (all)
ns_op_all = sum(1 for r in all_rows if r['target_type'] == 'not sign' and r['operating'] == 1)
no_op_all = sum(1 for r in all_rows if r['target_type'] == 'not online' and r['operating'] == 1)
nop_op_all = sum(1 for r in all_rows if r['target_type'] == 'not operating' and r['operating'] == 1)

# Score (all operating merchants, using roster BDs only for BD-level score)
# For total score, count ALL operating merchants regardless of BD
dir_map = {
    'not sign': ('not_signed', 6),
    'not online': ('not_online', 4),
    'not operating': ('not_operating', 3),
}

# Total score includes ALL operating merchants
total_score_all = 0
hv_count_all = 0
for r in all_rows:
    if r['target_type'] not in dir_map:
        continue
    if r['operating'] != 1:
        continue
    direction, base = dir_map[r['target_type']]
    hv = 1 if (r['red_order'] and r['red_order'] >= 20) else 0
    total_score_all += base + (2 if hv else 0)
    if hv:
        hv_count_all += 1

ns_score_all = ns_op_all * 6
no_score_all = no_op_all * 4
nop_score_all = nop_op_all * 3
hv_bonus_all = hv_count_all * 2

# BD-level score (roster BDs only)
bd_scores = defaultdict(lambda: {'not_signed': 0, 'not_online': 0, 'not_operating': 0, 'hv_bonus': 0, 'total': 0, 'leads': []})
for r in all_rows:
    bd = r['bd']
    if bd not in all_roster_bds:
        continue
    tt = r['target_type']
    if tt not in dir_map:
        continue
    direction, base = dir_map[tt]
    if r['operating'] != 1:
        continue
    hv = 1 if (r['red_order'] and r['red_order'] >= 20) else 0
    score = base + (2 if hv else 0)
    bd_scores[bd][direction] += 1
    bd_scores[bd]['hv_bonus'] += (2 if hv else 0)
    bd_scores[bd]['total'] += score
    bd_scores[bd]['leads'].append({
        'name': r['lead_name'],
        'direction': direction,
        'base': base,
        'hv': hv,
        'score': score,
    })

bd_level_score = sum(sc['total'] for sc in bd_scores.values())

print("===== REGIONAL OVERVIEW (ALL 818) =====")
print(f"Target: {total_target}")
print(f"Signed: {total_signed} ({total_signed/total_target*100:.1f}%)")
print(f"Operating: {total_operating} ({total_operating/total_target*100:.1f}%)")
print(f"Total Score: {total_score_all}")
print(f"BD-Level Score: {bd_level_score}")
print(f"NS: target={ns_target_all}, op={ns_op_all}, score={ns_score_all}")
print(f"NO: target={no_target_all}, op={no_op_all}, score={no_score_all}")
print(f"NOP: target={nop_target_all}, op={nop_op_all}, score={nop_score_all}")
print(f"HV: {hv_count_all} merchants, +{hv_bonus_all} pts")
print(f"Verify: {ns_score_all + no_score_all + nop_score_all + hv_bonus_all} == {total_score_all}")

# ===== CITY OVERVIEW (ALL) =====
print("\n===== CITY OVERVIEW =====")
city_data = {}
for city_full in ['Southern São Paulo Metropolitan', 'Western São Paulo Metropolitan', 'Santos City']:
    city_short = city_full.split(' São Paulo')[0] if 'São Paulo' in city_full else city_full.replace(' City','')
    c_rows = [r for r in all_rows if r['city'] == city_full]
    c_target = len(c_rows)
    c_signed = sum(1 for r in c_rows if r['sign'] == 1)
    c_op = sum(1 for r in c_rows if r['operating'] == 1)
    c_ns_target = sum(1 for r in c_rows if r['target_type'] == 'not sign')
    c_no_target = sum(1 for r in c_rows if r['target_type'] == 'not online')
    c_nop_target = sum(1 for r in c_rows if r['target_type'] == 'not operating')
    c_ns_op = sum(1 for r in c_rows if r['target_type'] == 'not sign' and r['operating'] == 1)
    c_no_op = sum(1 for r in c_rows if r['target_type'] == 'not online' and r['operating'] == 1)
    c_nop_op = sum(1 for r in c_rows if r['target_type'] == 'not operating' and r['operating'] == 1)
    c_ns_score = c_ns_op * 6
    c_no_score = c_no_op * 4
    c_nop_score = c_nop_op * 3
    c_hv = sum(1 for r in c_rows if r['operating'] == 1 and r['red_order'] and r['red_order'] >= 20)
    c_hv_bonus = c_hv * 2
    c_score = c_ns_score + c_no_score + c_nop_score + c_hv_bonus
    city_data[city_short] = {
        'target': c_target, 'signed': c_signed, 'operating': c_op, 'score': c_score,
        'op_rate': round(c_op/c_target*100, 1) if c_target else 0,
        'ns_target': c_ns_target, 'no_target': c_no_target, 'nop_target': c_nop_target,
        'ns_op': c_ns_op, 'no_op': c_no_op, 'nop_op': c_nop_op,
        'ns_score': c_ns_score, 'no_score': c_no_score, 'nop_score': c_nop_score,
        'hv_count': c_hv, 'hv_bonus': c_hv_bonus,
    }
    print(f"  {city_short}: target={c_target}, signed={c_signed} ({c_signed/c_target*100:.1f}%), op={c_op} ({c_op/c_target*100:.1f}%), score={c_score}")
    print(f"    NS: target={c_ns_target}, op={c_ns_op}, score={c_ns_score}")
    print(f"    NO: target={c_no_target}, op={c_no_op}, score={c_no_score}")
    print(f"    NOP: target={c_nop_target}, op={c_nop_op}, score={c_nop_score}")
    print(f"    HV: {c_hv} merchants, +{c_hv_bonus}")

# ===== BDM SCORES =====
print("\n===== BDM SCORES =====")
bdm_data = {}
for city_full, bdm_map in ROSTER.items():
    city_short = city_full.split(' São Paulo')[0] if 'São Paulo' in city_full else city_full.replace(' City','')
    for bdm, bd_list in bdm_map.items():
        team_score = sum(bd_scores[bd]['total'] for bd in bd_list if bd in bd_scores)
        bd_count = len(bd_list)
        avg = team_score / bd_count if bd_count > 0 else 0
        bdm_data[bdm] = {
            'city': city_short,
            'bd_count': bd_count,
            'team_score': team_score,
            'avg': round(avg, 2),
            'qualified': avg >= 15,
        }

for bdm, d in sorted(bdm_data.items(), key=lambda x: -x[1]['avg']):
    status = "✅" if d['qualified'] else "⚠️" if d['avg'] >= 10 else "❌"
    print(f"  {bdm} (city={d['city']}): BDs={d['bd_count']}, TeamScore={d['team_score']}, Avg={d['avg']} {status}")

# ===== BD SCORES =====
ws_bds = []
santos_bds = []
for bd in all_roster_bds:
    sc = bd_scores.get(bd, {'not_signed': 0, 'not_online': 0, 'not_operating': 0, 'hv_bonus': 0, 'total': 0, 'leads': []})
    city = bd_to_city[bd]
    bdm = bd_to_bdm[bd]
    entry = {'bd': bd, 'bdm': bdm, 'city': city, **sc}
    if city == 'Santos':
        santos_bds.append(entry)
    else:
        ws_bds.append(entry)

ws_bds.sort(key=lambda x: -x['total'])
santos_bds.sort(key=lambda x: -x['total'])

print(f"\n===== WS BDs (top 10) =====")
for i, bd in enumerate(ws_bds[:10]):
    print(f"  {i+1}. {bd['bd']}: Total={bd['total']}, NS={bd['not_signed']}, NO={bd['not_online']}, NOP={bd['not_operating']}, HV={bd['hv_bonus']}")

print(f"\n===== Santos BDs =====")
for i, bd in enumerate(santos_bds):
    print(f"  {i+1}. {bd['bd']}: Total={bd['total']}")

qualified_bds = [bd for bd in ws_bds + santos_bds if bd['total'] >= 15]
print(f"\nQualified BDs (≥15): {len(qualified_bds)}")

# Previous data (0816 from HTML)
prev = {
    'date': '0816',
    'total_operating': 112,
    'total_score': 533,
    'bd_level_score': 486,
    'ns_op': 41, 'no_op': 14, 'nop_op': 57,
    'signed': 324,
    'cities': {
        'Southern': {'signed': 161, 'op': 47, 'score': 192, 'ns_op': 16, 'no_op': 3, 'nop_op': 28},
        'Western': {'signed': 138, 'op': 53, 'score': 230, 'ns_op': 21, 'no_op': 8, 'nop_op': 24},
        'Santos': {'signed': 25, 'op': 12, 'score': 51, 'ns_op': 4, 'no_op': 3, 'nop_op': 5},
    }
}

# Save complete output
output = {
    'data_date': '0817',
    'operating_period': '0811-0817',
    'previous': prev,
    'regional_summary': {
        'total_target': total_target,
        'total_signed': total_signed,
        'total_operating': total_operating,
        'total_score': total_score_all,
        'bd_level_score': bd_level_score,
        'ns_target': ns_target_all, 'no_target': no_target_all, 'nop_target': nop_target_all,
        'ns_op': ns_op_all, 'no_op': no_op_all, 'nop_op': nop_op_all,
        'ns_score': ns_score_all, 'no_score': no_score_all, 'nop_score': nop_score_all,
        'hv_count': hv_count_all, 'hv_bonus': hv_bonus_all,
    },
    'city_summary': city_data,
    'bdm_summary': bdm_data,
    'ws_bds': ws_bds,
    'santos_bds': santos_bds,
    'bd_scores_detail': {bd: {'leads': sc['leads'], 'not_signed': sc['not_signed'], 'not_online': sc['not_online'], 'not_operating': sc['not_operating'], 'hv_bonus': sc['hv_bonus'], 'total': sc['total']} for bd, sc in bd_scores.items()},
}

with open('order_penetration_data_0817_final.json', 'w') as f:
    json.dump(output, f, indent=2, default=str)
print("\nSaved to order_penetration_data_0817_final.json")
