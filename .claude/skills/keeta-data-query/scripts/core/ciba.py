#!/usr/bin/env python3
"""
core/ciba.py — CIBA (Client-Initiated Backchannel Authentication) 换票

通过 CIBA 协议为指定用户（login_hint）获取 SSO access_token，
支持 token-exchange 换取目标 audience 的 token。

流程：
  1. 生成 client_assertion JWT（HS256）
  2. bc-authorize 获取 auth_req_id
  3. 轮询 token endpoint 等待用户在大象 App 授权
  4. token-exchange 换目标 audience 的 token

依赖：PyJWT（import jwt）
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
import uuid

try:
    import jwt
except ImportError:
    print("[ciba] 错误：缺少 PyJWT 依赖，请执行 pip install PyJWT", file=sys.stderr)
    raise

# ── 配置 ──────────────────────────────────────────────────────────────────────
_CLIENT_ID = "5a7dd523f0"
_CLIENT_SECRET = "38714cade6e642bb9b91714a82b09212"
_BASE_URL = "https://ssosv.sankuai.com"
_TOKEN_ENDPOINT = f"{_BASE_URL}/sson/auth/oidc/v1/token"
_BC_AUTHORIZE_ENDPOINT = f"{_BASE_URL}/sson/auth/oidc/v1/bc-authorize"

_POLL_INTERVAL = 5  # 轮询间隔秒数
_DEFAULT_TIMEOUT = 180  # 默认超时秒数


def _generate_jwt() -> str:
    """生成 client_assertion JWT（HS256），有效期 24h。"""
    now = int(time.time())
    payload = {
        "sub": _CLIENT_ID,
        "iss": _CLIENT_ID,
        "aud": [_TOKEN_ENDPOINT],
        "exp": now + 86400,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _CLIENT_SECRET, algorithm="HS256", headers={"typ": "JWT"})


def _post_form(url: str, data: dict) -> dict:
    """发送 POST application/x-www-form-urlencoded 请求，返回 JSON dict。"""
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except Exception:
            return {"error": "http_error", "status": e.code, "body": body}
    except Exception as e:
        return {"error": str(e)}


def ciba_exchange(
    login_hint: str,
    audience: str = "com.sankuai.fetc.mdbi.home",
    timeout: int = _DEFAULT_TIMEOUT,
) -> tuple[str, int]:
    """
    通过 CIBA 协议为指定用户换票。

    Args:
        login_hint: 用户 mis
        audience: 目标 SSO client_id
        timeout: 最大等待秒数

    Returns:
        (access_token, expires_in) 成功
        ("", 0) 失败
    """
    # ── 步骤 1: bc-authorize ──
    print(f"[ciba] 正在为 {login_hint} 发起授权请求...", file=sys.stderr)
    client_assertion = _generate_jwt()

    bc_data = {
        "scope": "profile",
        "login_hint": login_hint,
        "client_id": _CLIENT_ID,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": client_assertion,
    }
    bc_resp = _post_form(_BC_AUTHORIZE_ENDPOINT, bc_data)

    auth_req_id = bc_resp.get("auth_req_id", "")
    if not auth_req_id:
        auth_req_id = (bc_resp.get("extra_info") or {}).get("existing_auth_req_id", "")
        if auth_req_id:
            print("[ciba] 复用已有授权请求，继续等待用户授权...", file=sys.stderr)
    if not auth_req_id:
        print(f"[ciba] bc-authorize 失败: {bc_resp}", file=sys.stderr)
        return "", 0

    print(f"[ciba] auth_req_id 获取成功，等待 {login_hint} 在大象 App 中授权...", file=sys.stderr)

    # ── 步骤 2: 轮询 token endpoint ──
    deadline = time.time() + timeout
    access_token = ""
    poll_count = 0

    while time.time() < deadline:
        poll_count += 1
        time.sleep(_POLL_INTERVAL)

        # 每次轮询重新生成 JWT（避免 exp 边界问题）
        client_assertion = _generate_jwt()

        token_data = {
            "grant_type": "urn:openid:params:grant-type:ciba",
            "auth_req_id": auth_req_id,
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": client_assertion,
            "client_id": _CLIENT_ID,
        }
        token_resp = _post_form(_TOKEN_ENDPOINT, token_data)

        access_token = token_resp.get("access_token", "")
        if access_token:
            print(f"[ciba] 用户 {login_hint} 已授权（第 {poll_count} 次轮询）", file=sys.stderr)
            break

        # 检查是否是暂时性错误（authorization_pending）
        error = token_resp.get("error", "")
        if error and error not in ("authorization_pending", "slow_down"):
            print(f"[ciba] 轮询失败，非预期错误: {token_resp}", file=sys.stderr)
            return "", 0

        if poll_count % 6 == 0:  # 每 30s 打印一次提示
            remaining = int(deadline - time.time())
            print(f"[ciba] 仍在等待授权... 剩余 {remaining}s", file=sys.stderr)

    if not access_token:
        print(f"[ciba] 轮询超时（{timeout}s），用户未授权", file=sys.stderr)
        return "", 0

    # ── 步骤 3: token-exchange ──
    print(f"[ciba] 正在换取 {audience} 的 token...", file=sys.stderr)
    client_assertion = _generate_jwt()

    exchange_data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "auth_req_id": auth_req_id,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": client_assertion,
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "client_id": _CLIENT_ID,
        "audience": audience,
        "subject_token": access_token,
    }
    exchange_resp = _post_form(_TOKEN_ENDPOINT, exchange_data)

    final_token = exchange_resp.get("access_token", "")
    if not final_token:
        print(f"[ciba] token-exchange 失败: {exchange_resp}", file=sys.stderr)
        return "", 0

    expires_in = int(exchange_resp.get("expires_in", 7200))
    print(f"[ciba] 换票成功，有效期 {expires_in}s", file=sys.stderr)
    return final_token, expires_in
