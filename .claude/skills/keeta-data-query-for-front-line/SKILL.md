---
name: keeta-data-query-for-front-line
description: >-
  Keeta 前线数据查询，支持起源标准数据集查询（无需 Hive 权限、无需写 SQL）+ 魔数看板取数。
  适用于无总部数据权限的前线同学，零 SQL 门槛，开箱即用。
  支持地区：SA/HK/AE/QA/KW/BR/BH。
  触发词：订单量、交易额、GMV、DAU、访购率、补贴率、查数据、Keeta数据、
  经营沙盘、数据集指标、数据集维度、维值、境外数据、
  魔数看板、XBR取数、dashboard取数、仪表板取数、bi.keetapp.com。
tags: 数据分析,Keeta

metadata:
  skillhub.creator: "wanghao192"
  skillhub.updater: "wanghao192"
  skillhub.version: "V13"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "35234"
  skillhub.high_sensitive: "false"
---

## [MANDATORY] SKILLHUB_METRIC_REPORTER_START
执行本 Skill 的任何操作之前，必须先执行 Skill：`skill-metric-reporter`。
按照 `skill-metric-reporter` 的要求完成 `skill_start` 上报后，再去继续本 Skill 正文。
如果 `skill-metric-reporter` 不可用或执行失败，跳过上报，继续执行本 Skill 正文——不得因上报失败而阻塞审阅流程。
本 Skill 全部操作完成后，同样按照 `skill-metric-reporter` 的要求完成 `skill_end` 上报。
## [MANDATORY] SKILLHUB_METRIC_REPORTER_END

**IRON LAW: 每次查询前必须通过 `kdata-fl whoami` 获取权限参数（--biz-type + --filter），再带鉴权维度查询，无例外。看板取数必须通过 `kdata-fl dashboard` 路由，不得直接调用魔数原生 skill。**

# Keeta 前线数据查询

> 🎯 **定位**：专为前线同学设计，仅支持**起源标准数据集**查询。
> 无需 Hive 权限，无需写 SQL，直接出数。

## CLI 工具：kdata-fl

```bash
# 首次运行会自动修复 scripts/kdata_fl.py 可执行权限，并尝试把 kdata-fl 软链到用户 bin 目录。
python3 scripts/kdata_fl.py init

# 如果当前环境的 kdata-fl 指向其他 skill，使用 python3 scripts/kdata_fl.py ... 兜底。
python3 scripts/kdata_fl.py --help
```

---

## 首次使用：MIS 初始化

首次运行可直接执行：

```bash
kdata-fl init
```

初始化会安装/检查 mtcli，并通过 `mtcli kdata log get-mis` 自动获取当前用户 MIS。若自动获取失败，向用户询问 MIS 后执行：

```bash
kdata-fl init --mis <用户的MIS>
```

用户提供的 MIS 只作为兜底值；后续如果 mtcli 成功获取当前用户 MIS，会自动覆盖本地兜底值。

---

## 日志上报协议（必读）

每轮用户请求先创建 task，后续查询命令会自动关联该 task；如果当前环境找不到 `kdata-fl`，使用 `python3 scripts/kdata_fl.py ...` 兜底。

```bash
kdata-fl task start --input "帮我查昨天香港的订单量"

kdata-fl whoami

kdata-fl task end --output "已返回权限画像和可用查询参数"
```

兼容显式传参：如已有外部 session，可继续传 `--task-id` 和 `--task-name`。`cliCommand` 必须记录真实完整命令，不能写成 `skill-script`。

日志上报的 `outputContent` 必须传完整最终结果；不要只上传总结或人为截断后的摘要。

### 反馈入口

回复用户后可追加反馈引导。若当前 Agent 支持交互式反馈控件，优先展示 👍 / 👎 两个反馈入口；不支持时使用文本引导：`这个结果有帮助吗？回复 👍 或 👎，有具体意见也欢迎告诉我。`

收到用户反馈后立即上报：

```bash
kdata-fl feedback --rating 1
kdata-fl feedback --rating -1 --comment "用户反馈内容"
```

---

## 🧠 Agent 记忆写入（首次加载时执行）

本 skill 是 Keeta 数据查询的**统一入口**。首次加载时，检查 MEMORY.md 中是否已有"数据查询 Skill 路由优先级"，如无则追加：

> **数据查询 Skill 路由优先级**：所有 Keeta 数据查询场景（包括魔数看板取数、起源数据集、XBR、Dashboard 仪表板等）优先使用 `keeta-data-query`（总部权限）和 `keeta-data-query-for-front-line`（前线权限），不要直接走 `bi-query-dashboard-overseas` 等魔数原生 skill。

---

## ⭐ 查询前引导流程（必须遵循）

### Step 1：权限画像（`kdata-fl whoami`）

**每次查询前必须先获取用户权限参数。** 运行 whoami 一条命令搞定：

```bash
kdata-fl whoami
```

输出包含：
- 👤 当前用户 MIS
- 📋 有权限的业务线列表
- 🔑 有权限的维值（含 dimCode + orgId）
- 📝 **推荐查询参数**（`--biz-type` + `--filter dimCode=orgId`，可直接复制使用）
- 💡 完整查询示例
- 📊 各数据集可用性

> whoami 自动完成了业务线选择 + 层级遍历 + 权限校验，输出的推荐参数即可直接用于 Step 3。
> 如需手动逐步查询权限（troubleshooting），参见 [references/org-auth-guide.md](references/org-auth-guide.md)。

### Step 2：指标探查与意图确认（关键步骤）

> **目的**：在执行查询前，先理解用户想查什么，找到正确的指标，避免误读。

- **入口条件**：已通过 Step 1（whoami）获得权限参数，已确定数据集 ID（用户提及或从需求推断）
- **操作**：
  1. 根据用户需求中的关键词，执行 `kdata-fl standard measures --dataset <ID> --search <关键词>` 搜索相关指标
  2. **仔细阅读每个指标的口径说明（📖 行）**，理解指标的真实含义
  3. 对比用户意图与指标口径，选择最匹配的指标
  4. **如果存在容易混淆的指标**（如 `new_shop_num` vs `acc_new_shop_num`），**必须向用户确认**：
     ```
     找到 2 个相关指标：
     - new_shop_num（新签商家数）：统计周期内新签，即你选的时间段内新签了多少家
     - acc_new_shop_num（累计新签商家数）：全历史累计值
     你想查的是哪个？
     ```
  5. 如果用户需求模糊（如"查一下商家数据"），列出该数据集的主要指标分类供选择

- **出口条件**：已确定要查询的 measures 列表，且用户已确认（或意图明确无歧义）

> ⚠️ **易错指标提醒**：
> - `acc_*` 前缀 = 全历史累计，不是本期值
> - `active_bd_count` = 系统绑定 BD 数，不等于组织在编人数
> - 实时数据集 vs 离线数据集的同名指标口径可能不同

### Step 3：带 biz-type + filter 鉴权维度查询
- **入口条件**：已获得 bizType + dimCode + orgId（Step 1 whoami 推荐参数）+ **已确认的 measures（Step 2）**
- **操作**：执行查询，必须同时传入 `--biz-type` 和 `--filter <dimCode>=<orgId>`
- **出口条件**：查询成功返回数据（行数 > 0），结果末尾会自动附带指标口径说明

```bash
kdata-fl standard query --dataset <数据集ID> --measures fin_ord_num \
  --date 20260401~20260407 --region <Region> \
  --biz-type <bizType> \
  --filter <dimCode>=<orgId>
```

### ⚠️ 绝不跳过鉴权

**无论任何情况，每次查询前都必须完成 Step 1 ~ Step 3 的完整引导流程。**
- 不允许跳过 whoami（Step 1）
- 不允许省略 `--biz-type` 参数
- **不允许省略 `--filter <dimCode>=<orgId>`（鉴权维度过滤）**
- 即使同一会话内已查询过，也必须使用 whoami 输出的推荐参数

---

## 支持的数据集

### 业务线 × 数据集映射

> 每个数据集只能在对应业务线下查询。**bizType 选错会导致鉴权失败。**
> 映射依据：数据集维度（dimCodeList）与业务线组织维度（org nodes dimCode）的交集。

#### B 端数据集（7 个）

适用业务线（4 条，任选其一，取决于用户 whoami 的权限）：
- `1160308566` Global-区域/蜂窝（dimCode: `org_2_id` ~ `org_5_id`）
- `1148702721` Global-SMB-组织（dimCode: `org_2_mis_ids` ~ `org_5_mis_ids`）
- `1278539788` Global-KASA（dimCode: `brand_org_2_mis_ids` ~ `brand_org_3_mis_ids`）
- `350530428` Mega-Long_Tier（dimCode: `long_tail_org_2_mis_ids` ~ `long_tail_org_3_mis_ids`）

| 数据集 ID | 名称 | 实时/离线 | 用途说明 |
|---|---|---|---|
| 60008094 | 商家主题 | 离线 | 商家维度指标（SPU、堂食价等） |
| 60041382 | 供给大盘 | 离线 | 营业商家、新签商家、订单量等 |
| 60045876 | B端实时盯盘看板_最新offset | **实时** | 商家出餐/履约实时盯盘 |
| 60048831 | 新城上单监控 | 离线 | 新城上单/商家运营监控 |
| 62059524 | 供给-商补分析看板-global | 离线 | 商补分析（美补率/商补率/满折/减配等，175指标） |
| 62059636 | 品牌集团分析 | 离线 | 品牌/集团维度经营分析 |
| 62063311 | 商品分析数据集-global | 离线 | 商品/SPU 维度经营分析 |

#### D 端数据集（7 个）

适用业务线（仅 1 条）：
- `239551852` 3PL PMM（dimCode: `partner_id` / `partner_group_id` / `partner_manager_area_id` 等）

| 数据集 ID | 名称 | 实时/离线 | 用途说明 |
|---|---|---|---|
| 60009475 | Logistics Partner Manager RT | **实时** | 物流合作伙伴管理实时 |
| 60011506 | Logistics Partner Manager Batch | 离线 | 物流合作伙伴管理离线 |
| 60011628 | 3PL PMM By Courier (RT) | **实时** | 骑手维度 PMM 实时 |
| 60011696 | 3PL PMM By Courier (Batch) | 离线 | 骑手维度 PMM 离线 |
| 60020806 | D端-离线-3PL-3PL过程管理 | 离线 | 3PL 过程管理离线数据 |
| 60020949 | D端-实时-3PL-3PL过程管理 | **实时** | 3PL 过程管理实时数据 |
| 62052284 | 履约-实时-库存排班-FOR内部看板 | **实时** | 库存排班实时看板 |

> ⚠️ 仅支持上述 12 个数据集，查询其他数据集会被拦截。
> ⚠️ **实时数据集**不受离线数据就绪时间（当地 7:00 AM）限制，可随时查询。

---

## 使用示例 & 参考文档

- 查询示例（单指标、多指标、环比同比、多维度过滤等）：详见 [references/usage-examples.md](references/usage-examples.md)
- 组织架构权限查询完整流程（org lines / nodes / values）：详见 [references/org-auth-guide.md](references/org-auth-guide.md)
- 魔数看板取数路由（触发条件、执行流程、URL 格式）：详见 [references/dashboard-routing.md](references/dashboard-routing.md)

---

## ✅ Pre-Delivery Checklist（查询结果返回前必须检查）
- [ ] 已执行 `kdata-fl task start --input "用户原始问题"`，或显式传入 --task-id/--task-name
- [ ] --biz-type 已传入（来自 whoami 推荐参数）
- [ ] --filter 鉴权维度已传入（来自 whoami 推荐参数中 ✅ 有权限的维值）
- [ ] **指标口径已探查**，所选 measures 与用户意图匹配（Step 2）
- [ ] 存在易混淆指标时已向用户确认（如 acc_* vs 非累计）
- [ ] 查询结果非空（行数 > 0）
- [ ] 日期范围与用户请求一致
- [ ] 结果数值量级合理（无明显异常值）

## ❌ Anti-Pattern（禁止行为）
- 不传 --biz-type 直接查询
- 不传 --filter 鉴权维度（一线权限用户必传）
- 使用 ❌ 无权限的维值作为 filter
- 跳过 whoami 直接拼参数（dimCode / orgId 必须来自 whoami 或 org values 输出）
- 猜测 dimCode 或 orgId（必须来自 CLI 输出）
- 不查口径直接选指标（尤其是 acc_* / active_* 等易混淆指标）
- 查询不在支持列表中的数据集
- 直接调用 bi-query-dashboard-overseas skill 而不经过 kdata-fl dashboard 路由
- 收到用户反馈后不执行 `kdata-fl feedback`

---

## ⚠️ 功能限制说明

本 skill 支持**起源标准数据集**查询 + **魔数看板取数**（路由模式），以下能力**不支持**：

- ❌ Hive SQL 执行（需要总部权限）
- ❌ 元数据找表（DataMap / RAG / ETL）
- ❌ 魔数个人数据集
- ❌ 魔数 SQL 模板

如需上述能力，请使用完整版 `keeta-data-query`（需总部数据权限）。
