#!/usr/bin/env python3
"""
org_auth.py — front-line org permission helpers.

The underlying org APIs are exposed by `mtcli kdata standard`, so this module
does not call data-center.mykeeta.com directly or manage SSO cookies.
"""

from __future__ import annotations

import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from mtcli_standard_client import run_standard


_ORG_NODE_DIM_CODE_MAP = {
    # shared region node
    10104238: "global_region_code",
    # Global-区域/蜂窝
    10062119: "org_2_id",
    10062120: "org_3_id",
    10062762: "org_4_id",
    10100190: "org_5_id",
    # Global-SMB-组织
    10270829: "org_2_mis_ids",
    10270830: "org_3_mis_ids",
    10270831: "org_4_mis_ids",
    10270832: "org_5_mis_ids",
    # Global-KASA
    10265037: "org_type_ids",
    10273587: "brand_org_2_mis_ids",
    10273588: "brand_org_3_mis_ids",
    13276426: "brand_org_4_mis_ids",
    # Mega-Long_Tier
    13281930: "long_tail_org_2_mis_ids",
    13281932: "long_tail_org_3_mis_ids",
    # D端 PMM
    10135909: "partner_manager_area_id",
    10135908: "partner_manager_region_id",
    10136618: "partner_manager_group_id",
    10127015: "partner_id",
    10127017: "partner_group_id",
}


def dim_code_for_node(org_node_type: int | str) -> str:
    try:
        key = int(org_node_type)
    except (TypeError, ValueError):
        return ""
    return _ORG_NODE_DIM_CODE_MAP.get(key, "")


def node_type_for_dim_code(dim_code: str) -> int | None:
    for node_type, code in _ORG_NODE_DIM_CODE_MAP.items():
        if code == dim_code:
            return node_type
    return None


def _normalise_value(item: dict) -> dict:
    value = item.get("orgId") or item.get("value") or ""
    text = item.get("orgName") or item.get("text") or item.get("name") or value
    result = dict(item)
    result.setdefault("orgId", value)
    result.setdefault("orgName", text)
    result.setdefault("value", value)
    result.setdefault("text", text)
    return result


def list_org_lines() -> list[dict]:
    return run_standard(["list-org-lines"], timeout=45) or []


def list_org_nodes(biz_type: int, source: int = 999) -> list[dict]:
    body = {"bizType": str(biz_type)}
    if source is not None:
        body["source"] = str(source)
    nodes = run_standard(
        ["list-org-nodes", "--json", json.dumps(body, ensure_ascii=False)],
        timeout=45,
    ) or []
    for node in nodes:
        dim_code = dim_code_for_node(node.get("orgNodeType"))
        if dim_code:
            node["dimCode"] = dim_code
            node["dimCodeField"] = dim_code
    return nodes


def list_org_node_values(
    biz_type: int,
    org_node_type: int,
    org_ids: list[str] | None = None,
    source: int = 999,
) -> list[dict]:
    body: dict = {
        "bizType": int(biz_type),
        "orgNodeType": int(org_node_type),
    }
    if source is not None:
        body["source"] = str(source)
    if org_ids:
        body["orgIds"] = [str(v) for v in org_ids]
    values = run_standard(
        ["list-org-node-values", "--json", json.dumps(body, ensure_ascii=False)],
        timeout=45,
    ) or []
    return [_normalise_value(v) for v in values]


def list_first_permitted_values(biz_type: int, source: int) -> dict | None:
    nodes = list_org_nodes(biz_type, source)
    if not nodes:
        return None

    for node in sorted(nodes, key=lambda n: n.get("level", 0)):
        values = list_org_node_values(biz_type, node["orgNodeType"], source=source)
        permitted = [v for v in values if v.get("hasPermission")]
        if permitted:
            return {
                "orgNodeType": node["orgNodeType"],
                "orgNodeName": node.get("orgNodeName", ""),
                "level": node.get("level", 0),
                "values": [{"value": v["value"], "text": v.get("text", v["value"])} for v in permitted],
            }
    return None


def check_query_permission(
    biz_type: int,
    org_node_type: int | None = None,
    org_ids: list[str] | None = None,
    source: int = 999,
) -> tuple[bool, str]:
    try:
        lines = list_org_lines()
    except RuntimeError as e:
        return False, f"获取业务线权限失败: {e}"

    allowed_biz = {int(line["bizType"]) for line in lines if line.get("bizType") is not None}
    if int(biz_type) not in allowed_biz:
        allowed_names = ", ".join(
            f"{l.get('bizTypeName') or l.get('name', '')}({l.get('bizType')})" for l in lines
        )
        return False, f"您无权限访问业务线 {biz_type}。当前有权限的业务线：{allowed_names or '（无）'}"

    if org_node_type is None:
        return True, ""

    try:
        nodes = list_org_nodes(biz_type, source)
    except RuntimeError as e:
        return False, f"获取层级维度权限失败: {e}"

    node_map = {int(n["orgNodeType"]): n for n in nodes if n.get("orgNodeType") is not None}
    if int(org_node_type) not in node_map:
        return False, f"业务线 {biz_type} 下不存在层级维度 {org_node_type}。"

    if org_ids:
        try:
            allowed_values = list_org_node_values(biz_type, org_node_type, org_ids, source)
        except RuntimeError as e:
            return False, f"获取维值权限失败: {e}"
        allowed_org_ids = {str(v.get("orgId") or v.get("value")) for v in allowed_values if v.get("hasPermission")}
        denied = [str(oid) for oid in org_ids if str(oid) not in allowed_org_ids]
        if denied:
            return False, (
                f"您无权限访问以下维值：{', '.join(denied)}。"
                f"有权限的维值：{', '.join(sorted(allowed_org_ids)) or '（无）'}"
            )

    return True, ""
