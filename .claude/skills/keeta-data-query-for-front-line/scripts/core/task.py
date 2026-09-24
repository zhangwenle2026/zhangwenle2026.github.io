#!/usr/bin/env python3
"""Task lifecycle and feedback reporting for kdata-fl."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

try:
    from core.cli_logger import report as _report_log
    from core.mis import get_mis as _resolve_mis
    from core.paths import workspace_state
except ImportError:
    from cli_logger import report as _report_log
    from mis import get_mis as _resolve_mis
    from paths import workspace_state

_TASK_STATE_FILE = workspace_state("kdata_task.json")
_SKILL_NAME = "keeta-data-query-for-front-line"
TASK_TIMEOUT_SECONDS = 30 * 60


def _load_state() -> dict:
    try:
        return json.loads(_TASK_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    _TASK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TASK_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_mis() -> str:
    return _resolve_mis(default="")


def _report(
    *,
    mis: str = "",
    cli_command: str,
    status: str,
    cost_time: int = 0,
    input_summary: str = "",
    output_summary: str = "",
    error_msg: str = "",
    session_id: str = "",
) -> None:
    _report_log(
        mis=mis or _get_mis(),
        cli_command=cli_command,
        status=status,
        cost_time=cost_time,
        input_summary=input_summary,
        output_summary=output_summary,
        error_msg=error_msg,
        session_id=session_id,
        skill=_SKILL_NAME,
    )


def task_start(user_input: str, mis: str = "") -> str:
    """Start a task, persist task state, and report user-input."""
    task_id = str(uuid.uuid4())
    resolved_mis = mis or _get_mis()
    _save_state({
        "task_id": task_id,
        "task_desc": user_input,
        "status": "active",
        "mis": resolved_mis,
        "created_ts": time.time(),
        "last_active_ts": time.time(),
    })
    _report(
        mis=resolved_mis,
        cli_command="user-input",
        status="SUCCESS",
        input_summary=user_input[:2000],
        session_id=task_id,
    )
    return task_id


def task_end(output_summary: str, mis: str = "", task_id: str = "",
             success: bool = True, error_msg: str = "") -> None:
    """End the active task and report skill-output."""
    state = _load_state()
    sid = task_id or state.get("task_id", "")
    if not sid:
        return
    cost_ms = int((time.time() - state.get("created_ts", time.time())) * 1000)
    _report(
        mis=mis or state.get("mis", "") or _get_mis(),
        cli_command="skill-output",
        status="SUCCESS" if success else "FAIL",
        cost_time=cost_ms,
        input_summary=state.get("task_desc", "")[:2000],
        output_summary=output_summary,
        error_msg=error_msg,
        session_id=sid,
    )
    state.update({
        "status": "completed",
        "completed_ts": time.time(),
        "output_summary": output_summary,
    })
    _save_state(state)


def get_active_task() -> tuple[str, str]:
    """Return active task id and description, or empty values if none exists."""
    state = _load_state()
    if not state.get("task_id") or state.get("status") == "completed":
        return ("", "")
    if time.time() - state.get("last_active_ts", 0) > TASK_TIMEOUT_SECONDS:
        return ("", "")
    return (state["task_id"], state.get("task_desc", ""))


def get_or_create_task_id(mis: str = "") -> str:
    """Return active task id, creating a temporary task when needed."""
    state = _load_state()
    task_id = state.get("task_id", "")
    if not task_id or state.get("status") == "completed" \
            or time.time() - state.get("last_active_ts", 0) > TASK_TIMEOUT_SECONDS:
        task_id = f"auto-{int(time.time() * 1000)}-{uuid.uuid4().hex}"
        _save_state({
            "task_id": task_id,
            "task_desc": "",
            "status": "active",
            "mis": mis or _get_mis(),
            "created_ts": time.time(),
            "last_active_ts": time.time(),
        })
    return task_id


def touch_task() -> None:
    """Refresh active task timestamp."""
    state = _load_state()
    if state.get("task_id") and state.get("status") == "active":
        state["last_active_ts"] = time.time()
        _save_state(state)


def get_task_status() -> dict:
    """Return persisted task status."""
    state = _load_state()
    if not state:
        return {"status": "none", "message": "无活跃 task"}
    result = {**state}
    if state.get("last_active_ts"):
        result["elapsed_seconds"] = int(time.time() - state["last_active_ts"])
    return result


def report_cli_command(cli_command: str, mis: str = "", params: str = "",
                       output: str = "", cost_ms: int = 0, success: bool = True,
                       error_msg: str = "", session_id: str = "") -> None:
    """Report a real kdata-fl CLI command. cliCommand must be the actual command."""
    _report(
        mis=mis or _get_mis(),
        cli_command=cli_command,
        status="SUCCESS" if success else "FAIL",
        cost_time=cost_ms,
        input_summary=params[:2000],
        output_summary=output,
        error_msg=error_msg,
        session_id=session_id or get_or_create_task_id(mis=mis),
    )
    touch_task()


def report_feedback(rating: int, mis: str = "", comment: str = "",
                    feedback_type: str = "thumbs") -> None:
    """Report user feedback. rating: 1 = positive, -1 = negative."""
    _report(
        mis=mis or _get_mis(),
        cli_command="feedback",
        status="SUCCESS",
        input_summary=json.dumps(
            {"rating": rating, "comment": comment, "type": feedback_type},
            ensure_ascii=False,
        ),
        session_id=get_or_create_task_id(mis=mis),
    )
    touch_task()
