#!/usr/bin/env python3
"""
capability1_standard/mtcli_standard_client.py — 基于 mtcli 的起源标准数据集查询客户端与 CLI 处理函数

与旧 standard client 接口兼容，通过 shell out 到 `mtcli kdata standard *`
实现查询，无需自行管理 SSO 鉴权。

覆盖命令：
  list_datasets      → mtcli kdata standard datasets
  list_measures      → mtcli kdata standard measures
  list_dimensions    → mtcli kdata standard dims-by-dataset
  list_dim_values    → mtcli kdata standard dim-values
  query              → mtcli kdata standard query

本模块同时承接 `kdata standard ...` 的命令处理函数，保持主入口 kdata.py 只做路由。

已知限制：
  - datasets / measures / dims-by-dataset 不支持 region 参数（mtcli 未暴露），已静默忽略
  - search 过滤在客户端完成（measures / dims），dim-values 的 keyword 传服务端
"""

from __future__ import annotations

import json
import os
import re
import sys
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import quote

from .operators import calc_proportion, calc_gini, calc_fluctuation
from .operators.fluctuation import (
    resolve_ratio_components,
    infer_pop_from_date as _infer_pop_from_date,
    shift_date_range as _shift_date_range,
    merge_base_period as _merge_base_period,
    get_fluctuation_type as _get_fluctuation_type,
)

try:
    from core.mtcli import run as _mtcli_run
except ImportError:
    from mtcli import run as _mtcli_run


_STANDARD_SUPPORTED_REGIONS = ("SA", "HK", "AE", "QA", "KW", "BR", "BH")
_STANDARD_SUPPORTED_REGION_SET = set(_STANDARD_SUPPORTED_REGIONS)


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _run(args: list[str], timeout: int = 30, body: dict[str, Any] | None = None) -> dict:
    """
    执行 `mtcli <args>`，返回解析后的 JSON payload。
    失败时抛出 RuntimeError。
    """
    return _mtcli_run(args, body=body, timeout=timeout)


def _flatten_columns(col_list: list) -> list[str]:
    """递归展开嵌套 columnList，返回叶子 key 列表。"""
    keys: list[str] = []
    for c in col_list:
        children = c.get("children")
        if children:
            keys.extend(_flatten_columns(children))
        else:
            keys.append(c["key"])
    return keys


def _validate_date_range(date_range: str) -> None:
    """标准数据集后端只接受 yyyyMMdd 或 yyyyMMdd~yyyyMMdd。"""
    value = str(date_range or "").strip()
    if not value:
        raise ValueError("日期格式必须为 yyyyMMdd 或 yyyyMMdd~yyyyMMdd，例如 20260615 或 20260601~20260615")
    parts = value.split("~")
    if len(parts) > 2 or any(not re.fullmatch(r"\d{8}", part) for part in parts):
        raise ValueError("日期格式必须为 yyyyMMdd 或 yyyyMMdd~yyyyMMdd，例如 20260615 或 20260601~20260615")


def _flatten_search_text(value: Any) -> str:
    """Flatten nested metadata into searchable text without changing output shape."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_flatten_search_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_search_text(v) for v in value)
    return str(value)


def _search_terms(keyword: str) -> list[str]:
    raw = str(keyword or "").strip().lower()
    if not raw:
        return []
    terms = [raw]
    terms.extend(re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+", raw))
    result: list[str] = []
    for term in terms:
        if term and term not in result:
            result.append(term)
    return result


def _score_measure_match(measure: dict[str, Any], keyword: str) -> int:
    terms = _search_terms(keyword)
    if not terms:
        return 1

    fields = {
        "code": _flatten_search_text(measure.get("code")).lower(),
        "name": _flatten_search_text(measure.get("name")).lower(),
        "desc": _flatten_search_text(measure.get("desc")).lower(),
        "name_i18n": _flatten_search_text(measure.get("nameFieldList")).lower(),
        "desc_i18n": _flatten_search_text(measure.get("descFieldList")).lower(),
        "category": _flatten_search_text(measure.get("categoryList")).lower(),
    }
    whole = terms[0]
    score = 0

    if whole and whole == fields["code"]:
        score += 220
    if whole and whole == fields["name"]:
        score += 210
    weights = {
        "name": 110,
        "code": 95,
        "name_i18n": 80,
        "desc": 55,
        "desc_i18n": 50,
        "category": 35,
    }
    token_weights = {
        "name": 24,
        "code": 20,
        "name_i18n": 16,
        "desc": 9,
        "desc_i18n": 8,
        "category": 5,
    }

    for field, text in fields.items():
        if whole and whole in text:
            score += weights[field]
        for term in terms[1:]:
            if term in text:
                score += token_weights[field]

    return score


def _rank_measure_search_results(items: list[dict[str, Any]], keyword: str) -> list[dict[str, Any]]:
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, item in enumerate(items):
        score = _score_measure_match(item, keyword)
        if score > 0:
            scored.append((score, index, item))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [item for _, _, item in scored]


def _candidate_blob(item: dict[str, Any]) -> str:
    return " ".join(
        _flatten_search_text(item.get(key))
        for key in ("code", "name", "desc", "nameFieldList", "descFieldList", "nameI18nList", "descI18nList")
    ).lower()


def _suggest_items(code: str, items: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    query = str(code or "").lower()
    ranked: list[tuple[float, int, dict[str, Any]]] = []
    for index, item in enumerate(items):
        item_code = str(item.get("code") or "").lower()
        item_name = str(item.get("name") or "").lower()
        blob = _candidate_blob(item)
        score = max(
            SequenceMatcher(None, query, item_code).ratio(),
            SequenceMatcher(None, query, item_name).ratio() * 0.9,
        )
        if query and (query in item_code or item_code in query):
            score += 1.0
        if query and query in blob:
            score += 0.4
        if score > 0.35:
            ranked.append((score, index, item))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return [item for _, _, item in ranked[:limit]]


def _format_suggestions(missing_code: str, items: list[dict[str, Any]]) -> str:
    suggestions = _suggest_items(missing_code, items)
    if not suggestions:
        return "无相近候选"
    formatted = []
    for item in suggestions:
        code = item.get("code", "")
        name = item.get("name", "")
        formatted.append(f"{code}({name})" if name else str(code))
    return "、".join(formatted)


def _exit_unknown_codes(kind: str, dataset_id: Any, missing: list[str], items: list[dict[str, Any]], command_hint: str) -> None:
    print(f"错误: 以下{kind} code 不在数据集 {dataset_id} 中：{', '.join(missing)}", file=sys.stderr)
    for code in missing:
        print(f"  - {code}：相近候选：{_format_suggestions(code, items)}", file=sys.stderr)
    print(f"💡 可先执行：{command_hint}", file=sys.stderr)
    sys.exit(1)


def _append_filter_values(filters: dict[str, list[str]], key: str, values: list[str]) -> None:
    bucket = filters.setdefault(key, [])
    for value in values:
        if value and value not in bucket:
            bucket.append(value)


def _normalise_region_code(region: Any) -> str:
    return str(region or "").strip().upper()


def _ordered_supported_regions(regions: list[str]) -> list[str]:
    available = {_normalise_region_code(region) for region in regions if _normalise_region_code(region)}
    return [region for region in _STANDARD_SUPPORTED_REGIONS if region in available]


def _format_region_list(regions: list[str]) -> str:
    return "/".join(regions) if regions else "无"


def _load_allowed_region_context(client: Any) -> list[str] | None:
    loader = getattr(client, "list_region_hq_regions", None)
    if not callable(loader):
        return None
    return _ordered_supported_regions(loader())


def _prepare_standard_query_region(args: Any, client: Any) -> None:
    if getattr(args, "region", None):
        args.region = _normalise_region_code(args.region)

    allowed_regions = None
    try:
        allowed_regions = _load_allowed_region_context(client)
    except Exception as exc:
        print(f"⚠️  获取 Region 权限上下文失败，将继续执行查询：{exc}", file=sys.stderr)

    if allowed_regions is not None:
        print(f"ℹ️  当前账号可用区域总部权限 Region: {_format_region_list(allowed_regions)}", file=sys.stderr)

    if not getattr(args, "region", None):
        print("错误: region 必须指定（SA/HK/AE/QA/KW/BR/BH）", file=sys.stderr)
        if allowed_regions is not None:
            print(f"💡 当前账号可用区域总部权限 Region: {_format_region_list(allowed_regions)}", file=sys.stderr)
        sys.exit(1)

    if args.region not in _STANDARD_SUPPORTED_REGION_SET:
        print(f"错误: 不支持的 region: {args.region}。可选值：SA/HK/AE/QA/KW/BR/BH", file=sys.stderr)
        if allowed_regions is not None:
            print(f"💡 当前账号可用区域总部权限 Region: {_format_region_list(allowed_regions)}", file=sys.stderr)
        sys.exit(1)

    if allowed_regions is not None and args.region not in allowed_regions:
        print(f"错误: 当前账号无 {args.region} 区域总部权限，无法执行标准数据集查询。", file=sys.stderr)
        print(f"💡 当前账号可用区域总部权限 Region: {_format_region_list(allowed_regions)}", file=sys.stderr)
        sys.exit(1)


# ── 客户端 ────────────────────────────────────────────────────────────────────

class MtcliStandardClient:
    """
    通过 `mtcli kdata standard *` 实现起源标准数据集查询。
    对外接口保持旧 standard client 形状，供 kdata.py 直接调用。
    """

    def list_region_hq_regions(self) -> list[str]:
        """列出当前账号具备区域总部权限的 Region。"""
        payload = _run(["kdata", "user", "whoami"], timeout=15)
        data = payload.get("data") if isinstance(payload, dict) else {}
        region_permissions = data.get("regionPermissions") if isinstance(data, dict) else []
        regions: list[str] = []
        for item in region_permissions or []:
            if not isinstance(item, dict) or item.get("regionHqAuth") is not True:
                continue
            region = _normalise_region_code(item.get("region"))
            if region and region not in regions:
                regions.append(region)
        return regions

    def list_datasets(self, locale=None, region=None) -> list:
        """列出当前账号可访问的所有数据集。region 参数 mtcli 暂不支持，已静默忽略。"""
        return _run(["kdata", "standard", "datasets"]).get("data") or []

    def list_measures(self, dataset_id, search=None, locale=None, region=None) -> list:
        """
        列出数据集的所有指标。
        region 暂不支持；search 在客户端按 name/code 过滤。
        """
        args = ["kdata", "standard", "measures", "--dataSetId", str(dataset_id)]
        if locale:
            args += ["--locale", locale]
        items = _run(args).get("data") or []
        if search:
            items = _rank_measure_search_results(items, search)
        return items

    def list_dimensions(self, dataset_id, search=None, locale=None, region=None) -> list:
        """
        列出数据集的所有维度。
        region 暂不支持；search 在客户端按 name/code 过滤。
        """
        items = _run(
            ["kdata", "standard", "dims-by-dataset", "--dataSetId", str(dataset_id)]
        ).get("data") or []
        if search:
            kw = search.lower()
            items = [
                d for d in items
                if kw in d.get("name", "").lower() or kw in d.get("code", "").lower()
            ]
        return items

    def list_dim_values(self, dim_code, dataset_id=None, search=None,
                        locale=None, region=None) -> list:
        """查询维度的可选值，search/keyword 传服务端过滤。"""
        args = ["kdata", "standard", "dim-values", "--dimCode", dim_code]
        if search:
            args += ["--keyword", search]
        raw = _run(args).get("data") or {}
        # API 返回 {"count": N, "data": [...]}
        return raw.get("data", []) if isinstance(raw, dict) else (
            raw if isinstance(raw, list) else []
        )

    def query(
        self,
        dataset_id,
        measures,
        date_range,
        region=None,
        filters=None,
        group_by=None,
        order_by=None,
        pops=None,
        page_size=1000,
        locale=None,
    ) -> dict:
        """
        查询起源数据集数据。
        返回格式：{"columns": [...], "rows": [...], "total": N}
        """
        _locale = locale or "zh"
        if not region:
            raise ValueError("region 必须指定（SA/HK/AE/QA/KW/BR/BH）")
        _validate_date_range(date_range)

        ext: dict[str, Any] = {"locale": _locale, "region": region}
        _sender_uid = os.environ.get("KDATA_SENDER_UID", "").strip()
        if _sender_uid:
            ext["groupAssistantId"] = "4061856271"
            ext["senderUid"] = _sender_uid

        body: dict[str, Any] = {
            "queryEngineSource": 2,
            "dataSourceId": str(dataset_id),
            "measureCodeList": measures,
            "dateFilters": [{"code": "dt", "values": [date_range]}],
            "pagination": {"pageNum": 1, "pageSize": page_size},
            "ext": ext,
        }
        if filters:
            body["filters"] = (
                [[{"code": k, "values": v if isinstance(v, list) else [v]}]
                 for k, v in filters.items()]
                if isinstance(filters, dict) else filters
            )
        if group_by:
            body["groupBy"] = group_by
        if order_by:
            body["orderBy"] = order_by
        if pops:
            body["pops"] = pops

        inner = _run(["kdata", "standard", "query"], body=body, timeout=60).get("data") or {}

        columns = _flatten_columns(inner.get("columnList", []))
        rows = [
            {
                col: (
                    item.get(col, {}).get("value", "")
                    if isinstance(item.get(col, {}), dict)
                    else str(item.get(col, ""))
                )
                for col in columns
            }
            for item in inner.get("dataList", [])
        ]

        return {
            "columns": columns,
            "rows": rows,
            "total": inner.get("pagination", {}).get("total", len(rows)),
        }


# ── CLI 命令处理 ───────────────────────────────────────────────────────────────

def _get_standard_client():
    return MtcliStandardClient()


def _print_table(result):
    columns = result["columns"]
    rows = result["rows"]
    if not rows:
        print("（无数据）")
        return
    widths = {c: len(c) for c in columns}
    for row in rows:
        for c in columns:
            widths[c] = max(widths[c], len(str(row.get(c, ""))))
    header = "  ".join(c.ljust(widths[c]) for c in columns)
    sep = "  ".join("-" * widths[c] for c in columns)
    print(header)
    print(sep)
    for row in rows:
        print("  ".join(str(row.get(c, "")).ljust(widths[c]) for c in columns))
    print(f"\n共 {result['total']} 条")


def _build_measure_apply_url(kpi_ids):
    """根据指标 kpiId 列表拼接起源平台权限申请链接。"""
    rc_list = ",".join(f"MTBI::KPI::{kid}" for kid in kpi_ids)
    rc_encoded = quote(rc_list, safe="")
    resource_code = quote("MTBI::BIZ::274", safe="")
    return (
        f"https://auth.keetapp.com/apply"
        f"?system=MTBI"
        f"&resourceCode={resource_code}"
        f"&viewType=selectOnly"
        f"&viewChildRC={rc_encoded}"
        f"&childRC={rc_encoded}"
    )


def _compact_locale_value_list(value):
    if not isinstance(value, list):
        return value
    locales = []
    compacted = {}
    for item in value:
        if not isinstance(item, dict) or set(item) != {"locale", "value"}:
            return value
        locale = item.get("locale")
        if not locale or locale in compacted:
            return value
        locales.append(locale)
        compacted[locale] = item.get("value")
    return {locale: compacted[locale] for locale in locales}


_CATEGORY_COLUMNS = ["classId", "className", "level", "children", "multiLanguageInfoList"]
_MEASURE_OUTPUT_DROP_FIELDS = {
    "url",
    "dimId",
    "indexType",
    "unit",
    "precision",
    "showFormula",
    "negative",
}


def _is_empty_output_value(value):
    return value is None or value == "" or value == [] or value == {}


def _compact_category_list(value):
    if not isinstance(value, list):
        return value
    expected_keys = set(_CATEGORY_COLUMNS)
    rows = []
    for item in value:
        if not isinstance(item, dict) or not set(item).issubset(expected_keys):
            return value
        row = [item.get(column) for column in _CATEGORY_COLUMNS]
        while row and _is_empty_output_value(row[-1]):
            row.pop()
        rows.append(row)
    return rows


def _compact_measure_for_output(measure):
    item = dict(measure)
    for key in _MEASURE_OUTPUT_DROP_FIELDS:
        item.pop(key, None)
    if "nameFieldList" in item:
        item["nameFieldList"] = _compact_locale_value_list(item["nameFieldList"])
    if "descFieldList" in item:
        item["descFieldList"] = _compact_locale_value_list(item["descFieldList"])
    if "categoryList" in item:
        item["categoryList"] = _compact_category_list(item["categoryList"])
    for key in list(item):
        if _is_empty_output_value(item[key]):
            item.pop(key, None)
    return item


def _compact_dim_for_output(dim):
    item = dict(dim)
    if "nameI18nList" in item:
        item["nameI18nList"] = _compact_locale_value_list(item["nameI18nList"])
    if "descI18nList" in item:
        item["descI18nList"] = _compact_locale_value_list(item["descI18nList"])
    for key in list(item):
        if item[key] is None:
            item.pop(key, None)
    return item


def _compact_dataset_for_output(dataset):
    item = dict(dataset)
    measure_codes = item.pop("measureCodeList", None)
    dim_codes = item.pop("dimCodeList", None)
    if isinstance(measure_codes, list):
        item["measureCount"] = len(measure_codes)
    elif measure_codes is not None:
        item["measureCodeList"] = measure_codes
    if isinstance(dim_codes, list):
        item["dimCount"] = len(dim_codes)
    elif dim_codes is not None:
        item["dimCodeList"] = dim_codes
    for key in list(item):
        if item[key] is None:
            item.pop(key, None)
    return item


def cmd_datasets(args):
    items = _get_standard_client().list_datasets(region=args.region)
    if args.json:
        if getattr(args, "full", False):
            print(json.dumps(items, ensure_ascii=False, indent=2))
        else:
            compacted = [_compact_dataset_for_output(d) for d in items]
            print(json.dumps(compacted, ensure_ascii=False, separators=(",", ":")))
    else:
        print(f"{'dataSetId':<12} {'dataSetName':<35} owner")
        print('-' * 80)
        for d in items:
            owners = ','.join(d.get('ownerList', []))
            print(f"{str(d.get('dataSetId','')):<12} {d.get('dataSetName',''):<35} {owners}")
        print(f"\n共 {len(items)} 个数据集")


def cmd_measures(args):
    items = _get_standard_client().list_measures(args.dataset, search=args.search, locale=args.locale, region=args.region)
    if args.json:
        compacted = [_compact_measure_for_output(m) for m in items]
        print(json.dumps(compacted, ensure_ascii=False, separators=(",", ":")))
    else:
        print(f"{'code':<45} {'type':<14} {'name':<30} {'auth':<6} desc")
        print('-' * 130)
        for m in items:
            auth = '✓' if m.get('hasAuth', False) else '✗'
            ftype = _get_fluctuation_type(m)
            print(f"{m.get('code',''):<45} {ftype:<14} {m.get('name',''):<30} {auth:<6} {m.get('desc','')}")
        no_auth_measures = [m for m in items if not m.get('hasAuth', False)]
        summary = f"\n共 {len(items)} 个指标"
        if no_auth_measures:
            summary += f"（其中 {len(no_auth_measures)} 个无权限）"
        print(summary)
        if no_auth_measures:
            kpi_ids = [m.get('kpiId') or m.get('id') for m in no_auth_measures if m.get('kpiId') or m.get('id')]
            if kpi_ids:
                print(f"\n💡 无权限指标可通过以下链接申请：\n{_build_measure_apply_url(kpi_ids)}")


def cmd_dims(args):
    items = _get_standard_client().list_dimensions(args.dataset, search=args.search, locale=args.locale, region=args.region)
    if args.json:
        compacted = [_compact_dim_for_output(d) for d in items]
        print(json.dumps(compacted, ensure_ascii=False, separators=(",", ":")))
    else:
        print(f"{'code':<35} {'name':<25} {'is_date':<8} desc")
        print('-' * 100)
        for d in items:
            print(f"{d.get('code',''):<35} {d.get('name',''):<25} {str(d.get('date',False)):<8} {d.get('desc','')[:50]}")
        print(f"\n共 {len(items)} 个维度")


def cmd_dim_values(args):
    items = _get_standard_client().list_dim_values(args.dim_code, search=args.search, region=args.region)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print(f"{'value':<30} label")
        print('-' * 60)
        for v in items:
            if isinstance(v, dict):
                print(f"{str(v.get('value','')):<30} {v.get('label','')}")
            else:
                print(str(v))
        print(f"\n共 {len(items)} 个维值")


def _split_code_args(values) -> list[str]:
    result = []
    for item in values or []:
        result.extend(v.strip() for v in str(item).split(','))
    return [v for v in result if v]


def _validate_operator_measures(option_name: str, selected: list[str], measures: list[str]) -> None:
    missing = [m for m in selected if m not in measures]
    if missing:
        print(
            f"错误: {option_name} 指定的指标不在 --measures 中: {', '.join(missing)}。"
            f"请先把这些指标加入 --measures，或移除对应算子参数。",
            file=sys.stderr,
        )
        sys.exit(1)


def cmd_query(args):
    try:
        _validate_date_range(args.date)
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    filters = {}
    if args.filter:
        for f in args.filter:
            if '=' not in f:
                print(f"错误: --filter 格式应为 key=value，收到: {f}", file=sys.stderr)
                sys.exit(1)
            k, v = f.split('=', 1)
            values = [item.strip() for item in v.split(',') if item.strip()]
            if not k.strip() or not values:
                print(f"错误: --filter 格式应为 key=value，收到: {f}", file=sys.stderr)
                sys.exit(1)
            _append_filter_values(filters, k.strip(), values)
    group_by = args.group_by.split(',') if args.group_by else None

    measures = _split_code_args(args.measures)
    user_pops = args.pops.split(',') if args.pops else []

    raw_gini_measures = _split_code_args(args.gini)
    if raw_gini_measures:
        if not group_by:
            print("错误: --gini 需要配合 --group-by 使用，用于计算分组波动贡献集中度", file=sys.stderr)
            sys.exit(1)
        _validate_operator_measures("--gini", raw_gini_measures, measures)
    gini_measures = raw_gini_measures

    fluctuation_measures = _split_code_args(args.fluctuation)
    fluctuation_pops = []
    if fluctuation_measures:
        _validate_operator_measures("--fluctuation", fluctuation_measures, measures)
    for m in gini_measures:
        if m not in fluctuation_measures:
            fluctuation_measures.append(m)
    if fluctuation_measures:
        if not user_pops:
            user_pops = [_infer_pop_from_date(args.date)]
        fluctuation_pops = list(user_pops)

    proportion_measures = _split_code_args(args.proportion)
    if proportion_measures:
        _validate_operator_measures("--proportion", proportion_measures, measures)

    pops = user_pops or None
    order_by = None
    if args.order_by:
        if '=' not in args.order_by:
            print(f"错误: --order-by 格式应为 field=ASC|DESC，收到: {args.order_by}", file=sys.stderr)
            sys.exit(1)
        k, v = args.order_by.split('=', 1)
        order_by = {k: v}

    client = _get_standard_client()
    _prepare_standard_query_region(args, client)

    all_measures = None
    try:
        all_measures = client.list_measures(args.dataset, locale=args.locale, region=args.region)
        measure_map = {m.get('code', ''): m for m in all_measures}
        missing_measures = [code for code in measures if code not in measure_map]
        if missing_measures:
            _exit_unknown_codes(
                "指标",
                args.dataset,
                missing_measures,
                all_measures,
                f"kdata standard measures --dataset {args.dataset} --search <指标关键词>",
            )
        no_auth = [measure_map[code] for code in measures if code in measure_map and not measure_map[code].get('hasAuth', False)]
        if no_auth:
            names = ", ".join(f"{m.get('name','')}({m.get('code','')})" for m in no_auth)
            print(f"⚠️  以下指标无权限，查询可能失败：{names}", file=sys.stderr)
            kpi_ids = [m.get('kpiId') or m.get('id') for m in no_auth if m.get('kpiId') or m.get('id')]
            if kpi_ids:
                print(f"💡 请通过以下链接申请指标权限：\n{_build_measure_apply_url(kpi_ids)}", file=sys.stderr)
    except Exception:
        pass

    requested_dims = []
    if group_by:
        requested_dims.extend(dim.strip() for dim in group_by if dim.strip())
    if filters:
        requested_dims.extend(filters.keys())
    if requested_dims:
        try:
            all_dims = client.list_dimensions(args.dataset, locale=args.locale, region=args.region)
            dim_map = {d.get('code', ''): d for d in all_dims}
            missing_dims = [
                code for code in requested_dims
                if code not in dim_map and code != "dt"
            ]
            if missing_dims:
                _exit_unknown_codes(
                    "维度",
                    args.dataset,
                    missing_dims,
                    all_dims,
                    f"kdata standard dims --dataset {args.dataset} --search <维度关键词>",
                )
        except SystemExit:
            raise
        except Exception:
            pass

    effective_page_size = args.page_size
    result = client.query(
        dataset_id=args.dataset,
        measures=measures,
        date_range=args.date,
        filters=filters or None,
        group_by=group_by,
        order_by=order_by,
        pops=pops,
        page_size=args.page_size,
        locale=args.locale,
        region=args.region,
    )

    if gini_measures:
        try:
            total_rows = int(result.get("total", len(result.get("rows") or [])))
        except (TypeError, ValueError):
            total_rows = len(result.get("rows") or [])
        if total_rows > len(result.get("rows") or []):
            effective_page_size = total_rows
            result = client.query(
                dataset_id=args.dataset,
                measures=measures,
                date_range=args.date,
                filters=filters or None,
                group_by=group_by,
                order_by=order_by,
                pops=pops,
                page_size=total_rows,
                locale=args.locale,
                region=args.region,
            )

    if proportion_measures:
        total_result = client.query(
            dataset_id=args.dataset,
            measures=proportion_measures,
            date_range=args.date,
            filters=filters or None,
            locale=args.locale,
            region=args.region,
        )
        total_row = total_result["rows"][0] if total_result["rows"] else {}
        result = calc_proportion(result, total_row, proportion_measures)

    if fluctuation_measures:
        components = {}
        if getattr(args, 'fluctuation_components', None):
            for item in args.fluctuation_components:
                ratio_code, pair = item.split('=', 1)
                num_code, den_code = pair.split('/', 1)
                components[ratio_code.strip()] = (num_code.strip(), den_code.strip())

        fluctuation_mode = getattr(args, 'fluctuation_mode', 'auto')

        measures_meta = None
        if fluctuation_mode == 'auto':
            try:
                measures_meta = client.list_measures(args.dataset, locale=args.locale, region=args.region)
                meta_map = {m.get('code'): m for m in measures_meta if m.get('code')}
                detected = 'additive'
                for code in fluctuation_measures:
                    if code in meta_map:
                        t = _get_fluctuation_type(meta_map[code])
                        if t in ('ratio', 'deduplicative'):
                            detected = t
                            break
                fluctuation_mode = detected
            except Exception:
                fluctuation_mode = 'additive'

        if fluctuation_mode == 'ratio' and not components:
            if measures_meta is None:
                measures_meta = client.list_measures(args.dataset, locale=args.locale, region=args.region)
            components = resolve_ratio_components(measures_meta, fluctuation_measures)
            if not components:
                print('警告: 无法自动解析比值型指标的分子/分母，请用 --fluctuation-components 手动指定', file=sys.stderr)

        ratio_extra = set()
        if fluctuation_mode == 'ratio':
            for m in fluctuation_measures:
                if m in components:
                    ratio_extra.update(components[m])
        extra_list = [m for m in ratio_extra if m not in measures]

        if extra_list:
            result = client.query(
                dataset_id=args.dataset,
                measures=measures + extra_list,
                date_range=args.date,
                filters=filters or None,
                group_by=group_by,
                order_by=order_by,
                pops=pops,
                page_size=effective_page_size,
                locale=args.locale,
                region=args.region,
            )

        for pop in fluctuation_pops:
            base_result = client.query(
                dataset_id=args.dataset,
                measures=fluctuation_measures + extra_list,
                date_range=_shift_date_range(args.date, pop),
                filters=filters or None,
                group_by=group_by,
                locale=args.locale,
                region=args.region,
            )
            _merge_base_period(result, base_result, fluctuation_measures + extra_list, pop, group_by)

        total_result = client.query(
            dataset_id=args.dataset,
            measures=fluctuation_measures + extra_list,
            date_range=args.date,
            filters=filters or None,
            locale=args.locale,
            region=args.region,
        )
        for pop in fluctuation_pops:
            total_base_result = client.query(
                dataset_id=args.dataset,
                measures=fluctuation_measures + extra_list,
                date_range=_shift_date_range(args.date, pop),
                filters=filters or None,
                locale=args.locale,
                region=args.region,
            )
            _merge_base_period(total_result, total_base_result, fluctuation_measures + extra_list, pop)

        result = calc_fluctuation(
            result, total_result, fluctuation_measures, fluctuation_pops,
            mode=fluctuation_mode,
            components=components or None,
        )
        if gini_measures:
            result = calc_gini(
                result,
                gini_measures,
                fluctuation_pops,
                mode=getattr(args, "gini_mode", "normalized"),
            )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_table(result)


def cmd_apply(args):
    """生成指定数据集指标的起源平台权限申请链接。"""
    measures = []
    for m in args.measures:
        measures.extend(m.split(','))
    measures = [m.strip() for m in measures if m.strip()]

    client = _get_standard_client()
    all_measures = client.list_measures(args.dataset, locale=getattr(args, "locale", "zh"))
    measure_map = {m.get('code', ''): m for m in all_measures}

    found, not_found = [], []
    for code in measures:
        if code in measure_map:
            found.append(measure_map[code])
        else:
            not_found.append(code)

    if not_found:
        print(f"⚠️  以下 code 在数据集 {args.dataset} 中未找到：{', '.join(not_found)}", file=sys.stderr)
        print("💡 可用 kdata standard measures --dataset <id> 查看全部指标 code", file=sys.stderr)

    if not found:
        print("❌ 没有找到任何有效指标，退出", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'code':<45} {'name':<30} {'当前权限':<8} kpiId")
    print('-' * 105)
    for m in found:
        auth_str = '✓ 已有' if m.get('hasAuth', False) else '✗ 无'
        kpi_id = str(m.get('kpiId') or m.get('id') or '-')
        print(f"{m.get('code',''):<45} {m.get('name',''):<30} {auth_str:<8} {kpi_id}")

    already_auth = [m for m in found if m.get('hasAuth', False)]
    if already_auth:
        names = "、".join(m.get('name') or m.get('code', '') for m in already_auth)
        print(f"\n✅ 已有权限（申请链接仍会包含，不影响使用）：{names}")

    kpi_ids = [m.get('kpiId') or m.get('id') for m in found if m.get('kpiId') or m.get('id')]
    if not kpi_ids:
        print("\n⚠️  所有指标均未返回 kpiId，无法生成申请链接", file=sys.stderr)
        sys.exit(1)

    url = _build_measure_apply_url(kpi_ids)
    print(f"\n🔗 权限申请链接（共 {len(found)} 个指标）：\n{url}\n")
