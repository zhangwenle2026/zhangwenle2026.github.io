#!/usr/bin/env python3
"""
Keeta External Context - 大型活动/安全局势/竞争动态实时搜索
数据源：catclaw_search 实时搜索（bing/google，无本地缓存）

支持查询：
  - 体育赛事、F1、大型演唱会/展会
  - 中东/巴西安全局势、政策动态
  - Keeta 覆盖地区的竞争动态（iFood/Talabat/Careem 等）
"""
import argparse
import json
import os
import subprocess
import sys
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

def _find_catclaw_search() -> str:
    """动态探测 catclaw_search.py 路径（兼容系统 skill 和自定义 skill）"""
    candidates = [
        "/app/skills/catclaw-search/scripts/catclaw_search.py",
        os.path.expanduser("~/.openclaw/skills/catclaw-search/scripts/catclaw_search.py"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]  # 找不到时返回默认路径，让后续报错

CATCLAW_SEARCH = _find_catclaw_search()

REGION_META = {
    "SA": {"name": "沙特阿拉伯", "city": "Riyadh", "lang": "en"},
    "QA": {"name": "卡塔尔",     "city": "Doha",   "lang": "en"},
    "BH": {"name": "巴林",       "city": "Manama", "lang": "en"},
    "AE": {"name": "阿联酋",     "city": "Dubai",  "lang": "en"},
    "KW": {"name": "科威特",     "city": "Kuwait City", "lang": "en"},
    "HK": {"name": "香港",       "city": "Hong Kong",   "lang": "zh"},
    "BR": {"name": "巴西",       "city": "Sao Paulo",   "lang": "pt"},
}

SUPPORTED_REGIONS = list(REGION_META.keys())

CATEGORY_QUERIES = {
    "sports": {
        "en": "{city} major sports events {month}",
        "zh": "香港 大型体育赛事 {month}",
        "pt": "São Paulo grandes eventos esportivos {month}",
    },
    "security": {
        "en": "{country} security situation {month} latest news",
        "zh": "香港 安全局势 {month}",
        "pt": "Brasil situação segurança {month}",
    },
    "competition": {
        "en": "food delivery competition {country} {month} Talabat iFood Keeta",
        "zh": "香港 外卖 竞争 {month}",
        "pt": "entrega comida concorrência iFood {month}",
    },
    "general": {
        "en": "{city} major events {month}",
        "zh": "香港 大型活动 {month}",
        "pt": "São Paulo grandes eventos {month}",
    },
}

COUNTRY_NAMES = {
    "SA": "Saudi Arabia",
    "QA": "Qatar",
    "BH": "Bahrain",
    "AE": "UAE",
    "KW": "Kuwait",
    "HK": "Hong Kong",
    "BR": "Brazil",
}


def _catclaw_search(query: str, n: int = 8, engine: str = "bing") -> list:
    """调用 catclaw_search，返回结果列表"""
    # tracking: scripts/events_search.py::_catclaw_search::skill-script
    started_at = time.time()
    params = f"catclaw_search engine={engine} n={n} query={query}"
    if not os.path.exists(CATCLAW_SEARCH):
        msg = f"catclaw-search skill 未安装，请先安装：{CATCLAW_SEARCH}"
        _track_script(params, "", started_at, False, msg)
        raise FileNotFoundError(msg)
    try:
        result = subprocess.run(
            ["python3", CATCLAW_SEARCH, "search", query,
             "-s", engine, "-n", str(n), "--timeout", "20"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(f"搜索失败: {result.stderr.strip()}")
        data = json.loads(result.stdout)
        # catclaw_search 返回 {"results": [...]} 或直接 [...]
        if isinstance(data, dict):
            items = data.get("results", [])
        else:
            items = data
        _track_script(params, f"items={len(items)}", started_at, True)
        return items
    except subprocess.TimeoutExpired as e:
        msg = "搜索超时（30s）"
        _track_script(params, "", started_at, False, msg)
        raise RuntimeError(msg) from e
    except Exception as e:
        _track_script(params, "", started_at, False, str(e))
        raise


def _build_query(region: str, category: str, date_str: str) -> str:
    """根据地区/类型/日期构建搜索词"""
    meta = REGION_META[region]
    lang = meta["lang"]
    city = meta["city"]
    country = COUNTRY_NAMES[region]

    # 日期描述（如 "April 2026"）
    try:
        dt = datetime.strptime(date_str[:7], "%Y-%m")
        month_en = dt.strftime("%B %Y")
        month_zh = dt.strftime("%Y年%m月")
        month_pt = dt.strftime("%B %Y")
    except Exception:
        month_en = month_zh = month_pt = date_str

    month = {"en": month_en, "zh": month_zh, "pt": month_pt}[lang]

    template = CATEGORY_QUERIES.get(category, CATEGORY_QUERIES["general"])[lang]
    return template.format(city=city, country=country, month=month)


def search_events(region: str, date_str: str,
                  categories: list = None,
                  n_per_query: int = 6) -> dict:
    """
    实时搜索指定地区、日期的外部事件

    :param region: 地区代码 SA/QA/BH/AE/KW/HK/BR
    :param date_str: 日期字符串，YYYY-MM 或 YYYY-MM-DD
    :param categories: 查询类别列表，默认 ["sports", "security", "competition"]
    :param n_per_query: 每次搜索返回条数
    :return: 结构化结果 dict
    """
    if categories is None:
        categories = ["sports", "security", "competition"]

    region = region.upper()
    meta = REGION_META.get(region)
    if not meta:
        raise ValueError(f"不支持的地区: {region}，支持: {SUPPORTED_REGIONS}")

    results = {}
    errors = []

    for cat in categories:
        query = _build_query(region, cat, date_str)
        try:
            items = _catclaw_search(query, n=n_per_query)
            results[cat] = {
                "query": query,
                "count": len(items),
                "items": [
                    {
                        "title": r.get("title", ""),
                        "snippet": r.get("snippet", ""),
                        "url": r.get("url", ""),
                        "publish_time": r.get("publish_time", ""),
                    }
                    for r in items
                ],
            }
        except Exception as e:
            errors.append({"category": cat, "error": str(e)})

    return {
        "source": "catclaw_search_realtime",
        "region": region,
        "region_name": meta["name"],
        "date": date_str,
        "queried_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "categories": results,
        "errors": errors,
    }


def search_events_multi(regions: list, date_str: str,
                        categories: list = None) -> dict:
    """批量查询多个地区"""
    out = {}
    for region in regions:
        try:
            out[region] = search_events(region, date_str, categories)
        except Exception as e:
            out[region] = {"error": str(e)}
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="实时搜索 Keeta 各地区外部事件")
    parser.add_argument("region", nargs="?",
                        help="地区代码 SA/QA/BH/AE/KW/HK/BR，留空查全部")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m"),
                        help="日期 YYYY-MM 或 YYYY-MM-DD（默认当月）")
    parser.add_argument("--categories", default="sports,security,competition",
                        help="逗号分隔，可选: sports/security/competition/general")
    parser.add_argument("--regions", help="逗号分隔多地区（与 region 二选一）")
    parser.add_argument("--n", type=int, default=6, help="每类搜索返回条数")
    args = parser.parse_args()

    cats = [c.strip() for c in args.categories.split(",")]

    if args.regions:
        region_list = [r.strip().upper() for r in args.regions.split(",")]
        result = search_events_multi(region_list, args.date, cats)
    elif args.region:
        result = search_events(args.region.upper(), args.date, cats, args.n)
    else:
        result = search_events_multi(SUPPORTED_REGIONS, args.date, cats)

    print(json.dumps(result, ensure_ascii=False, indent=2))
