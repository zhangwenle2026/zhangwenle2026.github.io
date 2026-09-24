#!/usr/bin/env python3
"""Generate 4 KRI charts for SP Metropolitan Weekly Report (BRT 2026-05-31 ~ 2026-06-06)"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import json
import os

# Global settings - use CJK-capable font
plt.rcParams['font.family'] = ['WenQuanYi Zen Hei', 'DejaVu Sans', 'sans-serif']
plt.rcParams['font.size'] = 10
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['axes.unicode_minus'] = False

OUTPUT_DIR = '/mnt/openclaw/.openclaw/workspace/'
WIDTH_PX = 1335
DPI = 200
WIDTH_IN = WIDTH_PX / DPI
HEIGHT_IN = WIDTH_IN * 0.55  # aspect ratio

# Load data
with open(os.path.join(OUTPUT_DIR, 'weekly_data_0531_0606.json'), 'r') as f:
    data = json.load(f)


def save_chart(fig, filename):
    filepath = os.path.join(OUTPUT_DIR, filename)
    # Save with tight layout then resize to exact 1335px width
    fig.savefig(filepath, dpi=DPI, format='jpeg', bbox_inches='tight',
                facecolor='white', edgecolor='none',
                pil_kwargs={'quality': 92})
    plt.close(fig)
    # Resize to exact width 1335px, maintain aspect ratio
    from PIL import Image
    img = Image.open(filepath)
    w, h = img.size
    if w != WIDTH_PX:
        new_h = int(h * WIDTH_PX / w)
        img = img.resize((WIDTH_PX, new_h), Image.LANCZOS)
        img.save(filepath, 'JPEG', quality=92)
    size = os.path.getsize(filepath)
    print(f"  ✓ {filename} saved ({size/1024:.1f} KB, {WIDTH_PX}x{img.size[1]}px)")


# ============================================================
# Chart 1: New Signing 新签进展
# ============================================================
def chart_new_signing():
    print("Generating Chart 1: New Signing...")
    ns = data['new_signing']
    categories = ['Must-have', 'Top-Tier', 'Mid-Tier']
    values = [ns['weekly_total_by_priority']['Must-have'],
              ns['weekly_total_by_priority']['Top-Tier'],
              ns['weekly_total_by_priority']['Mid-Tier']]
    
    # Colors: all are weekly actual data, use blue tones
    colors = ['#1f77b4', '#2ca02c', '#ff7f0e']
    
    fig, ax = plt.subplots(figsize=(WIDTH_IN, HEIGHT_IN))
    
    bars = ax.bar(categories, values, color=colors, width=0.5, edgecolor='white', linewidth=0.5)
    
    # Add value labels on bars
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                str(val), ha='center', va='bottom', fontweight='bold', fontsize=12)
    
    # Monthly target reference lines (annotated)
    ax.axhline(y=306, color='red', linestyle='--', linewidth=1.2, alpha=0.7)
    ax.text(2.35, 306, 'Monthly Target\nTop+MH=306', fontsize=8, color='red',
            va='center', ha='left')
    
    ax.axhline(y=224, color='#e377c2', linestyle='--', linewidth=1.2, alpha=0.7)
    ax.text(2.35, 224, 'Monthly Target\nMid=224', fontsize=8, color='#e377c2',
            va='center', ha='left')
    
    # Total annotation
    total = sum(values)
    ax.set_title(f'New Signing 新签进展 (Week 5.31-6.6)\nWeekly Total: {total}',
                 fontweight='bold', pad=15)
    ax.set_ylabel('Number of New Signings')
    ax.set_ylim(0, max(350, max(values) * 1.3))
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    # Legend
    legend_elements = [mpatches.Patch(facecolor=c, label=cat) 
                       for c, cat in zip(colors, categories)]
    ax.legend(handles=legend_elements, loc='upper left', framealpha=0.9)
    
    fig.tight_layout()
    save_chart(fig, 'chart_new_signing_0531_0606.jpg')


# ============================================================
# Chart 2: Operating Rate 营业率
# ============================================================
def chart_operating_rate():
    print("Generating Chart 2: Operating Rate...")
    or_data = data['operating_rate']['daily_detail']
    
    dates = sorted(set(d['date'] for d in or_data))
    date_labels = [f"{d[4:6]}/{d[6:8]}" for d in dates]
    
    priorities = ['Must-have', 'Top-Tier', 'Mid-Tier']
    series = {p: [] for p in priorities}
    
    for date in dates:
        for item in or_data:
            if item['date'] == date:
                series[item['priority']].append(item['operating_rate'] * 100)
    
    fig, ax = plt.subplots(figsize=(WIDTH_IN, HEIGHT_IN))
    
    # Colors: MH green (above 60%), Top/Mid red (below 60%)
    colors = {'Must-have': '#2ca02c', 'Top-Tier': '#d62728', 'Mid-Tier': '#ff4444'}
    markers = {'Must-have': 'o', 'Top-Tier': 's', 'Mid-Tier': '^'}
    
    for p in priorities:
        ax.plot(date_labels, series[p], color=colors[p], marker=markers[p],
                linewidth=2, markersize=6, label=f'{p} (avg {np.mean(series[p]):.1f}%)')
    
    # Target line at 60%
    ax.axhline(y=60, color='red', linestyle='--', linewidth=1.5, alpha=0.8)
    ax.text(len(dates)-0.5, 61, 'Target 60%', fontsize=9, color='red',
            ha='right', va='bottom', fontweight='bold')
    
    ax.set_title('Operating Rate 营业率 (Week 5.31-6.6)', fontweight='bold', pad=15)
    ax.set_ylabel('Operating Rate (%)')
    ax.set_xlabel('Date')
    ax.set_ylim(20, 95)
    ax.legend(loc='upper left', framealpha=0.9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.grid(axis='x', alpha=0.2, linestyle=':')
    
    fig.tight_layout()
    save_chart(fig, 'chart_operating_rate_0531_0606.jpg')


# ============================================================
# Chart 3: Deep Discount Coverage DD覆盖率
# ============================================================
def chart_dd_coverage():
    print("Generating Chart 3: Deep Discount Coverage...")
    dd_data = data['deep_discount']['daily_detail']
    
    dates = [d['date'] for d in dd_data]
    date_labels = [f"{d[4:6]}/{d[6:8]}" for d in dates]
    
    dd_1plus = [d['1+_active_pool_dd_coverage'] * 100 for d in dd_data]
    dd_3plus = [d['3+_active_pool_dd_coverage'] * 100 for d in dd_data]
    
    fig, ax = plt.subplots(figsize=(WIDTH_IN, HEIGHT_IN))
    
    # 1+DD red (below 65% target), 3+DD green (above 30% target)
    ax.plot(date_labels, dd_1plus, color='#d62728', marker='o', linewidth=2.5,
            markersize=7, label=f'1+ DD (avg {np.mean(dd_1plus):.1f}%)')
    ax.plot(date_labels, dd_3plus, color='#2ca02c', marker='s', linewidth=2.5,
            markersize=7, label=f'3+ DD (avg {np.mean(dd_3plus):.1f}%)')
    
    # Target lines
    ax.axhline(y=65, color='red', linestyle='--', linewidth=1.5, alpha=0.8)
    ax.text(len(dates)-0.5, 65.5, '1+DD Target 65%', fontsize=9, color='red',
            ha='right', va='bottom', fontweight='bold')
    
    ax.axhline(y=30, color='#1f77b4', linestyle='--', linewidth=1.5, alpha=0.8)
    ax.text(len(dates)-0.5, 30.5, '3+DD Target 30%', fontsize=9, color='#1f77b4',
            ha='right', va='bottom', fontweight='bold')
    
    ax.set_title('Deep Discount Coverage DD覆盖率 (Week 5.31-6.6)', fontweight='bold', pad=15)
    ax.set_ylabel('Coverage Rate (%)')
    ax.set_xlabel('Date')
    ax.set_ylim(20, 75)
    ax.legend(loc='upper right', framealpha=0.9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.grid(axis='x', alpha=0.2, linestyle=':')
    
    # Add value annotations
    for i, (v1, v3) in enumerate(zip(dd_1plus, dd_3plus)):
        if i == 0 or i == len(dd_1plus)-1:
            ax.annotate(f'{v1:.1f}%', (date_labels[i], v1), 
                       textcoords="offset points", xytext=(0, 10),
                       ha='center', fontsize=8, color='#d62728')
            ax.annotate(f'{v3:.1f}%', (date_labels[i], v3),
                       textcoords="offset points", xytext=(0, -15),
                       ha='center', fontsize=8, color='#2ca02c')
    
    fig.tight_layout()
    save_chart(fig, 'chart_dd_coverage_0531_0606.jpg')


# ============================================================
# Chart 4: Promotion Coverage 促销覆盖率 (by Metro cities)
# ============================================================
def chart_promotion():
    print("Generating Chart 4: Promotion Coverage...")
    promo = data['promotion_coverage']
    
    # Metro 3 cities
    cities_data = {
        'NE': promo['Metropolitan Region - Northeast São Paulo Metropolitan'],
        'Western': promo['Metropolitan Region - Western São Paulo Metropolitan'],
        'Santos': promo['Metropolitan Region - Santos City'],
    }
    
    city_labels = ['NE', 'Western', 'Santos']
    metrics = ['avg_promo_coverage', 'avg_manzhe_coverage', 'avg_jianpei_coverage']
    metric_labels = ['Promo 促销', 'Manzhe 满折', 'Jianpei 减配']
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    
    x = np.arange(len(city_labels))
    width = 0.25
    
    fig, ax = plt.subplots(figsize=(WIDTH_IN, HEIGHT_IN))
    
    for i, (metric, label, color) in enumerate(zip(metrics, metric_labels, colors)):
        values = []
        for city_key in ['NE', 'Western', 'Santos']:
            val = cities_data[city_key][metric]
            values.append(val * 100 if val is not None else 0)
        
        bars = ax.bar(x + (i - 1) * width, values, width, label=label,
                      color=color, edgecolor='white', linewidth=0.5)
        
        # Value labels
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.8,
                    f'{val:.1f}%', ha='center', va='bottom', fontsize=8, fontweight='bold')
    
    ax.set_title('Promotion Coverage 促销覆盖率 (Week 5.31-6.6)', fontweight='bold', pad=15)
    ax.set_ylabel('Coverage Rate (%)')
    ax.set_xticks(x)
    ax.set_xticklabels(city_labels, fontsize=11)
    ax.set_ylim(0, 110)
    ax.legend(loc='upper right', framealpha=0.9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    fig.tight_layout()
    save_chart(fig, 'chart_promotion_0531_0606.jpg')


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    print("=" * 60)
    print("SP Metropolitan Weekly Charts Generator")
    print("Period: BRT 2026-05-31 ~ 2026-06-06")
    print("=" * 60)
    
    chart_new_signing()
    chart_operating_rate()
    chart_dd_coverage()
    chart_promotion()
    
    print("\n" + "=" * 60)
    print("All 4 charts generated successfully!")
    print("=" * 60)
    
    # Verify files
    files = [
        'chart_new_signing_0531_0606.jpg',
        'chart_operating_rate_0531_0606.jpg',
        'chart_dd_coverage_0531_0606.jpg',
        'chart_promotion_0531_0606.jpg',
    ]
    
    print("\nFile verification:")
    all_ok = True
    for f in files:
        path = os.path.join(OUTPUT_DIR, f)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  ✓ {f}: {size/1024:.1f} KB")
            if size < 10000:
                print(f"    ⚠️ WARNING: File seems too small!")
                all_ok = False
        else:
            print(f"  ✗ {f}: MISSING!")
            all_ok = False
    
    if all_ok:
        print("\n✅ All charts OK!")
    else:
        print("\n❌ Some charts have issues!")
