#!/usr/bin/env python3
"""
core/task.py — kdata task 生命周期管理（埋点）

埋点通过 `mtcli kdata log log-report` 上报，无需额外鉴权配置。

cliCommand 枚举：
    user-input    用户原始输入
    skill-output  Skill 最终输出（失败也必须上报）
    feedback      用户反馈
    skill-script  脚本节点执行
    skill-llm     LLM 节点调用

公开 API
--------
  task_start(user_input, mis="")    → task_id
  task_input(user_input, mis="")    → task_id
  task_end(output_summary, mis="")  → None
  get_active_task()                 → (task_id, task_desc) or ("", "")
  touch_task()                      → None
  get_task_status()                 → dict
  report_cli_command(cli_command, params, output, cost_ms, ...)
  report_script(params, output, cost_ms, ...)
  report_feedback(rating, ...)
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from core.mis import get_mis as _resolve_mis
    from core.mtcli import run as _mtcli_run
except ImportError:
    from mis import get_mis as _resolve_mis
    from mtcli import run as _mtcli_run

# ── 路径（跨平台，不依赖环境变量）──────────────────────────────────────────
_SKILL_ROOT = Path(__file__).resolve().parent.parent.parent  # core/ → scripts/ → skill根目录
_TASK_STATE_FILE = _SKILL_ROOT / ".cache" / "kdata_task.json"

TASK_TIMEOUT_SECONDS = 30 * 60
MAX_RECORDED_USER_INPUTS = 50

# ── MIS 缓存 ─────────────────────────────────────────────────────────────────
_mis_cache: str = ""

# ── 内部工具 ──────────────────────────────────────────────────────────────────

def _get_mis() -> str:
    """通过 mtcli 获取当前用户 MIS。"""
    global _mis_cache
    if _mis_cache:
        return _mis_cache

    _mis_cache = _resolve_mis(default="")
    return _mis_cache


def _report(mis: str, cli_command: str, status: str, cost_time: int,
            input_summary: str = "", output_summary: str = "",
            error_msg: str = "", session_id: str = "") -> None:
    """通过 mtcli kdata log log-report 上报一条埋点事件。
    失败只打 stderr，不抛异常，不阻塞主流程。
    """
    payload: dict = {
        "cliCommand": cli_command,
        "executeTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mis": mis or _get_mis(),
        "sessionId": session_id,
        "skill": "keeta-data-query",
        "status": status,
        "costTime": str(cost_time),
    }
    if input_summary:
        payload["inputContent"] = input_summary[:2000]
    if error_msg:
        payload["outputContent"] = f"ERROR: {error_msg}"[:500]
    elif output_summary:
        payload["outputContent"] = output_summary[:5000]

    try:
        _mtcli_run(["kdata", "log", "log-report"], body=payload, timeout=10)
    except Exception as e:
        print(f"[task] 埋点上报异常: {e}", file=sys.stderr)


# ── State 读写 ────────────────────────────────────────────────────────────────

def _load_state() -> dict:
    try:
        return json.loads(_TASK_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    _TASK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TASK_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _state_is_active(state: dict) -> bool:
    if not state.get("task_id") or state.get("status") == "completed":
        return False
    return time.time() - state.get("last_active_ts", 0) <= TASK_TIMEOUT_SECONDS


def _state_user_inputs(state: dict) -> list[str]:
    raw_inputs = state.get("user_inputs")
    if isinstance(raw_inputs, list):
        inputs = [str(item) for item in raw_inputs if str(item or "").strip()]
        if inputs:
            return inputs
    task_desc = str(state.get("task_desc") or "").strip()
    return [task_desc] if task_desc else []


def _format_user_inputs(inputs: list[str]) -> str:
    if not inputs:
        return ""
    if len(inputs) == 1:
        return inputs[0]
    return "\n".join(f"用户输入{i}: {text}" for i, text in enumerate(inputs, 1))


def _set_user_inputs(state: dict, inputs: list[str]) -> None:
    cleaned = [str(item) for item in inputs if str(item or "").strip()]
    if len(cleaned) > MAX_RECORDED_USER_INPUTS:
        cleaned = [cleaned[0]] + cleaned[-(MAX_RECORDED_USER_INPUTS - 1):]
    state["user_inputs"] = cleaned
    state["task_desc"] = _format_user_inputs(cleaned)
    state["last_user_input"] = cleaned[-1] if cleaned else ""


# ── 公开 API ──────────────────────────────────────────────────────────────────

def task_start(user_input: str, mis: str = "") -> str:
    """开始新 task，上报 user-input 事件，返回 task_id。"""
    mis = mis or _get_mis()
    task_id = str(uuid.uuid4())
    state = {
        "task_id": task_id,
        "status": "active",
        "mis": mis,
        "created_ts": time.time(),
        "last_active_ts": time.time(),
    }
    _set_user_inputs(state, [user_input])
    _save_state(state)
    _report(
        mis=mis,
        cli_command="user-input",
        status="SUCCESS",
        cost_time=0,
        input_summary=user_input[:2000],
        session_id=task_id,
    )
    return task_id


def task_input(user_input: str, mis: str = "") -> str:
    """记录同一 task 内的后续用户输入，上报 user-input 事件。"""
    mis = mis or _get_mis()
    state = _load_state()
    if not _state_is_active(state):
        return task_start(user_input, mis=mis)

    inputs = _state_user_inputs(state)
    inputs.append(user_input)
    _set_user_inputs(state, inputs)
    state["last_active_ts"] = time.time()
    _save_state(state)

    task_id = state.get("task_id", "")
    _report(
        mis=mis or state.get("mis", "") or _get_mis(),
        cli_command="user-input",
        status="SUCCESS",
        cost_time=0,
        input_summary=user_input[:2000],
        session_id=task_id,
    )
    return task_id


def task_end(output_summary: str, mis: str = "", task_id: str = "",
             success: bool = True, error_msg: str = "") -> None:
    """结束 task，上报 skill-output 事件。失败时也必须调用（success=False）。"""
    state = _load_state()
    sid = task_id or state.get("task_id", "")
    if not sid:
        print("[task][WARN] 无活跃 task，跳过 end", file=sys.stderr)
        return

    cost_ms = int((time.time() - state.get("created_ts", time.time())) * 1000)
    _report(
        mis=mis or state.get("mis", "") or _get_mis(),
        cli_command="skill-output",
        status="SUCCESS" if success else "FAIL",
        cost_time=cost_ms,
        input_summary=_format_user_inputs(_state_user_inputs(state))[:2000],
        output_summary=output_summary[:5000],
        error_msg=error_msg,
        session_id=sid,
    )
    state.update({"status": "completed", "completed_ts": time.time(),
                  "output_summary": output_summary[:500]})
    _save_state(state)


def get_active_task() -> tuple[str, str]:
    """返回当前活跃 task 的 (task_id, task_desc)，过期或无活跃时返回 ("", "")。"""
    state = _load_state()
    if not _state_is_active(state):
        return ("", "")
    return (state["task_id"], _format_user_inputs(_state_user_inputs(state)))


def get_or_create_task_id(mis: str = "") -> str:
    """获取当前 taskid，无活跃 task 时自动生成降级 taskid。"""
    state = _load_state()
    task_id = state.get("task_id", "")
    if not task_id or state.get("status") == "completed" \
            or time.time() - state.get("last_active_ts", 0) > TASK_TIMEOUT_SECONDS:
        task_id = f"auto-{int(time.time() * 1000)}-{uuid.uuid4().hex}"
        print("[task] 自动生成 taskid（建议先调用 task start）", file=sys.stderr)
        _save_state({
            "task_id": task_id, "task_desc": "", "status": "active",
            "user_inputs": [],
            "mis": mis or _get_mis(), "created_ts": time.time(), "last_active_ts": time.time(),
        })
    return task_id


def touch_task() -> None:
    """更新活跃时间，防止 30 分钟超时。"""
    state = _load_state()
    if state.get("task_id") and state.get("status") == "active":
        state["last_active_ts"] = time.time()
        _save_state(state)


def get_task_status() -> dict:
    """返回当前 task 状态信息。"""
    state = _load_state()
    if not state:
        return {"status": "none", "message": "无活跃 task"}
    result = {**state}
    if state.get("last_active_ts"):
        result["elapsed_seconds"] = int(time.time() - state["last_active_ts"])
    return result


def report_script(mis: str = "", params: str = "", output: str = "", cost_ms: int = 0,
                  success: bool = True, error_msg: str = "") -> None:
    """上报脚本节点执行（skill-script）。"""
    _report(
        mis=mis or _get_mis(),
        cli_command="skill-script",
        status="SUCCESS" if success else "FAIL",
        cost_time=cost_ms,
        input_summary=params[:2000],
        output_summary=output[:5000],
        error_msg=error_msg,
        session_id=get_or_create_task_id(),
    )
    touch_task()


def report_cli_command(cli_command: str, mis: str = "", params: str = "",
                       output: str = "", cost_ms: int = 0, success: bool = True,
                       error_msg: str = "", session_id: str = "") -> None:
    """上报 kdata CLI 命令执行，cliCommand 记录真实命令。"""
    _report(
        mis=mis or _get_mis(),
        cli_command=cli_command,
        status="SUCCESS" if success else "FAIL",
        cost_time=cost_ms,
        input_summary=params[:2000],
        output_summary=output[:5000],
        error_msg=error_msg,
        session_id=session_id or get_or_create_task_id(),
    )
    touch_task()


def report_feedback(rating: int, mis: str = "", comment: str = "",
                    feedback_type: str = "thumbs") -> None:
    """上报用户反馈（feedback）。rating: 1=点赞, -1=点踩"""
    _report(
        mis=mis or _get_mis(),
        cli_command="feedback",
        status="SUCCESS",
        cost_time=0,
        input_summary=json.dumps({"rating": rating, "comment": comment,
                                  "type": feedback_type}, ensure_ascii=False),
        session_id=get_or_create_task_id(),
    )


# ── CLI command handlers ─────────────────────────────────────────────────────

def cmd_task_start(args) -> None:
    """CLI handler: start a task and report the user input event."""
    mis = getattr(args, "mis", "") or _get_mis()
    user_input = getattr(args, "input", "") or ""
    if not user_input:
        print("❌ 请通过 --input 提供用户原始问题", file=sys.stderr)
        sys.exit(1)
    task_id = task_start(user_input, mis=mis)
    print(f"task_id={task_id}")


def cmd_task_input(args) -> None:
    """CLI handler: record a user input in the current task."""
    mis = getattr(args, "mis", "") or _get_mis()
    user_input = getattr(args, "input", "") or ""
    if not user_input:
        print("❌ 请通过 --input 提供用户输入", file=sys.stderr)
        sys.exit(1)
    task_id = task_input(user_input, mis=mis)
    print(f"task_id={task_id}")


def cmd_task_end(args) -> None:
    """CLI handler: end the current task and report final output."""
    output = getattr(args, "output", "") or ""
    task_id = getattr(args, "task_id", "") or ""
    task_end(output, task_id=task_id)
    print("✅ task 已结束")


def cmd_task_status(args) -> None:
    """CLI handler: show current task state."""
    status = get_task_status()
    if getattr(args, "json", False):
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return
    if status.get("status") == "none":
        print("(无活跃 task)")
        return

    task_id = status.get("task_id") or status.get("session_id") or "?"
    desc = status.get("task_desc", "")
    state = status.get("status", "?")
    elapsed = status.get("elapsed_seconds", 0)
    print(f"Task:    {task_id[:8]}...")
    print(f"Status:  {state}")
    print(f"Task:    {desc}")
    print(f"Elapsed: {elapsed}s")


def cmd_feedback(args) -> None:
    """CLI handler: report explicit user feedback."""
    rating = int(getattr(args, "rating", 0))
    comment = getattr(args, "comment", "") or ""
    feedback_type = getattr(args, "type", "") or "thumbs"
    mis = getattr(args, "mis", "") or _get_mis()
    report_feedback(rating=rating, mis=mis, comment=comment, feedback_type=feedback_type)
    print("✅ feedback 已上报")
