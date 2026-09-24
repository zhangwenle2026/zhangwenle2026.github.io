#!/usr/bin/env python3
"""Standalone BI helper for OpenClaw keeta-bi skill."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

# ── 路径注入：兼容包导入和直接执行 ──────────────────────────
_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_CORE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "core"))
for _path in (_SCRIPTS_DIR, _CORE_DIR, os.path.abspath(os.path.dirname(__file__))):
    if _path not in sys.path:
        sys.path.insert(0, _path)

try:
    from capability2_hive.hive_client import (
        BI_BASE,
        STATUS_RUNNING,
        STATUS_SUCCESS,
        STATUS_DONE,
        BiClient,
        _normalize_project_name,
        _resolve_sql_text,
    )
except ImportError:
    from hive_client import (
        BI_BASE,
        STATUS_RUNNING,
        STATUS_SUCCESS,
        STATUS_DONE,
        BiClient,
        _normalize_project_name,
        _resolve_sql_text,
    )


# ── 输出工具 ───────────────────────────────────────────────

def _print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        print("No rows.")
        return

    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    header_line = " | ".join(headers[idx].ljust(widths[idx]) for idx in range(len(headers)))
    sep_line = "-+-".join("-" * widths[idx] for idx in range(len(headers)))
    print(header_line)
    print(sep_line)
    for row in rows:
        print(" | ".join(row[idx].ljust(widths[idx]) for idx in range(len(headers))))


# ── 业务逻辑 ───────────────────────────────────────────────

def _raise_if_error(result: dict[str, Any], action: str) -> None:
    if result.get("error"):
        raise RuntimeError(f"{action}失败: {result['error']}")
    if result.get("code", 0) != 0:
        message = result.get("message") or result.get("msg") or result.get("errorMessage") or ""
        if message:
            raise RuntimeError(f"{action}失败(code={result.get('code')}): {message}")
        raise RuntimeError(f"{action}失败: {result}")


def _make_client(project_ref: str, base_url: str) -> BiClient:
    client = BiClient(project_id="0", base_url=base_url)
    client.project_id = client.resolve_project_id(project_ref)
    return client


def _ensure_queue(engine: str, queue: str | None) -> None:
    if engine.lower() != "doris" and not queue:
        raise RuntimeError("Hive/OneSQL/Presto/MySQL 查询需要指定 --queue")


def cmd_spaces(args: argparse.Namespace) -> int:
    client = BiClient(project_id="0", base_url=args.base_url)
    result = client.get_spaces()
    _raise_if_error(result, "获取工作空间")

    data = result.get("data", [])
    if args.json_output:
        _print_json(data)
        return 0

    rows: list[list[str]] = []
    for group in data:
        children = group.get("children", [])
        if children:
            for proj in children:
                rows.append(
                    [
                        str(proj.get("id", "")),
                        str(proj.get("name", "")),
                        "项目组空间",
                        str(proj.get("description", "")),
                        str(proj.get("admin", "")),
                    ]
                )
        else:
            rows.append(
                [
                    str(group.get("id", "")),
                    str(group.get("name", "")),
                    "个人空间",
                    "",
                    "",
                ]
            )

    _print_table(["ID", "名称", "类型", "描述", "管理员"], rows)
    return 0


def cmd_queues(args: argparse.Namespace) -> int:
    client = BiClient(project_id="0", base_url=args.base_url)
    result = client.get_queues()
    _raise_if_error(result, "获取队列")

    data = result.get("data", [])
    if args.json_output:
        _print_json(data)
        return 0

    rows = [
        [
            str(item.get("name", "")),
            str(item.get("vcoresQuota", "")),
            str(item.get("vcoresUsedNum", "")),
            str(item.get("vcoresPendingNum", "")),
        ]
        for item in data
    ]
    _print_table(["队列名称", "配额(vCores)", "已用", "排队中"], rows)
    return 0


def cmd_datasources(args: argparse.Namespace) -> int:
    client = _make_client(args.project, args.base_url)
    result = client.get_datasources()
    _raise_if_error(result, "获取数据源")

    data = result.get("data", {})
    if args.json_output:
        _print_json(data)
        return 0

    rows: list[list[str]] = []
    for engine_name, sources in data.items():
        for source in sources:
            rows.append(
                [
                    str(engine_name),
                    str(source.get("name", "")),
                    str(source.get("statDs", "")),
                    str(source.get("displayName", "")),
                    "Y" if source.get("permission") else "N",
                ]
            )
    _print_table(["引擎", "数据源名称(dsn)", "连接标识(statDs)", "显示名称", "权限"], rows)
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    _ensure_queue(args.engine, args.queue)
    sql = _resolve_sql_text(args.sql_or_file)
    client = _make_client(args.project, args.base_url)
    result = client.submit_sql(
        sql=sql,
        spark_queue=args.queue,
        engine=args.engine,
        ds_name=args.ds_name,
        stat_ds=args.stat_ds,
        resource_name=args.resource_name,
        resource_owner=args.resource_owner,
        entrance=args.entrance,
        filter_relation_type=args.filter_relation_type,
        filter_type=args.filter_type,
    )

    if args.json_output:
        _print_json(result)
    _raise_if_error(result, "提交 SQL")

    if args.json_output:
        return 0

    query_id = (result.get("data") or {}).get("queryId")
    print(f"提交成功 queryId={query_id}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    client = _make_client(args.project, args.base_url)
    result = client.get_status(args.query_id)
    if args.json_output:
        _print_json(result)
        _raise_if_error(result, "查询状态")
        return 0
    _raise_if_error(result, "查询状态")

    data = result.get("data") or {}
    status_code = data.get("status")
    status_labels = {
        STATUS_RUNNING: "运行中",
        STATUS_SUCCESS: "成功完成",
        STATUS_DONE: "已完成",
    }
    label = status_labels.get(status_code, f"失败(code={status_code})")
    print(f"queryId={args.query_id} 状态={label}")
    if data.get("problem"):
        print(f"错误信息: {data.get('problem')}")
    return 0


def cmd_result(args: argparse.Namespace) -> int:
    client = _make_client(args.project, args.base_url)
    result = client.get_result(args.query_id, limit=args.limit)
    if args.json_output:
        _print_json(result)
        _raise_if_error(result, "获取结果")
        return 0
    _raise_if_error(result, "获取结果")

    data = result.get("data") or {}
    columns = [str(col) for col in data.get("columns", [])]
    rows = data.get("data", [])
    total = data.get("totalNum", 0)

    print(f"总行数={total} 返回={len(rows)}")
    if columns and rows:
        table_rows = [[str(v) if v is not None else "" for v in row] for row in rows]
        _print_table(columns, table_rows)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    _ensure_queue(args.engine, args.queue)
    sql = _resolve_sql_text(args.sql_or_file)
    client = _make_client(args.project, args.base_url)
    result = client.run_sql(
        sql=sql,
        spark_queue=args.queue,
        engine=args.engine,
        ds_name=args.ds_name,
        stat_ds=args.stat_ds,
        resource_name=args.resource_name,
        resource_owner=args.resource_owner,
        entrance=args.entrance,
        filter_relation_type=args.filter_relation_type,
        filter_type=args.filter_type,
        limit=args.limit,
        poll_interval=args.poll_interval,
        timeout=args.timeout,
    )

    if args.json_output:
        _print_json(result)
        return 0 if result.get("success") else 1

    if not result.get("success"):
        error = result.get("error", "unknown")
        message = result.get("message", "")
        detail = result.get("detail")
        apply_links = result.get("apply_links") or []

        if error == "not_sql_input":
            raise RuntimeError(f"执行失败: {error}\n{message}")

        if error in ("ddl_dml_blocked", "meta_sql_blocked"):
            raise RuntimeError(f"{message}")

        if error == "submit_no_permission":
            # 权限不足：输出申请链接（若有）+ 引导提示
            if apply_links:
                lines = ["无表权限，可申请以下表的访问权限（个人空间，建议申请 6 个月有效期，并选择所需 region）："]
                for item in apply_links:
                    lines.append(f"  - {item['db']}.{item['table']}")
                    lines.append(f"    申请链接：{item['url']}")
                print("\n".join(lines), file=sys.stderr)
            hint = (
                "\n\n💡 权限不足，建议：\n"
                "  1. 执行 `kdata hive spaces` 获取可用项目空间\n"
                "  2. 用 `--project <项目空间ID>` 重新执行\n"
                "  3. 或前往权限平台申请表权限"
            )
            raise RuntimeError(f"执行失败: {error}\n{message}{hint}")

        if error == "submit_failed":
            raise RuntimeError(f"执行失败: {error}\n{message or error}")

        if error == "analyze_failed":
            msg = message or error
            remediation = ""
            if detail:
                _data = detail.get("data") or {}
                _diag = _data.get("sqlDiagnoseInfo") or _data.get("sqlErrorInfo") or {}
                _detail_msg = _diag.get("detailMessage", "")
                _solution = _diag.get("solution", "")
                _error_type = _diag.get("type", "") or _diag.get("errorType", "")
                if _detail_msg:
                    msg = f"{msg}\n详细: {_detail_msg}"
                if _solution:
                    msg += f"\n平台建议: {_solution}"

                # 根据错误模式生成可操作的修复建议
                _combined = f"{msg} {_detail_msg}".lower()
                if any(kw in _combined for kw in ("table not found", "table or view not found",
                                                   "不存在", "does not exist", "cannot be resolved",
                                                   "tablenotfoundexception", "nosuchobject")):
                    # 提取可能的表名用于建议
                    import re
                    _tables = re.findall(r'`?(\w+\.\w+)`?', _detail_msg or msg)
                    if _tables:
                        _tbl = _tables[0]
                        remediation = (
                            f"\n\n🔧 修复建议:\n"
                            f"  1. 表 `{_tbl}` 可能不存在或已下线\n"
                            f"  2. 执行 `kdata table search {_tbl.split('.')[-1]}` 确认表名\n"
                            f"  3. 执行 `kdata meta table bi {_tbl.split('.')[-1]}` 搜索相关表\n"
                            f"  4. 确认正确表名后用 `kdata table info <schema.table>` 验证字段"
                        )
                    else:
                        remediation = (
                            "\n\n🔧 修复建议:\n"
                            "  1. SQL 中引用的表可能不存在或已下线\n"
                            "  2. 执行 `kdata meta table bi <关键词>` 搜索正确表名\n"
                            "  3. 确认正确表名后用 `kdata table info <schema.table>` 验证字段"
                        )
                elif any(kw in _combined for kw in ("column", "field", "cannot be resolved to",
                                                     "字段", "列名", "invalid reference")):
                    import re
                    _tables = re.findall(r'`?(\w+\.\w+)`?', _detail_msg or msg)
                    _tbl_hint = _tables[0] if _tables else "<表名>"
                    remediation = (
                        f"\n\n🔧 修复建议:\n"
                        f"  1. SQL 中引用了不存在的字段\n"
                        f"  2. 执行 `kdata table info {_tbl_hint}` 查看该表所有字段\n"
                        f"  3. 根据返回的字段列表修正 SQL 中的列名"
                    )
                elif any(kw in _combined for kw in ("syntax error", "parse error", "语法",
                                                     "unexpected", "mismatched input")):
                    remediation = (
                        "\n\n🔧 修复建议:\n"
                        "  1. SQL 存在语法错误，请检查 SQL 关键字、括号匹配、逗号等\n"
                        "  2. 注意 Hive SQL 语法差异：不支持 LIMIT offset 写法，用子查询替代\n"
                        "  3. 字符串用单引号，表/列名用反引号"
                    )
                elif any(kw in _combined for kw in ("schema", "database", "namespace")):
                    remediation = (
                        "\n\n🔧 修复建议:\n"
                        "  1. Schema/数据库名可能不正确\n"
                        "  2. Keeta 数仓主要使用 `mart_sailor_global`、`mart_sailor_finance_global`\n"
                        "  3. 执行 `kdata hive spaces` 确认可用工作空间\n"
                        "  4. 尝试 `--project <空间ID>` 切换项目空间"
                    )
                else:
                    remediation = (
                        "\n\n🔧 修复建议:\n"
                        "  1. 执行 `kdata table info <schema.table>` 确认表和字段存在\n"
                        "  2. 检查 SQL 语法是否符合 Hive/OneSQL 规范\n"
                        "  3. 如果是权限问题，尝试 `kdata hive spaces` + `--project <ID>`"
                    )

            raise RuntimeError(f"SQL 语法检查失败 (analyze_failed)\n{msg}{remediation}")

        if detail:
            _print_json(detail)
        raise RuntimeError(f"执行失败: {error}")

    print(
        "查询成功 queryId={query_id} 总行数={total} 返回={returned}".format(
            query_id=result.get("query_id"),
            total=result.get("total_num", 0),
            returned=len(result.get("data", [])),
        )
    )
    columns = [str(col) for col in result.get("columns", [])]
    rows = result.get("data", [])
    if columns and rows:
        table_rows = [[str(v) if v is not None else "" for v in row] for row in rows]
        _print_table(columns, table_rows)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"OpenClaw standalone BI tool (default: {BI_BASE})"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    spaces_parser = subparsers.add_parser("spaces", help="List personal/project spaces")
    spaces_parser.add_argument("--base-url", default=BI_BASE, help="BI base URL")
    spaces_parser.add_argument("--json", dest="json_output", action="store_true", help="Output JSON")
    spaces_parser.set_defaults(func=cmd_spaces)

    queues_parser = subparsers.add_parser("queues", help="List available queues")
    queues_parser.add_argument("--base-url", default=BI_BASE, help="BI base URL")
    queues_parser.add_argument("--json", dest="json_output", action="store_true", help="Output JSON")
    queues_parser.set_defaults(func=cmd_queues)

    datasources_parser = subparsers.add_parser("datasources", help="List datasource metadata")
    datasources_parser.add_argument("--project", "-p", default="0", help="Project ID or name (0=personal)")
    datasources_parser.add_argument("--base-url", default=BI_BASE, help="BI base URL")
    datasources_parser.add_argument("--json", dest="json_output", action="store_true", help="Output JSON")
    datasources_parser.set_defaults(func=cmd_datasources)

    submit_parser = subparsers.add_parser("submit", help="Submit SQL only")
    submit_parser.add_argument("sql_or_file", help="SQL text or .sql file path")
    submit_parser.add_argument("--project", "-p", default="0", help="Project ID or name")
    submit_parser.add_argument("--queue", "-q", default=None, help="Spark queue (required for non-doris)")
    submit_parser.add_argument("--engine", "-e", default="onesql", help="Engine: onesql/hive/presto/doris/mysql")
    submit_parser.add_argument("--ds", dest="ds_name", default="dw_hive", help="Datasource name")
    submit_parser.add_argument("--stat-ds", dest="stat_ds", default="DW_ONESQL_DB_CONNECT_URL", help="Datasource stat key")
    submit_parser.add_argument("--resource-name", default="新查询", help="Resource name")
    submit_parser.add_argument("--resource-owner", default="", help="Resource owner")
    submit_parser.add_argument("--entrance", action="append", default=None, help="Entrance key (repeatable)")
    submit_parser.add_argument("--filter-relation", dest="filter_relation_type", default="AND", help="Filter relation type")
    submit_parser.add_argument("--filter-type", default="EQ", help="Filter type")
    submit_parser.add_argument("--base-url", default=BI_BASE, help="BI base URL")
    submit_parser.add_argument("--json", dest="json_output", action="store_true", help="Output JSON")
    submit_parser.add_argument("--as", dest="run_as", default="", help="以指定用户身份执行（mis）")
    submit_parser.set_defaults(func=cmd_submit)

    status_parser = subparsers.add_parser("status", help="Query status by query_id")
    status_parser.add_argument("query_id", type=int, help="Query ID")
    status_parser.add_argument("--project", "-p", default="0", help="Project ID or name")
    status_parser.add_argument("--base-url", default=BI_BASE, help="BI base URL")
    status_parser.add_argument("--json", dest="json_output", action="store_true", help="Output JSON")
    status_parser.set_defaults(func=cmd_status)

    result_parser = subparsers.add_parser("result", help="Fetch result by query_id")
    result_parser.add_argument("query_id", type=int, help="Query ID")
    result_parser.add_argument("--project", "-p", default="0", help="Project ID or name")
    result_parser.add_argument("--limit", "-n", type=int, default=200, help="Row limit")
    result_parser.add_argument("--base-url", default=BI_BASE, help="BI base URL")
    result_parser.add_argument("--json", dest="json_output", action="store_true", help="Output JSON")
    result_parser.set_defaults(func=cmd_result)

    run_parser = subparsers.add_parser("run", help="Analyze + submit + poll + fetch")
    run_parser.add_argument("sql_or_file", help="SQL text or .sql file path")
    run_parser.add_argument("--project", "-p", default="0", help="Project ID or name")
    run_parser.add_argument("--queue", "-q", default=None, help="Spark queue (required for non-doris)")
    run_parser.add_argument("--engine", "-e", default="onesql", help="Engine: onesql/hive/presto/doris/mysql")
    run_parser.add_argument("--ds", dest="ds_name", default="dw_hive", help="Datasource name")
    run_parser.add_argument("--stat-ds", dest="stat_ds", default="DW_ONESQL_DB_CONNECT_URL", help="Datasource stat key")
    run_parser.add_argument("--resource-name", default="新查询", help="Resource name")
    run_parser.add_argument("--resource-owner", default="", help="Resource owner")
    run_parser.add_argument("--entrance", action="append", default=None, help="Entrance key (repeatable)")
    run_parser.add_argument("--filter-relation", dest="filter_relation_type", default="AND", help="Filter relation type")
    run_parser.add_argument("--filter-type", default="EQ", help="Filter type")
    run_parser.add_argument("--limit", "-n", type=int, default=200, help="Row limit for result")
    run_parser.add_argument("--timeout", "-t", type=float, default=180.0, help="Polling timeout seconds")
    run_parser.add_argument("--poll-interval", type=float, default=3.0, help="Polling interval seconds")
    run_parser.add_argument("--base-url", default=BI_BASE, help="BI base URL")
    run_parser.add_argument("--json", dest="json_output", action="store_true", help="Output JSON")
    run_parser.add_argument("--as", dest="run_as", default="", help="以指定用户身份执行（mis）")
    run_parser.set_defaults(func=cmd_run)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        return int(args.func(args))
    except RuntimeError as exc:
        print(f"[keeta_bi_skill] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[keeta_bi_skill] unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
