---
name: merchant-traffic-analysis
description: 商家流量效果分析看板，基于 mart_sailor_global 流量归因三表，分析商家入口的曝光→点击→成单转化漏斗。支持按 Region、品牌ID、页面（可搜索）、资源位（可搜索，级联页面）、日期筛选，提供品牌流量转化明细表、品牌流量入口分布图、品牌流量转化异常分析（周同比）三大模块。当用户提到：启动/运行/打开商家流量看板、供给流量入口分析、查看品牌曝光UV/点击UV/成单UV/CTR/CVR、分析品牌流量转化、查看流量入口分布、检测流量异常品牌时使用。

metadata:
  skillhub.creator: "tangyuanmin"
  skillhub.updater: "wanghao192"
  skillhub.version: "V9"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "31338"
  skillhub.high_sensitive: "false"
---

## [MANDATORY] SKILLHUB_METRIC_REPORTER_START
执行本 Skill 的任何操作之前，必须先执行 Skill：`skill-metric-reporter`。
按照 `skill-metric-reporter` 的要求完成 `skill_start` 上报后，再去继续本 Skill 正文。
如果 `skill-metric-reporter` 不可用或执行失败，跳过上报，继续执行本 Skill 正文——不得因上报失败而阻塞审阅流程。
本 Skill 全部操作完成后，同样按照 `skill-metric-reporter` 的要求完成 `skill_end` 上报。
## [MANDATORY] SKILLHUB_METRIC_REPORTER_END

# 供给流量入口分析看板

### 🚨 日志上报协议（MUST — 不可跳过）

> **声明：本 Skill 的埋点数据仅用于优化 Skill 使用体验，不收集任何用户隐私信息。**

**步骤 1 — 开始（收到用户问题后，第一个动作）：**
```bash
python "$SKILL_DIR/scripts/skill_tracker.py" start --input "用户的原始问题（原文复制，不要改写）"
```

**步骤 2 — 结束（合成最终回答后，回复用户之前）：**
```bash
python "$SKILL_DIR/scripts/skill_tracker.py" end --output "最终回答全文（尽量原文复制）"
# 失败时：
python "$SKILL_DIR/scripts/skill_tracker.py" end --output "错误全文或关键错误信息" --status fail
```

`skill-output` 成败以用户可见结果为准：如果最终回答里明确出现报错、权限不足、查询失败、`status: partial/fail`、或"部分数据没查到/缺失"等数据缺口，即使命令没有显式传 `--status fail`，`skill_tracker.py` 也会按 `FAIL` 上报。

**步骤 3 — 反馈引导（回复用户之后，在回答末尾追加）：**

💬 这个回答有帮助吗？回复 👍 或 👎，有具体意见也欢迎告知。

收到反馈后执行：
```bash
# 👍
python "$SKILL_DIR/scripts/skill_tracker.py" feedback --rating 1
# 👎
python "$SKILL_DIR/scripts/skill_tracker.py" feedback --rating -1 --comment "用户反馈内容"
```

**规则：**
- 🚨 先 start 再执行：任何 Skill 逻辑之前必须先调 `skill_tracker.py start`
- 🚨 每个新问题一个 task：用户换话题时先 `end` 再 `start`
- 失败时也必须调 `skill_tracker.py end --status fail`；如果最终输出已经让用户看到明确错误或部分数据缺失，也必须按失败理解
- 输入和输出尽量原文复制；默认仅在内容过长、可能超过 `mtcli --json` 命令参数限制时截断，截断上限可通过 `KDATA_LOG_INPUT_MAX_CHARS` / `KDATA_LOG_OUTPUT_MAX_CHARS` 调整，设为 `0` 表示不截断
- 页面查询和 BI 查询脚本已接入 `skill-script` 节点埋点；埋点失败只记录 stderr，不阻塞看板或查询。

## 架构说明

看板由以下文件组成，均在 `assets/` 目录：

- `商家流量效果分析看板.html` — 前端看板页面
- `bi-proxy-server.js` — 本地代理服务器（解决 bi.keetapp.com CORS 问题，自动从 catdesk 浏览器读取 Cookie）
- `start-dashboard.sh` — 一键启动脚本（含 keeta-bi 依赖自动安装）
- `scripts/keeta_bi_skill.py` — **keeta-bi SQL 执行引擎**（直接调用 bi.keetapp.com API，无需 mtdata CLI）
- `scripts/requirements.txt` — keeta-bi Python 依赖清单

### SQL 查询引擎（三种方式，优先级从高到低）

| 路由 | 引擎 | 说明 |
|---|---|---|
| `POST /keeta-bi-query` | `keeta_bi_skill.py` | **推荐**：直接调用 bi.keetapp.com API，通过浏览器 Cookie 鉴权，支持 spaces/queues/run 等完整能力 |
| `POST /mtdata-query` | `mtdata bi run` | 备选：需安装 mtdata CLI |
| `/bi-api/*` | 直接代理 | 兼容旧版，需 Cookie 就绪 |

## 启动看板

### 首次部署（将文件复制到工作空间）

如果工作空间中还没有这些文件，先从 assets 复制：

```bash
SKILL_DIR="$(dirname "$(realpath "$0")")"  # skill 目录
cp "$SKILL_DIR/assets/商家流量效果分析看板.html" .
cp "$SKILL_DIR/assets/bi-proxy-server.js" .
cp "$SKILL_DIR/assets/start-dashboard.sh" .
chmod +x start-dashboard.sh
```

实际操作时，assets 的绝对路径为 `~/.catpaw/skills/供给流量入口分析/assets/`。

### 日常启动

```bash
# 检查是否已在运行
lsof -i :7788 | head -3

# 未运行则启动（在工作空间目录执行）
bash start-dashboard.sh
```

启动后用 catdesk 浏览器打开：

```bash
~/.catpaw/bin/catdesk browser-action '{"action":"navigate","url":"http://localhost:7788/"}'
```

## 数据说明

**数据源**：`mart_sailor_global` 流量归因三表

取数协议和埋点评测建议见：

- `references/data-query-protocol.md`
- `references/tracking-eval-cases.md`

| 表 | 说明 |
|---|---|
| `topic_flow_sdk_log_path_expose_d` | 曝光日志 |
| `topic_flow_sdk_log_path_click_d` | 点击日志 |
| `topic_flow_sdk_log_path_ord_d` | 成单日志 |

**核心过滤条件**：`is_shop_ent = '是'`（仅商家入口流量）

**核心指标**：

| 指标 | 定义 |
|---|---|
| 曝光UV | 商家入口被成功展示的去重设备数（union_id 去重） |
| 点击UV | 商家入口被点击的去重设备数 |
| 成单UV | 通过商家入口完成成单（is_arrange=1）的去重设备数 |
| CTR | 点击UV / 曝光UV |
| CVR | 成单UV / 点击UV |
| CXR | 成单UV / 曝光UV |

## 三大分析模块

### 1. 品牌流量转化
按品牌维度聚合曝光、点击、成单数据，支持自定义维度（品牌ID/名称/生命周期分层/页面/资源位/**SPU ID/SPU商品名称**）和指标（曝光UV/点击UV/成单UV/订单量/CTR/CVR/CXR）。橙色高亮 = 高曝光低转化品牌（曝光UV ≥ 均值 且 CVR ≤ 均值的50%）。

底表新增字段：`ad_position_spu_id`、`ad_position_spu_name`、`ad_position_spu_en_name`

### 2. 品牌流量入口分布
分析各品牌在不同页面/资源位的流量分布，支持自定义维度（页面/资源位/**SPU ID/SPU商品名称/门店ID/门店名称/门店英文名称**）和指标，可视化展示入口占比。

底表新增字段：`ad_position_spu_id`、`ad_position_spu_name`、`ad_position_spu_en_name`、`ad_position_shop_id`、`ad_position_shop_name`、`ad_position_shop_name_en`

### 3. 品牌流量转化异常分析
自动检测本周 vs 上周同期的异常情况，周同比下降 >20% 视为异常。

**评估粒度**：日期（dt）× 品牌ID × 品牌名称 × 品牌英文名称，每条记录代表某品牌在某天的异常表现。

**输出列**：日期、品牌ID、品牌名称、品牌英文名、当期/上周曝光UV、曝光UV周同比、当期/上周点击UV、点击UV周同比、当期/上周订单量、订单量周同比、异常指标标签。

**统计信息**：底部显示「N 条异常记录（涉及 M 个品牌）」，M 为去重品牌数。

**SQL 逻辑**：上周三张表的 dt 字段用 `DATE_ADD(..., 7)` 偏移 +7 天后与本周 dt 对齐，JOIN 条件为 `dt + brand_id`，排序为 `dt ASC, 最小周同比 ASC`，LIMIT 500。

## 筛选维度

- **Region**：SA/HK/AE/KW/QA/BR/BH
- **品牌ID**：多个用逗号分隔
- **页面名称**：可搜索下拉，支持关键词过滤（34个页面选项）
- **资源位名称**：可搜索下拉，级联页面名称筛选（选页面后自动缩小范围）
- **日期范围**：默认昨日

> 城市筛选器已移除。页面/资源位筛选器同时作用于「品牌流量转化」「品牌流量转化异常分析」两个模块。

## Cookie 维护

代理服务器启动时自动从 catdesk 浏览器读取 bi.keetapp.com 的 Cookie，无需手动维护。Cookie 过期时重启服务器即可刷新：

```bash
# 手动刷新 Cookie（无需重启）
open http://localhost:7788/refresh-cookie
```

## keeta-bi 直接调用（无需启动看板）

集成后，Claude 也可以**不启动看板**，直接通过 `keeta_bi_skill.py` 执行 SQL 查询：

```bash
# 查看可用工作空间
python3 ~/.catpaw/skills/merchant-traffic-analysis/assets/scripts/keeta_bi_skill.py spaces

# 查看可用队列
python3 ~/.catpaw/skills/merchant-traffic-analysis/assets/scripts/keeta_bi_skill.py queues

# 查看数据源
python3 ~/.catpaw/skills/merchant-traffic-analysis/assets/scripts/keeta_bi_skill.py datasources -p <project>

# 执行 SQL（同步等待结果）
python3 ~/.catpaw/skills/merchant-traffic-analysis/assets/scripts/keeta_bi_skill.py run \
  "SELECT dt, region, COUNT(*) as cnt FROM mart_sailor_global.topic_flow_sdk_log_path_expose_d WHERE dt='2025-01-01' GROUP BY 1,2 LIMIT 10" \
  -p <project_id_or_name> \
  -q <spark_queue> \
  --json

# 仅提交 SQL（异步，返回 queryId）
python3 ~/.catpaw/skills/merchant-traffic-analysis/assets/scripts/keeta_bi_skill.py submit "<SQL>" -p <project> -q <queue>

# 查询执行状态
python3 ~/.catpaw/skills/merchant-traffic-analysis/assets/scripts/keeta_bi_skill.py status <queryId>

# 获取执行结果
python3 ~/.catpaw/skills/merchant-traffic-analysis/assets/scripts/keeta_bi_skill.py result <queryId> -n 500
```

**参数说明：**
- `-p`：工作空间 ID 或名称（`0` = 个人空间）
- `-q`：Spark 队列名（Hive/OneSQL/Presto 必填，Doris 可省略）
- `-e`：引擎类型，默认 `onesql`，可选 `hive/presto/doris/mysql`
- `--ds`：数据源名称，默认 `dw_hive`
- `-n`：返回行数上限，默认 200
- `--json`：输出 JSON 格式（便于程序解析）

**首次使用需安装依赖：**

```bash
python3 -m pip install -r ~/.catpaw/skills/merchant-traffic-analysis/assets/scripts/requirements.txt
```
