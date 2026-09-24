#!/usr/bin/env python3
"""
MDBI Dashboard v1 版本数据抓取脚本
针对 https://bi.keetapp.com/dashboard/{id} 格式的 v1 仪表板（境外版）

v1 Dashboard 存在两种取数接口，本脚本均支持，自动识别：

「情况2（moshu）」：
  数据接口：/api/moshu/api/v2/dashboards/submit-query
  响应格式：
    {"code":0, "data": {"lid":..., "titles":[{"name":"列名"}], "data":[...], "size":{"total":N}}}

「情况1（mtbi）」：
  流程：拦截 /api/mtbi/bi/submit/v2 → 获取 data.queryId
       拦截 /api/mtbi/bi/{queryId}/data → 获取实际数据
       拦截 staticResourceInfo → 构建列名映射（code → 中文名）
  data 接口响应格式：
    {"code":0, "data": {"columns":["code1",...], "data":[...], "totalNum":N}}
"""

import argparse
import asyncio
import csv
import json
import os
import re
import shutil
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    from playwright.async_api import async_playwright, Page, Browser, Request, Response
except ImportError:
    print("请先安装playwright:\n  pip3 install playwright -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com\n  PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright playwright install chromium")
    sys.exit(1)

# ── 默认配置 ──────────────────────────────────────────────────────────────────
DEFAULT_TIMEOUT = 180   # 3分钟
MAX_TIMEOUT = 900       # 最大15分钟
DEFAULT_MAX_ROWS = 10000
OUTPUT_DIR = Path(__file__).parent.parent / "output"
# ── v1 数据接口匹配 ────────────────────────────────────────────────────────────
SUBMIT_QUERY_PATH  = "/api/moshu/api/v2/dashboards/submit-query"   # 情况2 moshu
MTBI_SUBMIT_PATH   = "/api/mtbi/bi/submit/v2"                      # 情况1 提交接口
STATIC_RESOURCE_PATH = "/api/mtbi/bidata/metaData/staticResourceInfo"  # 情况1 列名元数据


def detect_catpaw(cdp_port: Optional[int] = None) -> Optional[str]:
    """检测 CatPaw/OpenClaw 环境，返回可用的 CDP URL；未检测到则返回 None。"""
    import urllib.request

    catpaw_endpoint = os.environ.get("CATPAW_CDP_ENDPOINT")
    if catpaw_endpoint:
        return catpaw_endpoint

    if cdp_port is not None:
        url = f"http://127.0.0.1:{cdp_port}"
        try:
            urllib.request.urlopen(url + "/json/version", timeout=2)
            return url
        except Exception:
            return None

    if "CDP_URL" in os.environ:
        url = os.environ["CDP_URL"]
        try:
            urllib.request.urlopen(url + "/json/version", timeout=2)
            return url
        except Exception:
            return None

    # 探测 OpenClaw 默认端口
    url = "http://127.0.0.1:9222"
    try:
        urllib.request.urlopen(url + "/json/version", timeout=2)
        return url
    except Exception:
        return None


def check_env():
    """检查运行环境，缺失时输出安装命令并退出"""
    ok = True

    if sys.version_info < (3, 8):
        print(f"[缺失] Python 版本过低（当前 {sys.version}），需要 3.8+")
        ok = False

    try:
        import playwright  # noqa: F401
        print("[OK] playwright 已安装")
    except ImportError:
        print("[缺失] playwright 未安装，请执行：\n  pip3 install playwright -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com")
        ok = False

    chromium_path = shutil.which("chromium") or shutil.which("chromium-browser")
    pw_chromium = Path.home() / ".cache/ms-playwright"
    has_chromium = chromium_path or (pw_chromium.exists() and any(pw_chromium.glob("chromium-*/chrome-linux/chrome")))
    mac_chromium = Path.home() / "Library/Caches/ms-playwright"
    has_chromium = has_chromium or (mac_chromium.exists() and any(mac_chromium.glob("chromium-*")))

    if has_chromium:
        print("[OK] Chromium 已安装")
    else:
        print("[缺失] Chromium 未安装，请执行：\n  PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright playwright install chromium")
        ok = False

    if not ok:
        print("\n环境检查未通过，请先完成安装后重试。")
        sys.exit(1)
    else:
        print("\n环境检查通过，可以开始取数。")
        sys.exit(0)


class DashboardV1Fetcher:
    """v1 Dashboard 数据抓取器，自动识别并支持两种接口：
    - 情况2（moshu）：/api/moshu/api/v2/dashboards/submit-query
    - 情况1（mtbi） ：/api/mtbi/bi/submit/v2 → /api/mtbi/bi/{queryId}/data
    """

    def __init__(
        self,
        dashboard_id: int,
        timeout: int = DEFAULT_TIMEOUT,
        max_rows: int = DEFAULT_MAX_ROWS,
        env: str = "prod",  # "prod" / "st" / "prod-overseas" / "st-overseas"
        cdp_port: Optional[int] = None,
        url: Optional[str] = None,
    ):
        self.dashboard_id = dashboard_id
        self.timeout = timeout
        self.max_rows = max_rows
        self.env = env.lower()
        self.cdp_port = cdp_port
        self._start_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_id = f"{dashboard_id}_{self._start_ts}"

        # 构建目标 URL
        if url:
            self.base_url = url
        elif self.env == "st-overseas" or self.env == "st":
            self.base_url = f"https://mdbi.bi.st.keetapp.com/dashboard/{dashboard_id}"
        else:
            # 默认境外生产环境
            self.base_url = f"https://bi.keetapp.com/dashboard/{dashboard_id}"

        # ── 情况2（moshu）数据 ─────────────────────────────────────────────────
        # {lid_str: {"titles":[...], "data":[...], "lid":int, "tab_name":str}}
        self.submit_query_results: Dict[str, Dict] = {}

        # ── 情况1（mtbi）数据 ──────────────────────────────────────────────────
        # submit/v2 响应：{queryId_str: {"queryId":int, "tab_name":str, ...}}
        self.mtbi_submit_results: Dict[str, Dict] = {}
        # /data 响应：{queryId_str: {"columns":[...], "data":[...], "totalNum":int}}
        self.mtbi_data_results: Dict[str, Dict] = {}
        # staticResourceInfo 列名映射：{code: 中文名}
        self.static_resource_mapping: Dict[str, str] = {}

        # 当前激活的 tab 名称（用于打标签）
        self.current_tab_name: str = ""

    def setup_signal_handler(self):
        def signal_handler(signum, frame):
            print("\n收到中断信号，正在清理...")
            sys.exit(0)
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def cleanup(self):
        if hasattr(self, 'browser') and self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    def should_capture(self, url: str) -> bool:
        """判断是否是需要捕获的接口（情况1或情况2均可）"""
        return (
            SUBMIT_QUERY_PATH in url
            or MTBI_SUBMIT_PATH in url
            or bool(re.search(r"/api/mtbi/bi/\d+/data", url))
            or STATIC_RESOURCE_PATH in url
        )

    async def handle_response(self, response: Response) -> None:
        """统一处理响应：情况2 submit-query / 情况1 submit+data+staticResourceInfo"""
        url = response.url
        if not self.should_capture(url):
            return

        try:
            status = response.status
            if status != 200:
                return

            # ── 情况2：moshu submit-query ──────────────────────────────────────
            if SUBMIT_QUERY_PATH in url:
                await self._handle_moshu_submit_query(url, response)

            # ── 情况1-A：mtbi submit/v2（提交查询，获取 queryId）─────────────
            elif MTBI_SUBMIT_PATH in url:
                await self._handle_mtbi_submit(url, response)

            # ── 情况1-B：mtbi /data（实际数据）──────────────────────────────
            elif re.search(r"/api/mtbi/bi/\d+/data", url):
                await self._handle_mtbi_data(url, response)

            # ── 情况1-C：staticResourceInfo（列名元数据）─────────────────────
            elif STATIC_RESOURCE_PATH in url:
                await self._handle_static_resource(url, response)

        except Exception as e:
            print(f"  [handle_response] 异常: {e}")

    async def _handle_moshu_submit_query(self, url: str, response: Response) -> None:
        """处理情况2：/api/moshu/api/v2/dashboards/submit-query"""
        try:
            body = await response.json()
            if body.get("code") != 0:
                print(f"  [submit-query] API错误: {body.get('message')}")
                return

            data = body.get("data", {})
            if not data:
                return

            titles = data.get("titles", [])
            rows = data.get("data", [])
            lid = data.get("lid", 0)
            size = data.get("size", {})
            total = size.get("total", len(rows))

            key = str(lid) if lid else f"unknown_{len(self.submit_query_results)}"
            if key in self.submit_query_results:
                print(f"  [submit-query] lid={lid} 已存在，跳过重复")
                return

            col_names = [t.get("name", t.get("id", f"col_{i}")) for i, t in enumerate(titles)]
            print(f"  [submit-query] lid={lid}, tab={self.current_tab_name or '未知'}, 列数={len(col_names)}, 行数={len(rows)}/{total}")

            self.submit_query_results[key] = {
                "lid": lid,
                "titles": titles,
                "col_names": col_names,
                "data": rows,
                "total": total,
                "tab_name": self.current_tab_name,
            }
        except Exception as e:
            print(f"  [submit-query] 响应解析失败: {e}")

    async def _handle_mtbi_submit(self, url: str, response: Response) -> None:
        """处理情况1-A：/api/mtbi/bi/submit/v2，提取 queryId"""
        try:
            body = await response.json()
            if body.get("code") != 0:
                print(f"  [mtbi-submit] API错误: {body.get('message')}")
                return

            data = body.get("data", {})
            query_id = data.get("queryId")
            if not query_id:
                # 有些响应字段名是 id
                query_id = data.get("id")
            if not query_id:
                print(f"  [mtbi-submit] 未找到 queryId，data keys: {list(data.keys())}")
                return

            key = str(query_id)
            if key in self.mtbi_submit_results:
                return  # 重复，跳过

            print(f"  [mtbi-submit] queryId={query_id}, tab={self.current_tab_name or '未知'}, data keys={list(data.keys())}")
            self.mtbi_submit_results[key] = {
                "queryId": query_id,
                "tab_name": self.current_tab_name,
                "raw_data": data,
            }
        except Exception as e:
            print(f"  [mtbi-submit] 响应解析失败: {e}")

    async def _handle_mtbi_data(self, url: str, response: Response) -> None:
        """处理情况1-B：/api/mtbi/bi/{queryId}/data，提取实际数据"""
        try:
            m = re.search(r"/api/mtbi/bi/(\d+)/data", url)
            if not m:
                return
            query_id = m.group(1)

            body = await response.json()
            if body.get("code") != 0:
                print(f"  [mtbi-data] API错误: {body.get('message')}")
                return

            data = body.get("data", {})
            columns = data.get("columns", [])
            rows = data.get("data", [])
            total_num = data.get("totalNum", len(rows))

            if query_id in self.mtbi_data_results:
                print(f"  [mtbi-data] queryId={query_id} 已存在，跳过重复")
                return

            # 获取对应的 tab 名（从 submit 结果中查找）
            tab_name = self.mtbi_submit_results.get(query_id, {}).get("tab_name", self.current_tab_name)
            print(f"  [mtbi-data] queryId={query_id}, tab={tab_name or '未知'}, 列数={len(columns)}, 行数={len(rows)}/{total_num}")

            self.mtbi_data_results[query_id] = {
                "queryId": int(query_id),
                "columns": columns,
                "data": rows,
                "totalNum": total_num,
                "tab_name": tab_name,
            }
        except Exception as e:
            print(f"  [mtbi-data] 响应解析失败: {e}")

    async def _handle_static_resource(self, url: str, response: Response) -> None:
        """处理情况1-C：staticResourceInfo，构建列名映射"""
        try:
            body = await response.json()
            if body.get("code") != 0:
                return

            items = body.get("data", [])
            if not isinstance(items, list):
                return

            new_count = 0
            for item in items:
                code = item.get("code", "")
                name = item.get("name", "")
                if code and name and code not in self.static_resource_mapping:
                    self.static_resource_mapping[code] = name
                    new_count += 1

            print(f"  [staticResource] 新增 {new_count} 条列名映射，累计 {len(self.static_resource_mapping)} 条")
        except Exception as e:
            print(f"  [staticResource] 响应解析失败: {e}")

    async def scroll_page(self, page: Page) -> None:
        """滚动页面以触发懒加载"""
        try:
            await page.mouse.wheel(0, 3000)
            await asyncio.sleep(0.5)
            await page.mouse.wheel(0, 3000)
            await asyncio.sleep(0.5)
            await page.mouse.wheel(0, 5000)
        except Exception as e:
            print(f"  滚动失败: {e}")

    async def click_all_tabs(self, page: Page) -> None:
        """循环切换所有 Tab，触发每个 Tab 的 submit-query 请求，直到数据稳定或超时"""
        print("开始循环切 Tab 并等待 submit-query 数据...")
        start_time = time.time()

        # v1 的 Tab 选择器（与 v2 不同）
        # v1 使用 .ant-tabs-tab 或 .tab-item 等 Antd 风格
        TAB_SELECTORS = [
            ".ant-tabs-tab",
            ".tab-nav-item",
            ".bi-tabs-tab",
            '[role="tab"]',
        ]

        # 等待 Tab 元素出现
        tabs_selector = None
        for sel in TAB_SELECTORS:
            try:
                await page.wait_for_selector(sel, timeout=8000)
                tabs_selector = sel
                print(f"  找到 Tab 选择器: {sel}")
                break
            except Exception:
                continue

        if not tabs_selector:
            # 没有 Tab，当前页面只有一个视图，直接滚动触发懒加载
            print("  未找到 Tab 元素，直接滚动触发加载...")
            await self.scroll_page(page)
            await asyncio.sleep(5)
            return

        round_num = 0
        while True:
            elapsed = time.time() - start_time
            round_num += 1

            if elapsed >= self.timeout:
                print(f"\n⏱️  已达 {self.timeout}s 超时，停止（共 {len(self.submit_query_results)} 份数据）")
                break

            # 超过2分钟且已有3份及以上数据，提前结束
            if elapsed >= 120 and len(self.submit_query_results) >= 3:
                print(f"\n✓ 已超2分钟且获得 {len(self.submit_query_results)} 份数据，提前结束")
                break

            data_count_before = len(self.submit_query_results) + len(self.mtbi_data_results)
            print(f"\n第 {round_num} 轮（已用时 {elapsed:.0f}s，已有 {data_count_before} 份数据）...")

            try:
                tabs = await page.query_selector_all(tabs_selector)
            except Exception:
                tabs = []

            tab_count = min(20, len(tabs))
            if not tabs:
                print("  Tab 列表为空，等待...")
                await asyncio.sleep(3)
                continue

            for i in range(tab_count):
                elapsed = time.time() - start_time
                if elapsed >= self.timeout:
                    break
                if elapsed >= 120 and len(self.submit_query_results) >= 3:
                    break

                try:
                    tabs = await page.query_selector_all(tabs_selector)
                    if i >= len(tabs):
                        break
                    tab = tabs[i]

                    # 判断是否已激活（多种框架的 class 名）
                    is_active = await tab.evaluate(
                        "el => el.classList.contains('ant-tabs-tab-active') || "
                        "el.classList.contains('active-tab') || "
                        "el.classList.contains('bi-tabs-tab-active') || "
                        "el.getAttribute('aria-selected') === 'true'"
                    )
                    if is_active and round_num > 1:
                        # 第一轮跳过已激活 tab，后续轮次不跳过（可能有新数据）
                        continue

                    # 记录 tab 名称
                    tab_title = await tab.evaluate(
                        "el => el.querySelector('.ant-tabs-tab-btn, .tab-title, [role=tab]')?.textContent?.trim() || el.textContent?.trim() || ''"
                    )
                    self.current_tab_name = tab_title
                    await tab.click()
                    await asyncio.sleep(3)
                    await self.scroll_page(page)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"  点击 Tab {i} 失败: {e}")

            # 情况2（moshu）和情况1（mtbi data）的数量合计
            data_count_after = len(self.submit_query_results) + len(self.mtbi_data_results)
            new_count = data_count_after - data_count_before
            print(f"  本轮新增 {new_count} 个数据")
            if data_count_after > 0 and new_count == 0:
                print("  数据已稳定，结束循环")
                break

        total_captured = len(self.submit_query_results) + len(self.mtbi_data_results)
        print(f"\n循环结束，共捕获 {total_captured} 个图表数据"
              f"（情况2-moshu: {len(self.submit_query_results)}，情况1-mtbi: {len(self.mtbi_data_results)}）")

    def convert_to_csv(self, key: str, result: Dict) -> Optional[str]:
        """将单个 submit-query 结果转换为 CSV，返回 (csv_path, meta) 或 None"""
        lid = result["lid"]
        col_names = result["col_names"]
        rows = result["data"]
        total = result["total"]
        tab_name = result["tab_name"]

        if not col_names or rows is None:
            print(f"  lid={lid}: 没有列或数据，跳过")
            return None

        # 截断处理
        truncated = len(rows) > self.max_rows
        if truncated:
            print(f"  数据行数 ({len(rows)}) 超过限制 ({self.max_rows})，截断至 {self.max_rows} 行")
            rows = rows[:self.max_rows]

        exported_rows = len(rows)

        # 生成文件名：tab_lid_列数cols_行数rows_时间戳[_truncated].csv
        run_dir = OUTPUT_DIR / self.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = "_truncated" if truncated else ""
        safe_tab = re.sub(r'[\\/:*?"<>|]', '_', tab_name) if tab_name else ""
        prefix = f"{safe_tab}_" if safe_tab else ""
        filename = f"{prefix}lid{lid}_{exported_rows}rows_{len(col_names)}cols_{timestamp}{suffix}.csv"
        output_path = run_dir / filename

        try:
            with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(col_names)
                for row in rows:
                    writer.writerow(row)

            print(f"  ✓ CSV已生成: {output_path}")
            print(f"    Tab:     {tab_name or '（无Tab）'}")
            print(f"    列名:    {', '.join(col_names)}")
            print(f"    总行数:  {total}，实际导出: {exported_rows}{'（已截断）' if truncated else ''}")
            return str(output_path)
        except Exception as e:
            print(f"  写入CSV失败: {e}")
            return None

    def convert_to_csv_mtbi(self, query_id: str, result: Dict) -> Optional[str]:
        """将情况1（mtbi）的单个 /data 响应转换为 CSV，返回 csv_path 或 None"""
        query_id_int = result.get("queryId", query_id)
        columns = result.get("columns", [])
        rows = result.get("data", [])
        total_num = result.get("totalNum", len(rows))
        tab_name = result.get("tab_name", "")

        if not columns or rows is None:
            print(f"  queryId={query_id}: 没有列或数据，跳过")
            return None

        # 用 staticResourceInfo 映射列名（code → 中文名），fallback 原 code
        mapped_columns = [
            self.static_resource_mapping.get(col, col) for col in columns
        ]
        # 把映射后的列名存回 result，供上传汇总时引用
        result["_mapped_col_names"] = mapped_columns

        # 截断处理
        truncated = len(rows) > self.max_rows
        if truncated:
            print(f"  数据行数 ({len(rows)}) 超过限制 ({self.max_rows})，截断至 {self.max_rows} 行")
            rows = rows[:self.max_rows]

        exported_rows = len(rows)

        # 文件名：tab_qid{queryId}_{行数}rows_{列数}cols_{时间戳}[_truncated].csv
        run_dir = OUTPUT_DIR / self.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = "_truncated" if truncated else ""
        safe_tab = re.sub(r'[\\/:*?"<>|]', '_', tab_name) if tab_name else ""
        prefix = f"{safe_tab}_" if safe_tab else ""
        filename = f"{prefix}qid{query_id_int}_{exported_rows}rows_{len(mapped_columns)}cols_{timestamp}{suffix}.csv"
        output_path = run_dir / filename

        try:
            with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(mapped_columns)
                for row in rows:
                    writer.writerow(row)

            print(f"  ✓ CSV已生成: {output_path}")
            print(f"    Tab:    {tab_name or '（无Tab）'}")
            print(f"    列名:   {', '.join(mapped_columns)}")
            print(f"    总行数: {total_num}，实际导出: {exported_rows}{'（已截断）' if truncated else ''}")
            return str(output_path)
        except Exception as e:
            print(f"  写入CSV失败: {e}")
            return None

    async def fetch(self) -> List[str]:
        """执行抓取主流程"""
        run_dir = OUTPUT_DIR / self.run_id
        print(f"开始抓取 v1 Dashboard: {self.dashboard_id}")
        print(f"URL: {self.base_url}")
        print(f"输出目录: {run_dir}")
        print(f"超时时间: {self.timeout}秒")
        print(f"最大行数: {self.max_rows}")
        print("=" * 60)

        self.playwright = await async_playwright().start()

        # 检测 CatPaw/OpenClaw 环境
        cdp_url = detect_catpaw(self.cdp_port)
        is_catpaw = cdp_url is not None
        if is_catpaw:
            print(f"检测到 CDP 环境，通过 CDP 连接内置浏览器 ({cdp_url})")

        # 启动/连接浏览器
        try:
            if is_catpaw:
                import urllib.request as _ur
                _version = json.loads(_ur.urlopen(cdp_url + "/json/version").read())
                _ws_url = _version["webSocketDebuggerUrl"]
                self.browser = await self.playwright.chromium.connect_over_cdp(_ws_url)
            else:
                self.browser = await self.playwright.chromium.launch(
                    headless=False,
                    args=['--disable-blink-features=AutomationControlled']
                )
        except Exception as e:
            print(f"启动浏览器失败: {e}")
            return []

        try:
            if is_catpaw:
                contexts = self.browser.contexts
                context = contexts[0] if contexts else None
                if context is None:
                    print("CatPaw: 无法获取浏览器 context")
                    return []

                all_pages = context.pages
                print(f"CatPaw: 共检测到 {len(all_pages)} 个 page")
                for i, p in enumerate(all_pages):
                    print(f"  [{i}] {p.url}")

                # 找 URL 包含目标 dashboard_id 的 page
                page = None
                for p in all_pages:
                    if str(self.dashboard_id) in p.url and "keetapp.com" in p.url:
                        page = p
                        break

                if page is None:
                    print(f"CatPaw: 未找到 dashboard_id={self.dashboard_id} 对应的 page，请先用 browser_action 导航到目标 URL")
                    return []

                print(f"CatPaw: 复用 page（URL: {page.url}）")

            else:
                context = await self.browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                )
                page = await context.new_page()

            # 注册响应监听器
            page.on('response', self.handle_response)

            # 访问页面
            try:
                await page.goto(self.base_url, timeout=self.timeout * 1000, wait_until='domcontentloaded')

                # 等待页面稳定
                await asyncio.sleep(3)
                try:
                    await page.wait_for_load_state('networkidle', timeout=30000)
                except Exception:
                    print("页面加载超时，继续...")
                    await asyncio.sleep(2)

                print("页面加载完成")

                # 循环切 Tab 触发所有 submit-query 请求
                await self.click_all_tabs(page)

                total_captured = len(self.submit_query_results) + len(self.mtbi_data_results)
                if not total_captured:
                    print("\n警告: 未捕获到任何数据")
                    print("可能的原因：")
                    print("1. 页面未完全加载，请检查网络")
                    print("2. 该 Dashboard 使用了其他未知接口格式")

            except Exception as e:
                print(f"访问页面失败: {e}")
                if not is_catpaw:
                    await context.close()
                return []

            if not is_catpaw:
                await context.close()

        except Exception as e:
            print(f"浏览器操作失败: {e}")
            return []
        finally:
            await self.cleanup()

        # 转换所有数据为 CSV
        csv_paths = []   # List of (path, result_meta)
        print("\n开始导出CSV...")

        # 情况2（moshu）
        for key, result in self.submit_query_results.items():
            lid = result["lid"]
            tab_name = result.get("tab_name", "")
            print(f"\n[情况2] 处理图表 (lid={lid}, tab={tab_name or '未知'})...")
            csv_path = self.convert_to_csv(key, result)
            if csv_path:
                csv_paths.append((csv_path, result))

        # 情况1（mtbi）
        for query_id, result in self.mtbi_data_results.items():
            tab_name = result.get("tab_name", "")
            print(f"\n[情况1] 处理图表 (queryId={query_id}, tab={tab_name or '未知'})...")
            csv_path = self.convert_to_csv_mtbi(query_id, result)
            if csv_path:
                # 构造与情况2兼容的 meta dict 供上传汇总使用
                meta = {
                    "tab_name": tab_name,
                    "col_names": result.get("_mapped_col_names", result.get("columns", [])),
                    "data": result.get("data", []),
                    "total": result.get("totalNum", 0),
                }
                csv_paths.append((csv_path, meta))

        print(f"\n抓取完成！共导出 {len(csv_paths)} 个CSV文件")
        return csv_paths


async def main():
    parser = argparse.ArgumentParser(description='MDBI Dashboard v1 数据抓取工具（submit-query 接口）')

    parser.add_argument('dashboard_id', type=int, nargs='?', help='Dashboard ID')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT,
                        help=f'超时时间（秒），默认{DEFAULT_TIMEOUT}，最大{MAX_TIMEOUT}')
    parser.add_argument('--max-rows', type=int, default=DEFAULT_MAX_ROWS,
                        help=f'最大行数，默认{DEFAULT_MAX_ROWS}')
    parser.add_argument('--env', choices=['st', 'prod'], default='prod',
                        help='环境：st（测试）或 prod（线上），默认prod')
    parser.add_argument('--url', type=str, default=None,
                        help='完整的 Dashboard URL（优先级高于 dashboard_id + env）')
    parser.add_argument('--check-env', action='store_true',
                        help='检查运行环境')
    parser.add_argument('--cdp-port', type=int, default=None,
                        help='手动指定 CDP 端口（如 9222）')
    args = parser.parse_args()

    if args.check_env:
        check_env()
        return

    # 从完整 URL 解析 dashboard_id 和 env
    if args.url:
        domain_match = re.search(r'(mdbi\.bi\.st\.keetapp\.com|bi\.keetapp\.com)', args.url)
        # v1 URL 格式: /dashboard/{id}（无 /v2/）
        id_match = re.search(r'/dashboard/(?:mobile/)?(\d+)', args.url)
        if domain_match and id_match:
            args.env = 'st' if 'mdbi.bi.st' in domain_match.group(1) else 'prod'
            args.dashboard_id = int(id_match.group(1))
            print(f"从URL解析: dashboard_id={args.dashboard_id}, env={args.env}")
        else:
            print(f"无法从URL解析 dashboard_id，请检查URL格式")
            sys.exit(1)

    if not args.dashboard_id:
        parser.print_help()
        sys.exit(1)

    if args.timeout > MAX_TIMEOUT:
        print(f"超时时间 {args.timeout}s 超过最大限制 {MAX_TIMEOUT}s，已自动调整")
        args.timeout = MAX_TIMEOUT

    fetcher = DashboardV1Fetcher(
        dashboard_id=args.dashboard_id,
        timeout=args.timeout,
        max_rows=args.max_rows,
        env=args.env,
        cdp_port=args.cdp_port,
        url=args.url,
    )

    fetcher.setup_signal_handler()
    csv_path_metas = await fetcher.fetch()   # List of (path, result_meta)

    if csv_path_metas:
        print("\n" + "=" * 60)
        print("取数完成！CSV 文件路径：")
        print("=" * 60)
        for path, meta in csv_path_metas:
            fname = os.path.basename(path)
            tab_name = meta.get('tab_name', '') or '（无Tab）'
            col_names = meta.get('col_names', [])
            total = meta.get('total', 0)
            exported = min(len(meta.get('data', [])), fetcher.max_rows)
            truncated = len(meta.get('data', [])) > fetcher.max_rows
            print(f"  {path}")
            print(f"    Tab:    {tab_name}")
            print(f"    列名:   {', '.join(col_names)}")
            print(f"    行数:   {exported}/{total}{'（已截断）' if truncated else '（完整）'}")
        print("=" * 60)
    else:
        print("\n抓取失败，请检查错误信息")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
