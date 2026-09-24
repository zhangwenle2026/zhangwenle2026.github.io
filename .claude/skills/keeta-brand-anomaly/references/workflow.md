# 完整分析流程 - Workflow

> ⚠️ **语言规则（最高优先级，不得违反）**：本文件中所有输出模板均以中文示意。实际输出时，**必须严格使用用户对话所用的语言**（中文→中文，英文→英文，混合语言→英文）。
> - **🚨 纯度强制**：回复中**不得出现任何用户语言以外的字符**。英文回复中禁止夹带任何中文字（含括号、标点），中文回复中禁止夹带整段英文。指标名称须从 `sql-templates.md` 多语言对照表取对应语言版本。
> - 所有非指标名称的文本（步骤提示、结论、说明等）必须自动翻译为用户语言；禁止直接展示中文名或自行翻译；禁止在非中文回复中夹带任何中文字符。

## ⚠️ 单日 vs 多日模式（必读，优先级最高）

用户在第三步确认查询日期时，根据选择的周期自动确定分析模式，**全程固定，不得中途切换**：

| 模式 | 触发条件 | 对比期计算方式 | 说明 |
|------|---------|-------------|------|
| **单日模式** | 用户选择单天（如 `20260422`） | WoW：`current_dt - 7天` | 使用"单日"列指标 Code，全部为当日绝对值 |
| **多日-周模式** | 用户选择"上周"或以周为粒度的区间 | WoW：对比期 = 当期区间整体往前移7天 | 使用"多日"列指标 Code；周边界因 Region 不同（见下方规则） |
| **多日-月模式** | 用户选择"本月"或以月为粒度的区间 | MoM：对比期 = 上一自然月同区间 | 使用"多日"列指标 Code |
| **多日-自定义** | 用户自定义任意区间 | PoP：对比期由用户指定（或默认往前移相同天数） | 使用"多日"列指标 Code |

> ⚠️ 模式一旦确定，Step 0、模块 1~5 中所有 `--measures` 参数必须使用对应模式的 Code，见 sql-templates.md 各步骤的"多日替换"说明。
> ⚠️ 报告中 WoW/MoM/PoP 标注要与实际对比口径一致，不得统一写"WoW"。

---

## ⚠️ 数据时效说明（必读）

所有 Hive 表均为**离线数据**，最新只有 **t-1（昨天）** 的数据。
- 用户说"查最新一天"、"查今天"、"查最近数据" → 一律理解为 **t-1**
- 单日模式默认：`current_dt` = 今天日期 - 1 天；`prev_dt` = `current_dt` - 7 天（WoW）
- 禁止用今天日期作为 `dt` 参数，否则查不到任何数据

## ⚠️ 多日时间区间规则（必读）

**所有查询步骤（Step 1、Step 0、模块 1~5）必须使用同一时间区间和同一对比口径**，不得在大盘用多日、在品牌五维用单日，否则口径不一致，分析结论不可信。

**对比期确定规则**：
- **周粒度（WoW）**：`prev_start` = `current_start - 7天`，`prev_end` = `current_end - 7天`
- **月粒度（MoM）**：`prev_start`/`prev_end` 为上一自然月对应日期
- **自定义（PoP）**：若用户未指定，默认 `prev_start`/`prev_end` = 当期区间整体往前移（天数等于当期区间长度）；如用户明确指定了对比期则直接使用

**⚠️ 周边界规则（按 Region 区分，严格遵守）**：
用户说"上周"、"本周"等周粒度查询时，**周的起止日必须根据 Region 决定**：

| Region | 一周第一天 | 一周最后一天 | 格式 |
|--------|-----------|------------|------|
| **BR / HK / AE** | 周一（Monday） | 周日（Sunday） | Mon-Sun |
| **SA / QA / KW / BH** | 周日（Sunday） | 周六（Saturday） | Sun-Sat |

**计算示例**：
- BR / HK / AE「上周」= 找上一个已结束的完整 Mon-Sun 区间
- SA / QA / KW / BH「上周」= 找上一个已结束的完整 Sun-Sat 区间
- 展示区间给用户前必须验证起始日正确，验证失败则重新计算
- 自动计算后必须将区间明确告知用户确认（如：「HK 上周 = 04-14（Mon）~ 04-20（Sun），确认吗？」）

**具体规则**：
- Step 1 大盘品牌查询：`--date {current_start}~{current_end}` vs `--date {prev_start}~{prev_end}` ✅
- Step 0 品牌指标查询：同上 ✅
- 模块 1~5 门店级查询：同上 ✅
- **禁止**：大盘用区间、品牌/门店下钻只用结束日（`current_end`）单天 ❌

**校验方式（🚨🚨🚨 硬拦截，不可跳过）**：

> 🔴 **校验通过前，禁止输出任何日期给用户、禁止执行任何查询。这是最高优先级的硬拦截。**

**步骤1**：确认所有 kdata 命令的 `--date` 参数格式均为 `{start}~{end}`，start = end 时为单日

**步骤2**：**日期-星期校验（强制）**：确定日期范围后，必须用 Python 验证**所有四个日期**（当期起始、当期结束、对比期起始、对比期结束）与星期是否匹配，禁止凭印象判断：

```python
from datetime import date

# 验证所有四个日期
for label, d in [("当期起始", date(y1,m1,d1)), ("当期结束", date(y2,m2,d2)),
                 ("对比期起始", date(y3,m3,d3)), ("对比期结束", date(y4,m4,d4))]:
    print(f"{label}: {d.strftime('%Y%m%d %A')} weekday={d.weekday()}")

# 验证起始日和结束日
week_start_wd = 6 if region in ['SA','QA','KW','BH'] else 0  # Sun=6, Mon=0
week_end_wd = 5 if region in ['SA','QA','KW','BH'] else 6  # Sat=5, Sun=6
assert curr_start.weekday() == week_start_wd, f"当期起始日错误"
assert curr_end.weekday() == week_end_wd, f"当期结束日错误"
assert prev_start.weekday() == week_start_wd, f"对比期起始日错误"
assert prev_end.weekday() == week_end_wd, f"对比期结束日错误"
```

**步骤3**：验证通过后才能输出给用户或执行查询

❌ **违反后果 = 流程中断，重新校验**

## ⚠️ 输出数字与查询口径必须一致（必读）

**最终报告中引用的所有数字，必须来自与分析口径完全一致的查询结果，禁止混用。**

- 若用户选择多日区间（如 20260420~20260421），则报告中的大盘订单量、品牌订单量、WoW、贡献值，全部必须来自多日查询的聚合结果
- **禁止**：用多日区间分析，却把某一单日的数字（如只查了 20260421）混入报告 ❌
- **禁止**：大盘用区间查询的数字，品牌下钻却用单日查询的数字混搭计算贡献 ❌
- 若某步骤查询结果是单日的，需重新用区间口径补跑后再引用

**自查清单（输出报告前必须过一遍）**：
1. 大盘订单量（`fin_ord_num`）是否用区间查询取得？✅/❌
2. 各品牌订单量是否用同一区间查询取得？✅/❌
3. 贡献值 = 品牌变化量 / 上期大盘总量，两者是否来自同一口径？✅/❌
4. 模块 1~5 门店数据是否也用同一区间？✅/❌

---

## 整体流程图

```
第一步：确认角色
  ├─ 前线 BDM/BD → 自动查 kdata org 权限，获取 region + bizType + dimCode + orgId
  └─ 后线/内部 → 手动选 region

第二步（前线自动 / 后线手动）：确认 Region

第三步：确认查询日期

【前置品牌总览】自动执行
  → 查数据集 62059636，输出权限范围内所有品牌订单量 WoW
  → 后线："{REGION} 共 XX 个品牌，其中 WoW 为负 XX 个"
  → 前线 BDM：品牌维度总览（波动贡献排序）+ 组织维度总览（下属升降），直接问要深入分析哪个品牌
  → 前线 BD："你负责 XX 个品牌，其中 WoW 为负 XX 个"

第四步：确认分析方式（基于总览结果）
  ├─ 方式1 异动品牌：从总览结果筛 WoW 为负，按跌幅取 Top X
  ├─ 方式2 大盘监控（仅后线/内部）：从总览结果算贡献，取 Top X
  └─ 方式3 定向分析：指定品牌 ID

Step 1：获取品牌 id 列表（直接复用总览结果，不重复查询）

Step 2：逐品牌深入分析（多品牌时 spawn sub-agents 并行）
  ├─ 【并行】外部环境查询（天气 + 节假日 + 大型活动）
  ├─ Step 0：前置查询（品牌级 WoW 总览）
  ├─ 模块1：营业情况（从 Step 0 结果判断）
  ├─ 模块2：体验情况（从 Step 0 结果判断，需进一步跑数据集取消原因下钻）
  ├─ 模块3：活动参与情况（从 Step 0 结果判断，需进一步跑失效 SQL）
  ├─ 模块4：流量情况（单独 SQL：商品曝光 + 资源位流量）
  └─ 模块5：补贴情况（从 Step 0 结果判断）

Step 3：汇总输出（所有品牌完成后一次性发）
```

---

## ⚠️ 查询超时处理规范（必读，每次执行 kdata 查询均适用）

kdata 查询为离线任务，单次查询可能因数据量大或集群负载高而超时（通常 SIGTERM，约 5~10 分钟）。**每次执行 kdata 查询必须遵守以下规范，避免用户长时间无响应干等。**

### 执行前：发状态播报

**每次执行 kdata 查询之前**，必须先向用户发一条状态消息，说明当前在做什么、预计多久：

```
⏳ 正在执行 [步骤名称]（如：Step 0 品牌总览 / 模块1 门店营业情况 / 模块4 CTR 渠道下钻）
   通常需要 1~3 分钟，请稍候…
```

多步查询时，每一步执行前都要播报（例：「⏳ 正在执行模块2 出餐时长查询，通常 1~2 分钟…」）。

### 执行后：超时处理

捕获以下超时信号：
- 进程被 SIGTERM 终止（returncode = -15 或 returncode 非0）
- stderr 包含 `timeout`、`killed`、`SIGTERM` 等关键词
- 查询超过 **8 分钟**仍未返回结果

**超时后必须立即告知用户**，输出：

```
🔴 查询超时：[步骤名称] 未能在预期时间内完成（kdata 集群超时）

可能原因：
- 门店数量过多（建议：门店数 > 50 家时按批次查询，每批 ≤ 50 个 shop_id）
- 集群负载高（建议：稍等 2~3 分钟后重试）

请回复「重试」重新执行此步骤，或回复「跳过」继续后续分析（该步骤标注为"数据缺失"）。
```

**绝对禁止**：超时后静默继续，或将空结果当作正常结果使用。

### 大品牌预防性分批策略

**门店数 > 50 家的品牌**（如 McDonald's SA ~144 家），门店级查询（模块 1~5）容易超时。执行前先判断：

1. 从 Step 0 结果获取品牌门店总数（`online_shop_num`）
2. 若门店数 > 50，**主动拆分**：将 shop_id 列表分批，每批 ≤ 50 个，串行执行，结果合并
3. 播报格式调整为：「⏳ 正在执行 [步骤名称]，品牌共 XX 家门店，分 N 批查询，每批约 1~2 分钟…」

> ⚠️ 分批查询时，每批执行前也要发简短状态（如「第 2/3 批…」），让用户知道进度。

---

## 0. 外部环境查询（每次分析必须执行，放在汇总最上方）

在开始品牌分析前，**与品牌 SQL 并行执行**，最终汇总时放在最上方。

```bash
# 天气（当前分析日期）
python3 ~/.openclaw/skills/keeta-external-context/scripts/weather.py {REGION} {current_dt}

# 节假日（分析周期内）
python3 ~/.openclaw/skills/keeta-external-context/scripts/holidays.py range \
  --start {last_week_dt_fmt} --end {current_dt_fmt} --regions {REGION}

# 大型活动（当月）
python3 ~/.openclaw/skills/keeta-external-context/scripts/events_search.py {REGION} --year {YYYY} --date {YYYY-MM}
```

输出格式参见 `output-format.md` 中的天气输出规则。
- 内部数据集 SSO 失败时自动回退 Open-Meteo，**不需要告知用户**
- 无节假日/活动时输出"无"，不省略该部分

---

## 前置品牌总览查询

> 在第三步（确认查询日期）完成后立即自动执行，无需用户触发。
> 目的：给用户全局视角，同时为后续 Step 1 提供数据，**避免重复查询**。

**数据来源**：统一使用**供给大盘数据集（ID：62059636）**，指标为 `fin_ord_num`。

**查询命令**（完整参数见 sql-templates.md `brand_overview_query`）：

> ⚠️ **单日/多日模式使用不同的 `--date` 参数**，必须与用户选择的分析周期一致。

**单日模式**（`--date {current_dt}~{current_dt}` / `--date {last_week_dt}~{last_week_dt}`）：
```bash
# ⚠️ 所有 kdata 查询必须复用 SESSION_TASK_ID（在 skill_tracker.py start 中生成的 TASK_ID），
#    禁止每次重新 uuid4()，否则 kdata 子系统的 task-id 与 skill_tracker traceId/sessionId 无法关联。
# 查当期（单日，⚠️ page-size 必须 ≥ total 行数，推荐 5000）
kdata --json --task-id "$TASK_ID" --task-name "brand_overview_curr:{REGION}:{current_dt}" \
  standard query \
  --dataset 62059636 \
  --measures fin_ord_num \
  --date {current_dt}~{current_dt} \
  --region {REGION} \
  --group-by brand_id,brand_name \
  --page-size 5000

# 查上周同期（单日）
kdata --json --task-id "$TASK_ID" --task-name "brand_overview_prev:{REGION}:{last_week_dt}" \
  standard query \
  --dataset 62059636 \
  --measures fin_ord_num \
  --date {last_week_dt}~{last_week_dt} \
  --region {REGION} \
  --group-by brand_id,brand_name \
  --page-size 5000
```

**多日模式**（`--date {current_start}~{current_end}` / `--date {prev_start}~{prev_end}`）：
```bash
# ⚠️ 所有 kdata 查询必须复用 SESSION_TASK_ID（在 skill_tracker.py start 中生成的 TASK_ID），
#    禁止每次重新 uuid4()，否则 kdata 子系统的 task-id 与 skill_tracker traceId/sessionId 无法关联。
# 查当期区间（多日，⚠️ page-size 必须 ≥ total 行数，推荐 5000）
kdata --json --task-id "$TASK_ID" --task-name "brand_overview_curr:{REGION}:{current_start}~{current_end}" \
  standard query \
  --dataset 62059636 \
  --measures fin_ord_num \
  --date {current_start}~{current_end} \
  --region {REGION} \
  --group-by brand_id,brand_name \
  --page-size 5000

# 查对比期区间（多日）
kdata --json --task-id "$TASK_ID" --task-name "brand_overview_prev:{REGION}:{prev_start}~{prev_end}" \
  standard query \
  --dataset 62059636 \
  --measures fin_ord_num \
  --date {prev_start}~{prev_end} \
  --region {REGION} \
  --group-by brand_id,brand_name \
  --page-size 5000
```

**前线 BDM/BD 额外参数**（所有 kdata 查询都必须加）：
```bash
  --biz-type {bizType} \
  --filter {dimCode}={orgId}
```

> **真实格式示例**（来自 `kdata org lines --mis <mis>` 返回结果）：
> ```bash
> # 示例：用户 mis=zhangsan，kdata org lines 返回 bizType=1, dimCode=dept_id, orgId=12345
>   --biz-type 1 \
>   --filter dept_id=12345
> ```
> **获取步骤**：第二步执行 `kdata org lines --mis {user_mis}` 返回 `bizType`；`kdata org values --mis {user_mis}` 返回 `dimCode` 和 `orgId`（即可用的维值）。将这三个值记录后用于后续所有查询。

> ⚠️ kdata --json 输出时需用 `raw[raw.find('{'):]` 截取 JSON（stderr 有安装日志混入）
> ⚠️ 查询完成后校验：`返回行数 == total字段`，不一致需加大 page-size

**代码层处理**：

> ⚠️ **大盘订单量口径（必须严格遵守）**：
> - **大盘订单量必须通过独立的无 `--group-by` 聚合查询获取**，不得用分组查询各行求和代替
> - 分组查询（`--group-by brand_id,brand_name`）的各行 `fin_ord_num` 相加**不等于**大盘总量——`--page-size` 截断会导致数据不完整，求和值严重偏低
> - ✅ 正确做法：执行两次不带 `--group-by` 的查询分别得到 `total_curr` 和 `total_prev`，大盘 WoW = (total_curr - total_prev) / total_prev
> - 品牌贡献计算：`contrib = (brand_curr - brand_prev) / (total_curr - total_prev)`（分母用大盘总量变化量，而非 total_prev）
> - **`brand_id = 0` 不是真实品牌（未归属品牌），从大盘到品牌明细全程剔除，不参与任何环节**：
>   - **大盘总量**：独立聚合查询（不带 `--filter`）得到 raw_total，再减去分组明细中 brand_id=0 的订单量，得到剔除后的真实大盘（kdata `--filter` 不支持 `!=`，无法在查询层直接排除）
>   - **品牌明细**：分组查询结果中，过滤掉 `brand_id == "0"` 的行，不参与贡献排名、WoW统计、品牌总数计算
>   - 品牌总数 = 过滤后的行数；PoP为负品牌数 = 过滤后 WoW<0 的行数
>   - 品牌深度分析（Step 0 + 模块 1~5）：仅对有品牌归属的 brand_id 执行
>   - 贡献公式分母用剔除 brand_id=0 后的真实大盘变化量
> - 大盘总量查询命令见 `sql-templates.md` → `brand_overview_query` 中的独立总量查询示例

> ⚠️ **数值解析必读（千分位逗号陷阱，2026-04-23 修复）**：
> - kdata JSON 返回的所有量类字段均为**带千分位逗号的字符串**，如 `fin_ord_num = "2,608"` 而非 `2608`
> - **直接 `int(r['fin_ord_num'])` 会报 ValueError**，导致所有品牌订单量为 0，大盘汇总为 0
> - ✅ 正确写法：`int(str(r.get('fin_ord_num', '0')).replace(',', ''))`
> - rows 结构为 **dict 列表**，取值用 `r.get('field_name', '0')`（非 `r[index]`）
> - 此规则适用于所有量类字段：`fin_ord_num`、`shop_avg_shop_entry_exposure_uv`、`paid_order_cancel_num_refund_shop_res` 等
>
> ❌ 历史 bug（2026-04-23）：因千分位逗号未处理，QA 大盘订单量 259,273 被误算为 206,344，WoW 从 -8.2% 误报为 -6.4%

1. 大盘总量通过「独立无 `--group-by` 聚合查询」获取 `raw_total`，**再减去分组明细中 `brand_id=0` 行的订单量**，得到 `grand_total`（⚠️ kdata `--filter` 不支持 `!=` 语法，无法直接排除 brand_id=0）
2. 分组品牌明细查询结果中，**过滤 `brand_id == "0"` 的行**，不参与贡献排名、WoW统计、品牌总数计算
3. 两次过滤后的结果以 brand_id 为 key JOIN，计算每个品牌 PoP = (curr - prev) / prev
4. 贡献计算：`contrib = (brand_curr - brand_prev) / (grand_curr - grand_prev) * 100`（分母用剔除 brand_id=0 后的大盘总量变化量）
5. 统计：总品牌数 = 过滤后行数；PoP为负品牌数 = 过滤后 WoW<0 的行数
6. 将完整结果缓存，供 Step 1 直接使用

**输出**（后线/内部）：
```
📊 {REGION} 大盘品牌总览（{查询日期} vs 上周同期）
大盘订单量：{grand_curr:,}（PoP {pop:+.1%}）   ← 独立聚合查询，已过滤 brand_id=0
品牌总数：XX 个（不含 brand_id=0，不设订单量门槛）
其中订单量 PoP 为负的品牌：XX 个
```

**输出**（前线 BDM，⚠️ 仅 BDM）：

BDM 有自己及全部下属的数据权限，总览分为**两部分**：

**第一部分：品牌维度总览**
- 用全部有权限的维值（`--filter dimCode=orgId1,orgId2,...` 或多次查询累加），查当期 + 对比期所有品牌的 `fin_ord_num`
- 输出总品牌数、总订单量、WoW
- 如果总订单量下降了，按波动贡献输出对总订单量波动最大的下属品牌明细（品牌名、品牌ID、订单量、WoW、贡献度）
- 问用户：「要看哪个品牌的五维分析？」

**第二部分：组织维度总览（🚨 强制，不得跳过）**

> **2026-06-12 用户强制规则**：BDM 角色必须输出组织维度数据，禁止跳过。无论品牌维度是否有数据、无论 62059636 是否支持 brand_id group-by，组织维度总览都必须执行并输出。

- 用 `--group-by brand_org_3_mis_ids`（第三级组织维度）+ `--filter brand_org_2_mis_ids=<orgId>` 分组查询，输出每个下属的订单量
- 当期 + 对比期分别查，代码层计算每个下属 WoW
- 明确标出哪些下属的订单量升了（✅）、哪些降了（🔴）
- **组织维度是前线 BDM 总览的必选项，不是可选项。即使品牌维度查询失败/无数据，组织维度也必须执行**
- 问用户：「要不要看降了的下属具体哪些品牌降了？」

**输出**（前线 BD，⚠️ 仅 BD，非 BDM）：
```
📊 你负责的品牌总览（{查询日期} vs 上周同期）
负责品牌总数：XX 个
其中订单量 WoW 为负的品牌：XX 个
```

---

## 3.1 获取品牌 id 列表（直接复用总览结果）

> ⚠️ **不重复查询**：品牌总览已经拿到所有品牌的 fin_ord_num 当期 + 上周同期数据，Step 1 直接从缓存结果中筛选，无需再次请求数据集。

### 方式1：分析异动品牌

从总览缓存结果中筛选 `fin_ord_num` WoW 为负的品牌，按跌幅（WoW）升序（即跌幅最大在前）取 Top X，过滤 brand_id=0。

### 方式2：大盘监控（仅后线/内部）

基于总览缓存结果计算波动贡献：
1. 先读取学城文档 https://km.sankuai.com/collabpage/2729586426，根据监控指标类型确认是否为可加型指标
2. **可加型指标公式（如订单量）**：
   ```
   波动贡献 = (品牌当期 - 品牌对比期) ÷ (大盘当期总量 - 大盘对比期总量) × 100%
   ```
   含义：该品牌的变化量占大盘整体净变化量的比重。分母为大盘净变化量（带符号，非绝对值），大盘仅含 brand_id!=0 的品牌订单。
3. **根据大盘方向分支处理**：
   - **大盘下降（grand_curr < grand_prev）**：按贡献值降序取 Top X 负贡献品牌，输出 Top N 并进行深度分析
   - **大盘上升（grand_curr ≥ grand_prev）**：波动贡献排序对下跌品牌的识别价值低（负贡献品牌绝对量都小），不输出波动贡献 Top X。改为：
     1. 统计总览中 WoW 为负的品牌数量
     2. 输出大盘总览 + 负 WoW 品牌数，询问用户：
        - 「大盘上升，按跌幅排序看 Top X 异动品牌？」
        - 或「指定品牌 ID 查看？」
     3. 用户选定后再按指定方式输出品牌列表进入 Step 2
4. 过滤 brand_id=0

**前线 BDM（选项2）的特殊处理：**

总览阶段已完成品牌维度（按波动贡献排序）+ 组织维度（各下属维值升降）的双重输出，**直接询问用户要深入分析的 brand_id**，无需展示分析方式选项。

- 用户说"看XX品牌" → 直接进入 Step 2
- 用户说"看XX下属的明细" → 对该下属维值做一次品牌级查询，输出该下属负责的品牌中 WoW 为负的明细，再问要深入分析哪个品牌
- 用户说"全部"或"都看看" → 对组织维度中降了的下属逐个输出品牌明细

### 方式3：定向分析

跳过，直接使用用户提供的品牌 id 进入 Step 2。

> ⚠️ Step 1 的唯一目标是**拿到品牌 id 列表**。拿到后立即进入 Step 2，后续所有分析均通过数据集查询完成。不再使用 agent-browser 操作供给大盘看板，不再使用经营沙盘（60049761）。

---

## ⚠️ 模块必须全部输出（必读，不得跳过）

**每个模块无论是否有异常，都必须在最终报告中出现，并用业务语言标题呈现。**

✅ 正确示例：
```
**营业情况**
无异常。27家门店全部在线营业，WoW 无明显变化，无在线未营业门店。

**体验情况**
无异常。品牌级出餐时长 8.33 分钟，商责取消 WoW -25%（改善）。

**活动参与**
无异常。折扣菜 + 减配覆盖率 100%，满折本品牌未参与，与上周持平。

**流量分析**
无异常。品牌级曝光→进店转化率 WoW -1.7%，各渠道均未超 -10% 阈值。

**商补情况**
🔴 异常，品牌商补总额 WoW -12.2%，13家门店下降...（详见明细）
```

❌ 错误示例：只输出有异常的模块，跳过无异常的模块。

---

## ⚠️ 下钻强制规则（必读，任何情况不得违反）

**每个模块只要品牌级指标出现异常，必须继续下钻到门店粒度，列出具体门店 list。禁止只输出品牌层面结论后停止分析。**

| 模块 | 品牌级异常 | 必须下钻内容 |
|------|-----------|-------------|
| 模块1（营业） | 在线数/营业数/时长 WoW 下降 | 列出每家异常门店 id、门店负责人、具体异常类型 |
| 模块2（体验）- 出餐 | avg_cook_min > 15 | 列出超时门店 id、负责人、该店单均出餐时长 |
| 模块2（体验）- 商责 | 商责取消量 WoW 上升 | 列出取消上升门店 id、负责人、**每家门店的取消原因分布（原因 + 数量 + 占比）** |
| 模块3（活动） | 任一活动覆盖率 WoW 下降 | 列出失效门店 id、负责人、失效活动类型、失效时间 |
| 模块4（流量）- CTR | 总 CTR WoW < -10% | **两步必做**：① 品牌级7个渠道 CTR 分别列出 WoW（定位哪个资源位降了）；② 对每个下降的渠道，下钻门店粒度，列出各门店该渠道 CTR 当期值及 WoW |
| 模块4（流量）- 曝光UV | 曝光 UV WoW 下降 | **两步必做**：① 先查品牌级 7 个渠道曝光UV WoW，输出分渠道表格，判断是平台整体流量收缩还是某渠道单独异常；② 对 WoW ≤ -10% 的渠道进一步下钻门店粒度，列出具体门店曝光 WoW、负责人。**① 必须在输出流量模块时自动执行，不得等用户追问** |
| 模块5（补贴） | 商补金额 WoW 下降 | 列出商补下降门店 id、负责人、商补变化金额和幅度 |

❌ **错误示例**："该品牌商责取消上升 20%，需关注体验问题。" → 不可接受，必须列门店。
❌ **错误示例**："曝光→进店转化率 WoW -24.7%，系统性下降。" → 不可接受，必须下钻到渠道和门店。
✅ **正确示例（流量）**：
1. 先列品牌级 7 个资源位 CTR 当期 vs 上周 vs WoW 表格，标注哪些渠道下降
2. 再列门店级明细：哪些门店哪些渠道 CTR 下降、降幅多少
3. 最后给出综合判断（全渠道均降 vs 集中在某几个渠道 vs 集中在某几家门店）

---

## 3.2 单品牌分析

### Step 0：前置查询（⚡ 必须最先执行）

**目标**：通过**供给大盘数据集（ID：62059636）**一次性拉取品牌级所有核心指标的当期值和 WoW，判断哪些维度出现问题，后续模块从本结果路由，无需重复查询。

> ⚠️ **不再使用 Hive SQL（step0_brand_wow_query / step0_exposure_uv_brand_query）**，全部改用 kdata 数据集查询，见 sql-templates.md 的 Step 0 章节。

**执行步骤**：

1. **数据集查询（kdata）**：一次性查出当期 + 上周同期 10 个核心指标，计算 WoW（见 sql-templates.md `step0_dataset_query`）
2. **商责取消 SQL**：
   - **所有角色**：并行执行 `step2_cancel_brand_query`（数据集 62059636，品牌级商责取消绝对量 WoW，供模块2使用）—— **⚠️ 2026-06-10 起前线角色同样可查**

**10 个核心指标及路由规则**：

| 指标 | 单日 Code | 多日 Code | 路由规则（WoW 异常时触发） |
|------|----------|----------|--------------------------|
| 在线商家数 / 店均在线天数 | `online_shop_num` | `shop_avg_shop_actual_online_days` | → 模块1：营业情况 |
| 营业商家数 / 店均营业天数 | `open_shop_num` | `shop_avg_shop_actual_open_days` | → 模块1：营业情况 |
| 店均营业时长（小时） | `shop_avg_open_dura` | `davg_shop_avg_open_dura` | → 模块1：营业情况 |
| 商家单均出餐时长（分） | `shop_oavg_readied_duration` | `shop_oavg_readied_duration`（不变） | → 模块2：体验情况（出餐） |
| 支付成功后商责取消率 | `paid_order_cancel_rate_merchant_reason` | `paid_order_cancel_rate_merchant_reason`（不变） | → 模块2：体验情况（商责取消） |
| 满折活动生效营业商家覆盖率 | `fulldisc_open_shop_coverage` | `davg_fulldisc_open_shop_coverage` | → 模块3：活动参与情况 |
| 折扣菜活动生效营业商家覆盖率 | `discount_product_shop_ratio` | `davg_discount_spu_shop_coverage` | → 模块3：活动参与情况 |
| 减配活动生效营业商家覆盖率 | `reduceshipfee_open_shop_coverage` | `davg_reduceshipfee_shop_coverage` | → 模块3：活动参与情况 |
| 店均商家入口资源位曝光UV | `shop_avg_ad_position_shop_entry_exposure_uv` | `davg_shop_avg_ad_position_shop_entry_exposure_uv` | → 模块4：流量情况（曝光触发） |
| 曝光→进店转化率（CTR） | `shop_entry_exposure_visit_ratio` | `davg_shop_entry_exposure_visit_ratio` | → 模块4：流量情况（CTR触发） |
| 实付商补率 | `actual_shop_charge_amt_ratio` | `actual_shop_charge_amt_ratio`（不变） | → 模块5：补贴情况 |

> ⚠️ **曝光UV 与 CTR 是两个独立的流量触发维度**：曝光UV下降说明算法/广告减少推送（流量入口不足）；CTR下降说明转化效率下降（内容吸引力/活动不足）。两者需分别判断，不能只看其中一个。
> ⚠️ **曝光UV指标说明**：Step 0 和模块4的主曝光指标统一使用「店均商家入口**资源位**曝光UV」（单日：`shop_avg_ad_position_shop_entry_exposure_uv`；多日：`davg_shop_avg_ad_position_shop_entry_exposure_uv`）。**禁止使用 `shop_avg_shop_entry_exposure_uv`**（该字段分母口径不同，会导致数值偏高）。曝光UV下降时，直接查 7 个分渠道曝光UV，找出哪个渠道下降（见模块4第零步「曝光UV下钻」）。

**异常判断参考阈值**：

| 指标类型 | 触发阈值 |
|---------|---------|
| 量类（在线数/营业数） | WoW < -10% |
| 时长类（营业时长） | WoW < -10% |
| 出餐时长 | **绝对值 > 15 分钟 OR WoW > +10%**（两个条件满足其一即触发，不可只判断 WoW） |
| 覆盖率/占比类 | WoW 变化 < -5pp |
| 转化率（CTR） | WoW < -10% |
| 商责取消率 | WoW > +10%（上升为异常） |
| 实付商补率 | 品牌级 WoW < -10%（触发模块5执行）；门店级 WoW < -10% 纳入 Top 10 输出 |

---

### 模块 1：营业情况排查

**触发条件**：无论 Step 0 指标是否异常，**每次必须执行**模块 1 分析（WoW 判断 + 在线未营业判断是两个独立逻辑，均需输出）

**数据来源**：⚠️ **不再使用 Hive SQL**，改用数据集 62059636，按门店粒度查当期 + 上周同期（见 sql-templates.md `step1_shop_detail_query`）

**执行方式**（因单日/多日模式不同，查询参数有差异，见 sql-templates.md `step1_shop_detail_query`）：

代码层执行以下**两层独立判断**：

#### 判断层 1：WoW 同比异常（当期 vs 上周同期对比）

> 只要以下任一指标 WoW 达到阈值，即输出对应异常门店明细。

**单日模式**：group by `shop_id,shop_name,shop_owner_mis_id,is_online_shop,is_open_shop`，measure 取 `shop_avg_open_dura`

| 判断条件 | 异常类型 |
|---------|---------|
| 当期 `is_open_shop=0` AND 上周 `is_open_shop=1` | 🔴 本周新增未营业门店 |
| `shop_avg_open_dura` WoW < -10% | 🔴 营业时长下降（列出当期/上周时长及降幅） |

**多日模式**：group by `shop_id,shop_name,shop_owner_mis_id`，measures 取 `shop_avg_shop_actual_online_days,shop_avg_shop_actual_open_days,davg_shop_avg_open_dura`

| 判断条件 | 异常类型 |
|---------|---------|
| 品牌级 `shop_avg_shop_actual_open_days` vs `shop_avg_shop_actual_online_days` 有差值 → 下钻门店 | 🔴 在线天数 vs 营业天数不一致 |
| 门店级 `shop_avg_shop_actual_open_days` < `shop_avg_shop_actual_online_days` | 🔴 该门店有在线未营业天数 |
| `davg_shop_avg_open_dura` WoW < -10% | 🔴 日均营业时长下降（列出当期/上周时长及降幅） |

> **多日模式下在线未营业的输出规则（性能优先）**：
> - 只输出「在线天数 X 天 vs 营业天数 Y 天，差 Z 天」的汇总，**不逐日下钻展开具体是哪几天**
> - 除非用户明确要求「看具体是哪几天没营业」，才执行逐日下钻（按当期区间每天分别查单日 `is_online_shop=1 AND is_open_shop=0`）
> - 逐日下钻可能因区间过长/门店数量多而超时，用户主动要求时需提前告知风险

#### 判断层 2：当期在线未营业（独立判断，不依赖 WoW 是否异常）

> **无论判断层 1 是否触发，都必须执行此判断并输出结果。**

**单日模式**：

| 判断条件 | 异常类型 |
|---------|---------|
| 当期 `is_online_shop=1` AND `is_open_shop=0` | 🔴 当期在线但未营业 |

**多日模式**：此层判断已融入判断层 1（通过 `shop_avg_shop_actual_online_days` vs `shop_avg_shop_actual_open_days` 差值实现），**无需单独执行**，但必须在输出中说明"多日模式：通过在线天数 vs 营业天数差值判断在线未营业情况"。

即使该品牌 WoW 无异常（在线数/营业数/时长均正常），也需要检查当期是否存在在线但未营业的门店，若有则列出。

**输出**：门店 id、门店名称、负责人（shop_owner_mis_id）、异常类型、营业时长当期值及 WoW（在线未营业门店营业时长填 0 或 N/A）

---

### 模块 2：体验情况排查

**触发条件**：商家单均出餐时长 WoW 异常 / 支付成功后商责取消率 WoW 上升 时触发

**前提条件**：出餐时长分析**针对所有在线且营业的门店**（`is_online_shop=1 AND is_open_shop=1`）；商责取消分析同样针对全品牌门店。

> ⚠️ "仅对营业正常门店执行"的正确含义：**排除当期未营业（`is_open_shop=0`）的门店**，因为未营业门店无出餐数据，不纳入出餐时长计算。并非要求"模块1无异常才执行模块2"——模块1有异常时，模块2照常执行，对其余营业中的门店进行分析。

**数据来源**：
- **出餐时长**：数据集 62059636，门店粒度查当期 + 上周同期（见 `step2_cook_shop_query`）——**后线和前线均可执行**
- **商责取消**：⚠️ **2026-06-10 更新：取消原因下钻改用数据集 62059636 的 `order_cancel_code` + `order_cancellation_reason` 维度，所有角色均可执行，不再依赖 Hive。**
  - **后线/其他角色（选项1/4）**：执行 `step2_cancel_brand_query` + `step2_cancel_shop_query` + `step2_cancel_reason_query`（数据集查询）
  - **前线角色（选项2/3）**：**不再跳过**，同样执行数据集查询三步下钻

**[出餐时长]**

两次 kdata 查询（当期 + 上周同期），group by `shop_id,shop_name,shop_owner_mis_id`，measure 取 `shop_oavg_readied_duration`，代码层对比：

| 判断条件 | 异常类型 |
|---------|---------|
| 当期 `shop_oavg_readied_duration` > 15 分钟 | 🔴 单均出餐超时（>15分钟，**绝对值触发，不依赖 WoW**） |
| WoW > +10% | 🔴 出餐时长明显上升（**相对值触发，即使绝对值未超15min也需输出**） |

> ⚠️ 两个判断条件独立，满足任一即输出异常门店。例：某门店出餐 18min 但 WoW 0%（一直很慢），仍需列入；某门店出餐 12min 但 WoW +50%（骤然变慢），也需列入。

**输出**：门店 id、门店名称、负责人、当期出餐时长、WoW

**[商责取消]**

Step 0 的 `paid_order_cancel_rate_merchant_reason`（取消率）判断品牌级是否异常；
若满足下钻条件，执行数据集三步下钻（所有角色均可执行）：`step2_cancel_brand_query`（绝对量 WoW）→ `step2_cancel_shop_query`（门店排序）→ `step2_cancel_reason_query`（每家门店取消原因分布，按 `order_cancel_code` + `order_cancellation_reason` 维度 group-by）

| 判断条件 | 异常类型 |
|---------|---------|
| 取消率（`paid_order_cancel_rate_merchant_reason`）PoP > +10pp | 🔴 商责取消率上升 |
| 取消量（`paid_order_cancel_num_refund_shop_res`）PoP > +20%（取消率未超阈值但量级显著上升时补充判断） | 🔴 商责取消量上升 |

> ⚠️ 取消率是率类型，PoP 用 pp（百分点差值）；取消量是值类型，PoP 用 %（相对变化）。两者满足其一即下钻。

**输出**：门店 id、负责人、取消量 WoW、取消原因明细（原因 + 数量 + 占比）

---

### 模块 3：活动参与情况排查

**触发条件**：满折/减配/折扣菜活动覆盖率 WoW < -5pp 时触发（仅营业正常门店）

**数据来源**：⚠️ **不再使用 Hive SQL**，改用数据集 62059636 按门店粒度对比当期与上周同期，直接找出活动脱落门店。

**执行方式**（见 sql-templates.md `step3_activity_lapse_query`）：

```bash
# 查当期（current_dt）门店粒度三个活动覆盖率
kdata --json --task-id "$TASK_ID" --task-name "step3_activity_curr:{REGION}:{current_dt}" \
  standard query --dataset 62059636 \
  --measures fulldisc_open_shop_coverage,reduceshipfee_open_shop_coverage,discount_product_shop_ratio \
  --date {current_dt}~{current_dt} \
  --region {REGION} --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id --page-size 500

# 查上周同期（last_week_dt）相同字段
kdata --json --task-id "$TASK_ID" --task-name "step3_activity_prev:{REGION}:{last_week_dt}" \
  standard query --dataset 62059636 \
  --measures fulldisc_open_shop_coverage,reduceshipfee_open_shop_coverage,discount_product_shop_ratio \
  --date {last_week_dt}~{last_week_dt} \
  --region {REGION} --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id --page-size 500
```

**门店脱落判断规则**（代码层对比）：

**单日模式**（覆盖率为当日0/1，可精确判断）：

| 活动类型 | 判断条件 | 异常类型 |
|---------|---------|---------|
| 满折 | 上周 `fulldisc_open_shop_coverage = 100%` AND 当期 `= 0%` | 🔴 满折活动脱落 |
| 减配 | 上周 `reduceshipfee_open_shop_coverage = 100%` AND 当期 `= 0%` | 🔴 减配活动脱落 |
| 折扣菜 | 上周 `discount_product_shop_ratio = 100%` AND 当期 `= 0%` | 🔴 折扣菜活动脱落 |

**多日模式**（覆盖率为日均值，不会精确等于 100% 或 0%，改用 WoW 阈值）：

| 活动类型 | 判断条件 | 异常类型 |
|---------|---------|---------|
| 满折 | `davg_fulldisc_open_shop_coverage` WoW < -50pp | 🔴 满折活动大幅脱落 |
| 减配 | `davg_reduceshipfee_shop_coverage` WoW < -50pp | 🔴 减配活动大幅脱落 |
| 折扣菜 | `davg_discount_spu_shop_coverage` WoW < -50pp | 🔴 折扣菜活动大幅脱落 |

> ⚠️ 多日模式阈值说明：日均覆盖率 WoW 下降 > 50pp（百分点）视为显著脱落。例：上周日均覆盖率 85%，本周日均 25%，差值 -60pp → 触发异常。

> 一家门店可能同时脱落多个活动，合并输出。

**输出**：门店 id、门店名称、门店负责人（shop_owner_mis_id）、脱落的活动类型（可多个）

---

### 模块 4：流量情况排查

**触发条件**：总 CTR（`shop_entry_exposure_visit_ratio`）WoW < -10%，**或**店均商家入口资源位曝光UV（单日：`shop_avg_ad_position_shop_entry_exposure_uv`；多日：`davg_shop_avg_ad_position_shop_entry_exposure_uv`）WoW < -10% 时触发（仅营业正常门店）

**数据来源**：分三步，数据集选用规则如下：
- 第零步（曝光UV）：**数据集 62059636**
- 第一步（渠道CTR）：**首选 62059636**；仅当 62059636 返回 0 行或报错时，fallback 到 60041382（备用），输出时注明「使用 60041382 备用数据」
- 第二步（门店级下钻CTR）：**数据集 62059636**

#### ⚠️ PoP 计算规则（流量模块必读）

| 指标类型 | 计算方式 | 展示格式 |
|---------|---------|---------|
| 曝光UV（值类型） | `(curr - prev) / prev × 100` | +X% / -X% |
| CTR / 转化率（率类型，本身是百分比） | `curr_pct - prev_pct`（百分点差值） | +Xpp / -Xpp |

> ❌ 错误示例：CTR 从 5.0% → 4.5%，不应写 "-10%"，应写 "-0.5pp"
> ✅ 正确示例：曝光UV 从 10000 → 9000，写 "-10%"；CTR 从 5.0% → 4.5%，写 "-0.5pp"

#### 第零步：品牌级曝光UV（先于CTR分析）

**目的**：判断曝光UV是否下降，区分「曝光不足→CTR无意义」和「曝光正常→CTR下降才是问题」。

两次 kdata 查询（当期 + 上周同期），group by `brand_id`（品牌粒度），measure 取曝光UV：

| 模式 | Code | 指标名 |
|------|------|--------|
| 单日 | `shop_avg_ad_position_shop_entry_exposure_uv` | 店均商家入口资源位曝光UV |
| 多日 | `davg_shop_avg_ad_position_shop_entry_exposure_uv` | 日均店均商家入口资源位曝光UV |

代码层计算 WoW（值类型，用 % 表示），标注结论：
- WoW < -10% → 🔴 曝光下降，**进入分渠道曝光UV下钻**（见下方）
- WoW ≥ -10% → 曝光正常，分析重心转向 CTR

#### 曝光UV下钻：分渠道找下降来源

**触发条件**：品牌级曝光UV WoW < -10% 时执行。

两次 kdata 查询（当期 + 上周同期），group by `brand_id`（品牌粒度），measures 取 7 个分渠道曝光UV：

| 单日 Code | 多日 Code | 渠道名 |
|----------|----------|--------|
| `shop_avg_brand_wall_shop_entry_exposure_uv` | `davg_shop_avg_brand_wall_shop_entry_exposure_uv` | 单日：店均商家入口品牌墙曝光UV / 多日：日均店均商家入口品牌墙曝光UV |
| `shop_avg_feeds_shop_entry_exposure_uv` | `davg_shop_avg_feeds_shop_entry_exposure_uv` | 单日：店均商家入口Feeds曝光UV / 多日：日均店均商家入口Feeds曝光UV |
| `shop_avg_search_shop_entry_exposure_uv` | `davg_shop_avg_search_shop_entry_exposure_uv` | 单日：店均商家入口大搜曝光UV / 多日：日均店均商家入口大搜曝光UV |
| `shop_avg_gundam_business_card_shop_entry_exposure_uv` | `davg_shop_avg_gundam_business_card_shop_entry_exposure_uv` | 单日：店均商家入口高达商卡曝光UV / 多日：日均店均商家入口高达商卡曝光UV |
| `shop_avg_homepage_discount_dish_shop_entry_exposure_uv` | `davg_shop_avg_homepage_discount_dish_shop_entry_exposure_uv` | 单日：店均首页商家入口折扣菜卡片曝光UV / 多日：日均店均首页商家入口折扣菜卡片曝光UV |
| `shop_avg_zone_landing_page_shop_entry_exposure_uv` | `davg_shop_avg_zone_landing_page_shop_entry_exposure_uv` | 单日：店均商家入口金刚区商卡曝光UV / 多日：日均店均商家入口金刚区落地页曝光UV |
| `shop_avg_discount_dish_channelpage_shop_entry_exposure_uv` | `davg_shop_avg_discount_dish_channelpage_shop_entry_exposure_uv` | 单日：店均商家入口频道页折扣菜卡片曝光UV / 多日：日均店均商家入口折扣菜频道页曝光UV |

代码层对比各渠道 WoW（**值类型，用 % 表示**），列出所有渠道当期值 + PoP，标注哪些渠道下降（WoW < -10%）。

> ⚠️ **指标 Code 必须从数据集实际字段确认**。若某渠道查询返回空/无字段，在汇总表中填 `—`，不得跳过该渠道不输出。

#### 第一步：品牌级渠道 CTR 定位

**目的**：找出哪个资源位的 CTR 降了。

> ⚠️ **数据集选用：首选 62059636**；仅当 62059636 返回 0 行或报错时，fallback 到 60041382（备用）并在输出中注明。具体命令见 sql-templates.md 第一步方案 A/B。

两次 kdata 查询（当期 + 上周同期），group by `brand_id`（品牌粒度），measures 取 7 个渠道 CTR：

| 单日 Code | 多日 Code | 指标名 |
|----------|----------|--------|
| `brand_wall_shop_entry_exposure_visit_ratio` | `davg_shop_avg_brand_wall_shop_entry_exposure_visit_ratio` | 品牌墙 CTR |
| `feeds_shop_entry_expose_visit_ratio` | `davg_feeds_shop_entry_expose_visit_ratio` | Feeds CTR |
| `search_shop_entry_expose_visit_ratio` | `davg_search_shop_entry_expose_visit_ratio` | 大搜 CTR |
| `gundam_business_card_shop_entry_expose_visit_ratio` | `davg_gundam_business_card_shop_entry_expose_visit_ratio` | 高达商卡 CTR |
| `homepage_discount_dish_shop_entry_expose_visit_ratio` | `davg_homepage_discount_dish_shop_entry_expose_visit_ratio` | 首页折扣菜卡片 CTR |
| `zone_landing_page_shop_entry_expose_visit_ratio` | `davg_zone_landing_page_shop_entry_expose_visit_ratio` | 金刚区商卡 CTR |
| `discount_dish_channelpage_shop_entry_expose_visit_ratio` | `davg_discount_dish_channelpage_shop_entry_expose_visit_ratio` | 频道页折扣菜卡片 CTR |

代码层对比各渠道 WoW（**率类型用 pp，不用 %**），**定位出 CTR 下降的资源位**（可能多个）。

#### 第二步：门店级下钻

**仅对第一步中 CTR 下降的资源位**，重新查询门店粒度：

两次 kdata 查询（当期 + 上周同期），group by `shop_id,shop_name,shop_owner_mis_id`，measures 取**第一步定位到的下降渠道 CTR code**，代码层对比：

| 判断条件 | 异常类型 |
|---------|---------|
| 该渠道 CTR WoW < -10%（pp差值绝对值 > 1pp 且相对变化 > 10%） | 🔴 该资源位进店转化率下降 |

> ⚠️ CTR 的 WoW 判断：既考虑相对变化（>10%），也要看 pp 绝对差值（>1pp），避免 0.1%→0.09% 这种无意义变化被误报。

列出异常门店 id、门店名称、负责人、下降渠道名称、当期 CTR 值（绝对值）及 PoP（pp）。

> 一家门店可能在多个渠道同时下降，合并输出。

**输出**：
- 品牌级曝光UV：当期值、PoP（%）、异常/正常结论
- 品牌级CTR：各资源位 CTR 当期值 + PoP（pp）汇总，标注哪些渠道异常
- 门店级：异常门店 id、负责人、具体下降资源位、CTR 当期值及 PoP（pp）

---

### 模块 5：补贴情况排查

**触发条件**：实付商补率（`actual_shop_charge_amt_ratio`）品牌级 WoW < -10% 时触发（仅营业正常门店）

> ⚠️ **商补指标变更（2026-04-21 用户确认）**：不再使用实付补贴率（`actual_disc_ratio`），改用**实付商补率**（`actual_shop_charge_amt_ratio`）作为触发指标和分析指标。

**数据来源**：⚠️ **不再使用 Hive SQL**，改用数据集 62059636，按门店粒度查当期 + 上周同期（见 sql-templates.md `step5_subsidy_shop_query`）

**执行方式**：两次 kdata 查询（当期 + 上周同期），group by `shop_id,shop_name,shop_owner_mis_id`，measure 取 `actual_shop_charge_amt_ratio`，代码层对比：

| 判断条件 | 异常类型 |
|---------|---------|
| 品牌级 `actual_shop_charge_amt_ratio` WoW < -10% | 🔴 触发模块5，下钻门店 |
| 门店级 `actual_shop_charge_amt_ratio` WoW < -10% | 🔴 该门店实付商补率下降，纳入 Top 10 输出 |

**输出规则（2026-04-21 确认）**：
- 对比当期 vs 上周同期，按实付商补率 WoW 降幅降序排列
- **输出 Top 10 下降门店明细**（不截断，直接给 Top 10，不用提示是否输出完整列表）
- 输出字段：shop_id、门店名称、负责人（shop_owner_mis_id）、实付商补率当期值、上周值、WoW

---

## 最终汇总

完成 5 个模块后，按**门店粒度**合并所有结果：

- 同一门店可能在多个模块存在异常，合并到同一行输出
- 按异常模块数量降序排列（多模块异常的门店优先展示）
- 输出格式见 `output-format.md`

**汇总逻辑示例**：

```
门店 A：模块1（在线未营业）+ 模块3（满折失效）→ 合并为一行，异常模块列显示多个
门店 B：仅模块2（出餐超时）→ 单行输出
门店 C：模块4（品牌墙曝光-45%）+ 模块5（商补金额-20%）→ 合并为一行
```
