#!/usr/bin/env python3
"""
AE DBR 报告可视化 — 将查询结果渲染为表格图片

用法:
  python3 ae_dbr_chart.py --date 20260520
  python3 ae_dbr_chart.py                    # 默认昨天

输出:
  .artifacts/segment_analysis/{T1}/chart_{T1}.png        (大盘 + 生命周期分层)
  .artifacts/segment_analysis/{T1}/chart_{T1}_sab.png    (SAB 漏斗)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import font_manager as fm

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from ae_dbr_query import (  # noqa: E402
    _read_csv, _fv, _fv_num, _pct, _pp, calc_dates, yesterday,
)
from skill_tracker import report_script  # noqa: E402

# ── 中文字体 ───────────────────────────────────────────────────────────────────

def _setup_cjk_font() -> str:
    available = {f.name for f in fm.fontManager.ttflist}
    candidates = [
        # macOS
        "PingFang HK", "PingFang SC", "STHeiti", "Heiti TC",
        "Arial Unicode MS", "Songti SC",
        # Linux（文泉驿、Noto CJK、思源黑体、Droid）
        "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",
        "Noto Sans CJK SC", "Noto Sans CJK TC",
        "Noto Sans SC", "Noto Sans TC",
        "Source Han Sans CN", "Source Han Sans SC",
        "Droid Sans Fallback",
    ]
    for name in candidates:
        if name in available:
            plt.rcParams["font.family"] = name
            plt.rcParams["axes.unicode_minus"] = False
            return name
    return "sans-serif"

FONT = _setup_cjk_font()

# ── 字体缩放 ───────────────────────────────────────────────────────────────────
FS = 1.5   # 全局字体放大系数

# ── 配色方案 ───────────────────────────────────────────────────────────────────

C_HEAD_BG    = "#2C3E50"
C_HEAD_FG    = "#FFFFFF"
C_SEG_A      = "#90CAF9"   # 分层标签交替色 A（浅蓝）
C_SEG_B      = "#FFCC80"   # 分层标签交替色 B（浅橙）
C_SEG_FG     = "#1A252F"
C_ROW_ODD    = "#FFFFFF"
C_ROW_EVEN   = "#F5F7FA"
C_POS_DARK   = "#A8D5A2"   # DoD/WoW ≥ +5%
C_POS_LIGHT  = "#D4EDDA"   # DoD/WoW 0 ~ +5%
C_NEG_DARK   = "#F5C6CB"   # DoD/WoW ≤ -5%
C_NEG_LIGHT  = "#FAE0E4"   # DoD/WoW -5% ~ 0
C_NEUTRAL    = None
C_BORDER     = "#BDC3C7"
C_SUB_BG     = "#F5F5F5"   # O/S 子行背景


def _change_color(val: str) -> str | None:
    s = val.strip().replace("+", "").replace("%", "").replace("pp", "").strip()
    try:
        v = float(s)
        if v >= 5:   return C_POS_DARK
        if v > 0:    return C_POS_LIGHT
        if v <= -5:  return C_NEG_DARK
        if v < 0:    return C_NEG_LIGHT
    except ValueError:
        pass
    return C_NEUTRAL


# ── 数据构建 ───────────────────────────────────────────────────────────────────

SEG_DISPLAY = {
    "new1st":    "新客首访",
    "newNon1st": "新客非首访",
    "5plus":     "成熟(5+单)",
    "1to4":      "尝鲜(1-4单)",
    "lapsed":    "沉流用户",
}
SEG_ORDER = ["new1st", "newNon1st", "5plus", "1to4", "lapsed"]


def build_table_data(
    out_dir: Path, t9: str, t8: str, t2: str, t1: str
) -> tuple[list[list[str]], list[bool], list[str]]:
    """返回大盘 + 生命周期分层数据 (rows, is_seg_header, row_types)"""
    dates = [t9, t8, t2, t1]

    global_rows = {r["dt"]: r for r in _read_csv(out_dir / "sql_global.csv")}

    csub_seg: dict[tuple, float] = {}
    csub_dt:  dict[str, float]   = {}
    for r in _read_csv(out_dir / "sql_csub.csv"):
        c = _fv_num(r.get("c_sub")) or 0.0
        csub_seg[(r.get("seg", ""), r["dt"])] = c
        csub_dt[r["dt"]] = csub_dt.get(r["dt"], 0.0) + c

    vuv: dict[tuple, dict[str, float | None]] = {}
    for r in _read_csv(out_dir / "sql_funnel.csv"):
        ch = "O" if r["is_org"] == "1" else "S"
        vuv.setdefault((r["seg"], ch), {})[r["dt"]] = _fv_num(r.get("vuv"))
    for r in _read_csv(out_dir / "sql_visit_old.csv"):
        ch = "O" if r["is_org"] == "1" else "S"
        vuv.setdefault((r["seg"], ch), {})[r["dt"]] = _fv_num(r.get("vuv"))

    trade: dict[tuple, dict] = {}
    for r in _read_csv(out_dir / "sql_trade.csv"):
        trade[(r["seg"], r["os"], r["dt"])] = r

    def c_rate(dt: str) -> float | None:
        g = global_rows.get(dt, {})
        aov, ord_ = _fv_num(g.get("aov")), _fv_num(g.get("ord"))
        total_c = csub_dt.get(dt, 0)
        if aov and ord_ and aov * ord_ > 0 and total_c > 0:
            return total_c / (aov * ord_) * 100
        return None

    def make_row(seg_label: str, metric: str, vs: list, is_rate: bool) -> list[str]:
        dod = _pp(vs[3], vs[2]) if is_rate else _pct(vs[3], vs[2])
        wow = _pp(vs[3], vs[1]) if is_rate else _pct(vs[3], vs[1])
        return [seg_label, metric] + [_fv(v, is_pct=is_rate) for v in vs] + [dod, wow]

    def _sum(a: float | None, b: float | None) -> float | None:
        if a is None and b is None:
            return None
        return (a or 0) + (b or 0)

    def _weighted_aov(seg: str, dt: str) -> float | None:
        s = trade.get((seg, "S", dt), {})
        o = trade.get((seg, "O", dt), {})
        aov_s, ord_s = _fv_num(s.get("aov")), _fv_num(s.get("ord_cnt"))
        aov_o, ord_o = _fv_num(o.get("aov")), _fv_num(o.get("ord_cnt"))
        if aov_s and ord_s and aov_o and ord_o:
            return (aov_s * ord_s + aov_o * ord_o) / (ord_s + ord_o)
        return aov_s or aov_o or None

    def _weighted_sub(seg: str, dt: str) -> float | None:
        s = trade.get((seg, "S", dt), {})
        o = trade.get((seg, "O", dt), {})
        sub_s, aov_s, ord_s = _fv_num(s.get("sub")), _fv_num(s.get("aov")), _fv_num(s.get("ord_cnt"))
        sub_o, aov_o, ord_o = _fv_num(o.get("sub")), _fv_num(o.get("aov")), _fv_num(o.get("ord_cnt"))
        if sub_s and sub_o and aov_s and aov_o and ord_s and ord_o:
            rev_s, rev_o = aov_s * ord_s, aov_o * ord_o
            total_rev = rev_s + rev_o
            return (sub_s * rev_s + sub_o * rev_o) / total_rev if total_rev > 0 else None
        return sub_s or sub_o or None

    def _seg_gmv(seg: str, dt: str) -> float | None:
        s = trade.get((seg, "S", dt), {})
        o = trade.get((seg, "O", dt), {})
        as_, os_ = _fv_num(s.get("aov")), _fv_num(s.get("ord_cnt"))
        ao, oo   = _fv_num(o.get("aov")), _fv_num(o.get("ord_cnt"))
        gmv = ((as_ * os_) if as_ and os_ else 0.0) + ((ao * oo) if ao and oo else 0.0)
        return gmv if gmv > 0 else None

    def _c_rate_seg(seg: str, dt: str) -> float | None:
        c_sub = csub_seg.get((seg, dt))
        gmv = _seg_gmv(seg, dt)
        if c_sub is not None and gmv and gmv > 0:
            return c_sub / gmv * 100
        return None

    def _cvr(ouv: float | None, vuv_: float | None) -> float | None:
        if ouv is not None and vuv_ is not None and vuv_ > 0:
            return ouv / vuv_ * 100
        return None

    rows: list[list[str]] = []
    is_seg: list[bool] = []
    row_types: list[str] = []

    # ── 大盘 ─────────────────────────────────────────────────────────────────
    if global_rows:
        ALL_SEGS = ["new1st", "newNon1st", "5plus", "1to4", "lapsed"]

        def _g_vuv_ch(ch: str, dt: str) -> float | None:
            vals = [vuv.get((s, ch), {}).get(dt) for s in ALL_SEGS]
            vals = [v for v in vals if v is not None]
            return sum(vals) if vals else None

        def _g_ord_ch(ch: str, dt: str) -> float | None:
            vals = [_fv_num(trade.get((s, ch, dt), {}).get("ord_cnt")) for s in ALL_SEGS]
            vals = [v for v in vals if v is not None]
            return sum(vals) if vals else None

        g_vuv_s = [_g_vuv_ch("S", d) for d in dates]
        g_vuv_o = [_g_vuv_ch("O", d) for d in dates]
        g_vuv   = [_sum(s, o) for s, o in zip(g_vuv_s, g_vuv_o)]
        g_ord_s = [_g_ord_ch("S", d) for d in dates]
        g_ord_o = [_g_ord_ch("O", d) for d in dates]

        g_metrics = [
            ("visit UV",   g_vuv,                                                             False),
            ("  · S",      g_vuv_s,                                                           False),
            ("  · O",      g_vuv_o,                                                           False),
            ("Order UV",   [_fv_num(global_rows.get(d, {}).get("ouv")) for d in dates],       False),
            ("订单量",      [_fv_num(global_rows.get(d, {}).get("ord")) for d in dates],       False),
            ("  · S",      g_ord_s,                                                           False),
            ("  · O",      g_ord_o,                                                           False),
            ("AOV (AED)",  [_fv_num(global_rows.get(d, {}).get("aov")) for d in dates],       False),
            ("美补率",      [_fv_num(global_rows.get(d, {}).get("sub")) for d in dates],       True),
            ("C补率",       [c_rate(d) for d in dates],                                        True),
        ]
        for i, (metric, vs, is_rate) in enumerate(g_metrics):
            rows.append(make_row("大盘" if i == 0 else "", metric, vs, is_rate))
            is_seg.append(i == 0)
            row_types.append("data")

    # ── 各生命周期分层：合计 + O/S 子行 ──────────────────────────────────────
    for seg in SEG_ORDER:
        seg_label = SEG_DISPLAY[seg]
        first_row = True

        def _append3(metric_name: str, total_vs, s_vs, o_vs, is_rate: bool):
            nonlocal first_row
            rows.append(make_row(seg_label if first_row else "", metric_name, total_vs, is_rate))
            is_seg.append(first_row)
            row_types.append("total")
            first_row = False
            rows.append(make_row("", "  · S", s_vs, is_rate))
            is_seg.append(False)
            row_types.append("sub")
            rows.append(make_row("", "  · O", o_vs, is_rate))
            is_seg.append(False)
            row_types.append("sub")

        s_vuv = [vuv.get((seg, "S"), {}).get(d) for d in dates]
        o_vuv = [vuv.get((seg, "O"), {}).get(d) for d in dates]
        t_vuv = [_sum(s, o) for s, o in zip(s_vuv, o_vuv)]
        _append3("Visit UV", t_vuv, s_vuv, o_vuv, False)

        s_ouv = [_fv_num(trade.get((seg, "S", d), {}).get("ouv")) for d in dates]
        o_ouv = [_fv_num(trade.get((seg, "O", d), {}).get("ouv")) for d in dates]
        t_ouv = [_sum(s, o) for s, o in zip(s_ouv, o_ouv)]
        _append3("Order UV", t_ouv, s_ouv, o_ouv, False)

        s_ord = [_fv_num(trade.get((seg, "S", d), {}).get("ord_cnt")) for d in dates]
        o_ord = [_fv_num(trade.get((seg, "O", d), {}).get("ord_cnt")) for d in dates]
        t_ord = [_sum(s, o) for s, o in zip(s_ord, o_ord)]
        _append3("订单量", t_ord, s_ord, o_ord, False)

        t_cvr = [_cvr(t_ouv[i], t_vuv[i]) for i in range(4)]
        s_cvr = [_cvr(s_ouv[i], s_vuv[i]) for i in range(4)]
        o_cvr = [_cvr(o_ouv[i], o_vuv[i]) for i in range(4)]
        _append3("CVR", t_cvr, s_cvr, o_cvr, True)

        s_aov = [_fv_num(trade.get((seg, "S", d), {}).get("aov")) for d in dates]
        o_aov = [_fv_num(trade.get((seg, "O", d), {}).get("aov")) for d in dates]
        t_aov = [_weighted_aov(seg, d) for d in dates]
        _append3("AOV (AED)", t_aov, s_aov, o_aov, False)

        s_sub = [_fv_num(trade.get((seg, "S", d), {}).get("sub")) for d in dates]
        o_sub = [_fv_num(trade.get((seg, "O", d), {}).get("sub")) for d in dates]
        t_sub = [_weighted_sub(seg, d) for d in dates]
        _append3("美补率", t_sub, s_sub, o_sub, True)

        c_vs = [_c_rate_seg(seg, d) for d in dates]
        rows.append(make_row("", "C补率", c_vs, True))
        is_seg.append(False)
        row_types.append("total")

    return rows, is_seg, row_types


def build_sab_data(
    out_dir: Path, t9: str, t8: str, t2: str, t1: str
) -> tuple[list[list[str]], list[bool], list[str]]:
    """返回 SAB 漏斗数据 (rows, is_seg_header, row_types)"""
    dates = [t9, t8, t2, t1]

    sab: dict[tuple, dict] = {}
    sab_lvls: list[str] = []
    for r in _read_csv(out_dir / "sql_sab.csv"):
        sab[(r["lvl"], r["dt"])] = r
        if r["lvl"] not in sab_lvls:
            sab_lvls.append(r["lvl"])

    def make_row(seg_label: str, metric: str, vs: list, is_rate: bool) -> list[str]:
        dod = _pp(vs[3], vs[2]) if is_rate else _pct(vs[3], vs[2])
        wow = _pp(vs[3], vs[1]) if is_rate else _pct(vs[3], vs[1])
        return [seg_label, metric] + [_fv(v, is_pct=is_rate) for v in vs] + [dod, wow]

    rows: list[list[str]] = []
    is_seg: list[bool] = []
    row_types: list[str] = []

    for lvl in sab_lvls:
        label = f"SAB-{lvl}"
        v_vuv = [_fv_num(sab.get((lvl, d), {}).get("vuv")) for d in dates]
        v_ouv = [_fv_num(sab.get((lvl, d), {}).get("ouv")) for d in dates]
        for i, (metric, vs) in enumerate([("Visit UV", v_vuv), ("Order UV", v_ouv)]):
            rows.append(make_row(label if i == 0 else "", metric, vs, False))
            is_seg.append(i == 0)
            row_types.append("data")

    return rows, is_seg, row_types


# ── 渲染 ────────────────────────────────────────────────────────────────────────

COL_WIDTHS = [0.16, 0.11, 0.095, 0.095, 0.095, 0.095, 0.09, 0.09]
ROW_H      = 0.028 * FS   # 行高随字体放大


def _render_one_chart(
    rows: list[list[str]],
    is_seg: list[bool],
    row_types: list[str],
    headers: list[str],
    title: str,
    subtitle: str,
    out_path: Path,
) -> Path:
    """渲染单张图片并保存"""
    n_rows = len(rows)
    if n_rows == 0:
        print(f"⚠️  无数据，跳过：{out_path.name}")
        return out_path

    fig_w    = 20
    header_h = 1.4 * FS
    fig_h    = header_h + n_rows * ROW_H * fig_w + 0.6
    fig_h    = max(fig_h, 14)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    fig.patch.set_facecolor("#F0F4F8")
    ax.set_facecolor("#F0F4F8")

    _row_offset = 2 * ROW_H * fig_w / fig_h
    _title_y    = 0.99 - _row_offset

    fig.text(0.5, _title_y, title,
             ha="center", va="top",
             fontsize=20 * FS, fontweight="bold", color="#000000",
             transform=fig.transFigure)

    _date_y = _title_y - 20 * FS / 72 / fig_h * 2.2
    fig.text(0.5, _date_y, subtitle, ha="center", va="top",
             fontsize=15 * FS, fontweight="bold", color="#000000",
             transform=fig.transFigure)

    _axes_top = _date_y - 15 * FS / 72 / fig_h * 3.0

    # 建表坐标
    total_w = sum(COL_WIDTHS)
    col_x   = [sum(COL_WIDTHS[:i]) / total_w for i in range(8)]
    col_w   = [w / total_w for w in COL_WIDTHS]

    head_h = 0.040 * FS
    row_h  = (1.0 - head_h) / n_rows

    def draw_cell(x, y, w, h, text, bg, fg="#000000",
                  fontsize=9.5 * FS, bold=False, ha="center", va="center"):
        ax.add_patch(mpatches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="square,pad=0", linewidth=0.4,
            edgecolor=C_BORDER, facecolor=bg or C_ROW_ODD,
            transform=ax.transAxes, clip_on=False,
        ))
        ax.text(
            x + w * 0.5 if ha == "center" else x + w * 0.04,
            y + h * 0.5,
            text, ha=ha, va=va,
            fontsize=fontsize, color=fg,
            fontweight="bold" if bold else "normal",
            transform=ax.transAxes, clip_on=False,
        )

    # 表头行
    y_head = 1.0 - head_h
    for ci, (htext, cx, cw) in enumerate(zip(headers, col_x, col_w)):
        draw_cell(cx, y_head, cw, head_h, htext,
                  bg=C_HEAD_BG, fg=C_HEAD_FG,
                  fontsize=11 * FS, bold=True)

    # 按分层分组（用于合并格子 + 交替配色）
    seg_groups: list[tuple[str, int, int]] = []
    i = 0
    while i < len(rows):
        if is_seg[i]:
            label = rows[i][0]
            j = i + 1
            while j < len(rows) and not is_seg[j]:
                j += 1
            seg_groups.append((label, i, j - 1))
            i = j
        else:
            i += 1

    # 数据行（跳过列 0，由合并格子覆盖）
    for ri, (row, _, rtype) in enumerate(zip(rows, is_seg, row_types)):
        y = y_head - (ri + 1) * row_h
        base_bg = C_SUB_BG if rtype == "sub" else (C_ROW_ODD if ri % 2 == 0 else C_ROW_EVEN)

        for ci, (cell, cx, cw) in enumerate(zip(row, col_x, col_w)):
            if ci == 0:
                continue
            if ci in (1, 2, 3, 4, 5):
                bg   = C_SUB_BG if rtype == "sub" else C_ROW_ODD
                fg   = "#555555" if rtype == "sub" else "#000000"
                bold = rtype == "total"
            elif ci in (6, 7):
                bg   = _change_color(cell) or base_bg
                fg   = "#000000"
                bold = False
            else:
                bg   = base_bg
                fg   = "#555555" if rtype == "sub" else "#000000"
                bold = rtype == "total"

            ha = "left" if ci == 1 else "center"
            fs = 8.5 * FS if rtype == "sub" else 9.5 * FS
            draw_cell(cx, y, cw, row_h, cell, bg=bg, fg=fg, bold=bold, fontsize=fs, ha=ha)

    # 分层标签：合并格子，蓝/橙交替
    for gi, (seg_label, start, end) in enumerate(seg_groups):
        y_bottom = y_head - (end + 1) * row_h
        tall_h   = (end - start + 1) * row_h
        seg_bg   = C_SEG_A if gi % 2 == 0 else C_SEG_B
        draw_cell(col_x[0], y_bottom, col_w[0], tall_h, seg_label,
                  bg=seg_bg, fg=C_SEG_FG, bold=True,
                  fontsize=15 * FS, ha="center")

    # 图例
    legend_items = [
        mpatches.Patch(facecolor=C_POS_DARK,  label="≥ +5%"),
        mpatches.Patch(facecolor=C_POS_LIGHT, label="0 ~ +5%"),
        mpatches.Patch(facecolor=C_NEG_LIGHT, label="-5% ~ 0"),
        mpatches.Patch(facecolor=C_NEG_DARK,  label="≤ -5%"),
        mpatches.Patch(facecolor=C_SEG_A,     label="分层色 A"),
        mpatches.Patch(facecolor=C_SEG_B,     label="分层色 B"),
        mpatches.Patch(facecolor=C_SUB_BG,    label="O/S 子行"),
    ]
    ax.legend(handles=legend_items, loc="upper right",
              bbox_to_anchor=(1.0, -0.01),
              ncol=7, fontsize=8 * FS, frameon=True,
              framealpha=0.9, edgecolor=C_BORDER,
              bbox_transform=ax.transAxes)

    fig.tight_layout(rect=[0, 0.02, 1, _axes_top])
    fig.savefig(out_path, dpi=180, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"✅ 图表已保存：{out_path}")
    return out_path


def render_chart(
    out_dir: Path, t9: str, t8: str, t2: str, t1: str
) -> tuple[Path, Path]:
    headers  = ["分层", "指标", t9, t8, t2, t1, "DoD", "WoW"]
    title    = "AE DBR 用户生命周期监控  |  region = AE"
    subtitle = (
        f"查询日期：{t9} / {t8} / {t2} / {t1}    "
        f"DoD = {t1} vs {t2}    WoW = {t1} vs {t8}"
    )

    lc_rows, lc_is_seg, lc_types = build_table_data(out_dir, t9, t8, t2, t1)
    path1 = _render_one_chart(
        lc_rows, lc_is_seg, lc_types,
        headers, title, subtitle,
        out_dir / f"chart_{t1}.png",
    )

    sab_rows, sab_is_seg, sab_types = build_sab_data(out_dir, t9, t8, t2, t1)
    path2 = _render_one_chart(
        sab_rows, sab_is_seg, sab_types,
        headers, f"{title}  |  SAB漏斗", subtitle,
        out_dir / f"chart_{t1}_sab.png",
    )

    return path1, path2


# ── 主入口 ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AE DBR 报告可视化")
    parser.add_argument("--date",    default=None, help="T1 日期 YYYYMMDD（默认昨天）")
    parser.add_argument("--out-dir", default=None, help="输出目录（默认与 ae_dbr_query.py 一致）")
    args = parser.parse_args()

    t1_input = args.date or yesterday()
    t9, t8, t2, t1 = calc_dates(t1_input)
    out_dir = Path(args.out_dir) if args.out_dir else PROJECT_DIR / ".artifacts" / "segment_analysis" / t1
    params = {
        "script": "ae_dbr_chart.py",
        "date": t1,
        "out_dir": str(out_dir),
    }
    start = time.monotonic()

    def report_chart_node(success: bool, output: dict | None = None, error_msg: str = "") -> None:
        # tracking: scripts/ae_dbr_chart.py::report_chart_node::skill-script
        report_script(
            params=json.dumps(params, ensure_ascii=False),
            output=json.dumps(output or {}, ensure_ascii=False),
            cost_ms=int((time.monotonic() - start) * 1000),
            success=success,
            error_msg=error_msg[:200],
        )

    if not out_dir.exists():
        message = f"输出目录不存在：{out_dir}，请先运行 ae_dbr_query.py --date {t1}"
        print(f"❌ {message}", file=sys.stderr)
        report_chart_node(False, {"status": "failed", "missing_out_dir": str(out_dir)}, message)
        sys.exit(1)

    print(f"读取数据：{out_dir}")
    print(f"日期：T9={t9}  T8={t8}  T2={t2}  T1={t1}")
    try:
        chart_paths = render_chart(out_dir, t9, t8, t2, t1)
    except Exception as e:
        report_chart_node(False, {"status": "failed"}, str(e))
        raise

    # ── G5：图表生成 Gate Check ───────────────────────────────────────────────
    # 两张图片必须存在且非空，否则打印 [GATE FAIL] 并以退出码 1 退出
    expected = [
        out_dir / f"chart_{t1}.png",
        out_dir / f"chart_{t1}_sab.png",
    ]
    missing = [str(p) for p in expected if not p.exists() or p.stat().st_size == 0]
    if missing:
        gate_messages = []
        for p in missing:
            message = (
                f"[GATE FAIL] G5 图表生成：{p} 不存在或为空文件，"
                f"请检查 matplotlib 依赖是否已安装，或重新执行 ae_dbr_chart.py。"
            )
            gate_messages.append(message)
            print(message, file=sys.stderr)
        report_chart_node(
            False,
            {"status": "failed", "missing": missing, "charts": [str(p) for p in chart_paths]},
            "\n".join(gate_messages),
        )
        sys.exit(1)

    report_chart_node(True, {"status": "ok", "charts": [str(p) for p in chart_paths]})
    print("[GATE OK] G5 图表生成通过")
    for p in expected:
        print(f"  ✅ {p}")


if __name__ == "__main__":
    main()
