#!/usr/bin/env python3
"""
Keeta 起源数据集查询工具
基于 MtcliStandardClient，调用 `npx mtcli kdata standard`，无需自行管理 SSO。

⚠️  接口鉴权说明
  data-center.mykeeta.com 的所有接口请求头必须携带：
    region : 地区 code，枚举 HK / SA / AE / QA / KW / BR / BH
    locale : 语言，枚举 zh / en / pt-BR，默认 zh
  缺少任一参数服务端将返回 {"code":101000918,"message":"system error"}。
  mtcli 负责接口鉴权和 schema 路由；调用各 API 时可通过 --region / --locale 参数覆盖。

用法示例：
  # 查 SA 近7天订单量（按天分组，附环比同比）
  python3 origin_query.py query \
    --dataset 60041382 \
    --measures fin_ord_num \
    --date 20260314~20260320 \
    --region SA \
    --group-by dt \
    --pops wow,dod

  # 列出数据集所有指标（可按关键词过滤，--region 可选，默认 SA）
  python3 origin_query.py measures --dataset 60041382 --search 订单

  # 列出数据集所有维度（--region 可选，默认 SA）
  python3 origin_query.py dims --dataset 60041382

  # 列出所有数据集（--region 可选，默认 SA）
  python3 origin_query.py datasets

  # 查维度可选值（dim_code 必须来自 dims 命令的实际 code 列表）
  python3 origin_query.py dim-values global_region_code
  python3 origin_query.py dim-values city_id --search 九龙
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# 确保能 import mtcli_standard_client
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from mtcli_standard_client import MtcliStandardClient


# ────────────────────────────────────────────────
# 格式化输出
# ────────────────────────────────────────────────

def print_table(result: dict) -> None:
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


# ────────────────────────────────────────────────
# 子命令处理
# ────────────────────────────────────────────────

def cmd_query(args, client: MtcliStandardClient) -> None:
    filters = {}
    if args.filter:
        for f in args.filter:
            k, v = f.split("=", 1)
            filters[k] = v.split(",")

    measures = []
    for m in args.measures:
        measures.extend(m.split(","))

    group_by = args.group_by.split(",") if args.group_by else None
    pops = args.pops.split(",") if args.pops else None
    order_by = None
    if args.order_by:
        k, v = args.order_by.split("=", 1)
        order_by = {k: v}

    result = client.query(
        dataset_id=args.dataset,
        measures=measures,
        date_range=args.date,
        region=args.region,
        filters=filters or None,
        group_by=group_by,
        order_by=order_by,
        pops=pops,
        page_size=args.page_size,
        locale=args.locale,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_table(result)


def cmd_measures(args, client: MtcliStandardClient) -> None:
    items = client.list_measures(args.dataset, search=args.search, locale=args.locale, region=args.region)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print(f"{'code':<45} {'name':<30} desc")
        print("-" * 110)
        for m in items:
            print(f"{m.get('code',''):<45} {m.get('name',''):<30} {m.get('desc','')[:60]}")
        print(f"\n共 {len(items)} 个指标")


def cmd_dims(args, client: MtcliStandardClient) -> None:
    items = client.list_dimensions(args.dataset, search=args.search, locale=args.locale, region=args.region)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print(f"{'code':<35} {'name':<25} {'is_date':<8} desc")
        print("-" * 100)
        for d in items:
            print(f"{d.get('code',''):<35} {d.get('name',''):<25} {str(d.get('date', False)):<8} {d.get('desc','')[:50]}")
        print(f"\n共 {len(items)} 个维度")


def cmd_datasets(args, client: MtcliStandardClient) -> None:
    items = client.list_datasets(region=args.region)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print(f"{'dataSetId':<12} {'dataSetName':<35} owner")
        print("-" * 80)
        for d in items:
            owners = ",".join(d.get("ownerList", []))
            print(f"{str(d.get('dataSetId','')):<12} {d.get('dataSetName',''):<35} {owners}")
        print(f"\n共 {len(items)} 个数据集")


def cmd_dim_values(args, client: MtcliStandardClient) -> None:
    items = client.list_dim_values(args.dim_code, search=args.search, region=args.region)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print(f"{'value':<30} label")
        print("-" * 60)
        for v in items:
            if isinstance(v, dict):
                print(f"{str(v.get('value','')):<30} {v.get('label','')}")
            else:
                print(str(v))
        print(f"\n共 {len(items)} 个维值")


# ────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Keeta 起源数据集查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--locale", default="zh", help="语言枚举: zh / en / pt-BR，默认 zh（所有接口均需携带此 header）")

    sub = parser.add_subparsers(dest="cmd", required=True)

    # query
    p_q = sub.add_parser("query", help="查询数据")
    p_q.add_argument("--dataset", "-d", required=True, help="数据集 ID，如 60041382")
    p_q.add_argument("--measures", "-m", required=True, nargs="+", help="指标 code，支持逗号分隔或多次 -m")
    p_q.add_argument("--date", required=True, help="日期范围，如 20260314~20260320")
    p_q.add_argument("--filter", "-f", action="append", help="维度过滤，格式 code=value 或 code=v1,v2，可多次")
    p_q.add_argument("--group-by", "-g", help="分组维度，逗号分隔，如 dt,region_code")
    p_q.add_argument("--order-by", help="排序，如 dt=ASC")
    p_q.add_argument("--pops", help="环比同比，逗号分隔，如 wow,dod")
    p_q.add_argument("--region", help="地区 code，如 SA（通过 ext.region 传递，无需加入 --filter）")
    p_q.add_argument("--page-size", type=int, default=1000)
    p_q.set_defaults(func=cmd_query)

    # measures
    p_m = sub.add_parser("measures", help="列出数据集指标")
    p_m.add_argument("--dataset", "-d", required=True)
    p_m.add_argument("--search", "-s", help="关键词过滤")
    p_m.add_argument("--region", default="SA", help="地区 code（枚举 HK/SA/AE/QA/KW/BR/BH），默认 SA（接口 header 必传）")
    p_m.set_defaults(func=cmd_measures)

    # dims
    p_d = sub.add_parser("dims", help="列出数据集维度")
    p_d.add_argument("--dataset", "-d", required=True)
    p_d.add_argument("--search", "-s", help="关键词过滤")
    p_d.add_argument("--region", default="SA", help="地区 code（枚举 HK/SA/AE/QA/KW/BR/BH），默认 SA（接口 header 必传）")
    p_d.set_defaults(func=cmd_dims)

    # datasets
    p_ds = sub.add_parser("datasets", help="列出所有数据集")
    p_ds.add_argument("--region", default="SA", help="地区 code（枚举 HK/SA/AE/QA/KW/BR/BH），默认 SA（接口 header 必传）")
    p_ds.set_defaults(func=cmd_datasets)

    # dim-values
    p_dv = sub.add_parser("dim-values", help="查询维度的可选值（维值）；dim_code 必须来自 dims 命令的实际 code 列表")
    p_dv.add_argument("dim_code", help="维度 code（须先用 dims 命令确认），如 global_region_code、city_id")
    p_dv.add_argument("--search", "-s", help="关键词过滤（按 label 或 value）")
    p_dv.add_argument("--region", default="SA", help="地区 code（枚举 HK/SA/AE/QA/KW/BR/BH），默认 SA（接口 header 必传）")
    p_dv.set_defaults(func=cmd_dim_values)

    args = parser.parse_args()
    client = MtcliStandardClient()
    try:
        args.func(args, client)
    except RuntimeError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
