---
name: dashboard-v1
description: "从美团魔数境外 v1 仪表板（bi.keetapp.com/dashboard/xxx、mdbi.bi.st.keetapp.com/dashboard/xxx，注意无 /v2/ 路径段）自动采集数据并导出为文枢下载链接或本地 CSV。触发条件：(1) 用户提供 v1 格式 Dashboard 链接（/dashboard/ 而非 /v2/dashboard/）；(2) 用户提到 v1 dashboard 取数。基于 pinchtab 浏览器自动化实现，无需 Playwright。"
---

# 路由B：v1 仪表板（普通仪表板）

> 适用于 `/dashboard/{id}` 格式链接（无 `/v2/`）

## Agent 行为规范（进入路由B后必须遵守）

1. **【意图确认优先】首次交互必须先询问意图**：当用户只给了 URL 而没有说明具体需求时，**必须先问用户**想要哪个 Tab/组件的数据，或是需要全量下载，再执行相应流程。严禁在未确认意图的情况下直接执行批量下载。

   标准询问话术（直接复制使用）：
   ```
   请问你需要：
   1. 下载全部 Tab 的数据（批量导出）
   2. 指定某个 Tab 下的数据（请告诉我 Tab 名称）
   3. 指定某个特定组件（请告诉我组件名称）
   ```

2. **【前置环境检查 —— 硬性前置门禁，不可跳过】按以下固定顺序执行前置检查流程：**

   **【第一步：残留 Tab 清理 —— 硬性前置步骤，不可跳过】**

   在执行 `preflight.py`/`preflight_win.py` 之前，**必须首先强制检查当前机器是否有 pinchtab server 在运行，如果有，则清理该 server 中所有实例的所有 tab，如果实例连接失败需要继续重试连接，server存在则实例必然存在，必须强制把当前实例中的tab清理干净，不可以实例连接失败就跳过清理的步骤**。这一步确保不会有上一轮残留的页面占用资源或干扰本次流程。

   **检测与清理步骤：**

   1. 检查 pinchtab server 是否在运行：
      ```bash
      export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH" && pinchtab instances 2>&1
      ```
      - 如果命令报错（如 `pinchtab: command not found` 或连接失败），说明没有 server 在运行，**跳过清理，直接进入第二步前置检查**。
      - 如果返回了实例列表（JSON 数组），继续步骤 2。

   2. 对每个运行中的实例，获取其 port 并列出所有 tab：
      ```bash
      pinchtab --server http://127.0.0.1:{port} tab 2>&1
      ```

   3. 对每个 tab，执行 `eval` 导航到 `about:blank` 使其自动释放：
      ```bash
      pinchtab --server http://127.0.0.1:{port} --tab {tab_id} eval "window.location.href='about:blank';'ok'" 2>&1
      ```
      > ⚠️ **不要使用 `pinchtab nav "about:blank"`**，会报 `invalid url`，必须用 eval 方式。

   4. 清理完成后，验证 tab 列表为空：
      ```bash
      pinchtab --server http://127.0.0.1:{port} tab 2>&1
      ```
      预期输出：`{"tabs": []}` — 表示所有 tab 已清理。如果仍有残留，重复步骤 3。

   > 💡 如果实例较多，也可以通过写入并执行以下 Python 脚本一次性清理所有实例的所有 tab：
   > ```python
   > import subprocess, json
   > raw = subprocess.check_output(["pinchtab", "instances"], stderr=subprocess.DEVNULL).decode()
   > instances = json.loads(raw)
   > cleaned = 0
   > for inst in instances:
   >     port = inst.get("port", "")
   >     if not port:
   >         continue
   >     server = f"http://127.0.0.1:{port}"
   >     try:
   >         tab_raw = subprocess.check_output(["pinchtab", "--server", server, "tab"], stderr=subprocess.DEVNULL).decode()
   >         tabs = json.loads(tab_raw).get("tabs", [])
   >     except Exception:
   >         continue
   >     for t in tabs:
   >         tid = t.get("id", "")
   >         if not tid:
   >             continue
   >         try:
   >             subprocess.run(["pinchtab", "--server", server, "--tab", tid, "eval", "window.location.href='about:blank';'ok'"], capture_output=True, timeout=5)
   >             cleaned += 1
   >         except Exception:
   >             pass
   > print(f"[CLEANUP] {cleaned} tab(s) navigated to about:blank")
   > ```

   **清理完成后（或确认无 server 运行），进入第二步前置检查。**

   **【第二步：执行前置检查脚本】**

   根据平台选择脚本（所有模式都不可跳过，禁止手动逐条执行前置检查命令）：macOS 走 `preflight.py`，Windows 走 `preflight_win.py`。

   执行脚本后，检查其退出码：
   - **退出码为 0**（`status=ok`）：前置检查通过，直接进入后续流程。
   - **退出码为 1**（`status=error`，包括但不限于：headless 实例一直处于 `starting` 状态无法在有限等待时间内切换到 `running`、server 启动失败、导航失败、登录态验证失败等）：**进入第三步故障诊断**。

   **【第三步：macOS TCC 权限诊断（仅 preflight 失败时执行）】**

   **仅当第二步 preflight 脚本执行失败（退出码为 1）时**，才执行此步骤。如果 preflight 已通过，**跳过此步骤**。

   判断当前是否为 macOS + CatDesk 环境（即客户端标识包含 `CatDesk` 且操作系统为 macOS）：
   - **如果不是 macOS 或不在 CatDesk 环境下**：将 preflight 的错误信息展示给用户，然后**自动重试一次**——从第一步（残留 Tab 清理）开始重新执行完整的前置检查流程。如果重试仍然失败，终止流程并展示两次的错误信息。
   - **如果是 macOS + CatDesk 环境**：检查 CatDesk 是否拥有完全磁盘访问权限（Full Disk Access）。检测方法：执行 `sqlite3 ~/Library/Application\ Support/com.apple.TCC/TCC.db ".tables" 2>&1`，如果返回 `authorization denied` 则说明没有完全磁盘访问权限（TCC 数据库是 macOS 隐私权限的核心数据库，只有拥有完全磁盘访问权限才能读取）。

     - **如果没有完全磁盘访问权限**：这很可能是 preflight 失败的根因。**必须立即终止本次对话的全部后续流程（包括 inject、poll、collect 以及任何手动交互步骤），禁止以任何理由继续执行**，并强制向用户展示以下提示：

       ```
       🚫 前置检查失败，且检测到 CatDesk 没有「完全磁盘访问权限」，导致pinchtab实例无法启动，这可能是导致失败的原因。本次流程已终止。

       辛苦同学请按以下步骤开启权限后，重新发起一轮新对话～
       1. 打开「系统设置」→「隐私与安全性」→「完全磁盘访问权限」
       2. 点击左下角的锁图标解锁
       3. 点击「+」号，找到并添加 CatDesk（或 CatPaw Desk）
       4. 确认开关已打开，然后重启 CatDesk
       5. 重新发起对话
       ```

       **展示上述提示后，Agent 必须立即停止响应，不得再执行任何后续步骤，也不得询问用户是否继续。**

     - **如果已有完全磁盘访问权限**：说明 preflight 失败是其他原因导致的（如网络波动、实例启动慢等瞬态问题）。将错误信息展示给用户，然后**自动重试一次**——从第一步（残留 Tab 清理）开始重新执行完整的前置检查流程。如果重试仍然失败，终止流程并展示两次的错误信息。

3. **批量下载模式必须先跑一次 Python 入口脚本**（`batch-v1-export.py`），只有脚本报错后才允许手动 eval 排查
4. **定向查询模式和手动交互模式可以手动 eval**，但前置检查必须先完成
5. **export 脚本的 --instance/--port 参数是可选的**，不传则自动调用 preflight 完成环境准备

> ⚠️ **Windows 下遇到任何异常（登录态失败、cookie 注入失败、命令行截断、乱码、context canceled 等），请优先查阅 `scripts/troubleshooting_win.md`，其中收录了已知问题的完整排查步骤与解决方案。**

---

## 意图判断（进入路由B后首先执行）

根据用户的请求意图，选择执行模式。**核心原则：smart-query（定向查询）是首选方案，批量模式仅在用户明确要求"全部 Tab 不加任何筛选条件地全量导出"时才使用，手动交互仅在 smart-query 失败后作为兜底。**

| 用户意图 | 模式 | 走法 |
|---------|------|------|
| 用户**没有指定任何 Tab 名称**，且明确要求"下载全量数据"、"把所有 Tab 数据下载下来"、"批量导出全部" | **批量模式** | → 跳转「批量模式」 |
| 指定了 Tab 名称或组件名称（如"下载XX tab"、"帮我下载XX组件"、"只要某个图表的数据"、"取XX tab 下的所有数据"），**包括同时指定多个 Tab 的情况** | **定向查询 auto** | → 直接跳转「定向查询模式 - Auto」，**不必再询问用户**。多个 Tab 时分别执行 smart-query，**不要走批量模式** |
| 指定了 Tab/组件，同时要求修改筛选条件（如"XX tab 下一级品类为美妆日化的数据"、"改个日期重新跑"） | **定向查询 auto**（带 filters） | → 跳转「定向查询模式 - Auto」，在 targets 的 filters 中传入用户指定的筛选条件 |
| "帮我看看有哪些指标"、"有哪些组件"、不确定要哪个组件 | **定向查询 interactive** | → 跳转「定向查询模式 - Interactive」，先列组件让用户选 |
| "只要XX维度"、"我要自己选维度指标"、需要精细控制字段，但不确定有哪些字段可选 | **定向查询 interactive** | → 跳转「定向查询模式 - Interactive」，展示维度指标后让用户选择 |
| 明确指定了要保留或去掉的维度/指标（如"只要日期和渠道"、"不看XX维度"、"去掉XX字段"），且已知组件名和 Tab 名 | **定向查询 auto**（带 select_fields） | → 跳转「定向查询模式 - Auto」，在 targets 的 `filters.select_fields` 中传入需要保留的字段白名单。也可先走 interactive 查看全部字段，再通过 resume 的 filters.select_fields 选择需要的列 |
| 只给了 URL，没有说明具体需求 | **先询问** | 询问用户："需要全量下载所有 Tab 的数据，还是指定某个 Tab/组件下载？" |

> ⚠️ **决策树**：smart-query（定向查询）覆盖了绝大多数场景，包括指定 Tab/组件下载、改日期重跑等。只有在 smart-query 明确报错失败后，才考虑降级到手动交互模式。**严禁跳过 smart-query 直接走手动交互。**

---

## 批量模式（全量导出）

使用内置的端到端批量导出 Python 脚本，自动完成全流程：导航 → 登录态检测 → 注入 JS 拦截器 → 逐 Tab 遍历触发查询 → 分片读取数据 → CSV 导出 → 输出结果。全量导出所有 Tab 数据，必须用 `--mode preflight/inject/poll/collect` 分步执行。

> ✅ **组件类型支持**：批量模式同时支持 **analysis 类型**（`chartType=analysis`，通过 `initAnalysisModel` 初始化 + `submitV2`/`dataResponses` 拦截）和 **dashboard 类型**（`chartType=dashboard`，通过 `submit-query` 异步轮询等待 SQL 完成）两种组件，均可自动获取文枢下载链接。

> ⚠️ **CatDesk/CatClaw 环境不支持流式输出**，脚本跑完才返回结果。必须使用分步执行模式（`--mode`），每步结束后把输出展示给用户，让用户实时感知进度。

> `{SKILL_DIR}` 为 skill 安装目录（即 `SKILL.md` 所在目录的父目录），如 `/root/.openclaw/skills/keeta-data-query`。

---

### 步骤1：前置检查（preflight）

初始化 pinchtab 环境，导航到目标页面，验证登录态。

```bash
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH" && python3 {SKILL_DIR}/scripts/batch-v1-export.py \
  --mode preflight \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}"
```

输出示例：
```
[INFO] === 阶段1：前置检查 ===
[INFO] 登录态有效
[ENV] instance=abc123 port=9222 tab_id=XXXXXXX
[INFO] 前置检查完成。请记录上方 [ENV] 信息，用于后续步骤。
```

**记录 `[ENV]` 行中的 `instance`、`port`、`tab_id`，后续步骤需要。**

**URL 校验：** 检查输出日志中 `Current URL:` 里的 dashboard ID 是否与用户给的 URL 中的 ID 一致。如果不一致：
- 如果重定向到另一个 dashboard ID，**这是正常的服务端重定向行为，不需要终止流程**。inject 阶段会用 `--url` 参数中的原始 URL 重新导航，能正确到达目标页面。只需记录 ENV 信息继续后续步骤即可。
- 如果跳转到 404 页面或登录页面，**终止流程**并告知用户。

把输出展示给用户，告知前置检查已通过。

---

### 步骤2：注入脚本（inject）

重载页面，注入批量导出脚本，触发后台异步执行。

```bash
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH" && python3 {SKILL_DIR}/scripts/batch-v1-export.py \
  --mode inject \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}" \
  --instance {instance} --port {port} --tab-id {tab_id} \
  --max-rows 10000
```

输出示例：
```
[INFO] === 阶段2：注入脚本 ===
[INFO] 注入批量导出脚本（max_rows=10000）...
[RUN_ID] 123456_20260418_153022
[INFO] 脚本已注入，批量导出正在后台执行。
```

**记录 `[RUN_ID]`，collect 阶段需要。**
把输出展示给用户，告知脚本已开始运行。

---

### 步骤3：轮询进度（poll）

每次读取一次当前进度，立即返回。**Agent 需每隔 15~30 秒执行一次，直到 `phase=done` 或 `phase=error`，每次都把结果展示给用户。**

```bash
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH" && python3 {SKILL_DIR}/scripts/batch-v1-export.py \
  --mode poll \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}" \
  --instance {instance} --port {port} --tab-id {tab_id}
```

输出示例（进行中）：
```
[STATUS] {"phase":"running","progress":3,"total":8,"message":"正在处理 Tab: 概览 (3/8)"}
[INFO] 当前状态: phase=running progress=3/8 正在处理 Tab: 概览 (3/8)
[INFO] ⏳ 进行中，请稍后重试 --mode poll
```

输出示例（完成）：
```
[STATUS] {"phase":"done","progress":8,"total":8,"message":"全部完成"}
[INFO] ✅ 批量导出完成，可以执行 --mode collect 读取结果
```

- `phase=done` → 继续步骤4
- `phase=error` → 脚本报错，把错误信息展示给用户，排查后可从步骤2重新注入
- `phase=pending` → 页面仍在加载，等待后重试

---

### 步骤4：读取结果（collect）

读取浏览器内存中的结果数据，生成本地 CSV 或输出文枢链接。

```bash
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH" && python3 {SKILL_DIR}/scripts/batch-v1-export.py \
  --mode collect \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}" \
  --instance {instance} --port {port} --tab-id {tab_id} \
  --run-id {run_id}
```

把汇总结果完整展示给用户：
- 有 `FileUrl` 的组件 → 以裸链接形式告知用户
- 有本地 CSV 的组件 → 告知文件路径
- 数据为空的组件 → 明确告知"数据为空"
- 未覆盖的组件 → 建议使用定向查询模式

---

### 可选参数说明

| 参数 | 适用 mode | 默认值 | 说明 |
|------|----------|--------|------|
| `--max-rows` | inject | 10000 | 每组件最大行数（最大 100000） |
| `--instance` | inject/poll/collect | 无 | headless 实例 ID（步骤1 输出） |
| `--port` | inject/poll/collect | 无 | headless 实例端口（步骤1 输出） |
| `--tab-id` | inject/poll/collect | 无 | 浏览器 tab ID（步骤1 输出） |
| `--run-id` | collect | 无 | 本次导出 run ID（步骤2 输出） |

---

### 常见错误处理

- `[需要登录]` → 告知用户登录态失效，重新从步骤1开始
- `phase=error` → 把错误信息告知用户，从步骤2重新注入
- collect 报"无法读取 __batchResults" → poll 尚未返回 done，等待后重试
- 部分组件 NO_PERMISSION → 正常，汇总中标注，其他组件照常输出

> ⚠️ 批量模式完成后，**无需**再走手动交互流程。

---

## 定向查询模式（smart-query）⭐ 首选方案

> **📌 这是单组件/少量组件下载的首选方案。** 用户指定 Tab 或组件名称时，应直接走此模式，不需要先走手动交互。
>
> 使用 `smart-query-export.py` + `smart-query.js` 自动完成：拦截请求体 → 匹配目标组件 → 可选修改筛选条件 → 下载 → 输出文枢链接。
> 支持三种子模式：**auto**（分步执行 `--mode preflight/inject/poll/collect`）、**interactive**（分步执行 `--mode preflight/interactive/resume`，先看再选）、**resume**（interactive 会话中多轮选择）。

**前提：** 已完成前置条件（pinchtab 环境就绪）。无需提前导航到 dashboard 页面，脚本会自动导航。

> 💡 **与手动交互模式的关系**：smart-query 内部已自动完成拦截器注入、请求体匹配、下载提交等全部步骤。只有当 smart-query 报错（如 DOM 诊断返回 `query_intercept`、`unknown` 等特殊情况）且无法自动处理时，才降级到手动交互模式。

---

### 子模式选择

| 用户意图 | 子模式 | 说明 |
|---------|--------|------|
| 明确指定了组件名 + tab 名 | **auto** | 分步执行（`--mode preflight` → `inject` → `poll` → `collect`），不需要交互 |
| "帮我看看有哪些组件/指标"、不确定组件名、需要先看列表 | **interactive** | 分步执行（`--mode preflight` → `interactive` → `resume`），先列出组件列表，等用户选择后下载 |
| interactive 列出后用户选择下载 | **resume** | 发送选择，触发下载（`--mode resume`） |

---

### Auto 模式（指定组件名直接下载）

用户已明确目标组件名称和 tab 名时使用。名称支持模糊匹配。

> ⚠️ **必须使用 `--mode` 分步执行**（preflight → inject → poll → collect），避免多组件串行超时。每步结束后把输出展示给用户，让用户实时感知进度。

---

#### 步骤1：前置检查（preflight）

初始化 pinchtab 环境，导航到目标页面，验证登录态。

```bash
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH" && python3 {SKILL_DIR}/scripts/smart-query-export.py \
  --mode preflight \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}"
```

输出示例：
```
[INFO] === 定向查询 - 阶段1：前置检查 ===
[INFO] 登录态有效
[ENV] instance=abc123 port=9222 tab_id=XXXXXXX
[INFO] 前置检查完成
```

**记录 `[ENV]` 行中的 `instance`、`port`、`tab_id`，后续步骤需要。**

**URL 校验：** 检查输出日志中 `Current URL:` 里的 dashboard ID 是否与用户给的 URL 中的 ID 一致。如果不一致：
- 如果重定向到另一个 dashboard ID，**这是正常的服务端重定向行为，不需要终止流程**。inject 阶段会用 `--url` 参数中的原始 URL 重新导航，能正确到达目标页面。只需记录 ENV 信息继续后续步骤即可。
- 如果跳转到 404 页面或登录页面，**终止流程**并告知用户。

---

#### 步骤2：注入并执行（inject）

注入 smart-query.js，执行目标组件查询。targets 参数与原 auto 模式相同。

```bash
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH" && python3 {SKILL_DIR}/scripts/smart-query-export.py \
  --mode inject \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}" \
  --instance {instance} --port {port} --tab-id {tab_id} \
  --targets '[{"name":"组件名关键词","tab":"Tab名称"}]'
```

**修改日期筛选：**

```bash
python3 {SKILL_DIR}/scripts/smart-query-export.py \
  --mode inject \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}" \
  --instance {instance} --port {port} --tab-id {tab_id} \
  --targets '[{"name":"组件名","tab":"Tab名","filters":{"date":{"value":["2025-03-01","2025-04-01"]}}}]'
```

**修改维度筛选（如指定应用ID）：**

```bash
python3 {SKILL_DIR}/scripts/smart-query-export.py \
  --mode inject \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}" \
  --instance {instance} --port {port} --tab-id {tab_id} \
  --targets '[{"name":"组件名","tab":"Tab名","filters":{"dimensions":{"resource_id":["183287"]}}}]'
```

**指定保留的维度/指标列（select_fields 白名单）：**

> 当用户要求自定义输出的维度/指标列时（如"只要XX维度"、"不看XX维度"、"去掉XX字段"、"只保留日期和渠道"），使用 `filters.select_fields` 传入需要**保留**的字段名称列表（白名单机制）。未出现在列表中的维度/指标列将被移除。字段名称需与 interactive 输出的 Dimensions / Indicators 名称一致。

```bash
python3 {SKILL_DIR}/scripts/smart-query-export.py \
  --mode inject \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}" \
  --instance {instance} --port {port} --tab-id {tab_id} \
  --targets '[{"name":"组件名","tab":"Tab名","filters":{"select_fields":["日期","一级渠道","二级渠道","dau","gmv订单量"]}}]'
```

**组合使用（同时修改日期 + 指定保留字段）：**

```bash
python3 {SKILL_DIR}/scripts/smart-query-export.py \
  --mode inject \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}" \
  --instance {instance} --port {port} --tab-id {tab_id} \
  --targets '[{"name":"组件名","tab":"Tab名","filters":{"date":{"value":["20250401"]},"select_fields":["日期","一级渠道","dau"]}}]'
```

**多组件同时下载：** targets 数组传多个对象即可。

输出示例：
```
[INFO] === 定向查询 - 阶段2：注入脚本 ===
[INFO] 注入 smart-query.js 并执行，共 2 个目标组件
[INFO] 脚本已注入，后台异步执行中
```

---

#### 步骤3：轮询进度（poll）

每次读取一次当前进度，立即返回。**Agent 需每隔 15~30 秒执行一次，直到 `phase=done` 或 `phase=error`，每次都把结果展示给用户。**

```bash
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH" && python3 {SKILL_DIR}/scripts/smart-query-export.py \
  --mode poll \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}" \
  --instance {instance} --port {port} --tab-id {tab_id}
```

输出示例（进行中）：
```
[STATUS] {"phase":"running","progress":1,"total":2,"message":"正在处理目标 1/2"}
[INFO] ⏳ 进行中，请稍后重试 --mode poll
```

输出示例（完成）：
```
[STATUS] {"phase":"done","progress":2,"total":2,"message":"全部完成"}
[INFO] ✅ 定向查询完成，可以执行 --mode collect 读取结果
```

- `phase=done` → 继续步骤4
- `phase=error` → 脚本报错，把错误信息展示给用户，排查后可从步骤2重新注入
- `phase=pending` → JS 尚未开始执行，等待后重试

---

#### 步骤4：读取结果（collect）

读取浏览器内存中的结果，输出文枢下载链接或错误信息。

```bash
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH" && python3 {SKILL_DIR}/scripts/smart-query-export.py \
  --mode collect \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}" \
  --instance {instance} --port {port} --tab-id {tab_id}
```

**输出：** 每个组件的 fileUrl（裸链接）或错误信息。把结果完整展示给用户。

---

### Interactive 模式（先列组件再选择）
用户想看有哪些组件/维度/指标，或不确定具体组件名时使用。
> ⚠️ **推荐使用 `--mode` 分步执行**（preflight → interactive → resume），每步结束后把输出展示给用户。也支持旧的一体化参数 `--interactive` / `--resume`，但分步模式更可靠。
---
#### 步骤1：前置检查（preflight）
与 Auto 模式共用同一个 preflight 步骤，初始化 pinchtab 环境。
```bash
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH" && python3 {SKILL_DIR}/scripts/smart-query-export.py \
  --mode preflight \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}"
```
**记录 `[ENV]` 行中的 `instance`、`port`、`tab_id`，后续步骤需要。**
---
#### 步骤2：扫描组件列表（interactive）
reload 页面 → 注入 smart-query.js（interactive 模式）→ poll 到 awaiting_input → 输出组件列表。
```bash
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH" && python3 {SKILL_DIR}/scripts/smart-query-export.py \
  --mode interactive \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}" \
  --instance {instance} --port {port} --tab-id {tab_id} \
  --tab "Tab名称" \
  --timeout 300
```
- `--tab` 可多次指定（如 `--tab Tab1 --tab Tab2`）
- 不传 `--tab` 则扫描全部 tab（耗时较长，建议 `--timeout 600`）
- 输出：编号列表，每个组件展示 Dimensions、Indicators、Filters
- 输出末尾有 `--instance`、`--port`、`--tab-id` 信息，供 resume 使用
**展示给用户时**：将组件列表格式化展示，询问用户要下载哪些组件、是否需要修改筛选条件。
---
#### 步骤3：用户选择后下载（resume）
```bash
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH" && python3 {SKILL_DIR}/scripts/smart-query-export.py \
  --mode resume \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}" \
  --instance {instance} --port {port} --tab-id {tab_id} \
  --select '[{"index": 0, "filters": {}}, {"index": 5, "filters": {}}]'
```
- `index` 从 0 开始，对应 interactive 输出的编号 - 1
- `filters` 可选：`{"date": {"value": [...]}}` 修改日期、`{"dimensions": {"field_code": [...]}}` 修改维度筛选值、`{"select_fields": ["字段名1", "字段名2", ...]}` 指定保留的维度/指标列（白名单，未列出的列将被移除）。三者可组合使用
- 支持多组件同时下载
- **可重复执行**：每次 resume 都输出本轮新增结果，会话保持 active
#### 步骤4：结束会话
```bash
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH" && python3 {SKILL_DIR}/scripts/smart-query-export.py \
  --mode resume \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}" \
  --instance {instance} --port {port} --tab-id {tab_id} \
  --done
```
---
#### 旧参数（一体化模式，兼容保留）
> 以下旧参数仍可使用，但推荐使用上面的 `--mode` 分步方式。

**一体化列出组件（`--interactive`）：**
```bash
python3 {SKILL_DIR}/scripts/smart-query-export.py \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}" \
  --interactive \
  --tab "Tab名称" \
  --timeout 300
```
**一体化 resume（`--resume`）：**
```bash
python3 {SKILL_DIR}/scripts/smart-query-export.py \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}" \
  --resume \
  --instance {instance_id} --port {port} --tab-id {tab_id} \
  --select '[{"index": 0, "filters": {}}, {"index": 5, "filters": {}}]'
```
**一体化结束会话（`--resume --done`）：**
```bash
python3 {SKILL_DIR}/scripts/smart-query-export.py \
  --url "https://bi.keetapp.com/dashboard/{dashboardId}" \
  --resume --done \
  --instance {instance_id} --port {port} --tab-id {tab_id}
```

---

### 参数说明

| 参数 | 适用模式 | 说明 |
|------|---------|------|
| `--url` | 全部 | 仪表板 URL（必填） |
| `--mode` | auto / interactive（分步） | 分步执行模式：`preflight` / `inject` / `poll` / `collect`（auto）或 `preflight` / `interactive` / `resume`（interactive）。与 `--interactive`/`--resume` 旧参数互斥 |
| `--targets` | auto（inject） | 目标组件 JSON 数组 |
| --interactive | interactive（旧参数） | 一体化交互模式（与 --mode 互斥，推荐用 --mode interactive） |
| `--tab` | interactive | 只扫描指定 tab（可多次，不传则全扫） |
| --resume | resume（旧参数） | 一体化 resume（与 --mode 互斥，推荐用 --mode resume） |
| `--select` | resume | 选择参数 JSON 数组 `[{index, filters}]` |
| `--tab-id` | resume / auto（分步） | interactive 或 preflight 输出的 tab ID |
| `--done` | resume | 结束 interactive 会话 |
| `--instance` | 全部（可选） | pinchtab 实例 ID（不传自动 preflight） |
| `--port` | 全部（可选） | pinchtab 实例端口 |
| `--timeout` | 全部 | 超时秒数（默认 300，最大 900） |

---

### 下载机制

smart-query 对每个组件执行三级 fallback：

1. **download_submit**（analysis 类型）/ **moshu_download**（dashboard 类型）→ 返回文枢 S3 链接
2. **submit-query-sync**（dashboard 类型）→ 同步获取数据
3. **data_intercept** → 使用 Phase 1 拦截到的原始数据

每个组件独立尝试下载，无全局权限开关。无下载权限时快速失败（<1s）后自动降级。

### DOM 诊断

组件拦截失败时自动执行 DOM 检查（<1ms），诊断原因：

| 原因 | 说明 |
|------|------|
| `query_intercept` | 组件需要先选择筛选条件才能查询 |
| `no_permission` | 无数据权限 |
| `auth_required` | 缺少指标/维度鉴权 |
| `still_loading` | 组件仍在加载中 |
| `no_data` | 查询结果为空 |
| `unknown` | 可能使用了非标准 API（如 start-point） |

---

## 权限预检

> 在导航到目标 Tab 之前，先检查当前用户是否有该仪表板的下载权限。
> v1 仪表板可通过 `window.__DASHBOARD_DEBUG__` 全局变量直接读取权限信息。
> 若无权限，直接告知用户，**不再继续后续步骤**。

先导航到仪表板页面（不带 hash），等待页面加载完成后执行：

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var d=window.__DASHBOARD_DEBUG__;if(!d||!d.engineInstance)return JSON.stringify({ready:false});var p=d.engineInstance.permissionInfo||{};return JSON.stringify({ready:true,canDownload:p.canDownload,canEdit:p.canEdit,projectId:p.projectId,contentManagers:p.contentManagers||[]})})()"
```

返回示例：
```json
{
  "ready": true,
  "canDownload": true,
  "canEdit": true,
  "projectId": 106127,
  "contentManagers": [{"id": 2658149, "name": "张瑜", "login": "zhangyu181"}]
}
```

- `canDownload: true` → 继续后续步骤
- `canDownload: false` → **停止执行**，告知用户：

```
⚠️ 当前账号对该仪表板没有下载权限（canDownload=false）。
仪表板管理员：{contentManagers 中的 name (login)}
请联系管理员申请下载权限后重试。
```

- `ready: false` → `__DASHBOARD_DEBUG__` 尚未挂载，等待几秒后重试（最多 15 秒）

---

## 手动交互模式 - Analysis 组件（兜底方案）

> ⚠️ **这是兜底方案，仅在 smart-query（定向查询）明确失败后才使用。** 常见降级场景：smart-query DOM 诊断返回 `query_intercept`（组件需先选筛选条件）、`unknown`（非标准 API），或脚本报错无法自动处理。
>
> 适用于 `chartType=analysis` 的组件，走 `submit/v2` → `download/submit` → 轮询 fileUrl 链路。

### 步骤1：导航到目标 Tab

> 直接带 `#tab-{tid}` hash 导航，浏览器会在页面加载后自动定位到目标 Tab。
> `tid` 从步骤2获取（需先用不带 hash 的 URL 取一次 Tab 列表，再重新导航）。
> 若还不知道 tid，先用不带 hash 的 URL 导航，完成步骤2获取 tid 后再重新执行步骤1。

```bash
# 不带 hash（首次，用于获取 Tab 列表）
$PINCHTAB instance navigate $HEADLESS_INST "https://bi.keetapp.com/dashboard/{dashboardId}" 2>&1
# 记录 tabId 为 $TAB_ID

# 带 hash（确定目标 Tab 的 tid 后重新导航，触发目标 Tab 渲染）
$PINCHTAB instance navigate $HEADLESS_INST "https://bi.keetapp.com/dashboard/{dashboardId}#tab-{tid}" 2>&1
# 记录新 tabId 为 $TAB_ID（覆盖上面的值）
```

### 步骤2：获取 Tab 列表

> fetch 是异步的，两条命令之间需等待 1~2 秒让请求完成，否则 `window.__dashInfo` 还未赋值会报错。
> ⚠️ 所有 eval 命令必须带 `--server` 和 `--tab` 参数，确保操作在正确的 headless 实例和 tab 上执行。

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "fetch('/api/moshu/api/v2/dashboards/{dashboardId}?isOnline=1&version=112').then(r=>r.json()).then(d=>window.__dashInfo=d); 'fetching...'"
```

```bash
# 等待 1~2 秒后执行
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "JSON.stringify(window.__dashInfo.data.tabList.map(t => ({tabId: t.tabId, tid: t.tid, name: t.tabName})), null, 2)"
```

### 步骤3：获取组件列表

> 同样需要等待 fetch 完成后再读取结果。

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "var tab0 = window.__dashInfo.data.tabList[{TAB_INDEX}]; fetch('/api/moshu/api/v2/dashboards/{dashboardId}/tabs/'+tab0.tabId+'?isOnline=1&tid='+tab0.tid+'&version=112').then(r=>r.json()).then(d=>window.__tabDetail=d); 'fetching...'"
```

```bash
# 等待 1~2 秒后执行
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "JSON.stringify(window.__tabDetail.data.componentList.filter(c=>c.chartType==='analysis').map(c => ({chartType:c.chartType, id: c.analysisChartId, name: c.componentSettings.name, bizId: c.componentSettings.bizId, cid: c.cid})), null, 2)"
```

> 💡 **`cid` 字段即为 DOM 中的 `id` 属性**（如 `chart-axzl9-f5806`），是步骤4定位组件容器的关键，务必记录。
>
> 💡 如果目标组件的 `chartType` 为 `dashboard`，**停止使用本流程**，改用「手动交互模式 - Dashboard 组件」。

### 步骤4：拦截 submit/v2 请求体

> ⚠️ **submit/v2 请求体不可手工构造！** context 中包含 20+ 必填字段，缺任一个都会返回 99999。唯一可靠方式是拦截真实请求体作为模板，基于模板修改。
>
> 💡 **触发原理**：组件筛选区有独立的"查询"按钮（`pinchtab snap` 中显示为 `button "查询"`），用 `pinchtab click`（CDP 真实鼠标事件）点击即可触发 submit/v2 请求。JS `element.click()` 无效（Vue 事件层拦截），必须用 pinchtab click。
>
> ⚠️ 组件必须在视口内才能被 pinchtab click 点击，否则报 "element center is outside viewport"。用 `scrollIntoView` 保证组件在视口中央。
>
> 💡 **`cid` 即 DOM `id`**：步骤3返回的 `cid` 字段（如 `chart-axzl9-f5806`）就是组件容器的 DOM `id`，直接用 `document.getElementById(cid)` 定位。

**4.1 等待目标组件渲染进 DOM（轮询，最多 15 秒）**

```bash
# 替换 {CID} 为目标组件的 cid（如 chart-axzl9-f5806）
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var el=document.getElementById('{CID}');return el?'found':'not found'})()"
```

- 返回 `found` → 继续4.2
- 返回 `not found` → 等1秒重试，超过15秒仍未找到则执行以下 JS click Tab 切换后再轮询：
  ```bash
  # TAB_INDEX 为目标 Tab 在列表中的序号（0开始）
  $PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "document.querySelectorAll('.tab-item-title')[{TAB_INDEX}].click();'clicked'"
  # 等3秒后重新轮询
  ```

**4.2 scrollIntoView 让目标组件进视口**

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "document.getElementById('{CID}').scrollIntoView({block:'center'});'scrolled'"
```

**4.3 装拦截器（fetch + XHR 双拦截）**

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){window.__allRequests=[];var _f=window.fetch;window.fetch=function(url,opts){var u=typeof url==='string'?url:(url&&url.url)||'';var body=opts&&opts.body;window.__allRequests.push({url:u,body:body});return _f.apply(this,arguments)};var _xs=XMLHttpRequest.prototype.send;XMLHttpRequest.prototype.send=function(b){if(this.__xoa)window.__allRequests.push({url:this.__xoa.url,body:b});return _xs.apply(this,arguments)};var _xo=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(m,u){this.__xoa={method:m,url:u};return _xo.apply(this,arguments)};return 'ok'})()"
```

**4.4 snap 找查询按钮，逐个 pinchtab click 直到匹配目标 resourceId**

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID snap -i -c --max-tokens 300
```

对每个 `button "查询"` 的 ref（如 e7、e10）：

```bash
# 点击查询按钮（只点视口内的，视口外的跳过）
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID click {查询按钮ref}

# 等5秒后检查拦截结果
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var reqs=window.__allRequests.filter(function(r){return r.url&&r.url.includes('submit/v2')});return JSON.stringify(reqs.map(function(r){var b=r.body?JSON.parse(r.body):{};return {resourceId:b.context&&b.context.resourceId,resourceName:b.context&&b.context.resourceName}}))})()"
```

- resourceId 匹配目标 → 继续4.5
- 不匹配 → 重装拦截器，点下一个查询按钮
- 报 "element center is outside viewport" → 跳过该按钮，点下一个

**4.5 从拦截到的请求体提取维度、指标、筛选条件**

```bash
# 替换 {TARGET_ID} 为目标 analysisChartId

# 维度（refType===2）
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var reqs=window.__allRequests.filter(function(r){return r.url&&r.url.includes('submit/v2')});var req=reqs.slice().reverse().find(function(r){var b=JSON.parse(r.body);return b.context&&b.context.resourceId==={TARGET_ID}});var fields=JSON.parse(req.body).access.select.fields;return JSON.stringify(fields.filter(function(f){return f.refType===2}).map(function(f){return {id:f.id,name:f.name,code:f.code}}),null,2)})()"

# 指标（refType===1）
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var reqs=window.__allRequests.filter(function(r){return r.url&&r.url.includes('submit/v2')});var req=reqs.slice().reverse().find(function(r){var b=JSON.parse(r.body);return b.context&&b.context.resourceId==={TARGET_ID}});var fields=JSON.parse(req.body).access.select.fields;return JSON.stringify(fields.filter(function(f){return f.refType===1}).map(function(f){return {id:f.id,name:f.name,code:f.code}}),null,2)})()"

# 筛选条件（如日期）
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var reqs=window.__allRequests.filter(function(r){return r.url&&r.url.includes('submit/v2')});var req=reqs.slice().reverse().find(function(r){var b=JSON.parse(r.body);return b.context&&b.context.resourceId==={TARGET_ID}});return JSON.stringify(JSON.parse(req.body).access.filter,null,2)})()"
```

**4.6 获取组件内嵌筛选器（submit/v2 中不含组件级筛选，需单独获取）**

> ⚠️ 组件内嵌的筛选器（如"核心终端"等维值筛选）不会出现在 submit/v2 的 `access.filter` 中，需从组件配置接口单独获取。

```bash
# 获取组件详情（替换 {ANALYSIS_CHART_ID}）
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "fetch('/api/moshu/api/v2/dashboards/component/{ANALYSIS_CHART_ID}').then(r=>r.json()).then(d=>window.__compDetail=d); 'fetching...'"
```

```bash
# 等待 1~2 秒后解析组件内嵌筛选器列表
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var dc=window.__compDetail.data.dataConf;var conf=typeof dc==='string'?JSON.parse(dc):dc;var filters=conf.fieldAreaCacls&&conf.fieldAreaCacls.config&&conf.fieldAreaCacls.config.filters||[];return JSON.stringify(filters.map(function(f){var isDateParam=f.field&&f.field.paramName;var isNoFilter=f.config&&f.config[0]&&f.config[0].condition&&f.config[0].condition.isNoFilter;var values=f.config&&f.config[0]&&f.config[0].values;return {name:isDateParam?f.field.paramName:f.field&&f.field.name,type:isDateParam?'日期参数':'维值筛选',shared:f.shared,isRepeatWithOuterFilter:f.isRepeatWithOuterFilter||false,isNoFilter:isNoFilter||false,currentValues:values}}),null,2)})()"
```

输出示例及含义：

| 字段 | 含义 |
|------|------|
| `isRepeatWithOuterFilter:true` | 该筛选来自全局看板筛选器，与外层日期联动 |
| `isNoFilter:true` | 当前未启用过滤（即全选，不限制） |
| `shared:true` | 全局共享筛选器，影响所有组件 |
| `currentValues` | 当前筛选值，空数组表示未选择 |

**👉 将以下信息完整展示给用户，并询问选择：**

1. **维度列表**（可增删）
2. **指标列表**（可增删）
3. **全局筛选条件**（来自 submit/v2 的 `access.filter`，如日期，询问是否修改）
4. **组件内嵌筛选器**（来自组件配置，逐一说明当前状态）：
   - `isNoFilter:true`：当前"不过滤"，询问用户是否要限定具体值
   - `isRepeatWithOuterFilter:true`：全局日期筛选，已在上面处理
   - 其他：展示当前 `currentValues`，询问是否修改

### 步骤5：修改请求体 + 提交查询获取 queryId

> ⚠️ **日期参数的传递方式**：v1 仪表板的日期不通过 `access.params` 传递，而是通过 `access.filter.children` 中类型为 `VARIABLE` 的 `$$begindatekey` 字段。修改日期时找到该字段修改 `values` 数组即可（格式 `yyyyMMdd`）。
>
> **如何定位日期字段**：在拦截到的请求体中查找 `access.filter.children[0].children[0]`，确认 `field.code === "$$begindatekey"` 且 `field.type === "VARIABLE"`。

```bash
# 重放查询获取 fresh queryId（使用同步 XHR，替换 {TARGET_ID}）
# 注：window.__clientHeader 由 Python 入口脚本注入，自动附加客户端环境 header
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var reqs=window.__allRequests.filter(function(r){return r.url&&r.url.includes('submit/v2')});var req=reqs.slice().reverse().find(function(r){var b=JSON.parse(r.body);return b.context&&b.context.resourceId==={TARGET_ID}});var body=JSON.parse(req.body);body.context.lastQueryId=0;body.context.isUsedCache=false;var bodyStr=JSON.stringify(body);window.__targetBody=bodyStr;var x=new XMLHttpRequest();x.open('POST','/api/mtbi/bi/submit/v2',false);x.setRequestHeader('Content-Type','application/json');if(window.__clientHeader){x.setRequestHeader(window.__clientHeader.key,window.__clientHeader.val);}x.send(bodyStr);var resp=JSON.parse(x.responseText);window.__queryResult=resp;return JSON.stringify({code:resp.code,queryId:resp.data&&resp.data.queryId})})()"
```

> 💡 改用同步 XHR 重放（而非 fetch），可直接拿到 queryId，无需额外等待再读取。

> 如用户要求自定义维度/指标/筛选，**基于拦截到的原始请求体修改后重发**（v1 用 `refType` 区分：1=指标, 2=维度）：
>
> **修改维度**：从 `access.select.fields` 中移除不需要的维度（`refType===2` 的字段），或保留需要的。
>
> **修改指标**：从 `access.select.fields` 中移除不需要的指标（`refType===1` 的字段）。
>
> **修改日期**：找到 `access.filter.children[*].children[*]` 中 `field.code==="$$begindatekey"` 的节点，修改 `values: ["yyyyMMdd"]`。
>
> **组件内嵌筛选器的修改方式**：在 `access.filter.children` 中新增一个 `LEAF` 节点，例如：
> ```javascript
> // 维值包含筛选（如限定核心终端）
> {relationType:'AND',children:[{relationType:'LEAF',filterTab:'NORMAL',field:{code:'dim__xxx',name:'核心终端',type:'TEXT',dataType:'string',source:'ORIGIN_MODEL'},filterType:'INCLUDE',values:['美团外卖','闪购']}]}
> ```
> 将该节点 push 到 `body.access.filter.children` 数组中。
>
> **修改后必须设置**：`body.context.lastQueryId=0`、`body.context.isUsedCache=false`，然后重发 submit/v2。

### 步骤6：构造 headers 并提交下载（含标准轮询逻辑）

> ⚠️ v1 仪表板用 `refType===1` 判断指标
> ⚠️ **submit/v2 查询是异步的**，queryId 返回后底层 Hive/Doris 查询可能仍在执行。download/submit 返回 `code=40000`（"查询未结束"）是正常现象，需要轮询重试。
> ⚠️ 查询耗时差异很大：热数据（昨天/近期）通常几秒完成，冷数据（历史日期）可能需要 1~3 分钟。
> ⚠️ **eval 中的 JS 必须为单行**：CatDesk shell 工具不支持多行命令，所有 JS 代码必须压缩为单行后传入 eval。

**推荐轮询策略：每 15 秒重试一次 download/submit，最多重试 12 次（3 分钟）。** 使用同步 XHR 确保能拿到返回值：

```bash
# 一体化脚本：提交下载（单行，使用同步 XHR）
# 注：window.__clientHeader 由 Python 入口脚本注入，自动附加客户端环境 header
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var qId=window.__queryResult.data.queryId;var fields=JSON.parse(window.__modBody||window.__targetBody).access.select.fields;var hdrs=fields.map(function(f){var h={name:f.name,aliasName:f.aliasName||f.name,code:f.code,dataType:f.dataType,type:f.type};if(f.refType===1){h.format={scale:f.decimals||0,numericUnit:f.unit||'',textUnit:'',thousandSep:f.thousandSeparator!==false}}return h});var payload=JSON.stringify({queryId:qId,fileName:'download_data',fileType:'XLSX',headers:hdrs,data:[]});var x=new XMLHttpRequest();x.open('POST','/api/mtbi/download/submit',false);x.setRequestHeader('Content-Type','application/json');if(window.__clientHeader){x.setRequestHeader(window.__clientHeader.key,window.__clientHeader.val);}x.send(payload);var resp=JSON.parse(x.responseText);window.__dlResult=resp;return JSON.stringify({code:resp.code,taskId:resp.data&&resp.data.taskId,msg:resp.message})})()"
```

**如果返回 code=40000**（查询未完成），在 shell 层面做轮询（不要在 JS 中 sleep）：

```bash
# Shell 轮询：每 15 秒重试，最多 12 次（每次执行上面的单行 eval 脚本）
for i in $(seq 1 12); do sleep 15; RESULT=$($PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var qId=window.__queryResult.data.queryId;var fields=JSON.parse(window.__modBody||window.__targetBody).access.select.fields;var hdrs=fields.map(function(f){var h={name:f.name,aliasName:f.aliasName||f.name,code:f.code,dataType:f.dataType,type:f.type};if(f.refType===1){h.format={scale:f.decimals||0,numericUnit:f.unit||'',textUnit:'',thousandSep:f.thousandSeparator!==false}}return h});var payload=JSON.stringify({queryId:qId,fileName:'download_data',fileType:'XLSX',headers:hdrs,data:[]});var x=new XMLHttpRequest();x.open('POST','/api/mtbi/download/submit',false);x.setRequestHeader('Content-Type','application/json');if(window.__clientHeader){x.setRequestHeader(window.__clientHeader.key,window.__clientHeader.val);}x.send(payload);var resp=JSON.parse(x.responseText);window.__dlResult=resp;return JSON.stringify({code:resp.code,taskId:resp.data&&resp.data.taskId,msg:resp.message})})()"
 2>&1); echo "Attempt $i: $RESULT"; echo "$RESULT" | grep -q '"taskId":[0-9]' && break; done
```

**如果返回 code=0 且有 taskId**，进入步骤7轮询下载状态。

### 步骤7：轮询下载状态 → 获取文件链接

```bash
# 必须用同步 XHR
# 注：window.__clientHeader 由 Python 入口脚本注入，自动附加客户端环境 header
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var tId=window.__dlResult.data.taskId;var x=new XMLHttpRequest();x.open('GET','/api/mtbi/download/'+tId+'/status',false);if(window.__clientHeader){x.setRequestHeader(window.__clientHeader.key,window.__clientHeader.val);}x.send();return x.responseText})()"
```

当 `status === "SUCCEED"` 时，`data.fileUrl` 即为下载链接。

### 步骤8：输出文件链接给用户

获取到文件链接后，根据链接类型：

- `wenshu-s3.sankuai.com` 链接：用 `wenshu-tools` Skill 下载（所有环境统一）
- 无链接但有数据：数据已保存到本地文件，告知路径

**直接告知用户**：

```
数据已就绪，请使用以下链接下载（通过 wenshu-tools Skill）：
[图表名称](fileUrl)
⚠️ 链接有过期时间，请尽快点击下载。
```

**一般到此即可结束。**

---

## 手动交互模式 - Dashboard 组件（兜底方案）

> ⚠️ **这是兜底方案，仅在 smart-query（定向查询）明确失败后才使用。** 常见降级场景同 Analysis 组件。
>
> 适用于 `chartType=dashboard` 的组件，走 `submit-query-sync` 同步接口，直接返回全量数据（无 queryId）。
>
> **与 Analysis 组件的核心区别**：
> | | Analysis 组件 | Dashboard 组件 |
> |---|---|---|
> | 查询接口 | `submit/v2`（异步，返回 queryId） | `submit-query-sync`（同步，直接返回数据） |
> | 字段定义 | `access.select.fields` + refType | `dimIndicators` + type（2=维度, 3=指标） |
> | 筛选结构 | `access.filter.children` | `filters` + `globalFilterLists` |
> | 下载方式 | `download/submit` → 轮询 → fileUrl | 直接导出数据 → 本地生成 XLSX |
> | 列名映射 | 直接使用 fields 中的 name | 需从 `fillSetting.dimension` 中的 alias 映射 |

### 步骤1：导航到仪表板

> 不带 hash 导航，避免页面自动请求在拦截器之前发出。

```bash
$PINCHTAB instance navigate $HEADLESS_INST "https://bi.keetapp.com/dashboard/{dashboardId}" 2>&1
# 记录 tabId 为 $TAB_ID
```

等待页面加载完成（约 5 秒）。

权限预检（同「权限预检」章节，确认 `canDownload: true` 后继续）：

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var d=window.__DASHBOARD_DEBUG__;if(!d||!d.engineInstance)return JSON.stringify({ready:false});var p=d.engineInstance.permissionInfo||{};return JSON.stringify({ready:true,canDownload:p.canDownload,canEdit:p.canEdit})})()"
```

### 步骤2：获取 Tab 列表

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "fetch('/api/moshu/api/v2/dashboards/{dashboardId}?isOnline=1&version=112').then(r=>r.json()).then(d=>window.__dashInfo=d);'fetching...'"
```

```bash
# 等待 1~2 秒后执行
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "JSON.stringify(window.__dashInfo.data.tabList.map(t=>({tabId:t.tabId,tid:t.tid,name:t.tabName})),null,2)"
```

### 步骤3：获取目标 Tab 的组件列表

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "fetch('/api/moshu/api/v2/dashboards/{dashboardId}/tabs/{tabId}?isOnline=1&tid={tid}&version=112').then(r=>r.json()).then(d=>window.__tabDetail=d);'fetching...'"
```

```bash
# 等待 1~2 秒后执行
# 注意：chartType=dashboard 的组件可能没有 analysisChartId 和 name，用 lid 标识
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "JSON.stringify(window.__tabDetail.data.componentList.filter(c=>c.chartType==='analysis'||c.chartType==='dashboard').map(c=>({chartType:c.chartType,cid:c.cid,id:c.analysisChartId||null,lid:c.lid||null,name:(c.componentSettings&&c.componentSettings.name)||null,dsId:c.componentSettings&&c.componentSettings.datasourceId||null})),null,2)"
```

> 💡 `chartType=dashboard` 的组件通过 `lid` 标识（而非 `analysisChartId`），务必记录 `lid`。
> 💡 如果目标组件的 `chartType` 为 `analysis`，改用「手动交互模式 - Analysis 组件」。

### 步骤4：JS click 切换到目标 Tab

> ⚠️ **严禁使用 hash 导航**（`#tab-{tid}`）切换 Tab。hash 导航会触发页面重载，导致页面自动发出的查询请求在拦截器安装之前就完成了。
>
> 必须使用 JS click 方式切换 Tab，这样只会触发局部渲染，拦截器在切换前安装即可。

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var tabs=document.querySelectorAll('.tab-nav-item,.ant-tabs-tab,.bi-tabs-tab,[role=tab],.tab-item-title');var target='{目标TAB名称}';for(var i=0;i<tabs.length;i++){if(tabs[i].textContent.trim()===target){tabs[i].click();return 'clicked tab: '+target}}return 'tab not found: '+target})()"
```

等待 3~5 秒让目标 Tab 渲染完成。

验证 Tab 切换成功（替换 {CID} 为目标组件的 cid）：

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var el=document.getElementById('{CID}');return el?'found: '+'{CID}':'not found'})()"
```

- 返回 `found` → 继续步骤5
- 返回 `not found` → 等 2 秒重试，最多 15 秒

### 步骤5：安装拦截器 + 点击查询按钮

**5.1 安装 submit-query-sync 拦截器**

> 拦截 fetch 和 XHR 中包含 `submit-query-sync` 的请求，记录完整请求体（含 cid、datasourceId）。

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){window.__syncReqs=[];var _f=window.fetch;window.fetch=function(url,opts){var u=typeof url==='string'?url:(url&&url.url)||'';if(u.indexOf('submit-query-sync')!==-1||u.indexOf('submit/v2')!==-1){var body=opts&&opts.body;var rec={url:u,body:body,ts:Date.now()};try{var p=JSON.parse(body);rec.cid=p.cid;rec.dsId=p.datasourceId;rec.dashboardId=p.dashboardId}catch(e){}window.__syncReqs.push(rec)}return _f.apply(this,arguments)};var _xs=XMLHttpRequest.prototype.send;XMLHttpRequest.prototype.send=function(b){if(this.__syncOa&&(this.__syncOa.url.indexOf('submit-query-sync')!==-1||this.__syncOa.url.indexOf('submit/v2')!==-1)){var rec={url:this.__syncOa.url,body:b,ts:Date.now()};try{var p=JSON.parse(b);rec.cid=p.cid;rec.dsId=p.datasourceId;rec.dashboardId=p.dashboardId}catch(e){}window.__syncReqs.push(rec)}return _xs.apply(this,arguments)};var _xo=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(m,u){this.__syncOa={method:m,url:u};return _xo.apply(this,arguments)};return 'sync interceptor ok'})()"
```

**5.2 滚动到目标组件 + snap 找查询按钮**

```bash
# 滚动到组件
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "document.getElementById('{CID}').scrollIntoView({block:'center'});'scrolled'"
```

```bash
# snap 获取页面元素
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID snap -i -c --max-tokens 300
```

在 snap 结果中找到 `button "查询"` 对应的 ref（可能有多个：总览级、Tab 级、组件级）。

**5.3 点击查询按钮触发请求**

> 优先点击距离目标组件最近的查询按钮（通常是 Tab 级或组件级），避免触发无关组件的请求。

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID click {查询按钮ref}
```

**5.4 等待 5 秒后检查拦截结果**

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "JSON.stringify(window.__syncReqs.map(function(r,i){return {idx:i,url:r.url.split('/').pop(),cid:r.cid,dsId:r.dsId}}))"
```

> 💡 一次点击可能触发多个 submit-query-sync 请求（同 Tab 下多个组件联动），通过 cid 或 dsId 匹配目标。

如果没有拦截到任何请求：
1. 检查拦截器是否安装成功
2. 重新安装拦截器（5.1），再次点击查询按钮（5.3）

### 步骤6：从拦截请求中匹配目标组件

根据目标组件的 `cid` 从拦截列表中精确匹配：

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var target=window.__syncReqs.filter(function(r){return r.cid==='{TARGET_CID}'});if(target.length===0)return 'no match for cid={TARGET_CID}';window.__targetSyncReq=target[target.length-1];return JSON.stringify({cid:window.__targetSyncReq.cid,dsId:window.__targetSyncReq.dsId,bodyLen:window.__targetSyncReq.body.length})})()"
```

如果 cid 匹配不到，尝试用 datasourceId 匹配：

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var target=window.__syncReqs.filter(function(r){return r.dsId==={TARGET_DSID}});if(target.length===0)return 'no match for dsId={TARGET_DSID}';window.__targetSyncReq=target[target.length-1];return JSON.stringify({cid:window.__targetSyncReq.cid,dsId:window.__targetSyncReq.dsId,bodyLen:window.__targetSyncReq.body.length})})()"
```

### 步骤7：展示维度/指标/筛选条件给用户确认

**7.1 解析维度和指标**

submit-query-sync 的请求体使用 `dimIndicators` 定义维度和指标：`type=2` 为维度，`type=3` 为指标。

```bash
# 维度列表
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var body=JSON.parse(window.__targetSyncReq.body);var dims=body.dimIndicators.filter(function(d){return d.type===2});return JSON.stringify(dims.map(function(d){return {id:d.id,name:d.name,type:'维度'}}),null,2)})()"
```

```bash
# 指标列表
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var body=JSON.parse(window.__targetSyncReq.body);var metrics=body.dimIndicators.filter(function(d){return d.type===3});return JSON.stringify(metrics.map(function(d){return {id:d.id,name:d.name,type:'指标'}}),null,2)})()"
```

**7.2 解析筛选条件**

```bash
# filters 数组（组件级筛选）
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var body=JSON.parse(window.__targetSyncReq.body);return JSON.stringify(body.filters||[],null,2)})()"
```

```bash
# globalFilterLists（全局筛选）
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var body=JSON.parse(window.__targetSyncReq.body);return JSON.stringify(body.globalFilterLists||[],null,2)})()"
```

**7.3 解析列名映射（fillSetting.dimension）**

> 💡 submit-query-sync 返回的 `data.titles` 中，部分列名可能是内部代码。需从 `fillSetting.dimension` 中的 `alias` 字段获取用户可读的列名。

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var body=JSON.parse(window.__targetSyncReq.body);var dims=body.fillSetting&&body.fillSetting.dimension||[];return JSON.stringify(dims.map(function(d){return {id:d.id,name:d.name,alias:d.alias||d.name,type:d.type}}),null,2)})()"
```

**👉 将以下信息展示给用户，并询问是否修改：**

1. **维度列表**（dimIndicators 中 type=2）
2. **指标列表**（dimIndicators 中 type=3）
3. **筛选条件**（filters + globalFilterLists，如日期范围）
4. **列名映射**（fillSetting.dimension 中的 alias）

### 步骤8：修改请求体（如需）+ 重发 submit-query-sync 获取全量数据

**8.1 直接重发（不修改）**

如用户确认无需修改，直接用拦截到的原始请求体重发：

```bash
# 注：window.__clientHeader 由 Python 入口脚本注入，自动附加客户端环境 header
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var body=window.__targetSyncReq.body;var x=new XMLHttpRequest();x.open('POST','/api/moshu/api/v2/dashboards/submit-query-sync',false);x.setRequestHeader('Content-Type','application/json');if(window.__clientHeader){x.setRequestHeader(window.__clientHeader.key,window.__clientHeader.val);}x.send(body);var resp=JSON.parse(x.responseText);window.__syncResult=resp;return JSON.stringify({code:resp.code,size:resp.data&&resp.data.size,titleCount:resp.data&&resp.data.titles&&resp.data.titles.length})})()"
```

**8.2 修改筛选条件后重发**

如用户需要修改筛选条件（如日期）：

> **修改日期**：在 `globalFilterLists` 或 `filters` 中找到 `dateType` 为 true 或 `type=DATE` 的条目，修改 `values` 数组。
> **修改维度筛选**：在 `filters` 中找到对应字段，修改 `values` 数组。

```bash
# 注：window.__clientHeader 由 Python 入口脚本注入，自动附加客户端环境 header
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var body=JSON.parse(window.__targetSyncReq.body);/* 示例：修改日期筛选 body.globalFilterLists[0].values=['2026-04-01','2026-04-17'] */var bodyStr=JSON.stringify(body);var x=new XMLHttpRequest();x.open('POST','/api/moshu/api/v2/dashboards/submit-query-sync',false);x.setRequestHeader('Content-Type','application/json');if(window.__clientHeader){x.setRequestHeader(window.__clientHeader.key,window.__clientHeader.val);}x.send(bodyStr);var resp=JSON.parse(x.responseText);window.__syncResult=resp;return JSON.stringify({code:resp.code,size:resp.data&&resp.data.size,titleCount:resp.data&&resp.data.titles&&resp.data.titles.length})})()"
```

**8.3 验证返回结果**

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "JSON.stringify({code:window.__syncResult.code,titles:window.__syncResult.data.titles,size:window.__syncResult.data.size,sampleRow:window.__syncResult.data.data[0]})"
```

- `code=0` 且 `size>0` → 继续步骤9
- `code!=0` → 查看常见问题章节

### 步骤9：本地生成 XLSX + 输出给用户

> submit-query-sync 同步返回全量数据（无 queryId），无法走 download/submit 链路。
> 需要将浏览器中的数据分批导出到本地，生成 XLSX 文件。

**9.1 在浏览器中分批存储数据**

> 大数据量（万行级）不能一次通过 eval 传输，需分批。

```bash
# 获取总行数
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "window.__syncResult.data.size"
```

```bash
# 存储 titles（列头）
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "window.__titles=window.__syncResult.data.titles;JSON.stringify(window.__titles)"
```

```bash
# 分批存储数据（每 5000 行一批），替换 {START} 和 {END}
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "window.__batch_{N}=window.__syncResult.data.data.slice({START},{END});window.__batch_{N}.length"
```

**9.2 导出 titles 到本地 JSON**

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "JSON.stringify(window.__titles)" > /tmp/sync_titles.json
```

**9.3 逐批导出数据到本地 JSON**

```bash
# 导出每批数据（替换 {N}）
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "JSON.stringify(window.__batch_{N})" > /tmp/sync_batch_{N}.json
```

**9.4 列名 alias 映射**

> 从请求体的 `fillSetting.dimension` 中提取 alias 映射，用于替换 titles 中的内部代码。

```bash
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "(function(){var body=JSON.parse(window.__targetSyncReq.body);var dims=body.fillSetting&&body.fillSetting.dimension||[];var mapping={};dims.forEach(function(d){if(d.alias)mapping[d.name]=d.alias;if(d.id)mapping[d.id]=d.alias||d.name});window.__aliasMapping=mapping;return JSON.stringify(mapping)})()"
```

```bash
# 导出映射到本地
$PINCHTAB --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "JSON.stringify(window.__aliasMapping)" > /tmp/sync_alias_mapping.json
```

**9.5 用 Python 生成 XLSX**

```bash
cat > /tmp/sync_to_xlsx.py << 'PYEOF'
import json, os, glob

TITLES_FILE = "/tmp/sync_titles.json"
BATCH_PATTERN = "/tmp/sync_batch_*.json"
ALIAS_FILE = "/tmp/sync_alias_mapping.json"
OUTPUT_XLSX = "/tmp/sync_download_data.xlsx"

with open(TITLES_FILE, "r") as f:
    titles = json.load(f)

alias_mapping = {}
if os.path.exists(ALIAS_FILE):
    with open(ALIAS_FILE, "r") as f:
        alias_mapping = json.load(f)

mapped_titles = [alias_mapping.get(t, t) for t in titles]

batch_files = sorted(glob.glob(BATCH_PATTERN))
all_data = []
for bf in batch_files:
    with open(bf, "r") as f:
        all_data.extend(json.load(f))

print(f"Titles: {len(mapped_titles)} columns, Data: {len(all_data)} rows")

try:
    from openpyxl import Workbook
except ImportError:
    os.system("pip install openpyxl -q")
    from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws.title = "Data"
for col_idx, title in enumerate(mapped_titles, 1):
    ws.cell(row=1, column=col_idx, value=title)
for row_idx, row in enumerate(all_data, 2):
    for col_idx, val in enumerate(row, 1):
        ws.cell(row=row_idx, column=col_idx, value=val)

wb.save(OUTPUT_XLSX)
print(f"XLSX saved: {OUTPUT_XLSX}")
PYEOF

python3 /tmp/sync_to_xlsx.py
```

**9.6 输出结果给用户**

```
数据已就绪（{size} 行 × {columns} 列），文件已保存到本地：
/tmp/sync_download_data.xlsx
```

---

## 流程结束清理（所有模式必做）

> ⚠️ **无论使用哪种模式（批量 / 定向查询 / 手动交互），在流程完全结束后（结果已输出给用户），都必须执行此清理步骤。**
>
> 目的：将当前 server 中所有实例的所有 tab 导航到 `about:blank`，释放页面占用的内存和网络连接，避免后台持续加载仪表板消耗资源。

> ⚠️ **`pinchtab nav "about:blank"` 会报 `invalid url`**，必须用 `eval` 方式执行 `window.location.href='about:blank'`。导航到 about:blank 后 tab 会自动从列表中移除。

### 清理步骤

#### 步骤 1：写入清理脚本

> ⚠️ **不要使用 heredoc（`python3 << 'EOF'`）**，CatDesk 终端不允许命令中包含换行符，heredoc 会执行失败。
> 必须先用 write_file 工具将脚本写到临时文件，再单独执行。

将以下内容通过 **write_file 工具** 写入 `/tmp/_cleanup_tabs.py`：

```python
import subprocess, json

raw = subprocess.check_output(["pinchtab", "instances"], stderr=subprocess.DEVNULL).decode()
instances = json.loads(raw)
cleaned = 0
for inst in instances:
    port = inst.get("port", "")
    if not port:
        continue
    server = f"http://127.0.0.1:{port}"
    try:
        tab_raw = subprocess.check_output(
            ["pinchtab", "--server", server, "tab"],
            stderr=subprocess.DEVNULL
        ).decode()
        tabs = json.loads(tab_raw).get("tabs", [])
    except Exception:
        continue
    for t in tabs:
        tid = t.get("id", "")
        if not tid:
            continue
        try:
            subprocess.run(
                ["pinchtab", "--server", server, "--tab", tid,
                 "eval", "window.location.href='about:blank';'ok'"],
                capture_output=True, timeout=5
            )
            cleaned += 1
        except Exception:
            pass

print(f"[CLEANUP] {cleaned} tab(s) navigated to about:blank")
```

#### 步骤 2：执行清理脚本

```bash
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH" && python3 /tmp/_cleanup_tabs.py
```

预期输出示例：`[CLEANUP] 4 tab(s) navigated to about:blank`

#### 步骤 3：验证清理结果

清理后必须检查 tab 列表是否已清空：

```bash
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH" && pinchtab --server http://127.0.0.1:$HEADLESS_PORT tab
```

预期输出：`{"tabs": []}` — 表示所有 tab 已被清理。

- 如果仍有残留 tab，重新执行步骤 2
- eval 导航到 `about:blank` 后 tab 会自动从列表中移除，所以正常情况下列表应为空

#### 步骤 4：删除临时脚本

```bash
rm -f /tmp/_cleanup_tabs.py
```

### 排查指引

如果清理脚本输出 `[CLEANUP] 0 tab(s) navigated to about:blank` 但 tab 实际仍存在，按以下顺序排查：

1. **确认 pinchtab 在 PATH 中**：执行 `which pinchtab`，如果找不到，确保 `$HOME/.local/bin` 在 PATH 中
2. **确认实例在运行**：执行 `pinchtab instances`，检查是否有 `status: "running"` 的实例及其 port
3. **确认 tab 存在**：执行 `pinchtab --server http://127.0.0.1:{port} tab`，检查 tabs 数组是否非空
4. **手动测试单个 tab**：执行 `pinchtab --server http://127.0.0.1:{port} --tab {tab_id} eval "window.location.href='about:blank';'ok'"`，检查返回是否为 `{"result": "ok"}`

> 💡 如果流程中已记录了 `$HEADLESS_PORT` 和 `$TAB_ID`，也可以用更简洁的单 tab 清理：
>
> ```bash
> pinchtab --server http://127.0.0.1:$HEADLESS_PORT --tab $TAB_ID eval "window.location.href='about:blank';'ok'" 2>/dev/null && echo "[CLEANUP] Tab cleaned"
> ```
>
> 简洁方式只清理当前使用的 tab；完整 Python 方式清理所有实例的所有 tab（推荐）。

---

## 常见问题（Dashboard 组件手动模式）

### Q1：拦截器没有捕获到任何请求

**原因**：拦截器安装在页面请求之后，或 Tab 切换使用了 hash 导航导致页面重载。

**解决**：
1. 确认使用 JS click 切换 Tab（步骤4），不要用 hash 导航
2. 切换 Tab 后，先安装拦截器（步骤5.1），再点击查询按钮（步骤5.3）
3. 如仍不行，尝试重新安装拦截器后再点击

### Q2：拦截到的请求 cid 不是目标组件

**原因**：点击的查询按钮触发了其他组件的请求。

**解决**：
1. 确认已切换到正确的 Tab（步骤4）
2. 使用 snap 找到距离目标组件最近的查询按钮
3. 一次点击可能触发多个请求，从列表中按 cid 筛选目标

### Q3：重发请求报错"SQL 已被删除"

**原因**：手工构造的请求体缺少必要字段，或使用了错误的 datasourceId。

**解决**：不要手工构造请求体，只使用拦截到的真实请求体重发或修改后重发。

### Q4：eval 返回数据被截断

**原因**：数据量过大，单次 eval 输出超出限制。

**解决**：使用分批导出方案（步骤9.1-9.3），每次只传输 5000 行。

### Q5：XLSX 生成失败（openpyxl 未安装）

**解决**：脚本中已内置自动安装逻辑，如仍失败手动执行：

```bash
pip install openpyxl -q
```

### Q6：submit-query-sync 返回 code!=0

| 错误码 | 含义 | 处理方式 |
|--------|------|---------|
| `0` | 成功 | 继续后续步骤 |
| `99999` | 系统异常 | 请求体可能不完整或格式错误，确保使用拦截到的真实请求体 |
| `40001` | 无权限 | 用户对该数据源无访问权限，联系管理员 |
| `-1` | SQL 已被删除 | datasourceId 对应的 SQL 版本已失效，重新拦截最新请求体 |
