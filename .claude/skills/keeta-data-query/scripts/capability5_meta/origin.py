#!/usr/bin/env python3
"""Origin KPI lineage via mtcli."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

_CORE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "core"))
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)
_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

try:
    from core.mtcli import run as _mtcli_run
except ImportError:
    from mtcli import run as _mtcli_run

from capability5_meta.auth import get_origin_token as _auth_get_origin_token


BUSI_LINE_ID = 274

_KPI_UNIT = {-1: "无", 1: "次", 2: "元", 3: "单", 4: "人", 5: "家", 6: "秒", 7: "分钟", 8: "%", 9: "个", 10: "元/单", 11: "次/单", 12: "元/人", 13: "天", 14: "小时", 15: "倍", 16: "分"}
_KPI_TYPE = {1: "原子指标", 2: "派生指标", 3: "复合指标", 8: "原子指标", 9: "派生指标"}
_CERTIFIED = {0: "未认证", 1: "已认证", 2: "审核中"}
_TENDENCY = {1: "越大越好", 2: "越小越好", 0: "无倾向"}
_GLOBAL_SCHEMAS = ("mart_sailor_global.", "sailor_analysis_global.")


def _get_access_token(timeout: int = 12) -> str | None:
    del timeout
    return _auth_get_origin_token()


def _origin_headers() -> dict[str, str]:
    token = _get_access_token() or ""
    return {
        "access-token": token,
        "X-BusilineId": str(BUSI_LINE_ID),
        "x-locale": "zh",
        "x-i18n-lang": "1",
        "x-requested-with": "XMLHttpRequest",
    }


def _unwrap_data(payload: dict[str, Any]) -> Any:
    node: Any = payload
    if isinstance(node, dict) and node.get("success") is True and "data" in node:
        node = node["data"]
    if isinstance(node, dict) and node.get("code", 0) not in (0, 200, None):
        raise RuntimeError(node.get("message") or node.get("msg") or node)
    return node.get("data", node) if isinstance(node, dict) else node


def _parse_model_detail(data: dict[str, Any]) -> dict[str, Any]:
    model_info = data.get("modelInfo") or data
    detail_model = model_info.get("detailModel") or {}
    table_config = detail_model.get("tableConfig") or model_info.get("tableConfig") or {}

    main = {
        "db": table_config.get("dbName", ""),
        "table": table_config.get("tableName", ""),
        "dsn": table_config.get("dsn", ""),
        "filter": table_config.get("customFilterCondition") or "",
    }

    joins = []
    for relation in table_config.get("modelTableRelations", []) or []:
        join_keys = [
            {
                "main": join_col.get("mainJoinColumn") or join_col.get("customMainJoinColumn") or "",
                "join": join_col.get("joinColumn") or join_col.get("customJoinColumn") or "",
                "custom_sql": join_col.get("customJoinSql") or "",
            }
            for join_col in relation.get("joinColumns", []) or []
        ]
        filter_conditions = [
            {
                "column": condition.get("columnName", ""),
                "rule": condition.get("selectRule", ""),
                "value": condition.get("ruleValue", ""),
            }
            for condition in relation.get("filterConditions", []) or []
        ]
        joins.append({
            "seq": relation.get("joinTableNum", 0),
            "join_type": relation.get("joinType", "left join"),
            "join_db": relation.get("joinDb", ""),
            "join_table": relation.get("joinTable", ""),
            "join_keys": join_keys,
            "filter_conditions": filter_conditions,
        })

    return {"main_table": main, "joins": joins}


def fetch_model_detail(model_id: int, busi_line_id: int = BUSI_LINE_ID) -> dict[str, Any]:
    headers = _origin_headers()
    headers["X-BusilineId"] = str(busi_line_id)
    payload = _mtcli_run(
        ["kdata", "meta", "origin-model-detail"],
        body={"modelId": int(model_id)},
        headers=headers,
        timeout=30,
    )
    data = _unwrap_data(payload)
    return _parse_model_detail(data if isinstance(data, dict) else {})


def _items_from_kpi_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = _unwrap_data(payload)
    if isinstance(data, dict):
        items = data.get("items") or data.get("list") or data.get("data") or []
        return items if isinstance(items, list) else []
    return data if isinstance(data, list) else []


def _kpi_search_params(keyword: str, page_size: int) -> dict[str, str]:
    return {
        "busiLineId": str(BUSI_LINE_ID),
        "searchTxt": keyword,
        "pageNo": "1",
        "pageSize": str(page_size),
        "showType": "list",
        "status": "-1",
        "kpiType": "-1",
        "cn": "1",
        "brDefineStatus": "-1",
        "brTechStatus": "-1",
        "brType": "-1",
        "certifiedStatus": "-1",
        "complianceStatus": "0",
        "importantLevel": "0",
        "secrecyLevel": "0",
        "standard": "-1",
        "techStatus": "-1",
    }


def _normalise_kpi_item(item: dict[str, Any]) -> dict[str, Any]:
    code = item.get("kpiCode") or item.get("code") or item.get("metricCode") or ""
    name = item.get("kpiName") or item.get("name") or item.get("metricName") or ""
    desc = item.get("kpiDefine") or item.get("description") or item.get("desc") or item.get("metricDesc") or ""
    normalised = {
        "dataset_id": str(item.get("dataSetId") or item.get("dataset_id") or ""),
        "dataset_name": item.get("dataSetName") or item.get("dataset_name") or "",
        "code": code,
        "name": name,
        "desc": desc,
        "kpi_id": item.get("kpiId") or item.get("id"),
    }
    return {**item, **normalised}


def search_measures_online(keyword: str, max_results: int = 20) -> list[dict[str, Any]]:
    payload = _mtcli_run(
        ["kdata", "meta", "origin-kpi-list"],
        params=_kpi_search_params(keyword, max_results),
        headers=_origin_headers(),
        timeout=30,
    )
    return [_normalise_kpi_item(item) for item in _items_from_kpi_list(payload)][:max_results]


def search_measures(keyword: str) -> list[dict[str, Any]]:
    return search_measures_online(keyword)


def get_kpi_detail(kpi_id: int, kpi_code: str | None = None) -> dict | None:
    keyword = kpi_code or str(kpi_id)
    items = _items_from_kpi_list(_mtcli_run(
        ["kdata", "meta", "origin-kpi-list"],
        params=_kpi_search_params(keyword, 10),
        headers=_origin_headers(),
        timeout=30,
    ))
    for item in items:
        if (kpi_id and item.get("kpiId") == kpi_id) or (kpi_code and item.get("kpiCode") == kpi_code):
            return item
    return items[0] if items else None


def format_kpi_detail(detail: dict) -> str:
    if not detail:
        return ""
    lines = [
        f"指标名称：{detail.get('kpiName') or detail.get('name', '')}",
        f"英文代码：{detail.get('kpiCode') or detail.get('code', '')}",
        f"kpiId  ：{detail.get('kpiId') or detail.get('id', '')}",
    ]
    ktype = detail.get("kpiType") or detail.get("actualType")
    lines.append(f"指标类型：{_KPI_TYPE.get(ktype, str(ktype))}")
    unit = detail.get("kpiUnit")
    lines.append(f"单    位：{_KPI_UNIT.get(unit, str(unit) if unit else '无')}")
    cert = detail.get("certifiedStatus")
    lines.append(f"认证状态：{_CERTIFIED.get(cert, str(cert))}")
    tend = detail.get("kpiTendency")
    if tend is not None:
        lines.append(f"优化方向：{_TENDENCY.get(tend, str(tend))}")
    for label, key in (("业务负责人", "owner"), ("技术负责人", "techOwner"), ("口径定义", "kpiDefine")):
        value = detail.get(key)
        if value:
            lines.append(f"{label}：{value}")
    return "\n".join(lines)


def get_kpi_id_from_origin(measure_code: str) -> int | None:
    for item in search_measures_online(measure_code, max_results=10):
        if item.get("kpiCode") == measure_code or item.get("code") == measure_code:
            return item.get("kpiId") or item.get("id") or item.get("kpi_id")
    return None


def fetch_kpi_tech(kpi_id: int, timeout: int = 12) -> dict[str, Any]:
    del timeout
    headers = _origin_headers()
    params = {"kpiId": str(kpi_id)}
    tech = _mtcli_run(
        ["kdata", "meta", "origin-kpi-tech-get"],
        params=params,
        headers=headers,
        timeout=30,
    )
    dep = _mtcli_run(
        ["kdata", "meta", "kpi-tech-dependency"],
        params=params,
        headers=headers,
        timeout=30,
    )
    return {"tech": tech, "dep": dep}


def _payload_data(payload: Any) -> Any:
    return _unwrap_data(payload) if isinstance(payload, dict) else payload


def parse_models(tech_data: dict, global_only: bool = True) -> list[dict[str, Any]]:
    data = _payload_data(tech_data)
    if not isinstance(data, dict):
        return []
    models = []
    for model in (data.get("basicModels") or []) + (data.get("deriveModels") or []):
        formula = model.get("kpiFormula", "")
        table = ""
        match = re.search(r"\(([a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)\[", formula)
        if match:
            table = match.group(1)
        if global_only and table and not any(table.startswith(schema) for schema in _GLOBAL_SCHEMAS):
            continue
        raw_filter = (model.get("filterFormula") or "").strip()
        filter_expr = re.sub(r"\$\{[^}]+\.([a-zA-Z0-9_]+)\}", r"\1", raw_filter).strip() if raw_filter else ""
        models.append({
            "modelId": model.get("modelId"),
            "modelName": model.get("modelName"),
            "engine": model.get("engineType"),
            "dsn": model.get("dsn"),
            "table": table.replace("sailor_analysis_global.", "mart_sailor_global.") if table else "",
            "raw_table": table,
            "column": model.get("columnName"),
            "calType": model.get("calType"),
            "formula": formula,
            "filterFormula": filter_expr,
        })
    return models


def _dependency_items(dep_payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = _payload_data(dep_payload)
    return data if isinstance(data, list) else []


def query_lineage(kpi_id: int, depth: int = 0, timeout: int = 12, _visited: set[int] | None = None) -> dict[str, Any]:
    if _visited is None:
        _visited = set()
    if kpi_id in _visited:
        return {"kpiId": kpi_id, "models": [], "atomicKpis": []}
    _visited.add(kpi_id)

    pad = "  " * depth
    print(f"{pad}🔍 查询 kpiId={kpi_id}...", file=sys.stderr)
    raw = fetch_kpi_tech(kpi_id, timeout=timeout)
    global_only = not getattr(sys, "_all_schemas", False)
    models = parse_models(raw.get("tech"), global_only=global_only)
    atomic_kpis = _dependency_items(raw.get("dep") or {})
    result = {"kpiId": kpi_id, "models": models, "atomicKpis": []}

    if atomic_kpis and depth < 3:
        print(f"{pad}  → 派生指标，依赖 {len(atomic_kpis)} 个原子指标", file=sys.stderr)
        for atom in atomic_kpis:
            atom_id = atom.get("kpiId")
            if not atom_id:
                continue
            sub = query_lineage(atom_id, depth + 1, timeout, _visited)
            sub.update({"kpiName": atom.get("kpiName"), "kpiCode": atom.get("kpiCode")})
            result["atomicKpis"].append(sub)
    elif atomic_kpis:
        for atom in atomic_kpis:
            result["atomicKpis"].append({
                "kpiId": atom.get("kpiId"),
                "kpiName": atom.get("kpiName"),
                "kpiCode": atom.get("kpiCode"),
            })
    return result


def fetch_model_joins(model_id: int) -> list[dict[str, Any]]:
    try:
        detail = fetch_model_detail(model_id, BUSI_LINE_ID)
        return detail.get("joins", [])
    except Exception:
        return []


def print_lineage(lineage: dict[str, Any], indent: int = 0, show_joins: bool = False) -> None:
    pad = "  " * indent
    name = lineage.get("kpiName", f"kpiId={lineage.get('kpiId')}")
    code = lineage.get("kpiCode", "")
    label = f"{name}({code})" if code else name

    if lineage.get("models"):
        print(f"{pad}📊 {label}")
        for model in lineage["models"]:
            filter_str = f"  |  字段过滤: {model['filterFormula']}" if model.get("filterFormula") else ""
            print(f"{pad}  ├── 模型:  {model['modelName']} (id={model['modelId']})")
            print(f"{pad}  ├── 引擎:  {model['engine']}")
            print(f"{pad}  ├── 底层表: {model['table']}")
            print(f"{pad}  └── 字段:  {model['column']}  |  聚合: {model['calType']}{filter_str}")
            if show_joins:
                joins = fetch_model_joins(model["modelId"])
                if joins:
                    print(f"{pad}     【关联表配置】")
                    for join in joins:
                        print(f"{pad}       {join}")
    elif lineage.get("atomicKpis"):
        print(f"{pad}📐 {label}（派生指标）")
    else:
        print(f"{pad}❓ {label}（无模型信息）")

    for atom in lineage.get("atomicKpis", []):
        print_lineage(atom, indent + 1, show_joins=show_joins)


def _resolve_kpi_id(args: argparse.Namespace) -> int:
    if getattr(args, "kpi_id", None):
        return args.kpi_id

    keyword = getattr(args, "search", None) or getattr(args, "name", None) or getattr(args, "code", None)
    if not keyword:
        raise RuntimeError("需要提供 kpi_id、--code、--name 或 --search")
    results = search_measures(keyword)
    if not results:
        raise RuntimeError(f"未找到匹配指标: {keyword}")

    print(f"\n🔎 找到 {len(results)} 个匹配指标：", file=sys.stderr)
    for idx, item in enumerate(results[:20], 1):
        print(f"  {idx}. {item.get('code', '')} | {item.get('name', '')} kpiId={item.get('kpiId') or item.get('kpi_id', '')}", file=sys.stderr)

    if getattr(args, "list_only", False):
        if getattr(args, "json", False):
            print(json.dumps(results[:20], ensure_ascii=False, indent=2))
        raise SystemExit(0)

    kpi_id = results[0].get("kpiId") or results[0].get("id") or results[0].get("kpi_id")
    if not kpi_id and results[0].get("code"):
        kpi_id = get_kpi_id_from_origin(results[0]["code"])
    if not kpi_id:
        raise RuntimeError("无法确定 kpi_id")
    return int(kpi_id)


def run(args: argparse.Namespace) -> None:
    sys._all_schemas = getattr(args, "all_schemas", False)
    try:
        kpi_id = _resolve_kpi_id(args)
        lineage = query_lineage(kpi_id)
    except Exception as exc:
        print(f"❌ {exc}", file=sys.stderr)
        raise SystemExit(1)

    if getattr(args, "json", False):
        print(json.dumps(lineage, ensure_ascii=False, indent=2))
        return

    if getattr(args, "info", False):
        detail = get_kpi_detail(kpi_id)
        if detail:
            print("\n📊 指标信息：")
            print(format_kpi_detail(detail))
    print_lineage(lineage)


def main() -> None:
    parser = argparse.ArgumentParser(description="起源指标血缘查询 (mtcli, busiLineId=274)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("kpi_id", type=int, nargs="?")
    group.add_argument("--search", "-s")
    group.add_argument("--name", "-n")
    group.add_argument("--code", "-c")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--info", action="store_true")
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--all-schemas", action="store_true")
    parser.add_argument("--joins", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
