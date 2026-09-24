import json
d = json.load(open('/mnt/openclaw/.openclaw/workspace/projects/1_weekly_report/data/20260913/bml_org_summary.json'))
print('rows:', len(d))
print('fields:', list(d[0].keys()))
mt = sum(r['merchant_total'] for r in d); md = sum(r['merchant_done'] for r in d)
st = sum(r['spu_total'] for r in d); sd = sum(r['spu_done'] for r in d)
print(f'Metro totals: merchants {md}/{mt} ({md/mt*100:.1f}%), SPUs {sd}/{st} ({sd/st*100:.1f}%)')
from collections import defaultdict
bdm = defaultdict(lambda: [0,0,0,0])
for r in d:
    b = r['bdm_mis']
    bdm[b][0] += r['merchant_total']; bdm[b][1] += r['merchant_done']
    bdm[b][2] += r['spu_total']; bdm[b][3] += r['spu_done']
print('\n== By BDM ==')
for b,(mt,md,st,sd) in sorted(bdm.items(), key=lambda x: -(x[1][3]/x[1][2] if x[1][2] else 0)):
    print(f"{b:22s} merchants {md}/{mt} ({md/mt*100 if mt else 0:.0f}%)  SPU {sd}/{st} ({sd/st*100 if st else 0:.1f}%)")
cm = defaultdict(lambda: [0,0,0,0])
for r in d:
    c = r['cm_mis']
    cm[c][0] += r['merchant_total']; cm[c][1] += r['merchant_done']
    cm[c][2] += r['spu_total']; cm[c][3] += r['spu_done']
print('\n== By CM/city ==')
for c,(mt,md,st,sd) in sorted(cm.items()):
    print(f"{c:22s} merchants {md}/{mt} ({md/mt*100 if mt else 0:.0f}%)  SPU {sd}/{st} ({sd/st*100 if st else 0:.1f}%)")
bd = defaultdict(lambda: [0,0,0,0])
for r in d:
    b = r['bd_mis']
    bd[b][0] += r['merchant_total']; bd[b][1] += r['merchant_done']
    bd[b][2] += r['spu_total']; bd[b][3] += r['spu_done']
active = {b:v for b,v in bd.items() if v[2]>0}
print(f'\n== BDs with SPU tasks: {len(active)} ==')
rows = sorted(active.items(), key=lambda x: -(x[1][3]/x[1][2]))
print('Top 5:')
for b,(mt,md,st,sd) in rows[:5]: print(f"  {b:20s} SPU {sd}/{st} ({sd/st*100:.0f}%)")
print('Bottom 5:')
for b,(mt,md,st,sd) in rows[-5:]: print(f"  {b:20s} SPU {sd}/{st} ({sd/st*100:.0f}%)")
bands = {'>=60%':0,'50-60':0,'40-50':0,'<40%':0}
for b,(mt,md,st,sd) in active.items():
    p = sd/st*100
    if p>=60: bands['>=60%']+=1
    elif p>=50: bands['50-60']+=1
    elif p>=40: bands['40-50']+=1
    else: bands['<40%']+=1
print('BD bands:', bands)
