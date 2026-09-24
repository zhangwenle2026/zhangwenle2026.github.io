---
name: br-query
description: "XBR 看板数据获取技能。用户提供看板 ID 或 URL，本技能返回该看板数据的文枢下载链接（wenshuUrl）。【前置要求】必须已通过 npm install -g @datafe/br-cli --registry=http://r.npm.sankuai.com 安装 br-cli，未安装时先执行该命令再继续。安装完成后执行 br login 登录，登录成功后再执行后续命令。【环境自动识别】根据用户传递的看板 URL 自动识别环境并执行 br env set 切换到对应环境。【维度筛选器】支持通过 --common-filters-json 参数按维度值过滤数据。先用 br component list 查看筛选器和关联组件，再用 br dataset dim-values 检索筛选器值，最后用 --common-filters-json 传递筛选参数。【路由规则】1. 用户未描述具体组件/Tab → 直接用 --all-components 导出全看板；2. 用户描述了具体组件或 Tab（如「交叉表」「第二个 Tab」「指标卡」）→ 先 br component list 获取组件列表，找到匹配的 resourceId，再单独导出该组件。【时间规则】用户未指定时间时使用看板默认日期；指定时间则按指定范围查询。触发词：BR取数、BR数据、XBR数据、XBR看板数据、XBR取数、帮我拿XBR数据、导出看板、获取XBR看板数据、给我XBR数据、XBR数据下载链接、wenshuUrl、文枢链接。"
tags: br,xbr,数据,看板
visibility: public
---

# XBR 看板数据获取技能

用户提供看板 ID 或 URL，本技能自动获取数据并返回**文枢下载链接**。

---

## ⚠️ 前置：安装并登录

**执行任何命令前，必须完成以下两步，缺一不可：**

**第一步：安装 br-cli**

```bash
npm install -g  @datafe/br-cli --registry=http://r.npm.sankuai.com
```

**第二步：登录**

```bash
br login
```

完成登录后再继续执行后续命令。

---

## 环境自动识别

本技能根据用户传递的看板 URL 自动识别环境并执行环境切换，无需用户手动配置。

### 环境识别规则

| 环境 | URL 标识 | 自动执行命令 | 说明 |
|------|---------|----------|------|
| **线上环境** | `bi.keetapp.com` | `br env set keetapp` | 切换到境外线上环境。灰度参数仅在用户明确要求时设置 |
| **ST/测试环境** | `mdbi.bi.st.keetapp.com` | `br env set st` | 切换到境外测试环境。泳道参数仅在用户明确要求时设置 |

### 工作流程

1. **URL 解析**: 技能自动从用户输入的 URL 中提取主机名
2. **环境判断**: 根据主机名匹配对应环境
3. **环境切换**: 自动执行 `br env set <env>` 切换到对应环境
4. **可选参数设置**: 仅当用户明确要求时，才执行 `br env gray-set` 或 `br env swimlane-set` 等参数配置
5. **数据导出**: 在正确的环境下执行 `br component export` 命令

### 示例

```bash
# 用户输入测试环境看板（不设置泳道）
# 技能自动执行：br env set st
br component export --board https://mdbi.bi.st.keetapp.com/v2/xbr/42886 --all-components --auto-filters

# 用户输入线上环境看板（不设置灰度）
# 技能自动执行：br env set keetapp
br component export --board https://bi.keetapp.com/v2/xbr/33388 --all-components --auto-filters

# 用户要求"开启灰度查询"时
# 技能执行：br env set keetapp && br env gray-set on
br component export --board https://bi.keetapp.com/v2/xbr/33388 --all-components --auto-filters
```

---

## 执行路由

### 情况一：用户未描述具体组件

直接导出全看板所有组件：

```bash
br component export --board <boardId> --all-components --auto-filters
```

### 情况二：用户描述了具体组件或 Tab

先获取看板组件列表，找到匹配的 resourceId，再单独导出：

```bash
# Step 1：获取组件列表
br component list --board <boardId>

# Step 2：根据列表找到目标组件的 resourceId，导出该组件
br component export --board <boardId> --component <resourceId> --auto-filters
```

`br component list` 返回结构示例：
```
Tab: 概览
  [TABLE]  132239  表格1
  [CROSS]  132238  交叉表1
  [PANEL]  132520  指标卡1
```

根据用户描述（组件名称、类型、Tab 名）匹配对应 resourceId。

---

## 命令参数

| 参数 | 说明 |
|------|------|
| `--board <id\|url>` | 看板 ID 或完整 URL，如 `33388` 或 `https://bi.keetapp.com/v2/xbr/33388`（必填） |
| `--all-components` | 导出看板所有表格/指标卡组件（TABLE/CROSS/DETAIL/PANEL） |
| `--auto-filters` | 自动应用看板筛选器的默认值。BASE_DATE 筛选器使用 defaultValues 或系统默认（T-1，前一天）；COMMON 筛选器使用 defaultValues（如果存在）。与 `--common-filters-json` 一起使用时，用户指定的值优先级更高 |
| `--date-start <date>` | 开始日期，格式 YYYY-MM-DD（可选，不传则使用 BASE_DATE 筛选器的 defaultValues 或系统默认 T-1） |
| `--date-end <date>` | 结束日期，格式 YYYY-MM-DD（可选，不传则使用 BASE_DATE 筛选器的 defaultValues 或系统默认 T-1） |
| `--max-rows <n>` | 最大返回行数，默认 5000（可选） |
| `--common-filters-json <json>` | 维度筛选器参数，用于按维度值过滤数据。用户指定的值会完全覆盖看板中的默认值（可选） |

---

## ⚠️ 时间基期 vs 数据基期

**重要概念区分**（影响时间列查询）：

- **时间基期（BASE_DATE 筛选器）**：用户选择的查询日期范围
    - 默认值：T-1（前一天）
    - 通过 `--date-start`/`--date-end` 覆盖
    - 在 `--auto-filters` 模式下自动应用 defaultValues
    - 作用：作为 SQL WHERE 条件，过滤查询数据


## 维度筛选器（COMMON Filters）

看板中可能包含维度筛选器（kind=2），用于按维度值过滤数据。本技能支持通过 `--common-filters-json` 参数传递维度筛选器。

### 快速参考

```bash
# Step 1：查看看板中的筛选器和关联组件
br component list --board <id>

# Step 2：使用筛选器导出数据
br component export --board <id> --all-components \
  --common-filters-json '[{"name":"筛选器名","values":["值1","值2"]}]' \
  --auto-filters
```

### 识别维度筛选器

在 `br component list --board <id>` 的输出中查找：

- **globalFilters** 中 `kind: 2` 的筛选器为维度筛选器
- 筛选器名称对应 `filterName` 字段
- 关联组件信息在 **relations** 数组中（masterId = 筛选器 ID，slaveId = 组件 nodeKey）


### 传递筛选器参数

**方案 1：单个筛选器，单个值**

```bash
br component export --board 33388 --all-components \
  --common-filters-json '[{"name":"是否命中缓存","values":["0"]}]' \
  --auto-filters
```

**方案 2：单个筛选器，多个值（OR 关系）**

```bash
br component export --board 33388 --all-components \
  --common-filters-json '[{"name":"是否命中缓存","values":["0","1"]}]' \
  --auto-filters
```

相当于：`是否命中缓存 = "0" OR 是否命中缓存 = "1"`

**方案 3：多个筛选器（AND 关系）**

```bash
br component export --board 33388 --all-components \
  --common-filters-json '[
    {"name":"是否命中缓存","values":["0","1"]},
    {"name":"job状态","values":["FINISHED"]}
  ]' \
  --auto-filters
```

相当于：`(是否命中缓存 = "0" OR "1") AND job状态 = "FINISHED"`

### 常见问题

**Q：如何查看筛选器与哪些组件关联？**

```bash
br component list --board <id>
# 在 relations 中查找 masterId 为目标筛选器的记录
# 每条记录的 slaveId 就是关联的组件 nodeKey
```

**Q：为什么使用筛选器后查询失败？**

常见原因：
1. 筛选器名称与看板配置不一致（注意大小写和空格）
2. 筛选器与组件无关联（检查 relations 中是否存在关联）
3. 筛选器值错误（使用 `br dataset dim-values` 获取正确的枚举值）

**Q：多个筛选器值和多个筛选器的逻辑关系？**

- 单筛选器多值 = OR 关系：`values: ["0","1"]` 相当于 `value = "0" OR value = "1"`
- 多筛选器 = AND 关系：多个筛选器对象在 JSON 数组中相当于 AND 连接

---

## 示例

```bash
# 获取看板默认日期的数据（用户未指定时间时）
br component export --board 33388 --all-components --auto-filters

# 通过完整 URL 指定看板
br component export --board https://bi.keetapp.com/v2/xbr/33388 --all-components --auto-filters

# 指定时间范围
br component export --board 33388 --all-components --auto-filters \
  --date-start 2026-01-01 --date-end 2026-03-31
```

执行完成后，每个组件返回一个**文枢链接下载链接（wenshuUrl）**，将链接汇总展示给用户。

---

##  登录命令异常时 当登录出现异常时 检测如果是catclaw环境 可按以下步骤检查 SSO 环境
step 0 - CatClaw 沙箱环境判断（满足任一：环境变量 SANDBOX_ID 存在 / hostname 以 sandbox- 开头 / 存在 KUBERNETES_SERVICE_HOST 环境变量）
Step 1 — 检查 moa-ciba-login-online 进程是否存在及运行账户（catclaw/root）。

Step 2 — 检查 ~/.openclaw/sso 目录下 auth_info 和 agent_info 配置文件是否存在。

Step 3 — 检查 /app/skills/mtsso-skills-official 预装 Skill 目录是否存在。

Step 4 — 通过 MOA 日志或 npx mtsso-moa-feature-probe 确认 MOA 在线状态。

Step 5 — 查看 ~/.local/share/SSO/ 日志定位具体错误。

---

## 相关能力：嵌入学城

如果用户需要**将 BR 看板嵌入学城文档**（而非取数），使用 `br board share` 命令生成嵌入链接：

```bash
# 整个 BR 看板（+ 绑定学城日期控件）
br board share --board <id> --bind-date

# 嵌入特定 Tab
br board share --board <id> --tabs "Tab名称"

# 嵌入特定组件
br board share --board <id> --tabs "Tab名称/组件名称"
```

输出为原始链接，可直接粘贴到学城文档的「魔数2.0」三方组件中。

**常用选项：**
- `--auth-sync`：跟随学城权限（有学城文档权限即可查看）
- `--no-title`：隐藏看板标题
- `--style flat`：平铺所有图表（默认 `tab` 页签叠放）
- `--bind-date`：将 BASE_DATE 筛选器绑定到学城日期控件

- 使用 `br env get` 可一次性查看当前环境、灰度和泳道的全部状态
