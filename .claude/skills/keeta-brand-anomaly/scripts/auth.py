#!/usr/bin/env python3
"""
auth.py — keeta-brand-anomaly Skill SSO 鉴权工具

提供 get_token(audience) 获取 SSO access_token，对齐 keeta-data-query 的 auth 实现。
支持 CatClaw (mtsso-moa-local-exchange) + CatPaw Desk (catdesk auth exchange) + CDP 三层降级。
进程级缓存，失败静默返回空字符串。
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.parse
import urllib.request

_token_cache: dict = {}  # audience -> (token_str, expires_at)


def no_proxy_env() -> dict:
    """返回去掉 HTTP 代理变量的 os.environ 副本。"""
    drop = {"HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"}
    return {k: v for k, v in os.environ.items() if k not in drop}


def _is_catdesk() -> bool:
    return bool(os.environ.get("CATPAW_CLIENT_TYPE", ""))


def _is_catclaw() -> bool:
    return bool(os.environ.get("OPENCLAW_HOME", "") or os.environ.get("OPENCLAW_WORKSPACE_ROOT", ""))


def _catdesk_exchange(audience: str, timeout: int = 30) -> tuple[str, int]:
    """通过 catdesk auth exchange 换取 token，仅在 CatPaw Desk 环境下调用。"""
    catdesk = os.path.expanduser("~/.catpaw/bin/catdesk")
    if not os.path.exists(catdesk):
        return "", 0
    try:
        result = subprocess.run(
            [catdesk, "auth", "exchange", "--target-client-id", audience],
            capture_output=True, text=True, timeout=timeout, env=no_proxy_env(),
        )
        if result.returncode != 0:
            print(f"[brand-anomaly][auth] catdesk exchange 失败 ({audience}): {result.stderr.strip()[-200:]}", file=sys.stderr)
            return "", 0
        data = json.loads(result.stdout.strip())
        tok = data.get("accessToken", "")
        expires_in = int(
            data.get("expiresIn") or data.get("expires_in") or data.get("expireIn") or 1800
        )
        return tok, expires_in
    except Exception as e:
        print(f"[brand-anomaly][auth] catdesk exchange 异常 ({audience}): {e}", file=sys.stderr)
        return "", 0


def _cdp_get_all_cookies(host: str = "127.0.0.1", port: int = 9222) -> list:
    """从 CDP 获取浏览器所有 cookie，失败返回空列表。"""
    try:
        cdp_host = os.environ.get("MEITUAN_CDP_HOST", host)
        cdp_port = int(os.environ.get("MEITUAN_CDP_PORT", port))

        with urllib.request.urlopen(
            f"http://{cdp_host}:{cdp_port}/json/version", timeout=3
        ) as r:
            version = json.loads(r.read())
        ws_url = version.get("webSocketDebuggerUrl", "")
        if not ws_url:
            return []

        parsed = urllib.parse.urlparse(ws_url)
        key = base64.b64encode(os.urandom(16)).decode()
        sock = socket.create_connection((cdp_host, cdp_port), timeout=5)
        handshake = (
            f"GET {parsed.path} HTTP/1.1\r\n"
            f"Host: {cdp_host}:{cdp_port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(handshake.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += sock.recv(1024)

        def ws_send(data: str) -> None:
            payload = data.encode()
            ln = len(payload)
            mask = os.urandom(4)
            masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if ln <= 125:
                header = bytes([0x81, 0x80 | ln]) + mask
            elif ln <= 65535:
                header = bytes([0x81, 0xFE]) + struct.pack(">H", ln) + mask
            else:
                header = bytes([0x81, 0xFF]) + struct.pack(">Q", ln) + mask
            sock.sendall(header + masked)

        def ws_recv(timeout: float = 8.0) -> str:
            sock.settimeout(timeout)
            rbuf = b""
            def read_n(n: int) -> bytes:
                nonlocal rbuf
                while len(rbuf) < n:
                    rbuf += sock.recv(4096)
                out, rbuf = rbuf[:n], rbuf[n:]
                return out
            while True:
                hdr = read_n(2)
                opcode = hdr[0] & 0x0F
                masked_flag = (hdr[1] & 0x80) != 0
                length = hdr[1] & 0x7F
                if length == 126:
                    length = struct.unpack(">H", read_n(2))[0]
                elif length == 127:
                    length = struct.unpack(">Q", read_n(8))[0]
                mask_b = read_n(4) if masked_flag else b""
                pl = read_n(length)
                if masked_flag:
                    pl = bytes(b ^ mask_b[i % 4] for i, b in enumerate(pl))
                if opcode == 1:
                    return pl.decode()
                if opcode == 8:
                    raise ConnectionError("WebSocket closed")

        for method in ("Network.getAllCookies", "Storage.getCookies"):
            try:
                ws_send(json.dumps({"id": 1, "method": method, "params": {}}))
                resp = json.loads(ws_recv())
                cookies = resp.get("result", {}).get("cookies", [])
                if cookies:
                    sock.close()
                    return cookies
            except Exception:
                continue
        sock.close()
    except Exception:
        pass
    return []


def get_token(audience: str, *, cdp_fallback: bool = True) -> str:
    """
    获取指定 audience 的 SSO access_token。

    策略：
      - CatPaw Desk → catdesk auth exchange
      - CatClaw / 其他 → mtsso-moa-local-exchange
      - CDP WebSocket 作为降级路径

    进程级缓存，同一 audience 不重复换票（保留 60s 余量）。
    失败返回空字符串。
    """
    now = time.time()

    if audience in _token_cache:
        tok, exp = _token_cache[audience]
        if exp - now > 60:
            return tok

    # ── CatPaw Desk 环境 → catdesk auth exchange ──
    if _is_catdesk():
        tok, expires_in = _catdesk_exchange(audience)
        if tok:
            _token_cache[audience] = (tok, now + expires_in)
            return tok
        print(f"[brand-anomaly][auth] catdesk exchange 失败，尝试 CDP 降级", file=sys.stderr)
        cdp_tok = _cdp_get_token_from_cdp(audience, now)
        if cdp_tok:
            return cdp_tok
        print(f"[brand-anomaly][auth] ⚠️ 所有鉴权方案均失败 ({audience})", file=sys.stderr)
        return ""

    # ── CatClaw / 其他环境 → mtsso-moa-local-exchange ──
    try:
        npx = shutil.which("npx") or "npx"
        result = subprocess.run(
            [npx, "mtsso-moa-local-exchange", "--audience", audience],
            capture_output=True, text=True, timeout=15, env=no_proxy_env(),
        )
        if result.returncode == 0:
            data = json.loads(result.stdout.strip())
            tok = data.get("access_token", "")
            if tok:
                expires_in = int(data.get("expires_in", 10800))
                _token_cache[audience] = (tok, now + expires_in)
                return tok
        print(f"[brand-anomaly][auth] mtsso 失败 ({audience}): {result.stderr.strip()[-200:]}", file=sys.stderr)
    except Exception as e:
        print(f"[brand-anomaly][auth] mtsso 异常 ({audience}): {e}", file=sys.stderr)

    # ── CDP WebSocket 降级 ──
    cdp_tok = _cdp_get_token_from_cdp(audience, now)
    if cdp_tok:
        return cdp_tok

    print(f"[brand-anomaly][auth] ⚠️ 所有鉴权方案均失败 ({audience})", file=sys.stderr)
    return ""


def _cdp_get_token_from_cdp(audience: str, now: float) -> str:
    """从 CDP 获取指定 audience 的 ssoid cookie 作为 token 兜底。"""
    try:
        ssoid_key = f"{audience}_ssoid"
        cookies = _cdp_get_all_cookies()
        for c in cookies:
            if c.get("name") == ssoid_key:
                t = c.get("value", "")
                if t:
                    _token_cache[audience] = (t, now + 3600)
                    return t
        print(f"[brand-anomaly][auth] CDP 未找到 {ssoid_key}", file=sys.stderr)
    except Exception as e:
        print(f"[brand-anomaly][auth] CDP 异常: {e}", file=sys.stderr)
    return ""
