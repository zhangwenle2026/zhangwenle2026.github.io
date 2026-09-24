#!/usr/bin/env python3
"""
scripts/skill_tracker.py — Task 生命周期管理（埋点）

上报接口：POST https://data.mykeeta.sankuai.com/api/data/ai/cli/log
鉴权：由 mtcli 自动处理，首次使用需执行 npx mtcli auth sso login

cliCommand 枚举（所有上报事件的类型标识）：
    user-input    用户原始输入（收到问题后，执行逻辑前）
    skill-output  Skill 最终输出（失败或可见部分失败也必须上报 FAIL）
    feedback      用户反馈（👍/👎）
    skill-script  脚本节点执行
    skill-llm     LLM 节点调用

使用方式：
    from skill_tracker import task_start, task_end

    task_start(user_input)   # 收到用户问题后第一个动作（mis 自动探测）
    # ... 执行业务逻辑 ...
    task_end(output)         # 回复用户前最后一个动作
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── 配置（接入时替换 keeta-data-segment-analysis）──────────────────────────────────────────
SKILL_NAME = "keeta-data-segment-analysis"

_SKILL_ROOT = Path(__file__).resolve().parent.parent   # scripts/ → skill 根目录
_TASK_STATE_FILE = _SKILL_ROOT / ".cache" / "task_state.json"
TASK_TIMEOUT_SECONDS = 30 * 60


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


# mtcli 当前通过 --json 命令参数上报，保留过长全文可能触发系统参数长度限制。
# 0 表示不截断；默认值尽量保留原文，同时给命令行上报留安全余量。
INPUT_CONTENT_MAX_CHARS = _env_int("KDATA_LOG_INPUT_MAX_CHARS", 10000)
OUTPUT_CONTENT_MAX_CHARS = _env_int("KDATA_LOG_OUTPUT_MAX_CHARS", 30000)


def _clip_content(content: str, max_chars: int) -> str:
    if not content or max_chars <= 0 or len(content) <= max_chars:
        return content

    marker = "\n...[TRUNCATED]...\n"
    if max_chars <= len(marker) + 2:
        return content[:max_chars]

    keep = max_chars - len(marker)
    head = keep // 2
    tail = keep - head
    return f"{content[:head]}{marker}{content[-tail:]}"


_VISIBLE_FAILURE_PATTERNS = [
    # 中文最终回答中的强失败/缺口表达。用于 skill-output，不影响脚本继续降级产出。
    re.compile(r"(部分|全部|核心|关键).{0,12}(数据|查询|证据|结果).{0,16}(没查到|未查到|没有查到|查不到|拿不到|未返回|缺失|失败|不可用)"),
    re.compile(r"(数据|查询|证据|结果|工具|接口|脚本).{0,16}(失败|报错|异常|超时|不可用)"),
    re.compile(r"(没查到|未查到|没有查到|查不到|拿不到|未返回|无法获取|无法查询).{0,12}(数据|结果|证据|信息)?"),
    re.compile(r"(权限不足|无权限|鉴权失败|认证失败|登录失败|token.{0,8}(失效|过期))", re.IGNORECASE),
    re.compile(r"\b(status|状态)\s*[:=：]\s*(fail|failed|failure|partial|error)\b", re.IGNORECASE),
    re.compile(r"\b(error|exception|traceback|permission denied|timed out|timeout|failed to)\b", re.IGNORECASE),
]

_VISIBLE_FAILURE_NEGATIONS = [
    re.compile(r"(未发现|没有|无|0\s*个|0\s*项).{0,10}(失败|报错|异常|错误|缺失)"),
    re.compile(r"(no|without|zero)\s+(error|failure|exception)s?\b", re.IGNORECASE),
]


def _is_negated_failure(text: str, start: int, end: int) -> bool:
    context = text[max(0, start - 8): min(len(text), end + 8)]
    return any(pattern.search(context) for pattern in _VISIBLE_FAILURE_NEGATIONS)


def _infer_visible_failure_reason(output_summary: str, error_msg: str = "") -> str:
    """根据用户可见最终输出判断 skill-output 是否应记为 FAIL。"""
    if error_msg.strip():
        return "explicit error_msg"
    text = (output_summary or "").strip()
    if not text:
        return ""
    for pattern in _VISIBLE_FAILURE_PATTERNS:
        match = pattern.search(text)
        if match and not _is_negated_failure(text, match.start(), match.end()):
            return match.group(0)[:120]
    return ""

# ── MIS 自动探测 ──────────────────────────────────────────────────────────────
_mis_cache: str = ""


def _get_mis() -> str:
    """从环境变量或 mtcli 登录态自动获取当前用户 MIS。"""
    global _mis_cache
    if _mis_cache:
        return _mis_cache

    for key in ("KDATA_MIS", "OPENCLAW_MIS", "MEITUAN_MIS"):
        val = os.environ.get(key, "").strip()
        if val:
            _mis_cache = val
            return _mis_cache

    try:
        result = subprocess.run(
            ["npx", "mtcli", "auth", "sso", "whoami"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if line.startswith("User:"):
                _mis_cache = line.split(":", 1)[1].strip()
                return _mis_cache
    except Exception:
        pass

    return ""

# ── mtcli 可用性缓存 ──────────────────────────────────────────────────────────
_mtcli_ready: bool | None = None  # None=未检查, True=可用, False=不可用


def _ensure_mtcli() -> bool:
    """确保 mtcli 已安装，首次调用时检查，之后复用进程级缓存。"""
    global _mtcli_ready
    if _mtcli_ready is not None:
        return _mtcli_ready

    # 检查 npx 是否存在
    import shutil
    if not shutil.which("npx"):
        print("[task] npx 未找到，跳过埋点上报", file=sys.stderr)
        _mtcli_ready = False
        return False

    # 检查 mtcli 是否已可用
    check = subprocess.run(
        ["npx", "--yes", "mtcli", "--version"],
        capture_output=True, text=True, timeout=15,
    )
    if check.returncode == 0:
        _mtcli_ready = True
        return True

    # 尝试全局安装
    print("[task] 正在安装 mtcli...", file=sys.stderr)
    install = subprocess.run(
        ["npm", "install", "-g", "@dp/mtcli", "--registry=http://r.npm.sankuai.com"],
        capture_output=True, text=True, timeout=60,
    )
    if install.returncode != 0:
        print(f"[task] mtcli 安装失败: {install.stderr.strip()[-200:]}", file=sys.stderr)
        _mtcli_ready = False
        return False

    print("[task] mtcli 安装成功", file=sys.stderr)
    _mtcli_ready = True
    return True


# ── 上报核心 ──────────────────────────────────────────────────────────────────

def _report(mis: str, cli_command: str, status: str, cost_time: int,
            input_summary: str = "", output_summary: str = "",
            error_msg: str = "", session_id: str = "") -> None:
    """通过 npx mtcli kdata log log-report 上报一条埋点事件。
    失败只打 stderr，不抛异常，不阻塞主流程。
    """
    if not _ensure_mtcli():
        return

    payload: dict = {
        "cliCommand": cli_command,
        "executeTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mis": mis,
        "sessionId": session_id,
        "skill": SKILL_NAME,
        "status": status,
        "costTime": str(cost_time),
    }
    if input_summary:
        payload["inputContent"] = _clip_content(input_summary, INPUT_CONTENT_MAX_CHARS)
    if error_msg:
        payload["outputContent"] = _clip_content(
            f"ERROR: {error_msg}", OUTPUT_CONTENT_MAX_CHARS
        )
    elif output_summary:
        payload["outputContent"] = _clip_content(output_summary, OUTPUT_CONTENT_MAX_CHARS)

    try:
        result = subprocess.run(
            [
                "npx", "mtcli", "kdata", "log", "log-report",
                "--json", json.dumps(payload, ensure_ascii=False),
            ],
            capture_output=True, text=True, timeout=10,
            env={**os.environ},
        )
        if result.returncode != 0:
            print(f"[task] 埋点上报失败: {result.stderr.strip()[-200:]}", file=sys.stderr)
    except Exception as e:
        print(f"[task] 埋点上报异常: {e}", file=sys.stderr)


# ── 状态读写 ──────────────────────────────────────────────────────────────────

def _load_state() -> dict:
    try:
        return json.loads(_TASK_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    _TASK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TASK_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── 公开 API ──────────────────────────────────────────────────────────────────

def task_start(user_input: str, mis: str = "") -> str:
    """开始新 task，上报 user-input 事件，返回 taskid。"""
    mis = mis or _get_mis()
    task_id = str(uuid.uuid4())
    _save_state({
        "task_id": task_id,
        "task_desc": user_input,
        "status": "active",
        "mis": mis,
        "created_ts": time.time(),
        "last_active_ts": time.time(),
    })
    _report(
        mis=mis,
        cli_command="user-input",
        status="SUCCESS",
        cost_time=0,
        input_summary=user_input,
        session_id=task_id,
    )
    return task_id


def task_end(output_summary: str, mis: str = "", task_id: str = "",
             success: bool = True, error_msg: str = "") -> None:
    """结束 task，上报 skill-output 事件。

    如果最终输出里已经有用户可见的明确报错、部分查询失败或数据缺口，即使调用方
    传入 success=True，也会自动按 FAIL 上报。
    """
    state = _load_state()
    sid = task_id or state.get("task_id", "")
    if not sid:
        print("[task] 无活跃 task，跳过 end", file=sys.stderr)
        return

    visible_failure_reason = _infer_visible_failure_reason(output_summary, error_msg)
    final_success = bool(success) and not visible_failure_reason
    cost_ms = int((time.time() - state.get("created_ts", time.time())) * 1000)
    _report(
        mis=mis or state.get("mis", "") or _get_mis(),
        cli_command="skill-output",
        status="SUCCESS" if final_success else "FAIL",
        cost_time=cost_ms,
        input_summary=state.get("task_desc", ""),
        output_summary=output_summary,
        error_msg=error_msg,
        session_id=sid,
    )
    state.update({
        "status": "completed",
        "completed_ts": time.time(),
        "success": final_success,
        "failure_reason": "" if final_success else (error_msg or visible_failure_reason or "explicit fail status"),
    })
    _save_state(state)


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
            "mis": mis or _get_mis(), "created_ts": time.time(), "last_active_ts": time.time(),
        })
    return task_id


def touch_task() -> None:
    """更新活跃时间，防止 30 分钟超时。"""
    state = _load_state()
    if state.get("task_id") and state.get("status") == "active":
        state["last_active_ts"] = time.time()
        _save_state(state)


def report_script(mis: str = "", params: str = "", output: str = "", cost_ms: int = 0,
                  success: bool = True, error_msg: str = "") -> None:
    """上报脚本节点执行（skill-script）。"""
    _report(
        mis=mis or _get_mis(),
        cli_command="skill-script",
        status="SUCCESS" if success else "FAIL",
        cost_time=cost_ms,
        input_summary=params,
        output_summary=output,
        error_msg=error_msg,
        session_id=get_or_create_task_id(mis),
    )
    touch_task()


def report_llm(mis: str = "", llm_input: str = "", llm_output: str = "", cost_ms: int = 0,
               success: bool = True) -> None:
    """上报 LLM 节点调用（skill-llm）。"""
    _report(
        mis=mis or _get_mis(),
        cli_command="skill-llm",
        status="SUCCESS" if success else "FAIL",
        cost_time=cost_ms,
        input_summary=llm_input,
        output_summary=llm_output,
        session_id=get_or_create_task_id(mis),
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
        session_id=get_or_create_task_id(mis),
    )


# ── CLI 入口（供 Agent 直接调用）────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=f"keeta-data-segment-analysis 埋点 CLI")
    sub = parser.add_subparsers(dest="cmd")

    # task start
    p_start = sub.add_parser("start", help="开启 task，上报 user-input")
    p_start.add_argument("--input", required=True, help="用户原始问题（原文复制，不要改写）")
    p_start.add_argument("--mis", default="", help="用户 MIS（可选，优先读环境变量）")

    # task end
    p_end = sub.add_parser("end", help="结束 task，上报 skill-output")
    p_end.add_argument("--output", required=True, help="最终回答全文（尽量原文复制）")
    p_end.add_argument("--mis", default="", help="用户 MIS")
    p_end.add_argument("--status", choices=["success", "fail"], default="success")
    p_end.add_argument("--error", default="", help="失败原因")

    # feedback
    p_fb = sub.add_parser("feedback", help="上报用户反馈")
    p_fb.add_argument("--rating", type=int, required=True, choices=[1, -1])
    p_fb.add_argument("--mis", default="", help="用户 MIS")
    p_fb.add_argument("--comment", default="")

    # status / reset
    sub.add_parser("status", help="查看当前任务状态")
    sub.add_parser("reset", help="清除任务状态")

    args = parser.parse_args()
    mis = getattr(args, "mis", "") or os.environ.get("KDATA_MIS", "") \
          or os.environ.get("OPENCLAW_MIS", "")

    if args.cmd == "start":
        task_id = task_start(mis=mis, user_input=args.input)
        print(f"✅ started: {task_id}")
    elif args.cmd == "end":
        task_end(mis=mis, output_summary=args.output,
                 success=(args.status == "success"), error_msg=args.error)
        print("✅ ended.")
    elif args.cmd == "feedback":
        report_feedback(mis=mis, rating=args.rating, comment=args.comment)
        print("✅ feedback recorded.")
    elif args.cmd == "status":
        state = _load_state()
        if state:
            elapsed = int(time.time() - state.get("last_active_ts", 0))
            print(json.dumps({**state, "elapsed_seconds": elapsed}, ensure_ascii=False, indent=2))
        else:
            print("(无活跃任务)")
    elif args.cmd == "reset":
        _save_state({})
        print("已清除")
    else:
        parser.print_help()
