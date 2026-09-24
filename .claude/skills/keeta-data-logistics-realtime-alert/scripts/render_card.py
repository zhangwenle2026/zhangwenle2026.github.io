#!/usr/bin/env python3
"""
将告警数据渲染为 HTML 卡片图片。

用法：
  1. 作为模块导入：from render_card import render_alert_card
  2. 命令行测试：python3 render_card.py --demo
"""

import json, os, sys, time, subprocess, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── 从 alert_config 导入共享常量（避免重复定义） ──
import os as _os
_SCRIPT_DIR = _os.path.dirname(_os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from alert_config import REGION_TZ, _slot_range

# Keeta logo (base64 inline 或远程 URL)
KEETA_LOGO_URL = "https://s3plus.sankuai.com/v1/mss_a3eb3b3017f94e96a11a1c8414e3e849/keeta-open/keeta-logo.png"

# 指标英文名映射
METRIC_EN_NAMES = {
    "ontime_task_ratio": "On-time Rate (C)",
    "bod_ontime_task_ratio": "Large Order On Time Rate (C)",
    "delivering_upcoming_timeout_task_ratio": "Timeout Rate (Delivering)",
    "last_1h_delivered_ord_ontime_ratio": "L1H On Time Rate (C)",
    "last_1h_delivered_bod_ord_ontime_ratio": "L1H Large Order On Time Rate (C)",
    "last_1h_delivered_ord_me_ordavg": "L1H Avg ME (min)",
    "last_1h_delivered_ord_ata_ordavg": "L1H ATA (min)",
    "last_2h_cancel_after_grab_ratio": "L2H Cancellation Rate",
    "precipitation_hourly": "Precipitation (mm)",
    "last_1hour_online_courier_efficiency": "L1H Online Courier Efficiency",
    "meal_preparation_delay_merchant_num": "Meal Prep Delay Merchant Num",
    "meal_preparation_delay_merchant_ratio": "Meal Prep Delay Merchant Ratio",
    "unaccepted_task_num": "Unaccepted Tasks",
    "last_20min_meal_waiting_dura_task_avg": "Avg Time of Meal Waiting (Last 20min)",
}

# 指标中文名映射
METRIC_CN_NAMES = {
    "ontime_task_ratio": "C端准时率",
    "bod_ontime_task_ratio": "大订单C端准时率",
    "delivering_upcoming_timeout_task_ratio": "配送中即将超时占比",
    "last_1h_delivered_ord_ontime_ratio": "L1H C端准时率",
    "last_1h_delivered_bod_ord_ontime_ratio": "L1H 大订单C端准时率",
    "last_1h_delivered_ord_me_ordavg": "最近一小时单均ME",
    "last_1h_delivered_ord_ata_ordavg": "最近一小时单均ATA(分)",
    "last_2h_cancel_after_grab_ratio": "L2H 接单后取消率",
    "precipitation_hourly": "降水量(mm)",
    "last_1hour_online_courier_efficiency": "L1H 在线骑手效率",
    "meal_preparation_delay_merchant_num": "卡餐上报商家数",
    "meal_preparation_delay_merchant_ratio": "卡餐上报商家占比",
    "unaccepted_task_num": "积压任务单数",
    "last_20min_meal_waiting_dura_task_avg": "近20分钟平均等餐时长",
}

# 百分比类指标
PCT_METRICS = {
    "ontime_task_ratio", "bod_ontime_task_ratio",
    "delivering_upcoming_timeout_task_ratio",
    "last_1h_delivered_ord_ontime_ratio",
    "last_1h_delivered_bod_ord_ontime_ratio",
    "last_2h_cancel_after_grab_ratio",
    "meal_preparation_delay_merchant_ratio",
}


def format_val(key, val):
    if key in PCT_METRICS:
        return f"{val*100:.1f}%"
    elif key in ("last_1h_delivered_ord_me_ordavg", "last_1h_delivered_ord_ata_ordavg",
                 "last_1hour_online_courier_efficiency", "precipitation_hourly"):
        return f"{val:.2f}"
    elif key in ("meal_preparation_delay_merchant_num", "unaccepted_task_num"):
        return f"{int(val)}"
    elif key == "last_20min_meal_waiting_dura_task_avg":
        return f"{val:.2f}"
    return f"{val}"


def format_threshold(key, op, val):
    if key in PCT_METRICS:
        return f"{op} {val*100:.0f}%"
    return f"{op} {val:g}"


def _compute_delta(mk, val_str, val_float, thr_float, op):
    """计算当前值与阈值的偏差 delta，返回格式化字符串或 None（不应展示时）。"""
    if val_float is None or thr_float is None:
        return None
    delta = val_float - thr_float
    # 对于 < 阈值的指标（低告警），delta 为负表示触发；对于 > 阈值的指标（高告警），delta 为正表示触发
    # 只在告警触发时展示 delta（理论上卡片里都是触发的，但做防御）
    if op == "<" and delta >= 0:
        return None
    if op == ">" and delta <= 0:
        return None
    # 百分比类指标用 pp 展示
    if mk in PCT_METRICS:
        delta_pct = delta * 100
        sign = "+" if delta_pct >= 0 else ""
        return f"▼ {sign}{delta_pct:.1f}%" if delta_pct < 0 else f"▲ +{delta_pct:.1f}%"
    else:
        sign = "+" if delta >= 0 else ""
        return f"▼ {sign}{delta:.1f}" if delta < 0 else f"▲ +{delta:.1f}"


def build_html(region, dataset_label, alerts_by_dim, now_str, date_str, total_alerts, no_alert=False, text_header=None, granularity="city"):
    """
    生成告警卡片 HTML。

    alerts_by_dim: dict of { dim_value: [ (metric_key, metric_cn, value_str, threshold_str, val_float, thr_float, op_str), ... ] }
    """

    # 状态颜色
    if no_alert:
        status_color = "#52c41a"
        status_icon = "✅"
        status_text = "All metrics normal, no anomalies detected"
    else:
        status_color = "#fa541c"
        status_icon = "⚠️"
        dim_count = len(alerts_by_dim)
        unit_s = "city" if granularity == "city" else "zone"
        unit_p = "cities" if granularity == "city" else "zones"
        status_text = f"{dim_count} {unit_s if dim_count == 1 else unit_p} with metric anomalies"

    # 按告警条数降序排列城市
    sorted_dims = sorted(alerts_by_dim.keys(), key=lambda d: len(alerts_by_dim[d]), reverse=True)

    # 构建维度告警 HTML
    dim_blocks = []
    for dim_val in sorted_dims:
        items = alerts_by_dim[dim_val]
        alert_count = len(items)
        metric_rows = ""
        for item in items:
            # 兼容新旧格式：7-tuple 或 4-tuple
            if len(item) >= 7:
                mk, mcn, val_str, thr_str, val_float, thr_float, op_str = item[:7]
            else:
                mk, mcn, val_str, thr_str = item[:4]
                val_float, thr_float, op_str = None, None, None

            # 计算 delta
            delta_html = ""
            if val_float is not None:
                delta_str = _compute_delta(mk, val_str, val_float, thr_float, op_str)
                if delta_str:
                    delta_html = f'<span class="metric-delta">{delta_str}</span>'

            metric_rows += f"""
            <div class="metric-item">
              <div class="metric-name">{mcn}</div>
              <div class="metric-detail">
                <span class="metric-value">{val_str}</span>
                {delta_html}
                <span class="metric-threshold">Threshold {thr_str}</span>
              </div>
            </div>"""

        dim_blocks.append(f"""
        <div class="dim-block">
          <div class="dim-header">
            <span class="dim-pin">📍</span>
            <span class="dim-label">{region} | {dim_val}</span>
            <span class="dim-badge">{alert_count}</span>
          </div>
          {metric_rows}
        </div>""")

    dims_html = "\n".join(dim_blocks) if dim_blocks else ""

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{
    height: auto;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
    background: #f5f5f5;
    padding: 16px;
  }}
  .card {{
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    overflow: hidden;
    max-width: 760px;
  }}
  .card-header {{
    background: linear-gradient(135deg, #ff6b35 0%, #d4380d 100%);
    padding: 16px 20px;
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .card-header .title {{
    color: #fff;
    font-size: 24px;
    font-weight: 600;
  }}
  .card-header .subtitle {{
    color: rgba(255,255,255,0.85);
    font-size: 16px;
    margin-top: 4px;
  }}
  .card-body {{
    padding: 16px 20px;
  }}
  .info-row {{
    display: flex;
    align-items: center;
    margin-bottom: 10px;
    font-size: 17px;
    color: #666;
  }}
  .info-row .label {{
    width: 96px;
    color: #999;
    flex-shrink: 0;
  }}
  .info-row .value {{
    color: #333;
  }}
  .status-bar {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 14px 16px;
    border-radius: 8px;
    margin: 14px 0;
    font-size: 18px;
    font-weight: 500;
  }}
  .status-bar.alert {{
    background: #fff2e8;
    color: #d4380d;
    border: 1px solid #ffbb96;
  }}
  .status-bar.ok {{
    background: #f6ffed;
    color: #389e0d;
    border: 1px solid #b7eb8f;
  }}
  .dim-block {{
    margin-top: 12px;
    border: 1px solid #f0f0f0;
    border-radius: 8px;
    overflow: hidden;
  }}
  .dim-header {{
    background: #fafafa;
    padding: 14px 16px;
    font-size: 17px;
    font-weight: 500;
    color: #333;
    border-bottom: 1px solid #f0f0f0;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .dim-pin {{
    font-size: 14px;
  }}
  .metric-item {{
    padding: 10px 14px;
    border-bottom: 1px solid #f5f5f5;
  }}
  .metric-item:last-child {{
    border-bottom: none;
  }}
  .metric-name {{
    font-size: 17px;
    color: #333;
    font-weight: 500;
    margin-bottom: 6px;
  }}
  .metric-detail {{
    display: flex;
    align-items: baseline;
    gap: 12px;
    font-size: 17px;
  }}
  .metric-value {{
    color: #fa541c;
    font-weight: 600;
    font-size: 22px;
  }}
  .metric-delta {{
    color: #E53935;
    font-weight: 600;
    font-size: 17px;
    margin-left: 4px;
  }}
  .metric-threshold {{
    color: #666666;
    font-size: 15px;
  }}
  .dim-badge {{
    background: transparent;
    color: #bfbfbf;
    font-size: 13px;
    font-weight: 600;
    padding: 1px 7px;
    border-radius: 10px;
    border: 1px solid #d9d9d9;
    margin-left: auto;
  }}
  .card-footer {{
    padding: 14px 20px;
    border-top: 1px solid #f0f0f0;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 15px;
    color: #999;
  }}
  .footer-dot {{
    width: 6px; height: 6px;
    background: #00d68f;
    border-radius: 50%;
  }}
</style>
</head>
<body>
  <div class="card">
    
    <div class="card-header">
      <div>
        <div class="title">{region} {dataset_label} Alerts</div>
        <div class="subtitle">Keeta Realtime Alert</div>
      </div>
    </div>
    <div class="card-body">
      <div class="info-row">
        <span class="label">Alert Time</span>
        <span class="value">{date_str} {now_str.split(' ')[-1] if ' ' in now_str else now_str}</span>
      </div>
      <div class="status-bar {"alert" if not no_alert else "ok"}">
        <span>{status_icon}</span>
        <span>{status_text}</span>
      </div>
      {dims_html}
    </div>
    <div class="card-footer">
      <div class="footer-dot"></div>
      <span>Keeta Data · Realtime Alert</span>
    </div>
  </div>
</body>
</html>"""
    return html


def render_html_to_png(html_content, output_path, width=800):
    """通过 CDP 浏览器将 HTML 渲染为 PNG 图片"""
    # 写临时 HTML 文件
    tmp_html = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
    tmp_html.write(html_content)
    tmp_html.close()
    html_path = tmp_html.name

    try:
        # 用 node 脚本通过 CDP 截图
        node_script = f"""
const http = require('http');
const fs = require('fs');

const CDP_HOST = 'localhost';
const CDP_PORT = 9222;

async function main() {{
  // 1. 获取可用 target
  const targets = await new Promise((resolve, reject) => {{
    http.get(`http://${{CDP_HOST}}:${{CDP_PORT}}/json/list`, (res) => {{
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => resolve(JSON.parse(data)));
    }}).on('error', reject);
  }});

  // 2. 创建新 tab (PUT method required for Node v24+)
  const newTarget = await new Promise((resolve, reject) => {{
    const url = `http://${{CDP_HOST}}:${{CDP_PORT}}/json/new?file://{html_path}`;
    const req = http.request(url, {{ method: 'PUT' }}, (res) => {{
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => resolve(JSON.parse(data)));
    }});
    req.on('error', reject);
    req.end();
  }});

  const wsUrl = newTarget.webSocketDebuggerUrl;
  const targetId = newTarget.id;

  // 3. WebSocket 连接 (using Node built-in WebSocket)
  const ws = new WebSocket(wsUrl);

  let msgId = 1;
  const pending = {{}};

  function send(method, params = {{}}) {{
    return new Promise((resolve) => {{
      const id = msgId++;
      pending[id] = resolve;
      ws.send(JSON.stringify({{ id, method, params }}));
    }});
  }}

  ws.addEventListener('message', (event) => {{
    const msg = JSON.parse(event.data);
    if (msg.id && pending[msg.id]) {{
      pending[msg.id](msg.result);
      delete pending[msg.id];
    }}
  }});

  await new Promise(r => ws.addEventListener('open', r));

  // 4. 设置视口宽度
  await send('Emulation.setDeviceMetricsOverride', {{
    width: {width},
    height: 800,
    deviceScaleFactor: 2,
    mobile: false
  }});

  // 5. 等待页面加载
  await send('Page.enable');
  await new Promise(r => setTimeout(r, 500));

  // 6. 获取页面实际内容高度（card bottom + body padding）
  const evalRes = await send('Runtime.evaluate', {{
    expression: '(document.querySelector(".card") || document.body).getBoundingClientRect().bottom + 16',
    returnByValue: true
  }});
  const contentHeight = Math.max(Math.ceil(evalRes.result.value || 600), 200);

  // 7. 更新视口高度为内容高度
  await send('Emulation.setDeviceMetricsOverride', {{
    width: {width},
    height: contentHeight,
    deviceScaleFactor: 2,
    mobile: false
  }});

  await new Promise(r => setTimeout(r, 200));

  // 8. 截图（精确裁剪到内容高度）
  const screenshot = await send('Page.captureScreenshot', {{
    format: 'png',
    clip: {{ x: 0, y: 0, width: {width}, height: contentHeight, scale: 1 }}
  }});

  fs.writeFileSync('{output_path}', Buffer.from(screenshot.data, 'base64'));

  // 9. 关闭 tab
  await new Promise((resolve, reject) => {{
    const req = http.request(`http://${{CDP_HOST}}:${{CDP_PORT}}/json/close/${{targetId}}`, {{ method: 'PUT' }}, (res) => {{
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => resolve(data));
    }});
    req.on('error', reject);
    req.end();
  }});

  ws.close();
  console.log('OK');
}}

main().catch(e => {{ console.error(e); process.exit(1); }});
"""
        node_file = tempfile.NamedTemporaryFile(suffix=".js", delete=False, mode="w")
        node_file.write(node_script)
        node_file.close()
        try:
            result = subprocess.run(
                ["node", node_file.name],
                capture_output=True, text=True, timeout=15
            )
        finally:
            try:
                os.unlink(node_file.name)
            except OSError:
                pass

        if result.returncode != 0:
            print(f"[ERROR] Node CDP screenshot failed: {result.stderr}", file=sys.stderr)
            return False

        return os.path.exists(output_path)

    finally:
        os.unlink(html_path)


def render_alert_card(region, dataset_id, alerts_by_dim, total_alerts):
    """
    高级接口：给定告警数据，渲染为 PNG 图片并返回路径。

    alerts_by_dim: dict { dim_value: [(metric_key, value_float, threshold_float, op_str), ...] }
    返回：PNG 文件路径 或 None
    """
    tz = REGION_TZ.get(region, timezone(timedelta(hours=8)))
    now = datetime.now(tz)
    now_str = now.strftime("%H:%M")
    date_str = now.strftime("%Y-%m-%d")

    dataset_labels = {
        "60038303": "City-Level Metrics",
        "62059270": "Zone-Level Metrics",
    }
    dataset_label = dataset_labels.get(dataset_id, "Metrics")

    no_alert = total_alerts == 0

    # 转换数据格式（7-tuple: metric_key, en_name, val_str, thr_str, val_float, thr_float, op_str）
    formatted = {}
    for dim_val, items in alerts_by_dim.items():
        formatted[dim_val] = []
        for mk, val, thr, op in items:
            en = METRIC_EN_NAMES.get(mk, mk)
            val_str = format_val(mk, val)
            thr_str = format_threshold(mk, op, thr)
            formatted[dim_val].append((mk, en, val_str, thr_str, val, thr, op))

    # 构建 text_header（渲染到图片顶部横幅）
    granularity_en = {"60038303": "City-Level", "62059270": "Zone-Level"}.get(dataset_id, "Unknown")
    text_header = f"🚨 Keeta Real-Time Updates: {region} | {granularity_en} | Threshold Alert"

    granularity = "zone" if dataset_id == "62059270" else "city"
    html = build_html(region, dataset_label, formatted, now_str, date_str, total_alerts, no_alert, text_header=text_header, granularity=granularity)

    output_path = f"/tmp/keeta_alert_{region}_{int(time.time())}_{os.getpid()}.png"
    success = render_html_to_png(html, output_path)

    if success:
        return output_path
    return None


# ── Feature 2 — 运力供需异动监控图片卡片 ──


def _f2_format_val(val, parse_type, metric_key=None):
    """格式化 Feature 2 指标值。

    特殊指标精度：
    - supply_demand_ratio / rider_load → 小数点后2位
    - undelivered_timeout_task_rate → 百分比保留2位小数
    """
    if val is None:
        return "-"
    if metric_key in ("last_20min_supply_demand_ratio", "rider_load", "supply_demand_ratio"):
        return f"{val:.2f}"
    if metric_key == "undelivered_timeout_task_rate":
        return f"{val*100:.2f}%"
    # 整数量纲指标（单量、人数等）始终显示为整数
    INTEGER_METRICS = ("push_ord_num", "delivered_task_num", "currently_online_courier_num",
                       "delivering_courier_num", "assigned_unaccepted_task_num",
                       "unaccepted_task_num", "schedule_courier_num",
                       "meal_preparation_delay_merchant_num")
    if metric_key in INTEGER_METRICS:
        return f"{int(val):,}"
    if parse_type == "rate":
        return f"{val*100:.1f}%"
    elif parse_type == "num":
        if abs(val) >= 1000:
            return f"{int(val):,}"
        return f"{val:.1f}"
    else:
        return f"{val:.2f}"


def _f2_format_wow(wow_change, parse_type=None):
    """格式化周同比。rate 类指标用 pp，num 类指标用 %。"""
    if wow_change is None:
        return "N/A"
    sign = "+" if wow_change >= 0 else ""
    if parse_type == "rate":
        return f"{sign}{wow_change*100:.1f}pp"
    return f"{sign}{wow_change*100:.1f}%"


def _f2_anomaly_signals_html(signals):
    """将异常信号翻译为中文 HTML"""
    translations = {
        "normal": "正常",
        "current": "当前值异常",
        "WoW": "周同比异常",
        "persistence": "持续性异常",
        # 新版中文 reasons（alert.py 直接输出中文）
        "当前值异常": "当前值异常",
        "周同比异常": "周同比异常",
        "环比波动": "环比波动",
        "持续性异常": "持续性异常",
    }
    parts = [translations.get(s, s) for s in signals]
    return " / ".join(parts)


def build_feature2_html(region, tense_zones, latest_slot, now_str, date_str, total_tense, dim_label_en="Zone-Level"):
    """
    生成 Feature 2 运力供需异动监控的 HTML 卡片。

    tense_zones: list of {zone, trigger_details, ref_a_details, ref_b_details, attributions, push_ord_num}
    dim_label_en: 粒度英文标签 ("Zone-Level" 或 "City-Level")
    """

    no_alert = not tense_zones
    # 根据粒度动态选择 "zone(s)" 或 "city/cities"
    is_city = "city" in dim_label_en.lower()
    unit_singular = "city" if is_city else "zone"
    unit_plural = "cities" if is_city else "zones"

    if no_alert:
        status_color = "#52c41a"
        status_icon = "✅"
        status_text = f"All {unit_plural} normal, no supply-demand tension detected"
    else:
        status_color = "#fa541c"
        status_icon = "⚠️"
        n_show = len(tense_zones)
        if total_tense > n_show:
            status_text = f"{total_tense} {unit_plural} with tension (showing Top {n_show})"
        else:
            status_text = f"{total_tense} {unit_singular if total_tense == 1 else unit_plural} with supply-demand tension"

    # 构建每个 zone 的 HTML
    zone_blocks = []
    for tz_info in tense_zones:
        zone     = tz_info["zone"]
        triggers = tz_info["trigger_details"]
        refs     = tz_info.get("ref_details", [])
        attribs  = tz_info["attributions"]
        push_vol = tz_info.get("push_ord_num", 0)

        # Zone header
        block = f"""
        <div class="zone-block">
          <div class="zone-header">
            <span class="zone-name">📍 {zone}</span>
            <span class="zone-vol">Pushed Orders (Last 10 min): <span class="vol-num">{int(push_vol):,}</span></span>
          </div>"""

        # Layer 1: Trigger metrics（全量展示，超阈值红点高亮，未超阈值灰点）
        block += """
          <div class="section">
            <div class="section-title">📊 Layer 1 — Trigger Metrics</div>"""
        for td in triggers:
            label = td.get("label", td["metric"])
            parse_type = td.get("parse", "num")
            if td.get("current") is not None:
                val_str = _f2_format_val(td["current"], parse_type, metric_key=td["metric"])
            else:
                val_str = "-"
            is_triggered = td.get("triggered", False)
            dot_class = "red" if is_triggered else "grey"
            row_class = "trigger" if is_triggered else "normal"
            # 阈值显示（触发时展示）
            threshold_html = ""
            if is_triggered:
                op = td.get("op", ">")
                threshold = td.get("threshold")
                if threshold is not None:
                    if parse_type == "rate":
                        thr_str = f"{threshold*100:.0f}%"
                    else:
                        thr_str = f"{threshold:g}"
                    threshold_html = f'<span class="m-threshold">({op} {thr_str})</span>'
            block += f"""
            <div class="metric-row {row_class}">
              <span class="dot {dot_class}"></span>
              <span class="m-label">{label}</span>
              <span class="m-val">{val_str}</span>
              {threshold_html}
            </div>"""
        block += "</div>"

        # Layer 2: 归因指标（分组展示：需求侧 / 运力总量 / 运力效率）
        block += """
          <div class="section layer2">
            <div class="section-title">🔍 Layer 2 — Attribution Metrics (Last 10 min)</div>"""
        if attribs:
            GROUP_ICONS = {"需求侧": "📈", "运力总量": "👥", "运力效率": "⚙️", "Demand": "📈", "Capacity Volume": "👥", "Capacity Efficiency": "⚙️"}
            current_group = None
            for a in attribs:
                group = a.get("group", "")
                if group and group != current_group:
                    current_group = group
                    icon = GROUP_ICONS.get(group, "•")
                    block += f"""
            <div class="group-label">{icon} {group}</div>"""
                label = a.get("label", a["metric"])
                parse_type = a.get("parse", "num")
                val_str = _f2_format_val(a["current"], parse_type, metric_key=a["metric"])
                # skip_wow: 历史基准不足时 WoW 显示为 -
                reasons = a.get("reasons", [])
                if any("skip_wow" in r for r in reasons):
                    wow_str = "-"
                else:
                    wow_str = _f2_format_wow(a.get("wow_change"), parse_type=parse_type)
                is_anomaly = a.get("anomaly", False)
                if is_anomaly:
                    attribution = a.get("attribution", "")
                    block += f"""
            <div class="metric-row attrib anomaly">
              <span class="dot red"></span>
              <span class="m-label">{label}</span>
              <span class="m-val">{val_str}</span>
              <span class="m-wow">WoW: {wow_str}</span>
              <span class="m-attrib-tag">Root Cause: {attribution}</span>
            </div>"""
                else:
                    block += f"""
            <div class="metric-row attrib">
              <span class="dot gray"></span>
              <span class="m-label">{label}</span>
              <span class="m-val">{val_str}</span>
              <span class="m-wow">WoW: {wow_str}</span>
            </div>"""
        else:
            block += """
            <div class="no-attrib">No clear attribution identified</div>"""
        block += "</div>"

        # Reference metrics（放在归因指标后面，灰色底色区分）
        if refs:
            block += """
          <div class="section ref-section">
            <div class="section-title">📌 Reference Metrics</div>"""
            for r in refs:
                label = r.get("label", r["metric"])
                parse_type = r.get("parse", "num")
                val_str = _f2_format_val(r["current"], parse_type, metric_key=r["metric"])
                wow_html = ""
                if r.get("show_wow"):
                    wow_str = _f2_format_wow(r.get("wow_change"))
                    wow_html = f'<span class="m-wow">WoW: {wow_str}</span>'
                block += f"""
            <div class="metric-row ref">
              <span class="dot grey"></span>
              <span class="m-label">{label}</span>
              <span class="m-val">{val_str}</span>
              {wow_html}
            </div>"""
            block += "</div>"

        block += "</div>"  # close zone-block
        zone_blocks.append(block)

    zones_html = "\n".join(zone_blocks)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
    background: #f5f5f5;
    padding: 16px;
  }}
  .card {{
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    overflow: hidden;
    max-width: 760px;
  }}
  .card-header {{
    background: linear-gradient(135deg, #ff6b35 0%, #d4380d 100%);
    padding: 16px 20px;
  }}
  .card-header .title {{
    color: #fff;
    font-size: 22px;
    font-weight: 600;
  }}
  .card-header .subtitle {{
    color: rgba(255,255,255,0.85);
    font-size: 15px;
    margin-top: 4px;
  }}
  .card-body {{
    padding: 16px 20px;
  }}
  .info-row {{
    display: flex;
    align-items: center;
    margin-bottom: 8px;
    font-size: 15px;
    color: #666;
  }}
  .info-row .label {{ width: 80px; color: #999; flex-shrink: 0; }}
  .info-row .value {{ color: #333; }}
  .status-bar {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 14px;
    border-radius: 8px;
    margin: 12px 0 16px 0;
    font-size: 16px;
    font-weight: 500;
  }}
  .status-bar.alert {{ background: #fff2e8; color: #d4380d; border: 1px solid #ffbb96; }}
  .status-bar.ok {{ background: #f6ffed; color: #389e0d; border: 1px solid #b7eb8f; }}

  /* Zone blocks */
  .zone-block {{
    border: 1px solid #e8e8e8;
    border-radius: 10px;
    margin-bottom: 24px;
    overflow: hidden;
  }}
  .zone-block + .zone-block {{
    border-top: none;
    position: relative;
  }}
  .zone-block + .zone-block::before {{
    content: '';
    display: block;
    height: 1px;
    background: #E0E0E0;
    position: absolute;
    top: -13px;
    left: 10%;
    right: 10%;
  }}
  .zone-header {{
    background: linear-gradient(135deg, #f5f5f5, #fafafa);
    padding: 12px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #e8e8e8;
  }}
  .zone-name {{ font-size: 17px; font-weight: 600; color: #333; }}
  .zone-vol {{ font-size: 13px; color: #999; background: #fff; padding: 2px 10px; border-radius: 12px; border: 1px solid #e8e8e8; }}
  .zone-vol .vol-num {{ font-size: 16px; color: #333; font-weight: 700; }}

  .section {{ padding: 10px 16px; border-bottom: 1px solid #f5f5f5; }}
  .section:last-child {{ border-bottom: none; }}
  .section-title {{ font-size: 14px; font-weight: 600; color: #555; margin-bottom: 8px; }}
  .section.layer2 .group-label {{ font-size: 13px; color: #666; font-weight: 600; margin: 8px 0 4px 0; padding-top: 6px; border-top: 1px dashed #e0e0e0; }}
  .section.layer2 .group-label:first-child {{ border-top: none; margin-top: 0; padding-top: 0; }}
  .section.ref-section {{ background: #F8F9FA; border-radius: 6px; margin-top: 6px; }}

  .metric-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 0;
    font-size: 14px;
    flex-wrap: wrap;
  }}
  .dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}
  .dot.red {{ background: #ff4d4f; }}
  .dot.green {{ background: #52c41a; }}
  .dot.orange {{ background: #fa8c16; }}
  .dot.grey {{ background: #999; }}
  .dot.gray {{ background: #999; }}
  .metric-row.attrib.anomaly {{ background: #fff1f0; border-radius: 4px; padding: 2px 4px; }}
  .m-attrib-tag {{ color: #999; font-size: 13px; margin-left: 8px; white-space: nowrap; }}
  .dot.blue {{ background: #1890ff; }}

  .m-label {{ font-weight: 500; color: #333; font-size: 14px; }}
  .m-val {{ color: #d4380d; font-weight: 700; font-size: 15px; }}
  .m-reason {{ color: #999; font-size: 13px; }}
  .m-threshold {{ color: #999; font-size: 13px; font-weight: 400; }}
  .m-wow {{ color: #BBBBBB; font-size: 13px; }}
  .m-signal {{ color: #888; font-size: 13px; font-style: italic; }}

  .metric-row.normal .m-val {{ color: #52c41a; font-size: 15px; }}
  .metric-row.ref .m-val {{ color: #333; font-size: 15px; }}
  .metric-row.attrib .m-val {{ color: #1890ff; font-size: 15px; }}

  .attrib-group {{ margin-bottom: 6px; }}
  .attrib-dir {{ font-size: 14px; font-weight: 500; color: #444; margin: 6px 0 4px 0; }}
  .no-attrib {{ font-size: 14px; color: #999; padding: 4px 0; }}

  .card-footer {{
    padding: 12px 20px;
    border-top: 1px solid #f0f0f0;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: #999;
  }}
  .footer-dot {{ width: 6px; height: 6px; background: #ff6b35; border-radius: 50%; }}
</style>
</head>
<body>
  <div class="card">
    <div class="card-header">
      <div class="title">{region} Supply-Demand Monitoring</div>
      <div class="subtitle">Keeta Supply-Demand Monitoring · {dim_label_en}</div>
    </div>
    <div class="card-body">
      <div class="info-row">
        <span class="label">Date</span>
        <span class="value">{date_str}</span>
      </div>
      <div class="info-row">
        <span class="label">Time</span>
        <span class="value">{now_str} (slot: {_slot_range(latest_slot)})</span>
      </div>
      <div class="status-bar {"alert" if not no_alert else "ok"}">
        <span>{status_icon}</span>
        <span>{status_text}</span>
      </div>
      {zones_html}
    </div>
    <div class="card-footer">
      <div class="footer-dot"></div>
      <span>Keeta Data · Supply-Demand Alert</span>
    </div>
  </div>
</body>
</html>"""
    return html


def render_feature2_card(region, tense_zones, latest_slot, total_tense, dim_label_en="Zone-Level"):
    """
    高级接口：给定 Feature 2 告警数据，渲染为 PNG 图片并返回路径。

    tense_zones: list of {zone, trigger_details, ref_a_details, ref_b_details, attributions, push_ord_num}
    dim_label_en: 粒度英文标签 ("Zone-Level" 或 "City-Level")
    返回：PNG 文件路径 或 None
    """
    tz = REGION_TZ.get(region, REGION_TZ.get("SA", timezone(timedelta(hours=3))))
    now = datetime.now(tz)
    now_str = now.strftime("%Y-%m-%d %H:%M")
    date_str = now.strftime("%Y-%m-%d")

    # 给 trigger_details / ref_details / attributions 补 label 字段（如果缺失）
    # 从 alert.py 传过来的数据通常没有 label，需要从 metric key 推断
    # 这里通过导入方式从 alert.py 获取 label 映射，或直接在此定义
    F2_LABELS = {
        "last_20min_supply_demand_ratio": "Supply-Demand Ratio (Last 20 min)",
        "undelivered_timeout_task_rate": "Timeout Task Rate (Undelivered)",
        "rider_load": "Rider Load",
        "delivery_dura_ordavg": "Avg Delivery Duration (min)",
        "assigned_unaccepted_timeout_task_num": "Assigned Unaccepted Timeout Tasks",
        # legacy keys
        "assigned_unaccepted_task_num": "Assigned Unaccepted Tasks",
        "unaccepted_task_num": "Unaccepted Tasks",
        "currently_online_courier_num": "Online Courier Num",
        "delivering_courier_num": "Delivering Courier Num",
        "online_rate_of_scheduled": "Online Rate of Scheduled",
        "online_courier_location_reporting_ratio": "Courier Location Rate",
        "one_on_one_assign_rejection_rate": "1-on-1 Assign Rejection Rate",
        "push_ord_num": "Pushed Orders",
        "courier_wait_meal_duration_pickup_task_num_avg": "Avg Courier Wait for Meal",
        "supply_demand_ratio": "Supply-Demand Ratio",
        "delivery_ider_utilization_rate": "Rider Utilization Rate",
    }

    for tz_info in tense_zones:
        for td in tz_info.get("trigger_details", []):
            if "label" not in td:
                td["label"] = F2_LABELS.get(td["metric"], td["metric"])
        for r in tz_info.get("ref_details", []):
            if "label" not in r:
                r["label"] = F2_LABELS.get(r["metric"], r["metric"])
        for a in tz_info.get("attributions", []):
            if "label" not in a:
                a["label"] = F2_LABELS.get(a["metric"], a["metric"])

    html = build_feature2_html(region, tense_zones, latest_slot, now_str, date_str, total_tense, dim_label_en=dim_label_en)

    output_path = f"/tmp/keeta_f2_alert_{region}_{int(time.time())}_{os.getpid()}.png"
    success = render_html_to_png(html, output_path)

    if success:
        return output_path
    return None


# ── Demo / 测试 ──

def demo():
    """用模拟数据生成一张 demo 卡片"""
    alerts_by_dim = {
        "Al Khiran": [
            ("last_1h_delivered_ord_me_ordavg", -6.98, -8.0, ">"),
            ("last_1h_delivered_ord_ata_ordavg", 38.08, 34.0, ">"),
        ],
        "Hawally": [
            ("last_1h_delivered_ord_ata_ordavg", 35.2, 34.0, ">"),
            ("last_1hour_online_courier_efficiency", 1.25, 1.1, ">"),
        ],
        "Jahra": [
            ("last_1h_delivered_ord_me_ordavg", -7.5, -8.0, ">"),
            ("last_1h_delivered_ord_ata_ordavg", 36.1, 34.0, ">"),
            ("last_1hour_online_courier_efficiency", 1.52, 1.4, ">"),
        ],
    }
    total = sum(len(v) for v in alerts_by_dim.values())

    path = render_alert_card("KW", "62059270", alerts_by_dim, total)
    if path:
        print(f"✅ Demo 图片已生成: {path}")
    else:
        print("❌ 渲染失败")


def demo_feature2():
    """用模拟数据生成一张 Feature 2 demo 卡片"""
    tense_zones = [
        {
            "zone": "Riyadh Central",
            "push_ord_num": 167,
            "trigger_details": [
                {"metric": "last_20min_supply_demand_ratio", "current": 3.57, "triggered": True, "parse": "num", "op": ">", "threshold": 0.6},
                {"metric": "undelivered_timeout_task_rate", "current": 0.12, "triggered": True, "parse": "rate", "op": ">", "threshold": 0.12},
                {"metric": "rider_load", "current": 0.93, "triggered": False, "parse": "num", "op": ">", "threshold": 0.8},
            ],
            "ref_details": [
                {"metric": "delivery_dura_ordavg", "current": 38.5, "show_wow": True, "wow_change": 0.12, "parse": "num"},
                {"metric": "assigned_unaccepted_timeout_task_num", "current": 23, "show_wow": True, "wow_change": 0.35, "parse": "num"},
            ],
            "attributions": [
                {"metric": "push_ord_num", "current": 167, "wow_change": 0.18, "anomaly": True, "reasons": ["周同比异常", "持续性异常"], "attribution": "需求激增", "group": "需求侧", "parse": "num"},
                {"metric": "currently_online_courier_num", "current": 45, "wow_change": -0.15, "anomaly": True, "reasons": ["周同比异常", "持续性异常"], "attribution": "运力总量不足", "group": "运力总量", "parse": "num"},
                {"metric": "online_rate_of_scheduled", "current": 0.72, "wow_change": -0.08, "anomaly": True, "reasons": ["当前值异常"], "attribution": "排班出勤不足", "group": "运力总量", "parse": "rate"},
                {"metric": "online_courier_location_reporting_ratio", "current": 0.88, "wow_change": -0.02, "anomaly": False, "reasons": [], "attribution": "", "group": "运力总量", "parse": "rate"},
                {"metric": "one_on_one_assign_rejection_rate", "current": 0.15, "wow_change": 0.03, "anomaly": False, "reasons": [], "attribution": "", "group": "运力效率", "parse": "rate"},
                {"metric": "delivering_courier_num", "current": 32, "wow_change": 0.05, "anomaly": False, "reasons": [], "attribution": "", "group": "运力效率", "parse": "num"},
                {"metric": "delivery_ider_utilization_rate", "current": 0.68, "wow_change": -0.03, "anomaly": False, "reasons": [], "attribution": "", "group": "运力效率", "parse": "rate"},
            ],

        },
        {
            "zone": "Jeddah North",
            "push_ord_num": 89,
            "trigger_details": [
                {"metric": "last_20min_supply_demand_ratio", "current": 2.85, "triggered": True, "parse": "num", "op": ">", "threshold": 0.6},
                {"metric": "undelivered_timeout_task_rate", "current": 0.08, "triggered": False, "parse": "rate", "op": ">", "threshold": 0.12},
                {"metric": "rider_load", "current": 1.12, "triggered": True, "parse": "num", "op": ">", "threshold": 0.8},
            ],
            "ref_details": [
                {"metric": "delivery_dura_ordavg", "current": 35.2, "show_wow": True, "wow_change": 0.05, "parse": "num"},
            ],
            "attributions": [
                {"metric": "push_ord_num", "current": 89, "wow_change": 0.08, "anomaly": False, "reasons": [], "attribution": "", "group": "需求侧", "parse": "num"},
                {"metric": "currently_online_courier_num", "current": 28, "wow_change": -0.20, "anomaly": True, "reasons": ["当前值异常", "周同比异常"], "attribution": "运力总量不足", "group": "运力总量", "parse": "num"},
                {"metric": "online_rate_of_scheduled", "current": 0.65, "wow_change": -0.12, "anomaly": True, "reasons": ["周同比异常", "持续性异常"], "attribution": "排班出勤不足", "group": "运力总量", "parse": "rate"},
                {"metric": "online_courier_location_reporting_ratio", "current": 0.91, "wow_change": 0.01, "anomaly": False, "reasons": [], "attribution": "", "group": "运力总量", "parse": "rate"},
                {"metric": "one_on_one_assign_rejection_rate", "current": 0.18, "wow_change": 0.06, "anomaly": True, "reasons": ["周同比异常"], "attribution": "骑手拒单", "group": "运力效率", "parse": "rate"},
                {"metric": "delivering_courier_num", "current": 20, "wow_change": -0.02, "anomaly": False, "reasons": [], "attribution": "", "group": "运力效率", "parse": "num"},
                {"metric": "delivery_ider_utilization_rate", "current": 0.55, "wow_change": -0.08, "anomaly": False, "reasons": [], "attribution": "", "group": "运力效率", "parse": "rate"},
            ],

        },
    ]

    path = render_feature2_card("SA", tense_zones, "14:30", total_tense=2, dim_label_en="Zone-Level")
    if path:
        print(f"✅ Feature 2 Demo 图片已生成: {path}")
    else:
        print("❌ Feature 2 渲染失败")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true")
    p.add_argument("--demo-f2", action="store_true")
    args = p.parse_args()
    if args.demo:
        demo()
    elif args.demo_f2:
        demo_feature2()
    else:
        p.print_help()
