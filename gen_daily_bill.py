#!/usr/bin/env python3
"""汪汪队每日协作账单生成器"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import json
from datetime import datetime, timezone, timedelta
import os

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 读取 data.json
hq_dir = '/mnt/openclaw/.openclaw/workspace/wangwang-hq'
data_path = os.path.join(hq_dir, 'data.json')
with open(data_path) as f:
    data = json.load(f)

# BRT 日期
brt = datetime.now(timezone(timedelta(hours=-3)))
date_str = brt.strftime('%Y-%m-%d')

# 统计任务
tasks = data.get('tasks', [])
total = len(tasks)
running = sum(1 for t in tasks if t.get('status') == 'running')
error = sum(1 for t in tasks if t.get('status') == 'error')
success_rate = running / total * 100 if total > 0 else 0
time_saved = running * 0.5  # 每个任务节省30分钟

# 创建画布
fig, ax = plt.subplots(figsize=(10, 14), facecolor='#faf8ff')
ax.set_xlim(0, 10)
ax.set_ylim(0, 14)
ax.axis('off')

# 标题
ax.text(5, 13.3, '🐾 汪汪队每日协作账单', fontsize=28, fontweight='bold',
        ha='center', va='center', color='#4c1d95')
ax.text(5, 12.7, f'Daily Collaboration Bill · BRT {date_str}', fontsize=14,
        ha='center', va='center', color='#6b7280')

# 顶部装饰线
ax.plot([1, 9], [12.4, 12.4], color='#8b5cf6', linewidth=2, alpha=0.3)

# 统计卡片
cards = [
    (f'{total}', '总任务', '#8b5cf6'),
    (f'{running}', '运行中', '#10b981'),
    (f'{error}', '异常', '#ef4444'),
    (f'{success_rate:.0f}%', '成功率', '#3b82f6'),
    (f'{time_saved:.1f}h', '节省时间', '#f59e0b'),
]

for i, (val, label, color) in enumerate(cards):
    x = 1 + i * 1.8
    rect = FancyBboxPatch((x-0.7, 11.2), 1.4, 1.0, boxstyle="round,pad=0.05",
                          facecolor=color, edgecolor='none', alpha=0.12)
    ax.add_patch(rect)
    ax.text(x, 11.8, val, fontsize=20, fontweight='bold', ha='center', va='center', color=color)
    ax.text(x, 11.45, label, fontsize=10, ha='center', va='center', color='#6b7280')

# 任务表格标题
ax.text(0.5, 10.4, '📋 任务运行状态', fontsize=16, fontweight='bold', color='#374151')

# 表头
y = 9.9
ax.add_patch(FancyBboxPatch((0.3, y-0.25), 9.4, 0.5, boxstyle="round,pad=0.02",
              facecolor='#f3f4f6', edgecolor='none'))
ax.text(0.6, y, 'ID', fontsize=11, fontweight='bold', color='#6b7280', va='center')
ax.text(2.2, y, '任务名称', fontsize=11, fontweight='bold', color='#6b7280', va='center')
ax.text(6.2, y, 'Agent', fontsize=11, fontweight='bold', color='#6b7280', va='center')
ax.text(8.2, y, '状态', fontsize=11, fontweight='bold', color='#6b7280', va='center')

# 数据行
for idx, t in enumerate(tasks):
    y = 9.4 - idx * 0.48
    status = t.get('status', 'unknown')
    color = '#10b981' if status == 'running' else '#ef4444' if status == 'error' else '#6b7280'
    status_text = '● 正常' if status == 'running' else '● 异常' if status == 'error' else f'○ {status}'
    bg_color = '#f9fafb' if idx % 2 == 0 else '#ffffff'

    ax.add_patch(FancyBboxPatch((0.3, y-0.22), 9.4, 0.44, boxstyle="round,pad=0.02",
                  facecolor=bg_color, edgecolor='#e5e7eb', linewidth=0.5))

    ax.text(0.6, y, t.get('id', ''), fontsize=10, color='#374151', va='center', fontfamily='monospace')
    ax.text(2.2, y, t.get('name', ''), fontsize=10, color='#374151', va='center')
    ax.text(6.2, y, t.get('agent', ''), fontsize=10, color='#374151', va='center')
    ax.text(8.2, y, status_text, fontsize=10, color=color, va='center', fontweight='bold')

# 底部信息
bottom_y = 9.4 - len(tasks) * 0.48 - 0.5
ax.text(5, bottom_y, f'🏠 汪汪队指挥中心 · wangwang-hq · {data.get("updated", "")[:10]}',
        fontsize=11, ha='center', va='center', color='#9ca3af')
ax.text(5, bottom_y - 0.3, '自动化任务每日统计 · 数据来自 HQ data.json',
        fontsize=9, ha='center', va='center', color='#d1d5db')

plt.tight_layout()
output = os.path.join(hq_dir, f'daily_bill_{date_str}.png')
plt.savefig(output, dpi=150, bbox_inches='tight', facecolor='#faf8ff', pad_inches=0.3)
print(f'✅ Bill saved: {output}')
