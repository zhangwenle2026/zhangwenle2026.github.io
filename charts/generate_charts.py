import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os

plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica']
plt.rcParams['axes.unicode_minus'] = False

output_dir = '/mnt/openclaw/.openclaw/workspace/charts'

fig_width = 667 / 200
fig_height = 400 / 200

blue1 = '#2e6fba'
blue2 = '#4a90d4'
blue3 = '#7ab3e8'
red = '#e74c3c'
green = '#27ae60'
orange = '#f39c12'

# Chart 1: Daily New Signs
dates1 = ['6/28', '6/29', '6/30', '7/1', '7/2', '7/3', '7/4']
top = [0, 1, 2, 8, 7, 8, 2]
mid = [0, 0, 4, 9, 10, 9, 0]
mh = [0, 0, 0, 1, 1, 1, 0]
total = [0, 1, 6, 18, 18, 18, 2]

fig, ax = plt.subplots(figsize=(fig_width, fig_height))
x = np.arange(len(dates1))
width = 0.22

bars1 = ax.bar(x - width*1.5, top, width, label='Top', color=blue1)
bars2 = ax.bar(x - width*0.5, mid, width, label='Mid', color=blue2)
bars3 = ax.bar(x + width*0.5, mh, width, label='MH', color=blue3)
bars4 = ax.bar(x + width*1.5, total, width, label='Total', color=orange, alpha=0.8)

ax.set_xlabel('Date', fontsize=7)
ax.set_ylabel('New Signs', fontsize=7)
ax.set_title('Daily New Signs (BRT 6.28-7.4)\nWeekly: Top=28, Mid=32, MH=3, Total=63', fontsize=7, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(dates1, fontsize=6)
ax.legend(fontsize=6, loc='upper left')
ax.tick_params(axis='y', labelsize=6)
ax.set_ylim(0, max(total) + 4)

for bar in bars4:
    h = bar.get_height()
    if h > 0:
        ax.annotate(f'{int(h)}', xy=(bar.get_x() + bar.get_width()/2, h),
                   xytext=(0, 2), textcoords="offset points", ha='center', fontsize=5, color=orange)

plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'chart1_new_signs.jpg'), dpi=200, format='jpeg', bbox_inches='tight')
plt.close()

# Chart 2: Promotion Coverage
dates2 = ['6/28', '6/29', '6/30', '7/1', '7/2', '7/3', '7/4']
coverage_20 = [71.2, 71.8, 70.7, 70.3, 70.4, 70.2, 69.9]
dd_40 = [36.8, 37.0, 36.7, 36.8, 36.7, 36.4, 36.5]
total_promo = [93.8, 93.8, 93.7, 93.8, 93.9, 93.8, 93.8]

fig, ax = plt.subplots(figsize=(fig_width, fig_height))

ax.plot(dates2, total_promo, 'o-', color=blue1, linewidth=1.5, markersize=4, label='Total Promo')
ax.plot(dates2, coverage_20, 's-', color=blue2, linewidth=1.5, markersize=4, label='20%+ Coverage')
ax.plot(dates2, dd_40, '^-', color=orange, linewidth=1.5, markersize=4, label='40% DD')

for i, (tp, c20, d40) in enumerate(zip(total_promo, coverage_20, dd_40)):
    ax.annotate(f'{tp}%', (dates2[i], tp), textcoords="offset points", xytext=(0, 6), ha='center', fontsize=5, color=blue1)
    ax.annotate(f'{c20}%', (dates2[i], c20), textcoords="offset points", xytext=(0, 6), ha='center', fontsize=5, color=blue2)
    ax.annotate(f'{d40}%', (dates2[i], d40), textcoords="offset points", xytext=(0, -10), ha='center', fontsize=5, color=orange)

ax.set_xlabel('Date', fontsize=7)
ax.set_ylabel('Coverage %', fontsize=7)
ax.set_title('Promotion Coverage (BRT 6.28-7.4)', fontsize=7, fontweight='bold')
ax.legend(fontsize=6, loc='lower left')
ax.tick_params(axis='both', labelsize=6)
ax.set_ylim(30, 100)
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'chart2_promo_coverage.jpg'), dpi=200, format='jpeg', bbox_inches='tight')
plt.close()

# Chart 3: Cancel Rate Trend
dates3 = ['6/26', '6/27', '6/28', '6/29', '6/30', '7/1', '7/2', '7/3', '7/4']
cancel_rate = [0.97, 1.03, 1.37, 2.02, 1.54, 1.35, 1.24, 0.98, 1.03]
target = 1.5

fig, ax = plt.subplots(figsize=(fig_width, fig_height))

colors = [red if v > target else green for v in cancel_rate]
ax.plot(dates3, cancel_rate, '-', color=blue1, linewidth=1.5, zorder=1)
ax.scatter(dates3, cancel_rate, c=colors, s=30, zorder=2)

ax.axhline(y=target, color=red, linestyle='--', linewidth=1, alpha=0.7, label=f'Target: {target}%')

for i, v in enumerate(cancel_rate):
    color = red if v > target else green
    ax.annotate(f'{v}%', (dates3[i], v), textcoords="offset points", xytext=(0, 8), ha='center', fontsize=5.5, color=color, fontweight='bold')

ax.set_xlabel('Date', fontsize=7)
ax.set_ylabel('Cancel Rate %', fontsize=7)
ax.set_title('Cancel Rate Trend (Target: 1.5%)', fontsize=7, fontweight='bold')
ax.legend(fontsize=6)
ax.tick_params(axis='both', labelsize=6)
ax.set_ylim(0.5, 2.5)
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'chart3_cancel_rate.jpg'), dpi=200, format='jpeg', bbox_inches='tight')
plt.close()

# Chart 4: Daily Orders
dates4 = ['6/28', '6/29', '6/30', '7/1', '7/2', '7/3', '7/4']
orders = [81061, 58605, 60258, 61694, 63501, 103670, 106990]

fig, ax = plt.subplots(figsize=(fig_width, fig_height))

bars = ax.bar(dates4, orders, color=blue1, width=0.6, edgecolor='white', linewidth=0.5)

for bar, val in zip(bars, orders):
    if val > 100000:
        bar.set_color(blue2)

for bar, val in zip(bars, orders):
    ax.annotate(f'{val:,}', xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
               xytext=(0, 4), textcoords="offset points", ha='center', fontsize=5, fontweight='bold')

ax.set_xlabel('Date', fontsize=7)
ax.set_ylabel('Orders', fontsize=7)
ax.set_title('Daily Orders (BRT 6.28-7.4)', fontsize=7, fontweight='bold')
ax.tick_params(axis='both', labelsize=6)
ax.set_ylim(0, max(orders) * 1.15)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
ax.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'chart4_daily_orders.jpg'), dpi=200, format='jpeg', bbox_inches='tight')
plt.close()

print("All 4 charts generated successfully!")
for f in ['chart1_new_signs.jpg', 'chart2_promo_coverage.jpg', 'chart3_cancel_rate.jpg', 'chart4_daily_orders.jpg']:
    path = os.path.join(output_dir, f)
    size = os.path.getsize(path)
    print(f"  {f}: {size} bytes")
