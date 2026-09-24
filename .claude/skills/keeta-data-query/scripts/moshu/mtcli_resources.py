#!/usr/bin/env python3
"""Moshu dataset and SQL template metadata via mtcli kdata moshu commands."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any

try:
    from core.mtcli import run as _mtcli_run
except ImportError:
    from mtcli import run as _mtcli_run


BI_BASE = "https://bi.keetapp.com"


def _decode_payload(payload: dict[str, Any]) -> dict[str, Any]:
    body = payload.get("body")
    if isinstance(body, str):
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"mtcli moshu body 不是合法 JSON: {body[:200]}") from exc
        if isinstance(parsed, dict):
            return parsed
    return payload


def _checked(payload: dict[str, Any]) -> dict[str, Any]:
    data = _decode_payload(payload)
    code = data.get("code")
    if code not in (None, 0):
        raise RuntimeError(f"mtcli moshu 返回错误 code={code}: {data.get('message') or data}")
    return data


def get_dataset_list(page_num: int = 1, page_size: int = 50, query: str = "") -> list[dict[str, Any]]:
    payload = {
        "listType": "ALL",
        "resourceType": "NONSTANDARDDATASET",
        "query": {"queryStr": query, "favoriteFolderId": -1},
        "sortInfo": {},
        "pageInfo": {"pageNumber": page_num, "pageSize": page_size},
    }
    result = _checked(_mtcli_run(["kdata", "moshu", "dataset-list"], body=payload, timeout=30))
    data = result.get("data") or {}
    if isinstance(data, dict):
        return data.get("resourceList") or []
    return data if isinstance(data, list) else []


def get_dataset_info(subject_ids: list[int]) -> list[dict[str, Any]]:
    result = _checked(
        _mtcli_run(
            ["kdata", "moshu", "dataset-info"],
            body={"subjectIdList": subject_ids},
            timeout=30,
        )
    )
    data = result.get("data") or []
    return data if isinstance(data, list) else [data]


def get_template_list(
    q: str = "",
    managed: bool = False,
    shared: bool = False,
    project_id: str = "",
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"q": q, "managed": managed, "shared": shared}
    if project_id:
        params["projectId"] = project_id
    result = _checked(_mtcli_run(["kdata", "moshu", "template-list"], params=params, timeout=30))
    data = result.get("data") or {}
    folders = data.get("folders") if isinstance(data, dict) else []
    templates: list[dict[str, Any]] = []
    for folder in folders or []:
        for resource in folder.get("resources") or []:
            item = dict(resource)
            item["_folderName"] = folder.get("folderName", "")
            item["_folderId"] = folder.get("folderId", "")
            templates.append(item)
    return templates


def get_template_detail(template_id: str | int, ver_no: str | int = "1") -> dict[str, Any]:
    result = _checked(
        _mtcli_run(
            ["kdata", "moshu", "template-info"],
            params={"templateId": str(template_id), "verNo": str(ver_no)},
            timeout=30,
        )
    )
    data = result.get("data") or {}
    return data if isinstance(data, dict) else {}


def _fmt_time(ts_ms) -> str:
    if not ts_ms:
        return "-"
    return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def format_dataset(s: dict[str, Any]) -> str:
    dims = [c for c in s.get("allColumnInfoList", []) if c.get("refType") == 2]
    kpis = [c for c in s.get("allColumnInfoList", []) if c.get("refType") == 1]
    sql = "\n".join(m.get("sqlContent", "") for m in s.get("modelList", [])).strip()
    sid = s.get("subjectId", "")

    lines = [
        "### 基础信息",
        "",
        f"- 数据集：{s.get('subjectName', '')}",
        f"- ID：{sid}",
        f"- 链接：{BI_BASE}/v2/dataset/detail/{sid}",
        f"- 创建者：{s.get('createUser', '-')}",
        f"- 更新者：{s.get('updateUser', '-')}",
        f"- 更新时间：{_fmt_time(s.get('updateTime'))}",
        f"- 版本数：{len(s.get('allVersionInfo', []))}",
        "",
        f"### 维度（{len(dims)} 个）",
        "",
        "| 字段名 | 展示名称 |",
        "|--------|---------|",
    ]
    for d in dims:
        lines.append(f"| {d.get('columnName', '')} | {d.get('columnDisplayName', '')} |")

    lines += [
        "",
        f"### 指标（{len(kpis)} 个）",
        "",
        "| 字段名 | 展示名称 | 聚合方式 |",
        "|--------|---------|---------|",
    ]
    for k in kpis:
        aggr = k.get("aggrType", "")
        if aggr == "percentile" and k.get("percentileValue"):
            aggr = f"percentile({k['percentileValue']})"
        lines.append(f"| {k.get('columnName', '')} | {k.get('columnDisplayName', '')} | {aggr} |")

    lines += ["", "### SQL 源码", "", "```sql", sql, "```"]
    return "\n".join(lines)


def format_template_list(templates: list[dict[str, Any]]) -> str:
    if not templates:
        return "暂无 SQL 模板"
    lines = [f"共 {len(templates)} 个 SQL 模板："]
    for t in templates:
        folder = t.get("_folderName", "")
        folder_str = f"  [{folder}]" if folder else ""
        lines.append(
            f"  [{t.get('id', '-')}] {t.get('name', '-')}{folder_str}"
            f"  (创建: {t.get('creatorMis', '-')}, 更新: {_fmt_time(t.get('modifyTime'))})"
        )
    return "\n".join(lines)


def format_template_detail(t: dict[str, Any]) -> str:
    lines = [
        "### 基础信息",
        "",
        f"- 模板名称：{t.get('name', '-')}",
        f"- ID：{t.get('id', '-')}",
        f"- 链接：{BI_BASE}/v2/sql/edit/{t.get('id')}",
        f"- 数据源：{t.get('dsName', '-')}",
        f"- 创建者：{t.get('createMis', '-')}",
        f"- 更新时间：{_fmt_time(t.get('modifyTime'))}",
        f"- 版本号：v{t.get('verNo', 1)}",
        "",
        "### SQL 内容",
        "",
        "```sql",
        t.get("statement", "-- (空)"),
        "```",
    ]
    return "\n".join(lines)


def cmd_dataset_list(args: argparse.Namespace) -> None:
    items = get_dataset_list(page_num=args.page_num, page_size=args.page_size, query=args.query)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    print(f"共 {len(items)} 个数据集：")
    for ds in items:
        creator = ds.get("creator", {}).get("mis", "-") if isinstance(ds.get("creator"), dict) else ds.get("createUser", "-")
        print(f"  [{ds.get('id', '-')}] {ds.get('name', '-')}  (创建: {creator}, 更新: {_fmt_time(ds.get('updateTime'))})")


def cmd_dataset_info(args: argparse.Namespace) -> None:
    ids = [int(value) for value in args.ids]
    items = get_dataset_info(ids)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    for item in items:
        print(format_dataset(item))
        print()


def cmd_template_list(args: argparse.Namespace) -> None:
    items = get_template_list(q=args.query, managed=args.managed, shared=args.shared, project_id=args.project_id)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    print(format_template_list(items))


def cmd_template_info(args: argparse.Namespace) -> None:
    detail = get_template_detail(args.template_id, ver_no=args.ver_no)
    if args.json:
        print(json.dumps(detail, ensure_ascii=False, indent=2))
        return
    print(format_template_detail(detail))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="魔数个人数据集和 SQL 模板元信息查询")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("dataset-list", help="获取魔数个人数据集列表")
    p.add_argument("--query", default="", help="搜索关键词")
    p.add_argument("--page-num", type=int, default=1)
    p.add_argument("--page-size", type=int, default=50)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_dataset_list)

    p = sub.add_parser("dataset-info", help="获取魔数个人数据集详情")
    p.add_argument("ids", nargs="+")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_dataset_info)

    p = sub.add_parser("template-list", help="获取魔数 SQL 模板列表")
    p.add_argument("--query", "-q", default="", help="搜索关键词")
    p.add_argument("--managed", action="store_true")
    p.add_argument("--shared", action="store_true")
    p.add_argument("--project-id", default="")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_template_list)

    p = sub.add_parser("template-info", help="获取魔数 SQL 模板详情")
    p.add_argument("template_id")
    p.add_argument("--ver-no", default="1")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_template_info)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
