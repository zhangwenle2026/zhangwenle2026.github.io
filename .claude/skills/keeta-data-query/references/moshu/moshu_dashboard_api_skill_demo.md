---
name: mdbi-dashboard
description: "美团 MDBI 报表取数工具。当用户提到从 MDBI 报表/仪表板取数、查询图表数据、设置筛选器、获取报表组件列表、读取 BI 数据等时激活。支持：列出报表所有组件、读取/修改筛选器值、直接查询指定图表的数据，并在用户明确要求导出时获取文枢下载链接。"
---

# MDBI 报表取数 — Agent Skill

通过 `window.DashboardController` API 与美团 MDBI 报表页面交互，实现无侵入式取数。

---

## 环境适配说明

本文档示例命令以 **CatPaw Desk (macOS/Linux)** 环境为准。境外版无需 safeRoomToken，直接 navigate 原始 URL。各环境调用方式如下表：

| 操作 | CatPaw Desk (macOS/Linux) | CatPaw Desk (Windows) | CatClaw | OpenClaw |
|------|--------------------------|----------------------|---------|----------|
| **注入 headers**（navigate 前必须执行） | `headers_json=$([skill-dir]/scripts/moshu/build_headers.sh)`<br>`catdesk browser-action "{\"action\":\"headers\",\"headers\":$headers_json}"` | `$headers_json = & "[skill-dir]\scripts\moshu\build_headers.ps1"`<br>`catdesk.cmd browser-action "{\"action\":\"headers\",\"headers\":$headers_json}"` | 通过 `browser(evaluate)` 注入 fetch 拦截代码（见主 SKILL.md 说明） | 不需要 |
| **导航到页面** | `catdesk browser-action '{"action":"navigate","url":"<url>"}'` | `catdesk.cmd browser-action '{"action":"navigate","url":"<url>"}'` | 内置 `browser(navigate, url=<url>)`；若超时，改用 `browser(open, url=<url>)` 重试 | 内置 `browser(navigate, url=<url>)`；若超时，改用 `browser(open, url=<url>)` 重试 |
| **执行 JS** | `catdesk browser-action '{"action":"evaluate","script":"<js>"}'` | 同上，替换为 `catdesk.cmd` | 调用内置 `browser(evaluate, fn=<js>)` | 调用内置 `browser(evaluate, fn=<js>)` |
| **等待条件成立** | `catdesk browser-action '{"action":"waitforfunction","expression":"<js>","timeout":30000}'` | 同上，替换为 `catdesk.cmd` | 轮询 `browser(evaluate, fn=<js>)` 每 2 秒一次，最多 15 次 | 轮询 `browser(evaluate, fn=<js>)` 每 2 秒一次，最多 15 次 |
| **打开文枢链接**（无需 token） | 使用 `wenshu-tools` Skill 下载 | 使用 `wenshu-tools` Skill 下载 | 使用 `wenshu-tools` Skill 下载 | 使用 `wenshu-tools` Skill 下载 |

---

## 核心流程

### 第一步：打开报表并等待就绪

> 📌 **host 提取规则**：从用户提供的仪表板 URL 中读取 host，**不要硬编码**。
> - 用户给的是 `bi.keetapp.com/v2/dashboard/...` → host 用 `bi.keetapp.com`
> - 用户给的是 `mdbi.bi.st.keetapp.com/v2/dashboard/...` → host 用 `mdbi.bi.st.keetapp.com`
> - 其他环境同理，保持原 host 不变，只替换路径为 `/v2/dashboard/dashboard-controller?dashboardId={id}`

**CatPaw Desk (macOS/Linux)：**
```bash
# 注入 headers（navigate 前必须执行）
headers_json=$([skill-dir]/scripts/moshu/build_headers.sh)
catdesk browser-action "{\"action\":\"headers\",\"headers\":$headers_json}"

# 直接导航（境外版无需 token）
catdesk browser-action '{"action":"navigate","url":"https://{host}/v2/dashboard/dashboard-controller?dashboardId=<报表ID>"}'

# 等待控制器挂载（最多 30 秒）
catdesk browser-action '{"action":"waitforfunction","expression":"window.DashboardController !== undefined","timeout":30000}'
```

**CatPaw Desk (Windows)：**
```powershell
# 注入 headers（navigate 前必须执行）
$headers_json = & "[skill-dir]\scripts\moshu\build_headers.ps1"
catdesk.cmd browser-action "{\"action\":\"headers\",\"headers\":$headers_json}"

# 直接导航（境外版无需 token）
catdesk.cmd browser-action '{"action":"navigate","url":"https://{host}/v2/dashboard/dashboard-controller?dashboardId=<报表ID>"}'

# 等待控制器挂载（最多 30 秒）
catdesk.cmd browser-action '{"action":"waitforfunction","expression":"window.DashboardController !== undefined","timeout":30000}'
```

**CatClaw 环境：**
```bash
# 注入 headers（navigate 前必须执行）
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

# 直接导航（境外版无需 token）
browser(navigate, url="https://{host}/v2/dashboard/dashboard-controller?dashboardId=<报表ID>")
# 若超时，改用 browser(open, url=<同上>) 重试

# 轮询等待，每 2 秒一次，最多 15 次
browser(evaluate, fn="window.DashboardController !== undefined")
```

**OpenClaw 环境：**
```bash
# OpenClaw 无需注入 headers

# 直接导航（境外版无需 token）
browser(navigate, url="https://{host}/v2/dashboard/dashboard-controller?dashboardId=<报表ID>")
# 若超时，改用 browser(open, url=<同上>) 重试

# 轮询等待，每 2 秒一次，最多 15 次
browser(evaluate, fn="window.DashboardController !== undefined")
```

> 🚫 **严禁截图**：该页面对用户呈现为空白页，截图只会给用户造成困惑，任何情况下都不得对此页面执行 screenshot 操作。
>
> ✅ `window.DashboardController` 存在后即可直接调用其任意方法，无需额外等待。

---

### 第二步：获取报表所有组件

**CatPaw Desk (macOS/Linux)：**
```bash
catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.getComponents().then(res => JSON.stringify(res))"}'
```
**CatPaw Desk (Windows)：** 同上，替换路径。

**OpenClaw 环境：**
```
browser(evaluate, fn="window.DashboardController.getComponents().then(res => JSON.stringify(res))")
```

**返回示例：**
```json
{
  "code": 0,
  "data": [
    { "componentId": "...", "componentName": "GMV贡献Top10省份", "componentType": "chart", "relationComponents": ["..."] },
    { "componentId": "...", "componentName": "时间筛选器", "componentType": "filter", "extends": { "filterType": "time" } },
    { "componentId": "...", "componentName": "业务交易报表", "componentType": "tab", "childrenComponents": ["..."] }
  ]
}
```

**componentType 说明：**
- `chart` — 图表组件，可查询数据
- `filter` — 筛选器，可读取/修改筛选条件
- `tab` — 标签页容器，包含子组件列表

**记录下需要操作的组件名称和对应 ID，后续步骤会用到。**

---

### 第三步（可选）：按需执行以下操作，无固定顺序

> 获取组件后可直接跳到第四步触发查询。以下操作均为可选，根据实际需求选择执行，顺序不限。

#### A. 查看仪表板筛选器当前值

**CatPaw Desk (macOS/Linux)：**
```bash
catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.getFiltersInfo([\"<筛选器ID>\"]).then(res => JSON.stringify(res))"}'
```
**CatPaw Desk (Windows)：** 同上，替换路径。

**OpenClaw 环境：**
```
browser(evaluate, fn="window.DashboardController.getFiltersInfo(['<筛选器ID>']).then(res => JSON.stringify(res))")
```

**返回示例（时间筛选器）：**
```json
{
  "code": 0,
  "data": [{
    "name": "时间筛选器",
    "filterType": "time",
    "filterValue": [
      { "offset": -7, "granularity": "DAY", "type": "OFFSET" },
      { "offset": -1, "granularity": "DAY", "type": "OFFSET" }
    ]
  }]
}
```

**时间范围解读：**
- `filterValue[0]` 是起始时间，`filterValue[1]` 是结束时间
- `offset` 是相对今天的天数偏移，`-7` 表示 7 天前，`-1` 表示昨天
- 上例表示：**最近 7 天（不含今天）**

> 返回值字段完整说明（`key`、`filterType`、`filterValue`、`options` 等）见 [`dashboard-controller-api.md`](./dashboard-controller-api.md) → `getFiltersInfo` → 返回值。

---

#### B. 修改仪表板筛选器值

> ⚠️ **各类型筛选器的 `userInput` 格式（日期范围、单选、多选、树选、级联、数值、文本、组织、时区等）完整说明见 [`dashboard-controller-api.md`](./dashboard-controller-api.md) → `setFiltersValues` → FilterUserInput 格式（按筛选器类型）。**

#### 修改时间筛选器

**CatPaw Desk (macOS/Linux)：**
```bash
catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.setFiltersValues([{id:\"<筛选器ID>\",userInput:{value:[{offset:<起始偏移>,granularity:\"DAY\",type:\"OFFSET\"},{offset:<结束偏移>,granularity:\"DAY\",type:\"OFFSET\"}],granularity:\"DAY\"}}]).then(res => JSON.stringify(res))"}'
```
**CatPaw Desk (Windows)：** 同上，替换路径。

**OpenClaw 环境：**
```
browser(evaluate, fn="window.DashboardController.setFiltersValues([{id:'<筛选器ID>',userInput:{value:[{offset:<起始偏移>,granularity:'DAY',type:'OFFSET'},{offset:<结束偏移>,granularity:'DAY',type:'OFFSET'}],granularity:'DAY'}}]).then(res => JSON.stringify(res))")
```

**常用时间范围对照表：**

| 用户说的时间范围 | 起始 offset | 结束 offset |
|----------------|------------|------------|
| 最近 7 天       | -7         | -1         |
| 最近 14 天      | -14        | -1         |
| 最近 30 天      | -30        | -1         |
| 最近 90 天      | -90        | -1         |
| 昨天            | -1         | -1         |
| 今天            | 0          | 0          |

**修改枚举/下拉筛选器 — CatPaw 环境：**
```bash
~/.catpaw/bin/catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.setFiltersValues([{\"id\":\"<筛选器ID>\",\"userInput\":{\"value\":[\"选项值1\",\"选项值2\"],\"isEmpty\":false,\"isNoFilter\":false,\"isSelectDummyAll\":false,\"selectAllFlag\":false}}]).then(res => JSON.stringify(res))"}'
```

**修改枚举/下拉筛选器 — OpenClaw 环境：**
```
browser(action="act", kind="evaluate", fn="window.DashboardController.setFiltersValues([{id:'<筛选器ID>',userInput:{value:['选项值1','选项值2'],isEmpty:false,isNoFilter:false,isSelectDummyAll:false,selectAllFlag:false}}]).then(res => JSON.stringify(res))")
```

> 设置成功后返回 `{"code": 0, "message": "操作成功"}`。建议设置后用 `getFiltersInfo` 验证值已生效。

---

#### C. 查看并修改图表指标维度池

> 适用于需要调整图表展示哪些指标/维度字段的场景（如隐藏某个维度、增加某个指标）。
>
> ⚠️ **注意**：参数为图表的 `componentId`（格式如 `dashboard-chart-container-xxx`），直接从 `getComponents()` 返回的 `componentId` 字段获取。

**查看指标维度池 — CatPaw 环境：**
```bash
~/.catpaw/bin/catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.getFieldPools(\"<图表componentId>\").then(res => JSON.stringify(res))"}'
```

**查看指标维度池 — OpenClaw 环境：**
```
browser(action="act", kind="evaluate", fn="window.DashboardController.getFieldPools('<图表componentId>').then(res => JSON.stringify(res))")
```

**修改指标维度池 — CatPaw 环境：**
```bash
~/.catpaw/bin/catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.updateFieldPools(\"<图表componentId>\", {\"unselectedDimensions\":[\"<fieldId>\"],\"selectedMetrics\":[\"<fieldId>\"]}).then(res => JSON.stringify(res))"}'
```

**修改指标维度池 — OpenClaw 环境：**
```
browser(action="act", kind="evaluate", fn="window.DashboardController.updateFieldPools('<图表componentId>', {unselectedDimensions:['<fieldId>'],selectedMetrics:['<fieldId>']}).then(res => JSON.stringify(res))")
```

> `options` 四个字段均为可选，只传需要修改的：`selectedDimensions` / `unselectedDimensions` / `selectedMetrics` / `unselectedMetrics`。

---

#### D. 获取图表内部筛选器值

> 获取分析板中图表内嵌的筛选器信息（图表级筛选器，区别于仪表板级筛选器）。

**CatPaw 环境：**
```bash
~/.catpaw/bin/catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.getChartFilters([\"<图表componentId>\"]).then(res => JSON.stringify(res))"}'
```

**OpenClaw 环境：**
```
browser(action="act", kind="evaluate", fn="window.DashboardController.getChartFilters(['<图表componentId>']).then(res => JSON.stringify(res))")
```

> 参数为图表 `componentId` 数组（`dashboard-chart-container-xxx`），可同时传入多个图表。

---

#### E. 设置图表内部筛选器值

> 修改分析板中图表内嵌筛选器的值。与 `getChartFilters` 配对使用。
>
> ⚠️ **注意**：图表内嵌筛选器应使用本方法修改，而不是 `setFiltersValues`（`setFiltersValues` 仅适用于仪表板级筛选器）。

**CatPaw 环境（设置日期范围）：**
```bash
~/.catpaw/bin/catdesk browser-action '{"action":"evaluate","script":"DashboardController.setChartFilters([{\"id\":\"<图表componentId>\",\"filters\":[{\"type\":\"DATERANGE\",\"id\":\"<字段ID>\",\"name\":\"<字段名>\",\"userInput\":{\"filterType\":\"BETWEEN_AND\",\"relationType\":\"LEAF\",\"value\":[{\"direction\":\"FORWARD\",\"offsetValue\":1,\"granularity\":\"DAY\"},{\"direction\":\"FORWARD\",\"offsetValue\":20,\"granularity\":\"DAY\"}]},\"queryConfig\":{\"timeUnitType\":\"DAY\"}}]}])"}'
```

**CatPaw 环境（设置下拉筛选器）：**
```bash
~/.catpaw/bin/catdesk browser-action '{"action":"evaluate","script":"DashboardController.setChartFilters([{\"id\":\"<图表componentId>\",\"filters\":[{\"type\":\"ORDINARY\",\"id\":\"<字段ID>\",\"name\":\"<字段名>\",\"userInput\":{\"filterType\":\"INCLUDE\",\"relationType\":\"LEAF\",\"value\":[{\"label\":\"<选项展示文>\",\"value\":\"<选项值>\"}],\"isEmpty\":false,\"isNoFilter\":false,\"isSelectDummyAll\":false,\"sort\":{}}}]}])"}'
```

**OpenClaw 环境：**
```
browser(action="act", kind="evaluate", fn="DashboardController.setChartFilters([{id:'<图表componentId>',filters:[{type:'ORDINARY',id:'<字段ID>',name:'<字段名>',userInput:{filterType:'INCLUDE',relationType:'LEAF',value:[{label:'<选项展示文>',value:'<选项值>'}],isEmpty:false,isNoFilter:false,isSelectDummyAll:false,sort:{}}}]}])")
```

> 支持的筛选器类型：`DATERANGE`（日期范围）、`NUMERICAL`（数值）、`ORDINARY`（下拉/枚举）。各类型 `userInput` 格式详见 [`dashboard-controller-api.md`](./dashboard-controller-api.md) → `setChartFilters`。

---

#### F. 查看组织架构筛选器可选节点

> 获取用户有权限的组织架构树，用于 **Org 类型筛选器**的取值和设置。

**CatPaw 环境：**
```bash
~/.catpaw/bin/catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.getCurrentUserOrgTree({filterId:\"<组织架构筛选器ID>\"}).then(res => JSON.stringify(res))"}'
```

**OpenClaw 环境：**
```
browser(action="act", kind="evaluate", fn="window.DashboardController.getCurrentUserOrgTree({filterId:'<组织架构筛选器ID>'}).then(res => JSON.stringify(res))")
```

**返回值关键字段**：
- `tree`：树形结构，每个节点含 `value`（节点ID）、`label`（节点名称）、`children`
- `paths`：所有叶节点路径数组，每个路径为`[节点ID]` 或 `[父节点ID, 子节点ID, ...]`

---

#### G. 设置组织架构筛选器值

> 设置 Org 类型筛选器的选中节点。需先通过 `getCurrentUserOrgTree` 获取可选节点。

**CatPaw 环境：**
```bash
~/.catpaw/bin/catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.setFiltersValues([{id:\"<组织架构筛选器ID>\",userInput:{orgFilterInfo:[{values:[[\"<节点ID1>\"],[\"<节点ID2>\"]]}]}}]).then(res => JSON.stringify(res))"}'
```

**OpenClaw 环境：**
```
browser(action="act", kind="evaluate", fn="window.DashboardController.setFiltersValues([{id:'<组织架构筛选器ID>',userInput:{orgFilterInfo:[{values:[['<节点ID1>'],['<节点ID2>']]}]}}]).then(res => JSON.stringify(res))")
```

> 💡 `orgFilterInfo.values` 是节点路径数组。对于顶级节点，路径为 `[节点ID]`；对于嵌套节点，路径为 `[父节点ID, 子节点ID, ...]`。

---

### 第四步：触发查询并读取结果

> 总结或查看数据时，直接处理查询返回的数据内容：读取 `data.columns` 和 `data.data`，不要再调用 `executeDownload`。
>
> 只有用户明确要求导出、下载、CSV/Excel、文件链接或文枢链接时，才需要在本步骤完成后进入第六步调用 `executeDownload`。

**CatPaw Desk (macOS/Linux)：**
```bash
catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.executeQueryAndGetCHNResult(\"<图表组件ID>\").then(res => JSON.stringify(res))"}'
```
**CatPaw Desk (Windows)：** 同上，替换路径。

**OpenClaw 环境：**
```
browser(evaluate, fn="window.DashboardController.executeQueryAndGetCHNResult('<图表组件ID>').then(res => JSON.stringify(res))")
```

> 返回值中 `data.columns` 是列名，`data.data` 是二维数据行。基于这两个字段即可向用户展示或总结数据情况。

---

### 第六步：按需获取文枢下载链接（含指数退避重试）

> 仅当用户明确要求导出/下载时执行本步骤。`executeDownload` 由服务端异步生成文件，数据量大时可能未立即就绪而导致超时，需使用**指数退避重试**策略。

#### 重试策略

| 参数 | 值 |
|------|-----|
| 单次调用超时 | 30 秒 |
| 等待间隔序列 | 15s → 30s → 60s → 120s → 120s → ... （120s 封顶） |
| 总等待上限 | **约 10 分钟**（含调用时间 + 间隔时间） |
| 累计等待达 5 分钟时 | 告知用户：`"下载文件生成中，最长还需等待约 5 分钟，请耐心等候。"` |
| 超出总上限 | 放弃重试，告知用户服务端生成超时，建议稍后重试或前往仪表板手动下载 |

#### 不可重试的错误（立即终止，不进入重试循环）

| 返回值 | 含义 | 处理方式 |
|--------|------|---------|
| `undefined` | 该仪表板暂不支持自动下载功能 | 告知用户："您的仪表板暂不支持自动下载功能，请前往仪表板页面手动下载。" |
| `code !== 0` 且 message 含 `"请先查询数据"` | 未先调用 `executeQueryAndGetCHNResult` | 先执行第五步触发查询，再重新进入本步骤 |

#### 可重试的错误

| 错误类型 | 说明 |
|---------|------|
| 调用超时（30s 内未返回） | 服务端文件生成中，等待后重试 |
| 网络错误 / 接口异常 | 临时故障，等待后重试 |
| `code !== 0` 且 message **不含** `"请先查询数据"` | 服务端临时异常，等待后重试 |

#### 调用流程（伪代码）

```
wait_intervals = [15, 30, 60, 120]  # 秒，后续均为 120s
total_elapsed = 0
max_total = 600  # 总上限 10 分钟
has_warned_5min = false

for attempt = 1, 2, 3, ...:
    result = 调用 executeDownload（超时 30s）
    total_elapsed += 30  # 计入调用时间

    if result == undefined:
        → 该仪表板暂不支持此功能，立即终止，告知用户
        break

    if result.code == 0 且 result.data 非空:
        → 成功！返回 data（文枢下载链接）
        break

    if result.code != 0 且 result.message 含 "请先查询数据":
        → 先执行 executeQueryAndGetCHNResult，再重新进入本步骤
        break

    # 可重试错误，计算等待时间
    wait_index = min(attempt - 1, len(wait_intervals) - 1)
    wait_time = wait_intervals[wait_index]

    if total_elapsed + wait_time > max_total:
        → 超出总上限，放弃重试，告知用户
        break

    if not has_warned_5min 且 total_elapsed >= 300:
        → 告知用户："下载文件生成中，最长还需等待约 5 分钟，请耐心等候。"
        has_warned_5min = true

    等待 wait_time 秒
    total_elapsed += wait_time
```

#### 实际调用命令

**CatPaw Desk (macOS/Linux)：**
```bash
catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.executeDownload(\"<图表组件ID>\", {fileType: \"CSV\"}).then(res => JSON.stringify(res))"}'
```
**CatPaw Desk (Windows)：** 同上，替换路径。

**OpenClaw 环境：**
```
browser(evaluate, fn="window.DashboardController.executeDownload('<图表组件ID>', {fileType: 'CSV'}).then(res => JSON.stringify(res))")
```

**返回示例（成功）：**
```json
{
  "code": 0,
  "message": "",
  "data": "http://wenshu-s3.sankuai.com/.../%E6%96%87%E4%BB%B6%E5%90%8D.csv?AWSAccessKeyId=xxx&Expires=xxx&Signature=xxx"
}
```

> ⚠️ **【重要】展示文枢链接时，必须使用 `[图表名称](URL)` 超链接格式，严禁用反引号包裹裸 URL。**
> 原因：裸 URL 含中文 percent-encoding 字符串较长会被截断无法点击；超链接格式的 href 值不经过 Markdown URL 解码，用户点击时使用的是完整原始 URL，签名校验正常。
> 正确展示方式：`[图表名称](http://wenshu-s3.sankuai.com/.../%E6%96%87%E4%BB%B6%E5%90%8D.csv?...)`

**可选参数：**

| 参数 | 可选值 | 默认 | 说明 |
|------|-------|------|------|
| `fileType` | `'CSV'` / `'XLSX'` | `'CSV'` | 文件格式 |
| `useDataFormat` | `true` / `false` | `false` | `true`=展示格式，`false`=原始格式 |
| `tableType` | `'crosstab'` / `'raw'` | `'crosstab'` | 交叉表或原始表 |

---

## 完整示例：查询指定报表的图表数据

> 以下示例以 `mdbi.bi.st.keetapp.com` 为例（ST 环境），实际使用时请替换为用户 URL 中的 host。

**以下为 macOS/Linux 命令，Windows 替换路径即可。**

```bash
# 0. 注入 headers（navigate 前必须执行；CatClaw 使用 fetch 拦截方式注入，OpenClaw 无需注入）
headers_json=$([skill-dir]/scripts/moshu/build_headers.sh)
catdesk browser-action "{\"action\":\"headers\",\"headers\":$headers_json}"

# 1. 直接导航（境外版无需 token）
catdesk browser-action '{"action":"navigate","url":"https://mdbi.bi.st.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=249583"}'

# 2. 等待控制器就绪
catdesk browser-action '{"action":"waitforfunction","expression":"window.DashboardController !== undefined","timeout":30000}'

# 3. 获取所有组件，找到目标图表的 ID
catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.getComponents().then(res => JSON.stringify(res))"}'

# 4. 触发查询并读取结果；总结/查看数据时直接使用返回的 data.columns 和 data.data
catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.executeQueryAndGetCHNResult(\"<图表ID>\").then(res => JSON.stringify(res))"}'

# 5. 仅当用户明确要求导出/下载时，获取文枢下载链接（带指数退避重试，详见第六步）
catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.executeDownload(\"<图表ID>\", {fileType: \"CSV\"}).then(res => JSON.stringify(res))"}'
# 若超时或返回非成功结果，按 15s→30s→60s→120s 间隔重试，总上限约 10 分钟
```

---

## 常见问题

**Q: `executeQueryAndGetCHNResult` 返回 `{code: 0, message: ""}` 但没有 data？**

A: 先确认返回结构中是否存在 `data.columns` 和 `data.data`。总结或查看数据时，应直接处理这两个字段；如果确实为空，先等待引擎就绪后重试一次，仍为空再判断该图表是否不支持直接取数。只有用户明确要求导出时，才继续调用 `executeDownload`。

**Q: `executeDownload` 返回 `undefined`？**

A: 该仪表板暂不支持自动下载功能。**不可重试**，立即告知用户："您的仪表板暂不支持自动下载功能，请前往仪表板页面手动下载。"

**Q: 取数失败，且用户使用的是 1.0 仪表板（URL 格式为 `{domain}/dashboard/{id}`，无 `/v2/`）？**

A: 1.0 仪表板使用的是旧版取数方案，功能和稳定性不如 2.0 仪表板。建议告知用户："您当前使用的是 1.0 版本仪表板，建议联系仪表板负责人升级到 2.0 版本，升级后取数体验更好、功能更完整。如需协助，可提交 TT 工单：[提交问题反馈](https://tt.sankuai.com/ticket/custom/create/12669/16144)。"

**Q: `executeDownload` 调用超时了怎么办？**

A: 这通常是服务端正在生成文件。按指数退避策略重试（15s→30s→60s→120s 间隔），总上限约 10 分钟。累计等待达 5 分钟时需提醒用户。详见第六步的重试策略。

**Q: 如何同时修改多个筛选器？**

A: `setFiltersValues` 接受数组，可以一次传入多个筛选器配置：
```bash
catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.setFiltersValues([{id:\"<筛选器1ID>\",userInput:{...}},{id:\"<筛选器2ID>\",userInput:{...}}]).then(res => JSON.stringify(res))"}'
```

**Q: 修改筛选器后触发查询需要 force: true 吗？**

A: 不需要主动传。先用默认查询；如果 `executeQueryAndGetCHNResult` 返回的数据没有反映新的筛选条件，再改用 `{force: true}` 重新触发查询。

**Q: 如何获取报表 ID？**

A: 从报表页面 URL 中获取，格式为 `?dashboardId=<数字>`。

---

## API 速查

| 操作 | 方法 |
|------|------|
| 获取所有组件 | `window.DashboardController.getComponents()` |
| 查看仪表板筛选器值 | `window.DashboardController.getFiltersInfo([id1, id2, ...])` |
| 修改仪表板筛选器值 | `window.DashboardController.setFiltersValues([{id, userInput}])` |
| 查看图表指标维度池 | `window.DashboardController.getFieldPools(componentId)` |
| 修改图表指标维度池 | `window.DashboardController.updateFieldPools(componentId, {selectedDimensions, unselectedDimensions, selectedMetrics, unselectedMetrics})` |
| 获取图表内嵌筛选器值 | `window.DashboardController.getChartFilters([componentId1, ...])` |
| 设置图表内嵌筛选器值 | `DashboardController.setChartFilters([{id, filters:[{type, id, name, userInput}]}])` |
| 获取组织架构树 | `window.DashboardController.getCurrentUserOrgTree({filterId})` |
| 查询并返回图表数据 | `window.DashboardController.executeQueryAndGetCHNResult(chartId)` |
| 按需获取文枢下载链接 | `window.DashboardController.executeDownload(chartId, {fileType: "CSV"})` |
