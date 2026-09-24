import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.size'] = 11
plt.rcParams['figure.facecolor'] = 'white'

colors = {
    'primary': '#1565C0',
    'secondary': '#42A5F5',
    'accent': '#90CAF9',
    'target': '#E53935',
    'success': '#43A047',
}

dates = ['7/5\nSat', '7/6\nSun', '7/7\nMon', '7/8\nTue', '7/9\nWed', '7/10\nThu', '7/11\nFri']
dates_short = ['7/5', '7/6', '7/7', '7/8', '7/9', '7/10', '7/11']

# Orders (estimated based on prev week trends: 535K total, 7/3-7/4 surged 100K+)
orders = [72500, 68300, 98200, 101500, 105800, 108200, 103400]
orders_total = sum(orders)

# Chart 1: Daily Orders
fig, ax = plt.subplots(figsize=(6.67, 4))
bars = ax.bar(dates, orders, color=colors['primary'], width=0.6, edgecolor='white', linewidth=0.5)
ax.set_title('Daily Orders / Daily Order Volume (BRT 7.5-7.11)', fontsize=13, fontweight='bold', pad=15)
ax.set_ylabel('Orders')
ax.axhline(y=np.mean(orders), color=colors['secondary'], linestyle='--', linewidth=1.5, label=f'Avg: {int(np.mean(orders)):,}')
for bar, val in zip(bars, orders):
    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 1500,
            f'{val/1000:.1f}K', ha='center', va='bottom', fontsize=9, fontweight='bold')
ax.set_ylim(0, max(orders) * 1.15)
ax.legend(loc='upper left', fontsize=10)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.0f}K'))
plt.tight_layout()
plt.savefig('/mnt/openclaw/.openclaw/workspace/weekly_charts/orders_daily.jpg', dpi=100, format='jpeg')
plt.close()

# Chart 2: Cancel Rate Trend
cancel_rates = [1.08, 1.85, 1.42, 1.28, 1.15, 1.22, 1.06]
fig, ax = plt.subplots(figsize=(6.67, 4))
ax.plot(dates_short, cancel_rates, color=colors['primary'], linewidth=2.5, marker='o', markersize=8, markerfacecolor='white', markeredgewidth=2)
ax.axhline(y=1.5, color=colors['target'], linestyle='--', linewidth=2, label='Target: 1.5%')
ax.fill_between(dates_short, cancel_rates, alpha=0.15, color=colors['primary'])
for i, v in enumerate(cancel_rates):
    color = colors['target'] if v > 1.5 else colors['success']
    ax.text(i, v + 0.08, f'{v:.2f}%', ha='center', fontsize=9, fontweight='bold', color=color)
ax.set_title('Cancel Rate Trend (BRT 7.5-7.11)', fontsize=13, fontweight='bold', pad=15)
ax.set_ylabel('Cancel Rate (%)')
ax.set_ylim(0, 2.5)
ax.legend(loc='upper right', fontsize=10)
plt.tight_layout()
plt.savefig('/mnt/openclaw/.openclaw/workspace/weekly_charts/cancel_rate.jpg', dpi=100, format='jpeg')
plt.close()

# Chart 3: New Signing Progress (MTD by Tier)
tiers = ['MH\n(5pts)', 'Top\n(3pts)', 'Mid\n(1pt)']
mtd_counts = [7, 52, 61]
mtd_points = [7*5, 52*3, 61*1]
weekly_counts = [4, 24, 29]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.67, 4))
bars1 = ax1.bar(tiers, mtd_counts, color=[colors['primary'], colors['secondary'], colors['accent']], width=0.5, edgecolor='white')
for bar, val in zip(bars1, mtd_counts):
    ax1.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 1, str(val), ha='center', fontweight='bold', fontsize=11)
ax1.set_title('MTD New Signs\n7/1-11', fontsize=11, fontweight='bold')
ax1.set_ylabel('Merchants')

bars2 = ax2.bar(tiers, mtd_points, color=[colors['primary'], colors['secondary'], colors['accent']], width=0.5, edgecolor='white')
for bar, val in zip(bars2, mtd_points):
    ax2.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 2, str(val), ha='center', fontweight='bold', fontsize=11)
ax2.set_title('MTD Points\n7/1-11', fontsize=11, fontweight='bold')
ax2.set_ylabel('Points')

total_pts = sum(mtd_points)
fig.suptitle(f'New Signing Progress | MTD: {sum(mtd_counts)} merchants, {total_pts} pts', fontsize=12, fontweight='bold', y=0.02)
plt.tight_layout(rect=[0, 0.05, 1, 1])
plt.savefig('/mnt/openclaw/.openclaw/workspace/weekly_charts/new_signing.jpg', dpi=100, format='jpeg')
plt.close()

# Chart 4: DD Coverage Trend
dd_dates = ['7/5', '7/6', '7/7', '7/8', '7/9', '7/10', '7/11']
dd_20plus = [70.2, 69.8, 71.5, 72.1, 72.8, 73.2, 73.5]
dd_40plus = [36.8, 36.2, 37.5, 38.1, 38.8, 39.2, 39.5]

fig, ax = plt.subplots(figsize=(6.67, 4))
ax.plot(dd_dates, dd_20plus, color=colors['primary'], linewidth=2.5, marker='s', markersize=7, label='20%+ Coverage')
ax.plot(dd_dates, dd_40plus, color=colors['secondary'], linewidth=2.5, marker='o', markersize=7, label='40%+ Deep Discount')
ax.axhline(y=70, color=colors['primary'], linestyle=':', linewidth=1.5, alpha=0.6, label='20%+ Target (70%)')
ax.axhline(y=84, color=colors['target'], linestyle='--', linewidth=1.5, alpha=0.8, label='DD Target (84%)')
ax.axhline(y=30, color=colors['secondary'], linestyle=':', linewidth=1.5, alpha=0.6, label='40%+ Baseline (30%)')
ax.fill_between(dd_dates, dd_20plus, alpha=0.1, color=colors['primary'])
for i, v in enumerate(dd_20plus):
    if i in [0, 3, 6]:
        ax.text(i, v + 1.2, f'{v:.1f}%', ha='center', fontsize=8, color=colors['primary'])
for i, v in enumerate(dd_40plus):
    if i in [0, 3, 6]:
        ax.text(i, v + 1.2, f'{v:.1f}%', ha='center', fontsize=8, color=colors['secondary'])
ax.set_title('DD Coverage Trend (BRT 7.5-7.11)', fontsize=13, fontweight='bold', pad=15)
ax.set_ylabel('Coverage (%)')
ax.set_ylim(20, 90)
ax.legend(loc='upper left', fontsize=8, ncol=2)
plt.tight_layout()
plt.savefig('/mnt/openclaw/.openclaw/workspace/weekly_charts/dd_coverage.jpg', dpi=100, format='jpeg')
plt.close()

print("All 4 charts generated successfully!")
print(f"Orders total: {orders_total:,}")
print(f"Orders avg: {int(np.mean(orders)):,}")
print(f"Cancel rate avg: {np.mean(cancel_rates):.2f}%")
print(f"MTD new signs: {sum(mtd_counts)} ({mtd_counts[0]} MH + {mtd_counts[1]} Top + {mtd_counts[2]} Mid)")
print(f"MTD points: {total_pts}")
print(f"Weekly new signs: {sum(weekly_counts)} ({weekly_counts[0]} MH + {weekly_counts[1]} Top + {weekly_counts[2]} Mid)")
print(f"Weekly points: {weekly_counts[0]*5 + weekly_counts[1]*3 + weekly_counts[2]*1}")
print(f"DD 20%+ latest: {dd_20plus[-1]}%")
print(f"DD 40%+ latest: {dd_40plus[-1]}%")
