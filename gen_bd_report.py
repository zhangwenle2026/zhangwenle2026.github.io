#!/usr/bin/env python3
"""BD Deep Discount Daily Report Generator  [bd-v2.0-final]
Usage: python3 gen_bd_report.py <xlsx_path>
Input:  Must Have YYYY-MM-DD.xlsx  +  Top&Mid YYYY-MM-DD.xlsx  (same date, passed as first arg)
Output: /tmp/files/bd_report_output.jpg  +  CDN URL

═══ 清晰度定版标准（2026-04-14 文乐确认）══════════════════════════
  截图方式：browser-level CDP WebSocket
    - Target.createTarget(about:blank) → 独立 tab 不受 BI 干扰
    - Target.attachToTarget(flatten=True) → 获取 sessionId
    - 所有 CDP 指令带 sessionId，截图后 Target.closeTarget 清理
  图片规格：
    - body CSS width: 1800px
    - deviceScaleFactor: 1（DPR=1，不缩放，CSS 1px = 截图 1px）
    - IMG_WIDTH: 1560px JPEG q=62 + UnsharpMask(r=1.2,120%) 输出（<1MB）
    - CHUNK_H: 2000px（分段截图防超时）
    - viewport: 1800px × chunk_h（每段单独设置）
  字体规范（保证清晰度）：
    - BD 名字 .bd-name:     font-weight:700, color:#1f1f2e（深色加粗）
    - BDM 名字 .bdm-label:  font-weight:800, color:#4c1d95（深紫加粗）
    - CM 汇总 .cm-total-row: font-weight:700
    - 数值 .cv:             font-weight:900（最粗，高对比度）
    - 进度条旁百分比 .kpi-bar-pct: font-weight:800
    - DoD/WoW 胶囊 .chg-badge:   font-weight:900
  布局规范：
    - 主题：紫色渐变 #3b0764→#4c1d95→#5b21b6
    - 两列：Must Have + Top & Mid，grid 1fr 1fr
    - CM → BDM → BD 分组，MH 3+DD 降序
    - 空 DoD/WoW 行：.chg-row:has(.chg-nil){display:none} CSS 隐藏
════════════════════════════════════════════════════════════════════
"""

import sys, os, json, time, asyncio, math, base64
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import openpyxl
from PIL import Image
import io

XLSX_PATH  = sys.argv[1] if len(sys.argv) > 1 else '/tmp/files/bd_latest.xlsx'
OUT_HTML   = '/tmp/files/bd_report_v18_gen.html'
OUT_IMG    = '/tmp/files/bd_report_output.jpg'
CDP_URL    = 'http://localhost:9222'
IMG_WIDTH  = 1560
JPEG_Q     = 62
CHUNK_H    = 2000

TGT_MH3 = 0.30
TGT_MH1 = 0.65
TGT_TM3 = 0.30
TGT_TM1 = 0.50

CM_MAP = {
    'danielalbuquerque': {'name': 'Daniel',   'region': 'Northeast', 'color': '#f97316'},
    'fengmenglong':      {'name': 'Feng',     'region': 'Western',   'color': '#8b5cf6'},
    'jaylin':            {'name': 'Jaylin',   'region': 'Santos',    'color': '#06b6d4'},
    'tianjie':           {'name': 'Tian Jie', 'region': 'Southern',  'color': '#10b981'},
}

# ─── Excel parsing ────────────────────────────────────────────
def load_data(xlsx_path):
    wb = openpyxl.load_workbook(xlsx_path)
    sheet_name = None
    for c in ['Performance (BD Level)', '0']:
        if c in wb.sheetnames:
            sheet_name = c
            break
    if sheet_name is None:
        sheet_name = wb.sheetnames[0]
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))

    header_idx = 0
    for idx, row in enumerate(rows):
        if row and str(row[0]).lower() in ('rm','cm','bd name','bd_name'):
            header_idx = idx
            break
    header = [str(h).lower().strip() if h else '' for h in rows[header_idx]]

    ci_cm  = next((i for i,h in enumerate(header) if h=='cm'), 1)
    ci_bdm = next((i for i,h in enumerate(header) if h=='bdm'), 2)
    ci_bd  = next((i for i,h in enumerate(header) if h in ('bd','bd name','bd_name')), 3)

    # Find metric columns
    ci = {}
    patterns = {
        'mh1_v': ['1+dd_over15_coverage','mh 1+dd_val','mh1_val'],
        'mh1_dod': ['1+dd_over15.*dod','mh1.*dod'],
        'mh1_wow': ['1+dd_over15.*wow','mh1.*wow'],
        'mh3_v': ['3+dd_over15_coverage','mh 3+dd_val','mh3_val'],
        'mh3_dod': ['3+dd_over15.*dod','mh3.*dod'],
        'mh3_wow': ['3+dd_over15.*wow','mh3.*wow'],
        'tm1_v': ['1+dd_over40_coverage','tm 1+dd_val','tm1_val'],
        'tm1_dod': ['1+dd_over40.*dod','tm1.*dod'],
        'tm1_wow': ['1+dd_over40.*wow','tm1.*wow'],
        'tm3_v': ['3+dd_over40_coverage','tm 3+dd_val','tm3_val'],
        'tm3_dod': ['3+dd_over40.*dod','tm3.*dod'],
        'tm3_wow': ['3+dd_over40.*wow','tm3.*wow'],
    }
    import re
    for key, pats in patterns.items():
        for i, h in enumerate(header):
            for p in pats:
                if re.search(p, h):
                    ci.setdefault(key, i)
                    break
    # hard fallback
    defaults = {
        'mh1_v':5,'mh1_dod':6,'mh1_wow':7,
        'mh3_v':9,'mh3_dod':10,'mh3_wow':11,
        'tm1_v':13,'tm1_dod':14,'tm1_wow':15,
        'tm3_v':17,'tm3_dod':18,'tm3_wow':19,
    }
    for k,v in defaults.items():
        ci.setdefault(k,v)

    data = []
    for row in rows[header_idx+1:]:
        if not row: continue
        cm = str(row[ci_cm]).strip() if row[ci_cm] else None
        if not cm or cm in ('Total','-','cm','CM'): continue
        bdm = str(row[ci_bdm]).strip() if row[ci_bdm] else ''
        bd  = str(row[ci_bd]).strip()  if row[ci_bd]  else None
        if not bd: continue
        def g(k):
            idx = ci[k]
            v = row[idx] if idx < len(row) else None
            try: return float(v) if v not in (None,'') else 0.0
            except: return 0.0
        data.append({
            'cm':cm,'bdm':bdm,'bd':bd,
            'mh1':g('mh1_v'),'mh1_dod':g('mh1_dod'),'mh1_wow':g('mh1_wow'),
            'mh3':g('mh3_v'),'mh3_dod':g('mh3_dod'),'mh3_wow':g('mh3_wow'),
            'tm1':g('tm1_v'),'tm1_dod':g('tm1_dod'),'tm1_wow':g('tm1_wow'),
            'tm3':g('tm3_v'),'tm3_dod':g('tm3_dod'),'tm3_wow':g('tm3_wow'),
        })
    return data

# ─── HTML helpers ─────────────────────────────────────────────
def fmt_name(s):
    if not s: return ''
    return ' '.join(w.capitalize() for w in str(s).split())

def chg_badge(val):
    if val == 0 or val is None or abs(val) < 0.00005:
        return '<span class="chg-nil">—</span>'
    pct = val * 100
    abs_pct = abs(pct)
    sign = '+' if pct > 0 else ''
    intensity = min(abs_pct / 10.0, 1.0)
    # 增长 = 红色荧光（越多越深红），下降 = 绿色荧光（越多越深绿）
    if pct > 0:
        # 红色渐变：浅粉 → 深红
        r1 = 255; g1 = int(200 - 150*intensity); b1 = int(200 - 180*intensity)
        r2 = 255; g2 = int(80  -  80*intensity);  b2 = int(80  -  80*intensity)
        glow = f'rgba(220,0,0,1.0)'
        bg = f'background:linear-gradient(135deg,rgb({r1},{int(g1)},{int(b1)}),rgb({r2},{int(g2)},{int(b2)}))'
        txt_color = '#fff'
        return (f'<span class="chg-badge" style="{bg};color:{txt_color};font-weight:900;'
                f'text-shadow:0 1px 3px rgba(0,0,0,0.5);box-shadow:0 0 8px {glow},0 2px 4px rgba(0,0,0,0.2);">{sign}{pct:.1f}%</span>')
    else:
        # 绿色渐变：浅绿 → 深绿
        r1 = int(200 - 180*intensity); g1 = 255; b1 = int(200 - 150*intensity)
        r2 = int(0   +  20*(1-intensity)); g2 = int(200 -  80*intensity); b2 = int(80 - 60*intensity)
        glow = f'rgba(0,180,0,1.0)'
        bg = f'background:linear-gradient(135deg,rgb({int(r1)},{int(g1)},{int(b1)}),rgb({int(r2)},{int(g2)},{int(b2)}))'
        txt_color = '#fff'
        return (f'<span class="chg-badge" style="{bg};color:{txt_color};font-weight:900;'
                f'text-shadow:0 1px 3px rgba(0,0,0,0.5);box-shadow:0 0 8px {glow},0 2px 4px rgba(0,0,0,0.2);">{sign}{pct:.1f}%</span>')

def chg_cell(dod, wow):
    return (f'<div class="chg-cell">'
            f'<div class="chg-row"><span class="chg-lbl">DoD</span>{chg_badge(dod)}</div>'
            f'<div class="chg-row"><span class="chg-lbl">WoW</span>{chg_badge(wow)}</div>'
            f'</div>')

def cell_wrap(val, tgt, color):
    fill = min(val/tgt*100, 150) if tgt>0 else 0
    tgt_l = 100.0/1.5  # =66.7%
    return (f'<div class="cell-wrap">'
            f'<div class="cv">{val*100:.1f}%</div>'
            f'<div class="cbar-o">'
            f'<div class="cbar-i" style="width:{fill:.1f}%;background:{color}"></div>'
            f'<div class="cbar-tgt" style="left:{tgt_l:.1f}%"></div>'
            f'</div>'
            f'</div>')

def kpi_card(icon, label, actual, target, dod, wow, is_star=False):
    pct = actual/target*100 if target>0 else 0
    pc = min(pct,100)
    ok = pct >= 85
    star = ' ★' if is_star else ''
    badge_cls = 'kpi-badge-ok' if ok else 'kpi-badge-ng'
    badge_ico = '✅' if ok else '⚠️'
    return f'''<div class="kpi-card">
  <div class="kpi-top"><span class="kpi-icon">{icon}</span><div class="kpi-label">{label}{star}</div>
  <div class="kpi-badge {badge_cls}">{badge_ico} {pct:.0f}%</div></div>
  <div class="kpi-nums"><div class="kpi-actual">{actual*100:.1f}%</div>
  <div class="kpi-tgt">→ {target*100:.0f}%</div></div>
  <div class="kpi-bar-wrap"><div class="kpi-bar-track"><div class="kpi-bar-fill" style="width:{pc:.1f}%"></div></div>
  <div class="kpi-bar-pct">{pct:.0f}%</div></div>
  <div class="kpi-chg"><span class="cl">DoD</span>{chg_badge(dod)}&nbsp;&nbsp;<span class="cl">WoW</span>{chg_badge(wow)}</div>
</div>'''

def rs_cell(cm_key, bds, info):
    if not bds: return ''
    n = len(bds)
    mh3 = sum(b['mh3'] for b in bds)/n; mh1 = sum(b['mh1'] for b in bds)/n
    tm3 = sum(b['tm3'] for b in bds)/n; tm1 = sum(b['tm1'] for b in bds)/n
    mh3_dod=sum(b['mh3_dod'] for b in bds)/n; tm3_dod=sum(b['tm3_dod'] for b in bds)/n
    mh1_dod=sum(b['mh1_dod'] for b in bds)/n; tm1_dod=sum(b['tm1_dod'] for b in bds)/n
    mh3_wow=sum(b['mh3_wow'] for b in bds)/n; tm3_wow=sum(b['tm3_wow'] for b in bds)/n
    mh1_wow=sum(b['mh1_wow'] for b in bds)/n; tm1_wow=sum(b['tm1_wow'] for b in bds)/n

    TARGETS = {'mh3':0.30,'mh1':0.65,'tm3':0.30,'tm1':0.50}

    def rchg(v):
        # Region Summary 专用大号胶囊：把 chg-badge → rs-chg-badge
        if abs(v) < 0.00005:
            return '<span class="chg-nil">—</span>'
        badge = chg_badge(v)
        return badge.replace('class="chg-badge"', 'class="rs-chg-badge"')

    def rs_metric(label, val, tgt, dod, wow, is_star=False):
        pct   = min(val/tgt, 1.0)*100
        gap   = (val - tgt)*100          # negative = behind target
        star  = ' ★' if is_star else ''
        gap_color = '#16a34a' if gap >= 0 else ('#dc2626' if gap < -15 else '#d97706')
        gap_txt = f'+{gap:.1f}pp' if gap >= 0 else f'{gap:.1f}pp'
        return f'''<div class="rs-metric">
  <div class="rs-metric-top">
    <span class="rs-metric-lbl">{label}{star}</span>
    <span class="rs-metric-val">{val*100:.1f}%</span>
    <span class="rs-metric-tgt">/ {tgt*100:.0f}%</span>
    <span class="rs-metric-gap" style="color:{gap_color}">{gap_txt}</span>
  </div>
  <div class="rs-bar-track"><div class="rs-bar-fill" style="width:{pct:.1f}%;background:{info['color']}"></div></div>
  <div class="rs-chg-row"><span class="rs-chg-sep">DoD</span>{rchg(dod)}&nbsp;&nbsp;<span class="rs-chg-sep">WoW</span>{rchg(wow)}</div>
</div>'''

    return f'''<div class="rs-cell" style="border-left:4px solid {info['color']}">
  <div class="rs-city"><span class="cm-dot" style="background:{info['color']}"></span>{info['region']} · {info['name']}</div>
  {rs_metric('MH 3+DD', mh3, TARGETS['mh3'], mh3_dod, mh3_wow, is_star=True)}
  {rs_metric('MH 1+DD', mh1, TARGETS['mh1'], mh1_dod, mh1_wow)}
  {rs_metric('T&M 3+DD', tm3, TARGETS['tm3'], tm3_dod, tm3_wow, is_star=True)}
  {rs_metric('T&M 1+DD', tm1, TARGETS['tm1'], tm1_dod, tm1_wow)}
</div>'''

def cm_card(cm_key, bds, info):
    bdm_groups = defaultdict(list)
    for b in bds:
        bdm_groups[b['bdm']].append(b)
    bdm_sorted = sorted(bdm_groups.items(),
        key=lambda kv: sum(b['mh3'] for b in kv[1])/len(kv[1]), reverse=True)

    n = len(bds)
    def avg(key): return sum(b[key] for b in bds)/n

    def cm_total_row(side):
        if side == 'mh':
            return (f'<tr class="cm-total-row"><td><strong>CM Total</strong></td>'
                    f'<td>{cell_wrap(avg("mh3"),TGT_MH3,"#a855f7")}</td>'
                    f'<td>{chg_cell(avg("mh3_dod"),avg("mh3_wow"))}</td>'
                    f'<td>{cell_wrap(avg("mh1"),TGT_MH1,"#c084fc")}</td>'
                    f'<td>{chg_cell(avg("mh1_dod"),avg("mh1_wow"))}</td></tr>')
        else:
            return (f'<tr class="cm-total-row"><td><strong>CM Total</strong></td>'
                    f'<td>{cell_wrap(avg("tm3"),TGT_TM3,"#a855f7")}</td>'
                    f'<td>{chg_cell(avg("tm3_dod"),avg("tm3_wow"))}</td>'
                    f'<td>{cell_wrap(avg("tm1"),TGT_TM1,"#c084fc")}</td>'
                    f'<td>{chg_cell(avg("tm1_dod"),avg("tm1_wow"))}</td></tr>')

    mh_rows = cm_total_row('mh')
    tm_rows = cm_total_row('tm')

    for bdm_name, bdm_bds in bdm_sorted:
        nn = len(bdm_bds)
        def bavg(key, lst): return sum(b[key] for b in lst)/len(lst)
        lbl = f'<td><span class="bdm-label">{bdm_name}</span> <span class="n-badge">{nn}BD</span></td>'
        mh_rows += (f'<tr class="bdm-row">{lbl}'
                    f'<td>{cell_wrap(bavg("mh3",bdm_bds),TGT_MH3,"#a855f7")}</td>'
                    f'<td>{chg_cell(bavg("mh3_dod",bdm_bds),bavg("mh3_wow",bdm_bds))}</td>'
                    f'<td>{cell_wrap(bavg("mh1",bdm_bds),TGT_MH1,"#c084fc")}</td>'
                    f'<td>{chg_cell(bavg("mh1_dod",bdm_bds),bavg("mh1_wow",bdm_bds))}</td></tr>')
        tm_rows += (f'<tr class="bdm-row">{lbl}'
                    f'<td>{cell_wrap(bavg("tm3",bdm_bds),TGT_TM3,"#a855f7")}</td>'
                    f'<td>{chg_cell(bavg("tm3_dod",bdm_bds),bavg("tm3_wow",bdm_bds))}</td>'
                    f'<td>{cell_wrap(bavg("tm1",bdm_bds),TGT_TM1,"#c084fc")}</td>'
                    f'<td>{chg_cell(bavg("tm1_dod",bdm_bds),bavg("tm1_wow",bdm_bds))}</td></tr>')
        for b in sorted(bdm_bds, key=lambda x: x['mh3'], reverse=True):
            nm = f'<td class="bd-name">{fmt_name(b["bd"])}</td>'
            mh_rows += (f'<tr class="bd-row">{nm}'
                        f'<td>{cell_wrap(b["mh3"],TGT_MH3,"#a855f7")}</td>'
                        f'<td>{chg_cell(b["mh3_dod"],b["mh3_wow"])}</td>'
                        f'<td>{cell_wrap(b["mh1"],TGT_MH1,"#c084fc")}</td>'
                        f'<td>{chg_cell(b["mh1_dod"],b["mh1_wow"])}</td></tr>')
            tm_rows += (f'<tr class="bd-row">{nm}'
                        f'<td>{cell_wrap(b["tm3"],TGT_TM3,"#a855f7")}</td>'
                        f'<td>{chg_cell(b["tm3_dod"],b["tm3_wow"])}</td>'
                        f'<td>{cell_wrap(b["tm1"],TGT_TM1,"#c084fc")}</td>'
                        f'<td>{chg_cell(b["tm1_dod"],b["tm1_wow"])}</td></tr>')

    return f'''<div class="card cm-card card-table">
  <div class="ct"><span class="cm-dot" style="background:{info['color']}"></span>{info['region']} · {info['name']} <small>({n} BDs)</small></div>
  <div class="two-col">
    <div>
      <div class="col-hdr col-mh">Must Have</div>
      <table><colgroup><col style="width:22%"><col style="width:16%"><col style="width:20%"><col style="width:16%"><col></colgroup><thead><tr><th>BD</th><th>3+DD</th><th>△</th><th>1+DD</th><th>△</th></tr></thead>
      <tbody>{mh_rows}</tbody></table>
    </div>
    <div>
      <div class="col-hdr col-tm">Top &amp; Mid</div>
      <table><colgroup><col style="width:22%"><col style="width:16%"><col style="width:20%"><col style="width:16%"><col></colgroup><thead><tr><th>BD</th><th>3+DD</th><th>△</th><th>1+DD</th><th>△</th></tr></thead>
      <tbody>{tm_rows}</tbody></table>
    </div>
  </div>
</div>'''

# ─── HTML full page ───────────────────────────────────────────
CSS = '''
*{box-sizing:border-box;margin:0;padding:0}::-webkit-scrollbar{display:none}
html,body{width:1800px;font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;background:#fff;color:#1a1a1a;font-size:15px;overflow-x:hidden}
body{padding:22px 0}
.hdr{background:linear-gradient(135deg,#3b0764,#4c1d95,#5b21b6);color:#fff;border-radius:14px;padding:24px 40px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 4px 20px rgba(59,7,100,.3)}
.hdr h1{font-size:42px;font-weight:900;white-space:nowrap;line-height:1.1}
.hdr h1 span{font-size:22px;font-weight:400;opacity:.8;margin-left:10px}
.hdr p{font-size:18px;opacity:.65;margin-top:6px}
.hdr-right{font-size:17px;opacity:.6;text-align:right;line-height:2.2;flex-shrink:0;margin-left:20px}
.kpi-row{display:flex;flex-wrap:nowrap;gap:10px;margin-bottom:12px}
.kpi-card{width:calc(25% - 8px);flex-shrink:0;background:linear-gradient(160deg,#2e1065,#3b0764,#4c1d95);border-radius:12px;padding:16px 18px 12px;box-shadow:0 3px 16px rgba(59,7,100,.3);position:relative;overflow:hidden}
.kpi-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#a855f7,#7c3aed)}
.kpi-top{display:flex;align-items:center;gap:7px;margin-bottom:6px}
.kpi-icon{font-size:18px}
.kpi-label{font-size:18px;font-weight:900;color:#fff;flex:1}
.kpi-badge{font-size:11px;font-weight:800;padding:2px 8px;border-radius:99px}
.kpi-badge-ok{background:#166534;color:#86efac}
.kpi-badge-ng{background:#991b1b;color:#fca5a5}
.kpi-nums{display:flex;align-items:baseline;gap:8px;margin-bottom:5px}
.kpi-actual{font-size:40px;font-weight:900;color:#fff;line-height:1;letter-spacing:-1px}
.kpi-tgt{font-size:22px;font-weight:700;color:#a78bfa}
.kpi-bar-wrap{display:flex;align-items:center;gap:8px;margin-bottom:5px;max-width:100%}
.kpi-bar-track{flex:1;background:rgba(255,255,255,.15);border-radius:99px;height:10px;overflow:hidden}
.kpi-bar-fill{height:100%;border-radius:99px;background:linear-gradient(90deg,#a855f7,#e879f9);box-shadow:0 0 8px rgba(168,85,247,.6)}
.kpi-bar-pct{font-size:13px;font-weight:800;color:#c4b5fd;min-width:38px;text-align:right}
.kpi-chg{font-size:12px;color:#c4b5fd;display:flex;align-items:center;gap:4px;flex-wrap:wrap}
.cl{font-size:11px;color:#a78bfa;font-weight:700;background:rgba(167,139,250,.2);padding:1px 5px;border-radius:3px}
.card{background:#fff;border-radius:12px;padding:16px 22px;margin-bottom:12px;box-shadow:0 2px 10px rgba(0,0,0,.07)}.cm-card{border-radius:0;box-shadow:none;border-top:1px solid #e9d5ff;padding-bottom:0}.card-table{padding-left:0;padding-right:0}.cm-card .ct{padding-left:16px;margin-bottom:8px}.card-table .ct{padding-left:22px}.card-table .col-hdr{margin-left:0;margin-right:0}
.ct{font-size:22px;font-weight:900;color:#3b0764;border-left:5px solid #5b21b6;padding-left:12px;margin-bottom:12px}
.ct small{font-size:15px;font-weight:400;color:#9e9e9e;margin-left:8px}
.two-col{display:grid;grid-template-columns:1fr 1fr;align-items:stretch;gap:10px}
.two-col>div{min-width:0;display:flex;flex-direction:column}
.two-col>div>table{flex:1;width:100%}
.col-hdr{font-size:17px;font-weight:800;padding:7px 14px;border-radius:6px;margin-bottom:7px}
.col-mh{background:#dbeafe;color:#1d4ed8}
.col-tm{background:#fef3c7;color:#b45309}
table{width:100%;border-collapse:collapse;table-layout:fixed}
th{font-size:11px;font-weight:800;padding:4px 4px;color:#4c1d95;border-bottom:2px solid #e9d5ff;text-align:left;white-space:nowrap;overflow:hidden}
td{padding:2px 4px;border-bottom:1px solid #f5f3ff;vertical-align:middle;overflow:hidden}td:last-child{padding-right:0;text-align:right}
tr:last-child td{border-bottom:none}
.cell-wrap{display:flex;flex-direction:row;align-items:center;gap:4px;width:100%}
.cv{font-size:15px;font-weight:900;white-space:nowrap;flex-shrink:0}
.cbar-o{position:relative;background:#e9d5ff;border-radius:99px;height:5px;overflow:hidden;flex:1;min-width:20px;margin:0}
.cbar-i{height:100%;border-radius:99px}
.cbar-tgt{position:absolute;top:-3px;width:2px;height:13px;background:#7c3aed;border-radius:2px}
.chg-badge{display:inline-block;font-size:13px;font-weight:900;padding:2px 7px;border-radius:99px;white-space:nowrap;letter-spacing:0;line-height:1.4}
.rs-chg-badge{display:inline-block;font-size:20px;font-weight:900;padding:4px 12px;border-radius:99px;white-space:nowrap;letter-spacing:0;line-height:1.5;border:2px solid rgba(0,0,0,0.15)}
.chg-nil{font-size:12px;color:#9ca3af}
.chg-cell{display:flex;flex-direction:row;flex-wrap:nowrap;gap:4px;align-items:center;justify-content:flex-end}
.chg-row{display:flex;align-items:center;gap:3px;margin-bottom:1px;line-height:1}
.chg-row:last-child{margin-bottom:0}
.chg-lbl{font-size:11px;font-weight:900;color:#7c3aed;background:#ede9fe;padding:1px 5px;border-radius:3px;flex-shrink:0;min-width:26px;text-align:center}
.chg-row:has(.chg-nil){display:none}
.cm-total-row td{background:#faf5ff;font-weight:700}
.bdm-row td{background:#f8f4fe}
.bdm-label{font-weight:800;font-size:13px;color:#4c1d95}
.n-badge{font-size:10px;background:#e9d5ff;color:#4c1d95;padding:1px 5px;border-radius:99px;font-weight:600}
.bd-name{font-size:13px;font-weight:700;color:#1f1f2e;padding-left:14px}
.cm-dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:5px;vertical-align:middle}
.region-summary{background:#fff;border-radius:12px;padding:16px 22px;margin-bottom:12px;box-shadow:0 2px 10px rgba(0,0,0,.07)}
.rs-grid{display:flex;flex-wrap:nowrap;gap:12px;margin-top:10px}
.rs-cell{flex:1;min-width:0;border-radius:8px;padding:13px 14px;background:#fff;border:1px solid #e9d5ff;box-shadow:0 2px 8px rgba(91,33,182,.08)}
.rs-city{font-size:13px;font-weight:900;color:#3b0764;margin-bottom:10px;display:flex;align-items:center;gap:6px}
.rs-metric{margin-bottom:6px}
.rs-metric-top{display:flex;align-items:baseline;gap:5px;flex-wrap:nowrap;margin-bottom:2px}
.rs-metric-lbl{font-size:11px;font-weight:800;color:#6b21a8;flex-shrink:0;min-width:62px}
.rs-metric-val{font-size:15px;font-weight:900;color:#1a1a1a;line-height:1}
.rs-metric-tgt{font-size:11px;color:#9ca3af;font-weight:500}
.rs-metric-gap{font-size:11px;font-weight:800;margin-left:auto;flex-shrink:0}
.rs-bar-track{height:4px;background:#ede9fe;border-radius:99px;margin-bottom:2px;overflow:hidden}
.rs-bar-fill{height:100%;border-radius:99px}
.rs-chg-row{display:flex;align-items:center;gap:3px;font-size:11px;flex-wrap:nowrap;line-height:1.2}
.rs-chg-sep{font-size:13px;font-weight:900;color:#7c3aed;background:#ede9fe;padding:2px 6px;border-radius:4px;line-height:1.4}
.rk{font-size:12px;color:#6b7280;flex-shrink:0}
.rv{font-size:14px;font-weight:900;color:#1a1a1a}
.rchg{flex-shrink:0}
.footer{text-align:center;font-size:14px;color:#a78bfa;margin-top:12px;padding-top:12px;border-top:1px solid #e9d5ff}
'''

def generate_html(data, date_str=None):
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        mdays = [0,31,28,29,30,31,30,31,31,30,31,30,31]
        if dt.year%4==0: mdays[2]=29
        dom = dt.day; dim = mdays[dt.month]
        ep = dom/dim*100
        date_disp = dt.strftime('%B %-d, %Y')
        day_info = f'Day {dom}/{dim} · {ep:.1f}% elapsed'
    except:
        date_disp = date_str; day_info = ''

    cm_bds = defaultdict(list)
    for b in data:
        if b['cm'] in CM_MAP:
            cm_bds[b['cm']].append(b)

    all_bds = [b for bds in cm_bds.values() for b in bds]
    n = len(all_bds)
    if n == 0: raise ValueError('No valid BD data')

    def avg(key): return sum(b[key] for b in all_bds)/n

    # KPI row
    kpi_html = (
        kpi_card('⭐','MH 3+DD', avg('mh3'), TGT_MH3, avg('mh3_dod'), avg('mh3_wow'), True) +
        kpi_card('🏹','MH 1+DD', avg('mh1'), TGT_MH1, avg('mh1_dod'), avg('mh1_wow'), False) +
        kpi_card('⭐','T&M 3+DD', avg('tm3'), TGT_TM3, avg('tm3_dod'), avg('tm3_wow'), True) +
        kpi_card('🎯','T&M 1+DD', avg('tm1'), TGT_TM1, avg('tm1_dod'), avg('tm1_wow'), False)
    )

    # Region summary
    rs_cells = ''.join(
        rs_cell(k, cm_bds.get(k,[]), v)
        for k,v in CM_MAP.items()
    )

    # CM cards
    cm_cards = ''.join(
        cm_card(k, cm_bds[k], v)
        for k,v in CM_MAP.items()
        if cm_bds.get(k)
    )

    total_bds = sum(len(v) for v in cm_bds.values())

    html = f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<title>BD Deep Discount · {date_str}</title>
<style>{CSS}</style></head>
<body>
<div class="hdr">
  <div>
    <h1>🏹 BD Deep Discount Dashboard <span>深折扣日报 BD Level</span></h1>
    <p>SP Metropolitan Region · {date_disp} &nbsp;({day_info})</p>
  </div>
  <div class="hdr-right">MH 3+DD → {TGT_MH3*100:.0f}%<br>MH 1+DD → {TGT_MH1*100:.0f}%<br>T&amp;M 3+DD → {TGT_TM3*100:.0f}%<br>T&amp;M 1+DD → {TGT_TM1*100:.0f}%</div>
</div>
<div class="kpi-row">{kpi_html}</div>
<div class="region-summary">
  <div class="ct">📊 Region Summary <small>CM Level</small></div>
  <div class="rs-grid">{rs_cells}</div>
</div>
{cm_cards}
<div class="footer">💜 BD Deep Discount Daily Report v18 · LingLing · SP Metropolitan · {date_str} · {total_bds} BDs</div>
</body></html>'''
    return html

# ─── CDP screenshot ───────────────────────────────────────────
async def cdp_screenshot_chunks(html_content, out_path, chunk_h=CHUNK_H):
    import websockets, json as _json
    import urllib.request

    # Use browser-level WS to create an isolated tab
    ver = _json.loads(urllib.request.urlopen(f'{CDP_URL}/json/version', timeout=10).read())
    browser_ws = ver['webSocketDebuggerUrl']
    print(f'CDP browser ws: {browser_ws}')

    async with websockets.connect(browser_ws, max_size=50*1024*1024) as bws:
        _bid = 0
        async def bsend(method, params=None):
            nonlocal _bid; _bid += 1
            await bws.send(_json.dumps({'id':_bid,'method':method,'params':params or {}}))
            while True:
                raw = await asyncio.wait_for(bws.recv(), timeout=30)
                r = _json.loads(raw)
                if r.get('id') == _bid: return r.get('result',{})
        
        # Create new blank target
        r = await bsend('Target.createTarget', {'url': 'about:blank'})
        target_id = r['targetId']
        # Attach to it with flatten=True (gives us a sessionId)
        r2 = await bsend('Target.attachToTarget', {'targetId': target_id, 'flatten': True})
        session_id = r2['sessionId']

        _id = 0
        async def send(method, params=None):
            nonlocal _id; _id += 1
            msg = {'id':_id,'method':method,'params':params or {},'sessionId':session_id}
            await bws.send(_json.dumps(msg))
            while True:
                raw = await asyncio.wait_for(bws.recv(), timeout=60)
                r = _json.loads(raw)
                if r.get('id') == _id and r.get('sessionId') == session_id:
                    return r.get('result',{})

        # Enable domains
        await send('Page.enable')
        await send('Runtime.enable')

        # Navigate to data URL
        b64 = base64.b64encode(html_content.encode()).decode()
        data_url = f'data:text/html;base64,{b64}'
        await send('Page.navigate', {'url': data_url})
        await asyncio.sleep(1.5)

        # Pre-set viewport so body width:100% expands to 1800px
        await send('Emulation.setDeviceMetricsOverride', {
            'width': 1800, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False
        })
        await asyncio.sleep(0.5)

        # Get page dimensions
        res = await send('Runtime.evaluate', {
            'expression': 'JSON.stringify({w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight})',
            'returnByValue': True
        })
        dims = _json.loads(res['result']['value'])
        pw, ph = dims['w'], dims['h']
        print(f'Page size: {pw}x{ph}')

        # Set viewport
        await send('Emulation.setDeviceMetricsOverride', {
            'width': pw, 'height': min(ph, 8000),
            'deviceScaleFactor': 1, 'mobile': False
        })
        await asyncio.sleep(0.5)

        # Screenshot in chunks
        chunks = []
        y = 0
        while y < ph:
            h = min(chunk_h, ph - y)
            await send('Emulation.setDeviceMetricsOverride', {
                'width': pw, 'height': h,
                'deviceScaleFactor': 1, 'mobile': False
            })
            await send('Runtime.evaluate', {
                'expression': f'window.scrollTo(0, {y})',
                'returnByValue': True
            })
            await asyncio.sleep(0.3)
            shot = await send('Page.captureScreenshot', {
                'format': 'png',
                'clip': {'x':0,'y':y,'width':pw,'height':h,'scale':1}
            })
            img_data = base64.b64decode(shot['data'])
            img = Image.open(io.BytesIO(img_data))
            chunks.append(img)
            print(f'  chunk y={y} h={h} img={img.size}')
            y += h

        # Close the temporary target
        try:
            await bsend('Target.closeTarget', {'targetId': target_id})
        except: pass

    # Stitch chunks
    total_h = sum(c.size[1] for c in chunks)
    full = Image.new('RGB', (chunks[0].size[0], total_h), (255,255,255))
    y_off = 0
    for c in chunks:
        full.paste(c.convert('RGB'), (0, y_off))
        y_off += c.size[1]
    print(f'Stitched: {full.size}')

    # Crop bottom whitespace
    import statistics
    width = full.size[0]
    orig_h = full.size[1]
    last_content_row = orig_h - 1
    for row_idx in range(orig_h - 1, -1, -1):
        row_pixels = list(full.crop((0, row_idx, width, row_idx+1)).getdata())
        vals = [p[0] if isinstance(p, tuple) else p for p in row_pixels]
        if statistics.stdev(vals) > 12 or min(vals) < 210:
            last_content_row = row_idx
            break
    crop_h = min(last_content_row + 60, orig_h)
    if crop_h < orig_h:
        full = full.crop((0, 0, width, crop_h))
        print(f'Cropped to: {full.size}')

    # Crop right whitespace
    import statistics as _stats
    fw = full.size[0]
    fh2 = full.size[1]
    last_content_col = fw - 1
    for col_idx in range(fw - 1, fw - 100, -1):
        col_pixels = list(full.crop((col_idx, 0, col_idx+1, fh2)).getdata())
        vals = [p[0] if isinstance(p, tuple) else p for p in col_pixels]
        if _stats.stdev(vals) > 8 or min(vals) < 245:
            last_content_col = col_idx
            break
    if last_content_col < fw - 1:
        full = full.crop((0, 0, last_content_col + 2, fh2))
        print(f'Right-cropped to: {full.size}')

    # Resize to target width + sharpen
    from PIL import ImageFilter
    ratio = IMG_WIDTH / full.size[0]
    new_h = int(full.size[1] * ratio)
    full = full.resize((IMG_WIDTH, new_h), Image.LANCZOS)
    full = full.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=2))
    print(f'Resized: {full.size}')

    full.save(out_path, 'JPEG', quality=JPEG_Q)
    kb = os.path.getsize(out_path) // 1024
    print(f'✅ Saved: {out_path} ({kb}KB)')
    return out_path

# ─── Upload ───────────────────────────────────────────────────
def upload_image(img_path):
    import subprocess
    cmd = ['curl','-s','-X','POST',
           'https://qa.service.test.sankuai.com/api/flowCopilot/oversea/file/uploadImage',
           '-F', f'file=@{img_path}']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    print('Upload response:', r.stdout)
    try:
        j = json.loads(r.stdout)
        url = j.get('data',{}).get('url') or j.get('url') or j.get('data')
        if isinstance(url, str) and url.startswith('http'):
            return url
        # Try nested
        if isinstance(j.get('data'), dict):
            for k,v in j['data'].items():
                if isinstance(v,str) and v.startswith('http'):
                    return v
    except:
        pass
    return r.stdout.strip()

# ─── Main ─────────────────────────────────────────────────────
def main():
    t0 = time.time()
    print(f'📊 Loading {XLSX_PATH}...')
    data = load_data(XLSX_PATH)
    print(f'  {len(data)} BD rows loaded')

    # Detect date from filename
    import re
    fname = Path(XLSX_PATH).name
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', fname)
    date_str = date_match.group(1) if date_match else datetime.now().strftime('%Y-%m-%d')
    print(f'  Date: {date_str}')

    print('🎨 Generating HTML...')
    html = generate_html(data, date_str)
    with open(OUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'  HTML saved: {OUT_HTML}')

    print('📸 Taking CDP screenshot...')
    asyncio.run(cdp_screenshot_chunks(html, OUT_IMG))

    print('☁️  Uploading...')
    url = upload_image(OUT_IMG)
    print(f'  URL: {url}')

    elapsed = (time.time()-t0)/60
    print(f'\n✅ Done in {elapsed:.1f}min | URL: {url}')
    return url

if __name__ == '__main__':
    main()
