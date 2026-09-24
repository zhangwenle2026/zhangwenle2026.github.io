#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gen 4 KRI charts for weekly report BRT 9.14-9.18 (bdm_kri_0918.json, 11 BDM rows excl. CM)."""
import json, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

DATA = json.load(open('/root/.openclaw/workspace/projects/1_weekly_report/data/20260920/bdm_kri_0918.json'))
BDM = [r for r in DATA if r['role_level'] == 'BDM']
BDM.sort(key=lambda r: -r['total_coefficient'])
names = [r['mid_id'] for r in BDM]

def short(n):
    return n.replace('jaroslavsky','').replace('albuquerque','').replace('oliveira','').replace('ferreira','').replace('ceotto','').replace('arraes','').replace('fernandes','').replace('scavazini','').replace('moraes','').replace('anaves','').replace('leite','').replace('feitosa','').replace('saeed','') if len(n)>10 else n

# display names: keep readable short forms
disp = {
 'adriananaves':'Adriana','alisaeed':'Ali','biancaceotto':'Bianca','cesararraes':'Cesar',
 'fernandooliveira':'Fernando','igorfeitosa':'Igor','lucasferreira':'Lucas F.',
 'renataleite':'Renata','sabrinafernandes':'Sabrina','tadeumoraes':'Tadeu','thiagoscavazini':'Thiago'}
NAMES = [disp.get(n, n) for n in names]
OUT = '/root/.openclaw/workspace/projects/1_weekly_report/data/20260920/charts'

def band_color(v, bands):
    for lim, c in bands:
        if v >= lim:
            return c
    return bands[-1][1]

# --- Chart 1: Orders — total achievement + KM achievement (dual bars) ---
fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
x = np.arange(len(names)); w = 0.38
tot = [r['total_order_achievement_rate']*100 for r in BDM]
km  = [r['keymerch_order_achievement_rate']*100 for r in BDM]
avg = np.mean(tot)
b1 = ax.bar(x-w/2, tot, w, label='Total Orders 达成率', color='#f4a63a')
b2 = ax.bar(x+w/2, km, w, label='Key Merchant 达成率', color='#3a7f5a')
ax.axhline(avg, color='#c0392b', ls='--', lw=1.2, label=f'Total Avg {avg:.1f}%')
for xi, v in zip(x-w/2, tot):
    ax.text(xi, v+0.8, f'{v:.0f}', ha='center', fontsize=8, color='#555')
for xi, v in zip(x+w/2, km):
    ax.text(xi, v+0.8, f'{v:.0f}', ha='center', fontsize=8, color='#3a7f5a')
ax.set_xticks(x); ax.set_xticklabels(NAMES, rotation=30, ha='right', fontsize=9)
ax.set_ylabel('Achievement %'); ax.set_ylim(0, 100)
ax.set_title('Orders MTD Achievement by BDM (Sep, excl. Daniel*)  订单达成率', fontsize=12)
ax.legend(fontsize=8); ax.grid(axis='y', alpha=0.3)
plt.tight_layout(); plt.savefig(f'{OUT}/kri_orders.jpg', bbox_inches='tight'); plt.close()

# --- Chart 2: New Sign — MTD count + coefficient (bar + markers) ---
fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
cnt = [r['newsign_conquest_count'] for r in BDM]
coef = [r['newsign_coefficient'] for r in BDM]
order = sorted(range(len(names)), key=lambda i: -cnt[i])
cnt_s = [cnt[i] for i in order]; coef_s = [coef[i] for i in order]
NM = [NAMES[i] for i in order]
bars = ax.bar(range(len(order)), cnt_s, color='#5b8db8', label='MTD New Signs 家数')
ax.axhline(np.mean(cnt), color='#888', ls=':', lw=1, label=f'Avg {np.mean(cnt):.1f}')
ax2 = ax.twinx()
ax2.plot(range(len(order)), coef_s, 'o-', color='#c0392b', lw=1.5, ms=5, label='NS Coefficient 系数')
ax2.axhline(1.0, color='#c0392b', ls='--', lw=0.8, alpha=0.6)
for i, (c, k) in enumerate(zip(cnt_s, coef_s)):
    ax.text(i, c+0.3, f'{c:.0f}', ha='center', fontsize=8, color='#334')
    ax2.text(i, k+0.04, f'{k:.2f}', ha='center', fontsize=7, color='#c0392b')
ax.set_xticks(range(len(order))); ax.set_xticklabels(NM, rotation=30, ha='right', fontsize=9)
ax.set_ylabel('New Signs (count)'); ax2.set_ylabel('NS Coefficient'); ax2.set_ylim(0, 1.4)
ax.set_title('New Sign MTD: Count & Coefficient by BDM (Sep, excl. Daniel*)  新签', fontsize=12)
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1+h2, l1+l2, fontsize=8, loc='upper right')
ax.grid(axis='y', alpha=0.3)
plt.tight_layout(); plt.savefig(f'{OUT}/kri_newsign.jpg', bbox_inches='tight'); plt.close()

# --- Chart 3: Op Rate — churn exposure: deduction count vs SA merchant count (all coeff 0.5) ---
fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
sa = [r['op_sa_merchant_count'] for r in BDM]
ded = [r['op_deduction_count'] for r in BDM]
order = sorted(range(len(names)), key=lambda i: -sa[i])
sa_s = [sa[i] for i in order]; ded_s = [ded[i] for i in order]; NM = [NAMES[i] for i in order]
x = np.arange(len(order))
ax.bar(x-w/2, sa_s, w, color='#5b8db8', label='S/A Managed Merchants 在管商户')
ax.bar(x+w/2, ded_s, w, color='#c0392b', alpha=0.75, label='Churn Deductions (pre-exemption) 流失扣减')
for xi, v in zip(x-w/2, sa_s):
    ax.text(xi, v+3, f'{v:.0f}', ha='center', fontsize=8, color='#334')
ax.set_xticks(x); ax.set_xticklabels(NM, rotation=30, ha='right', fontsize=9)
ax.set_ylabel('Merchants'); ax.set_ylim(0, max(sa_s)*1.15)
ax.set_title('Op Rate: Managed Book vs Churn Deductions — exemptions pending, all coeff 0.5  营业率口径待豁免', fontsize=11)
ax.legend(fontsize=8); ax.grid(axis='y', alpha=0.3)
plt.tight_layout(); plt.savefig(f'{OUT}/kri_oprate.jpg', bbox_inches='tight'); plt.close()

# --- Chart 4: CI — result_level + coefficient band ---
fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
rl = [r['ci_result_level']*100 for r in BDM]
cf = [r['campaign_intel_coefficient'] for r in BDM]
order = sorted(range(len(names)), key=lambda i: -rl[i])
rl_s = [rl[i] for i in order]; cf_s = [cf[i] for i in order]; NM = [NAMES[i] for i in order]
# band colors by coefficient
cmap = {1.2:'#2e8b57', 1.1:'#7fbc6a', 1.0:'#a9d18e', 0.8:'#e6c068'}
cols = [cmap.get(round(c,2), '#bbb') for c in cf_s]
bars = ax.bar(range(len(order)), rl_s, color=cols)
for i, (v, c) in enumerate(zip(rl_s, cf_s)):
    ax.text(i, v+0.6, f'{v:.1f}%', ha='center', fontsize=8, color='#334')
    ax.text(i, max(v-6, 3), f'{c:.1f}x', ha='center', fontsize=8, color='white', fontweight='bold')
ax.axhline(78, color='#c0392b', ls='--', lw=1, label='Metro top band ≥78%')
ax.axhline(70, color='#e67e22', ls='--', lw=1, label='Santos top band ≥70%')
ax.set_xticks(range(len(order))); ax.set_xticklabels(NM, rotation=30, ha='right', fontsize=9)
ax.set_ylabel('CI Result Level %'); ax.set_ylim(0, 100)
ax.set_title('Campaign Intelligence: Result Level & Coefficient Band  智能营销', fontsize=12)
ax.legend(fontsize=8, loc='lower right'); ax.grid(axis='y', alpha=0.3)
plt.tight_layout(); plt.savefig(f'{OUT}/kri_ci.jpg', bbox_inches='tight'); plt.close()

print('done:', [f for f in ['kri_orders.jpg','kri_newsign.jpg','kri_oprate.jpg','kri_ci.jpg']])
print('BDM order:', NAMES)
print('orders avg', round(avg,1), 'ns total', sum(cnt), 'ci avg', round(np.mean(rl),1))
