#!/usr/bin/env python3
"""DataMap lineage queries via mtcli."""

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


def _clean_name(value: str) -> str:
    return re.sub(r"\[<(.+?)>\]", r"\1", value or "")


def _unwrap_data(payload: dict[str, Any]) -> Any:
    node: Any = payload
    if isinstance(node, dict) and node.get("success") is True and "data" in node:
        node = node["data"]
    if isinstance(node, dict) and node.get("code", 0) not in (0, 200, None):
        raise RuntimeError(node.get("message") or node.get("msg") or node)
    return node.get("data", node) if isinstance(node, dict) else node


def _search_tables(table_name: str, page_size: int = 10) -> list[dict[str, Any]]:
    payload = _mtcli_run(
        ["kdata", "meta", "datamap-table-search"],
        params={"source": "datamap"},
        body={
            "q": table_name,
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
    data = _unwrap_data(payload)
    if isinstance(data, dict):
        page_data = data.get("pageData") if isinstance(data.get("pageData"), dict) else data
        items = page_data.get("list") or page_data.get("items") or []
        return items if isinstance(items, list) else []
    return data if isinstance(data, list) else []


def find_table_id(table_name: str) -> tuple[int, str]:
    tables = _search_tables(table_name)
    if not tables:
        raise RuntimeError(f"未找到表: {table_name}")

    needle = table_name.lower()
    exact = [
        item for item in tables
        if _clean_name(item.get("fullName") or item.get("tableName", "")).lower() == needle
        or item.get("tableName", "").lower() == needle
    ]
    chosen = exact[0] if exact else tables[0]
    table_id = chosen.get("id")
    if not table_id:
        raise RuntimeError(f"表缺少 DataMap id: {chosen}")
    comment = chosen.get("tableComment") or chosen.get("comment") or ""
    name = _clean_name(chosen.get("fullName") or chosen.get("tableName") or table_name)
    if len(tables) > 1 and not exact:
        print(f"  ⚠️  共 {len(tables)} 个匹配，使用: [{table_id}] {name}  (用 --table-id 指定精确 ID)")
    return int(table_id), comment


def get_lineage(table_id: int, upstream: bool = True, downstream: bool = True) -> dict[str, Any]:
    payload = _mtcli_run(
        ["kdata", "meta", "datamap-lineage"],
        params={
            "downstream": "1" if downstream else "0",
            "id": str(table_id),
            "includeApp": "true",
            "lineageType": "ALL",
            "type": "table",
            "upstream": "1" if upstream else "0",
        },
        timeout=30,
    )
    data = _unwrap_data(payload)
    return data if isinstance(data, dict) else {}


def get_columns(table_id: int) -> list[dict[str, Any]]:
    payload = _mtcli_run(
        ["kdata", "meta", "datamap-table-columns"],
        params={"id": str(table_id)},
        timeout=30,
    )
    data = _unwrap_data(payload)
    return data if isinstance(data, list) else []


def get_column_lineage(column_id: int, upstream: int = 5, downstream: int = 5) -> dict[str, Any]:
    payload = _mtcli_run(
        ["kdata", "meta", "datamap-lineage"],
        params={
            "downstream": str(downstream),
            "id": str(column_id),
            "includeApp": "false",
            "lineageType": "ALL",
            "type": "column",
            "upstream": str(upstream),
        },
        timeout=30,
    )
    data = _unwrap_data(payload)
    return data if isinstance(data, dict) else {}


def fmt_table(table: dict[str, Any]) -> str:
    uri = table.get("uri", "")
    name = uri.split(".")[-1] if uri else table.get("tableName", "?")
    desc = table.get("description") or table.get("tableComment") or ""
    table_id = table.get("id", "?")
    hierarchy = table.get("hierarchy", 1)
    return f"  [id={table_id}] {name:<50}  层级={hierarchy}  {desc}"


def _run_with_args(args: argparse.Namespace) -> None:
    table_id = getattr(args, "table_id", None)
    if not table_id:
        table_name = getattr(args, "table", None)
        if not table_name:
            print("错误：需要提供 --table 或 --table-id", file=sys.stderr)
            raise SystemExit(1)
        table_id, comment = find_table_id(table_name)
        print(f"表名解析：{comment}（tableId={table_id}）", file=sys.stderr)

    if getattr(args, "columns", False):
        print(json.dumps(get_columns(table_id), ensure_ascii=False, indent=2))
        return

    if getattr(args, "column", None):
        col_name = args.column
        cols = get_columns(table_id)
        match = next(
            (col for col in cols if (col.get("columnName") or col.get("name")) == col_name),
            None,
        )
        if not match:
            print(f"字段 {col_name} 未找到，可用字段：{[(c.get('columnName') or c.get('name')) for c in cols[:10]]}", file=sys.stderr)
            raise SystemExit(1)
        print(json.dumps(get_column_lineage(match["id"]), ensure_ascii=False, indent=2))
        return

    upstream = not getattr(args, "downstream_only", False)
    downstream = not getattr(args, "upstream_only", False)
    data = get_lineage(table_id, upstream=upstream, downstream=downstream)

    if getattr(args, "json", False) or getattr(args, "as_json", False):
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if upstream:
        upstream_tables = data.get("upstream", [])
        print(f"\n⬆️  上游表（{len(upstream_tables)} 张）：")
        for table in sorted(upstream_tables, key=lambda x: x.get("hierarchy", 0)):
            print(fmt_table(table))

    if downstream:
        downstream_tables = data.get("downstream", [])
        print(f"\n⬇️  下游表（共 {len(downstream_tables)} 张，显示前 50）：")
        for table in sorted(downstream_tables, key=lambda x: x.get("hierarchy", 0))[:50]:
            print(fmt_table(table))
        if len(downstream_tables) > 50:
            print(f"  ... 用 --json 查看全部 {len(downstream_tables)} 张")

    apps = data.get("downstreamApp", [])
    if apps:
        print(f"\n📊 下游应用（{len(apps)} 个）：")
        for app in apps[:10]:
            print(f"  {app.get('name', '?')}  {app.get('type', '')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="DataMap 血缘查询（mtcli）")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--table")
    group.add_argument("--table-id", type=int, dest="table_id")
    parser.add_argument("--upstream-only", action="store_true")
    parser.add_argument("--downstream-only", action="store_true")
    parser.add_argument("--columns", action="store_true")
    parser.add_argument("--column")
    parser.add_argument("--json", dest="as_json", action="store_true")
    _run_with_args(parser.parse_args())


def run(args: argparse.Namespace) -> None:
    _run_with_args(args)


if __name__ == "__main__":
    main()
