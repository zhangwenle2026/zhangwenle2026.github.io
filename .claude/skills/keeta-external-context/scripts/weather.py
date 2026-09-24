#!/usr/bin/env python3
"""
Keeta External Context - 天气查询
数据源：起源数据集 62059322（Keeta 内部天气数据，城市/配送区域粒度）
备用：Open-Meteo API（无需 Key）

权限不足时：
  - 默认输出结构化错误（error_type: no_permission），由调用方（AI）告知用户并征求意见
  - 带 --allow-fallback 参数时：自动降级到 Open-Meteo（公开数据，精度略低）

【数据准确性说明】
当前数据源为天气供应商提供的当天实时天气预报，降雨量为当日的实时预估值，
可能与当天最终实测结果存在偏差（查询历史数据时同理，展示的是当日发布的预报，非事后复盘值）。
如业务对降雨量准确度要求较高，推荐改用历史实测表查询：
  mart_sailor_global.fact_weather_historical_weather_d
"""
import sys
import os
import json
import subprocess
import urllib.request
import urllib.parse
import time
from datetime import datetime, timedelta
try:
    from skill_tracker import report_script
except Exception:
    report_script = None


def _track_script(params: str, output: str, started_at: float,
                  success: bool, error_msg: str = "") -> None:
    if report_script is None:
        return
    try:
        report_script(
            params=params,
            output=output,
            cost_ms=int((time.time() - started_at) * 1000),
            success=success,
            error_msg=error_msg,
        )
    except Exception:
        pass

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _find_script(filename: str) -> str:
    """在 keeta-data-query/scripts/ 下动态探测脚本路径，兼容目录结构重构。"""
    base = os.path.expanduser("~/.openclaw/skills/keeta-data-query/scripts")
    for root, _dirs, files in os.walk(base):
        if filename in files:
            return os.path.join(root, filename)
    return ""  # 返回空字符串，调用方检查后走 fallback


ORIGIN_QUERY = _find_script("origin_query.py")
WEATHER_DATASET = "62059322"   # Keeta 内部天气数据集
WEATHER_APPLY_LINK = (
    "https://origin.keetapp.com/dataset/62059322"
    "  （起源平台数据集权限申请，或联系数据集负责人）"
)

REGIONS = {
    "SA": {"lat": 24.6877, "lon": 46.7219, "name": "沙特", "tz": "Asia/Riyadh"},
    "QA": {"lat": 25.2854, "lon": 51.5310, "name": "卡塔尔", "tz": "Asia/Qatar"},
    "BH": {"lat": 26.2154, "lon": 50.5832, "name": "巴林", "tz": "Asia/Bahrain"},
    "AE": {"lat": 25.2048, "lon": 55.2708, "name": "阿联酋", "tz": "Asia/Dubai"},
    "KW": {"lat": 29.3759, "lon": 47.9774, "name": "科威特", "tz": "Asia/Kuwait"},
    "HK": {"lat": 22.3193, "lon": 114.1694, "name": "香港", "tz": "Asia/Hong_Kong"},
    "BR": {"lat": -23.5505, "lon": -46.6333, "name": "巴西", "tz": "America/Sao_Paulo"},
}

# 各地区默认主城市（首都或最大城市），与内部数据集 op_city_name 字段对应
DEFAULT_CITY = {
    "SA": "Riyadh",
    "QA": "Doha",
    "BH": "Manamah",
    "AE": "Dubai",
    "KW": "Kuwait City",
    "HK": "Hong Kong",
    "BR": "Sao Paulo",
}

MEASURES = [
    "max_temperature", "min_temperature",
    "precipitation_hourly", "precipitation_probability",
    "wind_speed", "wind_gust_speed",
    "feelslike_temperature", "humidity",
]

# 注意：forcast_dt_code 过滤必须加，避免底表跨天预报数据导致聚合失真
# 空城市蜂窝过滤在结果层统一处理（跳过 op_city_name 为空的行），无需按地区单独配置

def _run_origin_query(cmd: list) -> list:
    """执行 origin_query.py 并返回 rows 列表，统一处理超时和权限异常。"""
    # tracking: scripts/weather.py::_run_origin_query::skill-script
    started_at = time.time()
    params = "origin_query " + " ".join(str(c) for c in cmd[:12])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired as e:
        msg = "天气数据集查询超时（45s），将自动回退 Open-Meteo"
        _track_script(params, "", started_at, False, msg)
        raise RuntimeError(msg) from e
    if result.returncode != 0:
        stderr = result.stderr.strip()
        perm_keywords = ["submit_no_permission", "NO_PERMISSION", "无表权限", "权限不足"]
        if any(k in stderr for k in perm_keywords):
            _track_script(params, result.stdout[-500:], started_at, False, stderr[-200:])
            raise PermissionError(f"NO_PERMISSION:{stderr}")
        _track_script(params, result.stdout[-500:], started_at, False, stderr[-200:])
        raise RuntimeError(f"内部数据集查询失败: {stderr}")
    output = json.loads(result.stdout)
    rows = output.get("rows", [])
    _track_script(params, f"rows={len(rows)}", started_at, True)
    return rows


def query_internal(region: str, start_date: str, end_date: str,
                   city: str = None, delivery_area: str = None) -> dict:
    """
    查询 Keeta 内部天气数据集 62059322
    start_date/end_date 格式: YYYYMMDD
    city: 城市名称过滤（如 Doha，不传则取 region 下所有城市汇总）

    关键口径说明：
    - 必须加 forcast_dt_code=当天日期过滤，否则底表含未来8天预报数据，聚合会取到未来极值
    - HK 需额外加 op_city_id=810001 过滤掉空城市蜂窝
    - 天气情况（weather_condition_name）单独 group by 查询，作为描述性附加信息
    """
    region_upper = region.upper()

    def _base_filters(date: str) -> list:
        """构造每天查询共用的过滤条件"""
        filters = [f"forcast_dt_code={date}"]
        if city:
            filters.append(f"op_city_name={city}")
        if delivery_area:
            filters.append(f"delivery_area_name={delivery_area}")
        return filters

    def _float(v):
        if v in (None, "-", ""):
            return None
        try:
            return float(str(v).rstrip("%"))
        except ValueError:
            return None

    # 遍历日期范围，逐天查询（每天 forcast_dt_code 不同）
    date_obj_s = datetime.strptime(start_date, "%Y%m%d")
    date_obj_e = datetime.strptime(end_date, "%Y%m%d")
    rows = []
    cur = date_obj_s
    while cur <= date_obj_e:
        date_str = cur.strftime("%Y%m%d")

        # --- 查询1：数值指标（group by dt, op_city_name）---
        cmd_num = [
            "python3", ORIGIN_QUERY, "--json", "query",
            "--dataset", WEATHER_DATASET,
            "--measures", ",".join(MEASURES),
            "--date", f"{date_str}~{date_str}",
            "--region", region_upper,
            "--group-by", "dt,op_city_name",
            "--order-by", "dt=ASC",
        ]
        for f in _base_filters(date_str):
            cmd_num += ["--filter", f]
        num_rows = _run_origin_query(cmd_num)

        # --- 查询2：天气类型分布（group by dt, op_city_name, weather_condition_name）---
        cmd_cond = [
            "python3", ORIGIN_QUERY, "--json", "query",
            "--dataset", WEATHER_DATASET,
            "--measures", "precipitation_hourly",
            "--date", f"{date_str}~{date_str}",
            "--region", region_upper,
            "--group-by", "dt,op_city_name,weather_condition_name",
        ]
        for f in _base_filters(date_str):
            cmd_cond += ["--filter", f]
        try:
            cond_rows = _run_origin_query(cmd_cond)
            # 收集当天出现的非零天气类型（有降水的优先）
            weather_types = sorted(
                set(r.get("weather_condition_name", "") for r in cond_rows if r.get("weather_condition_name")),
                key=lambda x: (0 if x == "Rain" else 1)  # Rain 排前面
            )
        except Exception:
            weather_types = []

        for r in num_rows:
            city_name = r.get("op_city_name") or ""
            # 所有地区统一过滤掉空城市行（蜂窝粒度中存在 city 为空的记录）
            if not city_name or city_name.strip() in ("", "null", "None"):
                continue
            rows.append({
                "date":            r.get("dt", date_str),
                "city":            city_name,
                "max_temp":        _float(r.get("max_temperature")),
                "min_temp":        _float(r.get("min_temperature")),
                "precip_mm":       _float(r.get("precipitation_hourly")),
                "precip_prob_pct": r.get("precipitation_probability", "-"),
                "wind_speed_ms":   _float(r.get("wind_speed")),
                "wind_gust_ms":    _float(r.get("wind_gust_speed")),
                "feels_like":      _float(r.get("feelslike_temperature")),
                "humidity_pct":    r.get("humidity", "-"),
                "weather_conditions": weather_types,  # 天气类型列表，Rain 优先排序
            })

        cur += timedelta(days=1)

    return {
        "region":     region_upper,
        "source":     "internal_dataset_62059322",
        "date_range": f"{start_date} ~ {end_date}",
        "data":       rows,
    }


def query_openmeteo(region: str, start_date: str, end_date: str) -> dict:
    """Open-Meteo 备用（无需 Key）"""
    # tracking: scripts/weather.py::query_openmeteo::skill-script
    started_at = time.time()
    params_for_tracking = f"open_meteo region={region.upper()} date={start_date}~{end_date}"
    r = REGIONS[region.upper()]
    date_obj_s = datetime.strptime(start_date, "%Y%m%d")
    date_obj_e = datetime.strptime(end_date, "%Y%m%d")
    today = datetime.now()

    if date_obj_s > today:
        # 预报
        days = (date_obj_e - today).days + 2
        params = urllib.parse.urlencode({
            "latitude": r["lat"], "longitude": r["lon"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode,windspeed_10m_max,windgusts_10m_max,apparent_temperature_max,precipitation_probability_max",
            "timezone": r["tz"], "forecast_days": min(days, 16),
        })
        url = f"https://api.open-meteo.com/v1/forecast?{params}"
        key = "forecast"
    else:
        # 历史
        params = urllib.parse.urlencode({
            "latitude": r["lat"], "longitude": r["lon"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode,windspeed_10m_max",
            "timezone": r["tz"],
            "start_date": date_obj_s.strftime("%Y-%m-%d"),
            "end_date": date_obj_e.strftime("%Y-%m-%d"),
        })
        url = f"https://archive-api.open-meteo.com/v1/archive?{params}"
        key = "history"

    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            raw = json.loads(resp.read())
    except Exception as e:
        _track_script(params_for_tracking, "", started_at, False, str(e))
        raise

    daily = raw["daily"]
    prefix = "temperature_2m_max" if key == "history" else "temperature_2m_max"
    rows = []
    for i, dt in enumerate(daily["time"]):
        rows.append({
            "date": dt.replace("-", ""),
            "city": r["name"] + "（Open-Meteo）",
            "max_temp": daily["temperature_2m_max"][i],
            "min_temp": daily["temperature_2m_min"][i],
            "precip_mm": daily["precipitation_sum"][i],
            "wind_speed_ms": round(daily.get("windspeed_10m_max", [None]*99)[i] / 3.6, 1) if daily.get("windspeed_10m_max") else None,
        })

    _track_script(params_for_tracking, f"rows={len(rows)}", started_at, True)
    return {"region": region.upper(), "source": "open_meteo_fallback", "data": rows}


def fetch_weather(region: str, start_date: str, end_date: str,
                  city: str = None, delivery_area: str = None,
                  fallback: bool = True,
                  allow_fallback: bool = False) -> dict:
    """统一入口：优先内部数据集，失败时行为由参数控制。

    未指定 city 时，自动使用 DEFAULT_CITY 中对应地区的主城市（首都或最大城市），
    并在返回结果中附上 queried_city 字段，明确告知查的是哪个城市。

    权限处理逻辑：
      - 无权限 + allow_fallback=False（默认）：返回结构化错误（error_type: no_permission），
        由 AI 告知用户并征求意见（申请权限 or 降级 Open-Meteo）
      - 无权限 + allow_fallback=True：静默降级 Open-Meteo
      - 其他错误 + fallback=True：自动降级 Open-Meteo
    """
    region_upper = region.upper()
    effective_city = city or DEFAULT_CITY.get(region_upper)

    if not os.path.exists(ORIGIN_QUERY):
        if allow_fallback or fallback:
            result = query_openmeteo(region, start_date, end_date)
            result["queried_city"] = REGIONS[region_upper]["name"] + "（Open-Meteo）"
            return result
        raise RuntimeError("keeta-data-query skill 未安装")
    try:
        result = query_internal(region, start_date, end_date, effective_city, delivery_area)
        result["queried_city"] = effective_city or "（全地区汇总）"
        return result
    except PermissionError as e:
        # 权限错误：优先让用户决策，而不是自动降级
        if allow_fallback:
            print(f"⚠️  天气数据集权限不足，已降级 Open-Meteo", file=sys.stderr)
            result = query_openmeteo(region, start_date, end_date)
            result["queried_city"] = REGIONS[region_upper]["name"] + "（Open-Meteo降级）"
            return result
        # 返回结构化错误，由 AI 层告知用户
        return {
            "error_type": "no_permission",
            "error_message": (
                f"没有查询天气内部数据集（{WEATHER_DATASET}）的权限。\n"
                "可选方案：\n"
                "  A）申请数据集权限（数据更准确，含降雨概率/风向/湿度等字段）\n"
                "  B）降级使用 Open-Meteo（公开数据，字段略少，精度略低）"
            ),
            "apply_link": WEATHER_APPLY_LINK,
            "fallback_available": True,
            "region": region_upper,
            "queried_city": effective_city,
            "date_range": f"{start_date} ~ {end_date}",
        }
    except Exception as e:
        if fallback:
            print(f"⚠️  内部数据集查询失败（{e}），回退 Open-Meteo", file=sys.stderr)
            result = query_openmeteo(region, start_date, end_date)
            result["queried_city"] = REGIONS[region_upper]["name"] + "（Open-Meteo）"
            return result
        raise


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Keeta 天气查询（数据集 62059322）")
    parser.add_argument("region", help="地区代码: SA/QA/BH/AE/KW/HK/BR")
    parser.add_argument("start_date", help="开始日期 YYYYMMDD")
    parser.add_argument("end_date",   nargs="?", help="结束日期 YYYYMMDD（默认=start_date）")
    parser.add_argument("--city",          help="按城市名过滤（如 Doha）")
    parser.add_argument("--delivery-area", help="按配送区域过滤")
    parser.add_argument("--no-fallback",    action="store_true", help="禁止回退 Open-Meteo")
    parser.add_argument("--allow-fallback", action="store_true",
                        help="无权限时自动降级 Open-Meteo（不提示用户选择）")
    args = parser.parse_args()

    end = args.end_date or args.start_date
    result = fetch_weather(args.region, args.start_date, end,
                           city=args.city, delivery_area=args.delivery_area,
                           fallback=not args.no_fallback,
                           allow_fallback=args.allow_fallback)
    print(json.dumps(result, ensure_ascii=False, indent=2))
