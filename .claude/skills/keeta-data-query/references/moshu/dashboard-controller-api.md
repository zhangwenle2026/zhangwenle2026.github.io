---
name: dashboard-controller-api
description: "window.DashboardController JS 接口完整技术参考文档，整合需求设计文档、线上验收记录与 FilterProtocol 规范。"
---

# DashboardController API 参考

> 来源：
> - 需求文档：https://km.sankuai.com/collabpage/2752941966
> - 线上验收记录：https://km.sankuai.com/collabpage/2753401867
> - FilterProtocol 规范：https://km.sankuai.com/collabpage/2749600978（第 3.2 节）
>
> **以线上验收记录为准**，与需求文档有出入时优先看验收记录列。

---

## 基本信息

| 项目 | 说明 |
|------|------|
| 挂载点 | `window.DashboardController`（**大写 C**） |
| 上线状态 | **已全量上线** |
| 专用页面 | `https://{host}/v2/dashboard/dashboard-controller?dashboardId={id}` |
| 普通查看页 | `https://{host}/v2/dashboard/{id}`（**不会挂载 DashboardController，禁止用此页面**） |

---

## 全局类型定义

### ComponentType（组件类型）

| 类型 | 说明 |
|------|------|
| `chart` | 图表组件，可调用 `executeQueryAndGetCHNResult` 取数 |
| `filter` | 筛选器组件，可调用 `getFiltersInfo` 获取详情，`setFiltersValues` 修改值 |
| `tab` | Tab 页签组件，含 `childrenComponents` 子组件列表 |

### FilterType（筛选器类型）

> `getFiltersInfo` 返回的 `filterType` 字段值为简化名称（如 `time`、`ordinary`），与下表的规范类型名不完全对应，以实际返回值为准。

| FilterType（规范名） | getFiltersInfo 返回的 filterType | 说明 |
|---------------------|----------------------------------|------|
| `Date` | `time` | 单日期筛选器 |
| `DateRange` | `time` | 日期范围筛选器 |
| `Time` | `time` | 时间筛选器（精确到时分秒） |
| `TimeRange` | `time` | 时间范围筛选器 |
| `Numerical` | `numerical` | 数值条件筛选器 |
| `Org` | `org` | 组织架构筛选器 |
| `TimeZone` | `timezone` | 时区筛选器 |
| `Input` | `input` | 文本条件筛选器 |
| `Radio` | `ordinary` | 单选筛选器 |
| `Multiple` | `ordinary` | 多选筛选器 |
| `Tree` | `ordinary` | 树筛选器 |
| `CascadeRadio` | `cascade` | 级联单选筛选器 |
| `CascadeMultiple` | `cascade` | 级联多选筛选器 |

> `options` 字段只对有维值的筛选器返回（Radio / Multiple / Tree / Cascade 类），日期类筛选器 `options` 为 `[]`。

---

## 接口一览

| 方法 | 说明 | 验收状态 |
|------|------|----------|
| `getComponents(params?)` | 获取全量或按条件过滤的组件元数据 | ✅ 全部通过 |
| `getFiltersInfo(componentIds?)` | 获取筛选器当前值和可选维值 | ✅ 全部通过 |
| `setFiltersValues(filters)` | 批量设置筛选器值 | ✅ 全部通过 |
| `executeQueryAndGetCHNResult(params)` | 执行查询，返回中文列名 + 数据 | ✅ 全部通过 |
| `waitForEngineReady()` | 等待渲染引擎就绪 | 实测存在，通常无需主动调用 |
| `executeDownload(componentId, options?)` | 触发图表数据下载，返回文枢 S3 下载链接 | ✅ 已验证（部分仪表板可能暂不支持，见方法详情） |

---

## 方法详情

### `getComponents(params?)` — 获取组件元数据

> **推荐不传参调用**：返回全量组件（chart + filter + tab），包含完整的 `childrenComponents`（子组件）和 `relationComponents`（关联筛选器）信息。

**参数**（均非必填）：

| 参数 | 类型 | 说明 |
|------|------|------|
| `componentType` | `'chart' \| 'filter' \| 'tab'` | 按类型过滤 |
| `componentName` | `string` | 按名称过滤（精确匹配） |
| `componentId` | `string` | 按 ID 过滤 |

**返回值**：

```json
{
  "code": 0,
  "message": "",
  "data": [
    {
      "componentId": "dashboard-chart-container-oxmf3-df06d",
      "componentName": "GMV贡献Top10省份",
      "componentType": "chart",
      "childrenComponents": [],
      "relationComponents": ["filter-4vmv0-89c75"],
      "extends": {}
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

> - `relationComponents`：与该组件关联的筛选器 ID 列表，设置筛选条件时可参考
> - `childrenComponents`：Tab 组件的子组件列表，仅 `componentType: "tab"` 时有内容
> - `extends.filterType`：筛选器类型，仅 `componentType: "filter"` 时有内容

**已验证调用示例**：

```javascript
// 获取全部组件
window.DashboardController.getComponents().then(res => console.log(res))

// 按类型过滤：仅图表
window.DashboardController.getComponents({ componentType: "chart" }).then(res => console.log(res))

// 按类型过滤：仅筛选器
window.DashboardController.getComponents({ componentType: "filter" }).then(res => console.log(res))

// 按类型过滤：仅 Tab
window.DashboardController.getComponents({ componentType: "tab" }).then(res => console.log(res))

// 按 ID 查找
window.DashboardController.getComponents({ componentId: "filter-4vmv0-89c75" }).then(res => console.log(res))

// 按名称查找
window.DashboardController.getComponents({ componentName: "应用ID" }).then(res => console.log(res))
```

---

### `getFiltersInfo(componentIds?)` — 获取筛选器详情

**参数**（非必填）：

| 参数 | 类型 | 说明 |
|------|------|------|
| `componentIds` | `string[]` | 筛选器 ID 数组（来自 `getComponents` 返回的 `componentId`）；不传则返回全部 |

**返回值**：

```json
{
  "code": 0,
  "message": "",
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
      "filterValue": {
        "kind": 1,
        "value": ["魔数2.0-仪表板"],
        "rel": "IN",
        "selectAllFlag": false
      },
      "options": [
        { "value": "魔数2.0-仪表板", "label": "魔数2.0-仪表板", "hasPermission": true },
        { "value": "AI-分析Agent", "label": "AI-分析Agent", "hasPermission": true }
      ]
    }
  ]
}
```

> - `key`：筛选器的 componentId，在调用 `setFiltersValues` 时作为 `id` 参数传入
> - `filterValue`：当前生效的筛选值；日期范围类型时为数组，`[0]` 是起始，`[1]` 是结束
> - `options`：可选维值列表，仅 Radio / Multiple / Tree / Cascade 类筛选器有值

**已验证调用示例**：

```javascript
// 获取全部筛选器
window.DashboardController.getFiltersInfo().then(res => console.log(res))

// 获取指定 ID 的筛选器
window.DashboardController.getFiltersInfo(["filter-4vmv0-89c75"]).then(res => console.log(res))
```

---

### `setFiltersValues(filters)` — 批量设置筛选器

**参数**：

```typescript
filters: Array<{
  id: string;           // 筛选器的 componentId（即 getFiltersInfo 返回的 key 字段）
  userInput: FilterUserInput;  // 见下方各类型格式说明
}>
```

**返回值**：

```json
{ "code": 0, "message": "操作成功", "data": null }
```

**已验证调用示例**：

```javascript
// 设置日期范围筛选器为固定日期区间
window.DashboardController.setFiltersValues([
  {
    "id": "filter-4vmv0-89c75",
    "userInput": {
      "value": ["2026-01-09", "2026-01-30"]
    }
  }
]).then(res => console.log(res))

// 同时修改多个筛选器
window.DashboardController.setFiltersValues([
  {
    "id": "filter-date-xxx",
    "userInput": {
      "value": [
        { "offset": -7, "granularity": "DAY", "type": "OFFSET" },
        { "offset": -1, "granularity": "DAY", "type": "OFFSET" }
      ],
      "granularity": "DAY"
    }
  },
  {
    "id": "filter-enum-yyy",
    "userInput": {
      "value": ["IOS"],
      "isEmpty": false,
      "isNoFilter": false,
      "isSelectDummyAll": false,
      "selectAllFlag": false
    }
  }
]).then(res => console.log(res))
```

> 设置成功后建议用 `getFiltersInfo` 验证值已生效。
>
> 全选时必须把 `options` 中每一个可选值都写入 `value`，不能只依赖空数组、`isNoFilter` 或虚拟“全部”标记。全选后要核对已选数量与可选项数量一致，再执行查询。

---

#### FilterUserInput 格式（按筛选器类型）

> ⚠️ **格式说明**：以下是 `setFiltersValues` 内部 API 的 `userInput` 格式，与 JS SDK 嵌入方案中的 `FilterProtocol`（见 https://km.sankuai.com/collabpage/2749600978 第 3.2 节）是两套不同协议，请勿混用。

---

##### 日期筛选器（Date）

```typescript
interface DateFilterUserInput {
  // 固定日期（字符串）或相对偏移（对象）
  value: string | { offset: number; granularity: 'DAY' | 'WEEK' | 'MONTH' | 'QUARTER' | 'YEAR'; type: 'OFFSET' }
  granularity: 'DAY' | 'WEEK' | 'MONTH' | 'QUARTER' | 'YEAR'
}
```

**示例：固定日期**

```javascript
{ "value": "2024-01-15", "granularity": "DAY" }
```

**示例：相对偏移（3 天前）**

```javascript
{ "value": { "offset": -3, "granularity": "DAY", "type": "OFFSET" }, "granularity": "DAY" }
```

---

##### 日期范围筛选器（DateRange）

```typescript
interface DateRangeFilterUserInput {
  // 固定日期数组 或 偏移对象数组；[0] 为起始，[1] 为结束
  value: [string, string] | [DateOffset, DateOffset]
  granularity: 'DAY' | 'WEEK' | 'MONTH' | 'QUARTER' | 'YEAR'
}
type DateOffset = { offset: number; granularity: string; type: 'OFFSET' }
```

**常用时间范围与 offset 对照表**：

| 用户说的时间范围 | 起始 offset | 结束 offset |
|----------------|------------|------------|
| 最近 7 天（不含今天） | -7 | -1 |
| 最近 14 天 | -14 | -1 |
| 最近 30 天 | -30 | -1 |
| 最近 90 天 | -90 | -1 |
| 昨天 | -1 | -1 |
| 今天 | 0 | 0 |

**示例：固定日期区间（线上验收通过）**

```javascript
{
  "value": ["2026-01-09", "2026-01-30"]
}
```

**示例：相对偏移（最近 7 天）**

```javascript
{
  "value": [
    { "offset": -7, "granularity": "DAY", "type": "OFFSET" },
    { "offset": -1, "granularity": "DAY", "type": "OFFSET" }
  ],
  "granularity": "DAY"
}
```

---

##### 时间筛选器（Time）

```typescript
interface TimeFilterUserInput {
  // 固定时间字符串（"YYYY-MM-DD HH:mm:ss"）或时间偏移对象
  value: string | TimeOffset
}
interface TimeOffset {
  dateGranularity: 'DAY' | 'WEEK' | 'MONTH' | 'QUARTER' | 'YEAR'
  dateOffsetValue: number
  dateDirection: 'FORWARD' | 'BACKWARD'
  timeGranularity: 'HOUR' | 'MINUTE' | 'SECOND'
  timeOffsetValue: number
  timeDirection: 'FORWARD' | 'BACKWARD'
}
```

**示例：固定时间**

```javascript
{ "value": "2024-01-15 14:30:00" }
```

**示例：相对偏移（1 小时前）**

```javascript
{
  "value": {
    "dateGranularity": "DAY", "dateOffsetValue": 0, "dateDirection": "BACKWARD",
    "timeGranularity": "HOUR", "timeOffsetValue": 1, "timeDirection": "BACKWARD"
  }
}
```

---

##### 时间范围筛选器（TimeRange）

```typescript
interface TimeRangeFilterUserInput {
  // 固定时间数组 或 偏移对象数组；[0] 为起始，[1] 为结束
  value: [string, string] | [TimeOffset, TimeOffset]
}
```

**示例**

```javascript
{ "value": ["2024-01-15 00:00:00", "2024-01-15 23:59:59"] }
```

---

##### 单选筛选器（Radio）

```typescript
interface RadioFilterUserInput {
  value: string         // 选中值（必须是 options 中存在的值）
  isEmpty: boolean      // 是否为空选择（未选任何值时为 true）
  isNoFilter: boolean   // 是否"不筛选"（相当于全部）
  isSelectDummyAll: boolean  // 是否选中虚拟"全部"选项
}
```

**示例**

```javascript
{
  "value": "已完成",
  "isEmpty": false,
  "isNoFilter": false,
  "isSelectDummyAll": false
}
```

---

##### 多选筛选器（Multiple）

```typescript
interface MultipleFilterUserInput {
  value: string[]       // 选中值数组（必须是 options 中存在的值）
  isEmpty: boolean
  isNoFilter: boolean
  isSelectDummyAll: boolean
  selectAllFlag: boolean  // 是否全选
}
```

**示例**

```javascript
{
  "value": ["魔数2.0-仪表板", "AI-分析Agent"],
  "isEmpty": false,
  "isNoFilter": false,
  "isSelectDummyAll": false,
  "selectAllFlag": false
}
```

---

##### 树筛选器（Tree）

```typescript
interface TreeFilterUserInput {
  // 注意：全选时 value 也需要填入全部可选项
  value: string[]
  isEmpty: boolean
  isNoFilter: boolean
  selectAllFlag: boolean
}
```

**示例**

```javascript
{
  "value": ["公司-美团-食杂零售-小象事业部"],
  "isEmpty": false,
  "isNoFilter": false,
  "selectAllFlag": false
}
```

---

##### 级联单选筛选器（CascadeRadio）

> `userInput` 是**数组**，每个元素对应一个级联层级。

```typescript
type CascadeRadioFilterUserInput = Array<{
  value: string
  isEmpty: boolean
  isNoFilter: boolean
  isSelectDummyAll: boolean
}>
```

**示例**

```javascript
[
  { "value": "北京市", "isEmpty": false, "isNoFilter": false, "isSelectDummyAll": false },
  { "value": "朝阳区", "isEmpty": false, "isNoFilter": false, "isSelectDummyAll": false }
]
```

---

##### 级联多选筛选器（CascadeMultiple）

> `userInput` 是**数组**，每个元素对应一个级联层级。

```typescript
type CascadeMultipleFilterUserInput = Array<{
  value: string[]
  isEmpty: boolean
  isNoFilter: boolean
  isSelectDummyAll: boolean
  selectAllFlag: boolean
}>
```

**示例**

```javascript
[
  { "value": ["电子产品", "家居用品"], "isEmpty": false, "isNoFilter": false, "isSelectDummyAll": false, "selectAllFlag": false },
  { "value": ["手机", "电脑"], "isEmpty": false, "isNoFilter": false, "isSelectDummyAll": false, "selectAllFlag": false }
]
```

---

##### 数值筛选器（Numerical）

```typescript
interface NumericalFilterUserInput {
  value:
    | { singleValue: string }                                              // 单值（EQ / GT / LT 等）
    | { minValue: string; minType: '<' | '≤'; maxValue: string; maxType: '<' | '≤' }  // 范围（RANGE）
  filterType: 'EQ' | 'NE' | 'GT' | 'GE' | 'LT' | 'LE' | 'RANGE' | 'OUT_RANGE' | 'EMPTY' | 'NOT_EMPTY'
}
```

**示例：等于**

```javascript
{ "value": { "singleValue": "1000" }, "filterType": "EQ" }
```

**示例：范围（100 ≤ x < 1000）**

```javascript
{
  "value": { "minValue": "100", "minType": "≤", "maxValue": "1000", "maxType": "<" },
  "filterType": "RANGE"
}
```

---

##### 文本条件筛选器（Input）

```typescript
interface InputFilterUserInput {
  value: string
  filterType: 'CONTAIN' | 'STARTS_WITH' | 'ENDS_WITH' | 'EQ' | 'NE' | 'EMPTY' | 'NOT_EMPTY'
}
```

**示例**

```javascript
{ "value": "手机", "filterType": "CONTAIN" }
```

---

##### 组织筛选器（Org）

```typescript
interface OrgFilterUserInput {
  // 二维数组：每个内层数组代表一条从根到叶的组织路径
  value: Array<Array<{
    value: string       // 组织节点值
    orgLineId: string   // 组织线 ID
    orgNodeType: string // 组织节点类型
  }>>
}
```

**示例**

```javascript
{
  "value": [
    [
      { "value": "dept-001", "orgLineId": "line-1", "orgNodeType": "department" },
      { "value": "team-001", "orgLineId": "line-1", "orgNodeType": "team" }
    ]
  ]
}
```

---

##### 时区筛选器（TimeZone）

```typescript
interface TimeZoneFilterUserInput {
  value: string  // IANA 时区标识，如 "Asia/Shanghai"
}
```

**示例**

```javascript
{ "value": "Asia/Shanghai" }
```

---

### `getFieldPools(chartId)` — 获取图表指标维度池

> 获取指定图表可用的指标/维度列表，以及当前选中（显示）状态。适用于需要了解图表当前展示了哪些字段、以及有哪些字段可被选中的场景。

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `chartId` | `string` | ✅ | 图表的 `componentId`（来自 `getComponents` 返回的 `componentId`，格式如 `dashboard-chart-container-xxx`） |

**返回值**：

```json
{
  "code": 0,
  "message": "",
  "data": {
    "dimensions": [
      { "fieldId": "date", "name": "日期", "selected": true },
      { "fieldId": "province", "name": "省份", "selected": false }
    ],
    "metrics": [
      { "fieldId": "gmv", "name": "GMV", "selected": true },
      { "fieldId": "order_cnt", "name": "订单量", "selected": true }
    ]
  }
}
```

> - `dimensions`：维度字段列表
> - `metrics`：指标字段列表
> - `selected: true`：当前图表中已选中（展示）的字段；`selected: false`：未选中（隐藏）的字段
> - `fieldId`：字段标识符，在 `updateFieldPools` 中使用

**已验证调用示例**：

```javascript
// 先获取图表的 componentId
window.DashboardController.getComponents().then(res => {
  const chart = res.data.find(c => c.componentName === "目标图表名称")
  return window.DashboardController.getFieldPools(chart.componentId)
}).then(res => console.log(res))

// 直接调用（已知 componentId）
window.DashboardController.getFieldPools("dashboard-chart-container-u2ytv-e4956").then(res => console.log(res))
```

---

### `updateFieldPools(chartId, options)` — 修改图表指标维度池

> 修改指定图表的指标维度池选中值，用于隐藏或显示特定的维度/指标字段。调用后图表将重新渲染。

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `chartId` | `string` | ✅ | 图表的 `componentId`（来自 `getComponents` 返回的 `componentId`，格式如 `dashboard-chart-container-xxx`） |
| `options` | `object` | ✅ | 选中/取消选中的字段配置，见下方说明 |

**options 参数格式**：

```typescript
interface UpdateFieldPoolsOptions {
  selectedDimensions?: string[]    // 设为选中状态的维度 fieldId 列表
  unselectedDimensions?: string[]  // 设为取消选中状态的维度 fieldId 列表
  selectedMetrics?: string[]       // 设为选中状态的指标 fieldId 列表
  unselectedMetrics?: string[]     // 设为取消选中状态的指标 fieldId 列表
}
```

> 四个字段均为可选，只传需要修改的字段即可。未传入的字段保持原有状态不变。

**返回值**：

```json
{ "code": 0, "message": "操作成功", "data": null }
```

**已验证调用示例**：

```javascript
// 取消选中维度 "date"
window.DashboardController.updateFieldPools("dashboard-chart-container-u2ytv-e4956", {
  unselectedDimensions: ["date"]
}).then(res => console.log(res))

// 同时修改维度和指标
window.DashboardController.updateFieldPools("dashboard-chart-container-u2ytv-e4956", {
  selectedDimensions: ["province"],
  unselectedDimensions: ["date"],
  selectedMetrics: ["gmv"],
  unselectedMetrics: ["order_cnt"]
}).then(res => console.log(res))
```

> 修改后可调用 `getFieldPools` 验证选中状态已生效，再调用 `executeQueryAndGetCHNResult` 触发查询获取新数据。

---

### `getChartFilters(chartIds)` — 获取图表内嵌筛选器

> 获取分析板中图表内嵌（图表级）筛选器的当前值和可选项。与 `getFiltersInfo`（获取仪表板级筛选器）不同，本方法专门用于获取嵌入在图表内部的筛选器。

> 💡 如需**修改**图表内嵌筛选器，使用配对方法 `setChartFilters`，而不是 `setFiltersValues`。

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `chartIds` | `string[]` | ✅ | 图表 `componentId` 数组（来自 `getComponents` 返回的 `componentId`，如 `dashboard-chart-container-xxx`） |

**返回值**：

```json
{
  "code": 0,
  "message": "",
  "data": [
    {
      "chartId": "dashboard-chart-container-xxx",
      "filters": [
        {
          "key": "chart-filter-xxx",
          "name": "时间筛选器",
          "filterType": "time",
          "filterValue": [
            { "offset": -7, "granularity": "DAY", "type": "OFFSET" },
            { "offset": -1, "granularity": "DAY", "type": "OFFSET" }
          ],
          "options": []
        }
      ]
    }
  ]
}
```

> 返回结构与 `getFiltersInfo` 相同，字段含义一致。

**已验证调用示例**：

```javascript
// 获取单个图表的内嵌筛选器
window.DashboardController.getChartFilters(["dashboard-chart-container-1ciqj-85534"])
  .then(res => console.log(res))

// 批量获取多个图表的内嵌筛选器
window.DashboardController.getChartFilters([
  "dashboard-chart-container-1ciqj-85534",
  "dashboard-chart-container-oxmf3-df06d"
]).then(res => console.log(res))
```

---

### `setChartFilters(configs)` — 设置图表内嵌筛选器

> 设置分析板中图表内嵌（图表级）筛选器的值。与 `getChartFilters` 配对使用。

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `configs` | `Array` | ✅ | 图表筛选器配置数组，每项对应一个图表 |

**configs 格式**：

```typescript
type SetChartFiltersConfig = Array<{
  id: string         // 图表 componentId（dashboard-chart-container-xxx 或 iframe-chart-xxx）
  filters: Array<{
    type: 'DATERANGE' | 'NUMERICAL' | 'ORDINARY'  // 筛选器类型
    id: string       // 筛选器字段 ID
    name: string     // 筛选器名称
    userInput: object  // 见下方各类型格式说明
    queryConfig?: object  // 可选，时间类型时可指定 timeUnitType
  }>
}>
```

**userInput 格式（按筛选器类型）**：

**日期范围（DATERANGE）**
```javascript
{
  "filterType": "BETWEEN_AND",
  "relationType": "LEAF",
  "value": [
    { "direction": "FORWARD", "offsetValue": 1, "granularity": "DAY" },  // 起始
    { "direction": "FORWARD", "offsetValue": 20, "granularity": "DAY" }  // 结束
  ]
}
// queryConfig: { "timeUnitType": "DAY" }
```

**数值（NUMERICAL）**
```javascript
{
  "filterType": "RANGE",
  "relationType": "LEAF",
  "value": [
    { "symbol": ">=", "value": 0 },
    { "symbol": "<=", "value": 20 }
  ]
}
```

**下拉/枚举（ORDINARY）**
```javascript
// 包含选项
{
  "filterType": "INCLUDE",
  "relationType": "LEAF",
  "value": [{ "label": "999", "value": "999" }],
  "isEmpty": false,
  "isNoFilter": false,
  "isSelectDummyAll": false,
  "sort": {}
}
// 不过滤（全部）
{
  "filterType": "INCLUDE",
  "relationType": "LEAF",
  "value": [],
  "isEmpty": false,
  "isNoFilter": true,
  "isSelectDummyAll": false,
  "sort": {}
}
```

**返回值**：

```json
{ "code": 0, "message": "操作成功", "data": null }
```

**已验证调用示例**：

```javascript
// 设置日期范围筛选器
DashboardController.setChartFilters([{
  "id": "iframe-chart-1",
  "filters": [{
    "type": "DATERANGE",
    "id": "datekey",
    "name": "日期",
    "userInput": {
      "filterType": "BETWEEN_AND",
      "relationType": "LEAF",
      "value": [
        { "direction": "FORWARD", "offsetValue": 1, "granularity": "DAY" },
        { "direction": "FORWARD", "offsetValue": 20, "granularity": "DAY" }
      ]
    },
    "queryConfig": { "timeUnitType": "DAY" }
  }]
}])

// 设置下拉筛选器（选中指定值）
DashboardController.setChartFilters([{
  "id": "iframe-chart-1",
  "filters": [{
    "type": "ORDINARY",
    "id": "warzone_id",
    "name": "战区ID",
    "userInput": {
      "filterType": "INCLUDE",
      "relationType": "LEAF",
      "value": [{ "label": "999", "value": "999" }],
      "isEmpty": false,
      "isNoFilter": false,
      "isSelectDummyAll": false,
      "sort": {}
    }
  }]
}])
```

---

### `getCurrentUserOrgTree(options)` — 获取用户有权限的组织架构树

> 获取用户有权限的组织架构树结构，用于 **Org 类型筛选器**的取值和设置。
>
> ⚠️ **适用场景**：当仪表板包含组织架构筛选器（`filterType: 'Org'`）时，需先调用此接口获取可选节点，再通过 `setFiltersValues` 设置选中值。

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `filterId` | `string` | ✅ | 组织架构筛选器的 componentId |

**返回值**：Promise，resolve 后返回组织架构树对象：

```typescript
{
  code: 0,
  data: {
    bizId: number,           // 业务线ID
    filterId: string,        // 筛选器ID
    filterName: string,      // 筛选器名称，如"组织架构"
    leafType: string,        // 叶节点类型，如"ORG"
    orgLines: Array<{        // 组织线列表
      orgLineId: string,
      orgLineName: string
    }>,
    originDims: number[],    // 原始维度ID数组
    paths: string[][],       // 节点路径数组，每个路径是从根到叶的ID链
    stats: {
      nodeCount: number,     // 节点总数
      leafCount: number,     // 叶节点数
      depth: number,         // 树深度
      truncated: boolean     // 是否被截断（数据过大时）
    },
    tree: TreeNode[]         // 树形结构，递归包含 children
  }
}

interface TreeNode {
  value: string,             // 节点ID
  label: string,             // 节点名称
  orgNodeType: number,       // 节点类型
  subOrgNodeType: string,    // 子节点类型
  isLeaf: boolean,           // 是否叶节点
  hasPermission: boolean,    // 用户是否有权限
  children?: TreeNode[]      // 子节点
}
```

**调用示例**：

```javascript
// 获取组织架构筛选器的可选树
window.DashboardController.getCurrentUserOrgTree({
  filterId: 'dashboard-filter-a8jdl-f67bf'
}).then(res => {
  console.log('组织架构树:', res.data.tree)
  console.log('可选路径:', res.data.paths)
})
```

**配合 `setFiltersValues` 设置组织架构筛选器**：

获取到组织架构树后，通过 `setFiltersValues` 设置选中的节点路径：

```javascript
// 设置组织架构筛选器的选中节点
// paths 中的每个元素是一个路径数组，如 [['152769'], ['114221', '子节点ID']]
window.DashboardController.setFiltersValues([{
  id: 'dashboard-filter-a8jdl-f67bf',
  userInput: {
    orgFilterInfo: [{
      values: [
        ['152769'],      // 选中节点1
        ['114221'],      // 选中节点2
        ['1022105'],     // 选中节点3
      ]
    }]
  }
}])
```

> 💡 **使用流程**：
> 1. 先通过 `getFiltersInfo()` 找到 `filterType: 'org'` 的筛选器ID
> 2. 调用 `getCurrentUserOrgTree({ filterId })` 获取可选树
> 3. 从返回的 `paths` 或 `tree` 中选择要设置的节点
> 4. 调用 `setFiltersValues` 配合 `orgFilterInfo` 格式设置选中值

---

### `executeQueryAndGetCHNResult(params)` — 执行查询取数

**参数**（数组格式）：

| 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `params[0]` | `string` | ✅ | 图表组件 ID（`getComponents` 返回的 `componentId`） |
| `params[1]` | `object` | 否 | 选项对象，如 `{ force: true }` 强制重新查询 |

> `force: true` 仅在以下情况使用：① 用户明确要求"强制刷新"；② 修改筛选器后默认查询数据未更新。**绝大多数情况不需要传**。

**返回值**：

```json
{
  "code": 0,
  "message": "",
  "data": {
    "columns": ["下单省份", "订单GMV"],
    "data": [
      ["广东省", "38564.22"],
      ["上海", "67748.04"],
      ["北京", "38316.12"]
    ],
    "filters": {}
  }
}
```

> - `data.columns`：中文列名数组
> - `data.data`：二维数组，每行一条记录，顺序与 `columns` 一致
> - `data.filters`：本次查询实际使用的筛选条件快照（含时间范围的具体日期）
> - 数据上限：**20,000 行**；超出时自动截断
> - 用户要求查看或总结图表数据时，直接使用本接口返回的 `data.columns` 和 `data.data`；不要调用 `executeDownload`

**已验证调用示例**：

```javascript
// 默认查询（推荐）
window.DashboardController.executeQueryAndGetCHNResult(["dashboard-chart-container-oxmf3-df06d"])
  .then(res => console.log(res))

// 强制重新查询（仅必要时使用）
window.DashboardController.executeQueryAndGetCHNResult(["dashboard-chart-container-oxmf3-df06d"], { force: true })
  .then(res => console.log(res))
```

---

### `executeDownload(componentId, options?)` — 获取数据下载链接

> ⚠️ **注意**：部分仪表板可能暂不支持此功能，调用后返回 `undefined`。
> 调用前**必须先调用** `executeQueryAndGetCHNResult`，否则报错 `"请先查询数据"`。

**参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `componentId` | `string` | ✅ | - | 图表组件 ID（`getComponents` 返回的 `componentId`） |
| `options.fileType` | `'CSV' \| 'XLSX'` | ❌ | `'CSV'` | 下载文件格式 |
| `options.useDataFormat` | `boolean` | ❌ | `false` | `true`=展示格式（数值带千分位等），`false`=原始格式 |
| `options.tableType` | `'crosstab' \| 'raw'` | ❌ | `'crosstab'` | 表格类型：交叉表或原始表 |

**返回值**：

```json
{
  "code": 0,
  "message": "",
  "data": "http://wenshu-s3.sankuai.com/.../文件名.csv?签名参数"
}
```

> - `data`：文枢 S3 文件下载链接（含 `Expires` 有效期时间戳，需尽快下载）
> - 文件存储路径前缀：CSV 为 `/mtbi-file-csv/`，Excel 为 `/mtbi-file-excel/`
> - 暂不支持时：返回 `undefined`（而非报错），需提前检查

**指数退避重试策略**：

> 该接口由服务端异步生成文件，数据量大时可能未立即就绪而超时。需按以下策略重试：

| 参数 | 值 |
|------|-----|
| 单次调用超时 | 30 秒 |
| 等待间隔序列 | 15s → 30s → 60s → 120s → 120s → ...（120s 封顶） |
| 总等待上限 | 约 10 分钟（含调用时间 + 间隔时间） |
| 累计等待达 5 分钟时 | 提醒用户最长还需约 5 分钟 |

**不可重试的错误**（立即终止）：
- 返回 `undefined` → 该仪表板暂不支持此功能，告知用户
- `code !== 0` 且 message 含 `"请先查询数据"` → 需先调用 `executeQueryAndGetCHNResult`

**可重试的错误**：调用超时、网络错误、其他 `code !== 0` 的服务端异常

**已验证调用示例**：

```javascript
// 完整调用流程（先查询，再获取下载链接）
await window.DashboardController.executeQueryAndGetCHNResult(["dashboard-chart-container-oxmf3-df06d"])
const result = await window.DashboardController.executeDownload(
  "dashboard-chart-container-oxmf3-df06d",
  { fileType: "CSV", useDataFormat: false, tableType: "crosstab" }
)
console.log(result.data)  // http://wenshu-s3.sankuai.com/.../文件.csv?签名

// 检查是否支持 executeDownload
const isSupported = typeof window.DashboardController.executeDownload === 'function'
```

**功能支持验证结果**：

| Dashboard ID | 支持状态 | 结果 |
|--------------|----------|------|
| 250639 | ✅ 支持 | 可用 |
| 249730 | ❌ 暂不支持 | 返回 `undefined` |

---

### `waitForEngineReady()` — 等待渲染引擎就绪

> 需求文档未提及，实测发现。
>
> ⚠️ **通常无需主动调用**：通过 `waitforfunction` 确认 `window.DashboardController !== undefined` 后，可直接调用各接口。
> 若 `executeQueryAndGetCHNResult` 返回 `code=0` 但 `data` 为空，原因通常是页面未完成渲染，此时可尝试调用此方法等待就绪后重试。

**参数**：无

**返回值**：Promise，resolve 后表示引擎就绪。

**调用示例**：

```javascript
window.DashboardController.waitForEngineReady().then(() => {
  window.DashboardController.executeQueryAndGetCHNResult(["chart-xxx"])
    .then(res => console.log(res))
})
```

---

## 注意事项

1. **必须使用专用页面**：`/v2/dashboard/dashboard-controller?dashboardId={id}`，普通查看页 `/v2/dashboard/{id}` **不会挂载** DashboardController
2. **host 不要硬编码**：从用户提供的 URL 中读取 host（bi.keetapp.com / mdbi.bi.st.keetapp.com 等），保持原 host 不变
3. **挂载时机**：页面加载后数秒内挂载，建议用 `waitforfunction` 等待 `window.DashboardController !== undefined` 后再调用，无需额外 sleep
4. **分析板限制**：分析板组件的筛选器不支持 `setFiltersValues` 修改值
5. **查询结果为空**：`executeQueryAndGetCHNResult` 返回 `code=0` 但 `data` 为空或无数据，原因：① 页面未完成渲染，调用 `waitForEngineReady()` 等待后重试；② 极少数特殊渲染组件不支持取数，判断依据是实际调用后 `data` 仍为空
6. **不能用 ID 前缀判断是否支持取数**：`dashboard-chart-container-` 是绝大多数普通 chart 的标准 ID 前缀，绝大多数都支持取数
7. **`getFiltersInfo` 与 `setFiltersValues` 的 ID 映射**：`getFiltersInfo` 返回对象的 `key` 字段即为筛选器 componentId，`setFiltersValues` 的 `id` 参数传此值
8. **严禁对专用页面截图**：该页面对用户呈现为空白页，截图只会造成困惑
9. **`executeDownload` 支持限制**：部分仪表板可能暂不支持此功能，调用前建议检查 `typeof DashboardController.executeDownload === 'function'`；不支持时返回 `undefined` 而非报错。**返回 `undefined` 不可重试**
10. **`executeDownload` 必须先查询**：调用 `executeDownload` 前必须先完成 `executeQueryAndGetCHNResult`，否则返回错误 `"请先查询数据"`。**此错误不可重试**，需先触发查询
11. **`executeDownload` 指数退避重试**：该接口可能因服务端文件生成未就绪而超时，需按指数退避重试（间隔 15s→30s→60s→120s，120s 封顶，总上限约 10 分钟）。累计等待达 5 分钟时需提醒用户
12. **`getFieldPools` / `updateFieldPools` 的 chartId 参数**：传入的是图表的 `componentId`（格式如 `dashboard-chart-container-xxx`），直接从 `getComponents()` 返回的 `componentId` 字段获取
13. **图表内嵌筛选器读写分离**：`getChartFilters` 读取图表内嵌筛选器；`setChartFilters` 修改图表内嵌筛选器。两者均**不能**用 `setFiltersValues`（仅适用于仪表板级筛选器）
14. **组织架构筛选器**：Org 类型筛选器需先用 `getCurrentUserOrgTree({ filterId })` 获取可选树，再用 `setFiltersValues` 配合 `orgFilterInfo` 格式设置。`orgFilterInfo.values` 是节点路径数组，每个路径为 `[节点ID]` 或 `[父节点ID, 子节点ID, ...]`
