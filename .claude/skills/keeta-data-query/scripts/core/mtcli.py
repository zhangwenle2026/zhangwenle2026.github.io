#!/usr/bin/env python3
"""Small mtcli runner used by kdata capabilities."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

MTCLI_NPM_PACKAGE = "@dp/mtcli"
NPM_REGISTRY = "http://r.npm.sankuai.com"
MTCLI_BIN = "mtcli"


def _no_proxy_env() -> dict[str, str]:
    drop = {"HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"}
    return {k: v for k, v in os.environ.items() if k not in drop}


def npx_mtcli_prefix(npx: str | None = None) -> list[str]:
    npx_cmd = npx or shutil.which("npx") or "npx"
    return [
        npx_cmd,
        "--yes",
        "--package",
        MTCLI_NPM_PACKAGE,
        "--registry",
        NPM_REGISTRY,
        MTCLI_BIN,
    ]


def _unwrap_output_json(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    if "status_code" not in payload or "data" not in payload:
        return payload
    if payload.get("success") is False:
        raise RuntimeError(f"mtcli 返回错误: {payload.get('message') or payload}")
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def _command_prefix() -> list[str]:
    mtcli = shutil.which(MTCLI_BIN)
    if mtcli:
        return [mtcli]
    return npx_mtcli_prefix()


def run(
    args: list[str],
    *,
    body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    headers: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Run an mtcli command and return parsed JSON output."""
    cmd = _command_prefix() + list(args)
    if params:
        cmd += ["--params", json.dumps(params, ensure_ascii=False)]
    if headers:
        cmd += ["--headers", json.dumps(headers, ensure_ascii=False)]
    if body is not None:
        cmd += ["--json", json.dumps(body, ensure_ascii=False)]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_no_proxy_env(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"mtcli 命令失败: {result.stderr.strip()[-500:]}")

    raw = result.stdout.strip()
    if not raw:
        raise RuntimeError("mtcli 输出为空")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"mtcli 输出解析失败: {exc}\n{raw[:500]}") from exc

    payload = _unwrap_output_json(payload)
    if isinstance(payload, dict) and payload.get("success") is False:
        raise RuntimeError(f"mtcli 返回错误: {payload.get('message') or payload}")
    return payload
