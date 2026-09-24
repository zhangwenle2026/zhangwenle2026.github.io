---
name: dashboard-meta
description: "获取美团魔数仪表板元数据：组件列表、筛选器结构与当前值、图表的数据集/指标/维度定义。适用于「想了解仪表板有哪些图表/筛选器」而不需要取数的场景。"
---

# Dashboard 元数据获取

当你只需要了解仪表板的结构信息（有哪些图表、筛选器是什么类型、指标维度定义等），而不需要获取数据时，使用本文档的方法。

---

## 两种元数据来源

| 来源 | 获取方式 | 能获取的信息 | 需要打开浏览器 |
|------|---------|------------|--------------|
| **JS 前端接口** | 浏览器 evaluate 直调 `DashboardController` | 组件列表、筛选器类型与**当前值**、可选维值 | ✅ 需要 |
| **MCP 后端接口** | `keeta_mtbi_dashboard_meta_info` MCP 工具 | 仪表板基础信息、**指标/维度定义**、数据集名称、安全等级 | ❌ 不需要 |

> 两者互补：JS 接口反映**运行时当前状态**（筛选器当前值、可选项）；MCP 接口反映**后端配置**（图表背后的指标/维度定义）。

---

## 方式一：JS 前端接口（DashboardController）

### 前置步骤：打开 controller 专用页面

> 📌 **host 提取规则**：从用户提供的仪表板 URL 中读取 host，不要硬编码。

**CatPaw Desk (macOS/Linux)：**
```bash
# 设置请求头（navigate 前必须执行，仅 CatDesk 环境）
headers_json=$([skill-dir]/scripts/moshu/build_headers.sh)
catdesk browser-action "{\"action\":\"headers\",\"headers\":$headers_json}"
# 直接导航（境外版无需 token）
catdesk browser-action '{"action":"navigate","url":"https://{host}/v2/dashboard/dashboard-controller?dashboardId={id}"}'
catdesk browser-action '{"action":"waitforfunction","expression":"window.DashboardController !== undefined","timeout":30000}'
```
**CatPaw Desk (Windows)：** 同上，替换路径。

**OpenClaw 环境：** 调用内置 `browser(navigate, url="https://{host}/v2/dashboard/dashboard-controller?dashboardId={id}")`；若超时，改用 `browser(open, url=<同上>)` 重试。再轮询等待 `window.DashboardController !== undefined`。

> 🚫 **严禁截图**：该页面对用户呈现为空白页。

---

### 1. 获取全量组件列表（`getComponents`）

```bash
# CatPaw Desk (macOS/Linux)
catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.getComponents().then(res => JSON.stringify(res))"}'
```
> Windows: 替换路径。

**返回的元数据字段：**

| 字段 | 说明 |
|------|------|
| `componentId` | 组件唯一 ID（取数/下载时使用） |
| `componentName` | 组件显示名称 |
| `componentType` | `chart`（图表）/ `filter`（筛选器）/ `tab`（Tab 容器） |
| `childrenComponents` | Tab 的子组件列表（仅 tab 类型有值） |
| `relationComponents` | 该图表关联的筛选器 ID 列表 |
| `extends.filterType` | 筛选器类型（仅 filter 类型有值，如 `time`、`ordinary`） |

**返回示例：**
```json
{
  "code": 0,
  "data": [
    {
      "componentId": "dashboard-chart-container-oxmf3-df06d",
      "componentName": "GMV贡献Top10省份",
      "componentType": "chart",
      "childrenComponents": [],
      "relationComponents": ["filter-4vmv0-89c75"]
    },
    {
      "componentId": "filter-4vmv0-89c75",
      "componentName": "时间筛选器",
      "componentType": "filter",
      "childrenComponents": [],
      "relationComponents": [],
      "extends": { "filterType": "time" }
    },
    {
      "componentId": "tabs-abc-12345",
      "componentName": "业务交易报表",
      "componentType": "tab",
      "childrenComponents": [
        { "componentId": "dashboard-chart-container-c1isq-141b4", "componentType": "chart" }
      ],
      "relationComponents": []
    }
  ]
}
```

**按类型过滤（常用）：**
```bash
# 只看图表
catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.getComponents({componentType:\"chart\"}).then(res => JSON.stringify(res))"}'
# 只看筛选器
catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.getComponents({componentType:\"filter\"}).then(res => JSON.stringify(res))"}'
```
> Windows: 替换路径。

---

### 2. 获取筛选器详情（`getFiltersInfo`）

在 `getComponents` 的基础上，进一步获取每个筛选器的**当前值**和**可选项**：

```bash
# 获取全部筛选器详情
catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.getFiltersInfo().then(res => JSON.stringify(res))"}'
# 获取指定筛选器
catdesk browser-action '{"action":"evaluate","script":"window.DashboardController.getFiltersInfo([\"filter-4vmv0-89c75\"]).then(res => JSON.stringify(res))"}'
```
> Windows: 替换路径。

**返回的额外元数据字段：**

| 字段 | 说明 |
|------|------|
| `filterValue` | 当前生效的筛选条件（日期范围为 offset 对象数组，枚举为值数组） |
| `options` | 可选维值列表（仅 Radio / Multiple / Tree / Cascade 类筛选器有值，日期类为 `[]`） |

**返回示例：**
```json
{
  "code": 0,
  "data": [
    {
      "key": "filter-4vmv0-89c75",
      "name": "时间筛选器",
      "filterType": "time",
      "filterValue": [
        { "offset": -7, "granularity": "DAY", "type": "OFFSET" },
        { "offset": -1, "granularity": "DAY", "type": "OFFSET" }
      ],
      "options": []
    },
    {
      "key": "dashboard-filter-6ssda-8e532",
      "name": "产品模块",
      "filterType": "ordinary",
      "filterValue": { "kind": 1, "value": ["魔数2.0-仪表板"], "rel": "IN", "selectAllFlag": false },
      "options": [
        { "value": "魔数2.0-仪表板", "label": "魔数2.0-仪表板", "hasPermission": true },
        { "value": "AI-分析Agent", "label": "AI-分析Agent", "hasPermission": true }
      ]
    }
  ]
}
```

> `key` 字段即为筛选器的 `componentId`，与 `getComponents` 返回的 ID 对应。

> 各筛选器类型的完整字段说明见 [`dashboard-controller-api.md`](./dashboard-controller-api.md)。

---

## 方式二：MCP 后端接口（`keeta_mtbi_dashboard_meta_info`）

无需打开浏览器，直接通过 MCP 接口获取仪表板后端配置元数据，**特别适合获取指标/维度定义**。使用境外专用的 `keeta_mtbi_ai` MCP Server。

### 步骤

> 📄 **完整调用流程详见 [`query_dashboard_meta.md`](./query_dashboard_meta.md)**，本节为概要说明。

**1. 解析 dashboardId**

从用户提供的 URL 路径最后一段提取，如 `bi.keetapp.com/v2/dashboard/12345` → `12345`。

**2. 注册 MCP Server 并调用**

按照 [`query_dashboard_meta.md`](./query_dashboard_meta.md) 步骤 2-3 完成：通过 `friday-mcp` skill 换票 → `mcporter config add` 注册 server（`keeta_mtbi_ai`）→ 调用 `keeta_mtbi_dashboard_meta_info`。

```bash
mcporter call 'keeta_mtbi_ai.keeta_mtbi_dashboard_meta_info(dashboardId: "<dashboardId>")'
```

**3. 过滤精简原始数据（可选）**

原始返回数据量较大，可用 `filter_dashboard_meta.py` 提炼关键字段，详见 [`query_dashboard_meta.md`](./query_dashboard_meta.md) 步骤 4：

```bash
mcporter call 'keeta_mtbi_ai.keeta_mtbi_dashboard_meta_info(dashboardId: "<dashboardId>")' > /tmp/dashboard_meta_raw.json
python3 scripts/filter_dashboard_meta.py --input /tmp/dashboard_meta_raw.json
```

输出保存在 `scripts/dashboard_meta.json`。

### 能获取的元数据字段

| 类别 | 字段 | 说明 |
|------|------|------|
| 仪表板基础信息 | `id` / `name` / `version` | 仪表板 ID、名称、版本号 |
| | `security_level` | 安全等级（来自 globalConfig） |
| Tab 结构 | `tab_id` / `tab_name` | 仪表板的 Tab 分组信息 |
| 组件信息 | `component_id` / `component_name` / `type` | 组件基础信息 |
| | `dataset_name` | 图表使用的数据集名称 |
| | `biz_id` / `dataset_id` | 数据集所属业务线 ID 和数据集 ID |
| | `dataset_url` | ⭐ 数据集起源链接（bizId=332 时指向个人数据集页；其他指向起源数据主题页） |
| **指标** | `metrics[].code` / `metrics[].name` | ⭐ JS 接口获取不到，图表使用的指标字段 |
| **维度** | `dims[].code` / `dims[].name` | ⭐ JS 接口获取不到，图表使用的维度字段 |
| 全局筛选器 | `fid` / `name` / `type` | 筛选器 ID、名称、类型 |
| | `fields[].code` / `fields[].name` | 筛选器关联的字段定义 |

**精简后输出示例：**
```json
{
  "dashboard": { "id": "12345", "name": "GMV核心指标看板", "version": "3", "security_level": "L2" },
  "tabs": [
    {
      "tab_id": "tab-001", "tab_name": "整体概览",
      "components": [
        {
          "component_id": "comp-abc", "component_name": "GMV趋势", "type": "line",
          "biz_id": 123, "dataset_id": "456",
          "dataset_name": "订单数据集",
          "dataset_url": "https://origin.keetapp.com/data-subject/detail/456?busiLineId=123",
          "metrics": [{ "code": "gmv", "name": "订单GMV" }],
          "dims":    [{ "code": "dt", "name": "日期" }, { "code": "province", "name": "省份" }]
        }
      ]
    }
  ],
  "global_filters": [
    { "fid": "f-001", "name": "时间筛选器", "type": "DateRange", "fields": [{ "code": "dt", "name": "日期" }] }
  ]
}
```

> ⚠️ MCP 接口调用失败不影响其他流程，失败时直接跳过。

---

## 两种方式对比速查

| | JS 前端接口 | MCP 后端接口 |
|--|------------|------------|
| 组件列表（ID、名称、类型） | ✅ | ✅ |
| 筛选器当前值 | ✅ | ❌ |
| 筛选器可选维值 | ✅ | ❌ |
| 指标/维度字段定义 | ❌ | ✅ |
| 数据集名称 | ❌ | ✅ |
| 安全等级 | ❌ | ✅ |
| 需要打开浏览器 | ✅ 需要 | ❌ 不需要 |
| 反映运行时状态 | ✅ 实时 | ❌ 静态配置 |
