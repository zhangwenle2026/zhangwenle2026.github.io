#!/usr/bin/env python3
"""
BiClient — 魔数 BI 平台客户端

封装 bi.keetapp.com 的鉴权与 API 调用，供 capability2_hive、capability3_dataset、
capability4_template 共享使用。

鉴权策略（三层回退）：
  1. 【优先】SSO 标准体系：通过 mtsso-moa-local-exchange 换取用户身份票据
  2. 【降级】browser_cookie3：从本地浏览器 profile 读取 cookie
  3. 【兜底】CDP WebSocket：从沙箱浏览器获取 cookie（需浏览器运行中）
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import ssl
import struct
import sys
import time
import urllib.parse
import urllib.request
from typing import Any


REQUIRED_MODULES = [
    "dotenv",
    "requests",
    "browser_cookie3",
    # keyring / cryptography 是 browser_cookie3 在各平台解密 Cookie 的系统依赖，
    # 本 skill 不直接调用 keyring API，亦不通过 keyring 存储任何凭据。
    "cryptography",
]
WORKSPACE_ROOT = Path(os.environ.get("OPENCLAW_WORKSPACE_ROOT", os.getcwd())).resolve()
OPENCLAW_HOME = Path(os.environ.get("OPENCLAW_HOME", str(WORKSPACE_ROOT / ".openclaw"))).expanduser()
STATE_ROOT = Path(
    os.environ.get("KEETA_BI_STATE_DIR", str(OPENCLAW_HOME / "state" / "keeta-bi"))
).expanduser()
DEFAULT_LOG_DIR = STATE_ROOT / "logs"
DEFAULT_STORAGE_DIR = STATE_ROOT / "storage"
DEFAULT_SSO_STORAGE_DIR = STATE_ROOT / "sso"

DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_SSO_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("MEITUAN_LOG_DIR", str(DEFAULT_LOG_DIR))
os.environ.setdefault("MEITUAN_STORAGE_DIR", str(DEFAULT_STORAGE_DIR))
os.environ.setdefault("MEITUAN_SSO_STORAGE_DIR", str(DEFAULT_SSO_STORAGE_DIR))
os.environ.setdefault("MEITUAN_BASE_DOMAIN", "keetapp.com")
os.environ.setdefault("MEITUAN_CDP_HOST", "127.0.0.1")
os.environ.setdefault("MEITUAN_CDP_PORT", "9222")

BI_BASE_OVERSEAS = "https://bi.keetapp.com"
BI_BASE = BI_BASE_OVERSEAS

STATUS_RUNNING = 3
STATUS_SUCCESS = 5
STATUS_DONE = 8
STATUS_RUNNING_VALUES = {
    STATUS_RUNNING,
    str(STATUS_RUNNING),
    "RUNNING",
    "PENDING",
    "QUEUED",
    "WAITING",
    "SCHEDULED",
}
STATUS_SUCCESS_VALUES = {
    STATUS_SUCCESS,
    STATUS_DONE,
    str(STATUS_SUCCESS),
    str(STATUS_DONE),
    "SUCCESS",
    "SUCCEEDED",
    "DONE",
    "FINISHED",
    "FINISH",
    "COMPLETED",
}

_ACCESS_TOKEN_COOKIE_CANDIDATES = (
    "com.sankuai.fetc.mdbi.home_ssoid",
    "moshu_ssoid",
    "ssoid",
)
_COOKIE_KEY_CANDIDATES = (
    "moshu_ssoid",
    "JSESSIONID",
    "ssoid",
    "com.sankuai.fetc.mdbi.home_ssoid",
)

_RUNTIME_READY = False
_REQUESTS = None
_BROWSER_COOKIE3 = None

# bi.keetapp.com 的 SSO client_id（cookie 名前缀 com.sankuai.fetc.mdbi.home_ssoid）
_BI_SSO_CLIENT_ID = "com.sankuai.fetc.mdbi.home"
# `cxr_query.py --first-round` 会在父进程预热 BI token 后注入该环境变量，
# 避免多个子进程同时调用 mtsso-moa-local-exchange。
_BI_ENV_TOKEN_KEY = "KEETA_BI_TOKEN"
# 进程级 mtsso token 缓存，格式: (token_str, expires_at_unix)
_bi_token_cache: dict = {}

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_CDP_TIMEOUT_SECONDS = 5
_BROWSER_READER_NAMES = (
    "chrome",
    "chromium",
    "edge",
    "brave",
    "opera",
    "vivaldi",
    "arc",
    "firefox",
    "lynx",
)


def _load_dotenv_if_exists() -> None:
    """从工作区根目录加载工具配置。

    安全约束：
    - 仅加载 WORKSPACE_ROOT 下的 .env 文件，不向上遍历父目录，
      避免意外读取系统级 .env 中的敏感凭据（如 API 密钥、数据库密码）。
    - .env 文件应仅包含非敏感的工具配置（如域名、队列名称等），
      禁止在 .env 中写入任何密码、密钥或个人凭据。
    """
    from dotenv import load_dotenv

    env_file = WORKSPACE_ROOT / ".env"
    if env_file.is_file():
        load_dotenv(env_file, override=False)


def _ensure_runtime() -> None:
    global _RUNTIME_READY, _REQUESTS, _BROWSER_COOKIE3
    if _RUNTIME_READY:
        return

    missing_modules = [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]
    if missing_modules:
        missing_text = ", ".join(sorted(missing_modules))
        raise RuntimeError(
            f"keeta-bi 缺少运行时依赖: {missing_text}。"
            " 请先执行 `python3 -m pip install -r requirements.txt`。"
        )

    _load_dotenv_if_exists()

    import browser_cookie3
    import requests

    _REQUESTS = requests
    _BROWSER_COOKIE3 = browser_cookie3
    _RUNTIME_READY = True


def _normalize_domain(url_or_host: str) -> str:
    parsed = urllib.parse.urlparse(url_or_host)
    host = parsed.hostname or url_or_host
    return host.split("/", 1)[0].split(":", 1)[0].lower()


def _normalize_project_name(value: str) -> str:
    lowered = value.strip().lower()
    return "".join(ch for ch in lowered if ch.isalnum())


def _pick_access_token(cookies: dict[str, str]) -> str | None:
    for name in _ACCESS_TOKEN_COOKIE_CANDIDATES:
        value = cookies.get(name)
        if value:
            return value
    return None


def _preferred_browser_name() -> str:
    return os.getenv("MEITUAN_SSO_DEFAULT_BROWSER", "chrome").strip().lower()


def _iter_browser_readers() -> list[tuple[str, Any]]:
    _ensure_runtime()
    preferred = _preferred_browser_name()
    ordered: list[str] = []
    if preferred:
        ordered.append(preferred)
    for name in _BROWSER_READER_NAMES:
        if name not in ordered:
            ordered.append(name)

    readers: list[tuple[str, Any]] = []
    for name in ordered:
        reader = getattr(_BROWSER_COOKIE3, name, None)
        if callable(reader):
            readers.append((name, reader))
    return readers


def _load_cookies_from_default_browser(domain: str) -> dict[str, str]:
    preferred = _preferred_browser_name()
    reader = getattr(_BROWSER_COOKIE3, preferred, None)
    if not callable(reader):
        return {}
    try:
        browser_cookies = reader(domain_name=domain)
    except Exception:
        return {}
    return {cookie.name: cookie.value for cookie in browser_cookies}


def _load_cookies_from_all_browsers(domain: str) -> dict[str, str]:
    merged: dict[str, str] = {}
    readers = _iter_browser_readers()
    for cookie_key in _COOKIE_KEY_CANDIDATES:
        for _browser_name, reader in readers:
            try:
                browser_cookies = reader(domain_name=domain)
                cookies = {cookie.name: cookie.value for cookie in browser_cookies}
            except Exception:
                continue
            if cookie_key in cookies:
                merged.update(cookies)
                break
    return merged


def _read_exact(stream: Any, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            raise RuntimeError("unexpected EOF while reading websocket frame")
        data += chunk
    return data


def _read_ws_frame(stream: Any) -> tuple[int, bool, bytes]:
    header = _read_exact(stream, 2)
    first_byte, second_byte = header[0], header[1]
    fin = bool(first_byte & 0x80)
    opcode = first_byte & 0x0F
    masked = bool(second_byte & 0x80)
    payload_length = second_byte & 0x7F

    if payload_length == 126:
        payload_length = struct.unpack("!H", _read_exact(stream, 2))[0]
    elif payload_length == 127:
        payload_length = struct.unpack("!Q", _read_exact(stream, 8))[0]

    mask_key = _read_exact(stream, 4) if masked else b""
    payload = _read_exact(stream, payload_length) if payload_length > 0 else b""
    if masked:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
    return opcode, fin, payload


def _build_ws_frame(payload: bytes, opcode: int) -> bytes:
    first_byte = 0x80 | (opcode & 0x0F)
    length = len(payload)
    frame = bytearray([first_byte])
    if length <= 125:
        frame.append(0x80 | length)
    elif length <= 65535:
        frame.append(0x80 | 126)
        frame.extend(struct.pack("!H", length))
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack("!Q", length))

    mask_key = os.urandom(4)
    frame.extend(mask_key)
    frame.extend(bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload)))
    return bytes(frame)


def _handshake_websocket(sock: socket.socket, stream: Any, parsed_ws_url: urllib.parse.ParseResult) -> None:
    path = parsed_ws_url.path or "/"
    if parsed_ws_url.query:
        path = f"{path}?{parsed_ws_url.query}"
    host = parsed_ws_url.hostname or "127.0.0.1"
    port = parsed_ws_url.port or (443 if parsed_ws_url.scheme == "wss" else 80)

    ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {ws_key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    sock.sendall(request.encode("ascii"))

    status_line = stream.readline().decode("utf-8", errors="replace").strip()
    if "101" not in status_line:
        raise RuntimeError(f"websocket handshake failed: {status_line}")

    response_headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if line in (b"", b"\r\n"):
            break
        decoded = line.decode("utf-8", errors="replace").strip()
        if ":" not in decoded:
            continue
        key, value = decoded.split(":", 1)
        response_headers[key.strip().lower()] = value.strip()

    expected_accept = base64.b64encode(
        hashlib.sha1(f"{ws_key}{_WS_GUID}".encode("ascii")).digest()
    ).decode("ascii")
    if response_headers.get("sec-websocket-accept") != expected_accept:
        raise RuntimeError("invalid websocket handshake response")


def _send_cdp_via_websocket(
    websocket_url: str, method: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(websocket_url)
    if parsed.scheme not in {"ws", "wss"}:
        raise ValueError(f"unsupported websocket scheme: {parsed.scheme}")

    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "wss" else 80)
    params = params or {}

    raw_socket = socket.create_connection((host, port), timeout=_CDP_TIMEOUT_SECONDS)
    raw_socket.settimeout(_CDP_TIMEOUT_SECONDS)
    socket_to_use: socket.socket
    if parsed.scheme == "wss":
        context = ssl.create_default_context()
        socket_to_use = context.wrap_socket(raw_socket, server_hostname=host)
        socket_to_use.settimeout(_CDP_TIMEOUT_SECONDS)
    else:
        socket_to_use = raw_socket

    with socket_to_use as sock:
        with sock.makefile("rb") as stream:
            _handshake_websocket(sock, stream, parsed)
            request_id = 1
            payload = json.dumps({"id": request_id, "method": method, "params": params}).encode("utf-8")
            sock.sendall(_build_ws_frame(payload, opcode=0x1))

            while True:
                opcode, _fin, frame_payload = _read_ws_frame(stream)
                if opcode == 0x8:
                    raise RuntimeError("websocket closed before CDP response")
                if opcode == 0x9:
                    sock.sendall(_build_ws_frame(frame_payload, opcode=0xA))
                    continue
                if opcode != 0x1:
                    continue

                message = json.loads(frame_payload.decode("utf-8"))
                if message.get("id") != request_id:
                    continue
                if "error" in message:
                    raise RuntimeError(f"CDP error for {method}: {message['error']}")
                return message.get("result") or {}


def _cdp_request(host: str, port: int, path: str = "/json/version") -> dict[str, Any]:
    with urllib.request.urlopen(f"http://{host}:{port}{path}", timeout=_CDP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _domain_matches(cookie_domain: str, target_domain: str) -> bool:
    cookie = _normalize_domain(cookie_domain.lstrip("."))
    target = _normalize_domain(target_domain)
    if not cookie or not target:
        return False
    return target == cookie or target.endswith(f".{cookie}") or cookie.endswith(f".{target}")


def _filter_cookies_by_domain(cookies: list[dict[str, Any]], domain: str) -> dict[str, str]:
    filtered: dict[str, str] = {}
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        cookie_domain = str(cookie.get("domain") or "")
        if not name or value is None:
            continue
        if _domain_matches(cookie_domain, domain):
            filtered[str(name)] = str(value)
    return filtered


def _get_cookies_via_cdp(domain: str) -> dict[str, str]:
    host = os.getenv("MEITUAN_CDP_HOST", "127.0.0.1")
    port_raw = os.getenv("MEITUAN_CDP_PORT", "9222")
    try:
        port = int(port_raw)
    except ValueError:
        return {}

    try:
        version_info = _cdp_request(host=host, port=port)
    except Exception:
        return {}

    websocket_url = str(version_info.get("webSocketDebuggerUrl") or "")
    if not websocket_url:
        return {}

    for method in ("Network.getAllCookies", "Storage.getCookies"):
        try:
            result = _send_cdp_via_websocket(websocket_url=websocket_url, method=method, params={})
            cookies = result.get("cookies") or []
            if not isinstance(cookies, list):
                continue
            matched = _filter_cookies_by_domain(cookies, domain)
            if matched:
                return matched
        except Exception:
            continue
    return {}


_NAV_WAIT_SEC = 8  # 导航等待时间（秒），与 keeta_client.py 保持一致


def _refresh_sso_via_cdp(target_url: str) -> None:
    """
    通过 CDP 导航目标页面，触发服务端自动刷新 session cookie。
    若已有对应 tab 则复用，否则开新 tab（完成后关闭）。
    """
    host = os.getenv("MEITUAN_CDP_HOST", "127.0.0.1")
    port_raw = os.getenv("MEITUAN_CDP_PORT", "9222")
    try:
        port = int(port_raw)
    except ValueError:
        return

    try:
        tabs = json.loads(
            urllib.request.urlopen(
                f"http://{host}:{port}/json/list", timeout=3
            ).read()
        )
    except Exception:
        return

    target_domain = urllib.parse.urlparse(target_url).netloc
    existing_id = None
    for t in tabs:
        if target_domain in t.get("url", "") and t.get("type") == "page":
            existing_id = t.get("id") or t.get("targetId")
            break

    opened_new = False
    if existing_id:
        try:
            ws_url = f"ws://{host}:{port}/devtools/page/{existing_id}"
            _send_cdp_via_websocket(websocket_url=ws_url, method="Page.navigate", params={"url": target_url})
        except Exception:
            pass
    else:
        try:
            result = json.loads(
                urllib.request.urlopen(
                    f"http://{host}:{port}/json/new?{urllib.parse.quote(target_url)}",
                    timeout=5,
                ).read()
            )
            existing_id = result.get("id") or result.get("targetId")
            opened_new = True
        except Exception:
            return

    print(f"[BiClient] SSO 续期中，等待 {_NAV_WAIT_SEC}s ...", file=sys.stderr)
    time.sleep(_NAV_WAIT_SEC)

    if opened_new and existing_id:
        try:
            urllib.request.urlopen(
                f"http://{host}:{port}/json/close/{existing_id}", timeout=3
            )
        except Exception:
            pass


def _resolve_sql_text(sql_or_file: str) -> str:
    candidate = Path(sql_or_file.strip()).expanduser()
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return sql_or_file


def _get_bi_token_via_mtsso(audience: str = _BI_SSO_CLIENT_ID) -> str:
    """通过 mtsso-moa-local-exchange 换取 bi.keetapp.com 的用户身份票据。

    返回 access_token 字符串，失败返回空字符串。
    """
    import subprocess
    import json as _json
    env_token = os.getenv(_BI_ENV_TOKEN_KEY, "").strip()
    if env_token:
        return env_token
    cache_key = f"bi_token:{audience}"
    now = time.time()
    if cache_key in _bi_token_cache:
        token_str, expires_at = _bi_token_cache[cache_key]
        if expires_at - now > 60:
            return token_str
    env = {**os.environ}
    for k in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        env.pop(k, None)
    try:
        result = subprocess.run(
            ["npx", "mtsso-moa-local-exchange", "--audience", audience],
            capture_output=True, text=True, timeout=30, env=env,
        )
        if result.returncode != 0:
            print(f"[BiClient] mtsso-moa-local-exchange 失败: {result.stderr.strip()[-200:]}", file=sys.stderr)
            return ""
        data = _json.loads(result.stdout.strip())
        token_str = data.get("access_token", "")
        expires_in = int(data.get("expires_in", 10800))
        if token_str:
            _bi_token_cache[cache_key] = (token_str, now + expires_in)
        return token_str
    except Exception as e:
        print(f"[BiClient] mtsso 取票异常: {e}", file=sys.stderr)
        return ""


class BiClient:
    """BI platform client using local browser/CDP cookies for authentication."""

    def __init__(
        self,
        project_id: str | int = "0",
        base_url: str = BI_BASE,
        session: Any = None,
        cookies: dict[str, str] | None = None,
    ) -> None:
        _ensure_runtime()
        # Clear proxy env vars for keetapp.com — proxies (e.g. 127.0.0.1:8118)
        # cause 502/503 errors since they can't forward requests to the internal BI service.
        # The browser bypasses these proxies via --proxy-bypass-list, so we mirror
        # that behavior here for direct HTTP requests.
        _proxy_keys = ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
                       "all_proxy", "ALL_PROXY"]
        for _k in _proxy_keys:
            os.environ.pop(_k, None)
        self.project_id = str(project_id)
        self.base_url = base_url.rstrip("/")
        self.domain = _normalize_domain(self.base_url)
        self.session = session or _REQUESTS.Session()
        # 优先通过 mtsso-moa-local-exchange 取票（标准 SSO 方式）
        self.access_token = _get_bi_token_via_mtsso()
        if not self.access_token:
            # 降级：从浏览器 / CDP 读取 cookie
            self.cookies = dict(cookies or self._load_domain_cookies(self.domain))
            if self.cookies:
                self.session.cookies.update(self.cookies)
            self.access_token = _pick_access_token(self.cookies) or self.access_token
        else:
            self.cookies = dict(cookies or {})
            if self.cookies:
                self.session.cookies.update(self.cookies)

    def _load_domain_cookies(self, domain: str) -> dict[str, str]:
        """降级鉴权路径：SSO 不可用时从本地浏览器读取指定域名 Cookie。

        安全约束：
        - 仅在 mtsso-moa-local-exchange 鉴权失败后触发（最低优先级降级路径）。
        - 仅读取 {domain} 域下的会话 Cookie，不访问其他任何域名。
        - 读取的 Cookie 仅用于本次 BI 查询请求，不会被持久化写入任何文件。
        - 如不希望触发浏览器 Cookie 读取，请确保 MOA 已登录以启用 mtsso 标准鉴权。
        """
        print(
            f"[BiClient] ⚠️  SSO 不可用，将从本地浏览器读取 {domain} 的会话 Cookie 用于 BI 鉴权。"
            " 如不希望此行为，请先登录 MOA 后重试（以启用 mtsso 标准鉴权）。",
            file=sys.stderr,
        )
        cookies = _load_cookies_from_default_browser(domain)
        if cookies:
            return cookies

        merged = _load_cookies_from_all_browsers(domain)
        if merged:
            return merged

        cookies = dict(_get_cookies_via_cdp(domain))
        if cookies:
            return cookies

        # 四层回退：CDP 取不到时，尝试 SSO 续期后重试（参考 keeta_client.py）
        print(f"[BiClient] Cookie 未找到，尝试 CDP 导航续期 ...", file=sys.stderr)
        _refresh_sso_via_cdp(f"https://{domain}")
        return dict(_get_cookies_via_cdp(domain))

    def _build_headers(self, project_id: str | None = None, pageurl: str | None = None) -> dict[str, str]:
        project = str(project_id) if project_id is not None else self.project_id
        if pageurl is None:
            parsed = urllib.parse.urlparse(self.base_url)
            pageurl = f"{parsed.netloc}/v2/sql/edit" if parsed.netloc else "bi.keetapp.com/v2/sql/edit"

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "X-LanguageType": "1",
            "X-TimeZone": "UTC+08:00",
            "x-locale": "zh",
            "x-requested-with": "XMLHttpRequest",
            "projectId": project,
            "pageurl": pageurl,
            "innerclientip": "0.0.0.0",
        }
        if self.access_token:
            headers["access-token"] = self.access_token
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if not self.cookies and not self.access_token:
            return {
                "error": f"未能读取 {self.domain} 的浏览器 Cookie，请先在浏览器登录后重试",
                "url": url,
            }

        try:
            resp = self.session.request(
                method=method,
                url=url,
                json=payload,
                headers=self._build_headers(project_id=project_id),
                timeout=30,
                allow_redirects=False,
            )
        except Exception as exc:
            return {"error": str(exc), "url": url}

        # Cookie 失效检测：redirect 或 502/503 时，重刷 Cookie 重试一次
        _should_retry = resp.is_redirect or resp.status_code in (502, 503)
        if _should_retry:
            print(f"[BiClient] 请求返回 {resp.status_code}，尝试刷新 Cookie 重试 ...", file=sys.stderr)
            _refresh_sso_via_cdp(f"https://{self.domain}")
            new_cookies = dict(_get_cookies_via_cdp(self.domain))
            if new_cookies:
                self.cookies = new_cookies
                self.session.cookies.update(new_cookies)
                self.access_token = _pick_access_token(new_cookies)
                try:
                    resp = self.session.request(
                        method=method,
                        url=url,
                        json=payload,
                        headers=self._build_headers(project_id=project_id),
                        timeout=30,
                        allow_redirects=False,
                    )
                except Exception as exc:
                    return {"error": str(exc), "url": url}
            # 重试后若仍是 redirect，返回错误
            if resp.is_redirect:
                return {
                    "error": "auth_redirect",
                    "url": url,
                    "status_code": resp.status_code,
                    "location": resp.headers.get("Location", ""),
                }

        try:
            data = resp.json()
        except ValueError:
            text = resp.text[:1000]
            return {
                "error": "non_json_response",
                "url": url,
                "status_code": resp.status_code,
                "text": text,
            }

        if isinstance(data, dict):
            if resp.status_code >= 400:
                data.setdefault("http_status", resp.status_code)
                data.setdefault("url", url)
            return data
        return {"data": data, "http_status": resp.status_code, "url": url}

    def _get(self, path: str, project_id: str | None = None) -> dict[str, Any]:
        return self._request_json("GET", path, project_id=project_id)

    def _post(self, path: str, payload: dict[str, Any], project_id: str | None = None) -> dict[str, Any]:
        return self._request_json("POST", path, payload=payload, project_id=project_id)

    def get_spaces(self) -> dict[str, Any]:
        return self._get("/api/moshu/api/v2/space/switch", project_id="0")

    def get_queues(self) -> dict[str, Any]:
        return self._get("/api/mtbi/bi/sql/queues/status")

    def get_datasources(self) -> dict[str, Any]:
        return self._get("/api/mtbi/meta/ds/list")

    def get_status(self, query_id: int | str) -> dict[str, Any]:
        return self._get(f"/api/mtbi/bi/sql/status?queryId={query_id}")

    def get_result(self, query_id: int | str, limit: int = 200) -> dict[str, Any]:
        return self._get(f"/api/mtbi/bi/sql/{query_id}/data?limit={limit}&plaintext=1")

    def analyze_sql(
        self,
        sql: str,
        engine: str = "onesql",
        ds_name: str = "dw_hive",
        stat_ds: str = "DW_ONESQL_DB_CONNECT_URL",
        var_map: dict[str, Any] | None = None,
        diagnose_source: str = "MTBI",
        get_inputs: bool = True,
        get_outputs: bool = False,
    ) -> dict[str, Any]:
        return self._post(
            "/api/mtbi/bisql/sql/analyze",
            {
                "engine": engine,
                "dsName": ds_name,
                "statDs": stat_ds,
                "statement": sql,
                "varMap": var_map or {},
                "diagnoseSource": diagnose_source,
                "getInputs": get_inputs,
                "getOutputs": get_outputs,
            },
        )

    def submit_sql(
        self,
        sql: str,
        spark_queue: str | None,
        engine: str = "onesql",
        ds_name: str = "dw_hive",
        stat_ds: str = "DW_ONESQL_DB_CONNECT_URL",
        resource_id: int = 0,
        resource_name: str = "新查询",
        resource_ver: int = 1,
        resource_owner: str = "",
        entrance: list[str] | None = None,
        filter_relation_type: str = "AND",
        filter_type: str = "EQ",
        filter_children: list[Any] | None = None,
    ) -> dict[str, Any]:
        resource_url = (
            f"{self.base_url}/v2/sql/edit?projectId={self.project_id}"
            if self.project_id and self.project_id != "0"
            else f"{self.base_url}/v2/sql/edit"
        )
        if entrance is None:
            parsed = urllib.parse.urlparse(self.base_url)
            entrance = [parsed.netloc] if parsed.netloc else ["bi.keetapp.com"]
        if filter_children is None:
            filter_children = []

        return self._post(
            "/api/mtbi/bi/sql/submit",
            {
                "context": {
                    "resourceId": resource_id,
                    "resourceName": resource_name,
                    "resourceVer": resource_ver,
                    "resourceUrl": resource_url,
                    "resourceOwner": resource_owner,
                    "mdbiSparkQueue": spark_queue or "",
                    "entrance": entrance,
                },
                "model": {
                    "datasourceInfo": {
                        "sqlModelInfo": {
                            "sqlContent": sql,
                            "dsn": ds_name,
                            "hostGroup": ds_name,
                            "keyForAuth": stat_ds,
                            "engineType": engine,
                        }
                    }
                },
                "access": {
                    "filter": {
                        "relationType": filter_relation_type,
                        "filterType": filter_type,
                        "children": filter_children,
                    }
                },
            },
        )

    def resolve_project_id(self, project_ref: str | int) -> str:
        ref = str(project_ref).strip()
        if not ref:
            return "0"
        if ref.isdigit():
            return ref

        spaces = self.get_spaces()
        if spaces.get("error"):
            raise RuntimeError(f"读取工作空间失败: {spaces['error']}")
        if spaces.get("code", 0) != 0:
            raise RuntimeError(f"读取工作空间失败: {spaces.get('message', spaces)}")

        data = spaces.get("data", [])
        if not isinstance(data, list):
            raise RuntimeError(f"工作空间返回格式异常: {type(data)}")

        normalized_target = _normalize_project_name(ref)
        candidates: list[tuple[str, str]] = []

        for group in data:
            children = group.get("children", [])
            if children:
                for proj in children:
                    name = str(proj.get("name", "")).strip()
                    project_id = str(proj.get("id", "")).strip()
                    if not project_id:
                        continue
                    candidates.append((name, project_id))
                    if (
                        ref.lower() == name.lower()
                        or normalized_target == _normalize_project_name(name)
                    ):
                        return project_id
            else:
                name = str(group.get("name", "")).strip()
                project_id = str(group.get("id", "")).strip()
                if not project_id:
                    continue
                candidates.append((name, project_id))
                if (
                    ref.lower() == name.lower()
                    or normalized_target == _normalize_project_name(name)
                ):
                    return project_id

        sample = ", ".join(f"{name}({project_id})" for name, project_id in candidates[:10])
        raise RuntimeError(f"未找到工作空间: {ref}。可用示例: {sample}")

    def run_sql(
        self,
        sql: str,
        spark_queue: str | None,
        engine: str = "onesql",
        ds_name: str = "dw_hive",
        stat_ds: str = "DW_ONESQL_DB_CONNECT_URL",
        resource_name: str = "新查询",
        resource_owner: str = "",
        entrance: list[str] | None = None,
        filter_relation_type: str = "AND",
        filter_type: str = "EQ",
        limit: int = 200,
        poll_interval: float = 3.0,
        timeout: float = 180.0,
    ) -> dict[str, Any]:
        analyze_result = self.analyze_sql(sql, engine=engine, ds_name=ds_name, stat_ds=stat_ds)
        analyze_data = analyze_result.get("data") or {}
        if analyze_result.get("code") != 0 or not analyze_data.get("isPass"):
            return {"success": False, "error": "analyze_failed", "detail": analyze_result}

        submit_result = self.submit_sql(
            sql=sql,
            spark_queue=spark_queue,
            engine=engine,
            ds_name=ds_name,
            stat_ds=stat_ds,
            resource_name=resource_name,
            resource_owner=resource_owner,
            entrance=entrance,
            filter_relation_type=filter_relation_type,
            filter_type=filter_type,
        )
        if submit_result.get("code") != 0:
            return {"success": False, "error": "submit_failed", "detail": submit_result}

        query_id = (submit_result.get("data") or {}).get("queryId")
        if not query_id:
            return {"success": False, "error": "no_query_id", "detail": submit_result}

        started_at = time.monotonic()
        deadline = started_at + timeout
        last_status_result: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            status_result = self.get_status(query_id)
            last_status_result = status_result
            status_data = status_result.get("data") or {}
            status = status_data.get("status")
            status_text_values = {
                str(v).strip().upper()
                for v in (
                    status,
                    status_data.get("statusName"),
                    status_data.get("statusText"),
                    status_data.get("state"),
                    status_data.get("queryState"),
                    status_data.get("executeStatus"),
                )
                if v is not None
            }

            if status in STATUS_SUCCESS_VALUES or status_text_values & STATUS_SUCCESS_VALUES:
                break
            if status not in STATUS_RUNNING_VALUES and not (status_text_values & STATUS_RUNNING_VALUES):
                return {
                    "success": False,
                    "error": "query_failed",
                    "status": status,
                    "status_text": sorted(status_text_values),
                    "problem": status_data.get("problem", ""),
                    "query_id": query_id,
                    "elapsed_sec": round(time.monotonic() - started_at, 2),
                    "detail": status_result,
                }

            time.sleep(max(0.2, poll_interval))
        else:
            return {
                "success": False,
                "error": "timeout",
                "query_id": query_id,
                "elapsed_sec": round(time.monotonic() - started_at, 2),
                "last_status": last_status_result,
            }

        result_data = self.get_result(query_id, limit=limit)
        if result_data.get("code") != 0:
            return {"success": False, "error": "data_failed", "detail": result_data, "query_id": query_id}

        data = result_data.get("data") or {}
        return {
            "success": True,
            "query_id": query_id,
            "elapsed_sec": round(time.monotonic() - started_at, 2),
            "columns": data.get("columns", []),
            "data": data.get("data", []),
            "total_num": data.get("totalNum", 0),
        }
