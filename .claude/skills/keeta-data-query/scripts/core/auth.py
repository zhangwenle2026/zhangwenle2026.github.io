#!/usr/bin/env python3
"""
core/auth.py — Keeta skill 统一 SSO 鉴权工具

提供：
  get_token(audience)  — 获取 SSO access_token（mtsso/CIBA，进程级缓存）
  get_mis()            — 获取当前用户 MIS（mtcli kdata log get-mis）
  no_proxy_env()       — 返回去掉 HTTP 代理的 env dict

鉴权优先级：
  mtsso-moa-local-exchange → CIBA 大象授权 → 过期缓存
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ── 路径：从 __file__ 自推导 ──────────────────────────────────────────────────
try:
    from core.mis import get_mis as _get_mtcli_mis
except ImportError:
    from mis import get_mis as _get_mtcli_mis

# ── 进程级缓存 ────────────────────────────────────────────────────────────────
_token_cache: dict = {}   # audience -> (token_str, expires_at)
_mis_cache: dict = {}     # "mis" -> mis_str
_USER_TOKEN_CACHE_DIR = Path("~/.openclaw/state/keeta-bi/user-tokens/").expanduser()

def no_proxy_env() -> dict:
    """返回去掉 HTTP 代理变量的 os.environ 副本。"""
    drop = {"HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"}
    return {k: v for k, v in os.environ.items() if k not in drop}


# ══════════════════════════════════════════════════════════════════════════════
# MIS 检测
# ══════════════════════════════════════════════════════════════════════════════

def get_mis(audience: str = "6bde082970") -> str:
    """
    获取当前用户 MIS，委托 core.mis：
      1. mtcli kdata log get-mis（失败重试一次）
      2. 环境变量 / manual_mis 兜底
    失败返回 "unknown"，结果进程内缓存。
    """
    if "mis" in _mis_cache:
        return _mis_cache["mis"]

    def _set(mis: str) -> str:
        _mis_cache["mis"] = mis
        return mis

    return _set(_get_mtcli_mis(default="unknown") or "unknown")


def _safe_cache_part(value: str) -> str:
    return "".join(c for c in value if c.isalnum() or c in ("_", "-", "."))


def _legacy_cache_file(mis: str) -> Path:
    return _USER_TOKEN_CACHE_DIR / f"{_safe_cache_part(mis)}.json"


def _cache_file(mis: str, audience: str) -> Path:
    return _USER_TOKEN_CACHE_DIR / f"{_safe_cache_part(mis)}__{_safe_cache_part(audience)}.json"


def _get_cached_user_token(mis: str, audience: str) -> str | None:
    cache_path = _cache_file(mis, audience)
    if not cache_path.exists():
        cache_path = _legacy_cache_file(mis)
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("audience") != audience:
        return None
    if time.time() > float(data.get("expires_at", 0)) - 60:
        return None
    token = data.get("token", "")
    return token if token else None


def _save_user_token(mis: str, audience: str, token: str, expires_in: int) -> None:
    _USER_TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "mis": mis,
        "audience": audience,
        "token": token,
        "expires_in": expires_in,
        "expires_at": time.time() + expires_in,
        "cached_at": time.time(),
    }
    try:
        _cache_file(mis, audience).write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"[auth] 写入 CIBA 缓存失败: {exc}", file=sys.stderr)


def _get_user_token(mis: str, audience: str, timeout: int = 180) -> str:
    cached = _get_cached_user_token(mis, audience)
    if cached:
        print(f"[auth] CIBA 缓存命中: {mis}", file=sys.stderr)
        return cached

    print(f"[auth] CIBA 缓存未命中，发起授权: {mis}", file=sys.stderr)
    try:
        from core.ciba import ciba_exchange
    except ImportError:
        from ciba import ciba_exchange

    token, expires_in = ciba_exchange(login_hint=mis, audience=audience, timeout=timeout)
    if not token:
        print(f"[auth] CIBA 换票失败: {mis}", file=sys.stderr)
        return ""
    _save_user_token(mis, audience, token, expires_in)
    return token


# ══════════════════════════════════════════════════════════════════════════════
# 统一 token 获取
# ══════════════════════════════════════════════════════════════════════════════

def get_token(audience: str, *, cdp_fallback: bool = True) -> str:
    """
    获取指定 audience 的 SSO access_token。

    所有运行环境都先走 mtsso-moa-local-exchange，再降级 CIBA。
    cdp_fallback 参数仅保留兼容；默认鉴权不再读取浏览器 Cookie。

    进程级缓存，同一 audience 不重复换票（保留 60s 余量）。
    失败返回空字符串，并打印原因到 stderr。
    """
    del cdp_fallback
    now = time.time()

    # Bug 4 fix: 缓存过期时先保留旧 token 作为兜底，换票成功再替换
    _stale_tok = ""
    if audience in _token_cache:
        tok, exp = _token_cache[audience]
        if exp - now > 60:
            return tok
        _stale_tok = tok  # 缓存已过期，但保留以备换票失败时兜底

    def _try_ciba() -> str:
        """CIBA 降级：通过大象推送授权换票，返回 token 或空字符串。"""
        try:
            mis = get_mis(audience)
            if not mis or mis == "unknown":
                print(f"[auth] CIBA 跳过：无法获取用户 MIS", file=sys.stderr)
                return ""
            tok = _get_user_token(mis=mis, audience=audience)
            if tok:
                # 从文件缓存读取真实 expires_at，最长 8h（28800s）
                _MAX_CACHE = 28800
                try:
                    cache_data = json.loads(_cache_file(mis, audience).read_text(encoding="utf-8"))
                    actual_expires_at = cache_data.get("expires_at", now + 10800)
                    cache_expires_at = min(actual_expires_at, now + _MAX_CACHE)
                except Exception:
                    cache_expires_at = now + 10800
                _token_cache[audience] = (tok, cache_expires_at)
                return tok
        except Exception as e:
            print(f"[auth] CIBA 异常 (audience={audience}): {e}", file=sys.stderr)
        return ""

    # ── mtsso-moa-local-exchange（先 feature-probe 探测 MOA WSS 可用性）──
    try:
        import shutil
        npx = shutil.which("npx") or "npx"
        # 1s 内探测 MOA WSS 是否可达；不可达直接跳过，避免 3 次重试超时污染输出
        probe = subprocess.run(
            [npx, "mtsso-moa-feature-probe", "--timeout", "1"],
            capture_output=True, text=True, timeout=3, env=no_proxy_env(),
        )
        if probe.returncode == 0:
            # MOA WSS 可达，正式换票
            _cid = os.environ.get("AGENT_SSO_CLIENT_ID", "5a7dd523f0")
            _csk = os.environ.get("AGENT_SSO_CLIENT_SECRET", "38714cade6e642bb9b91714a82b09212")
            result = subprocess.run(
                [npx, "mtsso-moa-local-exchange",
                 "--client_id", _cid, "--client_secret", _csk,
                 "--audience", audience],
                capture_output=True, text=True, timeout=10, env=no_proxy_env(),
            )
            if result.returncode == 0:
                data = json.loads(result.stdout.strip())
                tok = data.get("access_token", "")
                if tok:
                    expires_in = int(data.get("expires_in", 10800))
                    _token_cache[audience] = (tok, now + expires_in)
                    return tok
            print(f"[auth] mtsso 失败 (audience={audience}): {result.stderr.strip()[-200:]}", file=sys.stderr)
        # probe 失败（MOA WSS 不可达）→ 静默跳过，走 CIBA 降级
    except Exception as e:
        pass  # 探测或换票异常 → 静默降级

    # ── 方案二：CIBA 大象推送授权 ──
    ciba_tok = _try_ciba()
    if ciba_tok:
        return ciba_tok

    # Bug 4 fix: 所有方案失败，兜底返回旧 token
    if _stale_tok:
        print(f"[auth] ⚠️ 使用过期缓存 token 兜底 (audience={audience})", file=sys.stderr)
        return _stale_tok

    print(f"[auth] ⚠️ 所有鉴权方案均失败 (audience={audience})", file=sys.stderr)
    return ""
