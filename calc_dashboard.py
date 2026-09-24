import pandas as pd
import json

df = pd.read_excel('redtop2000_0805.xlsx')

# Filter Metropolitan Region cities only
metro_cities = ['Southern S\u00e3o Paulo Metropolitan', 'Western S\u00e3o Paulo Metropolitan', 'Santos City']
mdf = df[df['city'].isin(metro_cities)].copy()

city_short = {
    'Southern S\u00e3o Paulo Metropolitan': 'Southern',
    'Western S\u00e3o Paulo Metropolitan': 'Western',
    'Santos City': 'Santos'
}
mdf['city_short'] = mdf['city'].map(city_short)

# Score calculation
score_map = {'not sign': 6, 'not online': 4, 'not operating': 3}
mdf['operating'] = mdf['0730-0805 operating'].fillna(0).astype(float)
mdf['base_score'] = mdf.apply(lambda r: score_map.get(r['target type'], 0) if r['operating'] == 1.0 else 0, axis=1)
mdf['hv_bonus'] = mdf.apply(lambda r: 2 if r['operating'] == 1.0 and r['red order'] >= 20 else 0, axis=1)
mdf['total_score'] = mdf['base_score'] + mdf['hv_bonus']

# Regional overview
total_merchants = len(mdf)
has_bd = mdf['BD'].notna() & (mdf['BD'] != '')
assigned_bd = int(has_bd.sum())
assigned_pct = round(assigned_bd / total_merchants * 100, 1)
total_operating = int(mdf['operating'].sum())
operating_pct = round(total_operating / total_merchants * 100, 1)
total_score = int(mdf['total_score'].sum())

# Signed count
total_signed = int(mdf['sign-0806'].sum())

data = {
    'region': {
        'total': total_merchants, 'assigned': assigned_bd, 'assigned_pct': assigned_pct,
        'operating': total_operating, 'operating_pct': operating_pct, 'score': total_score,
        'signed': total_signed
    },
    'directions': {},
    'cities': {},
    'ws_bds': [],
    'santos_bds': [],
    'ws_bdms': [],
    'santos_bdms': []
}

# By direction
for tt in ['not sign', 'not online', 'not operating']:
    sub = mdf[mdf['target type'] == tt]
    t = len(sub)
    o = int(sub['operating'].sum())
    s = int(sub['total_score'].sum())
    pct = round(o/t*100, 1) if t > 0 else 0
    data['directions'][tt] = {'target': t, 'operating': o, 'score': s, 'pct': pct}

# City overview
for city in ['Southern', 'Western', 'Santos']:
    csub = mdf[mdf['city_short'] == city]
    ct = len(csub)
    ca = int((csub['BD'].notna() & (csub['BD'] != '')).sum())
    ca_pct = round(ca/ct*100, 1) if ct > 0 else 0
    cu = ct - ca
    co = int(csub['operating'].sum())
    cs = int(csub['total_score'].sum())
    co_pct = round(co/ct*100, 1) if ct > 0 else 0
    dirs = {}
    for tt in ['not sign', 'not online', 'not operating']:
        sub2 = csub[csub['target type'] == tt]
        t2 = len(sub2)
        o2 = int(sub2['operating'].sum())
        s2 = int(sub2['total_score'].sum())
        pct2 = round(o2/t2*100, 1) if t2 > 0 else 0
        dirs[tt] = {'target': t2, 'operating': o2, 'score': s2, 'pct': pct2}
    data['cities'][city] = {
        'target': ct, 'assigned': ca, 'assigned_pct': ca_pct,
        'unassigned': cu, 'operating': co, 'score': cs, 'operating_pct': co_pct,
        'directions': dirs
    }

# BD Rankings - only include BDs under our actual BDMs
bd_df = mdf[mdf['BD'].notna() & (mdf['BD'] != '')].copy()

# Filter to only BDs whose BDM is one of our actual BDMs
our_bdm_set = {'adriananaves', 'fernandooliveira', 'eduardoalbuquerque', 'alisaeed', 'tadeumoraes',
               'igorfeitosa', 'lucasferreira', 'cesararraes', 'thiagoscavazini', 'biancaceotto',
               'renataleite', 'sabrinafernandes'}
bd_df = bd_df[bd_df['BDM'].isin(our_bdm_set)].copy()

bd_ranks = []
for bd, grp in bd_df.groupby('BD'):
    bdm = grp['BDM'].dropna().iloc[0] if grp['BDM'].notna().any() else ''
    city = grp['city_short'].iloc[0]
    ns = int(grp[grp['target type']=='not sign']['base_score'].sum())
    no = int(grp[grp['target type']=='not online']['base_score'].sum())
    nop = int(grp[grp['target type']=='not operating']['base_score'].sum())
    hv = int(grp['hv_bonus'].sum())
    total = ns + no + nop + hv
    details = []
    scored = grp[grp['total_score'] > 0]
    for _, r in scored.iterrows():
        details.append({
            'name': r['Lead Name'],
            'dir': r['target type'],
            'base': int(r['base_score']),
            'hv': int(r['hv_bonus']),
            'sub': int(r['total_score'])
        })
    bd_ranks.append({
        'bd': bd, 'bdm': str(bdm), 'city': city,
        'ns': ns, 'no': no, 'nop': nop, 'hv': hv, 'total': total,
        'details': details
    })

bd_ranks.sort(key=lambda x: (-x['total'], x['bd']))
data['ws_bds'] = [b for b in bd_ranks if b['city'] in ['Western', 'Southern']]
data['santos_bds'] = [b for b in bd_ranks if b['city'] == 'Santos']

# BDM Rankings - only include actual BDMs from HC table
# Southern CM danielalbuquerque's BDMs:
southern_bdms = ['adriananaves', 'fernandooliveira', 'eduardoalbuquerque', 'alisaeed', 'tadeumoraes']
# Western CM marciojaroslavsky's BDMs:
western_bdms = ['igorfeitosa', 'lucasferreira', 'cesararraes', 'thiagoscavazini', 'biancaceotto']
# Santos CM jaylin's BDMs:
santos_bdms_list = ['renataleite', 'sabrinafernandes']

all_our_bdms = set(southern_bdms + western_bdms + santos_bdms_list)
ws_bdm_set = set(southern_bdms + western_bdms)
santos_bdm_set = set(santos_bdms_list)

for bdm, grp in bd_df.groupby('BDM'):
    if pd.isna(bdm) or bdm == '': continue
    bdm_str = str(bdm)
    if bdm_str not in all_our_bdms:
        continue  # Skip non-BDM people (CMs, RMs, etc.)
    team_score = int(grp['total_score'].sum())
    bd_count = grp['BD'].nunique()
    avg = round(team_score / bd_count, 1) if bd_count > 0 else 0
    if bdm_str in southern_bdms:
        city_display = 'Southern'
    elif bdm_str in western_bdms:
        city_display = 'Western'
    else:
        city_display = 'Santos'
    entry = {'bdm': bdm_str, 'city': city_display, 'score': team_score, 'bd_count': bd_count, 'avg': avg}
    if bdm_str in ws_bdm_set:
        data['ws_bdms'].append(entry)
    else:
        data['santos_bdms'].append(entry)

data['ws_bdms'].sort(key=lambda x: (-x['avg'], x['bdm']))
data['santos_bdms'].sort(key=lambda x: (-x['avg'], x['bdm']))

with open('/tmp/dashboard_data.json', 'w') as f:
    json.dump(data, f, ensure_ascii=False)

print(json.dumps(data['region']))
print(f"WS BDs: {len(data['ws_bds'])}, Santos BDs: {len(data['santos_bds'])}")
print(f"WS BDMs: {len(data['ws_bdms'])}, Santos BDMs: {len(data['santos_bdms'])}")
for d in ['not sign', 'not online', 'not operating']:
    dd = data['directions'][d]
    print(f"  {d}: target={dd['target']}, operating={dd['operating']}, score={dd['score']}")
for c in ['Southern', 'Western', 'Santos']:
    cc = data['cities'][c]
    print(f"  {c}: target={cc['target']}, assigned={cc['assigned']}, operating={cc['operating']}, score={cc['score']}")
print("DONE")
