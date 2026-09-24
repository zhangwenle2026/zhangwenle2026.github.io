# -*- coding: utf-8 -*-
"""0831 final: 基于analyze_0831.py输出 + 早鸟(43家铁证,按名字匹配) + marcia归adriana + adriana 8人口径"""
import openpyxl, json
from collections import defaultdict

# 1. Load raw 0831 output
D = json.load(open('order_penetration_data_0831_raw.json'))

# 2. Early bird names (43, from 0830 final; '__NULL__' = giovanabareno's unnamed lead, matched by BD+direction fallback)
eb_names = set(json.load(open('earlybird_0830_names.json')))

# 3. Recompute per-BD with early bird from 0831 xlsx (roster from analyze_0831.py)
src = open('analyze_0831.py').read()
start = src.index("ROSTER = {")
end = src.index("all_rows = []")
exec(compile(src[start:end], 'roster', 'exec'))

wb = openpyxl.load_workbook('redtop2000merchantsstatus-0831.xlsx', read_only=True, data_only=True)
ws = wb['Sheet1']
hdr = [str(c.value) if c.value else '' for c in next(ws.iter_rows(min_row=1, max_row=1))]
oph = '0825-0831 operating'
dir_map = {'not sign': ('not_signed', 6), 'not online': ('not_online', 4), 'not operating': ('not_operating', 3)}

bd_scores = defaultdict(lambda: {'not_signed': 0, 'not_online': 0, 'not_operating': 0, 'hv_bonus': 0, 'hv_count': 0, 'early': 0, 'total': 0, 'leads': []})
seen = set()
for row in ws.iter_rows(min_row=2, values_only=True):
    r = dict(zip(hdr, row))
    bd = r['BD']
    if bd not in all_roster_bds:
        continue
    tt = r.get('target type')
    if tt not in dir_map or r.get(oph) != 1:
        continue
    lid = str(r['Lead ID'])
    if lid in seen:
        continue
    seen.add(lid)
    direction, base = dir_map[tt]
    hv = 1 if (r['red order'] and r['red order'] >= 20) else 0
    nm = r['Lead Name']
    nm_key = '__NULL__' if nm is None or str(nm).strip() in ('','None') else str(nm)
    eb = 1 if nm_key in eb_names else 0
    score = base + (2 if hv else 0) + eb
    bd_scores[bd][direction] += 1
    bd_scores[bd]['hv_bonus'] += (2 if hv else 0)
    bd_scores[bd]['hv_count'] += hv
    bd_scores[bd]['early'] += eb
    bd_scores[bd]['total'] += score
    bd_scores[bd]['leads'].append({
        'name': nm, 'direction': direction, 'base': base,
        'hv': hv, 'early': eb, 'score': score,
    })

total_early = sum(s['early'] for s in bd_scores.values())
print(f'early bird applied: {total_early} leads')

# 4. BDM (standard roster, marcia still under alisaeed at this point)
bdm_data = {}
for city_full, bdm_map in ROSTER.items():
    city_short = city_full.split(' São Paulo')[0] if 'São Paulo' in city_full else city_full.replace(' City','')
    for bdm, bd_list in bdm_map.items():
        team_score = sum(bd_scores[bd]['total'] for bd in bd_list if bd in bd_scores)
        avg = team_score / len(bd_list)
        bdm_data[bdm] = {'city': city_short, 'bd_count': len(bd_list), 'team_score': team_score,
                         'avg': round(avg, 2), 'qualified': avg >= 15}

# 5. BD lists (marcia → adriananaves)
bd_to_bdm['marciajesuino'] = 'adriananaves'
ws_bds, santos_bds = [], []
for bd in all_roster_bds:
    sc = bd_scores.get(bd, {'not_signed': 0, 'not_online': 0, 'not_operating': 0, 'hv_bonus': 0, 'hv_count': 0, 'early': 0, 'total': 0, 'leads': []})
    entry = {'bd': bd, 'bdm': bd_to_bdm[bd], 'city': bd_to_city[bd], **sc}
    (santos_bds if bd_to_city[bd] == 'Santos' else ws_bds).append(entry)
ws_bds.sort(key=lambda x: -x['total'])
santos_bds.sort(key=lambda x: -x['total'])

# 6. BDM fix: adriana 8人口径 (team = full sum incl marcia & brunacrelien, count=8); alisaeed loses marcia
scores = {b['bd']: b['total'] for b in ws_bds + santos_bds}
adri_team = ['brunacrelien','elisangelasouza','evaldosilva','ivanfelizardo','josenascimento','murilosilva','rodrigoalmeida','tiagodangelo','wanessasilva','marciajesuino']
ts = sum(scores.get(bd, 0) for bd in adri_team)
bdm_data['adriananaves'] = {'city': 'Southern', 'bd_count': 8, 'team_score': ts, 'avg': round(ts/8, 2), 'qualified': ts/8 >= 15}
ali_team = ['camilabatista','davidcaramaschi','eduardosantos','ricardoaraujo','rodrigocorreia']
ts2 = sum(scores.get(bd, 0) for bd in ali_team)
bdm_data['alisaeed'] = {'city': 'Southern', 'bd_count': len(ali_team), 'team_score': ts2, 'avg': round(ts2/len(ali_team), 2), 'qualified': ts2/len(ali_team) >= 15}

# 7. Regional/city: add early bonus
R = D['regional_summary']
R['total_score'] += total_early
R['bd_level_score'] += total_early
R['early_count'] = total_early
R['early_bonus'] = total_early
for city, v in D['city_summary'].items():
    ce = sum(s['early'] for bd, s in bd_scores.items() if bd_to_city[bd] == city)
    v['score'] += ce
    v['early_count'] = ce

# 8. Save final
D['ws_bds'] = ws_bds
D['santos_bds'] = santos_bds
D['bdm_summary'] = bdm_data
D['bd_scores_detail'] = {bd: {'leads': s['leads'], 'not_signed': s['not_signed'], 'not_online': s['not_online'],
                              'not_operating': s['not_operating'], 'hv_bonus': s['hv_bonus'], 'hv_count': s['hv_count'],
                              'early': s['early'], 'total': s['total']} for bd, s in bd_scores.items()}
D['early_bird_rule'] = '铁证口径: 0805快照已营业 → +1/家 (43家名单沿用0830); 0817窗口52家待证据后补'
json.dump(D, open('order_penetration_data_0831_final.json', 'w'), indent=2, default=str, ensure_ascii=False)
print('saved order_penetration_data_0831_final.json')

q = [b for b in ws_bds + santos_bds if b['total'] >= 15]
print(f"\nQualified BDs: {len(q)}/71")
for b in ws_bds[:5] + santos_bds[:3]:
    print(f"  {b['bd']:18} total={b['total']} (early=+{b['early']})")
print('\nBDM RANKING:')
for bdm, v in sorted(bdm_data.items(), key=lambda x: -x[1]['avg']):
    print(f"  {bdm:22} {v['bd_count']}BDs team={v['team_score']} avg={v['avg']} {'OK' if v['qualified'] else ''}")
