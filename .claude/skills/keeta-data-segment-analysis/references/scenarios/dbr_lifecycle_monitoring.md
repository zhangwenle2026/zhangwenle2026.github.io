# DBR 用户生命周期监控 — 场景子协议

> 本文件是该场景的**唯一权威来源**。与 SKILL.md 冲突时，以本文件为准。

---

## 1. 适用范围

- **场景**：每日生成用户生命周期分层的核心指标监控，展示新客、潜客、尝鲜用户（1-4单）、成熟用户（5+单）、沉流用户在浏览、交易、AOV、补贴率等维度的表现，并拆分 Organic/Strategy 渠道。
- **支持 region**：仅 AE（UAE）。其他 region 的 SQL 口径和 PN 码需独立确认，**禁止直接套用本场景的 SQL 或 PN 码**。

---

## 2. 触发条件

满足以下任意一项时进入本场景：

- 用户明确提到 DBR、生命周期监控、各分层用户表现
- 用户要求分析新客/老客/成熟/沉流等生命周期分层指标
- region 为 AE 且需要标准用户分层数据

---

## 3. 输入参数

| 参数 | 说明 | 默认值 | 校验规则 |
|------|------|--------|---------|
| `region` | 查询区域 | 无，**必须由用户提供** | 当前仅支持 `AE`，其他 region 拒绝执行 |
| `date` | 查询基准日期 T1（格式 YYYYMMDD） | 昨天（系统日期 -1） | 不得为未来日期；不得超过今天 -1 |

> ⚠️ **弱模型常见错误**：将用户说的"今天"直接作为 T1。T1 = 昨天，今天的数据未入库，禁止用今天日期查询。

---

## 4. 日期口径

> ⚠️ **弱模型常见错误**：日期计算错误（如用今天作为 T1、T8 算成 -6 天而非 -7 天）。所有日期由脚本自动计算，**禁止手工推算日期**。

| 变量 | 含义 | 计算方式 |
|------|------|---------|
| `T1` | 基准日（昨天） | `date.today() - 1` 或用户指定 |
| `T2` | T1 前一天（DoD 对比基准） | `T1 - 1` |
| `T8` | 上周同期（WoW 对比基准） | `T1 - 7` |
| `T9` | T8 前一天 | `T1 - 8` |

- **DoD** = T1 vs T2
- **WoW** = T1 vs T8
- 图表展示 4 列：T9、T8、T2、T1
- SAB 快照固定使用 **T1** 日期，不随 dt 变化

---

## 5. 查询与产物

### 5.1 执行方式

所有查询通过 `scripts/ae_dbr_query.py` 统一执行：

```bash
# 查询昨天数据（默认）
scripts/ae_dbr_query.py

# 查询指定日期
scripts/ae_dbr_query.py --date 20260519

# 仅重跑指定 SQL（逗号分隔）
scripts/ae_dbr_query.py --date 20260519 --sql funnel,csub
```

图表通过 `scripts/ae_dbr_chart.py` 生成：

```bash
scripts/ae_dbr_chart.py --date 20260519
```

### 5.2 产物清单

| 产物 | 路径 | 说明 |
|------|------|------|
| SQL 结果 | `.artifacts/segment_analysis/{T1}/sql_{name}.csv` | 6 个 SQL，name = funnel/visit_old/trade/csub/global/sab |
| 图1（生命周期分层） | `.artifacts/segment_analysis/{T1}/chart_{T1}.png` | 大盘 + 各分层指标 |
| 图2（SAB 漏斗） | `.artifacts/segment_analysis/{T1}/chart_{T1}_sab.png` | SAB 层级 VUV/OUV |

> ⚠️ **CSV 文件为内部中间产物，禁止将 CSV 内容或 Markdown 数据表格发送给用户。**

### 5.3 SQL 列表

| SQL 名 | 内容 | 权限要求 |
|--------|------|---------|
| funnel | 新客/潜客 Visit UV，O/S 用 first_channel_name | 个人空间 |
| visit_old | 老客 Visit UV（1-4单/5+/沉流），O/S 用 user_id%10=0 | 个人空间 |
| trade | 各分层 Order UV/订单量/AOV/美补率，O/S 拆分 | 个人空间 |
| csub | C补率分子（AE region 专用 PN 码，必须 INNER JOIN 主表过滤 is_pickup=0） | 需要 fact_act_order_promotion_d 权限 |
| global | 全量 Order UV/订单量/AOV/美补率（C补率分母） | 个人空间 |
| sab | SAB 漏斗 VUV/OUV，SAB 快照用 T1 | 个人空间 |

**O/S 拆分铁律（禁止混用）：**

| 人群 | Organic 判断方式 |
|------|----------------|
| 新客/潜客（user_layers_5_id IN (1,2)） | `first_channel_name rlike '(?i)organic'` |
| 老客（1-4单/5+单/沉流） | `user_id % 10 = 0` |

**csub PN 码（AE region 专用，禁止用于其他 region）：**
`PN2576E9CS06242G`(新客)、`PN254G6A3S062439`(老客)、`PN2572094S06244C`(OFU)、`PN255B35GS06245B`(大促)、`PN2520A5DS062463`(裂变)

---

## 6. 发布前 Gate Check

> ⚠️ **所有 Gate Check 由脚本负责执行并以退出码通知（退出码非零 = 失败）。模型不得跳过或自行判定通过。任一 Gate 失败，禁止输出业务趋势结论，执行[失败输出格式]。**

脚本执行完成后，**模型必须检查脚本退出码**：

```bash
# 查询脚本退出码
scripts/ae_dbr_query.py --date 20260519; echo "EXIT:$?"

# 图表脚本退出码
scripts/ae_dbr_chart.py --date 20260519; echo "EXIT:$?"
```

**退出码约定：**

| 退出码 | 含义 |
|--------|------|
| 0 | 全部 Gate 通过，可继续 |
| 1 | Gate 失败（见脚本 stderr 中的 `[GATE FAIL]` 行） |
| 2 | 部分 SQL 失败（见脚本摘要输出） |

**Gate Check 项目（由脚本 ae_dbr_query.py 自动执行）：**

| Gate | 检测内容 | 失败条件 | 失败时行为 |
|------|---------|---------|-----------|
| G1 全量 SQL 完整性 | 6 条 SQL 全部成功 | 任意 SQL 失败或行数为 0 | 退出码 2，打印失败 SQL 列表 |
| G2 空分区检测 | T1 日期在各 CSV 中存在数据 | 任意核心 CSV（funnel/global/trade）中 T1 日期行数为 0 | 退出码 1，打印 `[GATE FAIL] G2` |
| G3 O/S 自检 | visit_old 中 5+ Strategy VUV 占比 | Strategy VUV 占比 < 80%（说明 O/S 口径混用） | 退出码 1，打印 `[GATE FAIL] G3` |
| G4 C补率范围 | C补率计算结果 | C补率 < 1% 或 > 20% | 退出码 1，打印 `[GATE FAIL] G4` |
| G5 图表生成 | 两张图片文件存在 | chart_{T1}.png 或 chart_{T1}_sab.png 不存在 | 退出码 1，打印 `[GATE FAIL] G5` |

> ⚠️ **弱模型常见错误**：
> - 看到"部分 SQL 成功"就继续生成结论——**禁止，必须全部成功**
> - 缓存冒充：上次已有 CSV，本次跳过查询直接出图——**禁止，每次必须重新执行脚本**
> - 图表脚本报错但模型继续回复——**禁止，图表生成失败须走失败流程**

---

## 7. 执行步骤

按顺序执行，不得跳步或调换顺序：

1. **参数确认**：确认 region=AE，确认 T1 日期（默认昨天，不得用今天）
2. **执行查询**：运行 `scripts/ae_dbr_query.py`，等待所有 SQL 完成
3. **检查退出码**：退出码非 0 → 执行[失败输出格式]，停止
4. **执行图表**：运行 `scripts/ae_dbr_chart.py`，等待两张图片生成
5. **检查退出码**：退出码非 0 → 执行[失败输出格式]，停止
6. **生成一句话结论**：扫描 CSV 数据，按[最终输出格式]规则生成结论
7. **分三次回复用户**：第1条发结论文字，第2条发图1，第3条发图2；每条消息之间不插入任何过渡文字

---

## 8. 最终输出格式

> ⚠️ **所有 Gate Check 通过后才能执行此步骤。**

**严格按以下顺序分三次发送，不得合并、不得增减、不得在任何两步之间插入过渡文字：**

| 消息 | 内容 |
|------|------|
| 第 1 条消息 | 一句话分析结论（纯文字，结尾不加任何引导语） |
| 第 2 条消息 | 仅图1：`.artifacts/segment_analysis/{T1}/chart_{T1}.png` |
| 第 3 条消息 | 仅图2：`.artifacts/segment_analysis/{T1}/chart_{T1}_sab.png` |

**禁止：**
- 禁止在结论与图片之间插入任何过渡文字（如"以下是图表："、"详见图片："等）
- 禁止在同一条消息内同时发送两张图片
- 禁止将 Markdown 数据表格发送给用户
- 禁止输出逐指标的多段长篇分析
- 禁止在一句话之外附加额外趋势解读段落

**一句话结论生成规则：**

- 扫描所有指标的 DoD 和 WoW 变化（来源：CSV 数据，不得凭记忆编写）
- **仅对绝对变化幅度 ≥5% 的指标**纳入结论（count 类、rate 类、AOV 统一使用此阈值）
- 最多点名 1-3 个异动最显著的指标，说明分层、方向和幅度
- 若无指标超过阈值：输出「各指标整体平稳，无显著异动。」

示例句式：「新客首单 S 渠道 VUV DoD +12%、5+单用户 AOV WoW -6%，其余指标平稳。」

---

## 9. 失败输出格式

任一 Gate 失败或脚本退出码非 0 时，**仅输出以下格式，不附加任何业务趋势判断**：

```
❌ 执行失败

失败步骤：<Gate 名称，如 "G3 O/S 自检">
失败原因：<脚本 stderr 中 [GATE FAIL] 行的原文>
已有产物：
  - .artifacts/segment_analysis/{T1}/sql_funnel.csv（若存在）
  - .artifacts/segment_analysis/{T1}/sql_global.csv（若存在）
  - （其他已成功的文件）
下一步动作：<根据失败原因给出的具体操作，例如：
  - G1/G2：检查 BI 接口连通性，重新执行脚本
  - G3：检查 SQL 2/3 O/S 逻辑，确认老客使用 user_id%10=0
  - G4：检查 SQL 4 csub 是否 INNER JOIN 主表并过滤 is_pickup=0
  - G5：重新执行 ae_dbr_chart.py，检查 matplotlib 依赖是否安装>
```

---

## 附录：常见问题排查

| 现象 | 原因 | 处理 |
|------|------|------|
| G3 触发：5+ Strategy VUV ≈ 0 | 老客 O/S 用了 first_channel_name | 检查 SQL 2/3 O/S 逻辑 |
| G4 触发：C补率 < 1% | csub 未 INNER JOIN 主表或未过滤 is_pickup=0 | 检查 SQL 4 |
| G4 触发：C补率 > 20% | csub JOIN 条件缺失导致膨胀 | 检查 SQL 4 先聚合到订单级再 JOIN |
| G1 触发：csub 权限报错 | 无 fact_act_order_promotion_d 权限 | 切换有权限的项目组，或申请表权限 |
| G5 触发：图片未生成 | matplotlib 未安装或字体缺失 | 检查依赖，重新执行 ae_dbr_chart.py |
| SQL 超时 | 复杂 JOIN 耗时 | 超时上限 6000s，可手动重试 |
