#!/usr/bin/env python3
"""Standalone BI helper for OpenClaw keeta-bi skill."""

from __future__ import annotations

import argparse
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

_TRACKER_DIR = Path(__file__).resolve().parents[2] / "scripts"
if _TRACKER_DIR.is_dir() and str(_TRACKER_DIR) not in sys.path:
    sys.path.insert(0, str(_TRACKER_DIR))
try:
    from skill_tracker import report_script
except Exception:  # pragma: no cover - tracking must never block BI execution.
    def report_script(
        mis: str = "",
        params: str = "",
        output: str = "",
        cost_ms: int = 0,
        success: bool = True,
        error_msg: str = "",
    ) -> None:
        return None


REQUIRED_MODULES = [
    "dotenv",
    "requests",
    "browser_cookie3",
    "keyring",
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
    from dotenv import load_dotenv

    seen: set[str] = set()
    search_roots = [WORKSPACE_ROOT, Path.cwd()]
    for root in search_roots:
        current = root
        while True:
            env_file = current / ".env"
            env_str = str(env_file.resolve())
            if env_file.is_file() and env_str not in seen:
                load_dotenv(env_file, override=False)
                seen.add(env_str)
            if current.parent == current:
                break
            current = current.parent


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


def _print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        print("No rows.")
        return

    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    header_line = " | ".join(headers[idx].ljust(widths[idx]) for idx in range(len(headers)))
    sep_line = "-+-".join("-" * widths[idx] for idx in range(len(headers)))
    print(header_line)
    print(sep_line)
    for row in rows:
        print(" | ".join(row[idx].ljust(widths[idx]) for idx in range(len(headers))))


def _resolve_sql_text(sql_or_file: str) -> str:
    candidate = Path(sql_or_file.strip()).expanduser()
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return sql_or_file


def _tracking_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None

    tracked: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            tracked[key] = _tracking_payload(value)
        elif isinstance(value, list):
            tracked[key] = [
                _tracking_payload(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            tracked[key] = value
    return tracked


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
        self.project_id = str(project_id)
        self.base_url = base_url.rstrip("/")
        self.domain = _normalize_domain(self.base_url)
        self.session = session or _REQUESTS.Session()
        self.cookies = dict(cookies or self._load_domain_cookies(self.domain))
        if self.cookies:
            self.session.cookies.update(self.cookies)
        self.access_token = _pick_access_token(self.cookies)

    def _load_domain_cookies(self, domain: str) -> dict[str, str]:
        cookies = _load_cookies_from_default_browser(domain)
        if cookies:
            return cookies

        merged = _load_cookies_from_all_browsers(domain)
        if merged:
            return merged

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
        return headers

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        started_at = int(time.time() * 1000)
        params_summary = json.dumps(
            {
                "method": method,
                "path": path,
                "project_id": project_id or self.project_id,
                "payload": _tracking_payload(payload),
            },
            ensure_ascii=False,
        )

        def finish_tracking(output: dict[str, Any], success: bool = True, error_msg: str = "") -> None:
            report_script(
                params=params_summary,
                output=json.dumps(output, ensure_ascii=False),
                cost_ms=int(time.time() * 1000) - started_at,
                success=success,
                error_msg=error_msg,
            )

        if not self.cookies:
            error = f"未能读取 {self.domain} 的浏览器 Cookie，请先在浏览器登录后重试"
            finish_tracking({"url": url, "error": error}, success=False, error_msg=error)
            return {
                "error": error,
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
            finish_tracking({"url": url, "error": str(exc)}, success=False, error_msg=str(exc))
            return {"error": str(exc), "url": url}

        if resp.is_redirect:
            error = "auth_redirect"
            finish_tracking(
                {
                    "url": url,
                    "status_code": resp.status_code,
                    "location": resp.headers.get("Location", ""),
                },
                success=False,
                error_msg=error,
            )
            return {
                "error": error,
                "url": url,
                "status_code": resp.status_code,
                "location": resp.headers.get("Location", ""),
            }

        try:
            data = resp.json()
        except ValueError:
            text = resp.text[:1000]
            finish_tracking(
                {"url": url, "status_code": resp.status_code, "error": "non_json_response"},
                success=False,
                error_msg="non_json_response",
            )
            return {
                "error": "non_json_response",
                "url": url,
                "status_code": resp.status_code,
                "text": text,
            }

        if isinstance(data, dict):
            code = data.get("code")
            success = resp.status_code < 400 and not data.get("error") and code in (None, 0, "0")
            finish_tracking(
                {"url": url, "status_code": resp.status_code, "code": code, "has_data": "data" in data},
                success=success,
                error_msg="" if success else str(data.get("error") or data.get("message") or code),
            )
            if resp.status_code >= 400:
                data.setdefault("http_status", resp.status_code)
                data.setdefault("url", url)
            return data
        finish_tracking(
            {"url": url, "status_code": resp.status_code, "data_type": type(data).__name__},
            success=resp.status_code < 400,
            error_msg="" if resp.status_code < 400 else str(resp.status_code),
        )
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

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status_result = self.get_status(query_id)
            status_data = status_result.get("data") or {}
            status = status_data.get("status")

            if status in (STATUS_SUCCESS, STATUS_DONE):
                break
            if status != STATUS_RUNNING:
                return {
                    "success": False,
                    "error": "query_failed",
                    "status": status,
                    "problem": status_data.get("problem", ""),
                    "query_id": query_id,
                    "detail": status_result,
                }

            time.sleep(max(0.2, poll_interval))
        else:
            return {"success": False, "error": "timeout", "query_id": query_id}

        result_data = self.get_result(query_id, limit=limit)
        if result_data.get("code") != 0:
            return {"success": False, "error": "data_failed", "detail": result_data, "query_id": query_id}

        data = result_data.get("data") or {}
        return {
            "success": True,
            "query_id": query_id,
            "columns": data.get("columns", []),
            "data": data.get("data", []),
            "total_num": data.get("totalNum", 0),
        }


def _raise_if_error(result: dict[str, Any], action: str) -> None:
    if result.get("error"):
        raise RuntimeError(f"{action}失败: {result['error']}")
    if result.get("code", 0) != 0:
        message = result.get("message") or result.get("msg") or result.get("errorMessage") or ""
        if message:
            raise RuntimeError(f"{action}失败(code={result.get('code')}): {message}")
        raise RuntimeError(f"{action}失败: {result}")


def _make_client(project_ref: str, base_url: str) -> BiClient:
    client = BiClient(project_id="0", base_url=base_url)
    client.project_id = client.resolve_project_id(project_ref)
    return client


def _ensure_queue(engine: str, queue: str | None) -> None:
    if engine.lower() != "doris" and not queue:
        raise RuntimeError("Hive/OneSQL/Presto/MySQL 查询需要指定 --queue")


def cmd_spaces(args: argparse.Namespace) -> int:
    client = BiClient(project_id="0", base_url=args.base_url)
    result = client.get_spaces()
    _raise_if_error(result, "获取工作空间")

    data = result.get("data", [])
    if args.json_output:
        _print_json(data)
        return 0

    rows: list[list[str]] = []
    for group in data:
        children = group.get("children", [])
        if children:
            for proj in children:
                rows.append(
                    [
                        str(proj.get("id", "")),
                        str(proj.get("name", "")),
                        "项目组空间",
                        str(proj.get("description", "")),
                        str(proj.get("admin", "")),
                    ]
                )
        else:
            rows.append(
                [
                    str(group.get("id", "")),
                    str(group.get("name", "")),
                    "个人空间",
                    "",
                    "",
                ]
            )

    _print_table(["ID", "名称", "类型", "描述", "管理员"], rows)
    return 0


def cmd_queues(args: argparse.Namespace) -> int:
    client = BiClient(project_id="0", base_url=args.base_url)
    result = client.get_queues()
    _raise_if_error(result, "获取队列")

    data = result.get("data", [])
    if args.json_output:
        _print_json(data)
        return 0

    rows = [
        [
            str(item.get("name", "")),
            str(item.get("vcoresQuota", "")),
            str(item.get("vcoresUsedNum", "")),
            str(item.get("vcoresPendingNum", "")),
        ]
        for item in data
    ]
    _print_table(["队列名称", "配额(vCores)", "已用", "排队中"], rows)
    return 0


def cmd_datasources(args: argparse.Namespace) -> int:
    client = _make_client(args.project, args.base_url)
    result = client.get_datasources()
    _raise_if_error(result, "获取数据源")

    data = result.get("data", {})
    if args.json_output:
        _print_json(data)
        return 0

    rows: list[list[str]] = []
    for engine_name, sources in data.items():
        for source in sources:
            rows.append(
                [
                    str(engine_name),
                    str(source.get("name", "")),
                    str(source.get("statDs", "")),
                    str(source.get("displayName", "")),
                    "Y" if source.get("permission") else "N",
                ]
            )
    _print_table(["引擎", "数据源名称(dsn)", "连接标识(statDs)", "显示名称", "权限"], rows)
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    _ensure_queue(args.engine, args.queue)
    sql = _resolve_sql_text(args.sql_or_file)
    client = _make_client(args.project, args.base_url)
    result = client.submit_sql(
        sql=sql,
        spark_queue=args.queue,
        engine=args.engine,
        ds_name=args.ds_name,
        stat_ds=args.stat_ds,
        resource_name=args.resource_name,
        resource_owner=args.resource_owner,
        entrance=args.entrance,
        filter_relation_type=args.filter_relation_type,
        filter_type=args.filter_type,
    )

    if args.json_output:
        _print_json(result)
    _raise_if_error(result, "提交 SQL")

    if args.json_output:
        return 0

    query_id = (result.get("data") or {}).get("queryId")
    print(f"提交成功 queryId={query_id}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    client = _make_client(args.project, args.base_url)
    result = client.get_status(args.query_id)
    if args.json_output:
        _print_json(result)
        _raise_if_error(result, "查询状态")
        return 0
    _raise_if_error(result, "查询状态")

    data = result.get("data") or {}
    status_code = data.get("status")
    status_labels = {
        STATUS_RUNNING: "运行中",
        STATUS_SUCCESS: "成功完成",
        STATUS_DONE: "已完成",
    }
    label = status_labels.get(status_code, f"失败(code={status_code})")
    print(f"queryId={args.query_id} 状态={label}")
    if data.get("problem"):
        print(f"错误信息: {data.get('problem')}")
    return 0


def cmd_result(args: argparse.Namespace) -> int:
    client = _make_client(args.project, args.base_url)
    result = client.get_result(args.query_id, limit=args.limit)
    if args.json_output:
        _print_json(result)
        _raise_if_error(result, "获取结果")
        return 0
    _raise_if_error(result, "获取结果")

    data = result.get("data") or {}
    columns = [str(col) for col in data.get("columns", [])]
    rows = data.get("data", [])
    total = data.get("totalNum", 0)

    print(f"总行数={total} 返回={len(rows)}")
    if columns and rows:
        table_rows = [[str(v) if v is not None else "" for v in row] for row in rows]
        _print_table(columns, table_rows)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    _ensure_queue(args.engine, args.queue)
    sql = _resolve_sql_text(args.sql_or_file)
    client = _make_client(args.project, args.base_url)
    result = client.run_sql(
        sql=sql,
        spark_queue=args.queue,
        engine=args.engine,
        ds_name=args.ds_name,
        stat_ds=args.stat_ds,
        resource_name=args.resource_name,
        resource_owner=args.resource_owner,
        entrance=args.entrance,
        filter_relation_type=args.filter_relation_type,
        filter_type=args.filter_type,
        limit=args.limit,
        poll_interval=args.poll_interval,
        timeout=args.timeout,
    )

    if args.json_output:
        _print_json(result)
        return 0 if result.get("success") else 1

    if not result.get("success"):
        detail = result.get("detail")
        if detail:
            _print_json(detail)
        raise RuntimeError(f"执行失败: {result.get('error', 'unknown')}")

    print(
        "查询成功 queryId={query_id} 总行数={total} 返回={returned}".format(
            query_id=result.get("query_id"),
            total=result.get("total_num", 0),
            returned=len(result.get("data", [])),
        )
    )
    columns = [str(col) for col in result.get("columns", [])]
    rows = result.get("data", [])
    if columns and rows:
        table_rows = [[str(v) if v is not None else "" for v in row] for row in rows]
        _print_table(columns, table_rows)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"OpenClaw standalone BI tool (default: {BI_BASE})"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    spaces_parser = subparsers.add_parser("spaces", help="List personal/project spaces")
    spaces_parser.add_argument("--base-url", default=BI_BASE, help="BI base URL")
    spaces_parser.add_argument("--json", dest="json_output", action="store_true", help="Output JSON")
    spaces_parser.set_defaults(func=cmd_spaces)

    queues_parser = subparsers.add_parser("queues", help="List available queues")
    queues_parser.add_argument("--base-url", default=BI_BASE, help="BI base URL")
    queues_parser.add_argument("--json", dest="json_output", action="store_true", help="Output JSON")
    queues_parser.set_defaults(func=cmd_queues)

    datasources_parser = subparsers.add_parser("datasources", help="List datasource metadata")
    datasources_parser.add_argument("--project", "-p", default="0", help="Project ID or name (0=personal)")
    datasources_parser.add_argument("--base-url", default=BI_BASE, help="BI base URL")
    datasources_parser.add_argument("--json", dest="json_output", action="store_true", help="Output JSON")
    datasources_parser.set_defaults(func=cmd_datasources)

    submit_parser = subparsers.add_parser("submit", help="Submit SQL only")
    submit_parser.add_argument("sql_or_file", help="SQL text or .sql file path")
    submit_parser.add_argument("--project", "-p", default="0", help="Project ID or name")
    submit_parser.add_argument("--queue", "-q", default=None, help="Spark queue (required for non-doris)")
    submit_parser.add_argument("--engine", "-e", default="onesql", help="Engine: onesql/hive/presto/doris/mysql")
    submit_parser.add_argument("--ds", dest="ds_name", default="dw_hive", help="Datasource name")
    submit_parser.add_argument("--stat-ds", dest="stat_ds", default="DW_ONESQL_DB_CONNECT_URL", help="Datasource stat key")
    submit_parser.add_argument("--resource-name", default="新查询", help="Resource name")
    submit_parser.add_argument("--resource-owner", default="", help="Resource owner")
    submit_parser.add_argument("--entrance", action="append", default=None, help="Entrance key (repeatable)")
    submit_parser.add_argument("--filter-relation", dest="filter_relation_type", default="AND", help="Filter relation type")
    submit_parser.add_argument("--filter-type", default="EQ", help="Filter type")
    submit_parser.add_argument("--base-url", default=BI_BASE, help="BI base URL")
    submit_parser.add_argument("--json", dest="json_output", action="store_true", help="Output JSON")
    submit_parser.set_defaults(func=cmd_submit)

    status_parser = subparsers.add_parser("status", help="Query status by query_id")
    status_parser.add_argument("query_id", type=int, help="Query ID")
    status_parser.add_argument("--project", "-p", default="0", help="Project ID or name")
    status_parser.add_argument("--base-url", default=BI_BASE, help="BI base URL")
    status_parser.add_argument("--json", dest="json_output", action="store_true", help="Output JSON")
    status_parser.set_defaults(func=cmd_status)

    result_parser = subparsers.add_parser("result", help="Fetch result by query_id")
    result_parser.add_argument("query_id", type=int, help="Query ID")
    result_parser.add_argument("--project", "-p", default="0", help="Project ID or name")
    result_parser.add_argument("--limit", "-n", type=int, default=200, help="Row limit")
    result_parser.add_argument("--base-url", default=BI_BASE, help="BI base URL")
    result_parser.add_argument("--json", dest="json_output", action="store_true", help="Output JSON")
    result_parser.set_defaults(func=cmd_result)

    run_parser = subparsers.add_parser("run", help="Analyze + submit + poll + fetch")
    run_parser.add_argument("sql_or_file", help="SQL text or .sql file path")
    run_parser.add_argument("--project", "-p", default="0", help="Project ID or name")
    run_parser.add_argument("--queue", "-q", default=None, help="Spark queue (required for non-doris)")
    run_parser.add_argument("--engine", "-e", default="onesql", help="Engine: onesql/hive/presto/doris/mysql")
    run_parser.add_argument("--ds", dest="ds_name", default="dw_hive", help="Datasource name")
    run_parser.add_argument("--stat-ds", dest="stat_ds", default="DW_ONESQL_DB_CONNECT_URL", help="Datasource stat key")
    run_parser.add_argument("--resource-name", default="新查询", help="Resource name")
    run_parser.add_argument("--resource-owner", default="", help="Resource owner")
    run_parser.add_argument("--entrance", action="append", default=None, help="Entrance key (repeatable)")
    run_parser.add_argument("--filter-relation", dest="filter_relation_type", default="AND", help="Filter relation type")
    run_parser.add_argument("--filter-type", default="EQ", help="Filter type")
    run_parser.add_argument("--limit", "-n", type=int, default=200, help="Row limit for result")
    run_parser.add_argument("--timeout", "-t", type=float, default=180.0, help="Polling timeout seconds")
    run_parser.add_argument("--poll-interval", type=float, default=3.0, help="Polling interval seconds")
    run_parser.add_argument("--base-url", default=BI_BASE, help="BI base URL")
    run_parser.add_argument("--json", dest="json_output", action="store_true", help="Output JSON")
    run_parser.set_defaults(func=cmd_run)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        return int(args.func(args))
    except RuntimeError as exc:
        print(f"[keeta_bi_skill] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[keeta_bi_skill] unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
