import openpyxl
import json
from collections import Counter, defaultdict

wb = openpyxl.load_workbook('redtop2000merchantsstatus-0817.xlsx', data_only=True)
ws = wb['Sheet1']
headers = [ws.cell(1, c).value for c in range(1, ws.max_column+1)]
cols = {h: i+1 for i, h in enumerate(headers) if h}

metro_cities = {'Southern São Paulo Metropolitan', 'Western São Paulo Metropolitan', 'Santos City'}

# Fixed BD roster from ORDER_PENETRATION_DASHBOARD_STANDARD.md
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

# Flatten roster
all_roster_bds = set()
all_roster_bdms = set()
for city, bdm_map in ROSTER.items():
    for bdm, bd_list in bdm_map.items():
        all_roster_bdms.add(bdm)
        for bd in bd_list:
            all_roster_bds.add(bd)

# Collect rows
rows = []
for r in range(2, ws.max_row+1):
    region = ws.cell(r, cols['region']).value
    city = ws.cell(r, cols['city']).value
    if region == 'Metropolitan Region' and city in metro_cities:
        rows.append({
            'lead_id': ws.cell(r, cols['Lead ID']).value,
            'lead_name': ws.cell(r, cols['Lead Name']).value,
            'red_order': ws.cell(r, cols['red order']).value,
            'region': region,
            'city': city,
            'target_type': ws.cell(r, cols['target type-删除offline，删除近30日签约']).value,
            'bd': ws.cell(r, cols['BD']).value,
            'bdm': ws.cell(r, cols['BDM']).value,
            'sign': ws.cell(r, cols['sign-0817']).value,
            'merchant_status': ws.cell(r, cols['merchent status -0817']).value,
            'operating': ws.cell(r, cols['0811-0817 operating']).value,
        })

# Only count rows where BD is in roster
rows_filtered = [r for r in rows if r['bd'] in all_roster_bds]

print(f"Total Metro rows: {len(rows)}")
print(f"Rows with roster BDs: {len(rows_filtered)}")
print(f"Rows without roster BDs: {len(rows) - len(rows_filtered)}")

# Also check non-roster BDs
non_roster_bds = set(r['bd'] for r in rows if r['bd'] and r['bd'] not in all_roster_bds)
print(f"Non-roster BDs: {sorted(non_roster_bds)}")

# Scoring
dir_map = {
    'not sign': ('not_signed', 6),
    'not online': ('not_online', 4),
    'not operating': ('not_operating', 3),
}

bd_scores = defaultdict(lambda: {'not_signed': 0, 'not_online': 0, 'not_operating': 0, 'hv_bonus': 0, 'total': 0, 'leads': []})

for r in rows_filtered:
    bd = r['bd']
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

# BD city and BDM from roster
bd_to_bdm = {}
bd_to_city = {}
for city, bdm_map in ROSTER.items():
    city_short = city.split(' São Paulo')[0] if 'São Paulo' in city else city.replace(' City','')
    for bdm, bd_list in bdm_map.items():
        for bd in bd_list:
            bd_to_bdm[bd] = bdm
            bd_to_city[bd] = city_short

# Regional summary (roster only)
total_target = len(rows_filtered)
total_assigned = len(rows_filtered)  # all have BD assigned
total_operating = sum(1 for r in rows_filtered if r['operating'] == 1)
total_signed = sum(1 for r in rows_filtered if r['sign'] == 1)
total_score = sum(sc['total'] for sc in bd_scores.values())

print(f"\n=== Regional Summary (Roster Only) ===")
print(f"Target Merchants: {total_target}")
print(f"Signed: {total_signed} ({total_signed/total_target*100:.1f}%)")
print(f"Operating: {total_operating} ({total_operating/total_target*100:.1f}%)")
print(f"Total Score: {total_score}")

# Direction breakdown
ns_op = sum(1 for r in rows_filtered if r['target_type'] == 'not sign' and r['operating'] == 1)
no_op = sum(1 for r in rows_filtered if r['target_type'] == 'not online' and r['operating'] == 1)
nop_op = sum(1 for r in rows_filtered if r['target_type'] == 'not operating' and r['operating'] == 1)
ns_score = ns_op * 6
no_score = no_op * 4
nop_score = nop_op * 3
hv_total = total_score - ns_score - no_score - nop_score
hv_count = hv_total // 2

print(f"\nDirection breakdown:")
print(f"  NS: {ns_op} operating, score={ns_score}")
print(f"  NO: {no_op} operating, score={no_score}")
print(f"  NOP: {nop_op} operating, score={nop_score}")
print(f"  HV: {hv_count} merchants, +{hv_total} pts")
print(f"  Verify: {ns_score + no_score + nop_score + hv_total} == {total_score}")

# City breakdown
print(f"\n=== City Summary ===")
city_data = {}
for city_full in ['Southern São Paulo Metropolitan', 'Western São Paulo Metropolitan', 'Santos City']:
    city_short = city_full.split(' São Paulo')[0] if 'São Paulo' in city_full else city_full.replace(' City','')
    city_rows = [r for r in rows_filtered if r['city'] == city_full]
    c_target = len(city_rows)
    c_signed = sum(1 for r in city_rows if r['sign'] == 1)
    c_op = sum(1 for r in city_rows if r['operating'] == 1)
    c_score = sum(bd_scores[r['bd']]['total'] for r in city_rows if r['bd'] in bd_scores and r['operating'] == 1)
    
    # Direction breakdown
    c_ns = sum(1 for r in city_rows if r['target_type'] == 'not sign' and r['operating'] == 1)
    c_no = sum(1 for r in city_rows if r['target_type'] == 'not online' and r['operating'] == 1)
    c_nop = sum(1 for r in city_rows if r['target_type'] == 'not operating' and r['operating'] == 1)
    c_ns_target = sum(1 for r in city_rows if r['target_type'] == 'not sign')
    c_no_target = sum(1 for r in city_rows if r['target_type'] == 'not online')
    c_nop_target = sum(1 for r in city_rows if r['target_type'] == 'not operating')
    c_ns_score = c_ns * 6
    c_no_score = c_no * 4
    c_nop_score = c_nop * 3
    c_hv = c_score - c_ns_score - c_no_score - c_nop_score
    
    city_data[city_short] = {
        'target': c_target, 'signed': c_signed, 'operating': c_op, 'score': c_score,
        'ns_op': c_ns, 'no_op': c_no, 'nop_op': c_nop,
        'ns_target': c_ns_target, 'no_target': c_no_target, 'nop_target': c_nop_target,
        'ns_score': c_ns_score, 'no_score': c_no_score, 'nop_score': c_nop_score,
        'hv_bonus': c_hv, 'op_rate': round(c_op/c_target*100, 1) if c_target else 0,
    }
    print(f"  {city_short}: target={c_target}, signed={c_signed} ({c_signed/c_target*100:.1f}%), op={c_op} ({c_op/c_target*100:.1f}%), score={c_score}")
    print(f"    NS: target={c_ns_target}, op={c_ns}, score={c_ns_score}")
    print(f"    NO: target={c_no_target}, op={c_no}, score={c_no_score}")
    print(f"    NOP: target={c_nop_target}, op={c_nop}, score={c_nop_score}")
    print(f"    HV bonus: {c_hv}")

# BDM scores
print(f"\n=== BDM Scores ===")
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

# BD scores sorted
print(f"\n=== BD Scores (all roster BDs, sorted) ===")
ws_bds = []
santos_bds = []
for bd in sorted(all_roster_bds):
    if bd not in bd_scores:
        # BD with 0 score
        sc = {'not_signed': 0, 'not_online': 0, 'not_operating': 0, 'hv_bonus': 0, 'total': 0, 'leads': []}
    else:
        sc = bd_scores[bd]
    city = bd_to_city.get(bd, '?')
    bdm = bd_to_bdm.get(bd, '?')
    entry = {'bd': bd, 'bdm': bdm, 'city': city, **sc}
    if city == 'Santos':
        santos_bds.append(entry)
    else:
        ws_bds.append(entry)

ws_bds.sort(key=lambda x: -x['total'])
santos_bds.sort(key=lambda x: -x['total'])

print("\n--- WS Combined (63 BDs) ---")
for i, bd in enumerate(ws_bds):
    status = "✅" if bd['total'] >= 15 else ""
    print(f"  {i+1}. {bd['bd']} (BDM={bd['bdm']}, city={bd['city']}): NS={bd['not_signed']}, NO={bd['not_online']}, NOP={bd['not_operating']}, HV={bd['hv_bonus']}, Total={bd['total']} {status}")

print("\n--- Santos (8 BDs) ---")
for i, bd in enumerate(santos_bds):
    status = "✅" if bd['total'] >= 15 else ""
    print(f"  {i+1}. {bd['bd']} (BDM={bd['bdm']}): NS={bd['not_signed']}, NO={bd['not_online']}, NOP={bd['not_operating']}, HV={bd['hv_bonus']}, Total={bd['total']} {status}")

# BDs with score >= 15
qualified_bds = [bd for bd in ws_bds + santos_bds if bd['total'] >= 15]
print(f"\nQualified BDs (≥15): {len(qualified_bds)}")
qualified_bdms = [bdm for bdm, d in bdm_data.items() if d['qualified']]
print(f"Qualified BDMs (avg≥15): {len(qualified_bdms)}")

# Save complete data
output = {
    'data_date': '0817',
    'operating_period': '0811-0817',
    'regional_summary': {
        'total_target': total_target,
        'total_signed': total_signed,
        'total_operating': total_operating,
        'total_score': total_score,
        'ns_op': ns_op, 'no_op': no_op, 'nop_op': nop_op,
        'ns_score': ns_score, 'no_score': no_score, 'nop_score': nop_score,
        'hv_count': hv_count, 'hv_bonus': hv_total,
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
