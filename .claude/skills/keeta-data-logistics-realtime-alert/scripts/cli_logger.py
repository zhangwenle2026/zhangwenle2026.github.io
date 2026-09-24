"""
scripts/cli_logger.py — keeta-data-logistics-realtime-alert 埋点上报模块

上报到 data.mykeeta.sankuai.com/api/data/ai/cli/log
认证：sso-auth-cli → mtsso-moa-local-exchange → 文件缓存 token（跨进程复用）
发送：daemon thread + atexit join，不阻塞 cron 主流程，进程退出前等待上报完成
降级：任何失败只 print WARN，不抛异常，不影响告警执行
"""
from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

# 追踪所有待完成的上报线程，atexit 时统一 join
_pending_threads: list[threading.Thread] = []
_threads_lock = threading.Lock()


def _atexit_join_threads() -> None:
    """进程退出前等待所有上报线程完成，总预算 5s（不是每线程 5s）。

    F2 等高频场景会启动 7-8 个 kdata 节点上报线程，openclaw cron 有 90s 超时限制；
    用总预算而非逐线程 timeout 确保 atexit 额外开销 ≤ 5s。
    """
    with _threads_lock:
        threads = list(_pending_threads)
    deadline = time.time() + 5
    for t in threads:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        t.join(timeout=remaining)

_LOG_BASE_URL = "https://data.mykeeta.sankuai.com"
_LOG_API_PATH = "/api/data/ai/cli/log"
_LOG_AUDIENCE = "6bde082970"
_SKILL_NAME   = "keeta-data-logistics-realtime-alert"

# 文件缓存路径（跨进程复用 token）
_TOKEN_CACHE_FILE = Path(tempfile.gettempdir()) / "cli_logger_token_6bde082970.json"


# ── token 获取 ────────────────────────────────────────────────────────────────

def _get_token() -> str:
    """获取 SSO token，优先文件缓存，缓存失效依次尝试 sso-auth-cli → mtsso。"""
    now = time.time()

    # 读文件缓存
    try:
        if _TOKEN_CACHE_FILE.exists():
            cached = json.loads(_TOKEN_CACHE_FILE.read_text())
            if cached.get("expires_at", 0) - now > 60:
                return cached["token"]
    except Exception:
        pass

    env = {k: v for k, v in os.environ.items()
           if k not in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy",
                        "ALL_PROXY", "all_proxy")}

    def _save_token(tok: str, expires_in: int = 10800) -> None:
        """原子写入 token 缓存（tmp + rename，防止并发撕裂）。"""
        _tmp = _TOKEN_CACHE_FILE.with_suffix(".json.tmp")
        _tmp.write_text(json.dumps({"token": tok, "expires_at": now + expires_in}))
        _tmp.replace(_TOKEN_CACHE_FILE)

    # ── 方案1：sso-auth-cli（本机交互式环境通用，输出 "{audience}_ssoid={token}"）──
    # timeout=5s：cron isolated session 中 Chrome 通常不运行，快速失败比长等待更好。
    try:
        r = subprocess.run(
            ["sso-auth-cli", _LOG_AUDIENCE, "--cookie"],
            capture_output=True, text=True, timeout=5, env=env,
        )
        if r.returncode == 0:
            line = r.stdout.strip()
            if "=" in line:
                token = line.split("=", 1)[1].strip()
                if token:
                    _save_token(token)
                    return token
    except FileNotFoundError:
        pass  # sso-auth-cli 不存在，尝试下一种方式
    except Exception as e:
        print(f"[cli_logger][WARN] sso-auth-cli 异常: {e}", file=sys.stderr)

    # ── 方案2：mtsso-moa-local-exchange（openclaw cron 环境，需 AGENT_SSO_CLIENT_ID）──
    # timeout=3s：AGENT_SSO_CLIENT_ID 不存在时 mtsso 应立即失败；
    # 若 npx 需要下载包则可能慢，但上报是非核心，宁可跳过也不拖慢主流程。
    try:
        r = subprocess.run(
            ["npx", "mtsso-moa-local-exchange", "--audience", _LOG_AUDIENCE],
            capture_output=True, text=True, timeout=3, env=env,
        )
        if r.returncode == 0:
            data = json.loads(r.stdout.strip())
            token = data.get("access_token", "")
            expires_in = int(data.get("expires_in", 10800))
            if token:
                _save_token(token, expires_in)
                return token
        else:
            print(f"[cli_logger][WARN] mtsso 失败: {r.stderr.strip()[-200:]}", file=sys.stderr)
    except Exception as e:
        print(f"[cli_logger][WARN] mtsso 异常: {e}", file=sys.stderr)

    return ""


# ── HTTP 上报 ─────────────────────────────────────────────────────────────────

def _do_post(payload: dict) -> None:
    """执行 HTTP POST，在 daemon thread 中调用，失败静默。"""
    try:
        import requests
    except ImportError:
        print("[cli_logger][WARN] requests 未安装，跳过日志上报", file=sys.stderr)
        return

    token = _get_token()
    if not token:
        print("[cli_logger][WARN] 无法获取 token，跳过日志上报", file=sys.stderr)
        return

    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json", "Accept": "application/json"})
    sess.cookies.set(f"{_LOG_AUDIENCE}_ssoid", token, domain="sankuai.com")
    sess.cookies.set("ssoid", token, domain="sankuai.com")

    try:
        resp = sess.post(f"{_LOG_BASE_URL}{_LOG_API_PATH}", json=payload, timeout=3)
        result = resp.json() if resp.content else {}
        if not result.get("success") and result.get("code") != 0:
            print(f"[cli_logger][WARN] 上报返回非成功: {resp.status_code} {resp.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"[cli_logger][WARN] HTTP 上报失败: {e}", file=sys.stderr)


# ── 公开接口 ──────────────────────────────────────────────────────────────────

def report(
    mis: str,
    cli_command: str,
    status: str,           # "SUCCESS" | "FAIL"
    cost_time: int,        # 毫秒
    *,
    input_summary: str  = "",
    output_summary: str = "",
    error_msg: str      = "",
    error_type: str     = "",   # kdata_timeout / kdata_fail / daxiang_fail / config_error / unknown
    session_id: str     = "",
    job_id: str         = "",
) -> None:
    """
    fire-and-forget 上报一条 CLI 执行日志。

    - 在 daemon thread 中执行 HTTP POST，主流程立即返回
    - 任何失败只打印 WARN，不抛异常
    """
    payload: dict = {
        "mis":        mis,
        "cliCommand": cli_command,
        "status":     status,
        "costTime":   cost_time,
        "skill":      _SKILL_NAME,
    }
    if input_summary:
        payload["inputContent"] = input_summary[:2000]

    # outputContent：error 优先，FAIL 时附加 errorType
    if error_msg:
        out = {"error": error_msg[:2000]}
        if error_type:
            out["errorType"] = error_type
        payload["outputContent"] = json.dumps(out, ensure_ascii=False)
    elif output_summary:
        payload["outputContent"] = output_summary[:5000]

    if session_id:
        payload["sessionId"] = session_id
    if job_id:
        payload["traceId"] = job_id  # API 用 traceId 存储 job_id

    def _run_and_cleanup():
        try:
            _do_post(payload)
        finally:
            with _threads_lock:
                try:
                    _pending_threads.remove(t)
                except ValueError:
                    pass

    t = threading.Thread(target=_run_and_cleanup, daemon=True)
    with _threads_lock:
        _pending_threads.append(t)
    t.start()
    # 不在此处 join（调用点立即返回），atexit 时统一等待所有线程完成


def report_kdata_call(
    mis: str,
    dataset_id: str,
    region: str,
    cost_ms: int,
    *,
    rows_count: int     = -1,
    success: bool       = True,
    error_msg: str      = "",
    session_id: str     = "",
    job_id: str         = "",
) -> None:
    """fire-and-forget 上报单次 kdata 查询（skill-script 事件）。

    借鉴 keeta-data-skill-dev-spec skill_tracker.py 的 report_script 设计，
    以 cliCommand="skill-script" 上报节点粒度的性能和成功率数据。
    """
    input_summary  = f"dataset={dataset_id} region={region}"
    output_summary = f"rows={rows_count}" if rows_count >= 0 else ""
    report(
        mis,
        "skill-script",
        "SUCCESS" if success else "FAIL",
        cost_ms,
        input_summary  = input_summary,
        output_summary = output_summary,
        error_msg      = error_msg,
        session_id     = session_id,
        job_id         = job_id,
    )


def report_feedback(
    mis: str,
    rating: int,          # 1=有用(👍)  -1=无用(👎)
    *,
    comment: str  = "",
    job_id: str   = "",
    session_id: str = "",
) -> None:
    """fire-and-forget 上报用户告警反馈（feedback 事件）。

    对应 KM 埋点设计 §三 路径一（用户反馈信号）：
    comment 保留用户反馈原文，不做摘要或改写；长度由 report() 的 inputContent
    通用上限控制。
    """
    payload_input = json.dumps(
        {"rating": rating, "comment": comment or ""},
        ensure_ascii=False,
    )
    report(
        mis,
        "feedback",
        "SUCCESS",
        0,
        input_summary = payload_input,
        session_id    = session_id,
        job_id        = job_id,
    )


atexit.register(_atexit_join_threads)
