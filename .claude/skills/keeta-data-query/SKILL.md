---
name: keeta-data-query
description: >-
  Keeta 用户提出找数、取数、查数、看指标、查口径、做经营数据分析、找数据来源、查表、执行 SQL、查看魔数资源或读取 BI 看板数据时优先使用本 Skill。
  能力覆盖：起源标准数据集查询，包括查数据集、查指标、查维度/维值和标准出数；找 Hive 表，包括表结构、字段、ETL、指标血缘、Hive 血缘；Hive SQL 执行，包括自定义口径、异步查询、项目空间和权限处理；
  魔数资源查询，包括个人数据集指标/维度/SQL 源码和 SQL 模板列表/内容；魔数 BI 看板取数，包括 bi.keetapp.com 看板数据、截图、KPI/表格提取。
  典型业务意图：订单量、交易额、GMV、DAU、访购率、补贴率等 Keeta 境外经营指标查询；环比、同比、占比、比例、份额、结构分析、构成分析、分布分析、波动贡献、贡献度、驱动分析、拆解；
  起源数据集/指标/维度/维值查询，指标权限申请，DataMap/RAG 找表，Hive 表结构和 data lineage，魔数 BI 看板查询。
  支持地区：SA/HK/AE/QA/KW/BR/BH。跳过：非 Keeta 业务数据、国内美团数据查询。

metadata:
  skillhub.creator: "wanghao192"
  skillhub.updater: "wanghao192"
  skillhub.version: "V33"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "1821"
  skillhub.high_sensitive: "false"
---

## [MANDATORY] SKILLHUB_METRIC_REPORTER_START
执行本 Skill 的任何操作之前，必须先执行 Skill：`skill-metric-reporter`。
按照 `skill-metric-reporter` 的要求完成 `skill_start` 上报后，再去继续本 Skill 正文。
如果 `skill-metric-reporter` 不可用或执行失败，跳过上报，继续执行本 Skill 正文——不得因上报失败而阻塞审阅流程。
本 Skill 全部操作完成后，同样按照 `skill-metric-reporter` 的要求完成 `skill_end` 上报。
## [MANDATORY] SKILLHUB_METRIC_REPORTER_END

# Keeta 数据查询 Skill

> 遇到问题先查 [FAQ](references/general/faq.md)。所有详细能力说明在 [references/README.md](references/README.md)。

## 初始化

每次激活 skill 时，在 keeta-data-query Skill 根目录执行：

```bash
bash scripts/preflight.sh
export PATH="$(python3 scripts/core/paths_cli.py bin-dir):$PATH"
```

根据 preflight 输出处理：

- `CONFLICT: <skill列表>`：告知用户这些 skill 与 keeta-data-query 功能重叠、不支持 Keeta 或体验不佳，询问是否卸载。
- `DEPS_REQUIRED`：npm 依赖自动安装失败；告知用户检查 Node.js/npm/npx 环境，并按终端错误提示处理后重新执行 preflight。
- `MIS_REQUIRED`：自动获取当前用户 MIS 失败，已重试一次仍未成功；读取 `MIS_ACTION`，向用户询问他的 MIS，把 `<MIS>` 替换为用户提供的值后执行。
- `READY`：可以开始查询。

如果当前 Agent 执行 `kdata` 报 `command not found` 或找不到路径，说明软链目录没有进入当前 shell 的 `PATH`。此时在 Skill 根目录使用 `python3 scripts/kdata.py ...` 兜底；所有 `kdata <subcommand>` 命令都可替换为 `python3 scripts/kdata.py <subcommand>`。

## 强制协议

- 每次用户数据查询任务必须执行完整生命周期：首条用户输入执行 `kdata task start --input "用户原始问题"` → 每收到一条后续用户输入先执行 `kdata task input --input "用户原始问题"` → 查询命令 → `kdata task end --output "回答摘要"`。不要只记录触发本 Skill 的第一条输入。
- 回复用户后可追加反馈引导。若当前 Agent 支持交互式反馈控件，优先展示 👍 / 👎 两个反馈入口；不支持时使用文本引导：`这个结果有帮助吗？回复 👍 或 👎，有具体意见也欢迎告诉我。`
- 收到用户反馈后立即上报：👍 执行 `kdata feedback --rating 1`；👎 执行 `kdata feedback --rating -1 --comment "用户反馈内容"`。如果 `kdata` 不可用，使用 `python3 scripts/kdata.py feedback ...` 兜底。

## 查询路由

执行任何查询前，先判断用户意图能否通过低成本探查收敛：

- 表层模糊不等于必须追问。可先用数据集、指标、维度、元数据或看板结构做低成本探查。
- 如果探查后 top1 候选明显领先，直接查询，并在结果中说明采用口径和默认假设。
- 如果候选接近，或仍无法区分查数、找口径、找表、诊断、报告，先向用户确认，不要直接取数。

默认路由按优先级执行：

1. 最高优先级是能力一：起源标准数据集查询。Keeta 经营指标、指标/维度/维值查询、维度下钻、权限、环比/同比、占比/贡献度/波动贡献，以及数据源不明确的找数/取数问题，都先查起源标准数据集。
2. 第二优先级是能力三：Hive SQL 执行。仅当起源标准数据集不覆盖，或用户明确要求 SQL、自定义口径、完整 Hive 表查询时使用。
3. 使用 Hive SQL 前必须先走能力二：找 Hive 表，验证表名、字段、分区、ETL 或血缘；用户只要求找表、查字段、查指标来源时，也停留在能力二。

显式资源路由：

- 用户明确要求查魔数个人数据集或 SQL 模板时，走 `kdata dataset list/info` 或 `kdata template list/show`；这些 kdata 对外命令保持历史兼容，内部只调用 `mtcli kdata moshu ...`。
- 用户明确输入 BI 看板链接，或明确要求看板取数、看板截图、读取看板表格/KPI 时，走能力五。

## 能力索引

### 能力一：起源标准数据集查询

覆盖：查数据集列表、查指标列表/权限、查维度列表、查维值；基于起源标准数据集做标准出数、环比/同比、多维过滤；支持经营沙盘、供给大盘、用增大盘、履约大盘、访购诊断等数据集；支持分析/占比/贡献度/波动贡献/基尼系数等算子。
入口：`kdata standard datasets/measures/dims/dim-values/query`
地区：`--region` 固定枚举：SA/HK/AE/QA/KW/BR/BH。用户已明确地区（如沙特=SA）时，直接在 `kdata standard query` 使用 `--region SA`，不要额外查询 `global_region_code` 维值。
日期：日期必须使用 `yyyyMMdd` 或 `yyyyMMdd~yyyyMMdd`，例如 `20260615` 或 `20260601~20260615`。
参考：[standard_reference.md](references/standard/standard_reference.md)

### 能力二：找 Hive 表

覆盖：搜表、查字段、查分区；BI+DataMap 关键词找表、RAG 语义找表、知识库检索、ETL 代码分析；起源指标血缘、Hive 表上下游、字段血缘、常用表参考。
入口：`kdata table search/info`、`kdata meta table bi/rag/etl`、`kdata meta origin/lineage`
参考：[table_reference.md](references/hive/table_reference.md)、[meta-workflow.md](references/meta/meta-workflow.md)、[origin-lineage.md](references/meta/origin-lineage.md)、[hive-lineage.md](references/meta/hive-lineage.md)、[common_tables.md](references/hive/common_tables.md)

### 能力三：Hive SQL 执行

覆盖：同步执行、SQL 文件执行、异步提交、查状态、拉结果、项目空间、队列、权限申请链路、异步轮询上限。
入口：`kdata hive run/submit/status/result/spaces/queues`
参考：[hive_reference.md](references/hive/hive_reference.md)

### 能力四：魔数资源查询

覆盖：魔数个人数据集列表、数据集详情、指标/维度和 SQL 源码；魔数 SQL 模板列表和模板 SQL 内容。
入口：`kdata dataset list/info`、`kdata template list/show`
参考：[bi_reference.md](references/moshu/bi_reference.md)

### 能力五：魔数 BI 看板取数

覆盖：境外魔数 XBR 看板、Dashboard v2、Dashboard v1、仪表板元数据查询；支持 `bi.keetapp.com` 和 `mdbi.bi.st.keetapp.com`，通过 DashboardController / br-cli / browser-action 流程取数。
指定 Tab、图表和筛选器的请求（例如“选择某个 Tab 后，查询某个图表；筛选器选择包含/全选；并总结数据情况”）优先走 DashboardController 定向查询，直接读取接口返回结果并总结；只有用户明确要求导出、下载或文件链接时才触发下载。

路由规则：

- `{domain}/v2/xbr/{id}`：读取 [xbr.md](references/moshu/xbr.md)。
- `{domain}/v2/dashboard/{id}`：读取 [dashboard-v2.md](references/moshu/dashboard-v2.md)。
- `{domain}/dashboard/{id}`：读取 [dashboard-v1.md](references/moshu/dashboard-v1.md)。
- 用户只问仪表板结构、图表、筛选器、指标/维度定义时：读取 [dashboard-meta.md](references/moshu/dashboard-meta.md)。
- 其他 URL 格式直接拒绝，并提示支持的 XBR / Dashboard v2 / Dashboard v1 格式。

辅助脚本：`scripts/moshu/build_headers.sh`、`scripts/moshu/openclaw_bridge.py`、`scripts/moshu/fetch_dashboard_v1.py`、`scripts/moshu/fetch_with_playwright.py`。
接口参考：[dashboard-controller-api.md](references/moshu/dashboard-controller-api.md)、[moshu_dashboard_api_skill_demo.md](references/moshu/moshu_dashboard_api_skill_demo.md)、[query_dashboard_meta.md](references/moshu/query_dashboard_meta.md)、[env-check.md](references/moshu/env-check.md)
