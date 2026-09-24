---
name: dashboard-v2
description: "从美团魔数境外仪表板（bi.keetapp.com/v2/dashboard/xxx、mdbi.bi.st.keetapp.com/v2/dashboard/xxx）定向查询图表数据或按需导出文枢下载链接。触发条件：(1) 用户提供 MDBI 仪表板链接或 dashboard ID (2) 用户要求获取、查询、总结、导出、留存 MDBI/dashboard 数据 (3) 用户提到 Tab、图表、筛选器、mdbi、bi 仪表板、取数、导 CSV/明细。交付：总结/查看数据时直接读取 executeQueryAndGetCHNResult 返回值；只有用户明确要求导出、下载、文件链接时才调用 executeDownload。"
---

# MDBI Dashboard 取数

从 MDBI 仪表板定向读取图表数据，或在用户明确要求导出时返回文枢下载链接。

典型定向请求可理解为：

> 选择 Tab「目标 Tab」后，查询图表「目标图表」的数据；将图表筛选器「目标筛选器」设置为包含指定值或全选，并基于查询结果总结数据情况。

---

## 技术架构

取数能力基于魔数 BI 前端 JS 接口（`window.DashboardController`），通过浏览器 evaluate 在页面直接调用：

```
browser evaluate → window.DashboardController
  ├── getComponents()                       — 获取全量组件元数据（chart / filter / tab）
  ├── [可选] getFiltersInfo()                — 获取筛选器当前值和可选项
  ├── [可选] setFiltersValues()              — 批量设置筛选条件
  ├── [可选] getFieldPools(componentId)      — 获取图表指标/维度配置
  ├── [可选] updateFieldPools(componentId)   — 修改图表指标/维度配置
  ├── [可选] getChartFilters(chartIds)       — 获取图表内部分析面板筛选器
  ├── [可选] setChartFilters(configs)        — 设置图表内部分析面板筛选器
  ├── [可选] getCurrentUserOrgTree({filterId}) — 获取组织架构筛选器可选树
  ├── executeQueryAndGetCHNResult()          — 触发查询并直接返回结果数据
  └── [按需] executeDownload()                — 用户明确要求导出/下载时获取文枢 S3 下载链接
```

> 🔧 **环境说明**：本文档示例以 **CatPaw Desk (macOS/Linux)** 为准。境外版无需 safeRoomToken，直接 navigate 原始 URL。各环境调用差异详见 [`moshu_dashboard_api_skill_demo.md`](./moshu_dashboard_api_skill_demo.md) 开头的环境适配说明表。

**完整操作流程参考 [`moshu_dashboard_api_skill_demo.md`](./moshu_dashboard_api_skill_demo.md)**

---

## 安全规则（必须严格遵守）

> **直接查询优先**：用户要求“查看数据”“查询图表”“总结数据情况”时，直接读取 `executeQueryAndGetCHNResult` 返回的 `data.columns` 和 `data.data` 并总结，不要调用 `executeDownload`。
>
> **按需下载**：只有用户明确要求“导出”“下载”“CSV/Excel”“文件链接”“文枢链接”时，才调用 `executeDownload`。

---

## 执行步骤

### 第一步：告知用户预期耗时（必做）

在开始任何操作之前，先向用户说明执行计划和预期时间：

> "好的，我现在开始从 Dashboard XXXXXX 获取数据。通常 **30 秒以内**完成；数据量大时可能需要重试等待，最长约 **10 分钟**，请稍候。"

### 第二步：打开 AI 控制器专用页面

> ⚠️ **必须打开 AI 控制器专用页面**，而不是普通仪表板查看页面。`window.DashboardController` 只在专用页面挂载：
> - 普通查看页（✖ 不挂载）：`https://{host}/v2/dashboard/{id}`
> - AI 控制器专用页（✔ 挂载）：`https://{host}/v2/dashboard/dashboard-controller?dashboardId={id}`

**CatPaw Desk (macOS/Linux)：**
```bash
# 步骤一：注入 headers（必须先执行）
headers_json=$([skill-dir]/scripts/moshu/build_headers.sh)
catdesk browser-action "{\"action\":\"headers\",\"headers\":$headers_json}"

# 步骤二：直接导航（境外版无需 token）
catdesk browser-action "{\"action\":\"navigate\",\"url\":\"https://{host}/v2/dashboard/dashboard-controller?dashboardId={id}\"}"

# 等待就绪
catdesk browser-action '{"action":"waitforfunction","expression":"window.DashboardController !== undefined","timeout":30000}'
```

**CatPaw Desk (Windows)：**
```powershell
# 步骤一：注入 headers（必须先执行）
$headers_json = & "[skill-dir]\scripts\moshu\build_headers.ps1"
catdesk.cmd browser-action "{\"action\":\"headers\",\"headers\":$headers_json}"

# 步骤二：直接导航（境外版无需 token）
catdesk.cmd browser-action "{\"action\":\"navigate\",\"url\":\"https://{host}/v2/dashboard/dashboard-controller?dashboardId={id}\"}"

# 等待就绪
catdesk.cmd browser-action '{"action":"waitforfunction","expression":"window.DashboardController !== undefined","timeout":30000}'
```

**CatClaw 环境：**
```bash
# 步骤一：注入 headers（必须先执行）
# 先执行 build_headers.sh 获取 headers JSON，再注入 fetch 拦截代码
headers_json=$([skill-dir]/scripts/moshu/build_headers.sh)
browser(evaluate, fn=`
(function() {
  const headers = ${headers_json};
  const originalFetch = window.fetch;
  window.fetch = function(url, options = {}) {
    options.headers = { ...options.headers, ...headers };
    return originalFetch(url, options);
  };
})();
`)

# 步骤二：直接导航（境外版无需 token）
browser(navigate, url="https://{host}/v2/dashboard/dashboard-controller?dashboardId={id}")
# 若超时，改用 browser(open, url=<同上>) 重试

# 轮询等待，每 2 秒一次，最多 15 次
browser(evaluate, fn="window.DashboardController !== undefined")
```

**OpenClaw 环境：**
```bash
# 步骤一：OpenClaw 无需注入 headers

# 步骤二：直接导航（境外版无需 token）
browser(navigate, url="https://{host}/v2/dashboard/dashboard-controller?dashboardId={id}")
# 若超时，改用 browser(open, url=<同上>) 重试

# 轮询等待，每 2 秒一次，最多 15 次
browser(evaluate, fn="window.DashboardController !== undefined")
```

> 🚫 **严禁截图**：该页面对用户呈现为空白页，截图只会给用户造成困惑。

### 第三步：调用 JS 接口定向取数

**完整操作流程详见 [`moshu_dashboard_api_skill_demo.md`](./moshu_dashboard_api_skill_demo.md)。**

该文件覆盖以下全部操作，以其为准：

- `getComponents()` — 获取全量组件，找到目标图表 ID
- `getFiltersInfo()` / `setFiltersValues()` — 查看或修改仪表板筛选条件（可选）
- `getFieldPools(componentId)` / `updateFieldPools(componentId, ...)` — 查看或修改图表指标/维度配置（可选）
- `getChartFilters(chartIds)` / `setChartFilters(configs)` — 查看或设置图表内部分析面板筛选器（可选）
- `getCurrentUserOrgTree({filterId})` — 获取组织架构筛选器可选树（Org 类型时可选；设置时仍用 `setFiltersValues` 传 `orgFilterInfo` 格式）
- `executeQueryAndGetCHNResult()` — 触发查询并返回结果数据；总结数据时直接读取返回值
- `executeDownload()` — 仅在用户明确要求导出/下载时获取文枢下载链接（含指数退避重试：15s→30s→60s→120s，总上限约 10 分钟）

定向查询处理顺序：

1. 从用户请求中抽取 Tab 名、图表名、筛选器名称、筛选器操作和值，以及是否需要总结或导出。
2. 用 `getComponents()` 获取组件树，先定位 Tab，再在该 Tab 的 `childrenComponents` 内定位目标图表；如果用户没有指定 Tab，则按图表名全局匹配，并在结果中说明实际命中的 Tab。
3. 用 `getFiltersInfo()` 获取仪表板级筛选器；用 `getChartFilters([chartId])` 获取图表内嵌筛选器。根据筛选器归属分别调用 `setFiltersValues()` 或 `setChartFilters()`。
4. 当用户说“筛选器全选”时，必须先读取筛选器 `options`，把每一个可选值都写入提交参数，设置后再次读取并核对已选数量与可选项数量一致。
5. 调用 `executeQueryAndGetCHNResult([chartId])` 执行查询。需要总结时，直接读取 `executeQueryAndGetCHNResult` 返回的 `data.columns` 和 `data.data`，不要调用 `executeDownload`。
6. 仅当用户明确要求导出/下载/文件链接，或直接查询结果超过接口行数限制且用户需要完整明细时，才进入下载链路。

### 第四步：按需触发文枢下载

仅当用户明确要求导出、下载、CSV/Excel、文件链接或文枢链接时，才对第三步获取到的 `wenshuUrl` 使用 `wenshu-tools` Skill 完成下载：

- 已安装 `wenshu-tools`：直接调用该 Skill，传入 `wenshuUrl` 完成下载
- 未安装：执行 `mtskills i wenshu-tools` 安装后再调用

> ⚠️ 如有多张表且用户明确要求导出，建议**并发触发查询 + 并发获取下载链接**（详见 [`moshu_dashboard_api_skill_demo.md`](./moshu_dashboard_api_skill_demo.md) 第五步「多图表并发触发」和第六步「多图表并发获取下载链接」），显著缩短总耗时；获取到的每个 `wenshuUrl` 仍需逐一传入 `wenshu-tools` Skill 触发下载。

### 第五步：输出结构化结果摘要

如果用户要求总结数据情况，输出应包含：

- 实际查询的 Dashboard、Tab、图表名称。
- 已生效的筛选器设置；全选筛选器需说明已按全部可选项提交并核对数量。
- 基于 `data.columns` 和 `data.data` 的主要数值、排序、异常点和结构性结论。
- 数据量或接口限制说明，例如返回行数、是否截断。

如果用户要求导出，再返回文枢链接：

> ⚠️ **【重要】展示文枢链接时，必须使用 `[图表名称](URL)` 超链接格式。**
> - 严禁用反引号包裹裸 URL（长 URL 会被截断，无法点击）
> - 超链接的显示文字用图表名称，href 为完整原始 URL（href 不会被 Markdown 渲染解码，签名校验正常）
> - 严禁用 `[下载链接](URL)` 这类通用文字作为显示文字

输出格式示例：

```
✅ 取数完成！Dashboard XXXXXX 共导出 N 张表：

1. [图表名A](http://wenshu-s3.sankuai.com/.../%E5%9B%BE%E8%A1%A8A.csv?AWSAccessKeyId=...)
2. [图表名B](http://wenshu-s3.sankuai.com/.../%E5%9B%BE%E8%A1%A8B.csv?AWSAccessKeyId=...)
```

### 第六步：执行 Step END 结束上报（⚠️ 必做，不可跳过）

> ⚠️ **【Step END 收尾，不可跳过】在进入后续分析之前，必须立即执行主 SKILL.md 中的 Step END 结束上报。无论流程成功或失败，此步骤不可遗漏。**

### 第七步：引导后续分析（⚠️ 必做，不可跳过）

> 执行主 SKILL.md 中的「引导后续分析」章节。

---

## 常见坑

| 现象 | 原因 | 解决方式 |
|------|------|---------|
| `window.DashboardController` 未挂载 | 未访问 AI 控制器专用页 | 确认访问的是 `/v2/dashboard/dashboard-controller?dashboardId={id}` 专用页 |
| `executeQueryAndGetCHNResult` 返回 `{code:0}` 但无 data | `DashboardController` 未完全就绪 | 确认 `waitforfunction` 已成功等到 `DashboardController !== undefined` 后再调用 |
| OpenClaw 环境出现 SSO 需要登录 | 用户需要认证身份 | 截图二维码发送给用户，登录后 cookie 会被保存供下次使用 |

---

## 参考文档

| 文档 | 说明 |
|------|------|
| [`moshu_dashboard_api_skill_demo.md`](./moshu_dashboard_api_skill_demo.md) | browser-action 直调 JS 接口完整操作流程 |
| [`dashboard-controller-api.md`](./dashboard-controller-api.md) | DashboardController JS 接口完整技术参考（接口签名、返回值、FilterUserInput 格式） |
| [`env-check.md`](./env-check.md) | 运行环境检查与安装指引 |
