#!/usr/bin/env python3
"""AI CLI log helper backed by mtcli.

Usage:
  cli_log.py write --mis <mis> --command <cmd> --status SUCCESS|FAIL [options]

The write path reports through:
  mtcli kdata log log-report --json '<payload>'
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

_MTCLI_NPM_PKG = "@dp/mtcli"
_NPM_REGISTRY = "http://r.npm.sankuai.com"


def _no_proxy_env() -> dict:
    drop = {"HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"}
    return {k: v for k, v in os.environ.items() if k not in drop}


def _mtcli_cmd() -> list[str]:
    mtcli = shutil.which("mtcli")
    if mtcli:
        return [mtcli]
    return [shutil.which("npx") or "npx", "mtcli"]


def _ensure_mtcli() -> bool:
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
            return True
    except Exception:
        pass

    npm = shutil.which("npm")
    if not npm:
        print("❌ 未找到 npm，无法安装 mtcli", file=sys.stderr)
        return False

    print("[cli_log] 正在安装 mtcli...", file=sys.stderr)
    try:
        install = subprocess.run(
            [npm, "install", "-g", _MTCLI_NPM_PKG, "--registry", _NPM_REGISTRY],
            capture_output=True,
            text=True,
            timeout=120,
            env=_no_proxy_env(),
        )
    except Exception as e:
        print(f"❌ mtcli 安装异常: {e}", file=sys.stderr)
        return False

    if install.returncode != 0:
        print(f"❌ mtcli 安装失败: {install.stderr.strip()[-300:]}", file=sys.stderr)
        return False
    return True


def write_log(args) -> None:
    if not _ensure_mtcli():
        sys.exit(1)

    payload = {
        "mis": args.mis,
        "cliCommand": args.command,
        "status": args.status,
        "executeTime": args.execute_time or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if args.input_content:
        payload["inputContent"] = args.input_content[:2000]
    if args.output_content:
        payload["outputContent"] = args.output_content
    if args.cost_time is not None:
        payload["costTime"] = str(args.cost_time)
    if args.trace_id:
        payload["traceId"] = args.trace_id
    if args.skill:
        payload["skill"] = args.skill
    if args.session_id:
        payload["sessionId"] = args.session_id

    result = subprocess.run(
        _mtcli_cmd() + ["kdata", "log", "log-report", "--json", json.dumps(payload, ensure_ascii=False)],
        capture_output=True,
        text=True,
        timeout=30,
        env=_no_proxy_env(),
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        print(f"❌ 日志写入失败: {msg[-500:]}", file=sys.stderr)
        sys.exit(result.returncode)
    print("✅ 日志写入成功")


def query_logs(_args) -> None:
    print("❌ cli_log.py query 已废弃，请通过 mtcli 或日志平台查询 CLI 日志。", file=sys.stderr)
    sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli_log",
        description="AI CLI 执行日志写入工具",
    )
    parser.add_argument("--json", action="store_true", help="兼容旧参数，write 不使用")
    sub = parser.add_subparsers(dest="cmd")

    wp = sub.add_parser("write", help="写入执行日志")
    wp.add_argument("--mis", required=True, help="执行人 MIS ID")
    wp.add_argument("--command", required=True, help="CLI 指令/命令名称")
    wp.add_argument("--status", required=True, choices=["SUCCESS", "FAIL"], help="执行状态")
    wp.add_argument("--execute-time", help="执行时间，默认当前 UTC 时间")
    wp.add_argument("--input-content", help="输入内容")
    wp.add_argument("--output-content", help="输出内容")
    wp.add_argument("--cost-time", type=int, help="执行耗时（ms）")
    wp.add_argument("--trace-id", help="Trace ID")
    wp.add_argument("--skill", default="keeta-data-query-for-front-line", help="Skill 名称")
    wp.add_argument("--session-id", help="对话 Session ID")

    qp = sub.add_parser("query", help="已废弃：请通过 mtcli 或日志平台查询")
    qp.set_defaults(func=query_logs)
    wp.set_defaults(func=write_log)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
