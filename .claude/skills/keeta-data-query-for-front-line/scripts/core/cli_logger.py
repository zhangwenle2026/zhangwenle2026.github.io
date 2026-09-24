#!/usr/bin/env python3
"""
core/cli_logger.py — CLI log reporter backed by mtcli.

Logs are reported through:
  mtcli kdata log log-report --json '<payload>'

Reporting failures are non-blocking.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

_MTCLI_NPM_PKG = "@dp/mtcli"
_NPM_REGISTRY = "http://r.npm.sankuai.com"
_mtcli_ready: bool | None = None


def _no_proxy_env() -> dict:
    drop = {"HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"}
    return {k: v for k, v in os.environ.items() if k not in drop}


def _mtcli_cmd() -> list[str]:
    mtcli = shutil.which("mtcli")
    if mtcli:
        return [mtcli]
    return [shutil.which("npx") or "npx", "mtcli"]


def _ensure_mtcli() -> bool:
    global _mtcli_ready
    if _mtcli_ready is not None:
        return _mtcli_ready

    cmd = _mtcli_cmd()
    try:
        check = subprocess.run(
            cmd + ["--version"],
            capture_output=True,
            text=True,
            timeout=15,
            env=_no_proxy_env(),
        )
        if check.returncode == 0:
            _mtcli_ready = True
            return True
    except Exception:
        pass

    npm = shutil.which("npm")
    if not npm:
        print("[cli_logger] npm 未找到，跳过埋点上报", file=sys.stderr)
        _mtcli_ready = False
        return False

    print("[cli_logger] 正在安装 mtcli...", file=sys.stderr)
    try:
        install = subprocess.run(
            [npm, "install", "-g", _MTCLI_NPM_PKG, "--registry", _NPM_REGISTRY],
            capture_output=True,
            text=True,
            timeout=120,
            env=_no_proxy_env(),
        )
    except Exception as e:
        print(f"[cli_logger] mtcli 安装异常: {e}", file=sys.stderr)
        _mtcli_ready = False
        return False

    if install.returncode != 0:
        print(f"[cli_logger] mtcli 安装失败: {install.stderr.strip()[-200:]}", file=sys.stderr)
        _mtcli_ready = False
        return False

    _mtcli_ready = True
    return True


def report(
    mis: str,
    cli_command: str,
    status: str,
    cost_time: int,
    *,
    input_summary: str = "",
    output_summary: str = "",
    error_msg: str = "",
    session_id: str = "",
    skill: str = "keeta-data-query-for-front-line",
) -> None:
    if not _ensure_mtcli():
        return

    payload: dict = {
        "cliCommand": cli_command,
        "executeTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mis": mis,
        "sessionId": session_id,
        "skill": skill,
        "status": status,
        "costTime": str(cost_time),
    }
    if input_summary:
        payload["inputContent"] = input_summary[:2000]
    if error_msg:
        payload["outputContent"] = f"ERROR: {error_msg}"
    elif output_summary:
        payload["outputContent"] = output_summary

    try:
        result = subprocess.run(
            _mtcli_cmd() + ["kdata", "log", "log-report", "--json", json.dumps(payload, ensure_ascii=False)],
            capture_output=True,
            text=True,
            timeout=10,
            env=_no_proxy_env(),
        )
        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip()
            print(f"[cli_logger][WARN] mtcli 上报失败: {msg[-200:]}", file=sys.stderr)
    except Exception as e:
        print(f"[cli_logger][WARN] mtcli 上报异常: {e}", file=sys.stderr)
