#!/usr/bin/env python3
"""
Keeta External Context - 节假日查询
数据源：mart_sailor_global.fact_public_date_info_snap_d（通过魔数BI查询）
需要：~/.openclaw/skills/keeta-data-query 已安装且有 sailor-product-data 空间权限

权限不足时：
  - 默认输出结构化错误（error_type: no_permission），由调用方（AI）告知用户并征求意见
  - 带 --allow-fallback 参数时：自动降级到本地 JSON 缓存（data/holidays_cache.json）

⚠️  注意：中东节假日（开斋节等）由伊斯兰历换算，有时前几天才能确认，
    本地缓存时效性有限，对准确性要求高时强烈建议申请数据表权限。
"""
import sys
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime
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
CACHE_PATH = os.path.join(SKILL_DIR, "data", "holidays_cache.json")
APPLY_LINK = (
    "https://data.keetapp.com/hetu/tableApply?"
    "applyType=external&providerType=person&refer=role"
    "&source=DW_ONESQL_DB_CONNECT_URL"
    "&database=mart_sailor_global&table=fact_public_date_info_snap_d"
)


def _find_script(filename: str) -> str:
    """在 keeta-data-query/scripts/ 下动态探测脚本路径，兼容目录结构重构。"""
    base = os.path.expanduser("~/.openclaw/skills/keeta-data-query/scripts")
    for root, _dirs, files in os.walk(base):
        if filename in files:
            return os.path.join(root, filename)
    raise FileNotFoundError(
        f"找不到 {filename}，请确认 keeta-data-query skill 已安装（路径：{base}）"
    )


KEETA_BI_SCRIPT = ""
SPACE_ID = "109495"          # sailor-product-data
QUEUE    = "root.fra02.hadoop-sailor.query"

SUPPORTED_REGIONS = ["SA", "QA", "BH", "AE", "KW", "HK", "BR"]


def _get_keeta_bi_script() -> str:
    """Lazy-resolve keeta-data-query so CLI help and imports still work."""
    global KEETA_BI_SCRIPT
    if not KEETA_BI_SCRIPT:
        KEETA_BI_SCRIPT = _find_script("keeta_bi_skill.py")
    return KEETA_BI_SCRIPT


def _get_bi_env() -> dict:
    """获取注入了 KEETA_BI_SSOID 的环境变量（优先用已有的，否则 mtsso 换票）"""
    env = os.environ.copy()
    if env.get("KEETA_BI_SSOID"):
        return env
    # tracking: scripts/holidays.py::_get_bi_env::skill-script
    started_at = time.time()
    params = "mtsso-moa-local-exchange audience=com.sankuai.fetc.mdbi.home"
    try:
        result = subprocess.run(
            ["npx", "mtsso-moa-local-exchange", "--audience", "com.sankuai.fetc.mdbi.home"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            token = json.loads(result.stdout).get("access_token", "")
            if token:
                env["KEETA_BI_SSOID"] = token
                _track_script(params, "token=present", started_at, True)
            else:
                _track_script(params, "", started_at, False, "missing access_token")
        else:
            error = result.stderr.strip() or f"returncode={result.returncode}"
            _track_script(params, "", started_at, False, error)
    except Exception:
        _track_script(params, "", started_at, False, "mtsso exchange failed")
        pass
    return env


def _is_permission_error(stderr: str) -> bool:
    """判断错误是否为权限不足"""
    keywords = ["submit_no_permission", "NO_PERMISSION", "无表权限", "权限不足"]
    return any(k in stderr for k in keywords)


def _no_permission_result(start_date: str = None, end_date: str = None,
                          year: int = None, regions: list = None) -> dict:
    """构造权限不足的结构化错误结果"""
    return {
        "error_type": "no_permission",
        "error_message": (
            "没有查询节假日数据表的权限（mart_sailor_global.fact_public_date_info_snap_d）。\n"
            "⚠️  说明：中东节假日（如开斋节）有时前几天才能由伊斯兰历换算确认，"
            "对准确性和时效性要求高时强烈建议申请数据表权限。"
        ),
        "apply_link": APPLY_LINK,
        "fallback_available": os.path.exists(CACHE_PATH),
        "date_range": f"{start_date} ~ {end_date}" if start_date else None,
        "year": year,
        "regions": regions or SUPPORTED_REGIONS,
    }


def _load_cache(start_date: str, end_date: str, regions: list) -> dict:
    """从本地 JSON 缓存读取节假日"""
    if not os.path.exists(CACHE_PATH):
        return {
            "error_type": "cache_not_found",
            "error_message": "本地缓存不存在，请先申请权限并通过 holidays.py 更新缓存。",
        }
    with open(CACHE_PATH, encoding="utf-8") as f:
        cache = json.load(f)

    start = start_date.replace("-", "")
    end   = end_date.replace("-", "")

    grouped = {}
    for region in regions:
        entries = cache.get("holidays", {}).get(region, [])
        filtered = []
        for e in entries:
            d = e["date"].replace("-", "")
            if start <= d <= end:
                filtered.append(e)
        if filtered:
            grouped[region] = filtered

    return {
        "source": "local_cache",
        "cache_updated_at": cache.get("updated_at", "unknown"),
        "date_range": f"{start_date} ~ {end_date}",
        "regions": list(grouped.keys()),
        "holidays": grouped,
    }


def _run_sql(sql: str) -> dict:
    """执行 SQL，返回 (success, data_or_error_dict)"""
    # tracking: scripts/holidays.py::_run_sql::skill-script
    started_at = time.time()
    sql_preview = " ".join(sql.split())[:320]
    params = f"holidays.run_sql space={SPACE_ID} queue={QUEUE} sql={sql_preview}"
    try:
        bi_script = _get_keeta_bi_script()
    except FileNotFoundError as e:
        _track_script(params, "", started_at, False, str(e))
        return {"ok": False, "stderr": str(e), "stdout": ""}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
        f.write(sql)
        sql_path = f.name
    try:
        result = subprocess.run(
            ["python3", bi_script, "run", sql_path,
             "-p", SPACE_ID, "-q", QUEUE, "--json"],
            capture_output=True, text=True, timeout=60,
            env=_get_bi_env()
        )
        if result.returncode != 0:
            _track_script(params, result.stdout[-500:], started_at, False, result.stderr[-200:])
            return {"ok": False, "stderr": result.stderr, "stdout": result.stdout}
        data = json.loads(result.stdout)
        row_count = len(data.get("data") or []) if isinstance(data, dict) else 0
        _track_script(params, f"rows={row_count}", started_at, True)
        return {"ok": True, "data": data}
    except subprocess.TimeoutExpired:
        msg = "查询超时（60s），请稍后重试或检查数仓连接"
        _track_script(params, "", started_at, False, msg)
        return {"ok": False, "stderr": msg, "stdout": ""}
    except Exception as e:
        _track_script(params, "", started_at, False, str(e))
        raise
    finally:
        os.unlink(sql_path)


def query_holidays(year: int, regions: list = None, allow_fallback: bool = False) -> dict:
    """从数仓查询节假日，返回按地区分组的结构"""
    if regions is None:
        regions = SUPPORTED_REGIONS
    regions_str = ",".join(f"'{r}'" for r in regions)
    start = f"{year}0101"
    end   = f"{year}1231"

    sql = f"""
SELECT region, date, holiday_name, type, detailed_type, i18n_key
FROM mart_sailor_global.fact_public_date_info_snap_d
WHERE dt = (SELECT MAX(dt) FROM mart_sailor_global.fact_public_date_info_snap_d)
  AND date >= '{start}' AND date <= '{end}'
  AND region IN ({regions_str})
  AND holiday_name != ''
ORDER BY region, date ASC
""".strip()

    res = _run_sql(sql)
    if not res["ok"]:
        if _is_permission_error(res["stderr"]):
            if allow_fallback:
                return _load_cache(f"{year}-01-01", f"{year}-12-31", regions)
            return _no_permission_result(year=year, regions=regions)
        raise RuntimeError(f"查询失败: {res['stderr']}")

    data = res["data"]
    if not data.get("success"):
        raise RuntimeError(f"查询错误: {data}")

    grouped = {}
    for row in data["data"]:
        region, date, name, typ, det, key = row
        if region not in grouped:
            grouped[region] = []
        grouped[region].append({
            "date": date,
            "holiday_name": name,
            "type": typ,
            "detailed_type": det,
            "i18n_key": key,
        })

    return {
        "source": "mart_sailor_global.fact_public_date_info_snap_d",
        "year": year,
        "regions": list(grouped.keys()),
        "holidays": grouped,
    }


def get_holidays_for_date_range(start_date: str, end_date: str,
                                regions: list = None,
                                allow_fallback: bool = False) -> dict:
    """查询指定日期范围内的节假日"""
    if regions is None:
        regions = SUPPORTED_REGIONS
    regions_str = ",".join(f"'{r}'" for r in regions)

    sql = f"""
SELECT region, date, holiday_name, type, detailed_type, i18n_key
FROM mart_sailor_global.fact_public_date_info_snap_d
WHERE dt = (SELECT MAX(dt) FROM mart_sailor_global.fact_public_date_info_snap_d)
  AND date >= '{start_date.replace("-","")}' 
  AND date <= '{end_date.replace("-","")}'
  AND region IN ({regions_str})
  AND holiday_name != ''
ORDER BY region, date ASC
""".strip()

    res = _run_sql(sql)
    if not res["ok"]:
        if _is_permission_error(res["stderr"]):
            if allow_fallback:
                return _load_cache(start_date, end_date, regions)
            return _no_permission_result(start_date=start_date, end_date=end_date, regions=regions)
        raise RuntimeError(f"查询失败: {res['stderr']}")

    data = res["data"]
    grouped = {}
    for row in data["data"]:
        region, date, name, typ, det, key = row
        if region not in grouped:
            grouped[region] = []
        grouped[region].append({
            "date": f"{date[:4]}-{date[4:6]}-{date[6:]}",
            "holiday_name": name,
            "type": typ,
            "detailed_type": det,
            "i18n_key": key,
        })

    return {
        "source": "mart_sailor_global.fact_public_date_info_snap_d",
        "date_range": f"{start_date} ~ {end_date}",
        "regions": list(grouped.keys()),
        "holidays": grouped,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="节假日查询")
    parser.add_argument("mode", choices=["year", "range"], help="year=整年 / range=日期范围")
    parser.add_argument("--year", type=int, default=datetime.now().year, help="年份（默认当年）")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD（range模式）")
    parser.add_argument("--end",   help="结束日期 YYYY-MM-DD（range模式）")
    parser.add_argument("--regions", help="逗号分隔的地区代码，默认全部",
                        default=",".join(SUPPORTED_REGIONS))
    parser.add_argument("--allow-fallback", action="store_true",
                        help="无权限时自动降级到本地JSON缓存（不提示用户选择）")
    args = parser.parse_args()

    regions = [r.strip().upper() for r in args.regions.split(",")]

    if args.mode == "year":
        result = query_holidays(args.year, regions, allow_fallback=args.allow_fallback)
    else:
        if not args.start or not args.end:
            print("range模式需要 --start 和 --end", file=sys.stderr)
            sys.exit(1)
        result = get_holidays_for_date_range(
            args.start, args.end, regions, allow_fallback=args.allow_fallback
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))
