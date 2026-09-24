# Dashboard 元信息获取（MCP 调用）

## 概述

在进入具体取数流程前，通过 MCP Server 的 `keeta_mtbi_dashboard_meta_info` 工具获取仪表板元信息，为后续过滤和取数提供基础数据。

> ⚠️ **重要提示**：元信息获取失败**不影响后续流程正常进行**，若调用失败，直接跳过本步骤，继续执行后续取数流程。

---

## 步骤 1：解析 dashboardId

从用户提供的 URL 中提取 `dashboardId`：

| URL 格式 | dashboardId 提取规则 |
|----------|---------------------|
| `bi.keetapp.com/v2/dashboard/12345` | 取路径最后一段：`12345` |
| `bi.keetapp.com/v2/dashboard/12345?xxx=yyy` | 取 `?` 前的最后一段：`12345` |
| `mdbi.bi.st.keetapp.com/v2/dashboard/12345` | 同上：`12345` |

---

## 步骤 2：注册 MCP Server（通过 friday-mcp）

调用 MCP 工具前，需先通过 `friday-mcp` skill 完成换票并注册 server：

- **接入点 URL**：`http://mcphub-server.sankuai.com/mcphub-c/ed9d97d1dc8246`
- **注册后的 server 名称**：`keeta_mtbi_ai`
- **需要调用的 tool**：`keeta_mtbi_dashboard_meta_info`，参数 `dashboardId: string`

按照 `friday-mcp` skill 的流程（换票 → `mcporter config add`）完成注册，注册成功后继续步骤 3。

> 若 `friday-mcp` skill 不存在或换票失败，直接跳过本步骤（元信息获取失败不影响后续流程）。

---

## 步骤 3：调用 MCP 工具获取元信息

注册完成后，通过 `mcporter` 调用 `keeta_mtbi_dashboard_meta_info` 工具，**必须使用函数调用风格**（整条命令用单引号包裹）：

```bash
mcporter call 'keeta_mtbi_ai.keeta_mtbi_dashboard_meta_info(dashboardId: "<步骤1解析出的ID>")'
```

> 若调用返回错误，直接跳过，继续后续取数流程。

---

## 步骤 4：元信息过滤

获取元信息后，将原始 JSON 输出保存为临时文件，再调用 `filter_dashboard_meta.py` 过滤处理，输出精简的元信息并保存到 `scripts/dashboard_meta.json`，供后续取数流程使用。

```bash
# 1. 将 mcporter 原始输出写入临时文件（stdout 重定向）
mcporter call 'keeta_mtbi_ai.keeta_mtbi_dashboard_meta_info(dashboardId: "<ID>")' > /tmp/dashboard_meta_raw.json

# 2. 调用过滤脚本处理（在 keeta-data-query skill 目录下执行）
python3 scripts/filter_dashboard_meta.py --input /tmp/dashboard_meta_raw.json
```

输出的 `dashboard_meta.json` 结构：
- `dashboard`：仪表板基础信息（id、name、version、security_level）
- `tabs`：Tab 列表，每个 Tab 包含其下组件（组件名、类型、数据集、指标列表、维度列表）
- `global_filters`：全局筛选器（fid、名称、类型、关联字段 code+name）
