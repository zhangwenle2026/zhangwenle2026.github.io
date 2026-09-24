import openpyxl
import json
from collections import Counter, defaultdict

dir_map_inv = {
    'not_signed': 'not sign',
    'not_online': 'not online',
    'not_operating': 'not operating',
}

wb = openpyxl.load_workbook('redtop2000merchantsstatus-0817.xlsx', data_only=True)
ws = wb['Sheet1']
headers = [ws.cell(1, c).value for c in range(1, ws.max_column+1)]
cols = {h: i+1 for i, h in enumerate(headers) if h}

# region col = 8, city col = 9
# Metro = region == 'Metropolitan Region'
# Cities within Metro: Southern São Paulo Metropolitan, Western São Paulo Metropolitan, Santos City

metro_cities = {'Southern São Paulo Metropolitan', 'Western São Paulo Metropolitan', 'Santos City'}

rows = []
for r in range(2, ws.max_row+1):
    region = ws.cell(r, cols['region']).value
    city = ws.cell(r, cols['city']).value
    if region == 'Metropolitan Region' and city in metro_cities:
        rows.append({
            'lead_id': ws.cell(r, cols['Lead ID']).value,
            'lead_name': ws.cell(r, cols['Lead Name']).value,
            'store_id': ws.cell(r, cols['Store ID']).value,
            'aor_name': ws.cell(r, cols['AOR Name']).value,
            'leads_type': ws.cell(r, cols['leads type']).value,
            'red_comment': ws.cell(r, cols['red comment']).value,
            'red_order': ws.cell(r, cols['red order']).value,
            'region': region,
            'city': city,
            'district': ws.cell(r, cols['district']).value,
            'target_type': ws.cell(r, cols['target type-删除offline，删除近30日签约']).value,
            'bd': ws.cell(r, cols['BD']).value,
            'bdm': ws.cell(r, cols['BDM']).value,
            'sign': ws.cell(r, cols['sign-0817']).value,
            'merchant_status': ws.cell(r, cols['merchent status -0817']).value,
            'operating': ws.cell(r, cols['0811-0817 operating']).value,
        })

print(f"Total Metro rows: {len(rows)}")
print(f"By city: {Counter(r['city'] for r in rows)}")
print(f"Target type: {Counter(r['target_type'] for r in rows)}")
print(f"Sign: {Counter(r['sign'] for r in rows)}")
print(f"Merchant status: {Counter(r['merchant_status'] for r in rows)}")
print(f"Operating (0811-0817): {Counter(r['operating'] for r in rows)}")

print("\n--- Cross tab: target_type x sign x status x op ---")
crosstab = Counter()
for r in rows:
    key = (r['target_type'], r['sign'], r['merchant_status'], r['operating'])
    crosstab[key] += 1
for k, v in sorted(crosstab.items(), key=lambda x: -x[1]):
    print(f"  target={k[0]}, sign={k[1]}, status={k[2]}, op={k[3]}: {v}")

bds = set(r['bd'] for r in rows if r['bd'])
bdms = set(r['bdm'] for r in rows if r['bdm'])
print(f"\nUnique BDs: {len(bds)}")
print(f"Unique BDMs: {len(bdms)}")
print("BDMs:", sorted(bdms))

# Scoring
dir_map = {
    'not sign': ('not_signed', 6),
    'not online': ('not_online', 4),
    'not operating': ('not_operating', 3),
}

bd_scores = defaultdict(lambda: {'not_signed': 0, 'not_online': 0, 'not_operating': 0, 'hv_bonus': 0, 'total': 0, 'leads': []})

for r in rows:
    bd = r['bd']
    if not bd:
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
        'bdm': r['bdm'],
        'city': r['city'],
    })

# BD->BDM mapping
bd_to_bdm = {}
bd_to_city = {}
for r in rows:
    if r['bd'] and r['bdm']:
        bd_to_bdm[r['bd']] = r['bdm']
        bd_to_city[r['bd']] = r['city']

bdm_bd_count = defaultdict(set)
for r in rows:
    if r['bd'] and r['bdm']:
        bdm_bd_count[r['bdm']].add(r['bd'])

print("\n=== BD Scores (top 20) ===")
sorted_bds = sorted(bd_scores.items(), key=lambda x: -x[1]['total'])
for bd, sc in sorted_bds[:20]:
    bdm = bd_to_bdm.get(bd, '?')
    city = bd_to_city.get(bd, '?')
    print(f"  {bd} (BDM={bdm}, city={city}): NS={sc['not_signed']}, NO={sc['not_online']}, NOP={sc['not_operating']}, HV={sc['hv_bonus']}, Total={sc['total']}, leads={len(sc['leads'])}")

print(f"\nTotal BDs with scores: {len(bd_scores)}")
print(f"Total BDs with score >= 15: {sum(1 for bd, sc in bd_scores.items() if sc['total'] >= 15)}")

print("\n=== BDM Scores ===")
for bdm, bds_set in sorted(bdm_bd_count.items(), key=lambda x: -sum(bd_scores[bd]['total'] for bd in x[1] if bd in bd_scores)):
    bds_list = list(bds_set)
    team_score = sum(bd_scores[bd]['total'] for bd in bds_list if bd in bd_scores)
    bd_count = len(bds_list)
    avg = team_score / bd_count if bd_count > 0 else 0
    city = bd_to_city.get(next(iter(bds_list)), '?') if bds_list else '?'
    status = "✅" if avg >= 15 else "⚠️" if avg >= 10 else "❌"
    print(f"  {bdm} (city={city}): BDs={bd_count}, TeamScore={team_score}, Avg={avg:.2f} {status}")

# Regional summary
total_target = len(rows)
total_assigned = sum(1 for r in rows if r['bd'])
total_operating = sum(1 for r in rows if r['operating'] == 1)
total_score = sum(sc['total'] for sc in bd_scores.values())

print(f"\n=== Regional Summary ===")
print(f"Target Merchants: {total_target}")
print(f"Assigned to BD: {total_assigned}")
print(f"Operating (0811-0817): {total_operating}")
print(f"Total Score: {total_score}")

# By direction (operating only)
for tt_name, direction in [('not sign', 'not_signed'), ('not online', 'not_online'), ('not operating', 'not_operating')]:
    count = sum(1 for r in rows if r['target_type'] == tt_name and r['operating'] == 1)
    print(f"  {direction}: {count} operating")

# By city
print("\n=== City Summary ===")
for city in sorted(metro_cities):
    city_rows = [r for r in rows if r['city'] == city]
    city_target = len(city_rows)
    city_assigned = sum(1 for r in city_rows if r['bd'])
    city_operating = sum(1 for r in city_rows if r['operating'] == 1)
    city_score = sum(bd_scores[r['bd']]['total'] for r in city_rows if r['bd'] and r['bd'] in bd_scores and r['operating'] == 1)
    print(f"  {city}: target={city_target}, assigned={city_assigned}, operating={city_operating}, score={city_score}")

# Save full data to JSON
output = {
    'data_date': '0817',
    'operating_period': '0811-0817',
    'regional_summary': {
        'total_target': total_target,
        'total_assigned': total_assigned,
        'total_operating': total_operating,
        'total_score': total_score,
    },
    'bd_scores': {bd: sc for bd, sc in bd_scores.items()},
    'bdm_summary': {},
    'city_summary': {},
}

for bdm, bds_set in bdm_bd_count.items():
    bds_list = list(bds_set)
    team_score = sum(bd_scores[bd]['total'] for bd in bds_list if bd in bd_scores)
    bd_count = len(bds_list)
    avg = team_score / bd_count if bd_count > 0 else 0
    city = bd_to_city.get(next(iter(bds_list)), '?') if bds_list else '?'
    output['bdm_summary'][bdm] = {
        'city': city,
        'bd_count': bd_count,
        'team_score': team_score,
        'avg': round(avg, 2),
    }

for city in sorted(metro_cities):
    city_rows = [r for r in rows if r['city'] == city]
    output['city_summary'][city] = {
        'target': len(city_rows),
        'assigned': sum(1 for r in city_rows if r['bd']),
        'operating': sum(1 for r in city_rows if r['operating'] == 1),
        'score': sum(bd_scores[r['bd']]['total'] for r in city_rows if r['bd'] and r['bd'] in bd_scores and r['operating'] == 1),
    }

with open('order_penetration_data_0817.json', 'w') as f:
    json.dump(output, f, indent=2, default=str)
print("\nSaved to order_penetration_data_0817.json")
