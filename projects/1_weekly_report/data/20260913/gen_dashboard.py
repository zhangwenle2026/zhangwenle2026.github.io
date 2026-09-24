#!/usr/bin/env python3
# S2 BML数据看板大图（修复版v3）
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import json, matplotlib.font_manager as fm
from collections import defaultdict

OUT = '/mnt/openclaw/.openclaw/workspace/projects/1_weekly_report/data/20260913/charts'
GREEN, LGREEN, YELLOW, RED, GREY, BLUE, DKGREY = '#10b981', '#84cc16', '#f59e0b', '#ef4444', '#888888', '#3b82f6', '#4b5563'

font_path = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
ch_font = fm.FontProperties(fname=font_path)
plt.rcParams.update({'font.size': 10, 'figure.dpi': 150, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.unicode_minus': False})

d = json.load(open('/mnt/openclaw/.openclaw/workspace/projects/1_weekly_report/data/20260913/bml_org_summary.json'))

city_cm = {'danielalbuquerque': 'Southern', 'marciojaroslavsky': 'Western', 'jaylin': 'Santos'}
cities = defaultdict(lambda: [0,0,0,0])
bdm_by_city = defaultdict(lambda: defaultdict(lambda: [0,0,0,0]))
other = [0,0,0,0]
for r in d:
    st, sd, mt, md = r['spu_total'], r['spu_done'], r['merchant_total'], r['merchant_done']
    city = city_cm.get(r['cm_mis'])
    if city:
        c = cities[city]; c[0]+=mt; c[1]+=md; c[2]+=st; c[3]+=sd
        b = bdm_by_city[city][r['bdm_mis']]; b[2]+=st; b[3]+=sd; b[0]+=mt; b[1]+=md
    else:
        other[0]+=mt; other[1]+=md; other[2]+=st; other[3]+=sd

names_map = {'tadeumoraes':'Tadeu','adriananaves':'Adriana','fernandooliveira':'Fernando','biancaceotto':'Bianca','sabrinafernandes':'Sabrina','igorfeitosa':'Igor','alisaeed':'Ali','cesararraes':'Cesar','renataleite':'Renata','lucasferreira':'Lucas F.','thiagoscavazini':'Thiago'}
city_colors = {'Southern': GREEN, 'Western': RED, 'Santos': YELLOW}
city_order = ['Southern', 'Western', 'Santos']

fig = plt.figure(figsize=(11, 9.5))
gs = gridspec.GridSpec(2, 2, height_ratios=[1, 1.25], hspace=0.40, wspace=0.30)

# (a) 城市SPU完成率
ax1 = fig.add_subplot(gs[0, 0])
cvals = [cities[c][3]/cities[c][2]*100 for c in city_order]
bars = ax1.barh(city_order[::-1], cvals[::-1], color=[city_colors[c] for c in city_order[::-1]], height=0.55)
for bar, p in zip(bars, cvals[::-1]):
    ax1.text(p+1, bar.get_y()+bar.get_height()/2, f"{p:.1f}%", va='center', fontsize=11, fontweight='bold')
ax1.axvline(60, color=DKGREY, ls='--', lw=1.2)
ax1.text(60.5, 2.62, 'Target: 60% (coeff=1.0)', fontsize=9, color=DKGREY, va='bottom')
ax1.set_xlim(0, 78)
ax1.set_title('SPU Completion by City', fontsize=11, fontweight='bold')
ax1.set_xlabel('SPU completion rate (%)', fontproperties=ch_font)

# (b) 城市商户完成率
ax2 = fig.add_subplot(gs[0, 1])
mvals = [cities[c][1]/cities[c][0]*100 for c in city_order]
bars = ax2.barh(city_order[::-1], mvals[::-1], color=[city_colors[c] for c in city_order[::-1]], height=0.55)
for bar, p in zip(bars, mvals[::-1]):
    ax2.text(p+1, bar.get_y()+bar.get_height()/2, f"{p:.1f}%", va='center', fontsize=11, fontweight='bold')
ax2.axvline(60, color=DKGREY, ls='--', lw=1.2)
ax2.text(60.5, 2.62, 'Target: 60% (coeff=1.0)', fontsize=9, color=DKGREY, va='bottom')
ax2.set_xlim(0, 78)
ax2.set_title('Merchant Completion by City', fontsize=11, fontweight='bold')
ax2.set_xlabel('Merchant completion rate (%)', fontproperties=ch_font)

# (c) BDM SPU完成率
ax3 = fig.add_subplot(gs[1, :])
individual = []
for city, bdict in bdm_by_city.items():
    for b, v in bdict.items():
        individual.append((names_map.get(b, b), city, v[3]/v[2]*100 if v[2] else 0))
individual.sort(key=lambda x: -x[2])

names = [x[0] for x in individual]
vals  = [x[2] for x in individual]
cols  = [city_colors[x[1]] for x in individual]
bars  = ax3.bar(names, vals, color=cols, width=0.62)
for bar, x in zip(bars, individual):
    ax3.text(bar.get_x()+bar.get_width()/2, x[2]+1.5, f"{x[2]:.1f}%", ha='center', fontsize=8.5)
ax3.axhline(60, color=DKGREY, ls='--', lw=1.2)
ax3.text(0.96, 0.98, f'Unassigned _other_\n{other[3]/other[2]*100:.1f}%\n({other[3]:,}/{other[2]:,} SPU)\n*BDs pending assignment*',
         transform=ax3.transAxes, fontsize=9, va='top', ha='right', color=GREY,
         bbox=dict(boxstyle='round,pad=0.35', facecolor='white', edgecolor=GREY, alpha=0.95))
# 目标线注释放在BDM图内左上
ax3.text(0.01, 0.98, 'Target: 60%\n(coeff=1.0)', transform=ax3.transAxes, fontsize=9, color=DKGREY, va='top')
ax3.set_ylim(0, 75)
ax3.set_ylabel('SPU completion rate (%)', fontproperties=ch_font)
ax3.set_title('SPU Completion by BDM (individual + unassigned summary on right)', fontsize=11, fontweight='bold')

import matplotlib.patches as mpatches
handles = [mpatches.Patch(color=GREEN, label='Southern'), mpatches.Patch(color=RED, label='Western'),
           mpatches.Patch(color=YELLOW, label='Santos')]
ax3.legend(handles=handles, loc='upper left', fontsize=9, frameon=False, bbox_to_anchor=(0.01, 0.60), borderaxespad=0)

fig.suptitle('BML Menu Price Correction Dashboard (as of Sep 12 · SP Metro)', fontsize=13, fontweight='bold', y=0.995)
plt.savefig(f'{OUT}/bml_dashboard.jpg', bbox_inches='tight', dpi=150)
plt.close()
print('saved', f'{OUT}/bml_dashboard.jpg')
from PIL import Image
print('size:', Image.open(f'{OUT}/bml_dashboard.jpg').size)
