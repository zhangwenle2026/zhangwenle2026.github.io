#!/usr/bin/env python3
"""kdata-fl - Keeta 前线数据查询 CLI 主入口（仅支持起源标准数据集）

用法：
  kdata-fl standard datasets
  kdata-fl standard measures --dataset 60041382 [--search 订单]
  kdata-fl standard dims --dataset 60041382
  kdata-fl standard dim-values global_region_code
  kdata-fl standard query --dataset 60041382 --measures fin_ord_num --date 20260318~20260324 --region HK --biz-type <bizType> --filter <dimCode>=<orgId>

  kdata-fl org lines                                       查询我有权限的业务线
  kdata-fl org nodes --biz-type 1001                       查询业务线下的层级结构（不含权限判断）
  kdata-fl org values --biz-type 1001 --node-type 10001    查询有权限的维值（唯一鉴权入口）
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time

# ── 模块路径 ─────────────────────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.realpath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)
for _sub in ["core", "capability1_standard"]:
    _p = os.path.join(_DIR, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ══════════════════════════════════════════════════════════════════════════════
# [TRACKING] CLI 日志上报
# ══════════════════════════════════════════════════════════════════════════════

try:
    from core.bootstrap import ensure_cli_installed as _ensure_cli_installed
    from core.mis import get_mis as _resolve_mis
    from core.mis import set_manual_mis as _set_manual_mis
    from core.paths import KDATA_CONF as _PATH_KDATA_CONF
    from core.paths import SKILL_SEARCH_DIRS as _SKILL_SEARCH_DIRS
    from core.paths import WORKSPACE_DIR as _PATH_WORKSPACE_DIR
    from core.task import (
        task_start as _task_start,
        task_end as _task_end,
        get_active_task as _get_active_task,
        touch_task as _touch_task,
        get_task_status as _get_task_status,
        report_feedback as _report_feedback,
        report_cli_command as _report_cli_command,
    )
    _CORE_IMPORTED = True
except ImportError as _e:
    print(f"[kdata-fl][WARN] core 模块导入失败，日志上报已禁用: {_e}", file=sys.stderr)
    _CORE_IMPORTED = False


def _get_current_mis() -> str:
    if _CORE_IMPORTED:
        return _resolve_mis(default="unknown")
    import re as _re
    for key in ("KDATA_MIS", "SANDBOX_MIS", "OPENCLAW_MIS", "MEITUAN_MIS"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    try:
        user_md = os.path.expanduser("~/.openclaw/workspace/USER.md")
        if os.path.exists(user_md):
            text = open(user_md, encoding="utf-8").read()
            m = _re.search(r"MIS[^::。]*[::：]\s*([a-zA-Z0-9_]+)", text)
            if m:
                return m.group(1).strip()
    except Exception:
        pass
    return "unknown"


def _report_log(
    mis: str, cli_command: str, status: str, cost_time: int,
    input_summary: str = "", output_summary: str = "", error_msg: str = "",
    session_id: str = "",
) -> None:
    if not _CORE_IMPORTED:
        return
    try:
        _report_cli_command(
            cli_command=cli_command,
            mis=mis,
            params=input_summary,
            output=output_summary,
            cost_ms=cost_time,
            success=(status == "SUCCESS"),
            error_msg=error_msg,
            session_id=session_id,
        )
    except Exception as _log_err:
        print(f"[kdata-fl][WARN] 日志上报异常: {_log_err}", file=sys.stderr)


def _normalise_argv(argv: list[str]) -> tuple[list[str], bool]:
    json_enabled = False
    cleaned = []
    for item in argv:
        if item == "--json":
            json_enabled = True
            continue
        cleaned.append(item)
    if json_enabled:
        cleaned.insert(0, "--json")
    return cleaned, json_enabled


def _build_cli_command(args, argv: list[str] | None = None) -> str:
    raw_argv = list(argv if argv is not None else getattr(args, "_raw_argv", []) or sys.argv[1:])
    parts = ["kdata-fl"] + raw_argv
    return " ".join(shlex.quote(str(p)) for p in parts if str(p))


def _unset_proxy():
    for k in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(k, None)


# ══════════════════════════════════════════════════════════════════════════════
# 组织架构权限校验辅助
# ══════════════════════════════════════════════════════════════════════════════

def _check_org_permission(args, filters: dict | None = None) -> None:
    """
    在 standard query 执行前校验组织架构权限。
    --biz-type 为必传参数，未传则直接报错退出。
    若校验不通过，打印错误并 sys.exit(1)。
    """
    biz_type = getattr(args, "biz_type", None)
    if biz_type is None:
        print("❌ 必须指定 --biz-type 参数。请先运行 `kdata-fl org lines` 查询有权限的业务线。", file=sys.stderr)
        sys.exit(1)

    from org_auth import check_query_permission, node_type_for_dim_code
    org_node_type = getattr(args, "org_node_type", None)
    org_ids = getattr(args, "org_ids", None)
    if org_node_type is None and not org_ids and filters:
        for dim_code, values in filters.items():
            inferred = node_type_for_dim_code(dim_code)
            if inferred is not None:
                org_node_type = inferred
                org_ids = values if isinstance(values, list) else [values]
                break
    if org_node_type is None or not org_ids:
        print("❌ 必须通过 --filter 传入 whoami 推荐的鉴权维度，例如 --filter org_2_id=123。", file=sys.stderr)
        sys.exit(1)

    print("[权限校验] 正在检查组织架构权限...", file=sys.stderr)
    source = _get_source_for_biz_type(biz_type)
    allowed, reason = check_query_permission(
        biz_type=biz_type,
        org_node_type=org_node_type,
        org_ids=org_ids,
        source=source,
    )
    if not allowed:
        print(f"❌ 权限不足：{reason}", file=sys.stderr)
        sys.exit(1)
    print("[权限校验] ✅ 权限校验通过", file=sys.stderr)


# ══════════════════════════════════════════════════════════════════════════════
# org 子命令
# ══════════════════════════════════════════════════════════════════════════════

# 前线 skill 仅支持以下数据集
_ALLOWED_DATASET_IDS = {
    # ── B 端 BD ──
    "60008094",   # 商家主题
    "60041382",   # 供给大盘
    "60045876",   # B端实时盯盘看板_最新offset
    "60048831",   # 新城上单监控
    "62059524",   # 供给-商补分析看板-global
    "62059636",   # 品牌集团分析
    "62063311",   # 商品分析数据集-global
    # ── D 端 PMM ──
    "60020949",   # D端-实时-3PL-3PL过程管理
    "60020806",   # D端-离线-3PL-3PL过程管理
    "60009475",   # Logistics Partner Manager RT
    "60011628",   # 3PL PMM By Courier (RT)
    "60011506",   # Logistics Partner Manager Batch
    "60011696",   # 3PL PMM By Courier (Batch)
    "62052284",   # 实时-履约-实时-库存排班-FOR内部看板
}


def _assert_allowed_dataset(dataset_id: str):
    """校验数据集 ID 是否在允许范围内，不在则报错退出。"""
    if str(dataset_id) not in _ALLOWED_DATASET_IDS:
        allowed = ", ".join(sorted(_ALLOWED_DATASET_IDS))
        print(f"❌ 数据集 {dataset_id} 不在支持范围内。\n支持的数据集 ID: {allowed}")
        raise SystemExit(1)


# 前线 skill 仅支持以下业务线（组织维度相关）
_ALLOWED_BIZ_TYPES = {
    # ── B 端 BD ──
    1148702721,   # Global-SMB-组织
    1278539788,   # Global-KASA
    350530428,    # Mega-Long_Tier
    1160308566,   # Global-区域/蜂窝
    # ── D 端 PMM ──
    239551852,    # D端 PMM 组织架构线
}


def _filter_allowed_lines(lines: list) -> list:
    """过滤出允许查询的业务线。"""
    return [l for l in lines if l.get("bizType") in _ALLOWED_BIZ_TYPES]


def _cmd_org_lines(args):
    """查询当前用户有权限的业务线列表（仅限支持的业务线）。"""
    from org_auth import list_org_lines
    lines = _filter_allowed_lines(list_org_lines())
    if args.json:
        print(json.dumps(lines, ensure_ascii=False, indent=2))
    else:
        if not lines:
            print("（当前用户在支持的业务线中无权限）")
            return
        print(f"共 {len(lines)} 条业务线权限：")
        for line in lines:
            name = line.get("bizTypeName") or line.get("name", "")
            source = line.get("sourceName", "")
            print(f"  bizType={line['bizType']}  {name}  [{source}]")


def _get_source_for_biz_type(biz_type: int) -> int:
    """从业务线列表中查出 biz_type 对应的 source 值，找不到返回 1。"""
    from org_auth import list_org_lines
    lines = list_org_lines()
    for line in lines:
        if line.get("bizType") == biz_type:
            return line.get("source", 1)
    return 1


def _assert_allowed_biz_type(biz_type: int):
    """校验 bizType 是否在允许范围内，不在则报错退出。"""
    if biz_type not in _ALLOWED_BIZ_TYPES:
        allowed = ", ".join(str(b) for b in sorted(_ALLOWED_BIZ_TYPES))
        print(f"❌ 业务线 {biz_type} 不在支持范围内。\n支持的业务线: {allowed}\n（B端: Global-SMB-组织 / Global-KASA / Mega-Long_Tier / Global-区域/蜂窝 | D端: PMM组织架构线）")
        raise SystemExit(1)


def _enrich_nodes_with_dim_code(nodes: list, region: str = "SA") -> list:
    """
    批量查询 orgNodeType 对应的维度 Code，并将 dimCode/dimCodeField 注入到每个 node 中。
    """
    from org_auth import dim_code_for_node
    for n in nodes:
        dim_code = n.get("dimCode") or dim_code_for_node(n.get("orgNodeType"))
        n["dimCode"] = dim_code
        n["dimCodeField"] = dim_code
    return nodes


def _cmd_org_nodes(args):
    """查询业务线下的层级维度列表（仅展示层级结构，不做鉴权判断）。"""
    from org_auth import list_org_nodes
    _assert_allowed_biz_type(args.biz_type)
    source = _get_source_for_biz_type(args.biz_type)
    nodes = list_org_nodes(args.biz_type, source=source)
    nodes = _enrich_nodes_with_dim_code(nodes)
    if args.json:
        # JSON 模式也去掉权限字段，避免误导
        cleaned = []
        for n in nodes:
            cleaned.append({
                "orgNodeType": n["orgNodeType"],
                "name": n.get("orgNodeName") or n.get("orgNodeTypeName") or n.get("name", ""),
                "level": n.get("level", ""),
                "dimCode": n.get("dimCode", ""),
            })
        print(json.dumps(cleaned, ensure_ascii=False, indent=2))
    else:
        if not nodes:
            print(f"（业务线 {args.biz_type} 下无层级维度）")
            return
        print(f"业务线 {args.biz_type} 共 {len(nodes)} 个层级维度：")
        for n in nodes:
            name = n.get("orgNodeName") or n.get("orgNodeTypeName") or n.get("name", "")
            level = n.get("level", "")
            dim_code = n.get("dimCode", "")
            code_str = f"  dimCode={dim_code}" if dim_code else ""
            print(f"  orgNodeType={n['orgNodeType']}  {name}  (level={level}){code_str}")


def _cmd_org_values(args):
    """查询指定层级下用户有权限的维值列表。"""
    from org_auth import list_org_node_values
    _assert_allowed_biz_type(args.biz_type)
    source = _get_source_for_biz_type(args.biz_type)
    org_ids = args.org_ids or None
    values = list_org_node_values(args.biz_type, args.node_type, org_ids, source=source)
    if args.json:
        print(json.dumps(values, ensure_ascii=False, indent=2))
    else:
        if not values:
            print(f"（业务线 {args.biz_type} / 层级 {args.node_type} 下无有权限的维值）")
            return
        permitted = [v for v in values if v.get("hasPermission")]
        print(f"共 {len(values)} 个维值（其中 {len(permitted)} 个有权限）：")
        for v in values:
            name = v.get("orgName") or v.get("text") or v.get("name", "")
            oid = v.get("orgId") or v.get("value", "")
            perm = "✅" if v.get("hasPermission") else "❌"
            print(f"  {perm} orgId={oid}  {name}")


def _cmd_org_values_permitted(args):
    """自动找到业务线下第一个有权限的层级，返回该层所有有权限的维值（含维度 Code）。"""
    from org_auth import list_first_permitted_values
    _assert_allowed_biz_type(args.biz_type)
    source = _get_source_for_biz_type(args.biz_type)
    result = list_first_permitted_values(args.biz_type, source)
    if result:
        # 补充维度 Code
        enriched = _enrich_nodes_with_dim_code([{
            "orgNodeType": result["orgNodeType"],
            "orgNodeName": result["orgNodeName"],
            "level": result["level"],
        }])
        result["dimCode"] = enriched[0].get("dimCode", "")
        result["dimCodeField"] = enriched[0].get("dimCodeField", "")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if not result:
            print(f"（业务线 {args.biz_type} 下未找到有权限的维值）")
            return
        print(f"业务线 {args.biz_type} — 有权限的最顶层维度：")
        dim_code = result.get("dimCode", "")
        code_str = f"  dimCode={dim_code}" if dim_code else ""
        print(f"  层级: {result['orgNodeName']} (level={result['level']}, orgNodeType={result['orgNodeType']}){code_str}")
        print(f"  共 {len(result['values'])} 个有权限的维值：")
        for v in result['values']:
            print(f"    value={v['value']}  text={v['text']}")


# ══════════════════════════════════════════════════════════════════════════════
# whoami — 一键权限画像
# ══════════════════════════════════════════════════════════════════════════════

# 业务线名称映射（用于人类可读输出）
_BIZ_TYPE_NAMES = {
    1148702721: "Global-SMB-组织",
    1278539788: "Global-KASA",
    350530428:  "Mega-Long_Tier",
    1160308566: "Global-区域/蜂窝",
    239551852:  "D端 PMM 组织架构线",
}

# 数据集名称映射
_DATASET_NAMES = {
    "60008094": "商家主题",
    "60041382": "供给大盘",
    "60045876": "B端实时盯盘看板_最新offset",
    "60048831": "新城上单监控",
    "62059524": "供给-商补分析看板-global",
    "62059636": "品牌集团分析",
    "62063311": "商品分析数据集-global",
    "60020949": "D端-实时-3PL-3PL过程管理",
    "60020806": "D端-离线-3PL-3PL过程管理",
    "60009475": "Logistics Partner Manager RT",
    "60011628": "3PL PMM By Courier (RT)",
    "60011506": "Logistics Partner Manager Batch",
    "60011696": "3PL PMM By Courier (Batch)",
    "62052284": "实时-履约-实时-库存排班-FOR内部看板",
}

# 数据集与业务线的推荐关系
_DATASET_BIZ_AFFINITY = {
    "60008094": [1148702721, 1278539788, 1160308566, 350530428],
    "60041382": [1148702721, 1278539788, 1160308566, 350530428],
    "60045876": [1148702721, 1278539788, 1160308566, 350530428],
    "60048831": [1148702721, 1278539788, 1160308566, 350530428],
    "62059524": [1148702721, 1278539788, 1160308566, 350530428],
    "62059636": [1148702721, 1278539788, 1160308566, 350530428],
    "62063311": [1148702721, 1278539788, 1160308566, 350530428],
    "60020949": [239551852],
    "60020806": [239551852],
    "60009475": [239551852],
    "60011628": [239551852],
    "60011506": [239551852],
    "60011696": [239551852],
    "62052284": [239551852],
}


def _cmd_whoami(args):
    """一键查看当前用户的完整权限画像 + 推荐查询参数。"""
    from org_auth import list_org_lines, list_org_nodes, list_org_node_values
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import io as _io

    json_mode = getattr(args, "json", False)
    # JSON 模式下把 stdout 重定向到 StringIO，静默所有 print
    _real_stdout = sys.stdout
    if json_mode:
        sys.stdout = _io.StringIO()

    mis = _get_current_mis()
    print(f"👤 用户: {mis}")
    print("=" * 60)

    # 1. 获取用户有权限的业务线（仅限支持范围内）
    try:
        all_lines = list_org_lines()
    except RuntimeError as e:
        print(f"❌ 获取业务线失败: {e}")
        if json_mode:
            sys.stdout = _real_stdout
            print(json.dumps({"error": str(e), "mis": mis}, ensure_ascii=False))
        return

    lines = _filter_allowed_lines(all_lines)
    user_biz_types = {l["bizType"] for l in lines}

    if not lines:
        print("\n⚠️  在支持的业务线中无权限。")
        print(f"   支持的业务线: {', '.join(f'{v}({k})' for k, v in _BIZ_TYPE_NAMES.items())}")
        if all_lines:
            print(f"   您有权限但不在支持范围内的业务线:")
            for l in all_lines:
                bt = l.get("bizType")
                if bt not in _ALLOWED_BIZ_TYPES:
                    name = l.get("bizTypeName") or l.get("name", "")
                    print(f"     bizType={bt}  {name}")
        if json_mode:
            sys.stdout = _real_stdout
            print(json.dumps({"error": "no_permission", "mis": mis, "bizLines": [], "permissions": []}, ensure_ascii=False))
        return

    print(f"\n📋 有权限的业务线（共 {len(lines)} 条）:")
    for l in lines:
        bt = l["bizType"]
        name = _BIZ_TYPE_NAMES.get(bt, l.get("bizTypeName", ""))
        print(f"  ✅ bizType={bt}  {name}")

    # 2. 并行查所有业务线的 nodes + 第一个有权限层级的 values
    print("\n" + "=" * 60)
    print("🔑 权限维值详情:")
    print("=" * 60)

    def _fetch_biz_perm(l):
        """并行任务：查一条业务线的 nodes → 第一个有权限层的 values。"""
        bt = l["bizType"]
        biz_name = _BIZ_TYPE_NAMES.get(bt, l.get("bizTypeName", ""))
        source = l.get("source", 1)
        result = {"bt": bt, "biz_name": biz_name, "error": None, "nodes": None, "perm_layer": None}

        try:
            nodes = list_org_nodes(bt, source=source)
            nodes = _enrich_nodes_with_dim_code(nodes)
            result["nodes"] = nodes
        except RuntimeError as e:
            result["error"] = str(e)
            return result

        if not nodes:
            return result

        # 按 level 排序，逐层查到第一个有权限的就停
        for n in sorted(nodes, key=lambda x: x.get("level", 0)):
            nt = n["orgNodeType"]
            try:
                values = list_org_node_values(bt, nt, source=source)
            except RuntimeError:
                continue
            permitted = [v for v in values if v.get("hasPermission")]
            if permitted:
                result["perm_layer"] = {
                    "node": n,
                    "total": len(values),
                    "permitted": permitted,
                }
                break

        return result

    # 并行查所有业务线
    biz_results = []
    with ThreadPoolExecutor(max_workers=len(lines)) as pool:
        futures = {pool.submit(_fetch_biz_perm, l): l for l in lines}
        for f in as_completed(futures):
            biz_results.append(f.result())

    # 按原始 lines 顺序输出
    biz_results_map = {r["bt"]: r for r in biz_results}
    perm_summary = []  # [(biz_type, biz_name, dim_code, org_id, org_name)]

    for l in lines:
        bt = l["bizType"]
        r = biz_results_map[bt]
        biz_name = r["biz_name"]
        print(f"\n── {biz_name} (bizType={bt}) ──")

        if r["error"]:
            print(f"  ❌ 获取层级失败: {r['error']}")
            continue
        if not r["nodes"]:
            print("  （无层级维度）")
            continue
        if not r["perm_layer"]:
            print("  ⚠️  所有层级均无有权限维值")
            continue

        layer = r["perm_layer"]
        n = layer["node"]
        node_name = n.get("orgNodeName") or n.get("orgNodeTypeName") or n.get("name", "")
        level = n.get("level", "")
        dim_code = n.get("dimCode", "")
        code_str = f", dimCode={dim_code}" if dim_code else ""
        print(f"\n  📍 {node_name} (level={level}{code_str})")
        print(f"     共 {layer['total']} 个维值，{len(layer['permitted'])} 个有权限:")

        for v in layer["permitted"]:
            org_id = v.get("orgId") or v.get("value", "")
            org_name = v.get("orgName") or v.get("text") or v.get("name", "")
            print(f"     ✅ {org_id}  {org_name}")
            if dim_code:
                perm_summary.append((bt, biz_name, dim_code, org_id, org_name))

    # 3. 生成推荐查询参数
    print("\n" + "=" * 60)
    print("📝 推荐查询参数（可直接复制使用）:")
    print("=" * 60)

    if not perm_summary:
        print("\n⚠️  未找到有效的权限维值，无法生成推荐参数。")
        if json_mode:
            sys.stdout = _real_stdout
            biz_list = [{"bizType": l["bizType"], "name": _BIZ_TYPE_NAMES.get(l["bizType"], "")} for l in lines]
            print(json.dumps({"mis": mis, "bizLines": biz_list, "permissions": []}, ensure_ascii=False))
        return

    # 按业务线分组
    from collections import defaultdict
    biz_perms = defaultdict(list)
    for bt, biz_name, dim_code, org_id, org_name in perm_summary:
        biz_perms[bt].append((biz_name, dim_code, org_id, org_name))

    example_idx = 0
    for bt, perms in biz_perms.items():
        biz_name = perms[0][0]
        print(f"\n── {biz_name} ──")
        for _, dim_code, org_id, org_name in perms:
            example_idx += 1
            print(f"\n  [{example_idx}] {org_name}")
            print(f"      --biz-type {bt} --filter {dim_code}={org_id}")

    # 4. 生成完整示例
    if perm_summary:
        bt, biz_name, dim_code, org_id, org_name = perm_summary[0]
        print(f"\n{'=' * 60}")
        print("💡 完整查询示例:")
        print("=" * 60)
        # 推荐与业务线匹配的数据集
        matched_ds = []
        for ds_id, affinities in _DATASET_BIZ_AFFINITY.items():
            if bt in affinities:
                matched_ds.append(ds_id)
        if matched_ds:
            ds = matched_ds[0]
            ds_name = _DATASET_NAMES.get(ds, ds)
            print(f"\n  # 查 {ds_name} (数据集 {ds})")
            print("  kdata-fl standard query \\")
            print(f"    --dataset {ds} --measures <指标> \\")
            print(f"    --date 20260401~20260407 --region <Region> \\")
            print(f"    --biz-type {bt} \\")
            print(f"    --filter {dim_code}={org_id}")

    # 5. 数据集可用性
    print(f"\n{'=' * 60}")
    print("📊 数据集可用性:")
    print("=" * 60)

    for ds_id in sorted(_ALLOWED_DATASET_IDS):
        ds_name = _DATASET_NAMES.get(ds_id, "")
        affinities = _DATASET_BIZ_AFFINITY.get(ds_id, [])
        matched = [bt for bt in affinities if bt in user_biz_types]
        if matched:
            biz_str = ", ".join(_BIZ_TYPE_NAMES.get(bt, str(bt)) for bt in matched)
            print(f"  ✅ [{ds_id}] {ds_name}")
            print(f"     可用业务线: {biz_str}")
        else:
            print(f"  ❌ [{ds_id}] {ds_name}")
            print(f"     ⚠️  无匹配的有权限业务线")

    # JSON 输出 —— 恢复 stdout 后输出纯 JSON
    if json_mode:
        sys.stdout = _real_stdout
        result = {
            "mis": mis,
            "bizLines": [
                {
                    "bizType": l["bizType"],
                    "name": _BIZ_TYPE_NAMES.get(l["bizType"], ""),
                }
                for l in lines
            ],
            "permissions": [
                {
                    "bizType": bt,
                    "bizName": bn,
                    "dimCode": dc,
                    "orgId": oid,
                    "orgName": on,
                }
                for bt, bn, dc, oid, on in perm_summary
            ],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))


# ══════════════════════════════════════════════════════════════════════════════
# standard 子命令
# ══════════════════════════════════════════════════════════════════════════════

def _get_standard_client():
    from mtcli_standard_client import MtcliStandardClient
    return MtcliStandardClient()


def _write_output_file(result: dict, output_path: str, measure_descs: dict = None, freshness_warning: str = ""):
    """将查询结果写入文件。根据后缀自动判断格式：.csv/.tsv/.json"""
    import csv as _csv

    columns = result.get("columns", [])
    rows = result.get("rows", [])
    ext = os.path.splitext(output_path)[1].lower()

    if ext == ".json":
        out = {"columns": columns, "rows": rows, "total": result.get("total", len(rows))}
        if measure_descs:
            out["measure_descriptions"] = measure_descs
        if freshness_warning:
            out["freshness_warning"] = freshness_warning
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    elif ext in (".csv", ".tsv"):
        delimiter = "\t" if ext == ".tsv" else ","
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = _csv.writer(f, delimiter=delimiter)
            writer.writerow(columns)
            for row in rows:
                writer.writerow([row.get(c, "") for c in columns])
    else:
        # 默认当 CSV
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = _csv.writer(f)
            writer.writerow(columns)
            for row in rows:
                writer.writerow([row.get(c, "") for c in columns])

    row_count = len(rows)
    print(f"📁 已写入 {output_path}（{row_count} 行，格式: {ext or '.csv'}）")


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


def _cmd_standard_datasets(args):
    items = _get_standard_client().list_datasets(region=args.region)
    # 过滤仅展示白名单内的数据集
    items = [ds for ds in items if str(ds.get("dataSetId", ds.get("id", ""))) in _ALLOWED_DATASET_IDS]
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print(f"共 {len(items)} 个数据集：")
        for ds in items:
            did = ds.get('dataSetId', ds.get('id', ''))
            name = ds.get('dataSetName', ds.get('name', ''))
            print(f"  [{did}] {name}")


def _cmd_standard_measures(args):
    _assert_allowed_dataset(args.dataset)
    items = _get_standard_client().list_measures(args.dataset, search=args.search, locale=args.locale, region=args.region)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print(f"共 {len(items)} 个指标：")
        for m in items:
            desc = m.get("desc") or m.get("description") or ""
            # 口径过长时截断，完整版用 --json
            desc_short = (desc[:80] + "...") if len(desc) > 80 else desc
            print(f"  {m['code']}  {m['name']}")
            if desc_short:
                print(f"    📖 {desc_short}")


def _cmd_standard_dims(args):
    _assert_allowed_dataset(args.dataset)
    items = _get_standard_client().list_dimensions(args.dataset, search=args.search, locale=args.locale, region=args.region)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print(f"共 {len(items)} 个维度：")
        for d in items:
            print(f"  {d['code']}  {d['name']}")


def _cmd_standard_dim_values(args):
    items = _get_standard_client().list_dim_values(args.dim_code, search=args.search, region=args.region)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print(f"共 {len(items)} 个维值：")
        for v in items:
            print(f"  {v}")


# ── 数据就绪检测 ──────────────────────────────────────────────────────────
# 离线数据通常在当地时间早上 7:00 前就绪。
# 如果查询日期范围触及「可能未就绪」的日期，无论结果是否有数据都给出提示。
# - 查包含今天 → 今日数据不会有，提示调整
# - 查包含昨天且当地 < 07:00 → 昨日数据可能未就绪，提示注意
# 多天查询场景：即使前几天有数据，末尾未就绪的天会拉低汇总/导致 WoW 失真。
# 实时数据集不受此限制，跳过检测。

_REGION_TIMEZONE = {
    "HK": "Asia/Hong_Kong",       # UTC+8
    "SA": "Asia/Riyadh",          # UTC+3
    "AE": "Asia/Dubai",           # UTC+4
    "QA": "Asia/Qatar",           # UTC+3
    "KW": "Asia/Kuwait",          # UTC+3
    "BH": "Asia/Bahrain",         # UTC+3
    "BR": "America/Sao_Paulo",    # UTC-3
}

# 实时数据集名称关键词 — 命中任一则跳过就绪检测
_RT_KEYWORDS = ("RT", "实时", "realtime", "Realtime", "盯盘")

# 数据集名称缓存（dataset_id → name），避免重复查询
_dataset_name_cache = {}

def _is_realtime_dataset(dataset_id, region: str = None) -> bool:
    """通过数据集名称关键词判断是否为实时数据集"""
    ds_id = str(dataset_id)
    if ds_id in _dataset_name_cache:
        name = _dataset_name_cache[ds_id]
    else:
        try:
            datasets = _get_standard_client().list_datasets(region=region)
            for d in datasets:
                _dataset_name_cache[str(d["dataSetId"])] = d.get("dataSetName", "")
            name = _dataset_name_cache.get(ds_id, "")
        except Exception:
            return False  # 查不到就保守当离线处理
    return any(kw in name for kw in _RT_KEYWORDS)


def _check_data_freshness(date_range: str, region: str, result: dict, dataset_id=None) -> str:
    """检查查询日期是否触及未就绪日期，返回警告文本或空字符串。实时数据集跳过。"""
    try:
        from datetime import datetime, timezone, timedelta
        import zoneinfo
    except ImportError:
        return ""

    if not date_range or not region:
        return ""

    # 实时数据集不需要就绪检测
    if dataset_id and _is_realtime_dataset(dataset_id, region=region):
        return ""

    # 解析日期范围
    dates = date_range.replace("~", "~").split("~")
    start_date_str = dates[0].strip()
    end_date_str = dates[-1].strip()
    if len(end_date_str) != 8:
        return ""
    try:
        start_date = datetime.strptime(start_date_str, "%Y%m%d").date()
        end_date = datetime.strptime(end_date_str, "%Y%m%d").date()
    except ValueError:
        return ""

    # 获取当地时区
    tz_name = _REGION_TIMEZONE.get(region.upper())
    if not tz_name:
        return ""
    try:
        local_tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        return ""

    now_local = datetime.now(local_tz)
    today_local = now_local.date()
    yesterday_local = today_local - timedelta(days=1)
    local_time_str = now_local.strftime("%H:%M")

    is_range = (start_date != end_date)  # 多天查询

    # Case 1: 日期范围包含今天（今日离线数据不可能有）
    if end_date >= today_local:
        if is_range:
            safe_end = yesterday_local if now_local.hour >= 7 else (yesterday_local - timedelta(days=1))
            return (
                f"数据就绪提醒：查询范围包含今天（{today_local}），离线数据通常在当地时间 07:00 前就绪。"
                f"当前 {region} 当地时间 {local_time_str}，今日数据尚未产出，会导致汇总值偏低 / 环比失真。"
                f"建议将结束日期调整为 {safe_end.strftime('%Y%m%d')}。"
            )
        else:
            return (
                f"数据就绪提醒：查询日期为今天（{today_local}），离线数据通常在当地时间 07:00 前就绪。"
                f"当前 {region} 当地时间 {local_time_str}，今日数据尚未产出。"
                f"建议将日期调整为昨天及之前。"
            )

    # Case 2: 日期范围包含昨天，且当地时间还没到 07:00
    if end_date >= yesterday_local and now_local.hour < 7:
        if is_range:
            safe_end = yesterday_local - timedelta(days=1)
            return (
                f"数据就绪提醒：查询范围包含昨天（{yesterday_local}），离线数据通常在当地时间 07:00 前就绪。"
                f"当前 {region} 当地时间 {local_time_str}（未到 07:00），昨日数据可能未就绪，会导致汇总值偏低 / 环比失真。"
                f"建议将结束日期调整为 {safe_end.strftime('%Y%m%d')}，或等 07:00 后重试。"
            )
        else:
            return (
                f"数据就绪提醒：查询日期为昨天（{yesterday_local}），离线数据通常在当地时间 07:00 前就绪。"
                f"当前 {region} 当地时间 {local_time_str}（未到 07:00），昨日数据可能尚未就绪。"
                f"建议稍后重试，或将日期调整为前天及之前。"
            )

    return ""


def _cmd_standard_query(args):
    _assert_allowed_dataset(args.dataset)
    # ── flatten measures（支持逗号分隔 + 空格分隔混用）───────────────
    args.measures = [m.strip() for raw in args.measures for m in raw.split(",") if m.strip()]

    filters = {}
    if args.filter:
        for f in args.filter:
            if "=" in f:
                k, v = f.split("=", 1)
                filters[k] = [item.strip() for item in v.split(",") if item.strip()]
            else:
                print(f"错误: --filter 格式应为 key=value，收到: {f}", file=sys.stderr)
                sys.exit(1)
    # ── 组织架构权限校验（强制执行，不可跳过）────────────────────────
    _check_org_permission(args, filters)
    # 解析 order_by: "col=ASC" → {"col": "ASC"}
    order_by = None
    if args.order_by:
        if "=" in args.order_by:
            k, v = args.order_by.split("=", 1)
            order_by = {k: v}
        else:
            order_by = {args.order_by: "ASC"}
    result = _get_standard_client().query(
        dataset_id=args.dataset,
        measures=args.measures,
        date_range=args.date,
        region=args.region,
        group_by=args.group_by,
        filters=filters,
        order_by=order_by,
        page_size=args.page_size,
        pops=args.pops.split(",") if args.pops else [],
        locale=args.locale,
        biz_type_str=str(args.biz_type) if getattr(args, "biz_type", None) else None,
    )

    # ── 获取指标口径说明 ─────────────────────────────────────────────
    measure_descs = {}
    try:
        all_measures = _get_standard_client().list_measures(
            args.dataset, locale=args.locale, region=args.region,
        )
        _req = set(args.measures)
        for m in all_measures:
            if m.get("code") in _req:
                _d = m.get("desc") or m.get("description") or ""
                if _d:
                    measure_descs[m["code"]] = {"name": m.get("name", ""), "desc": _d}
    except Exception:
        pass  # 口径获取失败不阻塞主查询

    # ── 数据就绪检测 ─────────────────────────────────────────────────
    freshness_warning = _check_data_freshness(args.date, args.region, result, dataset_id=args.dataset)

    # ── 文件输出 ─────────────────────────────────────────────────────
    output_path = getattr(args, "output", None)
    if output_path:
        _write_output_file(result, output_path, measure_descs, freshness_warning)

    if args.json:
        if measure_descs:
            result["measure_descriptions"] = measure_descs
        if freshness_warning:
            result["freshness_warning"] = freshness_warning
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_table(result)
        if freshness_warning:
            print(f"\n⚠️  {freshness_warning}")
        if measure_descs:
            print("\n📖 指标口径：")
            for code, info in measure_descs.items():
                print(f"  {code}（{info['name']}）: {info['desc']}")


# ══════════════════════════════════════════════════════════════════════════════
# 参数解析器构建
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# [DASHBOARD] 魔数看板路由
# ══════════════════════════════════════════════════════════════════════════════

_DASHBOARD_SKILL_NAME = "bi-query-dashboard-overseas"

# 支持的看板 URL 模式
import re as _re_mod
_DASHBOARD_URL_PATTERNS = [
    _re_mod.compile(r"https?://(?:bi\.keetapp\.com|mdbi\.bi\.st\.keetapp\.com)/v2/xbr/(\d+)"),
    _re_mod.compile(r"https?://(?:bi\.keetapp\.com|mdbi\.bi\.st\.keetapp\.com)/v2/dashboard/(\d+)"),
    _re_mod.compile(r"https?://(?:bi\.keetapp\.com|mdbi\.bi\.st\.keetapp\.com)/dashboard/(\d+)"),
]


def _detect_dashboard_type(url: str) -> str | None:
    """从 URL 判断看板类型：xbr / dashboard-v2 / dashboard-v1 / None"""
    if not url:
        return None
    for i, pat in enumerate(_DASHBOARD_URL_PATTERNS):
        if pat.search(url):
            return ["xbr", "dashboard-v2", "dashboard-v1"][i]
    return None


def _is_dashboard_skill_installed() -> bool:
    return _find_dashboard_skill_md() is not None


def _find_dashboard_skill_md() -> str | None:
    search_dirs = []
    if _CORE_IMPORTED:
        search_dirs.extend(str(path) for path in _SKILL_SEARCH_DIRS)
    search_dirs.extend([
        os.path.expanduser("~/.openclaw/skills"),
        os.path.expanduser("~/.catpaw/skills"),
        os.path.expanduser("~/.codex/skills"),
        os.path.expanduser("~/.keetai/profiles/codex/Default/.codex/skills"),
    ])
    seen = set()
    for base in search_dirs:
        if not base or base in seen:
            continue
        seen.add(base)
        candidate = os.path.join(base, _DASHBOARD_SKILL_NAME, "SKILL.md")
        if os.path.isfile(candidate):
            return candidate
    return None


def _install_dashboard_skill() -> bool:
    """通过 mtskills 安装看板 skill，返回是否成功。"""
    import shutil
    mtskills = shutil.which("mtskills")
    if not mtskills:
        print("⚠️  未找到 mtskills 命令，无法自动安装看板 skill", file=sys.stderr)
        print("   请手动安装：mtskills i bi-query-dashboard-overseas", file=sys.stderr)
        return False
    print(f"📦 正在安装 {_DASHBOARD_SKILL_NAME} ...", file=sys.stderr)
    env = {**os.environ}
    for k in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        env.pop(k, None)
    try:
        r = subprocess.run(
            [mtskills, "i", _DASHBOARD_SKILL_NAME, "-g", "-y"],
            timeout=120, env=env, capture_output=True, text=True,
        )
        if r.returncode == 0 and _is_dashboard_skill_installed():
            print(f"✅ {_DASHBOARD_SKILL_NAME} 安装成功", file=sys.stderr)
            return True
        else:
            print(f"❌ 安装失败 (exit={r.returncode})", file=sys.stderr)
            if r.stderr.strip():
                print(f"   {r.stderr.strip()[:200]}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"❌ 安装异常: {e}", file=sys.stderr)
        return False


def _cmd_dashboard(args):
    """魔数看板取数路由：检测/安装看板 skill → 上报日志 → 输出 Agent 指令。"""
    url = getattr(args, "url", None) or ""
    check_only = getattr(args, "check_only", False)
    dash_type = _detect_dashboard_type(url) if url else None

    # 1. 检测安装状态
    skill_md = _find_dashboard_skill_md()
    installed = skill_md is not None
    if not installed:
        installed = _install_dashboard_skill()
        if not installed:
            print(json.dumps({
                "status": "error",
                "message": f"看板 skill ({_DASHBOARD_SKILL_NAME}) 安装失败，请手动安装后重试",
                "command": f"mtskills i {_DASHBOARD_SKILL_NAME}",
            }, ensure_ascii=False))
            sys.exit(1)
        freshly_installed = True
        skill_md = _find_dashboard_skill_md()
    else:
        freshly_installed = False

    skill_md = skill_md or os.path.join(os.path.expanduser("~/.openclaw/skills"), _DASHBOARD_SKILL_NAME, "SKILL.md")

    if check_only:
        print(json.dumps({
            "status": "ok",
            "installed": True,
            "freshly_installed": freshly_installed,
            "skill_path": skill_md,
        }, ensure_ascii=False))
        return

    # 2. 构造 Agent 指令
    result = {
        "status": "ready",
        "skill_name": _DASHBOARD_SKILL_NAME,
        "skill_path": skill_md,
        "freshly_installed": freshly_installed,
        "url": url or None,
        "dashboard_type": dash_type,
        "instruction": (
            f"看板 skill 已就绪。请立即读取 {skill_md} 并按其流程完成取数。"
            + (f" 用户提供的 URL: {url}" if url else "")
            + (f" (类型: {dash_type})" if dash_type else "")
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ══════════════════════════════════════════════════════════════════════════════
# task / feedback 子命令
# ══════════════════════════════════════════════════════════════════════════════

def _cmd_task_start(args):
    """开始新 task：生成 taskId，记录用户原始输入。"""
    user_input = getattr(args, "input", "") or ""
    if not user_input:
        print("❌ 请通过 --input 提供用户原始问题", file=sys.stderr)
        sys.exit(1)
    mis = getattr(args, "mis", "") or _get_current_mis()
    if not _CORE_IMPORTED:
        import uuid as _uuid
        sid = str(_uuid.uuid4())
        print(f"task_id={sid}")
        print("[task][WARN] core 未导入，仅生成 ID，未上报日志", file=sys.stderr)
        return
    sid = _task_start(user_input, mis=mis)
    print(f"task_id={sid}")


def _cmd_task_end(args):
    """结束 task：记录最终输出。"""
    if not _CORE_IMPORTED:
        print("[task][WARN] core 未导入，跳过 end", file=sys.stderr)
        return
    output = getattr(args, "output", "") or ""
    session_id = getattr(args, "task_id", "") or ""
    mis = getattr(args, "mis", "") or ""
    _task_end(output, mis=mis, task_id=session_id)
    print("✅ task 已结束")


def _cmd_task_status(args):
    """查看当前 task 状态。"""
    if not _CORE_IMPORTED:
        print("(core 未导入，无法查询)")
        return
    status = _get_task_status()
    if getattr(args, "json", False):
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return
    if status.get("status") == "none":
        print("(无活跃 task)")
        return
    sid = status.get("task_id", "")
    desc = status.get("task_desc", "")
    st = status.get("status", "?")
    elapsed = status.get("elapsed_seconds", 0)
    print(f"Task:    {sid[:8]}...")
    print(f"Status:  {st}")
    print(f"Input:   {desc}")
    print(f"Elapsed: {elapsed}s")


def _cmd_feedback(args):
    """上报用户反馈。"""
    if not _CORE_IMPORTED:
        print("[feedback][WARN] core 未导入，跳过反馈上报", file=sys.stderr)
        return
    rating = int(getattr(args, "rating", 0))
    comment = getattr(args, "comment", "") or ""
    feedback_type = getattr(args, "type", "") or "thumbs"
    mis = getattr(args, "mis", "") or _get_current_mis()
    _report_feedback(rating=rating, mis=mis, comment=comment, feedback_type=feedback_type)
    print("✅ feedback 已上报")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kdata-fl",
        description="Keeta 前线数据查询 CLI（仅支持起源标准数据集）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--with-proxy", action="store_true", help="保留 HTTP 代理环境变量")
    parser.add_argument("--locale", default="zh", help="语言枚举: zh / en / pt-BR，默认 zh")
    parser.add_argument("--task-id", default="", help="任务 ID，用于日志关联；不传则自动读取活跃 task")
    parser.add_argument("--task-name", default="", help="任务描述；不传则自动读取活跃 task 输入")

    sub = parser.add_subparsers(dest="group", required=True)

    # ── standard ──────────────────────────────────────────────────────────────
    p_std = sub.add_parser("standard", help="起源标准数据集查询")
    std_sub = p_std.add_subparsers(dest="cmd", required=True)

    p_ds2 = std_sub.add_parser("datasets", help="列出所有数据集")
    p_ds2.add_argument("--region", default="HK")
    p_ds2.set_defaults(func=_cmd_standard_datasets)

    p_m = std_sub.add_parser("measures", help="列出数据集指标")
    p_m.add_argument("--dataset", required=True)
    p_m.add_argument("--search", default=None)
    p_m.add_argument("--region", default="HK")
    p_m.set_defaults(func=_cmd_standard_measures)

    p_dim = std_sub.add_parser("dims", help="列出数据集维度")
    p_dim.add_argument("--dataset", required=True)
    p_dim.add_argument("--search", default=None)
    p_dim.add_argument("--region", default="HK")
    p_dim.set_defaults(func=_cmd_standard_dims)

    p_dv = std_sub.add_parser("dim-values", help="查询维度的可选值")
    p_dv.add_argument("dim_code")
    p_dv.add_argument("--search", default=None)
    p_dv.add_argument("--region", default="HK")
    p_dv.set_defaults(func=_cmd_standard_dim_values)

    p_q = std_sub.add_parser("query", help="查询数据")
    p_q.add_argument("--dataset", required=True)
    p_q.add_argument("--measures", nargs="+", required=True)
    p_q.add_argument("--date", required=True, help="日期或范围，如 20260318 或 20260314~20260320")
    p_q.add_argument("--region", required=True, help="地区 code：HK/SA/AE/QA/KW/BR/BH")
    p_q.add_argument("--group-by", nargs="+", default=None)
    p_q.add_argument("--filter", action="append", default=[], help="过滤条件，格式 key=value，可多次传")
    p_q.add_argument("--order-by", default=None)
    p_q.add_argument("--page-size", type=int, default=50)
    p_q.add_argument("--pops", default=None, help="环比/同比，逗号分隔: dod,wow,mom")
    # ── 组织架构权限校验参数（可选，传入时自动校验权限）──────────────────────
    p_q.add_argument("--biz-type", type=int, default=None,
                     help="组织架构线 ID（传入时自动校验权限）")
    p_q.add_argument("--org-node-type", type=int, default=None,
                     help="层级维度 ID（配合 --biz-type 使用）")
    p_q.add_argument("--org-ids", nargs="+", default=None,
                     help="需要校验的维值列表（配合 --biz-type 使用）")
    # --skip-org-check 已移除，权限校验强制执行
    p_q.add_argument("--output", "-o", default=None,
                     help="输出到文件。根据后缀自动判断格式：.csv → CSV，.json → JSON，.tsv → TSV")
    p_q.set_defaults(func=_cmd_standard_query)

    # ── org ───────────────────────────────────────────────────────────────────
    p_org = sub.add_parser("org", help="组织架构权限查询")
    org_sub = p_org.add_subparsers(dest="cmd", required=True)

    org_sub.add_parser("lines", help="查询当前用户有权限的业务线列表") \
        .set_defaults(func=_cmd_org_lines)

    p_on = org_sub.add_parser("nodes", help="查询业务线下的层级维度列表及权限情况")
    p_on.add_argument("--biz-type", type=int, required=True, dest="biz_type",
                      help="业务线 ID（从 org lines 获取）")
    p_on.set_defaults(func=_cmd_org_nodes)

    p_ov = org_sub.add_parser("values", help="查询指定层级下有权限的维值列表")
    p_ov.add_argument("--biz-type", type=int, required=True, dest="biz_type",
                      help="业务线 ID")
    p_ov.add_argument("--node-type", type=int, required=True, dest="node_type",
                      help="层级维度 ID（从 org nodes 获取）")
    p_ov.add_argument("--org-ids", nargs="+", default=None, dest="org_ids",
                      help="待过滤的维值列表（不传返回全部有权限的维值）")
    p_ov.set_defaults(func=_cmd_org_values)

    p_ovp = org_sub.add_parser("values-permitted",
        help="自动找到业务线下第一个有权限的层级，返回所有有权限的维值")
    p_ovp.add_argument("--biz-type", type=int, required=True, dest="biz_type",
        help="业务线 bizType，如 1278539788")
    p_ovp.set_defaults(func=_cmd_org_values_permitted)

    # ── whoami ────────────────────────────────────────────────────────────────
    p_who = sub.add_parser("whoami", help="一键查看当前用户的完整权限画像 + 推荐查询参数")
    p_who.set_defaults(func=_cmd_whoami)

    # ── dashboard ─────────────────────────────────────────────────────────────
    p_dash = sub.add_parser("dashboard", help="魔数看板取数（自动安装/路由到 bi-query-dashboard-overseas skill）")
    p_dash.add_argument("url", nargs="?", default=None,
                        help="看板 URL，如 https://bi.keetapp.com/v2/xbr/12345")
    p_dash.add_argument("--check-only", action="store_true",
                        help="仅检查看板 skill 安装状态，不执行取数")
    p_dash.set_defaults(func=_cmd_dashboard)

    # ── init ──────────────────────────────────────────────────────────────────
    p_init = sub.add_parser("init", help="初始化 kdata-fl 运行依赖和可选 MIS 兜底")
    p_init.add_argument("--mis", default="", help="用户提供的 MIS 兜底；后续会被 mtcli 获取到的当前 MIS 覆盖")
    p_init.set_defaults(func=cmd_init)

    # ── task ─────────────────────────────────────────────────────────────────
    p_task = sub.add_parser("task", help="Task 生命周期管理（start/end/status）")
    task_sub = p_task.add_subparsers(dest="cmd", required=True)

    p_ts_start = task_sub.add_parser("start", help="开始新 task（记录用户输入）")
    p_ts_start.add_argument("--input", required=True, help="用户原始问题/输入")
    p_ts_start.add_argument("--mis", default="", help="执行人 MIS（不传则自动获取）")
    p_ts_start.set_defaults(func=_cmd_task_start)

    p_ts_end = task_sub.add_parser("end", help="结束 task（记录最终输出）")
    p_ts_end.add_argument("--output", default="", help="最终回答摘要")
    p_ts_end.add_argument("--mis", default="", help="执行人 MIS（不传则自动获取）")
    p_ts_end.set_defaults(func=_cmd_task_end)

    task_sub.add_parser("status", help="查看当前 task 状态").set_defaults(func=_cmd_task_status)

    # ── feedback ─────────────────────────────────────────────────────────────
    p_feedback = sub.add_parser("feedback", help="上报用户反馈（点赞/点踩）")
    p_feedback.add_argument("--rating", type=int, choices=[1, -1], required=True, help="反馈评分：1=有帮助，-1=无帮助")
    p_feedback.add_argument("--comment", default="", help="用户反馈内容")
    p_feedback.add_argument("--type", default="thumbs", help="反馈类型，默认 thumbs")
    p_feedback.add_argument("--mis", default="", help="执行人 MIS（不传则自动获取）")
    p_feedback.set_defaults(func=_cmd_feedback)

    return parser


if _CORE_IMPORTED:
    _KDATA_CONF_DIR = str(_PATH_WORKSPACE_DIR)
    _KDATA_CONF_PATH = str(_PATH_KDATA_CONF)
else:
    _KDATA_CONF_DIR = os.path.expanduser("~/.openclaw/workspace/keeta-data-query-for-front-line")
    _KDATA_CONF_PATH = os.path.join(_KDATA_CONF_DIR, "kdata.conf")


def cmd_init(args):
    """初始化运行依赖和可选 MIS 兜底。"""
    manual_mis = (getattr(args, "mis", "") or "").strip()
    if manual_mis:
        try:
            manual_mis = _set_manual_mis(manual_mis)
        except ValueError as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)

    _install_deps()
    mis = manual_mis or _get_current_mis()
    print("✅ kdata-fl 初始化完成")
    if mis and mis != "unknown":
        source = "用户提供" if manual_mis else "mtcli"
        print(f"  MIS: {mis}（{source}）")
    else:
        print("  MIS: 未获取到。请向用户询问 MIS 后执行：kdata-fl init --mis <MIS>")


# ══════════════════════════════════════════════════════════════════════════════
# 依赖检查
# ══════════════════════════════════════════════════════════════════════════════

_MTCLI_NPM_PKG = "@dp/mtcli"
_NPM_REGISTRY = "http://r.npm.sankuai.com"
_MTCLI_CMD = "mtcli"
_DEPS_CHECK_FILE = os.path.join(_KDATA_CONF_DIR, "deps_checked")
_DEPS_CHECK_INTERVAL = 86400


def _no_proxy_env() -> dict:
    env = {**os.environ}
    for k in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        env.pop(k, None)
    return env


def _npm_install(package: str, env: dict) -> bool:
    import shutil
    npm = shutil.which("npm")
    if not npm:
        return False
    try:
        r = subprocess.run(
            [npm, "install", "-g", package, "--registry", _NPM_REGISTRY],
            timeout=120, env=env, capture_output=True, text=True,
        )
        return r.returncode == 0
    except Exception:
        return False


def _check_deps():
    import shutil
    if shutil.which("npx") is None:
        print("❌ 未找到 npx，请先安装 Node.js", file=sys.stderr)
        sys.exit(1)
    if shutil.which(_MTCLI_CMD) is None:
        env = _no_proxy_env()
        print(f"[kdata-fl] 正在安装依赖 {_MTCLI_NPM_PKG} ...", file=sys.stderr)
        if not _npm_install(_MTCLI_NPM_PKG, env):
            print(
                f"❌ 安装失败，请手动运行：\n"
                f"  npm install -g {_MTCLI_NPM_PKG} --registry {_NPM_REGISTRY}",
                file=sys.stderr,
            )
            sys.exit(1)
    if not os.path.exists(_DEPS_CHECK_FILE):
        _install_deps()
        return
    try:
        last_checked = float(open(_DEPS_CHECK_FILE).read().strip())
    except Exception:
        last_checked = 0.0
    if time.time() - last_checked < _DEPS_CHECK_INTERVAL:
        return
    env = _no_proxy_env()
    subprocess.Popen(
        [sys.executable, "-c",
         f"import subprocess,os,time;"
         f"env={{k:v for k,v in os.environ.items() if k not in ('HTTP_PROXY','http_proxy','HTTPS_PROXY','https_proxy','ALL_PROXY','all_proxy')}};"
         f"r=subprocess.run(['npm','install','-g','{_MTCLI_NPM_PKG}','--registry','{_NPM_REGISTRY}'],timeout=120,env=env,capture_output=True);"
         f"open('{_DEPS_CHECK_FILE}','w').write(str(time.time())) if r.returncode==0 else None"
         ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _install_deps():
    import shutil
    if shutil.which("npx") is None:
        print("❌ 未找到 npx，请先安装 Node.js", file=sys.stderr)
        sys.exit(1)
    env = _no_proxy_env()
    if shutil.which(_MTCLI_CMD) is None:
        print(f"[kdata-fl] 正在安装依赖 {_MTCLI_NPM_PKG} ...", file=sys.stderr)
        if not _npm_install(_MTCLI_NPM_PKG, env):
            print(
                f"❌ 安装失败，请手动运行：\n"
                f"  npm install -g {_MTCLI_NPM_PKG} --registry {_NPM_REGISTRY}",
                file=sys.stderr,
            )
            sys.exit(1)
        print("[kdata-fl] mtcli 依赖安装完成 ✅", file=sys.stderr)
    try:
        os.makedirs(_KDATA_CONF_DIR, exist_ok=True)
        open(_DEPS_CHECK_FILE, "w").write(str(time.time()))
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════════════

def main():
    if _CORE_IMPORTED:
        _ensure_cli_installed()

    parser = _build_parser()
    raw_argv = sys.argv[1:]
    parse_argv, _ = _normalise_argv(raw_argv)
    args = parser.parse_args(parse_argv)
    args._raw_argv = raw_argv

    if not hasattr(args, "json"):
        args.json = False
    if not hasattr(args, "locale"):
        args.locale = "zh"
    if not hasattr(args, "region"):
        args.region = None

    if not getattr(args, "with_proxy", False):
        _unset_proxy()

    if getattr(args, "group", None) == "init":
        args.func(args)
        return

    if getattr(args, "group", None) in ("task", "feedback"):
        try:
            args.func(args)
        except SystemExit as e:
            sys.exit(e.code if isinstance(e.code, int) else 0)
        return

    _check_deps()

    _extra = ":".join([
        os.path.expanduser("~/.local/bin"),
        os.path.expanduser("~/bin"),
        "/usr/local/bin",
    ])
    _parts = os.environ.get("PATH", "/usr/bin:/bin").split(os.pathsep)
    _prepend = [p for p in _extra.split(os.pathsep) if p and p not in _parts]
    if _prepend:
        os.environ["PATH"] = os.pathsep.join(_prepend + _parts)

    _mis = _get_current_mis()
    if _mis == "unknown":
        print(
            "⚠️  未能自动获取您的 MIS 账号，日志将以 unknown 上报。\n"
            "   请告知您的 MIS 或运行：kdata-fl init --mis <your_mis>",
            file=sys.stderr,
        )
    _cli_cmd = _build_cli_command(args, raw_argv)
    _session_id = (
        getattr(args, "task_id", "")
        or os.environ.get("KDATA_SESSION_ID", "")
        or os.environ.get("OPENCLAW_SESSION_ID", "")
    )
    if not _session_id and _CORE_IMPORTED:
        _session_id, _ = _get_active_task()
    if not _session_id and _CORE_IMPORTED:
        _session_id = ""
        print(
            "[kdata-fl] ⚠️ 未检测到活跃 task，日志将使用临时 task。"
            " 建议查询前执行：kdata-fl task start --input \"用户原始问题\"",
            file=sys.stderr,
        )

    _task_desc = getattr(args, "task_name", "").strip() or os.environ.get("KDATA_TASK", "").strip()
    if not _task_desc and _CORE_IMPORTED:
        _, _task_desc = _get_active_task()
    _t0 = time.time()

    import io as _io
    _stdout_capture = _io.StringIO()
    _original_stdout = sys.stdout

    class _TeeWriter:
        def __init__(self, original, capture):
            self._orig = original
            self._cap = capture

        def write(self, s):
            try:
                self._orig.write(s)
            except BrokenPipeError:
                raise
            self._cap.write(s)

        def flush(self):
            self._orig.flush()

        def fileno(self):
            return self._orig.fileno()

        def isatty(self):
            return self._orig.isatty() if hasattr(self._orig, "isatty") else False

        def __getattr__(self, name):
            return getattr(self._orig, name)

    sys.stdout = _TeeWriter(_original_stdout, _stdout_capture)

    _exit_code = 0
    try:
        _result = args.func(args)
    except BrokenPipeError:
        sys.stdout = _original_stdout
        try:
            sys.stdout.flush()
        except Exception:
            pass
        sys.exit(0)
    except SystemExit as e:
        sys.stdout = _original_stdout
        _exit_code = e.code if isinstance(e.code, int) else 0
        _status = "SUCCESS" if _exit_code == 0 else "FAIL"
        _cost = int((time.time() - _t0) * 1000)
        _captured = _stdout_capture.getvalue()
        _report_log(_mis, _cli_cmd, _status, _cost, input_summary=_task_desc,
                    output_summary=_captured if _exit_code == 0 else "",
                    error_msg=f"exit {_exit_code}" if _exit_code else "",
                    session_id=_session_id)
        sys.exit(_exit_code)
    except RuntimeError as e:
        sys.stdout = _original_stdout
        _cost = int((time.time() - _t0) * 1000)
        _report_log(_mis, _cli_cmd, "FAIL", _cost, input_summary=_task_desc,
                    error_msg=str(e), session_id=_session_id)
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.stdout = _original_stdout
        sys.exit(0)
    except Exception as e:
        sys.stdout = _original_stdout
        _cost = int((time.time() - _t0) * 1000)
        _report_log(_mis, _cli_cmd, "FAIL", _cost, input_summary=_task_desc,
                    error_msg=f"uncaught {type(e).__name__}: {e}",
                    session_id=_session_id)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    sys.stdout = _original_stdout
    _cost = int((time.time() - _t0) * 1000)
    _captured = _stdout_capture.getvalue()
    _report_log(
        _mis,
        _cli_cmd,
        "SUCCESS",
        _cost,
        input_summary=_task_desc,
        output_summary=_captured if _captured else "",
        session_id=_session_id,
    )
    if _CORE_IMPORTED:
        try:
            _touch_task()
        except Exception:
            pass


if __name__ == "__main__":
    main()
