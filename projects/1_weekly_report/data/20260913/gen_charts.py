#!/usr/bin/env python3
# 9月第1期周报图表生成 (BRT 9.7-9.13)
# 数据源: bml_org_summary.json, visit_record.xlsx (本地解析结果)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json, os
from collections import defaultdict

OUT = '/mnt/openclaw/.openclaw/workspace/projects/1_weekly_report/data/20260913/charts'
os.makedirs(OUT, exist_ok=True)

# 配色 (skill规范)
GREEN, LGREEN, YELLOW, RED, GREY = '#10b981', '#84cc16', '#f59e0b', '#ef4444', '#888888'
plt.rcParams.update({'font.size': 10, 'figure.dpi': 150, 'axes.spines.top': False, 'axes.spines.right': False})

def color_band(p):
    if p >= 60: return GREEN
    if p >= 40: return YELLOW
    return RED

d = json.load(open('/mnt/openclaw/.openclaw/workspace/projects/1_weekly_report/data/20260913/bml_org_summary.json'))

# ============ Chart 1: BML BDM SPU完成率 (KRI行1) ============
bdm = defaultdict(lambda: [0,0,0,0])
for r in d:
    b = r['bdm_mis']
    bdm[b][0] += r['merchant_total']; bdm[b][1] += r['merchant_done']
    bdm[b][2] += r['spu_total']; bdm[b][3] += r['spu_done']
names_map = {'tadeumoraes':'Tadeu','adriananaves':'Adriana','fernandooliveira':'Fernando','biancaceotto':'Bianca','sabrinafernandes':'Sabrina','igorfeitosa':'Igor','alisaeed':'Ali','cesararraes':'Cesar','renataleite':'Renata','lucasferreira':'Lucas F.','thiagoscavazini':'Thiago'}
items = sorted([(names_map.get(b,b), v[3]/v[2]*100, v[3], v[2]) for b,v in bdm.items() if b != '_other_'], key=lambda x: -x[1])
fig, ax = plt.subplots(figsize=(8, 4.2))
labels = [f"{n}\n{sd}/{st}" for n,p,sd,st in items]
vals = [p for n,p,sd,st in items]
bars = ax.bar(labels, vals, color=[color_band(p) for p in vals])
ax.axhline(60, color=GREY, ls='--', lw=1.2)
ax.text(11.4, 61.5, '60% target (coeff 1.0)', ha='right', fontsize=8, color=GREY)
for bar, p in zip(bars, vals):
    ax.text(bar.get_x()+bar.get_width()/2, p+1, f"{p:.1f}%", ha='center', fontsize=8.5)
ax.set_ylabel('SPU completion rate')
ax.set_title('BML Menu Price Correction — BDM SPU Completion (as of Sep 12)', fontsize=11, fontweight='bold')
ax.set_ylim(0, 70)
plt.tight_layout(); plt.savefig(f'{OUT}/bml_bdm_spu.jpg', bbox_inches='tight'); plt.close()

# ============ Chart 2: BML 城市对比 (Southern/Western/Santos) ============
cm = defaultdict(lambda: [0,0,0,0])
for r in d:
    c = r['cm_mis']
    cm[c][0] += r['merchant_total']; cm[c][1] += r['merchant_done']
    cm[c][2] += r['spu_total']; cm[c][3] += r['spu_done']
city = {'Southern SP Metro': 'danielalbuquerque', 'Western SP Metro': 'marciojaroslavsky', 'Santos City': 'jaylin'}
fig, ax = plt.subplots(figsize=(7, 3.6))
xs, vs, cs = [], [], []
for i,(label, cmis) in enumerate(city.items()):
    mt,md,st,sd = cm[cmis]
    xs.append(label); vs.append(sd/st*100); cs.append(color_band(sd/st*100))
bars = ax.bar(xs, vs, color=cs, width=0.5)
for bar, v in zip(bars, vs):
    ax.text(bar.get_x()+bar.get_width()/2, v+1.2, f"{v:.1f}%", ha='center', fontsize=10)
ax.axhline(60, color=GREY, ls='--', lw=1.2)
ax.set_ylabel('SPU completion rate')
ax.set_title('BML SPU Completion by City (as of Sep 12)', fontsize=11, fontweight='bold')
ax.set_ylim(0, 70)
plt.tight_layout(); plt.savefig(f'{OUT}/bml_city.jpg', bbox_inches='tight'); plt.close()

# ============ Chart 3: Daily Visit Volume ============
days = [('9/7 Sun', 12), ('9/8 Mon', 274), ('9/9 Tue', 493), ('9/10 Wed', 455), ('9/11 Thu', 598), ('9/12 Sat', 22)]
fig, ax = plt.subplots(figsize=(7, 3.6))
labels = [d for d,v in days]; vals = [v for d,v in days]
bars = ax.bar(labels, vals, color=['#cbd5e1'] + ['#3b82f6']*4 + ['#cbd5e1'])
for bar, v in zip(bars, vals):
    ax.text(bar.get_x()+bar.get_width()/2, v+8, str(v), ha='center', fontsize=9)
avg = 458.8
ax.axhline(avg, color=GREY, ls='--', lw=1.2)
ax.text(5.4, avg+12, 'Mon-Thu avg 458', ha='right', fontsize=8, color=GREY)
ax.set_ylabel('Visits')
ax.set_title('Daily Visit Volume — SP Metro (BRT Sep 7-12)', fontsize=11, fontweight='bold')
plt.tight_layout(); plt.savefig(f'{OUT}/visit_daily.jpg', bbox_inches='tight'); plt.close()

# ============ Chart 4: 城市拜访人均 ============
fig, ax = plt.subplots(figsize=(7, 3.6))
regs = [('Southern (37 BD)', 4.4), ('Western (32 BD)', 4.7), ('Santos (12 BD)', 4.8)]
labels = [r for r,v in regs]; vals = [v for r,v in regs]
bars = ax.bar(labels, vals, color=[YELLOW, LGREEN, GREEN], width=0.5)
for bar, v in zip(bars, vals):
    ax.text(bar.get_x()+bar.get_width()/2, v+0.06, f"{v:.1f}", ha='center', fontsize=10)
ax.axhline(5.0, color=GREY, ls='--', lw=1.2)
ax.text(2.45, 5.06, 'target 5.0', ha='right', fontsize=8, color=GREY)
ax.set_ylabel('Visits per BD per day')
ax.set_title('Visit Productivity by City (Mon-Fri, 81 BDs)', fontsize=11, fontweight='bold')
ax.set_ylim(0, 6)
plt.tight_layout(); plt.savefig(f'{OUT}/visit_region.jpg', bbox_inches='tight'); plt.close()

# ============ Chart 5: 竞对提及分布 ============
fig, ax = plt.subplots(figsize=(7, 3.6))
comp = [('99', 73), ('Red', 45), ('Yellow', 24), ('iFood', 22)]
labels = [c for c,v in comp]; vals = [v for c,v in comp]
bars = ax.bar(labels, vals, color=['#ef4444', '#f59e0b', '#eab308', '#f97316'], width=0.5)
for bar, v in zip(bars, vals):
    ax.text(bar.get_x()+bar.get_width()/2, v+1, str(v), ha='center', fontsize=10)
ax.set_ylabel('Mentions')
ax.set_title('Competitor Mentions in Visit Records (Sep 7-12)', fontsize=11, fontweight='bold')
plt.tight_layout(); plt.savefig(f'{OUT}/competitor_mentions.jpg', bbox_inches='tight'); plt.close()

print('charts done:', os.listdir(OUT))
