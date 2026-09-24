#!/usr/bin/env python3
"""
Keeta 实时异动告警脚本

Feature 1 — 固定阈值告警：
  python3 alert.py --setup-cron --dataset 60038303 --regions SA --metrics all --interval 10 --push-daxiang
  python3 alert.py --setup-cron --dataset 62059270 --regions BH --metrics ontime_task_ratio,last_1h_delivered_ord_ontime_ratio --interval 10 --push-daxiang
  python3 alert.py --setup-cron ... --thresholds '{"ontime_task_ratio":0.85}' --dim-thresholds '{"Riyadh":{"ontime_task_ratio":0.84}}'

Feature 2 — 运力供需异动监控（统计异常检测，无固定阈值）：
  python3 alert.py --setup-cron --feature 2 --regions SA --interval 10 --push-daxiang
  python3 alert.py --setup-cron --feature 2 --regions SA,AE --interval 10 --push-daxiang --daxiang-target group:xxx

通用操作：
  python3 alert.py --setup-cron ... --dry-run          # 仅打印参数摘要，不写入配置
  python3 alert.py --cron-run --job-id ID              # 由 cron 调用（自动分派 Feature 1/2）
  python3 alert.py --stop-cron --job-id ID             # 删除指定定时任务
  python3 alert.py --list-jobs                         # 列出所有定时任务
  python3 alert.py --list-datasets                     # 列出所有已注册数据集
  python3 alert.py --print-defaults --dataset 60038303 # 打印指定数据集的默认阈值
  python3 alert.py --health-check                      # 自检：配置/依赖/凭证/cron注册
"""

import argparse, subprocess, json, sys, os, unicodedata, math, random, string, time
from datetime import datetime, timezone, timedelta
from collections import defaultdict, OrderedDict
from alert_config import REGION_TZ, REGION_TZ_NAMES, _slot_range

CRON_CONFIG_PATH  = os.path.expanduser("~/.openclaw/config/keeta-data-logistics-realtime-alert-config.json")
_LEGACY_CONFIG_PATH = os.path.expanduser("~/.openclaw/skills/keeta-data-logistics-realtime-alert/cron_config.json")
KEETA_DATA_QUERY_PATH    = os.path.expanduser("~/.openclaw/skills/keeta-data-query")
CLAW_GROUP_SPEAKER_PATH  = os.path.expanduser("~/.openclaw/skills/claw-group-speaker")
MIN_POLL_INTERVAL = 10  # 硬性下限（分钟）

# [TRACKING] kdata 调用计数器（逻辑查询粒度，在 _run_kdata_raw 入口递增）
_kdata_call_log: list = []

# [TRACKING] 埋点上报模块（导入失败时降级跳过）
try:
    from cli_logger import (
        report as _cli_logger_report,
        report_kdata_call as _cli_logger_report_kdata,
        report_feedback as _cli_logger_report_feedback,
    )
    _CLI_LOGGER_AVAILABLE = True
except ImportError:
    _CLI_LOGGER_AVAILABLE = False
    _cli_logger_report_kdata = None       # type: ignore
    _cli_logger_report_feedback = None    # type: ignore

# [TRACKING] cron-run 执行上下文（由 main() 在 cron-run 入口设置，供 kdata 函数读取）
_cron_context: dict = {}  # {"mis": ..., "session_id": ..., "job_id": ...}
# NOTE: 全局状态，单进程单次执行场景无问题。
# 若将来在同一进程多次调用（如测试框架），存在上下文污染风险；
# 届时可改为参数传递或 threading.local()。


def _report_log(
    mis: str,
    cli_command: str,
    status: str,
    cost_time: int,
    *,
    input_summary: str  = "",
    output_summary: str = "",
    error_msg: str      = "",
    error_type: str     = "",
    session_id: str     = "",
    job_id: str         = "",
) -> None:
    """上报埋点（委托给 cli_logger.report，导入失败时静默跳过）。"""
    if not _CLI_LOGGER_AVAILABLE:
        return
    try:
        _cli_logger_report(
            mis=mis, cli_command=cli_command, status=status, cost_time=cost_time,
            input_summary=input_summary, output_summary=output_summary,
            error_msg=error_msg, error_type=error_type,
            session_id=session_id, job_id=job_id,
        )
    except Exception as _e:
        print(f"[cli_logger][WARN] 上报异常: {_e}", file=sys.stderr)


def _get_mis() -> str:
    """获取当前用户 MIS（环境变量 → 未知）。"""
    for key in ("OPENCLAW_MIS", "OPENCLAW_OWNER_MIS", "AGENT_OWNER_ID", "KDATA_MIS", "MEITUAN_MIS"):
        v = os.environ.get(key, "").strip()
        if v:
            return v
    return "unknown"


def _mtskills_install(skill_name, extra_init=None):
    """通用 mtskills 安装函数，安装后可选执行初始化。"""
    try:
        r = subprocess.run(
            ["mtskills", "i", skill_name, "--target-dir", os.path.expanduser("~/.openclaw/skills")],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode == 0:
            print(f"[INFO] {skill_name} 安装成功", file=sys.stderr)
            if extra_init:
                extra_init()
            return True
        print(f"[ERROR] {skill_name} 安装失败: {r.stderr or r.stdout}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("[ERROR] mtskills 未安装，请先执行: npm install -g @mtfe/mtskills@latest --registry=http://r.npm.sankuai.com", file=sys.stderr)
        return False


def ensure_keeta_data_query():
    """检查 keeta-data-query skill 是否已安装，未安装则通过 mtskills 自动安装。"""
    if os.path.isdir(KEETA_DATA_QUERY_PATH) and os.path.exists(os.path.join(KEETA_DATA_QUERY_PATH, "SKILL.md")):
        return True
    print("[INFO] 前置依赖 keeta-data-query 未安装，正在通过 mtskills 安装...", file=sys.stderr)

    def _init():
        init_script = os.path.join(KEETA_DATA_QUERY_PATH, "scripts", "kdata.py")
        if os.path.exists(init_script):
            subprocess.run(["python3", init_script, "init"], capture_output=True, text=True, timeout=60)

    return _mtskills_install("keeta-data-query", extra_init=_init)


def ensure_claw_group_speaker():
    """检查 claw-group-speaker skill 是否已安装，未安装则通过 mtskills 自动安装。"""
    if os.path.isdir(CLAW_GROUP_SPEAKER_PATH) and os.path.exists(os.path.join(CLAW_GROUP_SPEAKER_PATH, "SKILL.md")):
        return True
    print("[INFO] 前置依赖 claw-group-speaker 未安装，正在通过 mtskills 安装...", file=sys.stderr)
    return _mtskills_install("claw-group-speaker")

DATASETS = {
    "60038303": {
        "label":     "实时告警推送（业务城市粒度）",
        "dim_field": "op_city_name",
        "dim_label": "业务城市",
        "dim_label_en": "City-Level",
    },
    "62059270": {
        "label":     "实时告警推送（配送区域粒度）",
        "dim_field": "delivery_area_name",
        "dim_label": "配送区域",
        "dim_label_en": "Zone-Level",
    },
    "60051927": {
        "label":     "运力出勤监控-供需&归因（支持城市/配送区域粒度）",
        "dim_field": "delivery_area_name",  # 功能2默认 zone 粒度；功能3 city 粒度时传 op_city_name
        "dim_label": "配送区域",
        "dim_label_en": "Zone-Level",
    },
    "60009475": {
        "label":     "运力出勤监控-排班出勤（配送区域粒度）",
        "dim_field": "delivery_area_name",
        "dim_label": "配送区域",
        "dim_label_en": "Zone-Level",
    },
}

ALL_METRICS = {
    "ontime_task_ratio":                          {"label": "C端准时率",                         "en": "On-time Rate (C)",                       "op": "<", "parse": "rate", "format": "pct2", "thr_city": 0.87,  "thr_area": 0.87},
    "bod_ontime_task_ratio":                      {"label": "大订单C端准时率",                   "en": "Large Order On Time Rate (C)",           "op": "<", "parse": "rate", "format": "pct2", "thr_city": 0.86,  "thr_area": 0.86},
    "delivering_upcoming_timeout_task_ratio":     {"label": "配送中即将超时任务单占比",           "en": "Timeout Rate (Delivering Tasks)",        "op": ">", "parse": "rate", "format": "pct2", "thr_city": 0.12,  "thr_area": 0.12},
    "last_1h_delivered_ord_ontime_ratio":         {"label": "最新一小时配送完成订单C端准时率",   "en": "L1H On Time Rate (C)",                   "op": "<", "parse": "rate", "format": "pct2", "thr_city": 0.88,  "thr_area": 0.88},
    "last_1h_delivered_bod_ord_ontime_ratio":     {"label": "最新一小时配送完成大订单C端准时率", "en": "L1H Large Order On Time Rate (C)",       "op": "<", "parse": "rate", "format": "pct2", "thr_city": 0.83,  "thr_area": 0.83},
    "last_1h_delivered_ord_me_ordavg":            {"label": "最近一小时完成订单单均ME",           "en": "L1H Avg ME (min)",                       "op": ">", "parse": "num",  "format": "f2",   "thr_city": -6.0,  "thr_area": -6.0},
    "last_1h_delivered_ord_ata_ordavg":           {"label": "最近一小时完成订单单均配送时长(分)","en": "L1H ATA (min)",                          "op": ">", "parse": "num",  "format": "f1",   "thr_city": 36.0,  "thr_area": 36.0},
    "last_2h_cancel_after_grab_ratio":            {"label": "最近两小时接单后取消率",             "en": "L2H Cancellation Rate (Picked-up Task)", "op": ">", "parse": "rate", "format": "pct2", "thr_city": 0.05,  "thr_area": 0.05},
    "precipitation_hourly":                       {"label": "降水量(mm)",                        "en": "Precipitation (mm)",                     "op": ">", "parse": "num",  "format": "f1",   "thr_city": 0.0,   "thr_area": 0.0},
    "last_1hour_online_courier_efficiency":       {"label": "最近一小时在线骑手效率",             "en": "L1H Online Courier Efficiency",          "op": ">", "parse": "num",  "format": "f2",   "thr_city": 1.5,   "thr_area": 1.5},
    "meal_preparation_delay_merchant_num":        {"label": "卡餐上报商家数",                     "en": "Meal Preparation Delay Merchant Num",    "op": ">", "parse": "num",  "format": "int",  "thr_city": 100,   "thr_area": 10},
    "meal_preparation_delay_merchant_ratio":      {"label": "卡餐上报商家占比",                   "en": "Meal Preparation Delay Merchant Ratio",  "op": ">", "parse": "rate", "format": "pct2", "thr_city": 0.1,   "thr_area": 0.1},
    "unaccepted_task_num": {
        "label": "积压任务单数",
        "en": "Unaccepted Tasks",
        "op": ">",
        "parse": "num",
        "format": "int",
        "thr_city": 100,
        "thr_area": 10,
    },
    "last_20min_meal_waiting_dura_task_avg": {
        "label": "近20分钟平均等餐时长",
        "en": "Avg Time of Meal Waiting (Last 20min)",
        "op": ">",
        "parse": "num",
        "format": "f1",
        "thr_city": 12.0,
        "thr_area": 12.0,
    },
}

REGIONS = ["SA", "AE", "QA", "KW", "BH", "HK", "BR"]
# 功能1 阈值告警支持的地区（数据集 60038303/62059270 不含 HK）
FEATURE1_REGIONS = ["SA", "AE", "QA", "KW", "BH", "BR"]

# ── 城市名中文→英文映射（用于 text_header 统一展示英文） ──────
# 硬编码作为 fallback，优先从 data/city_name_map.json 加载（来源：mart_sailor_global.dim_city_snap_d）
_CITY_MAP_FALLBACK_ZH_TO_EN = {
    # SA
    "利雅得": "Riyadh", "吉达": "Jeddah", "麦加": "Makkah", "麦地那": "Madinah",
    "达曼": "Dammam", "哈萨": "Al Ahsa", "塔伊夫": "Al Taif", "布赖代": "Buraydah",
    "塔布克": "Tabuk", "海尔": "Hail", "艾卜哈": "Abha", "吉赞": "Jazan",
    "纳季兰": "Najran", "延布": "Yanbu", "朱拜勒": "Al Jubail",
    "阿尔卡吉": "Al Kharj", "哈费尔巴廷": "Hafar Al Batin",
    # AE
    "迪拜": "Dubai", "阿布扎比": "Abu Dhabi", "沙迦市": "Sharjah City",
    "艾恩": "Al Ain", "阿治曼市": "Ajman City", "哈伊马角市": "Ras Al Khaimah City",
    "富查伊拉市": "Fujairah City", "乌姆盖万市": "Umm Al Quwain City",
    # QA
    "多哈": "Doha",
    # KW
    "科威特市": "Kuwait City",
    # BH
    "麦纳麦": "Manama",
    # HK
    "香港": "Hong Kong",
    # BR
    "圣保罗": "Sao Paulo", "桑托斯": "Santos",
}

def _load_city_name_map():
    """从 data/city_name_map.json 加载城市名映射，失败时使用硬编码 fallback。"""
    map_path = os.path.join(os.path.dirname(__file__), "..", "data", "city_name_map.json")
    try:
        with open(os.path.normpath(map_path), encoding="utf-8") as _f:
            _d = json.load(_f)
            zh2en = _d.get("zh_to_en", {})
            en2zh = _d.get("en_to_zh", {})
            if zh2en:
                return zh2en, en2zh
    except Exception:
        pass
    # fallback：使用硬编码并自动生成反向映射
    return _CITY_MAP_FALLBACK_ZH_TO_EN, {v: k for k, v in _CITY_MAP_FALLBACK_ZH_TO_EN.items()}

CITY_CN_TO_EN, _CITY_EN_TO_CN_FROM_FILE = _load_city_name_map()

def _to_en(name):
    """将城市/区域名转为英文（如有映射），否则原样返回。"""
    return CITY_CN_TO_EN.get(name, name)

# 反向映射：英文 → 中文（直接使用文件中的 en_to_zh，或由 CITY_CN_TO_EN 自动生成）
_CITY_EN_TO_CN = _CITY_EN_TO_CN_FROM_FILE

def _to_zh(name):
    """将城市/区域名转为中文（如有映射），否则原样返回。
    用于 dim_thresholds key 的标准化：兼容用户输入英文或中文 key。
    """
    return _CITY_EN_TO_CN.get(name, name)

def _normalize_dim_thresholds(raw: dict) -> dict:
    """将 dim_thresholds 的 key 统一转为英文，兼容中文输入。
    e.g. {"阿布扎比": {...}} → {"Abu Dhabi": {...}}
    """
    if not raw:
        return raw
    return {_to_en(k): v for k, v in raw.items()}

# ── 时间窗口检查 ─────────────────────────────────────────

def parse_active_hours(spec):
    """解析 active_hours 字符串为 [(start_minutes, end_minutes), ...] 列表。
    格式: "HH:MM-HH:MM,HH:MM-HH:MM"，24:00 等价于 1440。
    默认 "00:00-24:00" 表示全天。
    """
    if not spec or spec.strip() == "00:00-24:00":
        return None  # None 表示全天，不做过滤
    windows = []
    for seg in spec.split(","):
        seg = seg.strip()
        if not seg:
            continue
        parts = seg.split("-")
        if len(parts) != 2:
            print(f"[WARN] active_hours 格式错误，忽略: {seg}", file=sys.stderr)
            continue
        start_str, end_str = parts[0].strip(), parts[1].strip()
        try:
            sh, sm = map(int, start_str.split(":"))
            eh, em = map(int, end_str.split(":"))
            start_min = sh * 60 + sm
            end_min   = eh * 60 + em
            if end_min == 0:
                end_min = 1440  # 00:00 结尾视为 24:00
            windows.append((start_min, end_min))
        except (ValueError, IndexError):
            print(f"[WARN] active_hours 格式错误，忽略: {seg}", file=sys.stderr)
    return windows if windows else None


def is_within_active_hours(windows, region):
    """检查当前 region 本地时间是否在 active_hours 窗口内。
    windows=None 表示全天活跃，直接返回 True。
    """
    if windows is None:
        return True
    tz = REGION_TZ.get(region)
    if not tz:
        return True  # 未知地区不限制
    now_local = datetime.now(tz)
    cur_min = now_local.hour * 60 + now_local.minute
    for start_min, end_min in windows:
        if start_min <= end_min:
            # 正常范围，如 12:00-14:00（左闭右闭）
            if start_min <= cur_min <= end_min:
                return True
        else:
            # 跨午夜，如 22:00-06:00（左闭右闭）
            if cur_min >= start_min or cur_min <= end_min:
                return True
    return False


# ── 将军令 Region 权限校验 ────────────────────────────────

def check_region_permission(mis_id: str) -> dict:
    """
    通过将军令 API 检查用户是否有 sailor_data_tools Region 权限。

    原理：查询 sailor_data_tools_bu_hq_region 节点下的授权记录，
    tn > 0 表示用户（通过个人/用户组/组织任意方式）有 Region 权限。

    Returns:
        {"has_permission": bool, "error": str|None}
    """
    # 通过 agent-browser 在将军令页面内 fetch（借助浏览器 cookie）
    body = json.dumps({
        "permSource": 0,
        "resources": [{"name": "Region", "code": "sailor_data_tools_bu_hq_region"}],
        "system": "sailor_data_tools",
        "resourceType": "bu",
        "misId": mis_id
    })
    # JS 代码：在页面内用 axios 发 POST（axios 已全局加载）
    js_code = (
        "axios.post('/newapi/permission/person/query',"
        + body
        + ",{params:{sn:1,cn:1,ssoprotect:1},headers:{'Content-Type':'application/json'}})"
        + ".then(function(r){return JSON.stringify(r.data);})"
        + ".catch(function(e){return 'ERR:'+JSON.stringify(e.response&&e.response.data);})"
    )

    # 先确保将军令页面已打开（tab 存在）
    try:
        import subprocess as _sp, time as _time

        # 检查 CDP
        import urllib.request as _ur
        tabs_resp = _ur.urlopen("http://localhost:9222/json", timeout=5).read()
        tabs = json.loads(tabs_resp)
        auth_tab = next((t for t in tabs if "auth.keetapp.com" in t.get("url", "")), None)

        if not auth_tab:
            # 开一个新 tab 打开将军令
            _ur.urlopen(
                _ur.Request(
                    "http://localhost:9222/json/new?https://auth.keetapp.com/auth-query",
                    method="PUT"
                ), timeout=5
            ).read()
            _time.sleep(8)
            tabs_resp2 = _ur.urlopen("http://localhost:9222/json", timeout=5).read()
            tabs2 = json.loads(tabs_resp2)
            auth_tab = next((t for t in tabs2 if "auth.keetapp.com" in t.get("url", "")), None)

        if not auth_tab:
            return {"has_permission": None, "error": "无法打开将军令页面，请确保浏览器已登录"}

        ws_url = auth_tab["webSocketDebuggerUrl"]

        # 通过 CDP WebSocket 执行 JS
        import asyncio as _asyncio
        try:
            import websockets as _ws
        except ImportError:
            return {"has_permission": None, "error": "缺少 websockets 库，跳过权限校验"}

        async def _eval():
            async with _ws.connect(ws_url, max_size=10 * 1024 * 1024) as websocket:
                msg = {
                    "id": 9901,
                    "method": "Runtime.evaluate",
                    "params": {"expression": js_code, "awaitPromise": True, "returnByValue": True}
                }
                import time as _time
                await websocket.send(json.dumps(msg))
                _start = _time.monotonic()
                _timeout = 20.0
                while True:
                    _elapsed = _time.monotonic() - _start
                    _remain = _timeout - _elapsed
                    if _remain <= 0:
                        return ""
                    resp = await _asyncio.wait_for(websocket.recv(), timeout=_remain)
                    data = json.loads(resp)
                    if data.get("id") == 9901:
                        return data.get("result", {}).get("result", {}).get("value", "")

        raw = _asyncio.run(_eval())
        if not raw or raw.startswith("ERR:"):
            return {"has_permission": None, "error": f"权限查询接口异常: {raw}"}

        result = json.loads(raw)
        if result.get("status") != 200:
            return {"has_permission": None, "error": f"将军令返回异常: {result.get('message', '')}"}

        tn = result.get("content", {}).get("tn", 0)
        return {"has_permission": tn > 0, "error": None}

    except Exception as e:
        return {"has_permission": None, "error": str(e)}


def require_region_permission(mis_id: str, regions: list):
    """
    校验用户的 Region 权限。
    无权限时打印错误信息并 sys.exit(1)。
    权限查询异常时打印警告但不阻断流程（降级通过）。
    """
    print(f"[INFO] 正在校验 Region 权限（境外数据应用 sailor_data_tools_bu_hq_region）...", file=sys.stderr)
    result = check_region_permission(mis_id)

    if result["error"] or result["has_permission"] is None:
        reason = result["error"] or "权限查询结果为空"
        print(f"[WARN] 权限校验跳过（{reason}）", file=sys.stderr)
        return  # 降级：查询失败不阻断

    if not result["has_permission"]:
        print(
            f"[ERROR] 无对应Region权限，请重新进行Region选择。\n"
            f"        当前用户 {mis_id} 在将军令 系统: 境外数据应用 sailor_data_tools / 资源 sailor_data_tools_bu_hq_region 下无 Region 权限。\n"
            f"        请前往 https://auth.keetapp.com 申请权限后重试。",
            file=sys.stderr
        )
        sys.exit(1)

    print(f"[INFO] 权限校验通过 ✓", file=sys.stderr)


# ── 工具函数 ──────────────────────────────────────────────

def get_default_threshold(key, dataset_id):
    m = ALL_METRICS[key]
    return m["thr_area"] if dataset_id == "62059270" else m["thr_city"]


def parse_rate(val):
    if val is None or val == "-" or val == "": return 0.0
    if isinstance(val, str):
        if val.endswith("%"): return float(val.rstrip("%")) / 100
        if val.strip() == "-": return 0.0
    return float(val)


def parse_num(val):
    if val is None or val == "-" or val == "": return 0.0
    if isinstance(val, str):
        cleaned = val.replace(",", "").strip()
        if not cleaned or cleaned == "-": return 0.0
        return float(cleaned)
    return float(val)


def get_value(row, key):
    """解析指标值并过滤占位值。
    数据集在不满足前置条件（如单量不足）时会返回占位值：
      - 率类指标（准时率等）：默认 999 → 过滤 val >= 9
      - 配送中即将超时占比：默认 0   → 过滤 val == 0
      - ME/ATA/取消率/骑手效率/卡餐商家数：默认 -999 → 过滤 val <= -999
      - 卡餐商家占比：无前置条件，不额外过滤
    返回 None 表示占位值，调用方应跳过。
    """
    m   = ALL_METRICS[key]
    raw = row.get(key, 0)
    val = parse_rate(raw) if m["parse"] == "rate" else parse_num(raw)
    # 高占位值过滤（率类 >=9 即 900%+，数值类 >=9000）
    if m["parse"] == "rate" and val >= 9.0:    return None
    if m["parse"] == "num"  and val >= 9000.0: return None
    # 低占位值过滤（-999 系列）
    if m["parse"] == "num"  and val <= -999.0: return None
    if m["parse"] == "rate" and val <= -999.0: return None
    # 率类指标 val==0 视为占位值（前置条件不满足时数据集返回 0）
    # meal_preparation_delay_merchant_ratio 无前置条件，0 是有效值；precipitation_hourly 为 num 类型，不进入此分支
    if m["parse"] == "rate" and val == 0.0 and key not in ("meal_preparation_delay_merchant_ratio",):
        return None
    # ME/ATA val==0 视为无效（低单量时段无完成订单，数据集返回 0）
    if key in ("last_1h_delivered_ord_me_ordavg", "last_1h_delivered_ord_ata_ordavg") and val == 0.0:
        return None
    # 配送中即将超时占比：默认占位值为 0，但上面率类==0已覆盖
    return val


def format_value(key, val):
    fmt = ALL_METRICS[key]["format"]
    if fmt == "pct2": return f"{val*100:.1f}%"
    elif fmt == "f2":  return f"{val:.2f}"
    elif fmt == "f1":  return f"{val:.1f}"
    else:              return f"{int(val):,}"


def str_width(s):
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s)


# ── cron_config 读写 ─────────────────────────────────────

def _migrate_legacy_config():
    """如果新路径不存在但旧路径存在，自动迁移（兼容已有用户）"""
    if not os.path.exists(CRON_CONFIG_PATH) and os.path.exists(_LEGACY_CONFIG_PATH):
        try:
            os.makedirs(os.path.dirname(CRON_CONFIG_PATH), exist_ok=True)
            import shutil
            shutil.copy2(_LEGACY_CONFIG_PATH, CRON_CONFIG_PATH)
            print(f"[INFO] 配置已从旧路径迁移: {_LEGACY_CONFIG_PATH} → {CRON_CONFIG_PATH}")
            os.rename(_LEGACY_CONFIG_PATH, _LEGACY_CONFIG_PATH + '.bak')
            print(f"[INFO] 旧配置已备份至 {_LEGACY_CONFIG_PATH}.bak")
        except (OSError, IOError) as e:
            # 磁盘满/权限不足等情况：降级使用旧路径，不阻塞主流程
            print(f"[WARN] 配置迁移失败（将继续使用旧路径）: {e}", file=sys.stderr)


def load_cron_config():
    _migrate_legacy_config()
    if os.path.exists(CRON_CONFIG_PATH):
        with open(CRON_CONFIG_PATH) as f:
            return json.load(f)
    # fallback: 迁移失败时尝试读旧路径
    if os.path.exists(_LEGACY_CONFIG_PATH):
        with open(_LEGACY_CONFIG_PATH) as f:
            return json.load(f)
    return {"jobs": []}


def save_cron_config(cfg):
    os.makedirs(os.path.dirname(CRON_CONFIG_PATH), exist_ok=True)
    with open(CRON_CONFIG_PATH, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    # 写完配置后自动刷新城市名映射缓存（T-1 数据）
    _refresh_city_map_async()


def _refresh_city_map_async():
    """异步刷新城市名映射缓存。
    在创建/修改任务写入 config 后自动触发，失败不影响主流程。
    冷却机制：距上次更新不足 24 小时则跳过（城市名映射为 T-1 离线数据，每天最多刷一次即可）。
    """
    update_script = os.path.join(os.path.dirname(__file__), "update_city_map.py")
    if not os.path.exists(update_script):
        return
    # 冷却检查：距上次更新不足 24 小时则跳过
    city_map_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "city_name_map.json")
    if os.path.exists(city_map_path):
        mtime = os.path.getmtime(city_map_path)
        if time.time() - mtime < 86400:
            return
    try:
        subprocess.Popen(
            [sys.executable, update_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as _e:
        print(f"[city_map] 刷新启动失败（不影响任务）: {_e}", file=sys.stderr)


# ── 参数解析辅助 ─────────────────────────────────────────

def resolve_metrics(metrics_arg, dataset_id):
    """解析 --metrics 参数，支持 'all' 或逗号分隔的字段名列表"""
    if not metrics_arg or metrics_arg.strip().lower() == "all":
        return list(ALL_METRICS.keys())
    keys = [k.strip() for k in metrics_arg.split(",") if k.strip()]
    invalid = [k for k in keys if k not in ALL_METRICS]
    if invalid:
        print(f"[ERROR] 未知指标: {', '.join(invalid)}", file=sys.stderr)
        print(f"  可用指标: {', '.join(ALL_METRICS.keys())}", file=sys.stderr)
        sys.exit(1)
    return keys


def resolve_thresholds(thresholds_arg, metrics, dataset_id):
    """解析 --thresholds，未指定的指标使用数据集默认值"""
    overrides = {}
    if thresholds_arg:
        try:
            overrides = json.loads(thresholds_arg)
        except json.JSONDecodeError as e:
            print(f"[ERROR] --thresholds JSON 解析失败: {e}", file=sys.stderr)
            sys.exit(1)
    result = {}
    for k in metrics:
        if k in overrides:
            result[k] = float(overrides[k])
        else:
            result[k] = get_default_threshold(k, dataset_id)
    return result


def resolve_dim_thresholds(dim_thresholds_arg):
    """解析 --dim-thresholds JSON，并将 key 统一标准化为中文城市名（兼容英文输入）。"""
    if not dim_thresholds_arg:
        return {}
    try:
        raw = json.loads(dim_thresholds_arg)
        return _normalize_dim_thresholds(raw)
    except json.JSONDecodeError as e:
        print(f"[ERROR] --dim-thresholds JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)


# ── 配置任务（参数驱动） ───────────────────────────────────

def setup_cron(args):
    feature = getattr(args, "feature", 1) or 1

    # ── Feature 2: 运力供需异动监控（简化配置） ──
    if feature == 2:
        regions = [r.strip().upper() for r in args.regions.split(",") if r.strip()]
        invalid_regions = [r for r in regions if r not in REGIONS]
        if invalid_regions:
            print(f"[ERROR] 未知地区: {', '.join(invalid_regions)}，可选: {', '.join(REGIONS)}", file=sys.stderr)
            sys.exit(1)

        # ── Region 权限校验 ──
        mis_id = getattr(args, "mis_id", None) or ""
        require_region_permission(mis_id, regions)

        interval = args.interval
        if interval < MIN_POLL_INTERVAL:
            print(f"[ERROR] 轮询间隔 {interval} 分钟低于最小限制 {MIN_POLL_INTERVAL} 分钟", file=sys.stderr)
            sys.exit(1)

        push_daxiang   = args.push_daxiang
        daxiang_target = args.daxiang_target
        owner_uid      = args.owner_uid
        # 只要配了推送目标，自动开启推送（防止漏传 --push-daxiang）
        if daxiang_target and not push_daxiang:
            push_daxiang = True

        # 粒度选择
        f2_gran = getattr(args, "f2_granularity", "zone") or "zone"
        gran_info = F2_GRANULARITY[f2_gran]
        f2_dim_field    = gran_info["dim_field"]
        f2_dim_label    = gran_info["dim_label"]
        f2_dim_label_en = gran_info["dim_label_en"]

        active_hours = getattr(args, "active_hours", "00:00-24:00") or "00:00-24:00"

        # 解析阈值覆盖（功能2）
        f2_threshold_overrides = None
        if args.thresholds:
            try:
                f2_threshold_overrides = json.loads(args.thresholds) if isinstance(args.thresholds, str) else args.thresholds
            except (json.JSONDecodeError, TypeError):
                f2_threshold_overrides = None

        # 解析差异化阈值（功能2：按城市/区域差异化）
        f2_dim_thresholds = resolve_dim_thresholds(getattr(args, "dim_thresholds", None))
        if f2_dim_thresholds:
            # 校验白名单
            allowed = set(FEATURE2_L1_TRIGGER_KEYS)
            bad = {k for v in f2_dim_thresholds.values() for k in (v or {}) if k not in allowed}
            if bad:
                print(f"[ERROR] --dim-thresholds 包含 Feature 2 不支持的指标: {bad}，允许: {allowed}", file=sys.stderr)
                sys.exit(1)

        print(f"\n===== Feature 2 运力供需异动监控 配置摘要 =====")
        print(f"  功能:     Feature 2（统计异常检测，无固定阈值）")
        print(f"  数据集:   60051927 + 60009475（供需 + 排班出勤）")
        print(f"  粒度:     {f2_dim_label}（{f2_dim_field}）[{f2_dim_label_en}]")
        print(f"  地区:     {', '.join(regions)}")
        print(f"  Layer 1:  {len(FEATURE2_L1_TRIGGER_KEYS)} 个触发指标 + {len(FEATURE2_L1_REF_KEYS)} 个参考指标")
        print(f"  Layer 2:  {len(FEATURE2_LAYER2_METRICS)} 个归因指标")
        print(f"  轮询间隔: 每 {interval} 分钟（整点对齐）")
        print(f"  活跃时段: {active_hours}")
        print(f"  推大象:   {'是' if push_daxiang else '否'}{' → ' + daxiang_target if daxiang_target else ''}")
        if owner_uid:
            print(f"  接收人:   UID {owner_uid}")
        if f2_dim_thresholds:
            print(f"  差异阈值: {list(f2_dim_thresholds.keys())}")

        # 可选：推单量过滤门槛
        f2_min_push_ord_num = None
        _raw_min = getattr(args, "min_push_ord_num", None)
        if _raw_min is not None:
            f2_min_push_ord_num = int(_raw_min)
            print(f"  推单量门槛: push_ord_num < {f2_min_push_ord_num} 的城市/区域不触发告警")

        if args.dry_run:
            print("\n[DRY-RUN] 参数验证通过，未写入配置。\n")
            return

        _suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        job_id = f"f2-{'-'.join(r.lower() for r in regions)}-{datetime.now().strftime('%m%d%H%M')}-{_suffix}"
        print(f"\n  任务 ID:  {job_id}")

        job = {
            "id":           job_id,
            "name":         f"{'_'.join(regions)} 运力出勤监控",
            "feature":      2,
            "regions":      regions,
            "dim_field":    f2_dim_field,
            "dim_label":    f2_dim_label,
            "dim_label_en": f2_dim_label_en,
            "active_hours": active_hours,
            "thresholds":      f2_threshold_overrides,
            "dim_thresholds":  f2_dim_thresholds or None,
            "min_push_ord_num": f2_min_push_ord_num,
            "poll":            {"interval_min": interval, "push_daxiang": push_daxiang, "daxiang_target": daxiang_target},
            "owner_uid":    owner_uid,
            "mis_id":       mis_id or _get_mis(),
            "configured_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        }
        if job["mis_id"] == "unknown":
            print("[WARN] 无法自动获取 MIS，建议重新 setup 时传入 --mis-id <your_mis> 以便埋点归因", file=sys.stderr)
        cfg = load_cron_config()
        if owner_uid:
            cfg["owner_uid"] = owner_uid
        cfg["jobs"].append(job)
        save_cron_config(cfg)
        print(f"[INFO] 配置已保存到 {CRON_CONFIG_PATH}")
        register_cron(interval, job_id, regions=regions, daxiang_target=daxiang_target, owner_uid=owner_uid, feature=2)
        print(f"\n✅ Feature 2 告警任务 [{job_id}] 已成功注册！\n")
        return job_id

    # ── Feature 3: 商家出餐体验异动告警 ──
    if feature == 3:
        regions = [r.strip().upper() for r in args.regions.split(",") if r.strip()]
        invalid_regions = [r for r in regions if r not in FEATURE3_REGIONS]
        if invalid_regions:
            print(f"[ERROR] 未知地区: {', '.join(invalid_regions)}，功能3 可选: {', '.join(FEATURE3_REGIONS)}", file=sys.stderr)
            sys.exit(1)

        # ── Region 权限校验 ──
        mis_id = getattr(args, "mis_id", None) or ""
        require_region_permission(mis_id, regions)

        interval = args.interval
        if interval < MIN_POLL_INTERVAL:
            print(f"[ERROR] 轮询间隔 {interval} 分钟低于最小限制 {MIN_POLL_INTERVAL} 分钟", file=sys.stderr)
            sys.exit(1)

        push_daxiang   = args.push_daxiang
        daxiang_target = args.daxiang_target
        owner_uid      = args.owner_uid
        if daxiang_target and not push_daxiang:
            push_daxiang = True

        # 粒度选择（复用 --f2-granularity 参数，argparse 已保证默认值 "zone"）
        f3_gran = args.f2_granularity
        gran_info    = F2_GRANULARITY[f3_gran]
        f3_dim_field    = gran_info["dim_field"]
        f3_dim_label    = gran_info["dim_label"]
        f3_dim_label_en = gran_info["dim_label_en"]

        active_hours = getattr(args, "active_hours", "00:00-24:00") or "00:00-24:00"

        # Top N（优先使用 CLI 参数，否则默认值）
        top_n = args.top_n if args.top_n is not None else FEATURE3_DEFAULT_TOP_N

        # 解析阈值覆盖
        f3_threshold_overrides = None
        if args.thresholds:
            try:
                f3_threshold_overrides = json.loads(args.thresholds) if isinstance(args.thresholds, str) else args.thresholds
            except (json.JSONDecodeError, TypeError):
                f3_threshold_overrides = None

        # 解析差异化阈值（功能3：按城市/区域差异化，仅 GROUP2 指标）
        f3_dim_thresholds = resolve_dim_thresholds(getattr(args, "dim_thresholds", None))
        if f3_dim_thresholds:
            allowed = set(FEATURE3_GROUP2_KEYS)
            bad = {k for v in f3_dim_thresholds.values() for k in (v or {}) if k not in allowed}
            if bad:
                print(f"[ERROR] --dim-thresholds 包含 Feature 3 不支持的指标: {bad}，允许: {allowed}", file=sys.stderr)
                sys.exit(1)

        print(f"\n===== Feature 3 商家出餐体验异动告警 配置摘要 =====")
        print(f"  功能:     Feature 3（商家出餐体验异动监控）")
        print(f"  数据集:   {FEATURE3_AGG_DATASETS[f3_gran]['group1']}（第一组）+ 60051927（第二组）+ {FEATURE3_MERCHANT_DATASET_ID}（商家明细）")
        print(f"  粒度:     {f3_dim_label}（{f3_dim_field}）[{f3_dim_label_en}]")
        print(f"  地区:     {', '.join(regions)}")
        print(f"  监控指标: {', '.join(FEATURE3_ALL_KEYS)}")
        print(f"  Top N:    {top_n}")
        print(f"  轮询间隔: 每 {interval} 分钟（整点对齐）")
        print(f"  活跃时段: {active_hours}")
        print(f"  推大象:   {'是' if push_daxiang else '否'}{' → ' + daxiang_target if daxiang_target else ''}")
        if owner_uid:
            print(f"  接收人:   UID {owner_uid}")

        if args.dry_run:
            print("\n[DRY-RUN] 参数验证通过，未写入配置。\n")
            return

        _suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        job_id = f"f3-{'-'.join(r.lower() for r in regions)}-{datetime.now().strftime('%m%d%H%M')}-{_suffix}"
        print(f"\n  任务 ID:  {job_id}")

        job = {
            "id":           job_id,
            "name":         f"{'_'.join(regions)} 商家出餐体验异动告警",
            "feature":      3,
            "regions":      regions,
            "dim_field":    f3_dim_field,
            "dim_label":    f3_dim_label,
            "dim_label_en": f3_dim_label_en,
            "active_hours": active_hours,
            "thresholds":   f3_threshold_overrides,
            "dim_thresholds": f3_dim_thresholds or None,
            "top_n":        top_n,
            "poll":         {"interval_min": interval, "push_daxiang": push_daxiang, "daxiang_target": daxiang_target},
            "owner_uid":    owner_uid,
            "mis_id":       mis_id or _get_mis(),
            "configured_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        }
        cfg = load_cron_config()
        if owner_uid:
            cfg["owner_uid"] = owner_uid
        cfg["jobs"].append(job)
        save_cron_config(cfg)
        print(f"[INFO] 配置已保存到 {CRON_CONFIG_PATH}")
        register_cron(interval, job_id, regions=regions, daxiang_target=daxiang_target, owner_uid=owner_uid, feature=3)
        print(f"\n✅ Feature 3 告警任务 [{job_id}] 已成功注册！\n")
        return job_id

    # ── Feature 1: 固定阈值告警（原有逻辑） ──
    # 校验数据集
    dataset_id = args.dataset
    if dataset_id not in DATASETS:
        print(f"[ERROR] 未知数据集: {dataset_id}，可选: {', '.join(DATASETS.keys())}", file=sys.stderr)
        sys.exit(1)

    # 校验地区（功能1 数据集不含 HK）
    regions = [r.strip().upper() for r in args.regions.split(",") if r.strip()]
    invalid_regions = [r for r in regions if r not in FEATURE1_REGIONS]
    if invalid_regions:
        print(f"[ERROR] 未知地区: {', '.join(invalid_regions)}，功能1 可选: {', '.join(FEATURE1_REGIONS)}（HK 暂不支持功能1）", file=sys.stderr)
        sys.exit(1)

    # ── Region 权限校验 ──
    mis_id = getattr(args, "mis_id", None) or ""
    require_region_permission(mis_id, regions)

    # 指标
    metrics = resolve_metrics(args.metrics, dataset_id)

    # 阈值
    thresholds     = resolve_thresholds(args.thresholds, metrics, dataset_id)
    dim_thresholds = resolve_dim_thresholds(args.dim_thresholds)

    # 轮询间隔
    interval = args.interval
    if interval < MIN_POLL_INTERVAL:
        print(f"[ERROR] 轮询间隔 {interval} 分钟低于最小限制 {MIN_POLL_INTERVAL} 分钟", file=sys.stderr)
        sys.exit(1)

    push_daxiang   = args.push_daxiang
    daxiang_target = args.daxiang_target  # None = 发个人（默认），"group:xxx" = 发群聊
    owner_uid      = args.owner_uid       # 告警接收人 UID（cron isolated session 需要）
    # 只要配了推送目标，自动开启推送（防止漏传 --push-daxiang）
    if daxiang_target and not push_daxiang:
        push_daxiang = True

    active_hours = getattr(args, "active_hours", "00:00-24:00") or "00:00-24:00"

    # 打印参数摘要（dry-run 或正式写入前均显示）
    ds_label = DATASETS[dataset_id]["label"]
    print(f"\n===== 告警任务配置摘要 =====")
    print(f"  数据集:   {dataset_id}  {ds_label}")
    print(f"  地区:     {', '.join(regions)}")
    print(f"  指标数:   {len(metrics)} 个")
    for k in metrics:
        m = ALL_METRICS[k]
        t = thresholds.get(k)
        thr_str = f"{m['op']} {t}" if t is not None else "不告警"
        print(f"            {m['label']} {thr_str}")
    if dim_thresholds:
        print(f"  差异阈值: {list(dim_thresholds.keys())}")
    print(f"  轮询间隔: 每 {interval} 分钟（整点对齐）")
    print(f"  活跃时段: {active_hours}")
    print(f"  推大象:   {'是' if push_daxiang else '否'}{' → ' + daxiang_target if daxiang_target else ''}")
    if owner_uid:
        print(f"  接收人:   UID {owner_uid}")

    if args.dry_run:
        print("\n[DRY-RUN] 参数验证通过，未写入配置。\n")
        return

    # 生成 job_id 并写入配置
    _suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    job_id = f"{'-'.join(r.lower() for r in regions)}-{datetime.now().strftime('%m%d%H%M')}-{_suffix}"
    print(f"\n  任务 ID:  {job_id}")

    job = {
        "id":           job_id,
        "name":         f"{'_'.join(regions)} 告警",
        "feature":      1,
        "dataset_id":   dataset_id,
        "regions":      regions,
        "metrics":      metrics,
        "thresholds":   thresholds,
        "dim_thresholds": dim_thresholds,
        "active_hours": active_hours,
        "poll":         {"interval_min": interval, "push_daxiang": push_daxiang, "daxiang_target": daxiang_target},
        "owner_uid":    owner_uid,
        "mis_id":       mis_id or _get_mis(),
        "configured_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
    }
    if job["mis_id"] == "unknown":
        print("[WARN] 无法自动获取 MIS，建议重新 setup 时传入 --mis-id <your_mis> 以便埋点归因", file=sys.stderr)
    cfg = load_cron_config()
    # 同时保存 owner_uid 到全局配置（供 _get_default_owner_uid 读取）
    if owner_uid:
        cfg["owner_uid"] = owner_uid
    cfg["jobs"].append(job)
    save_cron_config(cfg)
    print(f"[INFO] 配置已保存到 {CRON_CONFIG_PATH}")
    register_cron(interval, job_id, regions=regions, daxiang_target=daxiang_target, owner_uid=owner_uid, feature=1)
    print(f"\n✅ 告警任务 [{job_id}] 已成功注册！\n")
    return job_id


# ── Cron 注册 / 删除 ──────────────────────────────────────

def register_cron(minutes, job_id, regions=None, daxiang_target=None, owner_uid=None, feature=1):
    if minutes < MIN_POLL_INTERVAL:
        print(f"[ERROR] 间隔 {minutes} 分钟低于最小限制 {MIN_POLL_INTERVAL} 分钟，注册中止", file=sys.stderr)
        return
    script    = os.path.abspath(__file__)
    cron_name = f"keeta-alert-{job_id}"
    # 延后 1 分钟触发（1-59/N），确保当前 slot 数据已入库
    cron_expr = f"1-59/{minutes} * * * *"
    tz        = REGION_TZ_NAMES.get(regions[0], "UTC") if regions else "UTC"

    prompt = (
        f'Run this shell command exactly once:\n'
        f'export PATH="$HOME/bin:$PATH" && python3 {script} --cron-run --job-id {job_id}\n\n'
        f'The script handles all messaging internally (sends alerts directly to Daxiang via API).\n'
        f'Do NOT read output files or send any messages yourself.\n'
        f'Do NOT re-run the command even if output is empty or the script exits with no stdout.\n'
        f'After the command finishes, reply "DONE".'
    )
    # F1 实际耗时 ~15s；F2/F3 kdata 串行查询 ~72s + 发送 ~30s + atexit ~5s = ~107s
    timeout_s = "60" if feature == 1 else "120"

    r = subprocess.run(
        ["openclaw", "cron", "add", "--name", cron_name,
         "--cron", cron_expr, "--tz", tz,
         "--session", "isolated",
         "--no-deliver",
         "--message", prompt,
         "--timeout-seconds", timeout_s],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        print(f"[INFO] 定时任务已注册：{cron_name}，cron={cron_expr}，tz={tz}（整点对齐）")
    else:
        print(f"[WARN] cron 注册失败:\n{r.stderr}")


def delete_cron_by_job_id(job_id):
    """删除 cron 条目并同时从 cron_config.json 移除 job 记录。"""
    delete_cron_by_job_id_keep_config(job_id)   # 先删 cron 条目（失败时已报错退出）
    cfg = load_cron_config()
    cfg["jobs"] = [j for j in cfg.get("jobs", []) if j.get("id") != job_id]
    save_cron_config(cfg)
    print(f"[INFO] 已从配置中移除 job: {job_id}")


def _arg_was_passed(*flags):
    """检测用户是否在命令行显式传入了某个参数（区分于 argparse 默认值）。"""
    argv = sys.argv[1:]
    for flag in flags:
        for tok in argv:
            if tok == flag or tok.startswith(flag + "="):
                return True
    return False


def update_job(args):
    """修改已有告警任务参数。仅覆盖用户显式传入的字段，其余保持不变。

    可修改字段（按 feature 生效）：
      --thresholds      阈值覆盖（三个 feature 统一按指标 merge，只改传入的指标；F2/F3 仅限触发指标）
      --dim-thresholds  差异化阈值（仅 F1）
      --interval        轮询间隔（变更会重新注册 cron）
      --active-hours    活跃时段
      --metrics         监控指标（仅 F1）
      --daxiang-target  推送目标
      --top-n           商家明细 Top N（仅 F3）
    """
    if not args.job_id:
        print("[ERROR] 需要 --job-id", file=sys.stderr); sys.exit(1)

    cfg  = load_cron_config()
    jobs = cfg.get("jobs", [])
    idx  = next((i for i, j in enumerate(jobs) if j.get("id") == args.job_id), None)
    if idx is None:
        print(f"[ERROR] 未找到 job: {args.job_id}（共 {len(jobs)} 个任务: {[j.get('id') for j in jobs]}）", file=sys.stderr)
        sys.exit(1)

    job     = jobs[idx]
    feature = job.get("feature", 1)
    changes = []                      # 记录变更明细，用于打印摘要
    cron_needs_reregister = False     # interval 变更需重注 cron

    # ── regions：不支持修改 ──
    # 改地区等于换监控对象（数据范围/时区/权限/阈值基线全变），应停旧任务+新建，
    # 不在 update-job 内支持，避免误操作。
    if _arg_was_passed("--regions"):
        print("[ERROR] --update-job 不支持修改 --regions：改地区等同于新建任务（涉及时区/权限/阈值基线变化）。\n"
              "        请用 --stop-cron 停掉当前任务，再用 --setup-cron 新建对应地区的任务。", file=sys.stderr)
        sys.exit(1)

    # ── granularity：不支持修改 ──
    # 改粒度（city/zone）会同时切换数据集和维度字段，等同于新建不同粒度的任务，
    # 避免因数据集切换导致历史比较失效，不在 update-job 内支持。
    if _arg_was_passed("--f2-granularity"):
        print("[ERROR] --update-job 不支持修改 --f2-granularity：改粒度会切换数据集，等同于新建任务。\n"
              "        请用 --stop-cron 停掉当前任务，再用 --setup-cron 新建对应粒度的任务。", file=sys.stderr)
        sys.exit(1)

    # ── interval ──
    if _arg_was_passed("--interval"):
        if args.interval < MIN_POLL_INTERVAL:
            print(f"[ERROR] 轮询间隔 {args.interval} 分钟低于最小限制 {MIN_POLL_INTERVAL} 分钟", file=sys.stderr)
            sys.exit(1)
        old_iv = job.get("poll", {}).get("interval_min")
        if args.interval != old_iv:
            changes.append(f"interval: {old_iv} → {args.interval} 分钟")
            job.setdefault("poll", {})["interval_min"] = args.interval
            cron_needs_reregister = True

    # ── active-hours ──
    if _arg_was_passed("--active-hours"):
        # 格式校验：parse_active_hours 返回 None 表示格式有误（非全天字符串）
        if args.active_hours not in ("00:00-24:00", "") and parse_active_hours(args.active_hours) is None:
            print(f"[ERROR] active_hours 格式有误: {args.active_hours!r}（应为 HH:MM-HH:MM，如 17:00-22:00）", file=sys.stderr)
            sys.exit(1)
        if args.active_hours != job.get("active_hours"):
            changes.append(f"active_hours: {job.get('active_hours')} → {args.active_hours}")
            job["active_hours"] = args.active_hours

    # ── daxiang-target ──
    if _arg_was_passed("--daxiang-target"):
        old_t = job.get("poll", {}).get("daxiang_target")
        if args.daxiang_target != old_t:
            changes.append(f"daxiang_target: {old_t} → {args.daxiang_target}")
            job.setdefault("poll", {})["daxiang_target"] = args.daxiang_target
            job["poll"]["push_daxiang"] = bool(args.daxiang_target)  # 同步更新：清空 target 时关闭推送
            cron_needs_reregister = True

    # ── metrics（仅 F1）──
    if _arg_was_passed("--metrics"):
        if feature != 1:
            print(f"[WARN] --metrics 仅对 feature 1 生效，当前 job 为 feature {feature}，已忽略", file=sys.stderr)
        else:
            new_metrics = resolve_metrics(args.metrics, job.get("dataset_id"))
            if new_metrics != job.get("metrics"):
                old_metrics = job.get("metrics", []) or []
                added = [k for k in new_metrics if k not in old_metrics]
                removed = [k for k in old_metrics if k not in new_metrics]
                detail = f"metrics: {len(old_metrics)} 个 → {len(new_metrics)} 个"
                sub = []
                if added:
                    sub.append(f"added={added}")
                if removed:
                    sub.append(f"removed={removed}")
                if sub:
                    detail += f" ({'; '.join(sub)})"
                changes.append(detail)
                job["metrics"] = new_metrics
                # 重算阈值：保留原有可复用阈值，新增指标用默认值
                old_thr = job.get("thresholds", {}) or {}
                job["thresholds"] = {k: old_thr.get(k, get_default_threshold(k, job.get("dataset_id"))) for k in new_metrics}

    # ── thresholds ──
    if _arg_was_passed("--thresholds"):
        try:
            overrides = json.loads(args.thresholds) if isinstance(args.thresholds, str) else (args.thresholds or {})
        except (json.JSONDecodeError, TypeError) as e:
            print(f"[ERROR] --thresholds JSON 解析失败: {e}", file=sys.stderr)
            sys.exit(1)
        # 三个 feature 统一按指标 merge：只覆盖传入的指标，其余保留。
        # F2/F3 补充合法触发指标 key 校验，防止误传非触发指标。
        if feature == 2:
            valid_keys = set(FEATURE2_L1_TRIGGER_KEYS)
        elif feature == 3:
            # F3 只有 GROUP2 指标（积压任务单数 unaccepted_task_num + 近20min平均等餐时长
            # last_20min_meal_waiting_dura_task_avg）参与触发判断、带阈值；
            # GROUP1（卡餐商家数/占比）仅作补充信息展示，不可改阈值。
            # 与 setup_cron 中「方案A：只有 GROUP2 指标参与触发判断」保持一致。
            valid_keys = set(FEATURE3_GROUP2_KEYS)
        else:
            valid_keys = None                         # F1 指标由任务动态选定，不做白名单校验
        if valid_keys is not None:
            bad = [k for k in overrides if k not in valid_keys]
            if bad:
                print(f"[ERROR] feature {feature} 不支持修改这些指标阈值: {bad}"
                      f"（可改触发指标: {sorted(valid_keys)}）", file=sys.stderr)
                sys.exit(1)
        cur = dict(job.get("thresholds", {}) or {})
        thr_detail = []
        for k, v in overrides.items():
            old_v = cur.get(k)
            new_v = float(v)
            cur[k] = new_v
            thr_detail.append(f"{k}: {old_v} → {new_v}" if old_v is not None else f"{k}: (新增) → {new_v}")
        changes.append(f"thresholds: {', '.join(thr_detail)}")
        job["thresholds"] = cur

    # ── dim-thresholds（F1/F2/F3 均支持，各 feature 的指标白名单不同）──
    if _arg_was_passed("--dim-thresholds"):
        if feature not in (1, 2, 3):
            print(f"[WARN] --dim-thresholds 仅对 feature 1/2/3 生效，已忽略", file=sys.stderr)
        else:
            # 各 feature 允许的 dim_thresholds 指标 key 白名单
            _dim_thr_allowed = {
                1: None,  # F1 不限制（all ALL_METRICS）
                2: set(FEATURE2_L1_TRIGGER_KEYS),
                3: set(FEATURE3_GROUP2_KEYS),
            }.get(feature)
            if _dim_thr_allowed is not None:
                _raw_dim = resolve_dim_thresholds(args.dim_thresholds) or {}
                _bad = {k for v in _raw_dim.values() for k in (v or {}) if k not in _dim_thr_allowed}
                if _bad:
                    print(f"[ERROR] --dim-thresholds 包含 feature {feature} 不支持的指标: {_bad}，允许: {_dim_thr_allowed}", file=sys.stderr)
                    sys.exit(1)
            # 与 thresholds 保持一致：按维度增量 merge，只覆盖传入的维度，其余维度保留。
            # 单个维度内部再按指标 merge，避免「只改 Riyadh 一个指标」却清空该维度其他指标。
            overrides_dim = resolve_dim_thresholds(args.dim_thresholds)
            cur_dim = dict(job.get("dim_thresholds", {}) or {})
            dim_detail = []
            for dv, thr_map in overrides_dim.items():
                merged = dict(cur_dim.get(dv, {}) or {})
                metric_changes = []
                for k, v in (thr_map or {}).items():
                    old_v = merged.get(k)
                    new_v = float(v)
                    merged[k] = new_v
                    metric_changes.append(f"{k}: {old_v} → {new_v}" if old_v is not None else f"{k}: (新增) → {new_v}")
                action = "更新" if dv in cur_dim else "新增"
                cur_dim[dv] = merged
                dim_detail.append(f"{dv}({action}): {', '.join(metric_changes)}")
            changes.append(f"dim_thresholds: {'; '.join(dim_detail)}")
            job["dim_thresholds"] = cur_dim

    # ── min-push-ord-num（仅 F2）──
    if _arg_was_passed("--min-push-ord-num"):
        if feature != 2:
            print(f"[WARN] --min-push-ord-num 仅对 feature 2 生效，已忽略", file=sys.stderr)
        else:
            old_val = job.get("min_push_ord_num")
            new_val = int(args.min_push_ord_num) if args.min_push_ord_num is not None else None
            if old_val != new_val:
                changes.append(f"min_push_ord_num: {old_val} → {new_val}")
                job["min_push_ord_num"] = new_val

    # ── top-n（仅 F3）──
    if _arg_was_passed("--top-n") and args.top_n is not None:
        if feature != 3:
            print(f"[WARN] --top-n 仅对 feature 3 生效，已忽略", file=sys.stderr)
        elif args.top_n != job.get("top_n"):
            changes.append(f"top_n: {job.get('top_n')} → {args.top_n}")
            job["top_n"] = args.top_n

    if not changes:
        print("[INFO] 未检测到任何参数变更（未传入可修改参数或值与原值相同）。")
        return {"changes_count": 0, "change_details": [], "cron_reregister": False}

    job["updated_at"] = datetime.now(timezone(timedelta(hours=8))).isoformat()

    print(f"\n===== 任务 [{args.job_id}]（feature {feature}）参数修改摘要 =====")
    for c in changes:
        print(f"  • {c}")
    if cron_needs_reregister:
        print(f"  ⚠ interval/推送目标变更 → 将重新注册 cron")

    if getattr(args, "dry_run", False):
        print("\n[DRY-RUN] 参数验证通过，未写入配置。\n")
        return {"changes_count": len(changes), "change_details": changes, "cron_reregister": cron_needs_reregister}

    jobs[idx] = job
    cfg["jobs"] = jobs
    # 先备份原始配置，便于出错时手动恢复
    backup_path = CRON_CONFIG_PATH + ".update_bak"
    try:
        import shutil
        shutil.copy2(CRON_CONFIG_PATH, backup_path)
    except Exception:
        pass  # 备份失败不阻断主流程
    save_cron_config(cfg)
    print(f"[INFO] 配置已保存到 {CRON_CONFIG_PATH}（原始备份: {backup_path}）")

    if cron_needs_reregister:
        interval = job.get("poll", {}).get("interval_min", MIN_POLL_INTERVAL)
        regions  = job.get("regions")
        dtarget  = job.get("poll", {}).get("daxiang_target")
        ouid     = job.get("owner_uid")
        feature  = job.get("feature", 1)
        delete_cron_by_job_id_keep_config(args.job_id)
        register_cron(interval, args.job_id, regions=regions, daxiang_target=dtarget, owner_uid=ouid, feature=feature)
        print(f"[INFO] cron 已重新注册（interval={interval} 分钟，feature={feature}）")

    print(f"\n✅ 告警任务 [{args.job_id}] 参数已更新！\n")
    return {"changes_count": len(changes), "change_details": changes, "cron_reregister": cron_needs_reregister}


def delete_cron_by_job_id_keep_config(job_id):
    """仅删除 cron 条目，不动 cron_config.json（用于 update 重注场景）。"""
    cron_name = f"keeta-alert-{job_id}"
    r = subprocess.run(["openclaw", "cron", "list", "--json"], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[ERROR] cron 列表获取失败，无法删除旧 cron，中止重注册。\n{r.stderr}", file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(r.stdout)
        jl = data.get("jobs", []) if isinstance(data, dict) else data
        for j in [j for j in jl if j.get("name") == cron_name]:
            rm = subprocess.run(["openclaw", "cron", "rm", j["id"]], capture_output=True, text=True)
            if rm.returncode != 0:
                print(f"[ERROR] cron 删除失败（{cron_name} / id={j['id']}），中止重注册。\n{rm.stderr}", file=sys.stderr)
                sys.exit(1)
            print(f"[INFO] 已删除旧 cron: {cron_name}")
    except Exception as e:
        print(f"[ERROR] 解析 cron 列表失败，中止重注册: {e}", file=sys.stderr)
        sys.exit(1)


def list_jobs():
    cfg  = load_cron_config()
    jobs = cfg.get("jobs", [])
    if not jobs:
        print("当前没有任何定时告警任务。")
        return
    print(f"\n共 {len(jobs)} 个定时告警任务：\n")
    for j in jobs:
        poll    = j.get("poll", {})
        feature = j.get("feature", 1)
        print(f"  ID:       {j.get('id', '<unknown>')}")
        _feature_labels = {1: "固定阈值", 2: "运力供需异动监控", 3: "商家出餐体验异动告警"}
        print(f"  Feature:  {feature} ({_feature_labels.get(feature, str(feature))})")
        if feature == 2:
            print(f"  数据集:   60051927 + 60009475（供需 + 排班出勤）")
            f2_dim = j.get("dim_field", "delivery_area_name")
            f2_lbl = j.get("dim_label", "业务城市" if f2_dim == "op_city_name" else "配送区域")
            print(f"  粒度:     {f2_lbl}（{f2_dim}）")
            _min_pov = j.get("min_push_ord_num")
            if _min_pov is not None:
                print(f"  推单量门槛: push_ord_num < {_min_pov} 不告警")
        elif feature == 3:
            f3_gran_key = "city" if j.get("dim_field") == "op_city_name" else "zone"
            f3_ds_g1 = FEATURE3_AGG_DATASETS[f3_gran_key]["group1"]
            print(f"  数据集:   {f3_ds_g1}（第一组）+ 60051927（第二组）+ {FEATURE3_MERCHANT_DATASET_ID}（商家明细）")
            f3_dim = j.get("dim_field", "delivery_area_name")
            f3_lbl = j.get("dim_label", "业务城市" if f3_dim == "op_city_name" else "配送区域")
            print(f"  粒度:     {f3_lbl}（{f3_dim}）")
            print(f"  Top N:    {j.get('top_n', FEATURE3_DEFAULT_TOP_N)}")
        else:
            ds_id = j.get("dataset_id", "-")
            print(f"  数据集:   {ds_id}  {DATASETS.get(ds_id, {}).get('label', '')}")
        print(f"  地区:     {', '.join(j.get('regions', []))}")
        if feature == 1:
            thr_str = " | ".join(
                f"{ALL_METRICS[k]['label']}{ALL_METRICS[k]['op']}{v}"
                for k, v in j.get("thresholds", {}).items() if k in ALL_METRICS
            )
            print(f"  全局阈值: {thr_str or '无'}")
            dthr = j.get("dim_thresholds", {})
            if dthr:
                print(f"  差异阈值: {list(dthr.keys())}")
        elif feature == 3:
            # 显示功能3当前生效的阈值（自定义覆盖 or 默认值）
            f3_dim = j.get("dim_field", "delivery_area_name")
            f3_thr_key = "thr_city" if f3_dim == "op_city_name" else "thr_area"
            custom_thr = j.get("thresholds") or {}
            thr_parts = []
            for k in FEATURE3_ALL_KEYS:
                m = ALL_METRICS.get(k, {})
                effective = custom_thr.get(k, m.get(f3_thr_key))
                if effective is not None:
                    label = m.get("en") or m.get("label", k)
                    thr_parts.append(f"{label}{m['op']}{effective}")
            print(f"  告警阈值: {' | '.join(thr_parts) or '默认'}")
        print(f"  间隔:     每 {poll.get('interval_min','?')} 分钟（整点对齐）")
        ah = j.get("active_hours", "00:00-24:00")
        print(f"  活跃时段: {ah}")
        print(f"  推大象:   {'是' if poll.get('push_daxiang') else '否'}")
        print(f"  创建时间: {j.get('configured_at', '-')}")
        print()


def list_datasets():
    print("\n可用数据集：\n")
    for ds_id, ds in DATASETS.items():
        print(f"  {ds_id}  {ds['label']}  (维度字段: {ds['dim_field']})")
    print()


def print_defaults(dataset_id):
    if dataset_id not in DATASETS:
        print(f"[ERROR] 未知数据集: {dataset_id}，可选: {', '.join(DATASETS.keys())}", file=sys.stderr)
        sys.exit(1)
    is_area = dataset_id == "62059270"
    label   = DATASETS[dataset_id]["label"]
    print(f"\n{dataset_id}  {label} 默认阈值：\n")
    for k, m in ALL_METRICS.items():
        t = m["thr_area"] if is_area else m["thr_city"]
        print(f"  {k:<48} {m['label']}  {m['op']} {t}")
    print()


# ── 数据查询 ──────────────────────────────────────────────

class _KdataEnvError(RuntimeError):
    """kdata 二进制不存在或无执行权限（环境问题，不是查询本身失败）。"""


def _try_fix_kdata(env: dict) -> None:
    """尝试修复 kdata execute bit；binary 不存在或修复失败时抛 _KdataEnvError。"""
    import shutil, stat as _stat
    kdata_bin = shutil.which("kdata", path=env.get("PATH") or None)
    if kdata_bin is None:
        # fallback: 直接用 kdata.py 绝对路径（isolated session 里软链接可能丢失）
        _kdata_py = os.path.join(KEETA_DATA_QUERY_PATH, "scripts", "kdata.py")
        if os.path.exists(_kdata_py):
            env["KDATA_BIN"] = _kdata_py  # 标记给 _run_kdata_raw 使用
            print(f"[WARN] kdata 软链接未找到，使用绝对路径: {_kdata_py}", file=sys.stderr)
            return
        raise _KdataEnvError(f"kdata 未找到（PATH={env.get('PATH', '')}）")
    try:
        st = os.stat(kdata_bin)
        if not (st.st_mode & _stat.S_IXUSR):
            os.chmod(kdata_bin, st.st_mode | 0o111)
            print(f"[WARN] kdata execute bit 已自动修复: {kdata_bin}", file=sys.stderr)
        else:
            raise _KdataEnvError(
                f"kdata 存在且有执行权限，但仍报 PermissionError: {kdata_bin}。"
                f" 可能原因：noexec 挂载点、SELinux/AppArmor 策略限制、或文件系统限制。"
                f" 请确认 kdata 所在分区未以 noexec 挂载：`mount | grep noexec`"
            )
    except _KdataEnvError:
        raise
    except OSError as e:
        raise _KdataEnvError(f"kdata 权限修复失败 ({kdata_bin}): {e}") from e


def _kdata_subprocess(cmd, env, timeout):
    """执行 kdata subprocess；遇到权限/未找到错误时自动修复 execute bit 并重试一次。"""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
    except (PermissionError, FileNotFoundError) as e:
        print(f"[WARN] kdata 无法执行 ({type(e).__name__}: {e})，尝试自动修复...", file=sys.stderr)
        _try_fix_kdata(env)  # 成功则继续重试，失败则抛 _KdataEnvError
        try:
            return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
        except (PermissionError, FileNotFoundError) as retry_e:
            # chmod 后仍无法执行（如 noexec 挂载点、SELinux 等），统一归类为环境问题
            raise _KdataEnvError(f"kdata 修复后仍无法执行: {retry_e}") from retry_e


def _parse_kdata_meta(cmd: list) -> tuple[str, str]:
    """从 kdata cmd 列表中提取 (dataset_id, region)，解析失败返回空字符串。"""
    dataset_id = region = ""
    try:
        for i, v in enumerate(cmd):
            if v == "--dataset" and i + 1 < len(cmd):
                dataset_id = cmd[i + 1]
            elif v == "--region" and i + 1 < len(cmd):
                region = cmd[i + 1]
    except Exception:
        pass
    return dataset_id, region


def _report_kdata(dataset_id: str, region: str, cost_ms: int,
                  rows: int = -1, success: bool = True, error_msg: str = "") -> None:
    """fire-and-forget 上报单次 kdata 查询节点（skill-script 事件）。"""
    if not _CLI_LOGGER_AVAILABLE or not _cron_context:
        return
    try:
        _cli_logger_report_kdata(
            _cron_context.get("mis", ""),
            dataset_id, region, cost_ms,
            rows_count=rows, success=success, error_msg=error_msg,
            session_id=_cron_context.get("session_id", ""),
            job_id=_cron_context.get("job_id", ""),
        )
    except Exception:
        pass


def _resolve_kdata_cmd(cmd: list, env: dict) -> list:
    """如果 kdata 软链接不在 PATH 里，改用 python3 kdata.py 绝对路径调用。"""
    import shutil
    if cmd and cmd[0] == "kdata" and shutil.which("kdata", path=env.get("PATH")) is None:
        _kdata_py = os.path.join(KEETA_DATA_QUERY_PATH, "scripts", "kdata.py")
        if os.path.exists(_kdata_py):
            print(f"[WARN] kdata 软链接不可用，改用绝对路径: {_kdata_py}", file=sys.stderr)
            return [sys.executable, _kdata_py] + cmd[1:]
    return cmd


def _run_kdata_raw(cmd, timeout=90):
    """执行 kdata CLI 命令并返回 rows 列表。失败时返回空列表并打印错误。"""
    _kdata_call_log.append(1)  # [TRACKING] 逻辑查询计数
    env = os.environ.copy()
    env["PATH"] = os.path.expanduser("~/bin") + ":" + env.get("PATH", "")
    cmd = _resolve_kdata_cmd(cmd, env)
    _ds, _region = _parse_kdata_meta(cmd)
    _t0_kdata = time.time()
    try:
        r = _kdata_subprocess(cmd, env, timeout)
    except subprocess.TimeoutExpired:
        print(f"[ERROR] kdata 查询超时（{timeout}s）: {' '.join(cmd[:5])}", file=sys.stderr)
        _report_kdata(_ds, _region, int((time.time() - _t0_kdata) * 1000),
                      success=False, error_msg="kdata_timeout")
        return None  # None 表示超时
    _cost_kdata = int((time.time() - _t0_kdata) * 1000)
    if r.returncode != 0:
        print(f"[ERROR] kdata 失败: {r.stderr[:500]}", file=sys.stderr)
        _report_kdata(_ds, _region, _cost_kdata, success=False, error_msg=r.stderr[:200])
        return []
    start = r.stdout.find("{")
    if start == -1:
        print(f"[WARN] kdata 未找到 JSON: {r.stdout[:200]}", file=sys.stderr)
        _report_kdata(_ds, _region, _cost_kdata, success=False, error_msg="no_json")
        return []
    try:
        rows = json.loads(r.stdout[start:]).get("rows", [])
        _report_kdata(_ds, _region, _cost_kdata, rows=len(rows))
        return rows
    except json.JSONDecodeError as e:
        print(f"[ERROR] kdata JSON 解析失败: {e}", file=sys.stderr)
        _report_kdata(_ds, _region, _cost_kdata, success=False, error_msg="json_decode_error")
        return []


def run_kdata(dataset_id, region, measures, dim_field):
    _kdata_call_log.append(1)  # [TRACKING] 逻辑查询计数（F1 不经过 _run_kdata_raw）
    tz    = REGION_TZ.get(region, REGION_TZ["SA"])
    today = datetime.now(tz).strftime("%Y%m%d")
    cmd   = ["kdata", "--task-id", "alert-query", "--task-name", "realtime-alert",
             "--json", "standard", "query",
             "--dataset", dataset_id,
             "--measures", *measures,
             "--date", f"{today}~{today}",
             "--region", region,
             "--group-by", dim_field,
             "--order-by", f"{measures[0]}=DESC"]
    env = os.environ.copy()
    env["PATH"] = os.path.expanduser("~/bin") + ":" + env.get("PATH", "")
    cmd = _resolve_kdata_cmd(cmd, env)
    _t0_kdata = time.time()
    try:
        r = _kdata_subprocess(cmd, env, timeout=60)
    except subprocess.TimeoutExpired:
        _report_kdata(dataset_id, region, int((time.time() - _t0_kdata) * 1000),
                      success=False, error_msg="kdata_timeout")
        print(f"[ERROR] kdata 查询超时（60s），region={region}", file=sys.stderr)
        sys.exit(1)
    _cost_kdata = int((time.time() - _t0_kdata) * 1000)
    if r.returncode != 0:
        _report_kdata(dataset_id, region, _cost_kdata, success=False, error_msg=r.stderr[:200])
        print(f"[ERROR] kdata 失败:\n{r.stderr}", file=sys.stderr)
        sys.exit(1)
    start = r.stdout.find("{")
    if start == -1:
        _report_kdata(dataset_id, region, _cost_kdata, success=False, error_msg="no_json")
        print(f"[ERROR] 未找到 JSON:\n{r.stdout}", file=sys.stderr)
        sys.exit(1)
    rows = json.loads(r.stdout[start:]).get("rows", [])
    _report_kdata(dataset_id, region, _cost_kdata, rows=len(rows))
    return rows


def run_kdata_snapshot(dataset_id, region, measures, dim_field, dt):
    """查询不带时间维度的快照数据（当天聚合值 / 最新快照值）。

    某些实时指标（supply_demand_ratio、rider_load 等）不支持 10min 时间粒度，
    只能按 delivery_area_name 分组查询，返回当天最新快照值。

    Args:
        dataset_id: 数据集 ID
        region: 地区代码
        measures: 指标字段列表
        dim_field: 维度字段
        dt: 日期字符串 YYYYMMDD

    Returns:
        list of rows ({dim_field: value, measure1: value, ...})
    """
    if not measures:
        return []
    cmd = [
        "kdata", "--task-id", "alert-query", "--task-name", "realtime-alert",
        "--json", "standard", "query",
        "--dataset", dataset_id,
        "--measures", *measures,
        "--date", f"{dt}~{dt}",
        "--region", region,
        "--group-by", dim_field,
    ]
    return _run_kdata_raw(cmd, timeout=60) or []


def _run_merchant_detail_query_by_dim(dataset_id, region, measure, dim_field, dim_raw_name, dt, top_n=5):
    """商家明细下钻查询（按单个城市/区域精确查询）。

    按 dim_field 过滤到指定城市/区域，服务端排序后只取 Top N，避免全量拉取截断问题。

    Args:
        dataset_id:   数据集 ID
        region:       地区代码
        measure:      单个指标字段（str）
        dim_field:    维度字段（op_city_name / delivery_area_name）
        dim_raw_name: 维度值（原始语言，如 '朱拜勒'）
        dt:           日期字符串 YYYYMMDD
        top_n:        返回前 N 条

    Returns:
        list of rows，已按 measure 降序排列，最多 top_n 条
    """
    if not measure or not dim_raw_name:
        return []
    cmd = [
        "kdata", "--task-id", "alert-query", "--task-name", "realtime-alert",
        "--json", "standard", "query",
        "--dataset", dataset_id,
        "--measures", measure,
        "--date", f"{dt}~{dt}",
        "--region", region,
        "--filter", f"{dim_field}={dim_raw_name}",
        "--group-by", f"{dim_field},shop_id,shop_name_en",
        "--order-by", f"{measure}=DESC",
        "--page-size", str(top_n),
    ]
    return _run_kdata_raw(cmd, timeout=60) or []


def _threshold_reason(m_info, t):
    fmt   = m_info["format"]
    op    = m_info["op"]
    t_str = f"{t*100:.0f}%" if fmt == "pct2" else (f"{t:g}" if fmt in ("f2","f1") else f"{int(t)}")
    return f"{'Less than' if op == '<' else 'Greater than'} {t_str}"


def build_message(region, rows, metrics, global_thr, dim_thresholds, dim_field):
    tz      = REGION_TZ.get(region, timezone(timedelta(hours=8)))
    now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    header  = f"🚨 Keeta 实时异动 | {region} | {now_str}"

    city_alerts = defaultdict(list)
    for row in rows:
        dv  = row.get(dim_field, "-")
        # dim_thresholds key 已经统一为英文，需要将 kdata 返回的中文城市名转英文后查找
        dv_en = _to_en(dv)
        thr = {**global_thr, **dim_thresholds.get(dv_en, {})}
        for k in metrics:
            if k not in thr or k not in ALL_METRICS: continue
            m   = ALL_METRICS[k]
            val = get_value(row, k)
            if val is None: continue
            t   = thr[k]
            if (m["op"] == ">" and val > t) or (m["op"] == "<" and val < t):
                city_alerts[dv].append((m["en"], format_value(k, val), _threshold_reason(m, t)))

    total = sum(len(v) for v in city_alerts.values())
    if not total:
        return f"{header}\n\n✅ No anomaly detected. All metrics are within normal range."

    sorted_cities = sorted(city_alerts.keys())
    all_entries   = [(c, en, vs, rs) for c in sorted_cities for en, vs, rs in city_alerts[c]]
    w_city = max(len(c)  for c, *_ in all_entries)
    w_en   = max(len(en) for _, en, _, _ in all_entries)
    w_val  = max(len(vs) for _, _, vs, _ in all_entries)
    PAD    = 4

    lines = [
        f"{c.ljust(w_city)}{' '*PAD}{en.ljust(w_en)}{' '*PAD}{vs.rjust(w_val)}{' '*PAD}Alert Reason: {rs}"
        for c in sorted_cities for en, vs, rs in city_alerts[c]
    ]
    return f"{header}\n\n△ {total} alert(s) triggered\n\n```\n" + "\n".join(lines) + "\n```"


# ── 大象推送 ──────────────────────────────────────────────

ALERT_OUTPUT_FILE   = f"/tmp/keeta_alert_output_{os.getpid()}.txt"
DAXIANG_SEND_SCRIPT      = os.path.expanduser("~/.openclaw/skills/daxiang-sender/scripts/send.py")
GROUP_SPEAKER_SEND_SCRIPT = os.path.expanduser("~/.openclaw/skills/claw-group-speaker/scripts/dx_send_msg.py")
BROWSER_SEND_FILE        = "/tmp/keeta_alert_browser_send.json"  # deprecated, kept for cleanup only


def _get_default_owner_uid():
    """从 cron_config.json 或环境变量获取默认 owner UID，不硬编码。"""
    # 1. 环境变量优先
    uid = os.environ.get("OPENCLAW_OWNER_UID", "").strip()
    if uid:
        return uid
    # 2. 从 cron_config.json 的 owner_uid 字段读取
    try:
        with open(CRON_CONFIG_PATH) as f:
            cfg = json.load(f)
        uid = cfg.get("owner_uid", "").strip()
        if uid:
            return uid
    except Exception:
        pass
    return ""


def _notify_owner_error(job_id, error_msg, owner_uid=None):
    """告警执行失败时主动通知 owner，避免静默挂掉。"""
    uid = owner_uid or _get_default_owner_uid()
    if not uid:
        print("[WARN] 无法通知 owner：未配置 owner_uid", file=sys.stderr)
        return
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    msg = (
        f"⚠️ **告警任务执行失败**\n\n"
        f"任务 ID: `{job_id}`\n"
        f"时间: {now_str}\n"
        f"错误: {error_msg}\n\n"
        f"请检查配置或依赖是否正常。可运行：\n"
        f"`python3 alert.py --health-check` 进行自检"
    )
    try:
        send_daxiang(msg, target=uid)
    except Exception as e:
        print(f"[WARN] 通知 owner 失败: {e}", file=sys.stderr)


def _run_health_check(verbose=True):
    """执行自检，返回 (passed: bool, issues: list[str])。"""
    issues = []

    # 1. cron_config.json 存在性 & 可读性
    if not os.path.exists(CRON_CONFIG_PATH):
        issues.append(f"❌ 配置文件不存在: {CRON_CONFIG_PATH}")
    else:
        try:
            with open(CRON_CONFIG_PATH) as f:
                cfg = json.load(f)
            jobs = cfg.get("jobs", [])
            if verbose:
                print(f"✅ 配置文件可读，{len(jobs)} 个任务已配置")
            if not cfg.get("owner_uid"):
                issues.append("⚠️  owner_uid 未配置（失败时无法通知你）")
        except json.JSONDecodeError as e:
            issues.append(f"❌ 配置文件 JSON 格式错误: {e}")
        except Exception as e:
            issues.append(f"❌ 配置文件读取失败: {e}")

    # 2. keeta-data-query 依赖
    if os.path.isdir(KEETA_DATA_QUERY_PATH) and os.path.exists(os.path.join(KEETA_DATA_QUERY_PATH, "SKILL.md")):
        if verbose:
            print("✅ keeta-data-query 已安装")
        # 检查 kdata 是否可执行（通过 --help 验证，kdata 无 --version）
        kdata_script = os.path.join(KEETA_DATA_QUERY_PATH, "scripts", "kdata.py")
        if os.path.exists(kdata_script):
            try:
                r = subprocess.run(
                    ["python3", kdata_script, "--help"],
                    capture_output=True, text=True, timeout=10
                )
                if r.returncode == 0:
                    if verbose:
                        print("✅ kdata 可执行")
                else:
                    issues.append(f"⚠️  kdata 执行报错: {(r.stderr or r.stdout)[:100]}")
            except subprocess.TimeoutExpired:
                issues.append("⚠️  kdata 执行超时（10s）")
            except Exception as e:
                issues.append(f"⚠️  kdata 执行异常: {e}")
        else:
            issues.append(f"❌ kdata 脚本不存在: {kdata_script}")
    else:
        issues.append(f"❌ keeta-data-query 未安装（路径: {KEETA_DATA_QUERY_PATH}）")

    # 3. daxiang-sender 依赖（个人推送）
    if os.path.exists(DAXIANG_SEND_SCRIPT):
        if verbose:
            print("✅ daxiang-sender 已安装")
    else:
        issues.append(f"⚠️  daxiang-sender 未安装（个人推送不可用）: {DAXIANG_SEND_SCRIPT}")

    # 4. daxiang 凭证
    client_id, client_secret = _load_daxiang_creds()
    if client_id and client_secret:
        if verbose:
            print("✅ 大象推送凭证已配置")
    else:
        issues.append("⚠️  大象推送凭证未配置（openclaw.json 中无 daxiang channel config）")

    # 5. 群推送凭证（如果有群任务）
    try:
        with open(CRON_CONFIG_PATH) as f:
            cfg = json.load(f)
        has_group_job = any(
            "group:" in (j.get("poll", {}).get("daxiang_target") or "")
            for j in cfg.get("jobs", [])
        )
        if has_group_job:
            gcid, gsec = _load_group_speaker_creds()
            if gcid and gsec:
                if verbose:
                    print("✅ 群推送凭证已配置")
            else:
                issues.append("❌ 有群推送任务但 group_client_id/group_client_secret 未配置")
            if not os.path.exists(GROUP_SPEAKER_SEND_SCRIPT):
                issues.append(f"❌ claw-group-speaker 未安装: {GROUP_SPEAKER_SEND_SCRIPT}")
    except Exception:
        pass

    # 6. cron 任务注册一致性检查
    try:
        r = subprocess.run(["openclaw", "cron", "list", "--json"], capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            cron_data = json.loads(r.stdout)
            cron_jobs = cron_data.get("jobs", []) if isinstance(cron_data, dict) else cron_data
            cron_names = {j.get("name", "") for j in cron_jobs}
            with open(CRON_CONFIG_PATH) as f:
                cfg = json.load(f)
            for j in cfg.get("jobs", []):
                _jid = j.get('id', '<unknown>')
                expected_cron = f"keeta-alert-{_jid}"
                if expected_cron not in cron_names:
                    issues.append(f"❌ 任务 {_jid} 在配置中存在但 cron 未注册（名: {expected_cron}）")
                elif verbose:
                    print(f"✅ 任务 {_jid} cron 已注册")
    except Exception as e:
        issues.append(f"⚠️  无法检查 cron 注册状态: {e}")

    # 汇总
    if issues:
        print(f"\n{'='*50}")
        print(f"🔍 自检发现 {len(issues)} 个问题：\n")
        for issue in issues:
            print(f"  {issue}")
        print(f"\n{'='*50}")
    elif verbose:
        print(f"\n✅ 所有检查通过，告警系统就绪！")

    return len(issues) == 0, issues


def _load_daxiang_creds():
    try:
        with open(os.path.expanduser("~/.openclaw/openclaw.json")) as f:
            cfg = json.load(f)
        dx = cfg.get("channels", {}).get("daxiang", {})
        return dx.get("clientId", ""), dx.get("clientSecret", "")
    except Exception:
        return "", ""


def _load_group_speaker_creds():
    """从 cron_config.json 读取群推送机器人凭证（group_client_id / group_client_secret）。"""
    try:
        with open(CRON_CONFIG_PATH) as f:
            cfg = json.load(f)
        cid = cfg.get("group_client_id", "").strip()
        sec = cfg.get("group_client_secret", "").strip()
        return cid, sec
    except Exception:
        return "", ""


def _upload_image_to_sankuai(image_path):
    """上传本地图片到 file.vip.sankuai.com，返回图片 URL 或 None。"""
    import requests as _req
    import uuid
    try:
        filename = os.path.basename(image_path)
        with open(image_path, "rb") as f:
            file_data = f.read()
        _tenant_id = os.environ.get("SANKUAI_FILE_TENANT_ID", "1501437563754258442")
        _access_key = os.environ.get("SANKUAI_FILE_ACCESS_KEY", "4427e507ade34bd1b216a02558541051")
        if not _access_key:
            raise RuntimeError(
                "环境变量 SANKUAI_FILE_ACCESS_KEY 未设置，无法上传图片。"
                "请设置: export SANKUAI_FILE_ACCESS_KEY=<your_access_key>"
            )
        if not _tenant_id:
            raise RuntimeError(
                "环境变量 SANKUAI_FILE_TENANT_ID 未设置，无法上传图片。"
                "请设置: export SANKUAI_FILE_TENANT_ID=<your_tenant_id>"
            )
        resp = _req.post(
            "https://file.vip.sankuai.com/file/images",
            files={"file": (filename, file_data, "image/png")},
            data={
                "tenantId": _tenant_id,
                "accessKey": _access_key,
                "fileName": filename,
                "creator": "openclaw-alert",
                "bizFileId": f"image/{uuid.uuid4()}",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        is_ok = data.get("isSuccess") or data.get("success")
        items = data.get("fileItems", [])
        if is_ok and items and len(items) > 0:
            url = items[0].get("url", "")
            if url:
                print(f"[INFO] 图片上传成功: {url}", file=sys.stderr)
                return url
        print(f"[WARN] 图片上传响应异常: {data}", file=sys.stderr)
    except Exception as e:
        print(f"[WARN] 图片上传失败: {e}", file=sys.stderr)
    return None


def _resolve_target(target):
    """解析推送目标。

    支持格式：
      - None / "self" / 空 → 发给 owner（默认）
      - "group:<ID>" → 发到指定群

    Returns: ("self", owner_uid) 或 ("group", group_id)
    """
    if not target or str(target).strip().lower() == "self":
        uid = _get_default_owner_uid() or ""
        return ("self", uid)
    s = str(target).strip()
    if s.startswith("group:"):
        return ("group", s.split(":", 1)[1])
    # 兼容旧配置：纯数字当 owner uid
    if s.isdigit():
        return ("self", s)
    # 未知格式 fallback 到 owner
    print(f"[WARN] 未识别的 target 格式 '{s}'，fallback 到 owner", file=sys.stderr)
    uid = _get_default_owner_uid() or ""
    return ("self", uid)


def _send_image_via_daxiang(image_path, target=None):
    """上传图片后通过 API 发送。
    - self 目标：daxiang-sender --image-url
    - group 目标：claw-group-speaker dx_send_msg.py --type image（需 ensure_claw_group_speaker）
    """
    image_url = _upload_image_to_sankuai(image_path)
    if not image_url:
        print("[WARN] 图片上传失败，跳过图片发送", file=sys.stderr)
        return

    ttype, tvalue = _resolve_target(target)
    env = os.environ.copy()
    env["PATH"] = os.path.expanduser("~/bin") + ":" + env.get("PATH", "")

    if ttype == "group":
        # 群推送：用 claw-group-speaker dx_send_msg.py
        if not ensure_claw_group_speaker():
            print("[WARN] claw-group-speaker 不可用，跳过群图片发送", file=sys.stderr)
            return
        gcid, gsec = _load_group_speaker_creds()
        if not gcid:
            print("[WARN] 未配置 group_client_id，跳过群图片发送", file=sys.stderr)
            return
        # dx_send_msg.py --image 只接受本地路径，需先下载
        import tempfile
        proxy = "http://nocode-supabase-squid.sankuai.com:443"
        tmp_img = tempfile.mktemp(suffix=".png")
        dl = subprocess.run(
            ["curl", "-sL", "-x", proxy, "-o", tmp_img, image_url],
            capture_output=True, timeout=30
        )
        if dl.returncode != 0 or not os.path.exists(tmp_img):
            print(f"[WARN] 图片下载失败，跳过群图片发送: {dl.stderr}", file=sys.stderr)
            return
        cmd = ["python3", GROUP_SPEAKER_SEND_SCRIPT,
               "--client-id", gcid, "--client-secret", gsec,
               "--gid", tvalue, "--type", "image", "--image", tmp_img]
    else:
        # 个人推送：daxiang-sender
        client_id, client_secret = _load_daxiang_creds()
        if not client_id:
            print("[WARN] 无大象凭证，跳过图片发送", file=sys.stderr)
            return
        cmd = ["python3", DAXIANG_SEND_SCRIPT, "send",
               "--client-id", client_id, "--client-secret", client_secret,
               "--to", tvalue, "--image-url", image_url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
        if r.returncode != 0:
            print(f"[WARN] image send failed: rc={r.returncode}, {r.stderr}", file=sys.stderr)
    except Exception as e:
        print(f"[WARN] _send_image_via_daxiang error: {e}", file=sys.stderr)
    finally:
        # 清理群推送的临时下载文件
        if ttype == "group":
            try:
                if "tmp_img" in dir() and os.path.exists(tmp_img):
                    os.unlink(tmp_img)
            except Exception:
                pass




def send_daxiang(message, target=None):
    """发送大象消息。
    - self 目标：daxiang-sender
    - group 目标：claw-group-speaker dx_send_msg.py（需配置 group_client_id/secret）
    """
    import time
    ttype, tvalue = _resolve_target(target)
    env = os.environ.copy()
    env["PATH"] = os.path.expanduser("~/bin") + ":" + env.get("PATH", "")

    if ttype == "group":
        # 群推送：用 claw-group-speaker
        if not ensure_claw_group_speaker():
            print("[WARN] claw-group-speaker 不可用，跳过群消息发送", file=sys.stderr)
            return
        gcid, gsec = _load_group_speaker_creds()
        if not gcid:
            print("[WARN] 未配置 group_client_id，跳过群消息发送。请在 cron_config.json 中配置 group_client_id/group_client_secret", file=sys.stderr)
            return
        cmd = ["python3", GROUP_SPEAKER_SEND_SCRIPT,
               "--client-id", gcid, "--client-secret", gsec,
               "--gid", tvalue, "--type", "text", "--text", message]
    else:
        # 个人推送：daxiang-sender
        client_id, client_secret = _load_daxiang_creds()
        if not client_id:
            with open(ALERT_OUTPUT_FILE, "w") as f:
                json.dump({"ts": time.time(), "message": message}, f, ensure_ascii=False)
            return
        cmd = ["python3", DAXIANG_SEND_SCRIPT, "send",
               "--client-id", client_id, "--client-secret", client_secret,
               "--to", tvalue, "--text", message, "--markdown"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
        if r.returncode != 0:
            print(f"[WARN] daxiang send failed: rc={r.returncode}, {r.stderr}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"[WARN] 推送超时（30s），跳过", file=sys.stderr)


# ══════════════════════════════════════════════════════════
# Feature 2: 运力供需异动监控（统计异常检测，无固定阈值）
# ══════════════════════════════════════════════════════════

# ── Feature 2 数据集元信息 ────────────────────────────────

F2_GRANULARITY = {
    "city": {"dim_field": "op_city_name",        "dim_label": "业务城市", "dim_label_en": "City-Level"},
    "zone": {"dim_field": "delivery_area_name",   "dim_label": "配送区域", "dim_label_en": "Zone-Level"},
}

FEATURE2_DATASETS = {
    "60051927": {
        "label":     "供需&归因指标",
        "dim_field": "delivery_area_name",
        "time_field": "10_minutes_str_HH_mm_code",
    },
    "60009475": {
        "label":     "排班出勤指标",
        "dim_field": "delivery_area_name",
        "time_field": "10_minutes_str_HH_mm_code",
    },
}

# ── 功能3：商家出餐体验异动告警 ────────────────────────────
FEATURE3_GROUP1_KEYS = ["meal_preparation_delay_merchant_num", "meal_preparation_delay_merchant_ratio"]
FEATURE3_GROUP2_KEYS = ["unaccepted_task_num", "last_20min_meal_waiting_dura_task_avg"]
FEATURE3_ALL_KEYS    = FEATURE3_GROUP1_KEYS + FEATURE3_GROUP2_KEYS

# 功能3 聚合层数据集（第一组复用功能1数据集，第二组复用功能2数据集60051927）
FEATURE3_AGG_DATASETS = {
    "city": {
        "group1": "60038303",
        "group2": "60051927",
    },
    "zone": {
        "group1": "62059270",
        "group2": "60051927",
    },
}

# 功能3 商家明细数据集（复用 group2，统一维护）
FEATURE3_MERCHANT_DATASET_ID = FEATURE3_AGG_DATASETS["city"]["group2"]

# 功能3 支持的地区（worldwide，含 HK）
FEATURE3_REGIONS = ["SA", "AE", "QA", "KW", "BH", "HK", "BR"]

# 功能3 默认 Top N
FEATURE3_DEFAULT_TOP_N = 5

# Layer 1: 供需紧张判定（全部来自 60051927）
# 方案（2026-04-28 更新）：
#   - trigger:    3 个触发指标，固定阈值判断（任一超阈值 → 触发告警）
#   - reference:  2 个参考指标，仅展示当前值 + WoW（不触发告警，无统计检测）
#
# role: "trigger" / "reference"
# direction: "negative" = 值越高越差, "positive" = 值越高越好
FEATURE2_LAYER1_METRICS = {
    # ── Trigger（阈值触发，瞬时指标，不展示 WoW） ──
    "last_20min_supply_demand_ratio":         {"label": "Supply-Demand Ratio (L20min)",    "en": "Supply-Demand Ratio (L20min)",       "parse": "num",  "role": "trigger",      "direction": "negative", "op": ">", "threshold": 0.6,  "show_wow": False},
    "undelivered_timeout_task_rate":          {"label": "Timeout Task Rate (Undelivered)", "en": "Undelivered Timeout Task Rate",      "parse": "rate", "role": "trigger",      "direction": "negative", "op": ">", "threshold": 0.12, "show_wow": False},
    "rider_load":                             {"label": "Rider Load",                      "en": "Rider Load",                         "parse": "num",  "role": "trigger",      "direction": "negative", "op": ">", "threshold": 0.8,  "show_wow": False},
    # ── Reference（仅展示，不触发告警） ──
    # delivery_dura_ordavg: 当天累计 ATA（分钟），today 用 snapshot，WoW 用 time_range_agg（上周同天 00:00~latest_slot 累计）。
    "delivery_dura_ordavg":                   {"label": "ATA (min)",                       "en": "ATA (min)",                          "parse": "num",  "role": "reference",    "direction": "negative", "show_wow": True},
    # assigned_unaccepted_timeout_task_num: 瞬时指标，不展示 WoW
    "assigned_unaccepted_timeout_task_num":   {"label": "Assigned Unaccepted Timeout Tasks", "en": "Assigned Unaccepted Timeout Tasks", "parse": "num",  "role": "reference",    "direction": "negative", "show_wow": False},
}

# 按角色分组（方便代码引用）
FEATURE2_L1_TRIGGER_KEYS     = [k for k, v in FEATURE2_LAYER1_METRICS.items() if v["role"] == "trigger"]
FEATURE2_L1_REF_KEYS         = [k for k, v in FEATURE2_LAYER1_METRICS.items() if v["role"] == "reference"]

# Layer 2: 归因指标
# online_rate_of_scheduled 来自 60009475，其余来自 60051927
# direction: "positive" = 值越高越好（下降=异常），"negative" = 值越高越差（上升=异常）
# 排列顺序：需求侧 → 运力总量 → 运力效率（与向导展示一致）
FEATURE2_LAYER2_METRICS = {
    # ── 📈 Demand ──
    "push_ord_num":                                        {"label": "Pushed Orders",              "en": "Pushed Orders",                    "parse": "num",  "direction": "negative",  "dataset": "60051927", "attribution": "Demand Surge",           "group": "Demand"},
    # ── 👥 Capacity Volume ──（顺序：在线骑手数 → 排班在线率 → FL在线率 → 骑手坐标上报率）
    "currently_online_courier_num":                         {"label": "Online Courier Num",         "en": "Online Courier Num",               "parse": "num",  "direction": "positive",  "dataset": "60051927", "attribution": "Insufficient Capacity",  "group": "Capacity Volume"},
    "online_rate_of_scheduled":                            {"label": "Online Rate of Scheduled",   "en": "Online Rate of Scheduled",         "parse": "rate", "direction": "positive",  "dataset": "60009475", "attribution": "Low Attendance Rate",    "group": "Capacity Volume"},
    "fl_online_rate_of_courier":                           {"label": "FL Online Rate",             "en": "FL Online Rate",                   "parse": "rate", "direction": "positive",  "dataset": "60051927", "attribution": "FL Low Attendance",      "group": "Capacity Volume"},
    "online_courier_location_reporting_ratio":             {"label": "Courier Location Rate",      "en": "Courier Location Reporting Rate",  "parse": "rate", "direction": "positive",  "dataset": "60051927", "attribution": "No GPS Signal",          "group": "Capacity Volume"},
    # ── ⚙️ Capacity Efficiency ──
    "delivering_courier_num":                              {"label": "Delivering Courier Num",     "en": "Delivering Courier Num",           "parse": "num",  "direction": "positive",  "dataset": "60051927", "attribution": "Low Utilization",        "group": "Capacity Efficiency"},
    "delivery_ider_utilization_rate":                      {"label": "Rider Utilization Rate",     "en": "Rider Utilization Rate",           "parse": "rate", "direction": "positive",  "dataset": "60051927", "attribution": "Low Utilization",        "group": "Capacity Efficiency"},
    "one_on_one_assign_rejection_rate":                    {"label": "1-on-1 Assign Rejection Rate", "en": "1-on-1 Assign Rejection Rate",   "parse": "rate", "direction": "negative",  "dataset": "60051927", "attribution": "Courier Rejection",      "group": "Capacity Efficiency"},
}


# ── Feature 2 时间槽计算 ─────────────────────────────────

def get_recent_slots(region, n=6, slot_minutes=10):
    """获取最近 n 个 10 分钟时间槽（region 本地时间）。

    Returns:
        (today_dt_str, [slot_strs], last_week_dt_str, [last_week_slot_strs])
        slot_strs 从旧到新排列，last_week_slot_strs 对应所有 n 个 slot 上周同一时间。
        如果 n 个 slot 跨越午夜，返回值中 today_dt_str 是最新 slot 的日期，
        但 slots 中可能包含前一天的 slot —— 调用方需要按 slot 所在日期分组查询。
    """
    tz = REGION_TZ.get(region, REGION_TZ["SA"])
    now = datetime.now(tz)

    # 对齐到最近的 10 分钟边界，查上一个已结束的 slot。
    # 例：17:01 执行 → current_slot=17:00 → latest=16:50（查 16:50-17:00 的数据）
    # cron 延后 1 分钟执行（1-59/10），确保上一个 slot 数据已入库。
    current_slot_min = (now.minute // slot_minutes) * slot_minutes
    current_slot = now.replace(minute=current_slot_min, second=0, microsecond=0)
    latest = current_slot - timedelta(minutes=slot_minutes)

    # 生成 n 个 slot（从旧到新）
    slot_datetimes = []
    for i in range(n):
        t = latest - timedelta(minutes=i * slot_minutes)
        slot_datetimes.append(t)
    slot_datetimes.reverse()  # oldest first

    today_dt = latest.strftime("%Y%m%d")
    slots = [t.strftime("%H:%M") for t in slot_datetimes]

    # WoW: 上周同一天同一时间（返回所有 n 个 slot 对应的上周 slot）
    last_week_latest = latest - timedelta(days=7)
    last_week_dt = last_week_latest.strftime("%Y%m%d")
    last_week_slots = [t.strftime("%H:%M") for t in
                       sorted((latest - timedelta(days=7) - timedelta(minutes=i * slot_minutes))
                              for i in range(n))]

    return today_dt, slots, last_week_dt, last_week_slots


def _group_slots_by_date(region, n=6, slot_minutes=10):
    """将最近 n 个 slot 按日期分组（处理跨午夜场景）。

    Returns:
        groups: list of (dt_str, [slot_strs]) — 今日按日期分组
        lw_groups: list of (dt_str, [slot_strs]) — 上周同时段按日期分组
        last_week_dt_str: 主 WoW 日期（last_week_latest 所在日期，用于 snapshot 查询）
        last_week_slot_strs: 所有 WoW slot 字符串（扁平列表，向后兼容）
    """
    tz = REGION_TZ.get(region, REGION_TZ["SA"])
    now = datetime.now(tz)
    current_slot_min = (now.minute // slot_minutes) * slot_minutes
    current_slot = now.replace(minute=current_slot_min, second=0, microsecond=0)
    latest = current_slot - timedelta(minutes=slot_minutes)

    slot_datetimes = []
    for i in range(n):
        t = latest - timedelta(minutes=i * slot_minutes)
        slot_datetimes.append(t)
    slot_datetimes.reverse()

    # 今日：按日期分组
    date_groups = OrderedDict()
    for t in slot_datetimes:
        dt_str = t.strftime("%Y%m%d")
        slot_str = t.strftime("%H:%M")
        date_groups.setdefault(dt_str, []).append(slot_str)
    groups = [(dt, slots) for dt, slots in date_groups.items()]

    # WoW：同样按日期分组（修复跨午夜时单一 lw_dt 的问题）
    lw_slot_datetimes = [latest - timedelta(days=7) - timedelta(minutes=i * slot_minutes) for i in range(n)]
    lw_slot_datetimes.reverse()
    lw_date_groups = OrderedDict()
    for t in lw_slot_datetimes:
        dt_str = t.strftime("%Y%m%d")
        slot_str = t.strftime("%H:%M")
        lw_date_groups.setdefault(dt_str, []).append(slot_str)
    lw_groups = [(dt, slots) for dt, slots in lw_date_groups.items()]

    last_week_latest = latest - timedelta(days=7)
    last_week_dt = last_week_latest.strftime("%Y%m%d")
    last_week_slots = sorted(set(s for _, slots in lw_groups for s in slots))

    return groups, lw_groups, last_week_dt, last_week_slots


# ── Feature 2 数据查询 ───────────────────────────────────

def run_kdata_with_time_filter(dataset_id, region, measures, dim_field, dt, time_slots, time_field="10_minutes_str_HH_mm_code"):
    """查询 kdata 并按日期和时间槽过滤。

    Args:
        dataset_id: 数据集 ID
        region: 地区代码
        measures: 指标字段列表
        dim_field: 维度字段（delivery_area_name）
        dt: 日期字符串 YYYYMMDD
        time_slots: 时间槽列表 ["HH:MM", ...]
        time_field: 时间维度字段名（默认 10min，60009475 用 5_minutes_str_HH_mm_code）

    Returns:
        list of rows, each row contains dim_field + time_field + measures
    """
    cmd = [
        "kdata", "--task-id", "alert-query", "--task-name", "realtime-alert",
        "--json", "standard", "query",
        "--dataset", dataset_id,
        "--measures", *measures,
        "--date", f"{dt}~{dt}",
        "--region", region,
        "--group-by", f"{dim_field},{time_field}",
    ]
    time_filter_val = ",".join(time_slots)
    cmd.extend(["-f", f"{time_field}={time_filter_val}"])
    return _run_kdata_raw(cmd, timeout=90) or []


def run_kdata_time_range_agg(dataset_id, region, measures, dim_field, dt, time_slots, time_field="10_minutes_str_HH_mm_code"):
    """查询 kdata，按时间范围过滤但只按 zone 聚合（不 group-by 时间维度）。

    与 run_kdata_with_time_filter 不同，这里只按 dim_field 分组，
    时间维度仅用于 WHERE 过滤，返回的是 time_range 内的聚合值。
    用于查询"截至某时间点的日内累计 ATA"等场景。

    Args:
        dataset_id: 数据集 ID
        region: 地区代码
        measures: 指标字段列表
        dim_field: 维度字段
        dt: 日期字符串 YYYYMMDD
        time_slots: 时间槽列表 ["HH:MM", ...]，表示 00:00~latest_slot 的全部 slot
        time_field: 时间维度字段名

    Returns:
        list of rows ({dim_field: value, measure1: value, ...})
    """
    if not measures or not time_slots:
        return []
    cmd = [
        "kdata", "--task-id", "alert-query", "--task-name", "realtime-alert",
        "--json", "standard", "query",
        "--dataset", dataset_id,
        "--measures", *measures,
        "--date", f"{dt}~{dt}",
        "--region", region,
        "--group-by", dim_field,  # 只按 zone 分组，不按时间
    ]
    time_filter_val = ",".join(time_slots)
    cmd.extend(["-f", f"{time_field}={time_filter_val}"])
    return _run_kdata_raw(cmd, timeout=90) or []


# ── Feature 2 占位值过滤 ─────────────────────────────────

def _f2_get_value(row, key, metrics_dict):
    """解析 Feature 2 指标值并过滤占位值。

    与 Feature 1 的 get_value 类似，但使用 Feature 2 的指标元信息。
    占位值过滤规则：
      - 原始值为 '-' / None / '' → 直接返回 None（真实缺数，不走 0 值过滤）
      - rate 类 >= 9.0 或 <= -999 → None
      - num 类 >= 9000 或 <= -999 → None
    """
    m = metrics_dict[key]
    raw = row.get(key, 0)
    # 原始占位符 '-' / None / '' 直接视为无数据，不解析为 0.0 后误判
    if raw is None or raw == "-" or raw == "":
        return None
    val = parse_rate(raw) if m["parse"] == "rate" else parse_num(raw)

    # 高占位值过滤
    if m["parse"] == "rate" and val >= 9.0:     return None
    if m["parse"] == "num"  and val >= 9000.0:  return None
    # 低占位值过滤
    if m["parse"] == "rate" and val <= -999.0:  return None
    if m["parse"] == "num"  and val <= -999.0:  return None

    # rate 类指标 val==0 视为占位值（前置条件不满足时数据集返回 0）
    # one_on_one_assign_rejection_rate / undelivered_timeout_task_rate 的 0 是有效值，排除
    _F2_RATE_ZERO_VALID = {"one_on_one_assign_rejection_rate", "undelivered_timeout_task_rate"}
    if m["parse"] == "rate" and val == 0.0 and key not in _F2_RATE_ZERO_VALID:
        return None

    return val


# ── Feature 2 统计计算 ───────────────────────────────────

def _calc_mean_stddev(values):
    """计算均值和标准差。values 为非空浮点数列表。"""
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    mean = sum(values) / n
    if n == 1:
        return mean, 0.0
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)  # sample stddev
    return mean, math.sqrt(variance)


def _wow_change(current, wow_val, parse_type=None):
    """计算 WoW 变化。

    parse_type="rate" → 绝对差值 current - wow（单位 pp，如 0.053 = 5.3pp）
    parse_type="num" 或 None → 相对变化率 (current - wow) / |wow|（如 0.14 = 14%）
    """
    if wow_val is None:
        return None
    if parse_type == "rate":
        # wow_val==0 视为数据缺失（新指标预热期），返回 None 防止虚假大幅 WoW（如 +87pp）
        if wow_val == 0:
            return None
        return current - wow_val
    if wow_val == 0:
        # num 类 WoW 是相对变化率，wow_val=0 会除零，返回 None
        return None
    return (current - wow_val) / abs(wow_val)


def _organize_by_zone_and_slot(rows, dim_field, time_field, metric_keys, metrics_dict):
    """将 kdata 返回的行数据按 zone → slot → metric 组织。

    Returns:
        dict: {zone_name: {slot_str: {metric_key: float_value}}}
    """
    result = defaultdict(lambda: defaultdict(dict))
    for row in rows:
        zone = row.get(dim_field, "-")
        slot = row.get(time_field, "-")
        for key in metric_keys:
            if key in metrics_dict:
                val = _f2_get_value(row, key, metrics_dict)
            else:
                # 辅助字段（delivered_task_num, push_ord_num 等）直接解析
                val = parse_num(row.get(key, 0))
            if val is not None:
                result[zone][slot][key] = val
    return result


# ── Feature 2 异常检测 ───────────────────────────────────

def _detect_layer1_tension(zone_slots, latest_slot, all_slots, wow_data, zone_name, threshold_overrides=None):
    """Layer 1: 检测某个 zone 是否处于供需紧张状态。

    v2 改版（2026-04-28）：
      - Trigger 指标（3个）：固定阈值判断，任一超阈值即触发。**全部展示**，超阈值的标记 triggered=True。
      - 触发指标都是瞬时指标，不展示 WoW。
      - Reference 指标（2个）：仅展示，不触发告警。根据 show_wow 决定是否展示 WoW。

    Args:
        zone_slots: {slot_str: {metric: value}} — 今日该 zone 的时间序列数据
        latest_slot: str — 最新 slot 名称
        all_slots: list[str] — 所有 slot 名称（从旧到新）
        wow_data: {metric: value} — 上周同一 slot 的数据（用于 reference 的 WoW）
        zone_name: str — zone 名称（用于日志）

    Returns:
        (is_tense: bool, trigger_details: list[dict], ref_details: list[dict])
    """
    trigger_details = []
    ref_details = []

    latest_data = zone_slots.get(latest_slot, {})

    # ── 1. Trigger 指标：全部展示，标记是否超阈值 ──
    any_triggered = False
    for key in FEATURE2_L1_TRIGGER_KEYS:
        m = FEATURE2_LAYER1_METRICS[key]
        current_val = latest_data.get(key)

        # 占位值过滤
        if current_val is not None:
            if m["parse"] == "rate" and (current_val >= 9.0 or current_val <= -999.0):
                current_val = None
            if m["parse"] == "num" and (current_val >= 9000.0 or current_val <= -999.0):
                current_val = None

        threshold = (threshold_overrides or {}).get(key, m["threshold"])
        op = m["op"]
        triggered = False
        if current_val is not None:
            triggered = (op == ">" and current_val > threshold) or (op == "<" and current_val < threshold)
        if triggered:
            any_triggered = True

        t_str = f"{threshold*100:.0f}%" if m["parse"] == "rate" else f"{threshold:g}"
        trigger_details.append({
            "metric":     key,
            "label":      m["label"],
            "en":         m["en"],
            "current":    current_val,
            "threshold":  threshold,
            "op":         op,
            "triggered":  triggered,
            "reason":     f"{'>' if op == '>' else '<'} {t_str}",
        })

    # ── 2. Reference 指标：仅展示 ──
    for key in FEATURE2_L1_REF_KEYS:
        m = FEATURE2_LAYER1_METRICS[key]
        current_val = latest_data.get(key)
        if current_val is None:
            continue
        # 占位值过滤
        if m["parse"] == "rate" and (current_val >= 9.0 or current_val <= -999.0):
            continue
        if m["parse"] == "num" and (current_val >= 9000.0 or current_val <= -999.0):
            continue
        wow_val = None
        wow_chg = None
        if m.get("show_wow"):
            wow_val = wow_data.get(key)
            wow_chg = _wow_change(current_val, wow_val, parse_type=m["parse"])

        ref_details.append({
            "metric":     key,
            "label":      m["label"],
            "en":         m["en"],
            "current":    current_val,
            "show_wow":   m.get("show_wow", False),
            "wow_val":    wow_val,
            "wow_change": wow_chg,
        })

    is_tense = any_triggered
    return is_tense, trigger_details, ref_details


def _detect_layer2_attribution(zone_slots_ds1, zone_slots_ds2, latest_slot, all_slots, wow_zone_ds1, wow_zone_ds2):
    """Layer 2: 归因分析，返回全部 7 个指标的当前值和 WoW，标记异常。

    对每个 Layer 2 指标，比较最近 3 个 slot 与上周同一 3 个 slot 的周同比：
      - 单 slot WoW 触发：最新 slot 周同比超 ±5%（方向感知）→ anomaly=True
      - 持续性 WoW 触发：全部 3 个 slot 周同比均超 ±5% 且方向一致 → persistent=True

    Returns:
        list[dict] — 全部 7 个指标详情（含 anomaly 标记）
    """
    WOW_THRESHOLD = 0.05  # num: ±5% 相对变化 | rate: ±5pp 绝对差

    attributions = []

    def _is_wow_anomaly(chg, dirn):
        """方向感知判断：positive 指标下降超阈值为异常，negative 指标上升超阈值为异常。
        num 类 chg 为相对变化率，rate 类 chg 为绝对差值（pp）。"""
        if chg is None:
            return False
        if dirn == "positive":
            return chg < -WOW_THRESHOLD
        else:
            return chg > WOW_THRESHOLD

    for key, m in FEATURE2_LAYER2_METRICS.items():
        direction = m["direction"]

        # 根据数据集选择数据源
        if m["dataset"] == "60051927":
            today_slots = zone_slots_ds1
            wow_slots = wow_zone_ds1
            iter_slots = list(all_slots)
            cur_slot = latest_slot
        else:  # 60009475（5min 粒度）
            today_slots = zone_slots_ds2
            wow_slots = wow_zone_ds2
            iter_slots = sorted(today_slots.keys()) if today_slots else []
            cur_slot = iter_slots[-1] if iter_slots else None

        if not cur_slot:
            attributions.append({
                "metric": key, "label": m["label"], "en": m["en"],
                "parse": m["parse"], "attribution": m["attribution"], "group": m.get("group", ""),
                "direction": direction, "current": None, "wow_val": None,
                "wow_change": None, "anomaly": False, "persistent": False, "reasons": [],
            })
            continue

        # ── 最新 slot 的值和 WoW ──
        current_val = today_slots.get(cur_slot, {}).get(key)
        if current_val is None:
            attributions.append({
                "metric": key, "label": m["label"], "en": m["en"],
                "parse": m["parse"], "attribution": m["attribution"], "group": m.get("group", ""),
                "direction": direction, "current": None, "wow_val": None,
                "wow_change": None, "anomaly": False, "persistent": False, "reasons": [],
            })
            continue

        # 找到上周对应最新 slot 的值
        wow_val = None
        if m["dataset"] == "60051927":
            wow_val = wow_slots.get(cur_slot, {}).get(key)
        else:
            wow_sorted = sorted(wow_slots.keys())
            if wow_sorted:
                if cur_slot in wow_slots:
                    wow_val = wow_slots[cur_slot].get(key)
                else:
                    wow_val = wow_slots[wow_sorted[-1]].get(key)

        wow_chg = _wow_change(current_val, wow_val, parse_type=m["parse"])

        # ── skip_wow: 暂时跳过异常判定（历史基准不足） ──
        if m.get("skip_wow"):
            attributions.append({
                "metric": key, "label": m["label"], "en": m["en"],
                "parse": m["parse"], "attribution": m["attribution"], "group": m.get("group", ""),
                "direction": direction, "current": current_val, "wow_val": wow_val,
                "wow_change": wow_chg, "anomaly": False, "persistent": False, "reasons": ["skip_wow: baseline not ready"],
            })
            continue

        # ── 判断最新 slot 是否 WoW 异常 ──
        latest_anomaly = _is_wow_anomaly(wow_chg, direction)

        # ── 持续性检查 ──
        persistent = False
        if latest_anomaly:
            persistent = True
            for s in iter_slots:
                today_val = today_slots.get(s, {}).get(key)
                if today_val is None:
                    persistent = False
                    break
                if m["dataset"] == "60051927":
                    s_wow_val = wow_slots.get(s, {}).get(key)
                else:
                    s_wow_val = wow_slots.get(s, {}).get(key) if s in wow_slots else None
                    if s_wow_val is None and wow_slots:
                        ws = sorted(wow_slots.keys())
                        closest = min(ws, key=lambda x: abs(int(x.replace(":", "")) - int(s.replace(":", ""))))
                        s_wow_val = wow_slots.get(closest, {}).get(key)
                s_wow_chg = _wow_change(today_val, s_wow_val, parse_type=m["parse"])
                if not _is_wow_anomaly(s_wow_chg, direction):
                    persistent = False
                    break

        reasons = []
        if latest_anomaly:
            reasons.append("周同比异常")
            if persistent:
                reasons.append("持续性异常")

        attributions.append({
            "metric":       key,
            "label":        m["label"],
            "en":           m["en"],
            "parse":        m["parse"],
            "attribution":  m["attribution"],
            "group":        m.get("group", ""),
            "direction":    direction,
            "current":      current_val,
            "wow_val":      wow_val,
            "wow_change":   wow_chg,
            "anomaly":      latest_anomaly,
            "persistent":   persistent,
            "reasons":      reasons,
        })

    return attributions


# ── Feature 2 格式化输出 ─────────────────────────────────

def _format_f2_value(val, parse_type, metric_key=None):
    """Feature 2 指标值格式化。

    - rate 类：百分比保留1位小数（如 12.3%）
    - num 类：
      - supply_demand_ratio / rider_load → 保留2位小数（如 0.65）
      - undelivered_timeout_task_rate → 百分比保留2位小数（如 12.34%）
      - 其他 ≥1000 的整数用千分位，其余保留1位小数
    """
    if val is None:
        return "-"
    # 特殊指标精度
    if metric_key in ("last_20min_supply_demand_ratio", "rider_load", "supply_demand_ratio"):
        return f"{val:.2f}"
    if metric_key == "undelivered_timeout_task_rate":
        return f"{val*100:.2f}%"
    # 整数量纲指标（单量、人数等）始终显示为整数
    INTEGER_METRICS = ("push_ord_num", "delivered_task_num", "currently_online_courier_num",
                       "delivering_courier_num", "assigned_unaccepted_task_num",
                       "unaccepted_task_num", "assigned_unaccepted_timeout_task_num",
                       "schedule_courier_num",
                       "meal_preparation_delay_merchant_num")
    if metric_key in INTEGER_METRICS:
        return f"{int(val):,}"
    if parse_type == "rate":
        return f"{val*100:.1f}%" if abs(val) < 10 else f"{val:.2f}"
    else:
        if abs(val) >= 1000:
            return f"{int(val):,}"
        return f"{val:.1f}"


def _format_wow_str(wow_chg, parse_type=None):
    """格式化 WoW 变化。

    parse_type="rate" → 绝对差值，单位 pp（percentage point）
    parse_type="num" 或 None → 相对变化率，单位 %
    """
    if wow_chg is None:
        return "N/A"
    sign = "+" if wow_chg >= 0 else ""
    if parse_type == "rate":
        # wow_chg 已是绝对差值（如 0.053 表示 5.3pp）
        return f"{sign}{wow_chg*100:.1f}pp"
    return f"{sign}{wow_chg*100:.1f}%"


def _build_feature2_text(region, tense_zones, latest_slot, total_tense=None, dim_label="配送区域"):
    """构建 Feature 2 的纯文本告警输出（中文版，v2 改版）。

    v2 改版（2026-04-28）：
      - 3 个触发指标全量展示，超阈值高亮（🔴），未超阈值正常展示（⚪）
      - 触发指标为瞬时指标，不展示 WoW
      - 参考指标：delivery_dura_ordavg（展示 WoW，today=snapshot 累计，WoW=上周同天 00:00~latest_slot 累计），assigned_unaccepted_timeout_task_num（瞬时，无 WoW）

    Args:
        region: 地区
        tense_zones: list of {zone, trigger_details, ref_details, attributions, push_ord_num}
            已按 push_ord_num 降序排序
        latest_slot: 最新 slot 名称
        total_tense: 触发告警的 zone 总数（排序截断前），用于显示"共 N 个，展示 Top N"
        dim_label: 维度标签（"配送区域" 或 "业务城市"）

    Returns:
        str — 纯文本告警消息
    """
    tz = REGION_TZ.get(region, REGION_TZ["SA"])
    now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    if not tense_zones:
        return (
            f"🚨 Keeta 运力供需异动监控: {region} | {dim_label}\n"
            f"⏰ {now_str} (slot: {_slot_range(latest_slot)})\n\n"
            f"✅ 未检测到供需紧张，所有{dim_label}指标正常。"
        )

    if total_tense is None:
        total_tense = len(tense_zones)

    summary = f"⚠️ {total_tense} 个{dim_label}存在供需紧张"
    if total_tense > len(tense_zones):
        summary += f"（按推单量排序，展示 Top {len(tense_zones)}）"
    summary += "："

    lines = [
        f"🚨 Keeta 运力供需异动监控: {region} | {dim_label}",
        f"⏰ {now_str} (slot: {_slot_range(latest_slot)})",
        f"",
        summary,
        f"",
    ]

    for tz_info in tense_zones:
        zone       = tz_info["zone"]
        triggers   = tz_info["trigger_details"]
        refs       = tz_info.get("ref_details", [])
        attribs    = tz_info["attributions"]
        push_vol   = tz_info.get("push_ord_num", 0)

        lines.append(f"━━━ {zone}（近10分钟推配送订单量: {int(push_vol)}）━━━")
        lines.append("")

        # ── 第一层：触发指标（全量展示，超阈值高亮） ──
        lines.append("📊 第一层 — 触发指标：")
        for td in triggers:
            m_info = FEATURE2_LAYER1_METRICS[td["metric"]]
            if td["current"] is not None:
                val_str = _format_f2_value(td["current"], m_info["parse"], metric_key=td["metric"])
            else:
                val_str = "-"
            if td.get("triggered"):
                lines.append(f"  🔴 {m_info['label']}: {val_str} ({td['reason']})")
            else:
                lines.append(f"  ⚪ {m_info['label']}: {val_str}")

        lines.append("")

        # ── 第二层：归因指标（分组展示：需求侧 / 运力总量 / 运力效率） ──
        lines.append("🔍 第二层 — 归因指标（近10分钟）：")
        GROUP_ICONS = {"需求侧": "📈", "运力总量": "👥", "运力效率": "⚙️"}
        current_group = None
        for a in attribs:
            group = a.get("group", FEATURE2_LAYER2_METRICS.get(a["metric"], {}).get("group", ""))
            if group and group != current_group:
                current_group = group
                icon = GROUP_ICONS.get(group, "•")
                lines.append(f"  {icon} {group}:")
            val_str = _format_f2_value(a["current"], a["parse"], metric_key=a["metric"])
            # skip_wow: 历史基准不足时 WoW 显示为 -
            reasons = a.get("reasons", [])
            if any("skip_wow" in r for r in reasons):
                wow_str = "-"
            else:
                wow_str = _format_wow_str(a["wow_change"], parse_type=a["parse"])
            if a.get("anomaly"):
                lines.append(f"    🔴 {a['label']}: {val_str} | WoW: {wow_str}  归因: {a['attribution']}")
            else:
                lines.append(f"    ⚪ {a['label']}: {val_str} | WoW: {wow_str}")

        # ── 参考指标（放在归因后面） ──
        if refs:
            lines.append("")
            lines.append("📌 参考指标：")
            for r in refs:
                m_info = FEATURE2_LAYER1_METRICS[r["metric"]]
                val_str = _format_f2_value(r["current"], m_info["parse"], metric_key=r["metric"])
                if r.get("show_wow"):
                    wow_str = _format_wow_str(r.get("wow_change"))
                    lines.append(f"  • {m_info['label']}: {val_str} | 周同比: {wow_str}")
                else:
                    lines.append(f"  • {m_info['label']}: {val_str}")

        lines.append("")

    return "\n".join(lines)


def _build_feature2_summary(region, tense_zones, latest_slot, total_tense=None, dim_label="配送区域"):
    """构建 Feature 2 的精简摘要版告警（用于 cron 推送，控制在 1500 字以内）。

    每个 zone 最多 3 行：zone名 + 触发指标（全量，超阈值加*标记） + 归因方向。

    Args:
        region: 地区
        tense_zones: list of {zone, trigger_details, ref_details, attributions, push_ord_num}
        latest_slot: 最新 slot 名称
        total_tense: 触发告警的 zone 总数（排序截断前）
        dim_label: 维度标签（"配送区域" 或 "业务城市"）

    Returns:
        str — 精简摘要文本
    """
    EMOJI_NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

    tz = REGION_TZ.get(region, REGION_TZ["SA"])
    now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    header = (
        f"🚨 Keeta 运力供需异动监控: {region} | {dim_label}\n"
        f"⏰ {now_str} (slot: {_slot_range(latest_slot)})"
    )

    if not tense_zones:
        return f"{header}\n\n✅ 未检测到供需紧张，所有{dim_label}指标正常。"

    if total_tense is None:
        total_tense = len(tense_zones)

    n_show = len(tense_zones)
    summary_line = f"⚠️ {total_tense} 个{dim_label}存在供需紧张"
    if total_tense > n_show:
        summary_line += f"（展示 Top {n_show}）"
    summary_line += "："

    lines = [header, "", summary_line, ""]

    for idx, tz_info in enumerate(tense_zones):
        zone     = tz_info["zone"]
        triggers = tz_info["trigger_details"]
        attribs  = tz_info["attributions"]
        push_vol = tz_info.get("push_ord_num", 0)

        emoji = EMOJI_NUMS[idx] if idx < len(EMOJI_NUMS) else f"({idx+1})"

        # Line 1: zone name + push volume
        lines.append(f"{emoji} {zone}（近10分钟推配送订单量: {int(push_vol):,}）")

        # Line 2: trigger metrics (compact, all 3 shown, exceeded ones marked with 🔴)
        if triggers:
            trigger_parts = []
            for td in triggers:
                m_info = FEATURE2_LAYER1_METRICS[td["metric"]]
                label = m_info["label"]
                if td["current"] is not None:
                    val_str = _format_f2_value(td["current"], m_info["parse"], metric_key=td["metric"])
                else:
                    val_str = "-"
                marker = "🔴" if td.get("triggered") else ""
                trigger_parts.append(f"{marker}{label}={val_str}")
            lines.append(f"   触发: {' | '.join(trigger_parts)}")

        # Line 3: attribution directions (only anomaly=True ones)
        anomaly_attribs = [a for a in attribs if a.get("anomaly")]
        if anomaly_attribs:
            directions = []
            seen = set()
            for a in anomaly_attribs:
                d = a["attribution"]
                if d not in seen:
                    seen.add(d)
                    directions.append(d)
            lines.append(f"   归因: {', '.join(directions)}")
        else:
            lines.append(f"   归因: 未识别到明确归因方向")

        lines.append("")

    return "\n".join(lines).rstrip()


# ── Feature 3 HTML/Text 渲染 ─────────────────────────────

def _build_feature3_html(region, triggered_zones, merchant_details, dim_label="配送区域", top_n=5):
    """
    生成功能3的 HTML 告警卡片。
    样式与功能1/2一致：.card 容器，按城市/区域分组，
    Layer1 展示触发指标（超阈值红色），Layer2 展示 Top N 商家明细。

    triggered_zones: list of dict {
        "dim": 城市/区域名（英文）,
        "metrics": [{"key": str, "label": str, "current": float, "threshold": float, "triggered": bool}]
    }
    merchant_details: dict {
        dim_en: {key: [{"merchant_name": str, "merchant_id": str, "value": float}]}
    }
    """
    from datetime import datetime as _dt

    tz = REGION_TZ.get(region, REGION_TZ["SA"])
    now = _dt.now(tz)
    now_str  = now.strftime("%H:%M")
    date_str = now.strftime("%Y-%m-%d")
    dim_label_en = "City-Level" if dim_label == "业务城市" else "Zone-Level"

    total_triggered = len(triggered_zones)
    no_alert = total_triggered == 0

    if no_alert:
        status_color = "#52c41a"
        status_icon  = "✅"
        status_text  = "All metrics normal, no merchant experience anomalies detected"
    else:
        status_color = "#fa541c"
        unit = "city" if "city" in dim_label_en.lower() else "zone"
        units = "cities" if unit == "city" else "zones"
        status_icon  = "⚠️"
        status_text  = f"{total_triggered} {unit if total_triggered == 1 else units} with merchant experience anomalies"

    # ─ 格式化辅助 ─
    def _fmt_val(key, val):
        if val is None:
            return "-"
        meta = ALL_METRICS.get(key, {})
        fmt  = meta.get("format", "f2")
        if fmt == "pct2":
            return f"{val*100:.2f}%"
        if fmt == "int":
            return f"{int(val):,}"
        if fmt == "f1":
            return f"{val:.1f}"
        return f"{val:.2f}"

    def _fmt_thr(key, thr):
        if thr is None:
            return "-"
        meta = ALL_METRICS.get(key, {})
        fmt  = meta.get("format", "f2")
        op   = meta.get("op", ">")
        sym  = ">" if op == ">" else "<"
        if fmt == "pct2":
            return f"{sym} {thr*100:.2f}%"
        if fmt == "int":
            return f"{sym} {int(thr):,}"
        if fmt == "f1":
            return f"{sym} {thr:.1f}"
        return f"{sym} {thr:.2f}"

    # ─ 构建各 zone block ─
    zone_blocks_html = ""
    for zone_info in triggered_zones:
        dim_name = zone_info.get("dim", "-")
        metrics  = zone_info.get("metrics", [])
        triggered_count = sum(1 for m in metrics if m.get("triggered"))

        # Layer 1: 触发指标（仅 GROUP2）+ 参考指标（GROUP1）
        # 构建主体内容：每个 GROUP2 指标后紧跟其商家明细
        metric_rows_html = ""
        ref_rows_html = ""
        dim_merch = merchant_details.get(dim_name, {})

        for m in metrics:
            key = m.get("key", "")
            label = m.get("label", key)
            cur_val = m.get("current")
            thr_val = m.get("threshold")
            is_triggered = m.get("triggered", False)

            val_str = _fmt_val(key, cur_val)

            # GROUP1 指标 → 放入 Reference Metrics 区块
            if key in FEATURE3_GROUP1_KEYS:
                ref_rows_html += f"""
          <div class="metric-item ref-item">
            <div class="metric-name">
              <span class="dot" style="background:#999;"></span>
              {label}
            </div>
            <div class="metric-detail">
              <span class="metric-value" style="color:#333;font-size:15px;">{val_str}</span>
            </div>
          </div>"""
                continue

            # GROUP2 指标 → 触发指标行
            thr_str = _fmt_thr(key, thr_val) if is_triggered else ""
            val_color = "#fa541c" if is_triggered else "#333"
            dot_color = "#fa541c" if is_triggered else "#d9d9d9"

            thr_html = f'<span class="metric-threshold">{thr_str}</span>' if thr_str else ""

            metric_rows_html += f"""
          <div class="metric-item">
            <div class="metric-name">
              <span class="dot" style="background:{dot_color};"></span>
              {label}
            </div>
            <div class="metric-detail">
              <span class="metric-value" style="color:{val_color};">{val_str}</span>
              {thr_html}
            </div>
          </div>"""

            # 如果该指标触发且有商家明细 → 紧跟在指标后面
            if is_triggered and key in dim_merch:
                zone_merchants = dim_merch[key]
                if zone_merchants:
                    rows_html = ""
                    for i, merch in enumerate(zone_merchants[:top_n], 1):
                        mval = merch.get("value")
                        mval_str = _fmt_val(key, mval)
                        rows_html += f"""
              <tr>
                <td class="td-rank">{i}</td>
                <td class="td-name">{merch.get("merchant_name") or merch.get("merchant_id", "-")}</td>
                <td class="td-id">{merch.get("merchant_id", "-")}</td>
                <td class="td-val" style="color:#fa541c;font-weight:600;">{mval_str}</td>
              </tr>"""

                    _g2_meta = ALL_METRICS.get(key, {})
                    key_label = _g2_meta.get("en") or _g2_meta.get("label", key)
                    metric_rows_html += f"""
          <div class="layer2-block">
            <div class="layer2-title">🔍 Top {len(zone_merchants[:top_n])} Merchants — {key_label}</div>
            <table class="merch-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Merchant Name</th>
                  <th>Merchant ID</th>
                  <th>Current Value</th>
                </tr>
              </thead>
              <tbody>{rows_html}
              </tbody>
            </table>
          </div>"""

        # Reference Metrics 区块（GROUP1 指标，灰色背景，放在最后）
        ref_section_html = ""
        if ref_rows_html:
            ref_section_html = f"""
        <div class="ref-section">
          <div class="ref-title">📌 Reference Metrics</div>
          {ref_rows_html}
        </div>"""

        zone_blocks_html += f"""
      <div class="dim-block">
        <div class="dim-header">
          <span class="dim-pin">📍</span>
          <span class="dim-label">{region} | {dim_name}</span>
          <span class="dim-badge">{triggered_count} alert{"s" if triggered_count != 1 else ""}</span>
        </div>
        <div class="layer1-section">
          {metric_rows_html}
        </div>
        {ref_section_html}
      </div>"""

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
    background: linear-gradient(135deg, #ff7a45 0%, #fa541c 100%);
    padding: 16px 20px;
  }}
  .card-header .title {{
    color: #fff;
    font-size: 22px;
    font-weight: 600;
  }}
  .card-header .subtitle {{
    color: rgba(255,255,255,0.85);
    font-size: 14px;
    margin-top: 4px;
  }}
  .card-body {{ padding: 16px 20px; }}
  .info-row {{
    display: flex;
    align-items: center;
    margin-bottom: 8px;
    font-size: 14px;
    color: #666;
  }}
  .info-row .label {{ width: 88px; color: #999; flex-shrink: 0; }}
  .info-row .value {{ color: #333; }}
  .status-bar {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 14px;
    border-radius: 8px;
    margin: 12px 0;
    font-size: 15px;
    font-weight: 500;
  }}
  .status-bar.alert {{ background: #fff2e8; color: #d4380d; border: 1px solid #ffbb96; }}
  .status-bar.ok    {{ background: #f6ffed; color: #389e0d; border: 1px solid #b7eb8f; }}
  .dim-block {{
    margin-top: 12px;
    border: 1px solid #f0f0f0;
    border-radius: 8px;
    overflow: hidden;
  }}
  .dim-header {{
    background: #fafafa;
    padding: 12px 14px;
    font-size: 15px;
    font-weight: 500;
    color: #333;
    border-bottom: 1px solid #f0f0f0;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .dim-badge {{
    background: transparent;
    color: #bfbfbf;
    font-size: 12px;
    font-weight: 600;
    padding: 1px 7px;
    border-radius: 10px;
    border: 1px solid #d9d9d9;
    margin-left: auto;
  }}
  .layer1-section {{ padding: 0 4px; }}
  .section-title {{
    font-size: 12px;
    color: #999;
    font-weight: 600;
    padding: 8px 10px 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .metric-item {{
    padding: 8px 12px;
    border-bottom: 1px solid #f5f5f5;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .metric-item:last-child {{ border-bottom: none; }}
  .metric-name {{
    font-size: 14px;
    color: #333;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 1;
  }}
  .dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }}
  .metric-detail {{
    display: flex;
    align-items: baseline;
    gap: 10px;
    font-size: 14px;
  }}
  .metric-value {{
    font-weight: 600;
    font-size: 17px;
  }}
  .metric-threshold {{
    color: #888;
    font-size: 12px;
  }}
  .ref-section {{
    background: #F8F9FA;
    border-radius: 6px;
    margin: 6px 10px;
    padding: 8px 4px;
  }}
  .ref-title {{
    font-size: 12px;
    font-weight: 600;
    color: #999;
    padding: 0 12px 4px;
  }}
  .ref-item {{
    border-bottom: none !important;
  }}
  .layer2-block {{
    border-top: 1px solid #f0f0f0;
    padding: 10px 14px;
    background: #fffbe6;
  }}
  .layer2-title {{
    font-size: 13px;
    font-weight: 600;
    color: #614700;
    margin-bottom: 8px;
  }}
  .merch-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }}
  .merch-table thead tr {{ background: #fff7e6; }}
  .merch-table th {{
    padding: 5px 8px;
    text-align: left;
    color: #614700;
    font-weight: 600;
    border-bottom: 1px solid #ffe58f;
  }}
  .merch-table td {{
    padding: 5px 8px;
    border-bottom: 1px solid #fff7e6;
    color: #333;
  }}
  .merch-table tbody tr:last-child td {{ border-bottom: none; }}
  .td-rank {{ color: #999; width: 24px; text-align: center; }}
  .td-name {{ max-width: 200px; word-break: break-all; }}
  .td-id   {{ color: #888; }}
  .td-val  {{ }}
  .td-thr  {{ color: #999; }}
  .card-footer {{
    padding: 12px 20px;
    border-top: 1px solid #f0f0f0;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: #999;
  }}
  .footer-dot {{ width: 6px; height: 6px; background: #fa541c; border-radius: 50%; }}
</style>
</head>
<body>
  <div class="card">
    <div class="card-header">
      <div class="title">{region} Merchant Experience Alert</div>
      <div class="subtitle">Keeta Realtime Alert · {dim_label_en}</div>
    </div>
    <div class="card-body">
      <div class="info-row">
        <span class="label">Alert Time</span>
        <span class="value">{date_str} {now_str}</span>
      </div>
      <div class="status-bar {"alert" if not no_alert else "ok"}">
        <span>{status_icon}</span>
        <span>{status_text}</span>
      </div>
      {zone_blocks_html}
    </div>
    <div class="card-footer">
      <div class="footer-dot"></div>
      <span>Keeta Data · Merchant Experience Alert</span>
    </div>
  </div>
</body>
</html>"""
    return html


def _build_feature3_text(region, triggered_zones, merchant_details, dim_label="配送区域", top_n=5):
    """功能3降级纯文本格式"""
    lines = [f"🚨 Merchant Experience Alert: {region} | {dim_label} |"]
    # Part1
    lines.append("--- Aggregated Metrics ---")
    for zone in triggered_zones:
        for m in zone["metrics"]:
            status = "⚠️ ALERT" if m["triggered"] else "✅ OK"
            lines.append(f"  {zone['dim']} | {m['label']} | {m['current']} | thr:{m['threshold']} | {status}")
    # Part2: merchant_details 结构 {dim_en: {key: [merchants]}}
    if merchant_details:
        lines.append("--- Top Merchants ---")
        for dim_en, key_map in merchant_details.items():
            for key, merchants in key_map.items():
                metric_label = ALL_METRICS.get(key, {}).get("en") or ALL_METRICS.get(key, {}).get("label", key)
                lines.append(f"  [{dim_en}] {metric_label}")
                for i, m in enumerate(merchants[:top_n], 1):
                    lines.append(f"    {i}. {m['merchant_name']} (ID:{m['merchant_id']}) | {m['value']}")
    return "\n".join(lines)


# ── Feature 2 主执行函数 ─────────────────────────────────

def run_feature2_alert(regions, interval=10, push_daxiang=False, daxiang_target=None, owner_uid=None, dim_field="delivery_area_name", threshold_overrides=None, dim_thresholds=None, min_push_ord_num=None):
    """执行 Feature 2 运力供需异动监控告警。

    统计方法检测供需紧张状态，并归因到根因方向。
    每个 region 需要 4 次 kdata 查询。
    """
    # dim_label 根据 dim_field 动态确定
    dim_label = "业务城市" if dim_field == "op_city_name" else "配送区域"
    time_field = "10_minutes_str_HH_mm_code"
    _kdata_call_log.clear()  # [TRACKING] 重置计数器
    _all_tense_zone_names: list = []   # [TRACKING] 所有紧张区域名称
    _all_attributions: list    = []    # [TRACKING] 所有归因类型

    # ── 按查询模式拆分指标 ──
    # 某些实时快照指标（supply_demand_ratio、rider_load 等）不支持 10min 时间粒度维度，
    # 只能用 delivery_area_name 单维度查询（返回当天最新快照值）。
    # 而 delivering_courier_num、currently_online_courier_num 等支持 10min 维度。

    # Snapshot measures（不支持 10min slot，用 run_kdata_snapshot 查）
    # Trigger（3个瞬时）+ Reference（全部）
    snapshot_measures = list(set(
        FEATURE2_L1_TRIGGER_KEYS +    # last_20min_supply_demand_ratio, undelivered_timeout_task_rate, rider_load
        FEATURE2_L1_REF_KEYS          # delivery_dura_ordavg, assigned_unaccepted_timeout_task_num
    ))

    # Time-series measures from 60051927（支持 10min slot，用 run_kdata_with_time_filter 查）
    # Layer 2 归因指标 + 辅助量（delivery_dura_ordavg 不在此，其 WoW 由独立的 time_range_agg 查询获取）
    ts_ds1_measures = list(set(
        [k for k, v in FEATURE2_LAYER2_METRICS.items() if v["dataset"] == "60051927"] +
        ["delivered_task_num", "push_ord_num"]  # 用于 zone 最低单量门槛过滤
    ))

    # Time-series measures from 60009475（排班在线率，5分钟粒度）
    ts_ds2_measures = [k for k, v in FEATURE2_LAYER2_METRICS.items() if v["dataset"] == "60009475"]
    DS2_TIME_FIELD = "5_minutes_str_HH_mm_code"  # 60009475 的时间维度是5分钟粒度

    # 所有指标元信息（用于解析数值）
    all_f2_metrics = {}
    all_f2_metrics.update(FEATURE2_LAYER1_METRICS)
    all_f2_metrics.update(FEATURE2_LAYER2_METRICS)

    output_items = []

    for region in regions:
        print(f"[Feature2] 查询 {region}...", file=sys.stderr)

        # 计算时间槽（处理跨午夜）
        date_groups, lw_groups, lw_dt, lw_slots = _group_slots_by_date(region, n=3, slot_minutes=10)
        _, all_slots, _, _ = get_recent_slots(region, n=3, slot_minutes=10)
        latest_slot = all_slots[-1]  # 最新 slot

        # ── 取今日日期（用于 snapshot 查询） ──
        tz = REGION_TZ.get(region, REGION_TZ["SA"])
        today_dt = datetime.now(tz).strftime("%Y%m%d")

        # ─── Query S1: Snapshot — today（Layer 1 Trigger + Reference） ───
        print(f"[Feature2] {region} snapshot 查询...", file=sys.stderr)
        snap_today = run_kdata_snapshot("60051927", region, snapshot_measures, dim_field, today_dt)

        # ─── Query S1w: Snapshot — last week（Layer 1 Reference WoW） ───
        lw_snap_dt = (datetime.now(tz) - timedelta(days=7)).strftime("%Y%m%d")
        print(f"[Feature2] {region} snapshot WoW 查询 (lw={lw_snap_dt})...", file=sys.stderr)
        snap_wow = run_kdata_snapshot("60051927", region, snapshot_measures, dim_field, lw_snap_dt)
        snap_wow_by_zone = {}
        for row in snap_wow:
            zone = row.get(dim_field, "")
            if not zone:
                continue
            snap_wow_by_zone.setdefault(zone, {})
            for k in snapshot_measures:
                raw = row.get(k)
                if raw is not None:
                    m_info = all_f2_metrics.get(k, {})
                    parse_type = m_info.get("parse", "num")
                    try:
                        val = float(str(raw).replace("%", "").replace(",", ""))
                        if parse_type == "rate" and "%" in str(raw):
                            val = val / 100.0
                        snap_wow_by_zone[zone][k] = val
                    except (ValueError, TypeError):
                        pass

        # ─── Query ATA-WoW: 上周同天 ATA 累计值（00:00 ~ latest_slot） ───
        # delivery_dura_ordavg WoW：按 dt 查询 + 时间范围过滤（00:00~latest_slot），不按 slot 分组
        # 这样拿到的是上周同天截至同一时间点的日内累计 ATA，与 today snapshot 口径一致
        ata_wow_slots = []
        h, m = 0, 0
        latest_h, latest_m = int(latest_slot[:2]), int(latest_slot[3:])
        while h < latest_h or (h == latest_h and m <= latest_m):
            ata_wow_slots.append(f"{h:02d}:{m:02d}")
            m += 10
            if m >= 60:
                m = 0
                h += 1
        if ata_wow_slots:
            print(f"[Feature2] {region} ATA WoW time_range_agg 查询 (lw={lw_snap_dt}, slots=00:00~{latest_slot})...", file=sys.stderr)
            ata_wow_rows = run_kdata_time_range_agg(
                "60051927", region, ["delivery_dura_ordavg"], dim_field,
                lw_snap_dt, ata_wow_slots
            )
            for row in ata_wow_rows:
                zone = row.get(dim_field, "")
                if not zone:
                    continue
                raw = row.get("delivery_dura_ordavg")
                if raw is not None:
                    try:
                        val = float(str(raw).replace(",", ""))
                        snap_wow_by_zone.setdefault(zone, {})
                        snap_wow_by_zone[zone]["delivery_dura_ordavg"] = val  # 覆盖 S1w 全天累计值
                    except (ValueError, TypeError):
                        pass

        # ─── Query T1: Time-series from 60051927（Ref B + Layer 2 + volume） ───
        print(f"[Feature2] {region} 时序查询 60051927 (today)...", file=sys.stderr)
        ts_today_ds1 = []
        for dt_str, slots in date_groups:
            rows = run_kdata_with_time_filter("60051927", region, ts_ds1_measures, dim_field, dt_str, slots)
            ts_today_ds1.extend(rows)

        # ─── Query T2: Time-series from 60009475（排班在线率，5min 粒度） ───
        ts_today_ds2 = []
        if ts_ds2_measures:
            print(f"[Feature2] {region} 时序查询 60009475 (today)...", file=sys.stderr)
            # 60009475 使用 5min 粒度，需要计算 5min 对应的 slots
            # 对于每个 10min slot，映射到对应的 5min slot（取前一个5min: e.g. 11:20 → 11:15,11:20）
            # 按日期组织 5min slots（处理跨午夜：00:00 的前置 5min slot 23:55 属于前一天）
            ds2_date_slots = OrderedDict()
            for dt_str, slots_10min in date_groups:
                for s10 in slots_10min:
                    h, m = int(s10[:2]), int(s10[3:])
                    ds2_date_slots.setdefault(dt_str, set()).add(f"{h:02d}:{m:02d}")
                    m5 = m - 5
                    h5 = h
                    if m5 < 0:
                        m5 += 60
                        h5 -= 1
                    if h5 >= 0:
                        ds2_date_slots.setdefault(dt_str, set()).add(f"{h5:02d}:{m5:02d}")
                    elif h5 == -1:
                        # 23:55 属于前一天，计算前一天日期
                        prev_dt = (datetime.strptime(dt_str, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
                        ds2_date_slots.setdefault(prev_dt, set()).add(f"23:{m5:02d}")
            for ds2_dt_str, ds2_slots in ds2_date_slots.items():
                if ds2_slots:
                    rows = run_kdata_with_time_filter("60009475", region, ts_ds2_measures, dim_field, ds2_dt_str, sorted(ds2_slots), time_field=DS2_TIME_FIELD)
                    ts_today_ds2.extend(rows)

        # ─── Query W1: WoW time-series from 60051927（跨日期分组查询）───
        wow_ts_ds1 = []
        for lw_dt_str, lw_dt_slots in lw_groups:
            rows = run_kdata_with_time_filter("60051927", region, ts_ds1_measures, dim_field, lw_dt_str, lw_dt_slots)
            wow_ts_ds1.extend(rows)

        # ─── Query W2: WoW time-series from 60009475（5min 粒度，跨日期分组查询）───
        wow_ts_ds2 = []
        if ts_ds2_measures and lw_groups:
            # 镜像 today DS2 逻辑：按日期组织 5min slots，正确处理跨午夜（23:55 属于前一天）
            wow_ds2_date_slots: dict = OrderedDict()
            for lw_dt_str, lw_dt_slots_10min in lw_groups:
                for s10 in lw_dt_slots_10min:
                    h, m = int(s10[:2]), int(s10[3:])
                    wow_ds2_date_slots.setdefault(lw_dt_str, set()).add(f"{h:02d}:{m:02d}")
                    m5 = m - 5
                    h5 = h
                    if m5 < 0:
                        m5 += 60
                        h5 -= 1
                    if h5 >= 0:
                        wow_ds2_date_slots.setdefault(lw_dt_str, set()).add(f"{h5:02d}:{m5:02d}")
                    elif h5 == -1:
                        # 跨午夜：23:55 属于前一天，计算前一天日期
                        lw_prev_dt = (datetime.strptime(lw_dt_str, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
                        wow_ds2_date_slots.setdefault(lw_prev_dt, set()).add(f"23:{m5:02d}")
            for wow_ds2_dt, wow_ds2_slots in wow_ds2_date_slots.items():
                if wow_ds2_slots:
                    rows = run_kdata_with_time_filter("60009475", region, ts_ds2_measures, dim_field, wow_ds2_dt, sorted(wow_ds2_slots), time_field=DS2_TIME_FIELD)
                    wow_ts_ds2.extend(rows)

        if not snap_today and not ts_today_ds1:
            print(f"[Feature2] {region} 无数据", file=sys.stderr)
            continue

        # ─── 组织 snapshot 数据 by zone → {metric: value}（无 WoW） ───
        snap_by_zone = {}
        for row in snap_today:
            zone = row.get(dim_field, "")
            if not zone:
                continue
            snap_by_zone.setdefault(zone, {})
            for k in snapshot_measures:
                raw = row.get(k)
                if raw is not None:
                    m_info = all_f2_metrics.get(k, {})
                    parse_type = m_info.get("parse", "num")
                    try:
                        val = float(str(raw).replace("%", "").replace(",", ""))
                        if parse_type == "rate" and "%" in str(raw):
                            val = val / 100.0
                        snap_by_zone[zone][k] = val
                    except (ValueError, TypeError):
                        pass

        # ─── 组织 time-series 数据 ───
        ts_zone_ds1 = _organize_by_zone_and_slot(ts_today_ds1, dim_field, time_field, ts_ds1_measures, all_f2_metrics)
        wow_zone_ds1 = _organize_by_zone_and_slot(wow_ts_ds1, dim_field, time_field, ts_ds1_measures, all_f2_metrics)

        # DS2（60009475）用 5min 时间字段
        ts_zone_ds2 = _organize_by_zone_and_slot(ts_today_ds2, dim_field, DS2_TIME_FIELD, ts_ds2_measures, all_f2_metrics) if ts_today_ds2 else {}
        wow_zone_ds2 = _organize_by_zone_and_slot(wow_ts_ds2, dim_field, DS2_TIME_FIELD, ts_ds2_measures, all_f2_metrics) if wow_ts_ds2 else {}

        # ─── 逐 zone 检测 ───
        all_zones = set(snap_by_zone.keys()) | set(ts_zone_ds1.keys())
        tense_zones = []

        for zone in sorted(all_zones):
            snap_data = snap_by_zone.get(zone, {})
            ts_slots_ds1 = ts_zone_ds1.get(zone, {})
            ts_slots_ds2 = ts_zone_ds2.get(zone, {})

            # Full WoW data for Layer 2 (all 3 slots, {slot: {metric: value}})
            wow_full_ds1 = wow_zone_ds1.get(zone, {})
            wow_full_ds2 = wow_zone_ds2.get(zone, {})

            # Flat WoW for Layer 1 (latest slot only)
            wow_ds1_latest = wow_full_ds1.get(lw_slots[-1], {}) if lw_slots else {}

            # 最低单量门槛：latest slot 完单数 < 5 的 zone 跳过
            latest_delivered = ts_slots_ds1.get(latest_slot, {}).get("delivered_task_num")
            latest_pushed = ts_slots_ds1.get(latest_slot, {}).get("push_ord_num")
            min_volume = max(latest_delivered or 0, latest_pushed or 0)
            if min_volume < 5:
                continue

            # 可配置的推单量门槛（可选）：push_ord_num < min_push_ord_num 时跳过告警
            if min_push_ord_num is not None and (latest_pushed or 0) < min_push_ord_num:
                continue

            # ── Layer 1: 检测供需紧张（混合模式） ──
            # 构造 zone_slots：把 snapshot 数据注入 latest_slot，ts 数据保持时序
            combined_slots = {}
            for s in all_slots:
                combined_slots[s] = dict(ts_slots_ds1.get(s, {}))
            if latest_slot not in combined_slots:
                combined_slots[latest_slot] = {}
            combined_slots[latest_slot].update(snap_data)

            # WoW 数据：合并 snapshot WoW + time-series WoW（仅 latest slot，用于 Layer 1）
            # snap_wow_by_zone 中 delivery_dura_ordavg 已被 ATA-WoW 查询覆盖为
            # 上周同天 00:00~latest_slot 的日内累计值（与 today snapshot 口径一致）。
            # wow_ds1_latest（W1 时序 latest slot）包含 Layer 2 归因指标的同 slot WoW 值。
            combined_wow = dict(snap_wow_by_zone.get(zone, {}))
            combined_wow.update(wow_ds1_latest)  # W1 时序覆盖（不含 ATA，ATA 已在 snap_wow_by_zone 中正确设置）
            # dim_thresholds key 统一为英文，zone 先转英文再查
            _zone_en = _to_en(zone)
            _zone_thr = (dim_thresholds or {}).get(_zone_en, {})
            is_tense, trigger_details, ref_details = _detect_layer1_tension(
                combined_slots, latest_slot, all_slots, combined_wow, zone,
                threshold_overrides={**(threshold_overrides or {}), **_zone_thr}
            )

            if not is_tense:
                continue

            # ── Layer 2: 归因分析（ds1 时序 + ds2 时序，传入完整 3 slot WoW 数据） ──
            attributions = _detect_layer2_attribution(
                ts_slots_ds1, ts_slots_ds2, latest_slot, all_slots, wow_full_ds1, wow_full_ds2
            )

            tense_zones.append({
                "zone":              _to_en(zone),
                "trigger_details":   trigger_details,
                "ref_details":       ref_details,
                "attributions":      attributions,
                "push_ord_num":      latest_pushed or 0,
            })

        # ─── 按推单量降序排序 ───
        tense_zones.sort(key=lambda x: x.get("push_ord_num", 0), reverse=True)
        total_tense = len(tense_zones)
        # [TRACKING] 收集紧张区域名称和归因类型
        _all_tense_zone_names.extend(z["zone"] for z in tense_zones)
        for _tz in tense_zones:
            for _att in _tz.get("attributions", []):
                _att_type = _att.get("attribution", "")
                if _att_type and _att.get("anomaly"):
                    _all_attributions.append(_att_type)
        # 城市粒度展示全部；区域粒度只保留 Top 5
        if dim_field == "delivery_area_name":
            tense_zones = tense_zones[:5]

        # ─── 构建输出 ───
        text_msg = _build_feature2_text(region, tense_zones, latest_slot, total_tense=total_tense, dim_label=dim_label)
        print(text_msg, file=sys.stderr)

        # 构建推送文本头 — 直接展示紧张城市/区域名称（最多5个）
        dim_label_en_f2 = "City-Level" if dim_field == "op_city_name" else "Zone-Level"
        _tense_names_all = [_to_en(z["zone"]) for z in tense_zones] if tense_zones else []
        tense_names = ", ".join(_tense_names_all[:5])
        if total_tense and total_tense > 5:
            tense_names += f" etc. ({total_tense} total)"
        elif len(_tense_names_all) > 5:
            tense_names += f" etc. ({len(_tense_names_all)} total)"
        text_header = f"🚨 Capacity Monitoring: {region} | {dim_label_en_f2} | {tense_names}" if _tense_names_all else ""

        text_summary = _build_feature2_summary(region, tense_zones, latest_slot, total_tense=total_tense, dim_label=dim_label)

        # 渲染图片卡片
        image_path = None
        if tense_zones:
            try:
                from render_card import render_feature2_card
                dim_label_en = "City-Level" if dim_field == "op_city_name" else "Zone-Level"
                image_path = render_feature2_card(region, tense_zones, latest_slot, total_tense, dim_label_en=dim_label_en)
                if image_path:
                    print(f"[Feature2][INFO] 已生成图片卡片: {image_path}", file=sys.stderr)
                else:
                    print(f"[Feature2][WARN] 图片渲染返回 None，降级为文本", file=sys.stderr)
            except Exception as e:
                print(f"[Feature2][WARN] 图片渲染失败: {e}，降级为文本", file=sys.stderr)

        output_items.append({
            "region":        region,
            "image_path":    image_path,
            "has_alert":     len(tense_zones) > 0,
            "total_alerts":  len(tense_zones),
            "text_header":   text_header,
            "text_fallback": text_msg,
            "text_summary":  text_summary,
            "daxiang_target": daxiang_target,
        })

    # 写入输出文件（保留，供调试/回溯）
    if push_daxiang and output_items:
        output_data = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "items": output_items,
            "daxiang_target": daxiang_target,
        }
        with open(ALERT_OUTPUT_FILE, "w") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"[Feature2][ALERT_OUTPUT] {ALERT_OUTPUT_FILE}", file=sys.stderr)

        # 直接发大象消息（不依赖 cron agent）
        for item in output_items:
            if not item.get("has_alert"):
                continue
            header = item.get("text_header", "")
            summary = item.get("text_summary", "")
            fallback = item.get("text_fallback", "")
            image_path = item.get("image_path", "")
            target = item.get("daxiang_target") or daxiang_target

            if image_path and os.path.exists(image_path):
                send_daxiang(header, target=target)
                _send_image_via_daxiang(image_path, target=target)
                try:
                    os.unlink(image_path)
                except OSError:
                    pass
            else:
                if summary:
                    send_daxiang(summary, target=target)
                else:
                    msg = header + "\n\n" + fallback if header else fallback
                    send_daxiang(msg, target=target)
        print("[Feature2][INFO] 告警消息已直接发送", file=sys.stderr)

    # [TRACKING] 返回执行统计，供 main() 埋点使用
    _unique_attributions = sorted(set(_all_attributions))
    _daxiang_pushed = push_daxiang and any(i["has_alert"] for i in output_items)
    return {
        "feature":          2,
        "granularity":      "city" if dim_field == "op_city_name" else "zone",
        "regions_queried":  len(regions),
        "regions_with_data": len(output_items),
        "kdata_queries":    len(_kdata_call_log),
        "total_alerts":     sum(i["total_alerts"] for i in output_items),
        "tense_zone_names": list(dict.fromkeys(_all_tense_zone_names)),  # dedup, preserve order
        "layer2_attributions": _unique_attributions,
        "daxiang_pushed":   _daxiang_pushed,
    }


# ── Feature 3 主执行函数 ─────────────────────────────────

def _f3_is_invalid(val, key):
    """功能3无效值过滤（继承现有规则）。"""
    if val is None:
        return True
    m = ALL_METRICS.get(key, {})
    parse = m.get("parse", "num")
    if parse == "rate":
        if val >= 9 or val <= -999:
            return True
    else:  # num
        if val >= 9000 or val <= -999:
            return True
        # 等餐时长 / ME / ATA 类指标：0 表示无完成订单，视为无效
        # unaccepted_task_num / meal_preparation_delay_merchant_num：0 是有效值（无积压/无卡餐）
        _ZERO_INVALID_KEYS = {"last_20min_meal_waiting_dura_task_avg"}
        if val == 0 and key in _ZERO_INVALID_KEYS:
            return True
    return False


def run_feature3_alert(regions, interval=10, push_daxiang=False, daxiang_target=None,
                       owner_uid=None, dim_field="delivery_area_name",
                       threshold_overrides=None, dim_thresholds=None, top_n=5):
    """
    功能3：商家出餐体验异动告警。

    Step1: 聚合层触发判断（4个指标）
    Step2: 商家明细下钻（仅第二组指标触发时执行）

    Args:
        regions:            地区列表
        interval:           轮询间隔（分钟）
        push_daxiang:       是否推送大象消息
        daxiang_target:     推送目标（None=自己，"group:xxx"=群）
        owner_uid:          告警接收人 UID
        dim_field:          维度字段（city: op_city_name, zone: delivery_area_name）
        threshold_overrides: 覆盖阈值 dict
        top_n:              商家明细 Top N 数量

    Returns:
        dict — 执行统计（含 feature=3）
    """
    dim_label    = "业务城市" if dim_field == "op_city_name" else "配送区域"
    dim_label_en = "City-Level" if dim_field == "op_city_name" else "Zone-Level"
    gran_key     = "city" if dim_field == "op_city_name" else "zone"

    _kdata_call_log.clear()
    _total_triggered_zones: list = []

    output_items = []

    for region in regions:
        print(f"[Feature3] 查询 {region}...", file=sys.stderr)

        tz      = REGION_TZ.get(region, REGION_TZ["SA"])
        today   = datetime.now(tz).strftime("%Y%m%d")

        # ─ 数据集选择 ─
        ds_group1 = FEATURE3_AGG_DATASETS[gran_key]["group1"]
        ds_group2 = FEATURE3_AGG_DATASETS[gran_key]["group2"]

        # ─ Step 1a: 查询第一组指标（卡餐商家数/占比，来自功能1数据集） ─
        group1_rows = []
        try:
            cmd_g1 = [
                "kdata", "--task-id", "alert-query", "--task-name", "realtime-alert",
                "--json", "standard", "query",
                "--dataset", ds_group1,
                "--measures", *FEATURE3_GROUP1_KEYS,
                "--date", f"{today}~{today}",
                "--region", region,
                "--group-by", dim_field,
            ]
            result = _run_kdata_raw(cmd_g1, timeout=60)
            if result is None:
                print(f"[Feature3][WARN] {region} group1 查询超时", file=sys.stderr)
                _notify_owner_error(f"f3-{region}", f"group1 查询超时", owner_uid=owner_uid)
            else:
                group1_rows = result
        except Exception as e:
            print(f"[Feature3][WARN] {region} group1 查询失败: {e}", file=sys.stderr)
            _notify_owner_error(f"f3-{region}", f"group1 查询异常: {e}", owner_uid=owner_uid)

        # ─ Step 1b: 查询第二组指标（积压单数/等餐时长，来自 60051927）─
        # 60051927 有 10min time_slot，使用 snapshot 取当天最新快照值（与功能2 Layer1 Trigger 一致）
        group2_rows = []
        try:
            group2_rows = run_kdata_snapshot(ds_group2, region, FEATURE3_GROUP2_KEYS, dim_field, today)
            if group2_rows is None:
                group2_rows = []
        except Exception as e:
            print(f"[Feature3][WARN] {region} group2 查询失败: {e}", file=sys.stderr)

        if not group1_rows and not group2_rows:
            print(f"[Feature3] {region} 无数据", file=sys.stderr)
            continue

        # ─ 按维度整合两组数据 ─
        zone_data: dict = {}       # dim_en → {metric_key: value}
        zone_raw_name: dict = {}   # dim_en → 原始维度值（用于 --filter 查询）

        def _parse_row(row, keys):
            raw_name = row.get(dim_field, "")
            dim_name = _to_en(raw_name)
            if not dim_name:
                return
            zone_data.setdefault(dim_name, {})
            zone_raw_name.setdefault(dim_name, raw_name)  # 保留原始名（中文/英文）
            for k in keys:
                raw = row.get(k)
                if raw is None:
                    continue
                meta = ALL_METRICS.get(k, {})
                parse_type = meta.get("parse", "num")
                try:
                    val = float(str(raw).replace("%", "").replace(",", ""))
                    if parse_type == "rate" and "%" in str(raw):
                        val /= 100.0
                    zone_data[dim_name][k] = val
                except (ValueError, TypeError):
                    pass

        for row in group1_rows:
            _parse_row(row, FEATURE3_GROUP1_KEYS)
        for row in group2_rows:
            _parse_row(row, FEATURE3_GROUP2_KEYS)

        # ─ 判断触发 ─
        triggered_zones = []  # [{dim, metrics: [{key, label, current, threshold, triggered}]}]

        for dim_name, vals in sorted(zone_data.items()):
            # dim_thresholds key 已统一为英文（_normalize_dim_thresholds 转换），dim_name 也是英文
            thr_overrides = {**(threshold_overrides or {}), **((dim_thresholds or {}).get(dim_name, {}))}
            metrics_info = []
            any_triggered = False  # Only GROUP2 keys can trigger

            for key in FEATURE3_ALL_KEYS:
                meta = ALL_METRICS.get(key, {})
                val  = vals.get(key)

                if _f3_is_invalid(val, key):
                    continue

                # 确定阈值
                if key in thr_overrides:
                    thr = thr_overrides[key]
                elif dim_field == "op_city_name":
                    thr = meta.get("thr_city")
                else:
                    thr = meta.get("thr_area")

                if thr is None:
                    continue

                op        = meta.get("op", ">")
                triggered = (op == ">" and val > thr) or (op == "<" and val < thr)

                # 方案A: 只有 GROUP2 指标（积压任务单数、等餐时长）参与触发判断
                # GROUP1 指标（卡餐商家数/占比）仅作为补充信息展示，不触发告警
                if triggered and key in FEATURE3_GROUP2_KEYS:
                    any_triggered = True

                metrics_info.append({
                    "key":       key,
                    "label":     meta.get("en") or meta.get("label", key),
                    "current":   val,
                    "threshold": thr,
                    "triggered": triggered,
                })

            if any_triggered:
                triggered_zones.append({
                    "dim":     dim_name,  # 已由 _parse_row 调用 _to_en() 转换，无需重复调用
                    "metrics": metrics_info,
                })
                # 无需额外记录 group2_triggered_dims，dim_group2_triggered（下方）已覆盖此逻辑

        _total_triggered_zones.extend(z["dim"] for z in triggered_zones)

        # ─ Step 2: 商家明细下钻（仅第二组指标触发时执行） ─
        # 结构: {dim_en: {key: [top_n_merchants]}}
        # 每个城市/区域独立维护自己的 Top N，哪个指标触发就展示哪个指标的商家明细
        merchant_details: dict = {}

        # 记录每个城市触发了哪些 group2 指标（用于 HTML 渲染时只展示触发的指标）
        dim_group2_triggered: dict = {}  # {dim_en: [triggered_key, ...]}
        for z in triggered_zones:
            triggered_g2 = [m["key"] for m in z["metrics"] if m["key"] in FEATURE3_GROUP2_KEYS and m["triggered"]]
            if triggered_g2:
                dim_group2_triggered[z["dim"]] = triggered_g2

        if dim_group2_triggered:
            print(f"[Feature3] {region} 商家明细下钻，各城市触发的 group2 指标: {dim_group2_triggered}", file=sys.stderr)
            # 逐城市逐指标精确查询：用 --filter 缩小范围，--order-by 服务端排序，--page-size 直取 Top N
            for dim_en, triggered_keys in dim_group2_triggered.items():
                raw_name = zone_raw_name.get(dim_en, dim_en)  # 原始维度值（用于 --filter）
                merchant_details[dim_en] = {}
                for key in triggered_keys:
                    try:
                        rows = _run_merchant_detail_query_by_dim(
                            FEATURE3_MERCHANT_DATASET_ID, region, key,
                            dim_field, raw_name, today, top_n=top_n
                        )
                        if not rows:
                            continue
                        meta = ALL_METRICS.get(key, {})
                        parse_type = meta.get("parse", "num")
                        merchant_list = []
                        for row in rows:
                            raw = row.get(key)
                            if raw in (None, "-", ""):
                                continue
                            try:
                                val = float(str(raw).replace("%", "").replace(",", ""))
                                if parse_type == "rate" and "%" in str(raw):
                                    val /= 100.0
                            except (ValueError, TypeError):
                                continue
                            if val == 0:
                                continue
                            merchant_list.append({
                                "merchant_name": row.get("shop_name_en") or row.get("shop_name") or row.get("shop_id", "-"),
                                "merchant_id":   str(row.get("shop_id", "-")),
                                "value":         val,
                            })
                        if merchant_list:
                            merchant_details[dim_en][key] = merchant_list
                    except Exception as e:
                        print(f"[Feature3][WARN] {region}/{dim_en}/{key} 商家明细查询失败: {e}", file=sys.stderr)

        # ─ 打印文本摘要 ─
        text_msg = _build_feature3_text(region, triggered_zones, merchant_details,
                                        dim_label=dim_label, top_n=top_n)
        print(text_msg, file=sys.stderr)

        # ─ 推送头 ─
        _tense_names = [z["dim"] for z in triggered_zones]
        tense_names_str = ", ".join(_tense_names[:5])
        if len(_tense_names) > 5:
            tense_names_str += f" etc. ({len(_tense_names)} total)"
        text_header = (
            f"🚨 Merchant Experience Alert: {region} | {dim_label_en} |"
            + (f" {tense_names_str}" if tense_names_str else "")
        )

        # ─ 渲染 HTML → PNG ─
        image_path = None
        if triggered_zones:
            try:
                html_content = _build_feature3_html(
                    region, triggered_zones, merchant_details,
                    dim_label=dim_label, top_n=top_n
                )
                image_path = f"/tmp/keeta_f3_alert_{region}_{int(time.time())}_{os.getpid()}.png"
                script_dir = os.path.dirname(os.path.abspath(__file__))
                sys.path.insert(0, script_dir)
                from render_card import render_html_to_png
                render_html_to_png(html_content, image_path, width=800)
                print(f"[Feature3][INFO] PNG 卡片已生成: {image_path}", file=sys.stderr)
            except Exception as e:
                print(f"[Feature3][WARN] PNG 渲染失败: {e}", file=sys.stderr)
                image_path = None

        output_items.append({
            "region":         region,
            "html_path":      image_path,
            "has_alert":      len(triggered_zones) > 0,
            "total_alerts":   len(triggered_zones),
            "text_header":    text_header,
            "text_fallback":  text_msg,
            "daxiang_target": daxiang_target,
        })

    # ─ 推送大象 ─
    if push_daxiang and output_items:
        for item in output_items:
            if not item.get("has_alert"):
                continue
            header    = item.get("text_header", "")
            fallback  = item.get("text_fallback", "")
            html_path = item.get("html_path", "")
            target    = item.get("daxiang_target") or daxiang_target

            if html_path and os.path.exists(html_path):
                send_daxiang(header, target=target)
                try:
                    _send_image_via_daxiang(html_path, target=target)
                except Exception as e:
                    print(f"[Feature3][WARN] HTML 发送失败: {e}，降级为文本", file=sys.stderr)
                    send_daxiang(fallback, target=target)
                try:
                    os.unlink(html_path)
                except OSError:
                    pass
            else:
                msg = header + "\n\n" + fallback if header else fallback
                send_daxiang(msg, target=target)
        print("[Feature3][INFO] 告警消息已直接发送", file=sys.stderr)

    _daxiang_pushed = push_daxiang and any(i["has_alert"] for i in output_items)
    return {
        "feature":              3,
        "granularity":          "city" if dim_field == "op_city_name" else "zone",
        "regions_queried":      len(regions),
        "regions_with_data":    len(output_items),
        "kdata_queries":        len(_kdata_call_log),
        "total_alerts":         sum(i["total_alerts"] for i in output_items),
        "triggered_zone_names": list(dict.fromkeys(_total_triggered_zones)),
        "daxiang_pushed":       _daxiang_pushed,
    }


# ── 执行告警 ──────────────────────────────────────────────

def _collect_alerts_for_card(region, rows, metrics, global_thr, dim_thresholds, dim_field):
    """收集告警数据，返回 render_card 所需的 alerts_by_dim 格式"""
    alerts_by_dim = defaultdict(list)
    for row in rows:
        dv  = row.get(dim_field, "-")
        # dim_thresholds key 已统一为英文，需将 kdata 返回的中文城市名转英文后查找
        dv_en = _to_en(dv)
        thr = {**global_thr, **dim_thresholds.get(dv_en, {})}
        for k in metrics:
            if k not in thr or k not in ALL_METRICS: continue
            m   = ALL_METRICS[k]
            val = get_value(row, k)
            if val is None: continue
            t   = thr[k]
            if (m["op"] == ">" and val > t) or (m["op"] == "<" and val < t):
                alerts_by_dim[dv].append((k, val, t, m["op"]))
    return dict(alerts_by_dim)


def run_alert(dataset_id, regions, metrics, thresholds, dim_thresholds=None, push_daxiang=False, silent_stdout=False, daxiang_target=None, owner_uid=None):
    if dim_thresholds is None: dim_thresholds = {}
    ds        = DATASETS[dataset_id]
    dim_field = ds["dim_field"]

    _kdata_call_log.clear()  # [TRACKING] 重置计数器

    # 导入卡片渲染器（降级保护：CDP/Node.js 不可用时退化为纯文本）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, script_dir)
    render_alert_card = None
    try:
        from render_card import render_alert_card
    except Exception as e:
        print(f"[WARN] render_card 导入失败: {e}，图片卡片功能不可用", file=sys.stderr)

    output_items = []   # list of {region, image_path, has_alert, text_fallback}
    _alert_dims_all: dict = {}  # region → sorted list of alerted dim names [TRACKING]

    for region in regions:
        print(f"[INFO] 查询 {region}...", file=sys.stderr)
        rows = run_kdata(dataset_id, region, metrics, dim_field)
        if not rows:
            print(f"[WARN] {region} 无数据", file=sys.stderr)
            continue

        # 收集告警
        alerts_by_dim = _collect_alerts_for_card(region, rows, metrics, thresholds, dim_thresholds, dim_field)
        total_alerts  = sum(len(v) for v in alerts_by_dim.values())
        if alerts_by_dim:  # [TRACKING]
            _alert_dims_all[region] = {d: len(v) for d, v in alerts_by_dim.items()}

        # 渲染图片卡片
        image_path = None
        if render_alert_card is not None:
            try:
                image_path = render_alert_card(region, dataset_id, alerts_by_dim, total_alerts)
            except Exception as e:
                print(f"[WARN] 图片渲染失败: {e}，降级为文本", file=sys.stderr)
        if image_path:
            print(f"[INFO] 已生成告警卡片: {image_path}", file=sys.stderr)

        # 同时生成纯文本作为 fallback
        text_msg = build_message(region, rows, metrics, thresholds, dim_thresholds, dim_field)
        if not silent_stdout:
            print(text_msg)

        # 构建推送文本头（图片上方的摘要行）— 直接展示异动城市/区域名称（最多5个）
        granularity_en = DATASETS.get(dataset_id, {}).get("dim_label_en", "Unknown")
        _alert_dims = sorted(alerts_by_dim.keys()) if alerts_by_dim else []
        alert_dim_names = ", ".join(_alert_dims[:5])
        if len(_alert_dims) > 5:
            alert_dim_names += f" etc. ({len(_alert_dims)} total)"
        text_header = f"🚨 Core Metrics Alert: {region} | {granularity_en} | {alert_dim_names}" if _alert_dims else ""

        output_items.append({
            "region":       region,
            "image_path":   image_path,
            "has_alert":    total_alerts > 0,
            "total_alerts": total_alerts,
            "text_header":  text_header,
            "text_fallback": text_msg,
            "daxiang_target": daxiang_target,
        })

    # 写入输出文件（保留，供调试/回溯）
    if push_daxiang and output_items:
        output_data = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "items": output_items,
            "daxiang_target": daxiang_target,
        }
        with open(ALERT_OUTPUT_FILE, "w") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"[ALERT_OUTPUT] {ALERT_OUTPUT_FILE}", file=sys.stderr)

        # 直接发大象消息（不依赖 cron agent）
        for item in output_items:
            if not item.get("has_alert"):
                continue
            header = item.get("text_header", "")
            fallback = item.get("text_fallback", "")
            image_path = item.get("image_path", "")
            target = item.get("daxiang_target") or daxiang_target or owner_uid

            if image_path and os.path.exists(image_path):
                send_daxiang(header, target=target)
                _send_image_via_daxiang(image_path, target=target)
                try:
                    os.unlink(image_path)
                except OSError:
                    pass
            else:
                msg = header + "\n\n" + fallback if header else fallback
                send_daxiang(msg, target=target)
        print("[INFO] 告警消息已直接发送", file=sys.stderr)

    # [TRACKING] 返回执行统计，供 main() 埋点使用
    _daxiang_pushed = push_daxiang and any(i["has_alert"] for i in output_items)
    return {
        "feature":          1,
        "granularity":      "city" if dim_field == "op_city_name" else "zone",
        "regions_queried":  len(regions),
        "regions_with_data": len(output_items),
        "kdata_queries":    len(_kdata_call_log),
        "total_alerts":     sum(i["total_alerts"] for i in output_items),
        "alerted_dims":     _alert_dims_all,
        "daxiang_pushed":   _daxiang_pushed,
    }


# ── 埋点辅助函数 ─────────────────────────────────────────────────────────────

def _build_setup_input(args) -> str:
    """构建 --setup-cron 的 inputContent 摘要。"""
    feature      = getattr(args, "feature", 1) or 1
    regions      = getattr(args, "regions", "") or ""
    interval     = getattr(args, "interval", 10)
    push         = getattr(args, "push_daxiang", False)
    daxiang_tgt  = (getattr(args, "daxiang_target", None) or "").strip()
    metrics_str  = getattr(args, "metrics", "all") or "all"
    thresholds_s = getattr(args, "thresholds", None)
    active_hours = (getattr(args, "active_hours", None) or "").strip()

    # 粒度：F1 由 dataset 决定，F2/F3 由 f2_granularity 决定
    if feature == 1:
        dataset = getattr(args, "dataset", "60038303") or "60038303"
        granularity = "city" if dataset == "60038303" else "zone"
    else:
        granularity = (getattr(args, "f2_granularity", "zone") or "zone")

    # 推送目标：埋点只记录类型，避免群 ID / UID 进入日志。
    target_str = _tracking_daxiang_target_label(daxiang_tgt) if push else "none"

    parts = [
        f"feature={feature}",
        f"regions={regions}",
        f"interval={interval}min",
        f"granularity={granularity}",
        f"daxiang_target={target_str}",
    ]

    # 活跃时段（非全天才上报）
    if active_hours and active_hours not in ("00:00-24:00", ""):
        parts.append(f"active_hours={active_hours}")

    # 推单量过滤门槛
    _min_pov = getattr(args, "min_push_ord_num", None)
    if _min_pov is not None:
        parts.append(f"min_push_ord_num={_min_pov}")

    # 指标（F1 有意义，F2/F3 无需）
    if feature == 1:
        if metrics_str and metrics_str != "all":
            codes = [m.strip() for m in metrics_str.split(",") if m.strip()]
            parts.append(f"metrics_codes={','.join(codes)}")
        else:
            parts.append("metrics=all")
        if thresholds_s:
            try:
                thr = json.loads(thresholds_s)
                if isinstance(thr, dict) and thr:
                    parts.append(f"thresholds_custom={list(thr.keys())}")
            except Exception:
                pass  # 非法 JSON 不上报，不影响主流程

    return " ".join(parts)


def _json_object_keys_summary(raw) -> str:
    """提取 JSON object 的 key 列表，用于埋点摘要；非法 JSON 不阻断主流程。"""
    if not raw:
        return ""
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return "<invalid_json>"
    if not isinstance(data, dict):
        return "<non_object>"
    return ",".join(str(k) for k in data.keys()) or "<empty>"


def _tracking_daxiang_target_label(raw_target: str) -> str:
    """埋点只记录推送目标类型，避免把群 ID / UID 写入日志。"""
    target = (raw_target or "").strip()
    if not target:
        return "none"
    if target.startswith("group:"):
        return "group"
    return "self"


def _change_detail_field(detail: str) -> str:
    """从 update-job 变更明细中提取字段名，用于埋点去重。"""
    return str(detail).split(":", 1)[0].strip() or "unknown"


def _build_update_input(args) -> str:
    """构建 --update-job 的 inputContent 摘要。"""
    job_id = getattr(args, "job_id", None) or ""
    parts = [f"job_id={job_id}"]

    # 尽量补充现有任务上下文；配置读取失败时不影响主流程和失败埋点。
    try:
        cfg = load_cron_config()
        job = next((j for j in cfg.get("jobs", []) if j.get("id") == job_id), None)
    except Exception:
        job = None
    if job:
        parts.append(f"feature={job.get('feature', 1)}")
        regions = job.get("regions", []) or []
        if regions:
            parts.append(f"regions={','.join(regions)}")

    requested_fields = []

    if _arg_was_passed("--regions"):
        requested_fields.append("regions")
        parts.append(f"regions_arg={getattr(args, 'regions', '')}")
    if _arg_was_passed("--f2-granularity"):
        requested_fields.append("f2_granularity")
        parts.append(f"f2_granularity={getattr(args, 'f2_granularity', '')}")
    if _arg_was_passed("--interval"):
        requested_fields.append("interval")
        parts.append(f"interval={getattr(args, 'interval', '')}min")
    if _arg_was_passed("--active-hours"):
        requested_fields.append("active_hours")
        parts.append(f"active_hours={getattr(args, 'active_hours', '')}")
    if _arg_was_passed("--daxiang-target"):
        requested_fields.append("daxiang_target")
        daxiang_tgt = (getattr(args, "daxiang_target", None) or "").strip()
        parts.append(f"daxiang_target={_tracking_daxiang_target_label(daxiang_tgt)}")
    if _arg_was_passed("--metrics"):
        requested_fields.append("metrics")
        metrics_str = getattr(args, "metrics", "all") or "all"
        if metrics_str and metrics_str != "all":
            codes = [m.strip() for m in metrics_str.split(",") if m.strip()]
            parts.append(f"metrics_codes={','.join(codes)}")
        else:
            parts.append("metrics=all")
    if _arg_was_passed("--thresholds"):
        requested_fields.append("thresholds")
        keys = _json_object_keys_summary(getattr(args, "thresholds", None))
        if keys:
            parts.append(f"thresholds_custom={keys}")
    if _arg_was_passed("--dim-thresholds"):
        requested_fields.append("dim_thresholds")
        keys = _json_object_keys_summary(getattr(args, "dim_thresholds", None))
        if keys:
            parts.append(f"dim_thresholds={keys}")
    if _arg_was_passed("--top-n"):
        requested_fields.append("top_n")
        parts.append(f"top_n={getattr(args, 'top_n', '')}")
    if _arg_was_passed("--min-push-ord-num"):
        requested_fields.append("min_push_ord_num")
        parts.append(f"min_push_ord_num={getattr(args, 'min_push_ord_num', '')}")
    if getattr(args, "dry_run", False):
        parts.append("dry_run=true")

    parts.insert(1, f"requested_fields={','.join(requested_fields) or 'none'}")
    return " ".join(parts)


def _build_cron_input(j: dict, job_regions: list) -> str:
    """构建 --cron-run 的 inputContent 摘要。"""
    parts = [
        f"job_id={j.get('id', '')}",
        f"feature={j.get('feature', 1)}",
        f"regions={','.join(job_regions)}",
        f"interval={j.get('poll', {}).get('interval_min', 10)}min",
        f"push_daxiang={j.get('poll', {}).get('push_daxiang', True)}",
    ]
    _min_pov = j.get("min_push_ord_num")
    if _min_pov is not None:
        parts.append(f"min_push_ord_num={_min_pov}")
    return " ".join(parts)


def _build_cron_output(stats: dict) -> str:
    """将 run_alert/run_feature2_alert/run_feature3_alert 返回的 stats dict 序列化为 JSON outputContent。"""
    feature = stats.get("feature", 0)
    out: dict = {
        "feature":           feature,
        "granularity":       stats.get("granularity", "zone"),
        "regions_queried":   stats.get("regions_queried", 0),
        "regions_with_data": stats.get("regions_with_data", 0),
        "kdata_queries":     stats.get("kdata_queries", 0),
        "total_alerts":      stats.get("total_alerts", 0),
        "daxiang_pushed":    stats.get("daxiang_pushed", False),
    }
    if feature == 1:
        out["alerted_dims"] = stats.get("alerted_dims", {})
    elif feature == 2:
        out["tense_zone_names"]    = stats.get("tense_zone_names", [])
        out["layer2_attributions"] = stats.get("layer2_attributions", [])
    elif feature == 3:
        out["triggered_zone_names"] = stats.get("triggered_zone_names", [])
    return json.dumps(out, ensure_ascii=False)


def _normalize_update_result(result) -> dict:
    """兼容 update_job 新旧返回值，统一成埋点 outputContent。"""
    if isinstance(result, dict):
        changes = result.get("change_details", []) or []
        changed_fields = list(dict.fromkeys(_change_detail_field(c) for c in changes))
        return {
            "updated": result.get("changes_count", 0) > 0,
            "changes_count": result.get("changes_count", len(changes)),
            "changed_fields": changed_fields,
            "cron_reregister": bool(result.get("cron_reregister", False)),
        }
    count = int(result or 0)
    return {
        "updated": count > 0,
        "changes_count": count,
        "changed_fields": [],
        "cron_reregister": False,
    }


# ── 主流程 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Keeta 实时异动告警脚本（参数驱动，无交互）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # 模式
    parser.add_argument("--setup-cron",    action="store_true", help="注册新定时告警任务")
    parser.add_argument("--update-job",    action="store_true", help="修改已有告警任务参数（需 --job-id，仅覆盖显式传入的参数）")
    parser.add_argument("--cron-run",      action="store_true", help="由 cron 执行告警（需 --job-id）")
    parser.add_argument("--stop-cron",     action="store_true", help="删除定时任务（需 --job-id）")
    parser.add_argument("--list-jobs",     action="store_true", help="列出所有已配置任务")
    parser.add_argument("--list-datasets", action="store_true", help="列出所有已注册数据集")
    parser.add_argument("--print-defaults",action="store_true", help="打印数据集默认阈值（需 --dataset）")
    parser.add_argument("--health-check",  action="store_true", help="自检：检查配置、依赖、凭证、cron 注册是否正常")
    parser.add_argument("--dry-run",       action="store_true", help="仅打印参数摘要，不写入配置")

    # --setup-cron 所需参数
    parser.add_argument("--dataset",       default="60038303",  help="数据集 ID（60038303 城市 / 62059270 区域）")
    parser.add_argument("--regions",       default="SA",        help="地区，逗号分隔，如 SA,AE,BH")
    parser.add_argument("--mis-id",        default=None,        help="操作人 MIS（用于 Region 权限校验，默认自动读取登录态）")
    parser.add_argument("--metrics",       default="all",       help="指标列表，逗号分隔，或 'all'")
    parser.add_argument("--thresholds",    default=None,        help='覆盖阈值，JSON，如 \'{"ontime_task_ratio":0.85}\'')
    parser.add_argument("--dim-thresholds",default=None,        help='差异化阈值，JSON，如 \'{"Riyadh":{"ontime_task_ratio":0.84}}\'')
    parser.add_argument("--interval",      type=int, default=10,help=f"轮询间隔（分钟），最低 {MIN_POLL_INTERVAL}")
    parser.add_argument("--push-daxiang",  action="store_true", help="有告警时推送大象消息")
    parser.add_argument("--daxiang-target",default=None,        help="推送目标：self（默认，发给自己）或 group:<group_id>（发到指定群）")
    parser.add_argument("--owner-uid",     default=None,        help="告警接收人 UID（用于 cron isolated session 投递）")
    parser.add_argument("--feature",       type=int, default=1, choices=[1, 2, 3],
                        help="告警功能版本：1=固定阈值（默认），2=运力出勤统计异常检测，3=商家出餐体验异动告警")
    parser.add_argument("--f2-granularity", choices=["city", "zone"], default="zone",
                        help="Feature 2 粒度: city=业务城市, zone=配送区域 (default: zone)")
    parser.add_argument("--active-hours",  default="00:00-24:00",
                        help="告警活跃时段（region 本地时间），逗号分隔多段，如 '12:00-14:00,17:00-20:00'，默认全天")

    parser.add_argument("--top-n",          type=int, default=None,
                        help=f"场景3商家明细 Top N 数量（默认 {FEATURE3_DEFAULT_TOP_N}）")

    # --cron-run / --stop-cron 所需参数
    parser.add_argument("--min-push-ord-num", type=int, default=None, help="F2：push_ord_num 低于此值的城市/区域不触发告警（如设为 20，则推单量<20的区域静默）")
    parser.add_argument("--job-id",        default=None,        help="任务 ID")

    # --feedback 参数（记录用户对告警的有效性评价）
    parser.add_argument("--feedback",      action="store_true", help="记录告警反馈（需 --job-id 和 --rating）")
    parser.add_argument("--rating",        type=int, choices=[1, -1], default=None,
                        help="反馈评分：1=有用(👍)  -1=误报(👎)")
    parser.add_argument("--comment",       default="",          help="反馈说明（可选，配合 --feedback 使用）")

    args = parser.parse_args()

    # [TRACKING] 获取执行者 MIS 和 session_id（用于埋点）
    _mis = (getattr(args, "mis_id", None) or "").strip() or _get_mis()
    _session_id = (
        os.environ.get("OPENCLAW_SESSION_ID", "")
        or os.environ.get("KDATA_SESSION_ID", "")
    )

    # ── 提前解析 owner_uid 以便依赖检查失败时能通知 ──
    _early_owner_uid = None
    if args.cron_run and args.job_id:
        try:
            _cfg = load_cron_config()
            _matched = [j for j in _cfg.get("jobs", []) if j.get("id") == args.job_id]
            if _matched:
                _early_owner_uid = _matched[0].get("owner_uid")
        except Exception:
            pass  # 配置读取失败时 fallback 到 _get_default_owner_uid()

    # ── 前置依赖检查：确保 keeta-data-query 已安装 ──
    # list-jobs / list-datasets / print-defaults / health-check 不需要实际查询，跳过检查
    needs_query = (args.cron_run or args.setup_cron or args.dry_run) and not args.update_job
    if needs_query and not ensure_keeta_data_query():
        _dep_err = "缺少前置依赖 keeta-data-query，无法继续执行。请手动安装：openclaw skills install keeta-data-query"
        print(f"[ERROR] {_dep_err}", file=sys.stderr)
        if args.cron_run and args.job_id:
            _notify_owner_error(args.job_id, _dep_err, owner_uid=_early_owner_uid)
        sys.exit(1)

    # ── 前置依赖检查：若目标含 group，确保 claw-group-speaker 已安装 + 凭证已配置 ──
    _daxiang_target = getattr(args, "daxiang_target", None) or ""
    if needs_query and str(_daxiang_target).startswith("group:"):
        if not ensure_claw_group_speaker():
            print("[ERROR] 缺少前置依赖 claw-group-speaker，无法继续执行。请手动安装：mtskills i claw-group-speaker --target-dir ~/.openclaw/skills", file=sys.stderr)
            sys.exit(1)
        # 同时检查群推送凭证（配置阶段就报错，而非推送时才 WARN 跳过）
        _gcid, _gsec = _load_group_speaker_creds()
        if not _gcid or not _gsec:
            print("[ERROR] 群推送凭证未配置。请在 cron_config.json 中添加 group_client_id 和 group_client_secret。", file=sys.stderr)
            print("[ERROR] 获取方式：在大象开放平台（https://dxopen.sankuai.com/home）创建企业内部应用机器人，拿到 client_id 和 client_secret 后写入配置。", file=sys.stderr)
            sys.exit(1)

    if args.list_jobs:
        list_jobs(); return

    if args.list_datasets:
        list_datasets(); return

    if args.health_check:
        print("🔍 Keeta 实时告警系统自检\n")
        passed, issues = _run_health_check(verbose=True)
        sys.exit(0 if passed else 1)

    if args.print_defaults:
        print_defaults(args.dataset); return

    if args.feedback:
        if not args.job_id:
            print("[ERROR] --feedback 需要 --job-id", file=sys.stderr); sys.exit(1)
        if args.rating is None:
            print("[ERROR] --feedback 需要 --rating（1=👍有用  -1=👎误报）", file=sys.stderr); sys.exit(1)
        if not _CLI_LOGGER_AVAILABLE or not _cli_logger_report_feedback:
            print("[ERROR] cli_logger 不可用，反馈无法上报。请确认 scripts/cli_logger.py 正常加载。", file=sys.stderr)
            sys.exit(1)
        _cli_logger_report_feedback(
            _mis, args.rating,
            comment=args.comment or "",
            job_id=args.job_id,
            session_id=_session_id,
        )
        label = "👍 有用" if args.rating == 1 else "👎 误报"
        print(f"✅ 反馈已记录：{label}（job_id={args.job_id}）")
        return

    if args.stop_cron:
        if not args.job_id:
            print("[ERROR] 需要 --job-id", file=sys.stderr); sys.exit(1)
        _t0 = time.time()
        try:
            delete_cron_by_job_id(args.job_id)
            _cost = int((time.time() - _t0) * 1000)
            _report_log(_mis, f"alert --stop-cron --job-id {args.job_id}", "SUCCESS", _cost,
                        input_summary=f"job_id={args.job_id}",
                        output_summary=json.dumps({"deleted": True}, ensure_ascii=False),
                        session_id=_session_id, job_id=args.job_id)
        except Exception as _e:
            _cost = int((time.time() - _t0) * 1000)
            _report_log(_mis, f"alert --stop-cron --job-id {args.job_id}", "FAIL", _cost,
                        input_summary=f"job_id={args.job_id}",
                        error_msg=str(_e), error_type="config_error",
                        session_id=_session_id, job_id=args.job_id)
            raise
        return

    if args.update_job:
        _t0 = time.time()
        _update_result = {"updated": False, "changes_count": 0, "changed_fields": [], "cron_reregister": False}
        try:
            _update_input = _build_update_input(args)
        except Exception as _bi_e:
            print(f"[WARN] update-job 埋点 input 序列化失败: {_bi_e}", file=sys.stderr)
            _update_input = f"job_id={args.job_id} build_input_error: {type(_bi_e).__name__}"
        try:
            _update_result = _normalize_update_result(update_job(args))
        except SystemExit as _se:
            _cost = int((time.time() - _t0) * 1000)
            if _se.code != 0:
                _report_log(_mis, f"alert --update-job --job-id {args.job_id}", "FAIL", _cost,
                            input_summary=_update_input,
                            error_msg=f"exit {_se.code}", error_type="config_error",
                            session_id=_session_id, job_id=args.job_id)
            raise
        except Exception as _e:
            _cost = int((time.time() - _t0) * 1000)
            _report_log(_mis, f"alert --update-job --job-id {args.job_id}", "FAIL", _cost,
                        input_summary=_update_input,
                        error_msg=str(_e), error_type="config_error",
                        session_id=_session_id, job_id=args.job_id)
            raise
        else:
            if not getattr(args, "dry_run", False):
                _cost = int((time.time() - _t0) * 1000)
                _report_log(_mis, f"alert --update-job --job-id {args.job_id}", "SUCCESS", _cost,
                            input_summary=_update_input,
                            output_summary=json.dumps(_update_result, ensure_ascii=False),
                            session_id=_session_id, job_id=args.job_id)
        return

    if args.setup_cron or args.dry_run:
        _t0 = time.time()
        _setup_job_id = None
        try:
            _setup_input = _build_setup_input(args)
        except Exception as _bi_e:
            print(f"[WARN] 埋点 input 序列化失败: {_bi_e}", file=sys.stderr)
            _setup_input = f"build_input_error: {type(_bi_e).__name__}"
        try:
            _setup_job_id = setup_cron(args)
        except SystemExit as _se:
            _cost = int((time.time() - _t0) * 1000)
            if _se.code != 0:
                _report_log(_mis, "alert --setup-cron", "FAIL", _cost,
                            input_summary=_setup_input,
                            error_msg=f"exit {_se.code}", error_type="config_error",
                            session_id=_session_id)
            raise
        except Exception as _e:
            _cost = int((time.time() - _t0) * 1000)
            _report_log(_mis, "alert --setup-cron", "FAIL", _cost,
                        input_summary=_setup_input,
                        error_msg=str(_e), error_type="config_error",
                        session_id=_session_id)
            raise
        else:
            if not args.dry_run and _setup_job_id:
                _cost = int((time.time() - _t0) * 1000)
                _setup_cmd = f"alert --setup-cron --job-id {_setup_job_id}"
                _report_log(_mis, _setup_cmd, "SUCCESS", _cost,
                            input_summary=_setup_input,
                            output_summary=json.dumps({"registered": True, "job_id": _setup_job_id}, ensure_ascii=False),
                            session_id=_session_id, job_id=_setup_job_id)
        return

    if args.cron_run:
        if not args.job_id:
            print("[ERROR] 需要 --job-id", file=sys.stderr); sys.exit(1)
        # 清理遗留文件（deprecated browser send queue，保留兼容清理）
        if os.path.exists(BROWSER_SEND_FILE):
            try:
                os.remove(BROWSER_SEND_FILE)
            except Exception:
                pass
        cfg  = load_cron_config()
        jobs = {j["id"]: j for j in cfg.get("jobs", [])}
        if args.job_id not in jobs:
            _err = f"未找到 job: {args.job_id}（配置中共 {len(jobs)} 个任务: {list(jobs.keys())}）"
            print(f"[ERROR] {_err}", file=sys.stderr)
            _notify_owner_error(args.job_id, _err, owner_uid=_early_owner_uid)
            sys.exit(1)
        j        = jobs[args.job_id]
        interval = j.get("poll", {}).get("interval_min", MIN_POLL_INTERVAL)
        if interval < MIN_POLL_INTERVAL:
            print(f"[ERROR] job {args.job_id} 轮询间隔 {interval} 分钟低于最小限制，执行中止", file=sys.stderr)
            sys.exit(1)

        # ── 时间窗口检查：对每个 region 单独判断，过滤掉不在活跃时段的 region ──
        active_hours_spec = j.get("active_hours", "00:00-24:00")
        active_windows = parse_active_hours(active_hours_spec)
        job_regions = j.get("regions", ["SA"])
        if active_windows is not None:
            active_regions = [r for r in job_regions if is_within_active_hours(active_windows, r)]
            if not active_regions:
                print(f"[INFO] job {args.job_id} 所有 region 当前均不在活跃时段 ({active_hours_spec})，跳过执行", file=sys.stderr)
                return
            if len(active_regions) < len(job_regions):
                skipped = [r for r in job_regions if r not in active_regions]
                print(f"[INFO] job {args.job_id} 部分 region 不在活跃时段，跳过: {skipped}", file=sys.stderr)
                job_regions = active_regions

        # [TRACKING] cron-run: 优先用 job 中持久化的 mis_id；若为 "unknown" 则回退到当前环境变量
        _stored_mis = j.get("mis_id", "")
        _cron_mis = _stored_mis if _stored_mis and _stored_mis != "unknown" else _mis
        _cron_cmd = f"alert --cron-run --job-id {args.job_id}"
        _cron_input = _build_cron_input(j, job_regions)
        _t0 = time.time()
        _owner_uid = j.get("owner_uid")
        # [TRACKING] 清理同进程复用时的残留状态，再设置本次 cron-run 上下文。
        _kdata_call_log.clear()
        _cron_context.clear()
        _cron_context.update({"mis": _cron_mis, "session_id": _session_id, "job_id": args.job_id})

        feature = j.get("feature", 1)
        try:
            if feature == 2:
                # Feature 2: 运力供需异动监控
                _stats = run_feature2_alert(
                    regions        = job_regions,
                    interval       = interval,
                    push_daxiang   = j.get("poll", {}).get("push_daxiang", True),
                    daxiang_target = j.get("poll", {}).get("daxiang_target"),
                    owner_uid      = _owner_uid,
                    dim_field      = j.get("dim_field", "delivery_area_name"),
                    threshold_overrides = j.get("thresholds"),
                    dim_thresholds      = j.get("dim_thresholds", {}),
                    min_push_ord_num    = j.get("min_push_ord_num"),
                )
            elif feature == 3:
                # Feature 3: 商家出餐体验异动告警（整体超时兜底 300s）
                import signal as _signal
                def _f3_timeout_handler(signum, frame):
                    raise TimeoutError("Feature3 run_feature3_alert timed out after 300s")
                _signal.signal(_signal.SIGALRM, _f3_timeout_handler)
                _signal.alarm(300)
                try:
                    _stats = run_feature3_alert(
                        regions        = job_regions,
                        interval       = interval,
                        push_daxiang   = j.get("poll", {}).get("push_daxiang", True),
                        daxiang_target = j.get("poll", {}).get("daxiang_target"),
                        owner_uid      = _owner_uid,
                        dim_field      = j.get("dim_field", "delivery_area_name"),
                        threshold_overrides = j.get("thresholds"),
                        dim_thresholds      = j.get("dim_thresholds", {}),
                        top_n          = j.get("top_n", FEATURE3_DEFAULT_TOP_N),
                    )
                finally:
                    _signal.alarm(0)  # 取消超时
            else:
                # Feature 1: 固定阈值告警
                _stats = run_alert(
                    dataset_id     = j.get("dataset_id", "60038303"),
                    regions        = job_regions,
                    metrics        = j.get("metrics", list(ALL_METRICS.keys())),
                    thresholds     = j.get("thresholds", {}),
                    dim_thresholds = j.get("dim_thresholds", {}),
                    push_daxiang   = j.get("poll", {}).get("push_daxiang", True),
                    daxiang_target = j.get("poll", {}).get("daxiang_target"),
                    owner_uid      = _owner_uid,
                    silent_stdout  = True,
                )
            _cost = int((time.time() - _t0) * 1000)
            _report_log(_cron_mis, _cron_cmd, "SUCCESS", _cost,
                        input_summary=_cron_input,
                        output_summary=_build_cron_output(_stats or {}),
                        session_id=_session_id, job_id=args.job_id)
        except SystemExit as _se:
            # run_kdata() 在超时/失败时调 sys.exit(1)，SystemExit 不是 Exception 子类，需单独捕获
            _cost = int((time.time() - _t0) * 1000)
            _err_type = "kdata_fail" if (_se.code or 0) != 0 else "unknown"
            _err_msg = f"数据查询失败 (sys.exit({_se.code}))"
            _report_log(_cron_mis, _cron_cmd, "FAIL", _cost,
                        input_summary=_cron_input,
                        error_msg=_err_msg, error_type=_err_type,
                        session_id=_session_id, job_id=args.job_id)
            _notify_owner_error(args.job_id, _err_msg, owner_uid=_owner_uid)
            raise
        except subprocess.TimeoutExpired:
            _cost = int((time.time() - _t0) * 1000)
            _err_msg = "数据查询超时 (kdata timeout)"
            _report_log(_cron_mis, _cron_cmd, "FAIL", _cost,
                        input_summary=_cron_input,
                        error_msg=_err_msg, error_type="kdata_timeout",
                        session_id=_session_id, job_id=args.job_id)
            _notify_owner_error(args.job_id, _err_msg, owner_uid=_owner_uid)
            raise
        except _KdataEnvError as _e:
            # kdata binary 不存在或无执行权限，自动修复也失败 → 环境问题
            _cost = int((time.time() - _t0) * 1000)
            _err_msg = str(_e)
            _report_log(_cron_mis, _cron_cmd, "FAIL", _cost,
                        input_summary=_cron_input,
                        error_msg=_err_msg, error_type="kdata_env",
                        session_id=_session_id, job_id=args.job_id)
            _notify_owner_error(args.job_id, f"kdata 环境异常：{_err_msg}", owner_uid=_owner_uid)
            raise
        except Exception as _e:
            _cost = int((time.time() - _t0) * 1000)
            _err_msg = f"{type(_e).__name__}: {_e}"
            _report_log(_cron_mis, _cron_cmd, "FAIL", _cost,
                        input_summary=_cron_input,
                        error_msg=_err_msg, error_type="unknown",
                        session_id=_session_id, job_id=args.job_id)
            _notify_owner_error(args.job_id, _err_msg, owner_uid=_owner_uid)
            raise
        finally:
            _cron_context.clear()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
