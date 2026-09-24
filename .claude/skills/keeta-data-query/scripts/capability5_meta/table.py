#!/usr/bin/env python3
"""Keeta DataMap table search via mtcli."""

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

try:
    from core.mtcli import run as _mtcli_run
except ImportError:
    from mtcli import run as _mtcli_run

try:
    from capability5_meta.table_filters import is_unusable_table_item
except ImportError:
    from table_filters import is_unusable_table_item


def _clean_name(value: str) -> str:
    return re.sub(r"\[<(.+?)>\]", r"\1", value or "")


def _unwrap_data(payload: dict[str, Any]) -> Any:
    node: Any = payload
    if isinstance(node, dict) and node.get("success") is True and "data" in node:
        node = node["data"]
    if isinstance(node, dict) and node.get("code", 0) not in (0, 200, None):
        raise RuntimeError(node.get("message") or node.get("msg") or node)
    return node.get("data", node) if isinstance(node, dict) else node


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = _unwrap_data(payload)
    if isinstance(data, dict):
        page_data = data.get("pageData") if isinstance(data.get("pageData"), dict) else data
        items = page_data.get("list") or page_data.get("items") or []
        return items if isinstance(items, list) else []
    return data if isinstance(data, list) else []


def parse_columns(raw_cols: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for col in raw_cols or []:
        name = _clean_name(col.get("columnName") or col.get("name", ""))
        result.append({
            "id": col.get("id"),
            "name": name,
            "type": col.get("columnType") or col.get("type", ""),
            "comment": col.get("columnComment") or col.get("comment") or col.get("shortColumnComment", ""),
            "is_partition": bool(col.get("isPartitionColumn")),
            "is_important": bool(col.get("isImportant", col.get("primary", False))),
            "heat": col.get("heat", 0),
            "security": col.get("securityLevel", 0),
        })
    result.sort(key=lambda x: (x["is_partition"], not x["is_important"], x["name"]))
    return result


def _owner_text(owner_raw: Any) -> str:
    owners = []
    for owner in owner_raw or []:
        if isinstance(owner, str):
            owners.append(owner)
        elif isinstance(owner, dict):
            owners.append(owner.get("mis") or owner.get("name") or "")
    return ", ".join(owner for owner in owners if owner)


def enrich_table(item: dict[str, Any]) -> dict[str, Any]:
    columns = parse_columns(item.get("columns") or item.get("columnList") or [])
    partitions = [col["name"] for col in columns if col.get("is_partition")]
    name = _clean_name(item.get("fullName") or item.get("tableName") or item.get("name", ""))
    return {
        "id": item.get("id"),
        "name": name,
        "dsn": item.get("dsnName") or item.get("dsn", ""),
        "comment": item.get("tableComment") or item.get("comment", ""),
        "permission": None,
        "owner": _owner_text(item.get("ownerList")) or item.get("owner", ""),
        "heat": item.get("heat", 0),
        "layer": item.get("layer", ""),
        "security": item.get("securityLevel", 0),
        "columns": columns,
        "partitions": partitions,
        "_source": "mtcli:datamap-table-search",
    }


def _datamap_search(keyword: str, page_size: int = 40) -> list[dict[str, Any]]:
    payload = _mtcli_run(
        ["kdata", "meta", "datamap-table-search"],
        params={"source": "datamap"},
        body={
            "q": keyword,
            "filters": {
                "categoryIdList": [],
                "engineTypeList": [],
                "bizProcessIdList": [],
                "layerList": [],
                "tagIdList": [],
                "isLatestModel": False,
            },
            "pageNum": 1,
            "pageSize": page_size,
        },
        timeout=30,
    )
    return [
        enrich_table(item)
        for item in _extract_items(payload)
        if not is_unusable_table_item(item)
    ]


def search_tables(q: str, page_size: int = 10, include_columns: bool = True) -> list[dict[str, Any]]:
    """Search DataMap tables through mtcli."""
    if os.environ.get("KDATA_DISABLE_MTCLI_META", "").strip() == "1":
        raise RuntimeError("mtcli meta disabled by KDATA_DISABLE_MTCLI_META")
    results = _datamap_search(q, page_size=page_size)
    if include_columns:
        return results
    compact = []
    for item in results:
        slim = dict(item)
        slim.pop("columns", None)
        slim.pop("partitions", None)
        compact.append(slim)
    return compact


def get_table_info(table_name: str) -> dict | None:
    """Return a single table's detail, preferring exact name matches."""
    results = search_tables(table_name, page_size=5, include_columns=True)
    if not results:
        return None
    for item in results:
        if item.get("name", "").lower() == table_name.lower():
            return item
    return results[0]


def filter_tables(items: list[dict[str, Any]], schema_filter: str = "mart_sailor_global") -> list[dict[str, Any]]:
    if not schema_filter:
        return items
    blocked = ("test", "backup", "tmp", "temp", "swordedge")
    result = []
    for item in items:
        if is_unusable_table_item(item):
            continue
        name = item.get("name", "")
        if schema_filter in name and not any(token in name.lower() for token in blocked):
            result.append(item)
    return result


def search_multi(
    keywords: list[str],
    page_size: int = 40,
    schema_filter: str = "mart_sailor_global",
    force_refresh_cookie: bool = False,
) -> list[dict[str, Any]]:
    del force_refresh_cookie
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for keyword in keywords:
        for table in _datamap_search(keyword, page_size=page_size):
            name = table.get("name", "")
            if not name or name in seen:
                continue
            seen.add(name)
            results.append(table)
    return filter_tables(results, schema_filter) if schema_filter else results


def search_multi_enriched(
    keywords: list[str],
    page_size: int = 40,
    schema_filter: str = "mart_sailor_global",
    force_refresh_cookie: bool = False,
    enrich: bool = True,
) -> list[dict[str, Any]]:
    del enrich
    return sorted(
        search_multi(keywords, page_size, schema_filter, force_refresh_cookie),
        key=lambda item: -(item.get("heat") or 0),
    )


def _print_items(items: list[dict[str, Any]], keywords: list[str]) -> None:
    if not items:
        print(f"未找到相关表（关键词: {', '.join(keywords)}）")
        return

    print(f"找到 {len(items)} 张相关表：\n")
    for table in items:
        heat = f"🔥{table['heat']}" if table.get("heat") else ""
        layer = f"[{table['layer']}]" if table.get("layer") else ""
        owner = f"负责人: {table['owner']}" if table.get("owner") else ""
        print(f"— {table['name']} {layer} {heat}")
        if table.get("comment"):
            print(f"   {table['comment']}")
        if owner:
            print(f"   {owner}")

        important_cols = [c for c in table.get("columns", []) if c.get("is_important")][:5]
        other_cols = [
            c for c in table.get("columns", [])
            if not c.get("is_important") and not c.get("is_partition")
        ][:3]
        partition_cols = [c for c in table.get("columns", []) if c.get("is_partition")]

        if important_cols:
            print("   重要字段: " + " | ".join(
                f"★{c['name']}({c.get('comment', '')[:20]})" for c in important_cols
            ))
        if other_cols:
            print("   其他字段: " + " | ".join(
                f"{c['name']}({c.get('comment', '')[:20]})" for c in other_cols
            ))
        if partition_cols:
            print(f"   分区字段: {', '.join(c['name'] for c in partition_cols)}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Keeta DataMap 关键词找表（mtcli）")
    parser.add_argument("keywords", nargs="+")
    parser.add_argument("--page-size", type=int, default=40)
    parser.add_argument("--schema", default="mart_sailor_global")
    parser.add_argument("--no-filter", action="store_true")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--refresh-cookie", action="store_true")
    parser.add_argument("--no-enrich", action="store_true")
    args = parser.parse_args()
    run(args)


def run(args: argparse.Namespace) -> None:
    items = search_multi_enriched(
        keywords=args.keywords,
        page_size=args.page_size,
        schema_filter=None if args.no_filter else args.schema,
        force_refresh_cookie=getattr(args, "refresh_cookie", False),
        enrich=not getattr(args, "no_enrich", False),
    )
    if not args.no_filter:
        items = filter_tables(items, args.schema)

    if args.format == "json":
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return

    _print_items(items, args.keywords)


if __name__ == "__main__":
    main()
