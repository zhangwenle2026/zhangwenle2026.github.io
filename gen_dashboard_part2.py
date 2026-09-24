#!/usr/bin/env python3
"""Part 2: Generate the full HTML from context."""
import json

with open("_gen_ctx.json", "r") as f:
    c = json.load(f)

rs = c["rs"]
prev = c["prev"]
s = c["s"]
w = c["w"]
st = c["st"]

# The CSS (same as original)
css = """* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #f5f7fa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #2c3e50; padding: 20px; }
.container { max-width: 1400px; margin: 0 auto; }
.header { text-align: center; padding: 30px 20px; margin-bottom: 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px; color: white; }
.header h1 { font-size: 28px; margin-bottom: 4px; }
.header .subtitle { font-size: 16px; opacity: 0.9; }
.header .date { font-size: 13px; opacity: 0.75; margin-top: 8px; }
.validity-banner { background: #fff3cd; border: 2px solid #ffc107; border-radius: 8px; padding: 12px 20px; margin-bottom: 24px; text-align: center; font-size: 14px; color: #856404; font-weight: 600; }
.section-title { font-size: 20px; font-weight: 700; margin: 32px 0 16px; padding-left: 12px; border-left: 4px solid #667eea; }
.section-subtitle { font-size: 13px; color: #7f8c8d; margin-top: -12px; margin-bottom: 16px; padding-left: 16px; }
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.kpi-card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); text-align: center; }
.kpi-value { font-size: 36px; font-weight: 800; color: #2c3e50; }
.kpi-value small { font-size: 16px; color: #95a5a6; font-weight: 400; }
.kpi-label { font-size: 13px; color: #7f8c8d; margin-top: 4px; }
.kpi-dod { font-size: 13px; margin-top: 6px; }
.kpi-sub { font-size: 11px; color: #95a5a6; margin-top: 2px; }
.dod-up { color: #27ae60; font-weight: 600; }
.dod-down { color: #e74c3c; font-weight: 600; }
.dod-flat { color: #95a5a6; }
.dod-card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 24px; }
.dod-card h3 { font-size: 16px; margin-bottom: 16px; color: #34495e; }
.dod-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.dod-item { display: flex; flex-direction: column; gap: 4px; padding: 12px; background: #f8f9fa; border-radius: 8px; }
.dod-label { font-size: 13px; font-weight: 600; color: #555; margin-bottom: 4px; }
.dir-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
.dir-card { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.dir-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; padding: 8px; border-radius: 8px; background: #f8f9fa; }
.dir-icon { font-size: 20px; }
.dir-title { font-size: 15px; font-weight: 600; }
.dir-subtitle { font-size: 11px; color: #95a5a6; }
.dir-stats { display: flex; justify-content: space-between; margin-bottom: 10px; }
.dir-stat { text-align: center; }
.dir-stat-label { display: block; font-size: 11px; color: #95a5a6; }
.dir-stat-value { display: block; font-size: 20px; font-weight: 700; }
.dir-pct { text-align: right; font-size: 12px; color: #95a5a6; margin-top: 4px; }
.progress-bar-wrap { background: #ecf0f1; border-radius: 6px; height: 8px; overflow: hidden; }
.progress-bar-wrap.small { height: 5px; margin-top: 4px; }
.progress-bar { height: 100%; border-radius: 6px; transition: width 0.6s ease; min-width: 2px; }
.city-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
.city-card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.city-card h3 { font-size: 18px; font-weight: 700; margin-bottom: 12px; color: #34495e; }
.city-pool { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 12px; }
.city-stat { display: flex; justify-content: space-between; padding: 4px 0; }
.city-stat-label { font-size: 12px; color: #7f8c8d; }
.city-stat-value { font-size: 14px; font-weight: 600; }
.city-stat-value.highlight { color: #e74c3c; font-size: 16px; }
.city-stat-value small { font-size: 11px; color: #95a5a6; font-weight: 400; }
.city-directions { margin-top: 16px; }
.city-dir { margin-bottom: 10px; padding: 8px; background: #f8f9fa; border-radius: 8px; }
.city-dir-label { font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.city-dir-stats { font-size: 12px; color: #555; display: flex; gap: 12px; }
.tabs { display: flex; gap: 0; margin-bottom: 0; }
.tab { padding: 10px 24px; background: #ecf0f1; border: none; cursor: pointer; font-size: 14px; font-weight: 600; color: #7f8c8d; border-radius: 8px 8px 0 0; }
.tab.active { background: white; color: #2c3e50; box-shadow: 0 -2px 8px rgba(0,0,0,0.06); }
.tab-content { display: none; }
.tab-content.active { display: block; }
.table-wrap { background: white; border-radius: 0 12px 12px 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow-x: auto; margin-bottom: 24px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th { background: #f8f9fa; padding: 10px 8px; text-align: left; font-weight: 600; font-size: 12px; color: #555; border-bottom: 2px solid #ecf0f1; white-space: nowrap; }
tbody td { padding: 8px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }
tbody tr:hover { background: #fafbfc; }
.score-ns { color: #e74c3c; font-weight: 600; }
.score-no { color: #f39c12; font-weight: 600; }
.score-nop { color: #27ae60; font-weight: 600; }
.score-hv { color: #8e44ad; font-weight: 600; }
.score-total { font-size: 15px; }
.status-ok { color: #27ae60; font-weight: 600; font-size: 12px; }
.status-gap { color: #e74c3c; font-weight: 600; font-size: 12px; }
.prize { color: #D4A017; font-weight: 700; white-space: nowrap; }
.zero-row { opacity: 0.4; }
.gold { background: linear-gradient(90deg, rgba(212,160,23,0.08) 0%, transparent 100%); }
.silver { background: linear-gradient(90deg, rgba(160,160,160,0.08) 0%, transparent 100%); }
.bronze { background: linear-gradient(90deg, rgba(205,127,50,0.08) 0%, transparent 100%); }
.detail-row td { padding: 0 !important; background: #f8f9fa; }
.detail-table-wrap { padding: 8px 16px 8px 40px; }
.detail-table { width: auto; min-width: 400px; font-size: 12px; }
.detail-table th { background: #eef1f5; font-size: 11px; padding: 6px 10px; }
.detail-table td { padding: 5px 10px; border-bottom: 1px solid #eee; }
.rules-card { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 24px; }
.rules-table { width: 100%; }
.rules-table th { background: #667eea; color: white; padding: 10px; text-align: left; }
.rules-table td { padding: 10px; border-bottom: 1px solid #eee; }
.rules-table tr:nth-child(even) td { background: #f8f9fa; }
.stats-bar { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 16px; font-size: 12px; color: #7f8c8d; }
.footnote { background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 8px; padding: 12px 16px; margin-bottom: 24px; font-size: 12px; color: #856404; }
.footnote p { margin-bottom: 4px; }
.early-bird { background: #e8f5e9; border-left: 4px solid #27ae60; border-radius: 8px; padding: 12px 16px; margin-top: 16px; font-size: 12px; color: #2e7d32; }
.early-bird p { margin-bottom: 4px; }
@media (max-width: 900px) { .kpi-grid { grid-template-columns: repeat(2, 1fr); } .dir-grid { grid-template-columns: 1fr; } .city-grid { grid-template-columns: 1fr; } .dod-grid { grid-template-columns: 1fr; } .header h1 { font-size: 20px; } }
@media (max-width: 600px) { .kpi-grid { grid-template-columns: 1fr; } body { padding: 10px; } }"""

js = """function switchTab(tab) {
    document.querySelectorAll(".tab-content").forEach(function(el) {
        if (el.id === "tab-" + tab) { el.classList.add("active"); }
        else if (el.id.startsWith("tab-") && !el.id.startsWith("tab-bdm-")) { el.classList.remove("active"); }
    });
    var tabs = document.querySelectorAll(".tabs")[0].querySelectorAll(".tab");
    tabs.forEach(function(t, i) {
        if ((tab === "ws" && i === 0) || (tab === "santos" && i === 1)) t.classList.add("active");
        else t.classList.remove("active");
    });
}
function toggleDetail(id) {
    var row = document.getElementById("detail-" + id);
    if (row) row.style.display = row.style.display === "none" ? "" : "none";
}"""

dod_ns_sign = "+" if c["dod_ns_op"] >= 0 else ""
no_class = "dod-down" if c["dod_no_op"] < 0 else "dod-up"

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Order Penetration Incentive Race Dashboard</title>
<style>
{css}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>🏆 Order Penetration Incentive Race Dashboard</h1>
<div class="subtitle">Order Penetration Incentive Race / Painel de Corrida</div>
<div class="date">Data as of: 2026-08-17 (BRT) | Metropolitan Region</div>
</div>

<div class="validity-banner">
⚠️ Validity Standard: Operating ≥ 15h AND ≥ 1 order in last 7 days / 有效性标准：最近7天营业≥15小时且≥1订单
</div>

<div class="section-title">📊 MODULE 1: Regional Overview</div>
<div class="section-subtitle">Battle Pool — Full Coverage (All Merchants)</div>
<div class="kpi-grid">
<div class="kpi-card"><div class="kpi-value">{rs["total_target"]}</div><div class="kpi-label">Target Merchants</div></div>
<div class="kpi-card"><div class="kpi-value">{rs["total_signed"]} <small>({c["signed_pct"]:.1f}%)</small></div><div class="kpi-label">Signed</div></div>
<div class="kpi-card"><div class="kpi-value">{rs["total_operating"]} <small>({c["op_pct"]:.1f}%)</small></div><div class="kpi-label">Total Operating</div><div class="kpi-sub">BD-Assigned: 103</div></div>
<div class="kpi-card"><div class="kpi-value" style="color:#e74c3c">{rs["total_score"]}</div><div class="kpi-label">Total Score (with HV)</div><div class="kpi-sub">BD-Level: {rs["bd_level_score"]}</div></div>
</div>

<div class="dod-card">
<h3>📈 Day-over-Day Changes (8/16 → 8/17)</h3>
<div class="dod-grid">
<div class="dod-item"><span class="dod-label">Operating</span><span class="dod-up">{prev["total_operating"]} → {rs["total_operating"]} (+{c["dod_op"]}, +{c["dod_op_pct"]:.1f}%)</span></div>
<div class="dod-item"><span class="dod-label">Total Score</span><span class="dod-up">{prev["total_score"]} → {rs["total_score"]} (+{c["dod_score"]}, +{c["dod_score_pct"]:.1f}%)</span></div>
<div class="dod-item"><span class="dod-label">BD-Level Score</span><span class="dod-up">{prev["bd_level_score"]} → {rs["bd_level_score"]} (+{c["dod_bd"]})</span></div>
<div class="dod-item"><span class="dod-label">NS Score</span><span class="dod-up">→ {rs["ns_score"]} pts ({rs["ns_op"]} operating, {dod_ns_sign}{c["dod_ns_op"]})</span></div>
<div class="dod-item"><span class="dod-label">NO Score</span><span class="{no_class}">→ {rs["no_score"]} pts ({rs["no_op"]} operating, {c["dod_no_op"]})</span></div>
<div class="dod-item"><span class="dod-label">NOP + HV</span><span class="dod-up">→ {rs["nop_score"]} + {rs["hv_bonus"]} = {rs["nop_score"] + rs["hv_bonus"]} pts</span></div>
</div>
</div>

<div class="section-subtitle">Three Attack Directions (Full Coverage)</div>
<div class="dir-grid">
<div class="dir-card"><div class="dir-header" style="border-left:4px solid #e74c3c"><span class="dir-icon">🔴</span><div><div class="dir-title">Not Signed</div><div class="dir-subtitle">Not Signed → Operating</div></div></div><div class="dir-stats"><div class="dir-stat"><span class="dir-stat-label">Target</span><span class="dir-stat-value">{rs["ns_target"]}</span></div><div class="dir-stat"><span class="dir-stat-label">Score</span><span class="dir-stat-value">{rs["ns_score"]}</span></div></div><div class="progress-bar-wrap"><div class="progress-bar" style="width:{c["ns_comp"]:.1f}%;background:#e74c3c"></div></div><div class="dir-pct">{c["ns_comp"]:.1f}% completion ({rs["ns_op"]} operating)</div></div>
<div class="dir-card"><div class="dir-header" style="border-left:4px solid #f39c12"><span class="dir-icon">🟡</span><div><div class="dir-title">Not Online</div><div class="dir-subtitle">Signed Not Online → Operating</div></div></div><div class="dir-stats"><div class="dir-stat"><span class="dir-stat-label">Target</span><span class="dir-stat-value">{rs["no_target"]}</span></div><div class="dir-stat"><span class="dir-stat-label">Score</span><span class="dir-stat-value">{rs["no_score"]}</span></div></div><div class="progress-bar-wrap"><div class="progress-bar" style="width:{c["no_comp"]:.1f}%;background:#f39c12"></div></div><div class="dir-pct">{c["no_comp"]:.1f}% completion ({rs["no_op"]} operating)</div></div>
<div class="dir-card"><div class="dir-header" style="border-left:4px solid #27ae60"><span class="dir-icon">🟢</span><div><div class="dir-title">Not Operating</div><div class="dir-subtitle">Signed Not Operating → Recovered</div></div></div><div class="dir-stats"><div class="dir-stat"><span class="dir-stat-label">Target</span><span class="dir-stat-value">{rs["nop_target"]}</span></div><div class="dir-stat"><span class="dir-stat-label">Score</span><span class="dir-stat-value">{rs["nop_score"]}</span></div></div><div class="progress-bar-wrap"><div class="progress-bar" style="width:{c["nop_comp"]:.1f}%;background:#27ae60"></div></div><div class="dir-pct">{c["nop_comp"]:.1f}% completion ({rs["nop_op"]} operating)</div></div>
</div>

<div class="footnote">
<p>📊 <b>Score Breakdown:</b> NS {rs["ns_op"]}×6={rs["ns_score"]} + NO {rs["no_op"]}×4={rs["no_score"]} + NOP {rs["nop_op"]}×3={rs["nop_score"]} + HV {rs["hv_count"]}×2={rs["hv_bonus"]} = <b>{rs["total_score"]}</b></p>
<p>🏆 <b>HV Bonus:</b> {rs["hv_count"]} merchants with iFood orders ≥ 20, +2 pts each = {rs["hv_bonus"]} pts</p>
</div>

<div class="section-title">🏙️ MODULE 2: City Battle Overview</div>
<div class="city-grid">
<div class="city-card"><h3>Southern</h3><div class="city-pool"><div class="city-stat"><span class="city-stat-label">Target</span><span class="city-stat-value">{s["target"]}</span></div><div class="city-stat"><span class="city-stat-label">Signed</span><span class="city-stat-value">{s["signed"]} <small>({c["s_sp"]:.1f}%)</small></span></div><div class="city-stat"><span class="city-stat-label">Operating</span><span class="city-stat-value">{s["operating"]} <small>({s["op_rate"]:.1f}%)</small></span></div><div class="city-stat"><span class="city-stat-label">Score</span><span class="city-stat-value highlight">{s["score"]}</span></div></div><div class="progress-bar-wrap"><div class="progress-bar" style="width:{s["op_rate"]:.1f}%;background:#3498db"></div></div><div class="dir-pct">Operating Rate: {s["op_rate"]:.1f}%</div><div class="city-directions"><div class="city-dir"><div class="city-dir-label">🔴 Not Sign</div><div class="city-dir-stats"><span>Target: {s["ns_target"]}</span><span>→ Op: {s["ns_op"]}</span><span>→ Score: {s["ns_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{c["s_nsp"]:.1f}%;background:#e74c3c"></div></div></div><div class="city-dir"><div class="city-dir-label">🟡 Not Online</div><div class="city-dir-stats"><span>Target: {s["no_target"]}</span><span>→ Op: {s["no_op"]}</span><span>→ Score: {s["no_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{c["s_nop"]:.1f}%;background:#f39c12"></div></div></div><div class="city-dir"><div class="city-dir-label">🟢 Not Oper.</div><div class="city-dir-stats"><span>Target: {s["nop_target"]}</span><span>→ Op: {s["nop_op"]}</span><span>→ Score: {s["nop_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{c["s_nopp"]:.1f}%;background:#27ae60"></div></div></div></div></div>
<div class="city-card"><h3>Western</h3><div class="city-pool"><div class="city-stat"><span class="city-stat-label">Target</span><span class="city-stat-value">{w["target"]}</span></div><div class="city-stat"><span class="city-stat-label">Signed</span><span class="city-stat-value">{w["signed"]} <small>({c["w_sp"]:.1f}%)</small></span></div><div class="city-stat"><span class="city-stat-label">Operating</span><span class="city-stat-value">{w["operating"]} <small>({w["op_rate"]:.1f}%)</small></span></div><div class="city-stat"><span class="city-stat-label">Score</span><span class="city-stat-value highlight">{w["score"]}</span></div></div><div class="progress-bar-wrap"><div class="progress-bar" style="width:{w["op_rate"]:.1f}%;background:#3498db"></div></div><div class="dir-pct">Operating Rate: {w["op_rate"]:.1f}%</div><div class="city-directions"><div class="city-dir"><div class="city-dir-label">🔴 Not Sign</div><div class="city-dir-stats"><span>Target: {w["ns_target"]}</span><span>→ Op: {w["ns_op"]}</span><span>→ Score: {w["ns_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{c["w_nsp"]:.1f}%;background:#e74c3c"></div></div></div><div class="city-dir"><div class="city-dir-label">🟡 Not Online</div><div class="city-dir-stats"><span>Target: {w["no_target"]}</span><span>→ Op: {w["no_op"]}</span><span>→ Score: {w["no_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{c["w_nop"]:.1f}%;background:#f39c12"></div></div></div><div class="city-dir"><div class="city-dir-label">🟢 Not Oper.</div><div class="city-dir-stats"><span>Target: {w["nop_target"]}</span><span>→ Op: {w["nop_op"]}</span><span>→ Score: {w["nop_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{c["w_nopp"]:.1f}%;background:#27ae60"></div></div></div></div></div>
<div class="city-card"><h3>Santos</h3><div class="city-pool"><div class="city-stat"><span class="city-stat-label">Target</span><span class="city-stat-value">{st["target"]}</span></div><div class="city-stat"><span class="city-stat-label">Signed</span><span class="city-stat-value">{st["signed"]} <small>({c["st_sp"]:.1f}%)</small></span></div><div class="city-stat"><span class="city-stat-label">Operating</span><span class="city-stat-value">{st["operating"]} <small>({st["op_rate"]:.1f}%)</small></span></div><div class="city-stat"><span class="city-stat-label">Score</span><span class="city-stat-value highlight">{st["score"]}</span></div></div><div class="progress-bar-wrap"><div class="progress-bar" style="width:{st["op_rate"]:.1f}%;background:#3498db"></div></div><div class="dir-pct">Operating Rate: {st["op_rate"]:.1f}%</div><div class="city-directions"><div class="city-dir"><div class="city-dir-label">🔴 Not Sign</div><div class="city-dir-stats"><span>Target: {st["ns_target"]}</span><span>→ Op: {st["ns_op"]}</span><span>→ Score: {st["ns_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{c["st_nsp"]:.1f}%;background:#e74c3c"></div></div></div><div class="city-dir"><div class="city-dir-label">🟡 Not Online</div><div class="city-dir-stats"><span>Target: {st["no_target"]}</span><span>→ Op: {st["no_op"]}</span><span>→ Score: {st["no_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{c["st_nop"]:.1f}%;background:#f39c12"></div></div></div><div class="city-dir"><div class="city-dir-label">🟢 Not Oper.</div><div class="city-dir-stats"><span>Target: {st["nop_target"]}</span><span>→ Op: {st["nop_op"]}</span><span>→ Score: {st["nop_score"]}</span></div><div class="progress-bar-wrap small"><div class="progress-bar" style="width:{c["st_nopp"]:.1f}%;background:#27ae60"></div></div></div></div></div>
</div>

<div class="section-title">👤 MODULE 3: BD Personal Rankings</div>
<div class="tabs">
<button class="tab active" onclick="switchTab('ws')">Western + Southern (63 BDs)</button>
<button class="tab" onclick="switchTab('santos')">Santos (8 BDs)</button>
</div>
<div id="tab-ws" class="tab-content active"><div class="table-wrap">
<table><thead><tr><th>Rank</th><th>BD</th><th>BDM</th><th>City</th><th>🔴 NS</th><th>🟡 NO</th><th>🟢 NOP</th><th>HV+2</th><th>Total</th><th>Status</th><th>Prize</th></tr></thead><tbody>
{c["ws_rows"]}</tbody></table></div></div>
<div id="tab-santos" class="tab-content"><div class="table-wrap">
<table><thead><tr><th>Rank</th><th>BD</th><th>BDM</th><th>City</th><th>🔴 NS</th><th>🟡 NO</th><th>🟢 NOP</th><th>HV+2</th><th>Total</th><th>Status</th><th>Prize</th></tr></thead><tbody>
{c["santos_rows"]}</tbody></table></div></div>

<div class="section-title">👥 MODULE 4: BDM Team Rankings</div>
<div class="table-wrap">
<table><thead><tr><th>Rank</th><th>BDM</th><th>City</th><th>BD Count</th><th>Team Score</th><th>Avg</th><th>Status</th></tr></thead><tbody>
{c["bdm_rows"]}
</tbody></table></div>

<div class="section-title">📋 MODULE 5: Scoring Rules</div>
<div class="rules-card">
<table class="rules-table">
<thead><tr><th>Direction</th><th>Condition</th><th>Base Score</th><th>HV Bonus</th></tr></thead>
<tbody>
<tr><td>🔴 Not Signed</td><td>Not signed → Operating</td><td>6</td><td>iFood ≥ 20: +2</td></tr>
<tr><td>🟡 Not Online</td><td>Signed not online → Operating</td><td>4</td><td>iFood ≥ 20: +2</td></tr>
<tr><td>🟢 Not Operating</td><td>Signed not operating → Recovered</td><td>3</td><td>iFood ≥ 20: +2</td></tr>
</tbody></table>
<div class="stats-bar"><span>Valid: 7d ≥ 15h + ≥ 1 order</span><span>| BD pass: ≥ 15 pts</span><span>| BDM pass: avg ≥ 15</span></div>
<div class="early-bird">
<p>🐦 <b>Early Bird Bonus: +1 pt</b> — conversion validated before Aug 15 / 早鸟加分：8月15日前完成转化并达标</p>
<p>⚠️ <b>Note:</b> Early Bird bonus requires final validity on Aug 31. If not valid on Aug 31, ALL points forfeited.</p>
<p>📌 <b>Current data does not include Early Bird bonus</b> (conversion date not available in source data).</p>
</div>
</div>

<div class="footnote">
<p>⚠️ <b>Data Quality Note:</b> 35 out of 113 operating merchants have status "Closed" in the source data. These are included in the operating count based on business hours and order activity meeting the validity standard, but may require data cleanup.</p>
<p>📋 <b>WoW Note:</b> 8/9 baseline: 73 operating, 192 score. 8/13 intermediate data point excluded due to calculation method inconsistency. All 8/17 figures use full-coverage (not BD-level only).</p>
</div>

</div>
<script>
{js}
</script>
</body>
</html>"""

with open("order_penetration_dashboard_v4.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"HTML written. Length: {len(html)} chars")
