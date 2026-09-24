"""
filter_dashboard_meta.py
将 mtbi_dashboard_meta_info MCP 工具返回的原始 JSON 提炼为精简的元信息概况，
并保存到 scripts/dashboard_meta.json。

输入：通过 stdin 或 --input 文件读取 mcporter 返回的原始 JSON
输出：scripts/dashboard_meta.json（相对于本脚本所在目录）

输出格式：
{
  "dashboard": { "id": ..., "name": ..., "version": ..., "security_level": ... },
  "tabs": [
    {
      "tab_id": ..., "tab_name": ...,
      "components": [
        {
          "component_id": ..., "component_name": ..., "type": ...,
          "dataset_name": ...,
          "metrics": [{"code": ..., "name": ...}, ...],
          "dims":    [{"code": ..., "name": ...}, ...]
        }
      ]
    }
  ],
  "global_filters": [
    { "fid": ..., "name": ..., "type": ..., "fields": [{"code":..., "name":...}] }
  ]
}
"""

import argparse
import json
import os
import sys


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def extract_field_brief(field: dict) -> dict:
    """从字段对象中只取 code 和 name。"""
    return {
        "code": field.get("code", ""),
        "name": field.get("displayName") or field.get("name", ""),
    }


def build_dataset_url(biz_id, dataset_id) -> str:
    """
    根据 bizId 拼接数据集起源链接（境外版，使用 keetapp.com 域名）：
    - bizId == 332（个人数据集）→ bi.keetapp.com/v2/dataset/detail/{datasetId}
    - 其他业务线         → origin.keetapp.com/data-subject/detail/{datasetId}?busiLineId={bizId}
    """
    if biz_id == 332:
        return f"https://bi.keetapp.com/v2/dataset/detail/{dataset_id}"
    return f"https://origin.keetapp.com/data-subject/detail/{dataset_id}?busiLineId={biz_id}"


def extract_component(comp: dict) -> dict:
    """从组件对象提炼关键字段：id、名称、类型、数据集、指标、维度。"""
    biz_id = comp.get("bizId", "")
    dataset_id = comp.get("datasetId", "")
    return {
        "component_id": comp.get("cid", comp.get("id", "")),
        "component_name": comp.get("name", ""),
        "type": comp.get("type", ""),
        "biz_id": biz_id,
        "dataset_id": dataset_id,
        "dataset_name": comp.get("datasetName", ""),
        "dataset_url": build_dataset_url(biz_id, dataset_id) if biz_id and dataset_id else "",
        "metrics": [extract_field_brief(m) for m in comp.get("metrics", [])],
        "dims":    [extract_field_brief(d) for d in comp.get("dims", [])],
    }


def extract_tab(tab: dict) -> dict:
    """从 tab 对象提炼关键字段：tabId、名称、子组件列表。"""
    return {
        "tab_id":   tab.get("tabId", ""),
        "tab_name": tab.get("tabName", ""),
        "components": [extract_component(c) for c in tab.get("components", [])],
    }


def extract_global_filter(f: dict) -> dict:
    """从全局筛选器提炼：fid、展示名称、类型、关联字段（code+name）。"""
    return {
        "fid":    f.get("fid", ""),
        "name":   f.get("name", ""),
        "type":   f.get("type", ""),
        "fields": [extract_field_brief(field) for field in f.get("fields", [])],
    }


# ──────────────────────────────────────────────
# 核心过滤逻辑
# ──────────────────────────────────────────────

def filter_meta(raw: dict) -> dict:
    """
    接受 mcporter 返回的原始 JSON（支持双层 data 包裹）,
    返回精简的元信息 dict。
    """
    # mcporter 返回结构：{ "code":0, "data": { "code":0, "data": { ... } } }
    inner = raw.get("data", raw)
    if isinstance(inner, dict) and "data" in inner:
        inner = inner["data"]

    # 仪表板基础信息
    dashboard = {
        "id":             inner.get("dashboardId", ""),
        "name":           inner.get("dashboardName", ""),
        "version":        inner.get("version", ""),
        "security_level": inner.get("globalConfig", {}).get("securityLevel", ""),
    }

    # Tab 列表
    tabs = [extract_tab(t) for t in inner.get("tabs", [])]

    # 全局筛选器（来自 globalConfig.filters）
    global_filters = [
        extract_global_filter(f)
        for f in inner.get("globalConfig", {}).get("filters", [])
    ]

    return {
        "dashboard":      dashboard,
        "tabs":           tabs,
        "global_filters": global_filters,
    }


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="过滤 mtbi_dashboard_meta_info 返回的原始 JSON，输出精简元信息"
    )
    parser.add_argument(
        "--input", "-i",
        help="原始 JSON 文件路径；不指定则从 stdin 读取",
    )
    parser.add_argument(
        "--output", "-o",
        help="输出 JSON 文件路径；默认为本脚本同目录下的 dashboard_meta.json",
    )
    args = parser.parse_args()

    # 读取原始 JSON
    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            raw = json.load(f)
    else:
        raw = json.load(sys.stdin)

    # 过滤
    result = filter_meta(raw)

    # 确定输出路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = args.output or os.path.join(script_dir, "dashboard_meta.json")

    # 写入
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[OK] 元信息已保存到: {output_path}")

    # 同时输出概况到 stdout，方便查看
    dash = result["dashboard"]
    print(f"  仪表板: {dash['name']}（id={dash['id']}，version={dash['version']}）")
    print(f"  全局筛选器: {len(result['global_filters'])} 个")
    for tab in result["tabs"]:
        comp_count = len(tab["components"])
        print(f"  Tab [{tab['tab_name']}]: {comp_count} 个组件", end="")
        for comp in tab["components"]:
            url_hint = f" | 起源: {comp['dataset_url']}" if comp.get("dataset_url") else ""
            print(f"\n    └ {comp['component_name']}（{comp['type']}）"
                  f" | 数据集: {comp.get('dataset_name', '')} [{comp.get('dataset_id', '')}]"
                  f" | 指标 {len(comp['metrics'])} 个"
                  f" | 维度 {len(comp['dims'])} 个"
                  f"{url_hint}", end="")
        print()


if __name__ == "__main__":
    main()
