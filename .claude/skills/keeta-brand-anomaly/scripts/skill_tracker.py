#!/usr/bin/env python3
"""
Privacy-safe Skill telemetry for keeta-brand-anomaly.

This module reports task lifecycle and script-node execution summaries to the
Keeta AI CLI log endpoint through mtcli. It deliberately avoids uploading raw
user prompts, SQL, result rows, report bodies, local paths, tokens, or cookies.

Reported content is limited to safe summaries such as hashes, status, duration,
date/region/brand/module parameters, row counts, query ids, and error categories.
Telemetry failure is always soft-fail and must not block the business workflow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_NAME = "keeta-brand-anomaly"

_SKILL_ROOT = Path(__file__).resolve().parent.parent
_TASK_STATE_FILE = _SKILL_ROOT / ".cache" / "task_state.json"
TASK_TIMEOUT_SECONDS = 30 * 60
MAX_FIELD_CHARS = 500

_mis_cache = ""
_mtcli_ready: bool | None = None

_ALLOWED_PARAM_KEYS = {
    "event",
    "stage",
    "task",
    "label",
    "script",
    "command",
    "date",
    "date_range",
    "region",
    "role",
    "brand_id",
    "brand_name",
    "module",
    "dataset",
    "measure",
    "group_by",
    "task_name",
    "biz_type",
    "dim_code",
    "org_id",
    "limit",
}
_ALLOWED_OUTPUT_KEYS = {
    "event",
    "stage",
    "task",
    "label",
    "status",
    "success",
    "returncode",
    "error_type",
    "query_id",
    "rows",
    "total_num",
    "brands",
    "shops",
    "abnormal_shops",
    "metric_value",
    "wow",
    "pop",
    "module",
    "elapsed_sec",
    "output_hash",
    "output_chars",
    "data_file",
    "narrative_file",
    "final_file",
    "missing_task_start",
}
_REGION_RE = re.compile(r"\b(SA|HK|AE|QA|KW|BR|BH)\b", re.I)
_DATE_RE = re.compile(r"\b20\d{6}(?:~20\d{6})?\b")
_KEY_VALUE_RE = re.compile(r"([A-Za-z_][\w.-]*)=([^\s]+)")


def content_hash(value: Any) -> str:
    """Return a short stable hash for content that must not be uploaded raw."""
    if isinstance(value, (dict, list, tuple)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    else:
        text = "" if value is None else str(value)
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _redact(text: str) -> str:
    if not text:
        return ""
    patterns = [
        r"(?i)(access_token|token|cookie|ssoid|password|secret|authorization)\s*[:=]\s*[^\s,;]+",
        r"(?i)(bearer)\s+[A-Za-z0-9._~+/=-]+",
        r"(?i)(select|with|insert|update|delete)\s+.+",
        r"/Users/[^\s]+",
    ]
    redacted = text
    for pattern in patterns:
        redacted = re.sub(pattern, lambda m: m.group(1) + "=<redacted>" if m.lastindex else "<redacted>", redacted)
    return redacted


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    text = _redact(str(value)).strip()
    if len(text) > 120:
        return {"hash": content_hash(text), "chars": len(text)}
    return text


def _compact_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)[:MAX_FIELD_CHARS]


def _safe_map(data: dict[str, Any], allowed_keys: set[str]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in data.items():
        normalized = key.replace("-", "_")
        if normalized in allowed_keys:
            safe[normalized] = _safe_scalar(value)
    return safe


def _extract_key_values(text: str, allowed_keys: set[str]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in _KEY_VALUE_RE.findall(text):
        normalized = key.replace("-", "_")
        if normalized in allowed_keys:
            safe[normalized] = _safe_scalar(value)
    return safe


def _classify_error(text: str) -> str:
    lower = (text or "").lower()
    if not lower:
        return ""
    checks = [
        ("auth_failed", ("auth", "sso", "401", "403", "token", "login")),
        ("timeout", ("timeout", "timed out", "超时")),
        ("empty_data", ("成功 0", "empty", "no data", "无数据")),
        ("invalid_args", ("usage:", "invalid", "argument", "参数")),
        ("missing_dependency", ("modulenotfounderror", "no module named", "缺失")),
        ("tool_unavailable", ("tls", "handshake", "connection", "network")),
    ]
    for error_type, needles in checks:
        if any(needle in lower for needle in needles):
            return error_type
    return "unknown"


def _intent_tags(user_input: str) -> list[str]:
    text = user_input.lower()
    tags: list[str] = []
    keyword_map = {
        "brand_anomaly": ("品牌", "brand", "异动", "anomaly"),
        "order_drop": ("订单", "order", "下降", "下滑", "波动", "wow"),
        "shop_diagnosis": ("门店", "shop", "门店诊断"),
        "market_overview": ("大盘", "供给大盘", "overview"),
        "operation": ("营业", "在线", "开店", "opening"),
        "experience": ("体验", "出餐", "取消", "cancel", "preparation"),
        "campaign": ("活动", "满折", "折扣", "campaign"),
        "traffic": ("流量", "曝光", "ctr", "feeds", "资源位"),
        "subsidy": ("商补", "补贴", "subsidy"),
    }
    for tag, keywords in keyword_map.items():
        if any(keyword in text for keyword in keywords):
            tags.append(tag)
    return tags[:8]


def _summarize_user_input(user_input: str) -> dict[str, Any]:
    regions = sorted({m.group(1).upper() for m in _REGION_RE.finditer(user_input or "")})
    return {
        "event": "task_start",
        "input_hash": content_hash(user_input),
        "input_chars": len(user_input or ""),
        "contains_date": bool(_DATE_RE.search(user_input or "")),
        "regions": regions[:5],
        "intent_tags": _intent_tags(user_input or ""),
    }


def _summarize_task_output(output: str, success: bool, error_msg: str = "") -> dict[str, Any]:
    summary: dict[str, Any] = {
        "event": "task_end",
        "success": success,
        "output_hash": content_hash(output),
        "output_chars": len(output or ""),
    }
    error_type = _classify_error(error_msg) if error_msg or not success else ""
    if error_type:
        summary["error_type"] = error_type
    return summary


def _summarize_event_content(value: Any, allowed_keys: set[str], event: str) -> dict[str, Any]:
    if isinstance(value, dict):
        safe = _safe_map(value, allowed_keys)
        safe.setdefault("event", event)
        safe.setdefault("input_hash" if allowed_keys is _ALLOWED_PARAM_KEYS else "output_hash", content_hash(value))
        return safe

    text = "" if value is None else str(value)
    safe = _extract_key_values(_redact(text), allowed_keys)
    safe.setdefault("event", event)
    if text:
        hash_key = "input_hash" if allowed_keys is _ALLOWED_PARAM_KEYS else "output_hash"
        chars_key = "input_chars" if allowed_keys is _ALLOWED_PARAM_KEYS else "output_chars"
        safe[hash_key] = content_hash(text)
        safe[chars_key] = len(text)
    return safe


def _session_id(default: str = "") -> str:
    for key in ("CODEX_SESSION_ID", "OPENCLAW_SESSION_ID", "CLAUDE_SESSION_ID", "SESSION_ID"):
        value = os.environ.get(key, "").strip()
        if value:
            return value[:128]
    return default


def _get_mis() -> str:
    global _mis_cache
    if _mis_cache:
        return _mis_cache

    for key in ("KDATA_MIS", "OPENCLAW_MIS", "MEITUAN_MIS"):
        value = os.environ.get(key, "").strip()
        if value:
            _mis_cache = value
            return _mis_cache

    try:
        result = subprocess.run(
            ["npx", "--no-install", "mtcli", "auth", "sso", "whoami"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            if line.startswith("User:"):
                _mis_cache = line.split(":", 1)[1].strip()
                return _mis_cache
    except Exception:
        pass

    return ""


def _ensure_mtcli() -> bool:
    global _mtcli_ready
    if os.environ.get("SKILL_TRACKER_DRY_RUN") == "1":
        return True
    if os.environ.get("SKILL_TRACKER_DISABLE_REPORT") == "1":
        _mtcli_ready = False
        return False
    if _mtcli_ready is not None:
        return _mtcli_ready

    if not shutil.which("npx"):
        print("[task] npx 未找到，跳过埋点上报", file=sys.stderr)
        _mtcli_ready = False
        return False

    try:
        check = subprocess.run(
            ["npx", "--no-install", "mtcli", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        _mtcli_ready = check.returncode == 0
    except Exception:
        _mtcli_ready = False

    if not _mtcli_ready:
        print("[task] mtcli 不可用，跳过埋点上报；请预先安装/登录 mtcli 后再启用", file=sys.stderr)
    return _mtcli_ready


def _report(
    mis: str,
    cli_command: str,
    status: str,
    cost_time: int,
    input_summary: Any = "",
    output_summary: Any = "",
    error_msg: str = "",
    session_id: str = "",
    trace_id: str = "",
) -> None:
    """Report a sanitized telemetry event. Failure never raises."""
    payload: dict[str, Any] = {
        "cliCommand": cli_command,
        "executeTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mis": mis,
        "sessionId": _session_id(session_id or trace_id),
        "traceId": trace_id or session_id,
        "skill": SKILL_NAME,
        "status": status,
        "costTime": int(cost_time),
    }
    if input_summary:
        payload["inputContent"] = (
            _compact_json(input_summary) if isinstance(input_summary, dict) else str(input_summary)[:MAX_FIELD_CHARS]
        )
    if error_msg:
        error_summary = {
            "error_type": _classify_error(error_msg),
            "error_hash": content_hash(error_msg),
        }
        if isinstance(output_summary, dict):
            payload["outputContent"] = _compact_json({**output_summary, **error_summary})
        else:
            payload["outputContent"] = _compact_json(error_summary)
    elif output_summary:
        payload["outputContent"] = (
            _compact_json(output_summary) if isinstance(output_summary, dict) else str(output_summary)[:MAX_FIELD_CHARS]
        )

    if os.environ.get("SKILL_TRACKER_DRY_RUN") == "1":
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return

    if not _ensure_mtcli():
        return

    try:
        result = subprocess.run(
            ["npx", "--no-install", "mtcli", "kdata", "log", "log-report", "--json", json.dumps(payload, ensure_ascii=False)],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ},
        )
        if result.returncode != 0:
            print(f"[task] 埋点上报失败: {result.stderr.strip()[-200:]}", file=sys.stderr)
    except Exception as exc:
        print(f"[task] 埋点上报异常: {exc}", file=sys.stderr)


def _load_state() -> dict[str, Any]:
    try:
        return json.loads(_TASK_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict[str, Any]) -> None:
    _TASK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TASK_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _active_task_state() -> tuple[dict[str, Any], bool]:
    state = _load_state()
    active = bool(
        state.get("task_id")
        and state.get("status") == "active"
        and time.time() - float(state.get("last_active_ts", 0)) <= TASK_TIMEOUT_SECONDS
    )
    return state, active


def _get_active_or_implicit_task(mis: str = "") -> tuple[str, str, bool]:
    state, active = _active_task_state()
    if active:
        return state["task_id"], state.get("session_id", state["task_id"]), False

    task_id = f"implicit-{int(time.time() * 1000)}-{uuid.uuid4().hex[:12]}"
    session_id = _session_id(task_id)
    _save_state({
        "task_id": task_id,
        "session_id": session_id,
        "task_desc_hash": "",
        "status": "active",
        "implicit": True,
        "mis": mis or _get_mis(),
        "created_ts": time.time(),
        "last_active_ts": time.time(),
    })
    print("[task] 未发现 active task，已生成隐式 traceId；建议先调用 start", file=sys.stderr)
    return task_id, session_id, True


def _get_feedback_task(mis: str = "") -> tuple[str, str, bool]:
    state, active = _active_task_state()
    if active:
        return state["task_id"], state.get("session_id", state["task_id"]), False

    completed_ts = float(state.get("completed_ts", state.get("last_active_ts", 0)) or 0)
    if (
        state.get("task_id")
        and state.get("status") == "completed"
        and time.time() - completed_ts <= TASK_TIMEOUT_SECONDS
    ):
        return state["task_id"], state.get("session_id", state["task_id"]), False

    return _get_active_or_implicit_task(mis)


def task_start(user_input: str, mis: str = "") -> str:
    mis = mis or _get_mis()
    task_id = str(uuid.uuid4())
    session_id = _session_id(task_id)
    _save_state({
        "task_id": task_id,
        "session_id": session_id,
        "task_desc_hash": content_hash(user_input),
        "status": "active",
        "implicit": False,
        "mis": mis,
        "created_ts": time.time(),
        "last_active_ts": time.time(),
    })
    _report(
        mis=mis,
        cli_command="user-input",
        status="SUCCESS",
        cost_time=0,
        input_summary=_summarize_user_input(user_input),
        session_id=session_id,
        trace_id=task_id,
    )
    return task_id


def task_end(
    output_summary: str,
    mis: str = "",
    task_id: str = "",
    success: bool = True,
    error_msg: str = "",
) -> None:
    state = _load_state()
    trace_id = task_id or state.get("task_id", "")
    if not trace_id:
        print("[task] 无活跃 task，跳过 end", file=sys.stderr)
        return

    cost_ms = int((time.time() - float(state.get("created_ts", time.time()))) * 1000)
    _report(
        mis=mis or state.get("mis", "") or _get_mis(),
        cli_command="skill-output",
        status="SUCCESS" if success else "FAIL",
        cost_time=cost_ms,
        input_summary={"event": "task_end", "task_desc_hash": state.get("task_desc_hash", "")},
        output_summary=_summarize_task_output(output_summary, success, error_msg),
        error_msg=error_msg,
        session_id=state.get("session_id", trace_id),
        trace_id=trace_id,
    )
    state.update({"status": "completed", "completed_ts": time.time(), "last_active_ts": time.time()})
    _save_state(state)


def get_or_create_task_id(mis: str = "") -> str:
    trace_id, _session, _missing = _get_active_or_implicit_task(mis)
    return trace_id


def touch_task() -> None:
    state = _load_state()
    if state.get("task_id") and state.get("status") == "active":
        state["last_active_ts"] = time.time()
        _save_state(state)


def report_script(
    mis: str = "",
    params: Any = "",
    output: Any = "",
    cost_ms: int = 0,
    success: bool = True,
    error_msg: str = "",
) -> None:
    trace_id, session_id, missing_task_start = _get_active_or_implicit_task(mis)
    input_summary = _summarize_event_content(params, _ALLOWED_PARAM_KEYS, "skill-script")
    output_summary = _summarize_event_content(output, _ALLOWED_OUTPUT_KEYS, "skill-script")
    output_summary["success"] = success
    if missing_task_start:
        output_summary["missing_task_start"] = True
    if error_msg:
        output_summary["error_type"] = _classify_error(error_msg)

    _report(
        mis=mis or _get_mis(),
        cli_command="skill-script",
        status="SUCCESS" if success else "FAIL",
        cost_time=cost_ms,
        input_summary=input_summary,
        output_summary=output_summary,
        error_msg=error_msg,
        session_id=session_id,
        trace_id=trace_id,
    )
    touch_task()


def report_llm(
    mis: str = "",
    llm_input: Any = "",
    llm_output: Any = "",
    cost_ms: int = 0,
    success: bool = True,
    error_msg: str = "",
) -> None:
    trace_id, session_id, missing_task_start = _get_active_or_implicit_task(mis)
    input_summary = {
        "event": "skill-llm",
        "input_hash": content_hash(llm_input),
        "input_chars": len(str(llm_input or "")),
    }
    output_summary = {
        "event": "skill-llm",
        "success": success,
        "output_hash": content_hash(llm_output),
        "output_chars": len(str(llm_output or "")),
    }
    if missing_task_start:
        output_summary["missing_task_start"] = True
    if error_msg:
        output_summary["error_type"] = _classify_error(error_msg)

    _report(
        mis=mis or _get_mis(),
        cli_command="skill-llm",
        status="SUCCESS" if success else "FAIL",
        cost_time=cost_ms,
        input_summary=input_summary,
        output_summary=output_summary,
        error_msg=error_msg,
        session_id=session_id,
        trace_id=trace_id,
    )
    touch_task()


def report_feedback(
    rating: int,
    mis: str = "",
    comment: str = "",
    feedback_type: str = "thumbs",
) -> None:
    trace_id, session_id, missing_task_start = _get_feedback_task(mis)
    input_summary = {
        "event": "feedback",
        "rating": rating,
        "type": feedback_type,
        "comment_hash": content_hash(comment) if comment else "",
        "comment_chars": len(comment or ""),
    }
    if missing_task_start:
        input_summary["missing_task_start"] = True
    _report(
        mis=mis or _get_mis(),
        cli_command="feedback",
        status="SUCCESS",
        cost_time=0,
        input_summary=input_summary,
        session_id=session_id,
        trace_id=trace_id,
    )
    touch_task()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"{SKILL_NAME} privacy-safe telemetry CLI")
    parser.add_argument("--dry-run", action="store_true", help="只打印脱敏 payload，不调用 mtcli")
    sub = parser.add_subparsers(dest="cmd")

    p_start = sub.add_parser("start", help="开启 task，上报脱敏 user-input 摘要")
    p_start.add_argument("--input", required=True, help="用户原始问题，原文复制，不要改写；仅在本地计算 hash/标签，不原文上报")
    p_start.add_argument("--mis", default="", help="用户 MIS（可选，优先读环境变量）")

    p_end = sub.add_parser("end", help="结束 task，上报脱敏 skill-output 摘要")
    p_end.add_argument("--output", required=True, help="最终回答；仅在本地计算 hash/长度，不原文上报")
    p_end.add_argument("--mis", default="", help="用户 MIS")
    p_end.add_argument("--status", choices=["success", "fail"], default="success")
    p_end.add_argument("--error", default="", help="失败原因；仅上报错误类型和 hash")

    p_feedback = sub.add_parser("feedback", help="上报脱敏用户反馈摘要")
    p_feedback.add_argument("--rating", type=int, required=True, choices=[1, -1])
    p_feedback.add_argument("--mis", default="", help="用户 MIS")
    p_feedback.add_argument("--comment", default="", help="反馈内容；仅上报 hash/长度")

    sub.add_parser("status", help="查看当前任务状态")
    sub.add_parser("reset", help="清除任务状态")
    sub.add_parser("self-test", help="生成一组 dry-run 脱敏 payload 用于验收")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.dry_run or args.cmd == "self-test":
        os.environ["SKILL_TRACKER_DRY_RUN"] = "1"

    mis = getattr(args, "mis", "") or os.environ.get("KDATA_MIS", "") or os.environ.get("OPENCLAW_MIS", "")

    if args.cmd == "start":
        task_id = task_start(user_input=args.input, mis=mis)
        print(task_id)
    elif args.cmd == "end":
        task_end(output_summary=args.output, mis=mis, success=(args.status == "success"), error_msg=args.error)
        print("ended")
    elif args.cmd == "feedback":
        report_feedback(rating=args.rating, mis=mis, comment=args.comment)
        print("feedback recorded")
    elif args.cmd == "status":
        state = _load_state()
        if state:
            elapsed = int(time.time() - float(state.get("last_active_ts", 0)))
            printable = {k: v for k, v in state.items() if k != "task_desc"}
            print(json.dumps({**printable, "elapsed_seconds": elapsed}, ensure_ascii=False, indent=2))
        else:
            print("(无活跃任务)")
    elif args.cmd == "reset":
        _save_state({})
        print("已清除")
    elif args.cmd == "self-test":
        task_start("分析 20260601 SA KFC 品牌订单异动原因", mis=mis)
        report_script(
            params={
                "event": "self_test",
                "script": "kdata",
                "date": "20260601",
                "region": "SA",
                "brand_name": "KFC",
                "module": "overview",
                "dataset": "62059636",
            },
            output={"event": "self_test", "rows": 3, "elapsed_sec": 0.1, "query_id": "dry-run"},
            cost_ms=100,
            success=True,
        )
        task_end("self-test ok", mis=mis)
        print("self-test completed")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
