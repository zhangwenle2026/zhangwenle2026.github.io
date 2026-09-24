#!/usr/bin/env python3
"""
keeta-data-query 统一认证检查。

业务探活统一通过 mtcli kdata meta 执行，避免脚本直接请求 BI/RAG/Origin/XT
业务接口，也不再从浏览器 Cookie 或 CDP 读取登录态。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any


CAPABILITY_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(CAPABILITY_DIR)
CORE_DIR = os.path.join(SCRIPTS_DIR, "core")
for _path in (SCRIPTS_DIR, CORE_DIR, CAPABILITY_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

try:
    from core.mtcli import run as _mtcli_run
except ImportError:
    from mtcli import run as _mtcli_run

from auth import _mtsso_exchange


STATUS: dict[str, dict[str, Any]] = {}

_ORIGIN_AUDIENCE = "5af3aa3409"
_XT_AUDIENCE = "xt"
_XT_PROBE_TASK = os.getenv("KDATA_AUTH_CHECK_XT_TASK", "hmart_sailor_global.topic_ord_info_d")


def _payload_ok(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return bool(payload)
    if payload.get("success") is False:
        return False
    code = payload.get("code")
    if code is not None:
        try:
            return int(code) in (0, 200)
        except (TypeError, ValueError):
            return str(code).strip().lower() in {"0", "200", "ok", "success"}
    status = str(payload.get("status", "")).strip().lower()
    if status in {"error", "fail", "failed", "failure"}:
        return False
    return True


def _run_mtcli_meta(
    command: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    return _mtcli_run(
        ["kdata", "meta", command],
        params=params,
        headers=headers,
        body=body,
        timeout=timeout,
    )


def _set_ok(name: str, message: str) -> bool:
    STATUS[name] = {"ok": True, "msg": message}
    return True


def _set_fail(name: str, message: str) -> bool:
    STATUS[name] = {"ok": False, "msg": message}
    return False


def _probe_with_mtcli(
    name: str,
    command: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, Any] | None = None,
    timeout: int = 30,
) -> bool:
    try:
        payload = _run_mtcli_meta(command, params=params, headers=headers, timeout=timeout)
    except Exception as exc:
        return _set_fail(name, f"mtcli 探活失败（{command}）: {exc}")
    if not _payload_ok(payload):
        return _set_fail(name, f"mtcli 探活返回异常（{command}）: {payload}")
    return _set_ok(name, f"mtcli 探活成功（{command}）")


def check_bi(fix: bool = False) -> bool:
    del fix
    return _probe_with_mtcli("bi", "bi-hive-spaces", timeout=30)


def check_rag(fix: bool = False) -> bool:
    del fix
    return _probe_with_mtcli(
        "rag",
        "rag-table-search",
        params={"query": "订单宽表", "type": "table"},
        timeout=60,
    )


def _origin_headers(token: str) -> dict[str, str]:
    return {
        "access-token": token,
        "X-BusilineId": "274",
        "x-locale": "zh",
        "x-i18n-lang": "1",
        "x-requested-with": "XMLHttpRequest",
    }


def _origin_params() -> dict[str, Any]:
    return {
        "busiLineId": 274,
        "cn": 1,
        "kpiType": -1,
        "pageNo": 1,
        "pageSize": 1,
        "searchTxt": "gmv",
        "showType": "list",
        "status": -1,
    }


def _probe_origin(name: str) -> bool:
    token = _mtsso_exchange(_ORIGIN_AUDIENCE)
    if not token:
        return _set_fail(name, f"无法获取 Origin access-token（audience={_ORIGIN_AUDIENCE}）")
    return _probe_with_mtcli(
        name,
        "origin-kpi-list",
        params=_origin_params(),
        headers=_origin_headers(token),
        timeout=30,
    )


def check_origin(fix: bool = False) -> bool:
    del fix
    return _probe_origin("origin")


def check_origin_cookie(fix: bool = False) -> bool:
    return check_origin(fix=fix)


def check_origin_token(fix: bool = False) -> bool:
    return check_origin(fix=fix)


def check_xt(fix: bool = False) -> bool:
    del fix
    ok = _probe_with_mtcli(
        "xt",
        "xt-task-info",
        params={"task_name": _XT_PROBE_TASK},
        timeout=30,
    )
    if ok:
        return True

    msg = str(STATUS.get("xt", {}).get("msg") or "").lower()
    if "access-token" not in msg:
        return False

    token = _mtsso_exchange(_XT_AUDIENCE)
    if not token:
        return _set_fail("xt", f"mtcli SSO 探活要求 access-token，但无法获取 XT token（audience={_XT_AUDIENCE}）")

    ok = _probe_with_mtcli(
        "xt",
        "xt-task-info",
        params={"task_name": _XT_PROBE_TASK},
        headers={"access-token": token},
        timeout=30,
    )
    if ok:
        STATUS["xt"]["msg"] += "（服务要求 access-token，已用 mtsso/CIBA token 兼容）"
    return ok


def check_km(fix: bool = False) -> bool:
    name = "km"
    try:
        result = subprocess.run(
            ["oa-skills", "citadel", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return _set_ok(name, "oa-skills citadel CLI 可用（内置自动续期）")
    except FileNotFoundError:
        pass

    if fix:
        try:
            subprocess.run(
                ["npm", "install", "-g", "@it/oa-skills@latest", "--registry=http://r.npm.sankuai.com"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            result = subprocess.run(
                ["oa-skills", "citadel", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return _set_ok(name, "oa-skills 安装成功")
        except Exception as exc:
            return _set_fail(name, f"oa-skills 安装失败: {exc}")

    return _set_fail(
        name,
        "oa-skills 未安装: npm install -g @it/oa-skills@latest --registry=http://r.npm.sankuai.com",
    )


CHECKS = [
    ("bi", check_bi, "魔数BI", "mtcli kdata meta bi-hive-spaces"),
    ("rag", check_rag, "RAG语义", "mtcli kdata meta rag-table-search"),
    ("origin", check_origin, "起源", "mtcli kdata meta origin-kpi-list"),
    ("xt", check_xt, "XT ETL", "mtcli kdata meta xt-task-info"),
    ("km", check_km, "学城KM", "oa-skills citadel CLI"),
]

_KEY_ALIASES = {
    "bi": "bi",
    "rag": "rag",
    "origin": "origin",
    "origin_cookie": "origin",
    "origin_token": "origin",
    "xt": "xt",
    "km": "km",
}


def run(
    fix: bool = False,
    check_only: bool = False,
    targets: list[str] | None = None,
    as_json: bool = False,
) -> bool:
    actual_fix = fix and not check_only
    resolved_targets = [_KEY_ALIASES.get(t, t) for t in targets] if targets else None

    for key, fn, _label, _desc in CHECKS:
        if resolved_targets and key not in resolved_targets:
            continue
        try:
            fn(fix=actual_fix)
        except Exception as exc:
            STATUS[key] = {"ok": False, "msg": f"检查异常: {exc}"}

    if as_json:
        print(json.dumps(STATUS, ensure_ascii=False, indent=2))
        return all(v["ok"] for v in STATUS.values())

    print()
    print("=" * 66)
    print("  keeta-data-query 认证状态")
    print("=" * 66)
    for key, _fn, label, desc in CHECKS:
        if resolved_targets and key not in resolved_targets:
            continue
        info = STATUS.get(key, {})
        icon = "OK" if info.get("ok") else "FAIL"
        msg = info.get("msg", "未检查")
        print(f"  [{icon:<4}] [{label:<8}]  {msg}")
        print(f"             ({desc})")
    print("=" * 66)

    failed = [k for k, v in STATUS.items() if not v["ok"]]
    checked = list(STATUS.keys())
    if not failed:
        print("  所有认证探活正常，keeta-data-query 可正常使用")
    else:
        print(f"  {len(failed)}/{len(checked)} 项异常: {', '.join(failed)}")
        print("  → 请先确认 `mtcli auth sso whoami`，必要时执行 `mtcli auth sso login` 后重试")
    print()
    return not failed


def watch_mode(interval: int = 600) -> None:
    print(f"[WATCH] 持续监控模式，间隔 {interval}s，Ctrl+C 退出")
    while True:
        print(f"\n[WATCH] {time.strftime('%Y-%m-%d %H:%M:%S')} 开始检查...")
        STATUS.clear()
        run(fix=True)
        failed = [k for k, v in STATUS.items() if not v["ok"]]
        if failed:
            print(f"[WATCH] 仍有 {len(failed)} 项失败: {failed}")
        time.sleep(interval)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="keeta-data-query 统一认证检查（业务探活走 mtcli）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 auth_check.py
  python3 auth_check.py --check
  python3 auth_check.py --fix bi rag
  python3 auth_check.py --json
  python3 auth_check.py --watch --interval 300
        """,
    )
    parser.add_argument("--check", action="store_true", help="仅检查，不触发修复")
    parser.add_argument("--fix", action="store_true", help="兼容参数；业务探活仍统一走 mtcli")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--watch", action="store_true", help="持续监控模式")
    parser.add_argument("--interval", type=int, default=600, help="watch 模式间隔秒数")
    parser.add_argument("targets", nargs="*", help="指定检查项：bi rag origin origin_token xt km")
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    if args.watch:
        watch_mode(interval=args.interval)
    else:
        ok = run(
            fix=args.fix,
            check_only=args.check,
            targets=args.targets if args.targets else None,
            as_json=args.json,
        )
        sys.exit(0 if ok else 1)
