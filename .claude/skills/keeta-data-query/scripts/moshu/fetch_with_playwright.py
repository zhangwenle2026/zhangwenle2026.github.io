#!/usr/bin/env python3
"""
MDBI Dashboard 自动抓取脚本
使用 Playwright 进行浏览器自动化和数据抓取

功能：
1. 自动打开浏览器访问Dashboard
2. 触发所有Tab页
3. 捕获所有API请求响应（支持多个表）
4. 自动导出CSV
5. 支持超时控制和行数限制
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

# 尝试导入playwright
try:
    from playwright.async_api import async_playwright, Page, Browser, Request, Response
except ImportError:
    print("请先安装playwright:\n  pip3 install playwright -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com\n  PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright playwright install chromium")
    sys.exit(1)

# 默认配置
DEFAULT_TIMEOUT = 180  # 3分钟
MAX_TIMEOUT = 900      # 最大15分钟
DEFAULT_MAX_ROWS = 10000
OUTPUT_DIR = Path(__file__).parent.parent / "output"


def detect_catpaw(cdp_port: Optional[int] = None) -> Optional[str]:
    """检测 CatPaw/OpenClaw 环境，返回可用的 CDP URL；未检测到则返回 None。
    优先级：
      1. 环境变量 CATPAW_CDP_ENDPOINT（CatPaw 平台注入，有即为 CatPaw 环境）
      2. 命令行 --cdp-port
      3. 环境变量 CDP_URL
      4. 自动探测 OpenClaw 默认端口 9222
    """
    import urllib.request

    # CatPaw 平台会注入 CATPAW_CDP_ENDPOINT，有则直接使用，无需探测
    catpaw_endpoint = os.environ.get("CATPAW_CDP_ENDPOINT")
    if catpaw_endpoint:
        return catpaw_endpoint

    # 命令行参数
    if cdp_port is not None:
        url = f"http://127.0.0.1:{cdp_port}"
        try:
            urllib.request.urlopen(url + "/json/version", timeout=2)
            return url
        except Exception:
            return None

    # 环境变量 CDP_URL
    if "CDP_URL" in os.environ:
        url = os.environ["CDP_URL"]
        try:
            urllib.request.urlopen(url + "/json/version", timeout=2)
            return url
        except Exception:
            return None

    # 非 CatPaw 环境，探测 OpenClaw 默认端口
    url = "http://127.0.0.1:9222"
    try:
        urllib.request.urlopen(url + "/json/version", timeout=2)
        return url
    except Exception:
        return None


def check_env():
    """检查运行环境，缺失时输出安装命令并退出"""
    ok = True

    # 1. Python 版本
    if sys.version_info < (3, 8):
        print(f"[缺失] Python 版本过低（当前 {sys.version}），需要 3.8+")
        ok = False

    # 2. playwright 包
    try:
        import playwright  # noqa: F401
        print("[OK] playwright 已安装")
    except ImportError:
        print("[缺失] playwright 未安装，请执行：\n  pip3 install playwright -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com")
        ok = False

    # 3. Chromium 浏览器
    chromium_path = shutil.which("chromium") or shutil.which("chromium-browser")
    # 也检查 playwright 管理的 chromium
    pw_chromium = Path.home() / ".cache/ms-playwright"
    has_chromium = chromium_path or any(pw_chromium.glob("chromium-*/chrome-linux/chrome")) if pw_chromium.exists() else False
    # macOS 路径
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


class MdbiDataFetcher:
    """MDBI数据抓取器"""

    def __init__(
        self,
        dashboard_id: int,
        timeout: int = DEFAULT_TIMEOUT,
        max_rows: int = DEFAULT_MAX_ROWS,
        headless: bool = False,
        env: str = "st",  # "st" / "prod" / "prod-overseas" / "st-overseas"
        cdp_port: Optional[int] = None,
        url: Optional[str] = None,  # 完整URL，优先级高于 env+dashboard_id 构造
    ):
        self.dashboard_id = dashboard_id
        self.timeout = timeout
        self.max_rows = max_rows
        self.headless = headless
        self.env = env.lower()
        self.cdp_port = cdp_port
        # run_id 确定性生成：dashboard_id + 启动时间，方便定位输出目录
        self._start_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_id = f"{dashboard_id}_{self._start_ts}"

        # 根据环境选择基础URL；若传入完整URL则直接使用（保留mobile路径等）
        if url:
            self.base_url = url
        elif self.env == "st-overseas" or self.env == "st":
            self.base_url = f"https://mdbi.bi.st.keetapp.com/v2/dashboard/{dashboard_id}"
        else:
            # 默认境外生产环境
            self.base_url = f"https://bi.keetapp.com/v2/dashboard/{dashboard_id}"

        # 存储所有捕获的数据 - 支持多个表
        self.data_responses: Dict[int, Dict] = {}  # {lid: response}
        self.static_resource_response: Optional[Dict] = None

        # 捕获的数据列表
        self.captured_responses: List[Dict] = []

        # tab 前缀映射：{lid: tab_title}
        self.lid_to_tab: Dict[int, str] = {}
        self.current_tab_name: str = ""

    def setup_signal_handler(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            print("\n收到中断信号，正在清理...")
            if hasattr(self, 'browser') and self.browser:
                asyncio.create_task(self.cleanup())
            sys.exit(0)
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def cleanup(self):
        """清理资源"""
        if hasattr(self, 'browser') and self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    def should_capture_request(self, request: Request) -> bool:
        """判断是否应该捕获这个请求"""
        url = request.url
        # 捕获数据API - 使用正则匹配 /api/mtbi/bi/{数字}/data
        if re.search(r'/api/mtbi/bi/\d+/data', url):
            return True
        # 捕获元数据API
        if '/api/mtbi/bidata/metaData/staticResourceInfo' in url:
            return True
        return False

    async def handle_response(self, response: Response) -> None:
        """处理捕获的响应"""
        url = response.url

        try:
            # 只处理我们关心的API - 使用正则匹配
            if re.search(r'/api/mtbi/bi/\d+/data', url):
                # 提取lid
                match = re.search(r'/api/mtbi/bi/(\d+)/data', url)
                if match:
                    lid = int(match.group(1))
                    status = response.status
                    print(f"  [数据API] lid={lid}, status={status}")

                    try:
                        body = await response.json()
                        # 存储所有数据响应
                        self.data_responses[lid] = body
                        # 记录该 lid 归属的 tab
                        if lid not in self.lid_to_tab:
                            self.lid_to_tab[lid] = self.current_tab_name
                        self.captured_responses.append({
                            'type': 'data',
                            'url': url,
                            'body': body,
                            'lid': lid
                        })

                        # 检查是否需要分页
                        if body.get('code') == 0:
                            data = body.get('data', {})
                            total = data.get('totalNum', 0)
                            limit = 10000  # 默认limit
                            if total > limit:
                                print(f"      ⚠️  数据量: {total}行 (超过{limit}，需要分页)")
                        else:
                            print(f"      ❌ API错误: {body.get('message')}")
                    except Exception as e:
                        print(f"      ❌ 解析JSON失败: {e}")

            elif '/api/mtbi/bidata/metaData/staticResourceInfo' in url:
                status = response.status
                print(f"  [元数据API] status={status}")
                try:
                    body = await response.json()
                    self.static_resource_response = body
                    self.captured_responses.append({
                        'type': 'meta',
                        'url': url,
                        'body': body
                    })
                    if body.get('code') == 0:
                        data = body.get('data', [])
                        print(f"      ✓ 获得 {len(data)} 个列名映射")
                except Exception as e:
                    print(f"      ❌ 解析JSON失败: {e}")
        except Exception as e:
            print(f"处理响应失败: {e}")

    async def scroll_page_down(self, page: Page) -> None:
        """滚动到最后一个 chart-edit-view（非mobile）或 mobile-layout-item（mobile），确保所有懒加载内容触发"""
        try:
            # 优先使用非mobile的 chart-edit-view
            items = await page.query_selector_all('.chart-edit-view')
            selector_name = 'chart-edit-view'
            if not items:
                items = await page.query_selector_all('.mobile-layout-item')
                selector_name = 'mobile-layout-item'
            if items:
                last_item = items[-1]
                await last_item.scroll_into_view_if_needed()
                print(f"    ✓ 滚动到最后一个 {selector_name}（共 {len(items)} 个）")
            else:
                # fallback：在画面中部偏下执行大距离滚动
                viewport = page.viewport_size or {'width': 1920, 'height': 1080}
                await page.mouse.move(viewport['width'] // 2, int(viewport['height'] * 0.65))
                await page.mouse.wheel(0, 999999)
                print("    ✓ 未找到 chart-edit-view/mobile-layout-item，使用 fallback 滚动")
        except Exception as e:
            print(f"    滚动失败: {e}")

    async def click_all_tabs_fast(self, page: Page) -> None:
        """在3分钟时间窗口内，持续循环：切Tab → 等待 → 滚动到底，直到超时或数据稳定"""
        print("开始持续循环切Tab并触发懒加载...")
        start_time = time.time()

        try:
            await page.wait_for_selector('.tab-nav-item', timeout=10000)
        except Exception:
            print("未找到Tab元素，跳过")
            return

        tabs = await page.query_selector_all('.tab-nav-item')
        tab_count = min(20, len(tabs))
        print(f"找到 {len(tabs)} 个Tab元素，将处理前 {tab_count} 个")

        # 初始化：读取当前已激活的 tab 名称，避免首屏数据没有 tab 前缀
        for tab in tabs:
            is_active = await tab.evaluate("el => el.classList.contains('active-tab')")
            if is_active:
                self.current_tab_name = await tab.evaluate("el => el.querySelector('.tab-title')?.textContent?.trim() || ''")
                print(f"初始激活Tab: {self.current_tab_name}")
                break

        round_num = 0
        while True:
            elapsed = time.time() - start_time
            round_num += 1

            # 超时检查：最多3分钟
            if elapsed >= self.timeout:
                print(f"\n⏱️  已达 {self.timeout}s 超时，停止（共 {len(self.data_responses)} 份数据）")
                break

            # 提前结束：超过2分钟且已有3份及以上数据
            if elapsed >= 120 and len(self.data_responses) >= 3:
                print(f"\n✓ 已超2分钟且获得 {len(self.data_responses)} 份数据，提前结束")
                break

            data_count_before = len(self.data_responses)
            print(f"\n第 {round_num} 轮（已用时 {elapsed:.0f}s，已有 {data_count_before} 份数据）...")

            for i in range(tab_count):
                elapsed = time.time() - start_time
                if elapsed >= self.timeout:
                    break
                if elapsed >= 120 and len(self.data_responses) >= 3:
                    break

                try:
                    tabs = await page.query_selector_all('.tab-nav-item')
                    if i >= len(tabs):
                        break
                    tab = tabs[i]
                    # 已是当前选中的tab，跳过（数据已加载）
                    is_active = await tab.evaluate("el => el.classList.contains('active-tab')")
                    if is_active:
                        continue
                    # 记录即将激活的 tab 名称
                    tab_title = await tab.evaluate("el => el.querySelector('.tab-title')?.textContent?.trim() || ''")
                    self.current_tab_name = tab_title
                    await tab.click()
                    await asyncio.sleep(3)  # 等待数据加载
                    await self.scroll_page_down(page)  # 滚动到底触发懒加载
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

            # 本轮没有新数据，说明已全部加载完成
            data_count_after = len(self.data_responses)
            new_count = data_count_after - data_count_before
            print(f"  本轮新增 {new_count} 个数据API")
            if data_count_after > 0 and new_count == 0:
                print("  数据已稳定，结束循环")
                break

        print(f"\n循环结束，共捕获 {len(self.data_responses)} 个数据API")

    async def wait_for_data_loaded(self, timeout: int = 180) -> bool:
        """阻塞式等待数据加载完成"""
        print(f"等待数据加载完成（最多{timeout}秒）...")

        start_time = time.time()
        last_data_count = 0
        stable_count = 0
        check_interval = 1  # 检查间隔

        while time.time() - start_time < timeout:
            # 检查是否已收到数据
            if self.data_responses:
                data_count = len(self.data_responses)
                if data_count > last_data_count:
                    last_data_count = data_count
                    stable_count = 0
                    print(f"  ✓ 已收到 {data_count} 个数据API响应")
                else:
                    stable_count += 1

                # 如果数据稳定（连续5次检查没有新数据），则认为加载完成
                if stable_count >= 5:
                    print(f"✓ 数据加载完成！共收到 {data_count} 个数据API")
                    return True

            await asyncio.sleep(check_interval)

        print(f"⏱️  等待超时，已收到 {last_data_count} 个数据API")
        return last_data_count > 0

    def build_column_mapping(self) -> Dict[str, str]:
        """从staticResourceInfo构建列名映射"""
        mapping = {}
        if not self.static_resource_response:
            return mapping

        data = self.static_resource_response.get('data', [])
        if not isinstance(data, list):
            return mapping

        for item in data:
            code = item.get('code', '')
            name = item.get('name', '')
            if code and name:
                mapping[code] = name
        return mapping

    def convert_to_csv(self, lid: int, data_response: Dict, tab_name: str = "") -> Optional[str]:
        """将单个数据转换为CSV"""
        if not data_response:
            return None

        # 检查响应状态
        if data_response.get('code') != 0:
            print(f"  API返回错误: {data_response.get('message')}")
            return None

        data = data_response.get('data', {})
        columns = data.get('columns', [])
        rows = data.get('data', [])
        total_num = data.get('totalNum', 0)

        if not columns or not rows:
            print(f"  没有数据或列信息")
            return None

        # 构建列名映射
        column_mapping = self.build_column_mapping()

        # 映射列名
        mapped_columns = []
        for col in columns:
            if col in column_mapping:
                mapped_columns.append(column_mapping[col])
            else:
                mapped_columns.append(col)

        # 检查是否需要截断
        truncated = len(rows) > self.max_rows
        if truncated:
            print(f"  数据行数 ({len(rows)}) 超过限制 ({self.max_rows})，将截断保留前{self.max_rows}行")
            rows = rows[:self.max_rows]

        # 生成文件名（加 tab 前缀）
        run_dir = OUTPUT_DIR / self.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = "_truncated" if truncated else ""
        # 清理 tab_name 中不能用于文件名的字符
        safe_tab = re.sub(r'[\\/:*?"<>|]', '_', tab_name) if tab_name else ""
        prefix = f"{safe_tab}_" if safe_tab else ""
        filename = f"{prefix}lid{lid}_{timestamp}{suffix}.csv"
        output_path = run_dir / filename

        # 写入CSV
        try:
            with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(mapped_columns)
                for row in rows:
                    writer.writerow(row)

            print(f"  CSV已生成: {output_path}")
            print(f"  总行数: {total_num}, 实际导出: {len(rows)}")
            return str(output_path)
        except Exception as e:
            print(f"  写入CSV失败: {e}")
            return None

    async def fetch(self) -> List[str]:
        """执行抓取"""
        run_dir = OUTPUT_DIR / self.run_id
        print(f"开始抓取 Dashboard: {self.dashboard_id}")
        print(f"URL: {self.base_url}")
        print(f"输出目录: {run_dir}")
        print(f"超时时间: {self.timeout}秒")
        print(f"最大行数: {self.max_rows}")
        print("="*60)

        self.playwright = await async_playwright().start()

        # 检测 CatPaw/OpenClaw 环境
        cdp_url = detect_catpaw(self.cdp_port)
        is_catpaw = cdp_url is not None
        if is_catpaw:
            print(f"检测到 CDP 环境，通过 CDP 连接内置浏览器 ({cdp_url})")

        # 启动/连接浏览器
        try:
            if is_catpaw:
                # 用浏览器级别的 WebSocket URL 连接（/json/version），
                # 而非 page 级别（/json），否则 browser.contexts 为空
                from urllib.request import urlopen as _urlopen
                _version = json.loads(_urlopen(cdp_url + "/json/version").read())
                _ws_url = _version["webSocketDebuggerUrl"]
                self.browser = await self.playwright.chromium.connect_over_cdp(_ws_url)
            elif self.headless:
                self.browser = await self.playwright.chromium.launch(headless=True)
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
                # CatPaw Desk：复用已有 context，不能创建新 target
                contexts = self.browser.contexts
                context = contexts[0] if contexts else None
                if context is None:
                    print("CatPaw: 无法获取浏览器 context")
                    return []

                all_pages = context.pages
                print(f"CatPaw: 共检测到 {len(all_pages)} 个 page")
                for i, p in enumerate(all_pages):
                    print(f"  [{i}] {p.url}")

                # 优先找 URL 包含目标 dashboard 的 page（browser_action 已导航好）
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

            if not is_catpaw:
                page = await context.new_page()

            # 设置响应处理器
            page.on('response', self.handle_response)

            # 访问页面
            try:
                await page.goto(self.base_url, timeout=self.timeout * 1000, wait_until='domcontentloaded')

                # 额外等待让页面完全渲染
                await asyncio.sleep(3)

                # 等待页面稳定
                try:
                    await page.wait_for_load_state('networkidle', timeout=60000)
                except Exception:
                    print("页面加载超时，继续...")
                    await asyncio.sleep(2)

                print("页面加载完成")

                # 点击所有Tab，每个Tab等3s后滚动，循环直到数据稳定
                await self.click_all_tabs_fast(page)

                # 检查捕获的数据
                if not self.data_responses:
                    print("\n警告: 未捕获到数据API响应")
                    print("可能的原因：")
                    print("1. 该Dashboard没有数据")
                    print("3. 需要手动切换Tab来触发数据加载")
                    print("\n请在浏览器中完成以下操作：")
                    print("1. 扫码登录（如果需要）")
                    print("2. 手动切换各个Tab页")
                    print("3. 等待数据加载完成")
                    print("\n完成后在此窗口按回车继续...（或等待30秒）")
                    try:
                        await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(None, input),
                            timeout=30
                        )
                    except asyncio.TimeoutError:
                        print("超时，继续...")

                    # 再等待一会儿
                    await asyncio.sleep(5)

                if not self.static_resource_response:
                    print("\n警告: 未捕获到元数据API响应（列名映射可能不完整）")

            except Exception as e:
                print(f"访问页面失败: {e}")
                await context.close()
                return []

            await context.close()

        except Exception as e:
            print(f"浏览器操作失败: {e}")
            return []
        finally:
            await self.cleanup()

        # 转换所有数据为CSV
        csv_paths = []
        print("\n开始导出CSV...")
        for lid, data_response in self.data_responses.items():
            tab_name = self.lid_to_tab.get(lid, "")
            print(f"\n处理表 (lid={lid}, tab={tab_name or '未知'})...")
            csv_path = self.convert_to_csv(lid, data_response, tab_name)
            if csv_path:
                csv_paths.append(csv_path)

        print("\n抓取完成!")
        return csv_paths


async def main():
    parser = argparse.ArgumentParser(description='MDBI Dashboard 数据抓取工具')

    parser.add_argument('dashboard_id', type=int, nargs='?', help='Dashboard ID')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT, help=f'超时时间（秒），默认{DEFAULT_TIMEOUT}，最大{MAX_TIMEOUT}（15分钟）')
    parser.add_argument('--max-rows', type=int, default=DEFAULT_MAX_ROWS, help=f'最大行数，默认{DEFAULT_MAX_ROWS}')
    parser.add_argument('--headless', action='store_true', help='无头模式运行（需要已登录）')
    parser.add_argument('--env', choices=['st', 'prod'], default='prod', help='环境选择：st（测试环境）或 prod（线上环境），默认prod')
    parser.add_argument('--url', type=str, default=None, help='完整的Dashboard URL（可选，优先级高于 dashboard_id + env）')
    parser.add_argument('--check-env', action='store_true', help='检查运行环境（Python/Playwright/Chromium）')
    parser.add_argument('--cdp-port', type=int, default=None, help='手动指定 CDP 端口（覆盖自动检测，如 9222 或 50089）')
    args = parser.parse_args()

    # 环境检查模式
    if args.check_env:
        check_env()
        return  # check_env 内部会 sys.exit，这里作为保险

    # 如果传入了完整 URL，从中解析 dashboard_id 和 env
    if args.url:
        domain_match = re.search(r'(mdbi\.bi\.st\.keetapp\.com|bi\.keetapp\.com)', args.url)
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

    # 限制最大超时时间为15分钟
    if args.timeout > MAX_TIMEOUT:
        print(f"超时时间 {args.timeout}s 超过最大限制 {MAX_TIMEOUT}s（15分钟），已自动调整")
        args.timeout = MAX_TIMEOUT

    fetcher = MdbiDataFetcher(
        dashboard_id=args.dashboard_id,
        timeout=args.timeout,
        max_rows=args.max_rows,
        headless=args.headless,
        env=args.env,
        cdp_port=args.cdp_port,
        url=args.url,
    )

    fetcher.setup_signal_handler()

    csv_paths = await fetcher.fetch()

    if csv_paths:
        print("\n" + "="*60)
        print("取数完成！CSV 文件路径：")
        print("="*60)
        for path in csv_paths:
            print(f"  {path}")
        print("="*60)
    else:
        print("\n抓取失败，请检查错误信息")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
