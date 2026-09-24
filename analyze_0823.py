import openpyxl
import json
from collections import Counter, defaultdict

wb = openpyxl.load_workbook('redtop2000merchantsstatus-0823.xlsx', data_only=True)
ws = wb['Sheet1']
headers = [ws.cell(1, c).value for c in range(1, ws.max_column+1)]
cols = {h: i+1 for i, h in enumerate(headers) if h}

# Print column headers to verify
print("Column headers:")
for i, h in enumerate(headers):
    print(f"  Col {i+1}: {h}")

metro_cities = {'Southern São Paulo Metropolitan', 'Western São Paulo Metropolitan', 'Santos City'}

# UPDATED ROSTER: cristianedasilva moved from eduardoalbuquerque to fernandooliveira
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

# Collect ALL metro rows and roster rows
all_rows = []
for r in range(2, ws.max_row+1):
    region = ws.cell(r, cols['region']).value
    city = ws.cell(r, cols['city']).value
    if region == 'Metropolitan Region' and city in metro_cities:
        row = {
            'lead_name': ws.cell(r, cols['Lead Name']).value,
            'red_order': ws.cell(r, cols['red order']).value,
            'city': city,
            'target_type': ws.cell(r, cols['target type']).value,
            'bd': ws.cell(r, cols['BD']).value,
            'bdm': ws.cell(r, cols['BDM']).value,
            'sign': ws.cell(r, cols['sign-0823']).value,
            'operating': ws.cell(r, cols['0817-0823 operating']).value,
        }
        all_rows.append(row)

dir_map = {
    'not sign': ('not_signed', 6),
    'not online': ('not_online', 4),
    'not operating': ('not_operating', 3),
}

# ===== BD-LEVEL SCORES (roster BDs only) =====
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

# ===== BDM SCORES =====
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

# ===== BD LISTS =====
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

# ===== PRINT RESULTS =====
print("\n===== CRISTIANEDASILVA SCORE DETAIL =====")
cs = bd_scores.get('cristianedasilva', {})
print(f"  BDM: {bd_to_bdm['cristianedasilva']}")
print(f"  City: {bd_to_city['cristianedasilva']}")
print(f"  Not Signed: {cs.get('not_signed', 0)}")
print(f"  Not Online: {cs.get('not_online', 0)}")
print(f"  Not Operating: {cs.get('not_operating', 0)}")
print(f"  HV Bonus: {cs.get('hv_bonus', 0)}")
print(f"  Total: {cs.get('total', 0)}")
print(f"  Leads: {json.dumps(cs.get('leads', []), indent=2, ensure_ascii=False)}")

print("\n===== UPDATED BDM SCORES (12 BDMs, sorted by avg) =====")
for i, (bdm, d) in enumerate(sorted(bdm_data.items(), key=lambda x: -x[1]['avg']), 1):
    status = "✅" if d['qualified'] else "⚠️" if d['avg'] >= 10 else "❌"
    print(f"  {i}. {bdm} (city={d['city']}): BDs={d['bd_count']}, TeamScore={d['team_score']}, Avg={d['avg']} {status}")

print("\n===== EDUARDOALBUQUERQUE DETAIL =====")
ea = bdm_data['eduardoalbuquerque']
print(f"  BDs: {ea['bd_count']}, TeamScore: {ea['team_score']}, Avg: {ea['avg']}")
ea_bds = [bd for bd in ROSTER['Southern São Paulo Metropolitan']['eduardoalbuquerque']]
for bd in ea_bds:
    sc = bd_scores.get(bd, {})
    print(f"    {bd}: total={sc.get('total', 0)}")

print("\n===== FERNANDOOLIVEIRA DETAIL =====")
fo = bdm_data['fernandooliveira']
print(f"  BDs: {fo['bd_count']}, TeamScore: {fo['team_score']}, Avg: {fo['avg']}")
fo_bds = [bd for bd in ROSTER['Southern São Paulo Metropolitan']['fernandooliveira']]
for bd in fo_bds:
    sc = bd_scores.get(bd, {})
    print(f"    {bd}: total={sc.get('total', 0)}")

print(f"\n===== WS BDS (TOP 20) =====")
for i, bd in enumerate(ws_bds[:20], 1):
    status = "✅" if bd['total'] >= 15 else f"还差 {15 - bd['total']} 分"
    print(f"  {i}. {bd['bd']} (BDM={bd['bdm']}, City={bd['city']}): NS={bd['not_signed']}, NO={bd['not_online']}, NOP={bd['not_operating']}, HV={bd['hv_bonus']}, Total={bd['total']} [{status}]")

print(f"\n===== SANTOS BDS =====")
for i, bd in enumerate(santos_bds, 1):
    status = "✅" if bd['total'] >= 15 else f"还差 {15 - bd['total']} 分"
    print(f"  {i}. {bd['bd']} (BDM={bd['bdm']}): Total={bd['total']} [{status}]")

qualified_bds = [bd for bd in ws_bds + santos_bds if bd['total'] >= 15]
print(f"\nQualified BDs (≥15): {len(qualified_bds)}")

# ===== ALSO COMPUTE REGIONAL/CITY OVERVIEW =====
total_target = len(all_rows)
total_signed = sum(1 for r in all_rows if r['sign'] == 1)
total_operating = sum(1 for r in all_rows if r['operating'] == 1)

ns_target_all = sum(1 for r in all_rows if r['target_type'] == 'not sign')
no_target_all = sum(1 for r in all_rows if r['target_type'] == 'not online')
nop_target_all = sum(1 for r in all_rows if r['target_type'] == 'not operating')

ns_op_all = sum(1 for r in all_rows if r['target_type'] == 'not sign' and r['operating'] == 1)
no_op_all = sum(1 for r in all_rows if r['target_type'] == 'not online' and r['operating'] == 1)
nop_op_all = sum(1 for r in all_rows if r['target_type'] == 'not operating' and r['operating'] == 1)

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

bd_level_score = sum(sc['total'] for sc in bd_scores.values())

print(f"\n===== REGIONAL OVERVIEW =====")
print(f"Target: {total_target}, Signed: {total_signed}, Operating: {total_operating}")
print(f"Total Score: {total_score_all}, BD-Level Score: {bd_level_score}")
print(f"NS: target={ns_target_all}, op={ns_op_all}, score={ns_score_all}")
print(f"NO: target={no_target_all}, op={no_op_all}, score={no_score_all}")
print(f"NOP: target={nop_target_all}, op={nop_op_all}, score={nop_score_all}")
print(f"HV: {hv_count_all} merchants, +{hv_bonus_all}")

# City overview
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
    
    # assigned = roster BDs in this city
    c_assigned = sum(1 for r in c_rows if r['bd'] in all_roster_bds)
    
    city_data[city_short] = {
        'target': c_target, 'signed': c_signed, 'operating': c_op, 'score': c_score,
        'op_rate': round(c_op/c_target*100, 1) if c_target else 0,
        'ns_target': c_ns_target, 'no_target': c_no_target, 'nop_target': c_nop_target,
        'ns_op': c_ns_op, 'no_op': c_no_op, 'nop_op': c_nop_op,
        'ns_score': c_ns_score, 'no_score': c_no_score, 'nop_score': c_nop_score,
        'hv_count': c_hv, 'hv_bonus': c_hv_bonus,
        'assigned': c_assigned,
    }
    print(f"\n  {city_short}: target={c_target}, signed={c_signed}, op={c_op}, score={c_score}, assigned={c_assigned}")

# Previous data (0819)
with open('order_penetration_data_0820_final.json', 'r') as f:
    prev_data = json.load(f)

# Build output JSON
output = {
    'data_date': '0823',
    'operating_period': '0817-0823',
    'previous': {
        'date': '0820',
        'total_operating': prev_data['regional_summary']['total_operating'],
        'total_score': prev_data['regional_summary']['total_score'],
        'bd_level_score': prev_data['regional_summary']['bd_level_score'],
        'ns_op': prev_data['regional_summary']['ns_op'],
        'no_op': prev_data['regional_summary']['no_op'],
        'nop_op': prev_data['regional_summary']['nop_op'],
        'signed': prev_data['regional_summary']['total_signed'],
        'cities': prev_data['city_summary'],
    },
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

with open('order_penetration_data_0823_final.json', 'w') as f:
    json.dump(output, f, indent=2, default=str)
print("\nSaved to order_penetration_data_0823_final.json")
