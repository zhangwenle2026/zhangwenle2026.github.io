#!/usr/bin/env python3
"""
MtcliStandardClient — front-line standard dataset client.

All standard dataset calls are delegated to `npx mtcli kdata standard ...` so the
skill does not need to manage data-center SSO cookies by itself.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any


def _mtcli_cmd() -> list[str]:
    mtcli = shutil.which("mtcli")
    if mtcli:
        return [mtcli]
    return [shutil.which("npx") or "npx", "mtcli"]


def _no_proxy_env() -> dict:
    drop = {"HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"}
    return {k: v for k, v in os.environ.items() if k not in drop}


def _unwrap_payload(payload: dict) -> Any:
    if not payload.get("success", False):
        raise RuntimeError(f"mtcli 返回错误: {payload.get('message') or payload}")

    data = payload.get("data")
    if isinstance(data, dict) and ("code" in data or "success" in data):
        if data.get("success") is False or data.get("code", 0) not in (0, None):
            raise RuntimeError(f"mtcli 返回错误: {data.get('message') or data}")
        return data.get("data")
    return data


def run_standard(args: list[str], timeout: int = 30) -> Any:
    result = subprocess.run(
        _mtcli_cmd() + ["kdata", "standard"] + args + ["--output", "json"],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_no_proxy_env(),
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"mtcli 命令失败: {msg[-500:]}")
    try:
        payload = json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        raise RuntimeError(f"mtcli 输出解析失败: {e}\n{result.stdout[:300]}")
    return _unwrap_payload(payload)


def _flatten_columns(col_list: list) -> list[str]:
    keys: list[str] = []
    for c in col_list:
        children = c.get("children")
        if children:
            keys.extend(_flatten_columns(children))
        else:
            keys.append(c["key"])
    return keys


class MtcliStandardClient:
    def list_datasets(self, locale=None, region=None) -> list:
        return run_standard(["datasets"], timeout=45) or []

    def list_measures(self, dataset_id, search=None, locale=None, region=None) -> list:
        args = ["measures", "--dataSetId", str(dataset_id)]
        if locale:
            args += ["--locale", locale]
        items = run_standard(args, timeout=45) or []
        if search:
            kw = str(search).lower()
            items = [
                m for m in items
                if kw in str(m.get("name", "")).lower()
                or kw in str(m.get("code", "")).lower()
                or kw in str(m.get("desc", "")).lower()
            ]
        return items

    def list_dimensions(self, dataset_id, search=None, locale=None, region=None) -> list:
        items = run_standard(
            ["dims-by-dataset", "--dataSetId", str(dataset_id)],
            timeout=45,
        ) or []
        if search:
            kw = str(search).lower()
            items = [
                d for d in items
                if kw in str(d.get("name", "")).lower()
                or kw in str(d.get("code", "")).lower()
                or kw in str(d.get("desc", "")).lower()
            ]
        return items

    def list_dim_values(self, dim_code, dataset_id=None, search=None, locale=None, region=None) -> list:
        args = ["dim-values", "--dimCode", str(dim_code)]
        if search:
            args += ["--keyword", str(search)]
        raw = run_standard(args, timeout=45) or {}
        if isinstance(raw, dict):
            return raw.get("data", []) or []
        return raw if isinstance(raw, list) else []

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
        biz_type_str=None,
    ) -> dict:
        if not region:
            raise ValueError("region 必须指定（SA/HK/AE/QA/KW/BR/BH）")

        ext: dict[str, Any] = {"locale": locale or "zh", "region": region}
        if biz_type_str:
            ext["bizTypeStr"] = str(biz_type_str)
        sender_uid = os.environ.get("KDATA_SENDER_UID", "").strip()
        if sender_uid:
            ext["groupAssistantId"] = "4061856271"
            ext["senderUid"] = sender_uid

        body: dict[str, Any] = {
            "queryEngineSource": 2,
            "dataSourceId": str(dataset_id),
            "measureCodeList": list(measures or []),
            "dateFilters": [{"code": "dt", "values": [date_range]}],
            "pagination": {"pageNum": 1, "pageSize": page_size},
            "ext": ext,
        }
        if filters:
            body["filters"] = [
                [{"code": k, "values": v if isinstance(v, list) else [v]}]
                for k, v in filters.items()
            ] if isinstance(filters, dict) else filters
        if group_by:
            body["groupBy"] = group_by if isinstance(group_by, list) else [group_by]
        if order_by:
            body["orderBy"] = order_by
        if pops:
            body["pops"] = pops

        inner = run_standard(
            ["query", "--json", json.dumps(body, ensure_ascii=False)],
            timeout=90,
        ) or {}
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
