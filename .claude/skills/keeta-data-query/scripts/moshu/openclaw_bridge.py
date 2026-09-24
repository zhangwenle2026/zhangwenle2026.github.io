#!/usr/bin/env python3
"""
openclaw_bridge.py — CatPaw/OpenClaw 公共工具模块

提供两类能力：

1. 环境自检（P4）
   detect_environment()      → "catdesk" | "openclaw" | "unknown"
   is_catdesk_available()    → bool

2. HTTP 桥接（P1）
   用于 OpenClaw 环境下路线 B 落盘：浏览器沙箱与 Agent 沙箱隔离，无法直接写文件，
   改为在 Agent 侧起一个本地 HTTP 服务器，让浏览器把数据 POST 过来。

   start_bridge_server(port) → (server, token)
   wait_for_data(token, timeout) → str  # 收到的原始 JSON 字符串

用法示例（路线 B OpenClaw 分支）：
   from openclaw_bridge import start_bridge_server, wait_for_data

   server, token = start_bridge_server(port=19876)
   # 调用内置 browser evaluate 工具，执行以下 JS：
   #   fetch("http://127.0.0.1:19876", {
   #     method: "POST",
   #     headers: {"Content-Type": "application/json"},
   #     body: JSON.stringify(window.__dashboard_data)
   #   }).then(r => r.text())
   data_str = wait_for_data(token, timeout=60)
   # data_str 即 window.__dashboard_data 的 JSON 字符串，后续写文件或直接解析
"""

import http.server
import os
import threading
from pathlib import Path
from typing import Optional, Tuple


# ── 环境自检 ──────────────────────────────────────────────────────────────────

def is_catdesk_available() -> bool:
    """检查当前环境是否存在 CatPaw Desk CLI。

    判断依据：~/.catpaw/bin/catdesk 可执行文件是否存在。
    """
    catdesk_path = Path.home() / ".catpaw" / "bin" / "catdesk"
    return catdesk_path.is_file() and os.access(catdesk_path, os.X_OK)


def detect_environment() -> str:
    """自动检测当前运行环境。

    返回值：
        "catdesk"  — 检测到 CatPaw Desk CLI，应使用 catdesk browser-action 命令
        "openclaw" — 未检测到 CatDesk，推断为 OpenClaw，使用内置 browser 工具
        "unknown"  — 无法确定（预留扩展用）

    用法：
        env = detect_environment()
        print(f"当前环境：{env}")
    """
    if is_catdesk_available():
        return "catdesk"
    # OpenClaw 没有独立的检测标志，目前以"非 CatDesk 即 OpenClaw"作为推断
    return "openclaw"


# ── HTTP 桥接（OpenClaw 路线 B 落盘）────────────────────────────────────────

class _BridgeToken:
    """内部数据容器，用于在 start_bridge_server / wait_for_data 之间传递状态。"""

    def __init__(self) -> None:
        self.data: Optional[str] = None     # 收到的原始 POST body
        self.thread: Optional[threading.Thread] = None


def start_bridge_server(port: int = 19876) -> Tuple[http.server.HTTPServer, _BridgeToken]:
    """在 Agent 侧启动临时 HTTP 接收服务，等待浏览器 POST 一次数据。

    服务器只接收一个请求后即停止监听（handle_request），适合单次落盘场景。

    参数：
        port — 监听端口，默认 19876；如果端口已被占用，调用方应换一个端口

    返回：
        (server, token) 元组
        - server  — HTTPServer 实例，wait_for_data 后调用 server.server_close() 清理
        - token   — 内部 token 对象，传给 wait_for_data() 取结果

    用法：
        server, token = start_bridge_server(port=19876)
        # 然后让浏览器 POST 数据到 http://127.0.0.1:{port}
        data_str = wait_for_data(token, timeout=60)
        server.server_close()
    """
    token = _BridgeToken()

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_OPTIONS(self):
            # 处理跨域预检请求
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            token.data = body.decode("utf-8")
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass  # 静默日志，避免干扰 Agent 输出

    server = http.server.HTTPServer(("127.0.0.1", port), _Handler)
    # 在后台线程中只处理一次请求
    t = threading.Thread(target=server.handle_request, daemon=True)
    t.start()
    token.thread = t
    print(f"[bridge] HTTP server listening on 127.0.0.1:{port}")
    return server, token


def wait_for_data(token: _BridgeToken, timeout: float = 60) -> str:
    """等待浏览器 POST 数据并返回原始 JSON 字符串。

    参数：
        token   — start_bridge_server() 返回的 token 对象
        timeout — 最长等待秒数，默认 60 秒

    返回：
        收到的原始字符串（即浏览器 POST body）

    异常：
        TimeoutError — 超时未收到数据
        RuntimeError — 收到空数据
    """
    if token.thread is None:
        raise RuntimeError("token 无效，请先调用 start_bridge_server()")

    token.thread.join(timeout=timeout)

    if token.thread.is_alive():
        raise TimeoutError(f"[bridge] 等待超时（{timeout}s），未收到浏览器数据")

    if not token.data:
        raise RuntimeError("[bridge] 收到空数据，浏览器可能未正常发送")

    print(f"[bridge] 数据接收成功（{len(token.data)} 字节）")
    return token.data
