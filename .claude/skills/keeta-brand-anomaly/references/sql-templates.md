# SQL 模板

> **执行规则**：
> - **数据集查询**：使用 `kdata standard query` 命令（本文件绝大多数场景）
> - **Hive SQL**：使用 `kdata hive run <sql_file> --project 109495`（SQL 必须存文件，不能直接传长字符串）
> - ⛔ `/tmp/keeta_sql_runner_v4.py` 已废弃，禁止使用（依赖 agent-browser cookie，容器内不可用）
> - 不要让用户感知到在跑 SQL，直接将结果融入诊断结论输出
> - SQL 执行失败时，将完整 SQL 输出给用户，请用户在万象 SQL 探数页面手动执行后粘贴结果
>
> ⚠️ **数据时效说明（重要）**：所有 Hive 表均为**离线数据**，最新只有 **t-1（昨天）**的数据。用户说"查最新一天"、"查今天"、"查最近数据"时，一律理解为 **t-1**，即今天日期减1天。禁止用今天日期作为 `dt` 查询，否则查不到数据。
>
> ⚠️ **已知限制**：bi.keetapp.com Sinux 权限引擎对含 `GROUP BY` 的 SQL 存在 AST 解析 bug（code=40018），会错误报"鉴权解析异常"。
> **绕过方法**：若单条 GROUP BY SQL 失败，拆成多条 COUNT(1) + WHERE 精确过滤的子查询，在代码层合并计算 WoW。
>
> ⚠️ **数值解析必读（千分位逗号陷阱）**：kdata JSON 返回的所有数值字段均为**带千分位逗号的字符串**（如 `"2,608"`、`"12,345"`），直接 `int(val)` 会报错或得到错误结果。**必须先 `.replace(',', '')` 再转换**：
> - ✅ 正确：`int(str(r.get('fin_ord_num', '0')).replace(',', ''))`
> - ❌ 错误：`int(r['fin_ord_num'])`（ValueError 或结果为 0）
> - rows 结构为 **dict 列表**（非 list of list），取值用 `r.get('field_name', '0')`
> - 推荐统一用 `2>/dev/null` 处理 stderr，stdout 即为纯 JSON

> ⚠️ **kdata 埋点关键规则（必须严格遵守）**：
>
> **① session 共享**：本文件所有 kdata 命令中 `--task-id` 必须使用 `skill_tracker.py start` 生成并导出的同一个 `TASK_ID`（即品牌异动分析的会话 UUID），**禁止**在每条命令前用 `python3 -c "import uuid; print(uuid.uuid4())"` 重新生成新 UUID。这是 brand-anomaly session 与 keeta-data-query 埋点关联的唯一手段。
>
> ❌ 错误（每条命令各自生成新 UUID，导致 session 断开）：
> ```bash
> TASK_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
> kdata --json --task-id "$TASK_ID" ...
> ```
>
> ✅ 正确（直接用 brand-anomaly 会话 UUID 字面量）：
> ```bash
> kdata --json --task-id "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" ...   # 填入 TASK_ID 实际值
> ```
>
> **② task-name 须携带上下文**：`--task-name` 的值会被 keeta-data-query 记录为 `input_content`，必须包含 `region` 和日期，格式：`"{step_label}:{REGION}:{date_or_range}"`。
>
> ❌ 错误（仅有步骤标签，无法从埋点定位问题）：
> ```bash
> --task-name "brand_overview_curr"
> ```
>
> ✅ 正确（含 region 和日期，埋点可读）：
> ```bash
> --task-name "brand_overview_curr:BR:20260512~20260518"
> ```
>
> 本文件所有 `--task-name` 模板均需在执行时按此规则追加 `:{REGION}:{date_range}`。

---

## 前置品牌总览（brand_overview_query）

> 第三步确认查询日期后立即自动执行。结果同时用于：1）向用户展示品牌总览；2）Step 1 直接复用，无需重复查询。
> ⚠️ **单日/多日模式的 `--date` 参数不同**，必须与用户选择的分析周期保持一致。

**单日模式**：
```bash
# 查当期（单日，⚠️ page-size 必须 ≥ total 行数，推荐 5000）
kdata --json --task-id "$TASK_ID" --task-name "brand_overview_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures fin_ord_num \
  --date {current_dt}~{current_dt} \
  --region {REGION} \
  --group-by brand_id,brand_name \
  --page-size 5000

# 查上周同期（单日）
kdata --json --task-id "$TASK_ID" --task-name "brand_overview_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures fin_ord_num \
  --date {last_week_dt}~{last_week_dt} \
  --region {REGION} \
  --group-by brand_id,brand_name \
  --page-size 5000
```

**多日模式**（用户选择周/月/自定义区间）：
```bash
# 查当期区间（多日，⚠️ page-size 必须 ≥ total 行数，推荐 5000）
kdata --json --task-id "$TASK_ID" --task-name "brand_overview_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures fin_ord_num \
  --date {current_start}~{current_end} \
  --region {REGION} \
  --group-by brand_id,brand_name \
  --page-size 5000

# 查对比期区间（多日）
kdata --json --task-id "$TASK_ID" --task-name "brand_overview_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures fin_ord_num \
  --date {prev_start}~{prev_end} \
  --region {REGION} \
  --group-by brand_id,brand_name \
  --page-size 5000
```

**前线 BDM/BD 额外参数（每条命令都必须加）**：
```
  --biz-type {bizType} --filter {dimCode}={orgId}
```

**代码层处理**：
- **过滤 `brand_id == "0"` 的行**（不是真实品牌，必须剔除，不参与任何计算）
- JOIN 两次过滤后的结果计算 WoW = (curr - prev) / prev
- 统计总品牌数 = 过滤后行数；WoW 为负品牌数 = 过滤后 WoW<0 的行数
- 缓存完整过滤后结果供 Step 1 复用（方式1：筛 WoW<0 按跌幅排序；方式2：算贡献排序）

---

### 前线 BDM 组织维度总览查询（🚨 强制，不得跳过）

> **2026-06-12 用户强制规则**：BDM 角色必须执行组织维度查询并输出，禁止跳过。即使品牌维度查询失败/无数据（如 62059636 不支持 brand_id group-by），组织维度也必须执行。

**单日模式**：
```bash
# 查当期（单日）
kdata --json --task-id "$TASK_ID" --task-name "org_overview_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures fin_ord_num \
  --date {current_dt}~{current_dt} \
  --region {REGION} \
  --biz-type {bizType} \
  --filter {dimCode}={orgId} \
  --group-by brand_org_3_mis_ids \
  --page-size 100

# 查上周同期（单日）
kdata --json --task-id "$TASK_ID" --task-name "org_overview_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures fin_ord_num \
  --date {last_week_dt}~{last_week_dt} \
  --region {REGION} \
  --biz-type {bizType} \
  --filter {dimCode}={orgId} \
  --group-by brand_org_3_mis_ids \
  --page-size 100
```

**多日模式**（周/月/自定义区间）：
```bash
# 查当期区间（多日）
kdata --json --task-id "$TASK_ID" --task-name "org_overview_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures fin_ord_num \
  --date {current_start}~{current_end} \
  --region {REGION} \
  --biz-type {bizType} \
  --filter {dimCode}={orgId} \
  --group-by brand_org_3_mis_ids \
  --page-size 100

# 查对比期区间（多日）
kdata --json --task-id "$TASK_ID" --task-name "org_overview_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures fin_ord_num \
  --date {prev_start}~{prev_end} \
  --region {REGION} \
  --biz-type {bizType} \
  --filter {dimCode}={orgId} \
  --group-by brand_org_3_mis_ids \
  --page-size 100
```

**代码层处理**：
- 当期 + 对比期分别查，JOIN 按 `brand_org_3_mis_ids` 计算每个下属 WoW
- 明确标出 ✅（WoW ≥ 0）和 🔴（WoW < 0）
- **组织维度是 BDM 总览的必选项**，与品牌维度并列，缺一不可

> 🚨 **大盘总量计算规则（严禁直接用无 filter 的聚合查询）**
>
> ⚠️ **kdata `--filter` 只支持 `code=value` 等于语法，不支持 `!=`**，因此无法在聚合查询中直接排除 brand_id=0。
>
> **正确做法（两步）**：
> 1. 不带 `--group-by` 执行聚合查询，得到含 brand_id=0 的全量总量 `raw_total`
> 2. 从分组查询结果中找到 `brand_id=0` 的行，取其 `fin_ord_num` 为 `unattributed`
> 3. `grand_total = raw_total - unattributed`（若分组查询中无 brand_id=0 行，则 `unattributed = 0`）
>
> ⚠️ 分组查询 `--page-size` 必须 ≥ 实际品牌数（推荐 10000），否则截断导致 brand_id=0 可能被漏掉。验证：`len(rows) == total` 字段才说明完整。
>
> ```bash
> # 第一步：全量聚合查询（含 brand_id=0，当期）
> kdata --json --task-id "$TASK_ID" --task-name "region_total_curr:{REGION}:{date_or_range}" \
>   standard query \
>   --dataset 62059636 \
>   --measures fin_ord_num \
>   --date {current_dt}~{current_dt} \
>   --region {REGION}
> # 结果：raw_total_curr = int(rows[0]['fin_ord_num'].replace(',',''))
>
> # 第二步：从分组明细（已用 page-size 10000 全量拉取）中取 brand_id=0 的值
> # unattributed_curr = int(brand0_row['fin_ord_num'].replace(',',''))  （若无此行则为 0）
>
> # 第三步：计算正确大盘
> # grand_curr = raw_total_curr - unattributed_curr
> # grand_prev = raw_total_prev - unattributed_prev
> ```
>
> 大盘 WoW = (grand_curr - grand_prev) / grand_prev × 100%，用这两个数计算，不得直接用 raw_total。

---

## Step 1: 大盘整体表现（供给大盘数据集 62059636）

> ⚠️ **统一使用数据集 62059636**，不再使用经营沙盘（60049761）。
> 默认监控指标为 `fin_ord_num`（完成订单量），可按需替换为其他指标。

### 路径 A：波动贡献排序 — kdata 命令

> ⚠️ **分页陷阱（必读）**：`--page-size` 默认 500，但 HK 品牌数量超过 3000 行。
> **必须使用 `--page-size 5000`（或更大值）** 才能拿到全量数据，否则品牌维度聚合总量严重偏低，波动贡献计算结果不可信。
> 验证方法：查询结果中 `total` 字段 = 实际返回行数，两者相等才说明数据完整。

```bash
# 第一步：读学城文档，确认监控指标对应的波动贡献公式
# https://km.sankuai.com/collabpage/2729586426

# 第二步：查当期所有品牌的监控指标（⚠️ page-size 必须 ≥ total 行数，推荐 5000）
kdata --json --task-id "$TASK_ID" --task-name "step1_rank_curr:{REGION}:{date_or_range}" \
  standard query --dataset 62059636 --measures {metric} \
  --date {current_dt}~{current_dt} --region {REGION} \
  --group-by brand_id,brand_name --page-size 5000

# 第三步：查上周同期所有品牌的监控指标（同样 page-size 5000）
kdata --json --task-id "$TASK_ID" --task-name "step1_rank_prev:{REGION}:{date_or_range}" \
  standard query --dataset 62059636 --measures {metric} \
  --date {last_week_dt}~{last_week_dt} --region {REGION} \
  --group-by brand_id,brand_name --page-size 5000

# 第四步：在代码层计算波动贡献
# ❗️ 先过滤 brand_id=="0" 的行，再计算
# 可加型指标公式：贡献度 = (品牌当期 - 品牌对比期) ÷ (大盘当期总量 - 大盘对比期总量) × 100%
# 分母为大盘总量变化量（带符号，大盘下降时为负値）
# 按贡献降序取 Top X（大盘下跌时，贡献值最大的品牌就是拖累最大的）
```

> ⚠️ kdata 数值解析：所有数值字段均为带千分位逗号的字符串（如 `"2,608"`），必须用 `str(val).replace(',','')` 再转 int/float；推荐用 `2>/dev/null` 处理 stderr，stdout 即为纯 JSON

### 路径 B：指标降序 — kdata 命令

```bash
# 查当期监控指标品牌排序，过滤 brand_id=0，降序取 Top X
kdata --json --task-id "$TASK_ID" --task-name "step1_metric_rank:{REGION}:{date_or_range}" \
  standard query --dataset 62059636 --measures {metric} \
  --date {current_dt}~{current_dt} --region {REGION} \
  --group-by brand_id,brand_name --page-size 5000
```

---

## Step 0: 前置查询（品牌级 WoW 总览）

> ⚠️ **不再使用 Hive SQL**，改用**供给大盘数据集（ID：62059636）**通过 kdata 查询。
> `step0_brand_wow_query` 和 `step0_exposure_uv_brand_query` 已废弃，由下方 `step0_dataset_query` 替代。

### step0_dataset_query：品牌级 10 个核心指标（当期 + 上周同期）

使用 `kdata standard query` 分两次查出当期和上周同期数据，在代码层计算 WoW。

> ⚠️ **单日/多日模式切换**：根据用户选择的查询周期，`--measures` 中的指标 Code 不同，见下方两套命令。

**单日模式**（用户选择单天）：
```bash
# ===== 查当期（单日）=====
kdata --json --task-id "$TASK_ID" --task-name "step0_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures online_shop_num,open_shop_num,shop_avg_open_dura,shop_oavg_readied_duration,paid_order_cancel_rate_merchant_reason,fulldisc_open_shop_coverage,discount_product_shop_ratio,reduceshipfee_open_shop_coverage,shop_avg_ad_position_shop_entry_exposure_uv,shop_entry_exposure_visit_ratio,actual_shop_charge_amt_ratio \
  --date {current_dt}~{current_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10

# ===== 查上周同期（单日）=====
kdata --json --task-id "$TASK_ID" --task-name "step0_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures online_shop_num,open_shop_num,shop_avg_open_dura,shop_oavg_readied_duration,paid_order_cancel_rate_merchant_reason,fulldisc_open_shop_coverage,discount_product_shop_ratio,reduceshipfee_open_shop_coverage,shop_avg_ad_position_shop_entry_exposure_uv,shop_entry_exposure_visit_ratio,actual_shop_charge_amt_ratio \
  --date {last_week_dt}~{last_week_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10
```

**多日模式**（用户选择周/月/自定义区间）：
```bash
# ===== 查当期（多日）=====
kdata --json --task-id "$TASK_ID" --task-name "step0_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures fin_ord_num,shop_avg_shop_actual_online_days,shop_avg_shop_actual_open_days,davg_shop_avg_open_dura,shop_oavg_readied_duration,paid_order_cancel_rate_merchant_reason,davg_fulldisc_open_shop_coverage,davg_discount_spu_shop_coverage,davg_reduceshipfee_shop_coverage,davg_shop_avg_ad_position_shop_entry_exposure_uv,davg_shop_entry_exposure_visit_ratio,actual_shop_charge_amt_ratio \
  --date {current_start}~{current_end} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10

# ===== 查对比期（多日）=====
kdata --json --task-id "$TASK_ID" --task-name "step0_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures fin_ord_num,shop_avg_shop_actual_online_days,shop_avg_shop_actual_open_days,davg_shop_avg_open_dura,shop_oavg_readied_duration,paid_order_cancel_rate_merchant_reason,davg_fulldisc_open_shop_coverage,davg_discount_spu_shop_coverage,davg_reduceshipfee_shop_coverage,davg_shop_avg_ad_position_shop_entry_exposure_uv,davg_shop_entry_exposure_visit_ratio,actual_shop_charge_amt_ratio \
  --date {prev_start}~{prev_end} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10
```

> ⚠️ kdata 输出解析：推荐用 `2>/dev/null` 过滤 stderr，stdout 即纯 JSON；所有数值字段均为带千分位逗号字符串，解析前必须 `str(val).replace(',','')` 再转 int/float

**指标说明与模块路由**：

| 单日 Code | 多日 Code | 指标含义 | PoP 异常阈值 | PoP 计算方式 | 路由模块 |
|----------|----------|---------|------------|------------|---------|
| `online_shop_num` | `shop_avg_shop_actual_online_days` | 在线商家数 / 店均在线天数 | PoP < -10% | % （值类型） | 模块1：营业 |
| `open_shop_num` | `shop_avg_shop_actual_open_days` | 营业商家数 / 店均营业天数 | PoP < -10% | % （值类型） | 模块1：营业 |
| `shop_avg_open_dura` | `davg_shop_avg_open_dura` | 店均营业时长（小时）/ 日均店均营业时长（小时） | PoP < -10% | % （值类型） | 模块1：营业 |
| `shop_oavg_readied_duration` | `shop_oavg_readied_duration`（不变） | 商家单均出餐时长（分钟） | 当期 > 15 或 PoP > +10% | % （值类型） | 模块2：体验 |
| `paid_order_cancel_rate_merchant_reason` | `paid_order_cancel_rate_merchant_reason`（不变） | 支付成功后商责取消率 | PoP > +10pp | pp（率类型） | 模块2：体验 |
| `fulldisc_open_shop_coverage` | `davg_fulldisc_open_shop_coverage` | 满折活动生效营业商家覆盖率 / 日均满折活动生效营业商家覆盖率 | PoP < -5pp | pp（率类型） | 模块3：活动 |
| `discount_product_shop_ratio` | `davg_discount_spu_shop_coverage` | 折扣菜活动生效营业商家覆盖率 / 日均折扣菜活动生效营业商家覆盖率 | PoP < -5pp | pp（率类型） | 模块3：活动 |
| `reduceshipfee_open_shop_coverage` | `davg_reduceshipfee_shop_coverage` | 减配活动生效营业商家覆盖率 / 日均减配活动生效营业商家覆盖率 | PoP < -5pp | pp（率类型） | 模块3：活动 |
| `shop_avg_ad_position_shop_entry_exposure_uv` | `davg_shop_avg_ad_position_shop_entry_exposure_uv` | **店均商家入口资源位曝光UV**（主曝光指标，单日模式必用）/ 日均店均商家入口资源位曝光UV | PoP < -10% | % （值类型） | 模块4：流量（主曝光触发）|
| ~~`shop_avg_ad_position_shop_entry_exposure_uv`~~ | ~~`davg_shop_avg_ad_position_shop_entry_exposure_uv`~~ | ~~店均商家入口曝光UV~~（**⚠️ 禁止在流量渠道模块使用此字段**，分母口径与资源位曝光UV不同，会得到偏高数值，需用 `shop_avg_ad_position_shop_entry_exposure_uv`） | — | — | **禁用** |
| `shop_avg_brand_wall_shop_entry_exposure_uv` | `davg_shop_avg_brand_wall_shop_entry_exposure_uv` | 店均商家入口品牌墙曝光UV | PoP < -10% | % （值类型） | 模块4：流量 |
| `shop_avg_feeds_shop_entry_exposure_uv` | `davg_shop_avg_feeds_shop_entry_exposure_uv` | 店均商家入口Feeds曝光UV | PoP < -10% | % （值类型） | 模块4：流量 |
| `shop_avg_search_shop_entry_exposure_uv` | `davg_shop_avg_search_shop_entry_exposure_uv` | 店均商家入口大搜曝光UV | PoP < -10% | % （值类型） | 模块4：流量 |
| `shop_avg_gundam_business_card_shop_entry_exposure_uv` | `davg_shop_avg_gundam_business_card_shop_entry_exposure_uv` | 店均商家入口高达商卡曝光UV | PoP < -10% | % （值类型） | 模块4：流量 |
| `shop_avg_homepage_discount_dish_shop_entry_exposure_uv` | `davg_shop_avg_homepage_discount_dish_shop_entry_exposure_uv` | 店均首页商家入口折扣菜卡片曝光UV | PoP < -10% | % （值类型） | 模块4：流量 |
| `shop_avg_zone_landing_page_shop_entry_exposure_uv` | `davg_shop_avg_zone_landing_page_shop_entry_exposure_uv` | 店均商家入口金刚区落地页曝光UV | PoP < -10% | % （值类型） | 模块4：流量 |
| `shop_avg_discount_dish_channelpage_shop_entry_exposure_uv` | `davg_shop_avg_discount_dish_channelpage_shop_entry_exposure_uv` | 店均商家入口折扣菜频道页曝光UV | PoP < -10% | % （值类型） | 模块4：流量 |
| `shop_entry_exposure_visit_ratio` | `davg_shop_entry_exposure_visit_ratio` | 曝光→进店转化率（CTR）/ 日均店均商家入口曝光→进店转化率（CTR） | PoP < -10%（pp绝对差 > 1pp） | pp（率类型） | 模块4：流量 |
| `actual_shop_charge_amt_ratio` | `actual_shop_charge_amt_ratio`（不变） | 实付商补率（2026-04-21起替换 actual_disc_ratio） | PoP < -10% | pp（率类型） | 模块5：补贴 |
| — | `fin_ord_num`（多日新增，SUM求和） | 订单量 | 展示用，不做路由触发 | % （值类型） | — |

**PoP 计算规则（必须严格区分，不得混用）**：
- **值类型**（量类、时长类、UV类）：`PoP = (curr - prev) / prev × 100`，展示为 `+X% / -X%`
- **率/占比类**（覆盖率、CTR、商补率、商责取消率等本身以百分比表达）：`PoP = curr_pct - prev_pct`，展示为 `+Xpp / -Xpp`
- 当期出餐时长绝对值直接读 `shop_oavg_readied_duration` 当期值

> ❌ 错误：商补率从 8.5% → 6.1%，写"-28.3%"
> ✅ 正确：商补率从 8.5% → 6.1%，写"-2.4pp"

---

## 模块 1: 营业情况（门店级下钻）

> ⚠️ **不再使用 Hive SQL**，改用数据集 62059636 按门店粒度对比当期与上周同期。

### step1_shop_detail_query：找出营业异常门店（kdata 数据集查询）

> ⚠️ **单日/多日模式，查询参数不同**，见下方两套命令。

**单日模式**：
```bash
# 查当期（单日）
kdata --json --task-id "$TASK_ID" --task-name "step1_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures shop_avg_open_dura \
  --date {current_dt}~{current_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id,is_online_shop,is_open_shop \
  --page-size 500

# 查上周同期（单日）
kdata --json --task-id "$TASK_ID" --task-name "step1_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures shop_avg_open_dura \
  --date {last_week_dt}~{last_week_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id,is_online_shop,is_open_shop \
  --page-size 500
```

**多日模式**：
```bash
# 查当期（多日）
kdata --json --task-id "$TASK_ID" --task-name "step1_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures shop_avg_shop_actual_online_days,shop_avg_shop_actual_open_days,davg_shop_avg_open_dura \
  --date {current_start}~{current_end} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id \
  --page-size 500

# 查对比期（多日）
kdata --json --task-id "$TASK_ID" --task-name "step1_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures shop_avg_shop_actual_online_days,shop_avg_shop_actual_open_days,davg_shop_avg_open_dura \
  --date {prev_start}~{prev_end} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id \
  --page-size 500
```

> 多日模式：若发现某门店 `shop_avg_shop_actual_open_days` < `shop_avg_shop_actual_online_days`，需进一步逐日下钻，对当期区间内每天执行**单日模式**查询，找出具体哪几天 `is_online_shop=1 AND is_open_shop=0`。

**代码层异常判断**（以 shop_id 为 key JOIN 两次结果）：

```python
abnormal_shops = []
for shop_id, curr in curr_dict.items():
    prev = prev_dict.get(shop_id, {})
    issues = []
    # 在线但未营业
    if curr.get('is_online_shop') == '1' and curr.get('is_open_shop') == '0':
        issues.append('在线但未营业')
    # 本周新增未营业（上周营业，本周未营业）
    elif prev.get('is_open_shop') == '1' and curr.get('is_open_shop') == '0':
        issues.append('本周新增未营业')
    # 营业时长下降 > 10%
    curr_dur = float(curr.get('shop_avg_open_dura') or 0)
    prev_dur = float(prev.get('shop_avg_open_dura') or 0)
    if prev_dur > 0 and (curr_dur - prev_dur) / prev_dur < -0.1:
        wow_pct = round((curr_dur - prev_dur) / prev_dur * 100, 1)
        issues.append(f'营业时长下降 {wow_pct}%（{prev_dur}h→{curr_dur}h）')
    if issues:
        abnormal_shops.append({
            'shop_id': shop_id,
            'shop_name': curr.get('shop_name'),
            'shop_owner_mis_id': curr.get('shop_owner_mis_id'),
            'issues': issues
        })
```

**输出字段**：shop_id、shop_name、shop_owner_mis_id、issues（异常类型列表）

---

## 模块 2: 体验情况

### step2_cancel_brand_query：品牌级商责取消量 WoW（数据集，优先使用）

> ⚠️ **不再使用 Hive SQL 查品牌/门店级取消量**，改用数据集 62059636 的 `shop_pos_cancel_ord_num`（商家取消订单量）指标。
> **只有当品牌级 WoW 异常（> +10%）时，才下钻拆取消原因**（使用数据集 62059636，无需 Hive）。

**单日模式**：
```bash
# 查当期品牌级商责取消量（单日）
kdata --json --task-id "$TASK_ID" --task-name "step2_cancel_brand_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures paid_order_cancel_num_refund_shop_res \
  --date {current_dt}~{current_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10

# 查上周同期（单日）
kdata --json --task-id "$TASK_ID" --task-name "step2_cancel_brand_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures paid_order_cancel_num_refund_shop_res \
  --date {last_week_dt}~{last_week_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10
```

**多日模式**：
```bash
# 查当期品牌级商责取消量（多日）
kdata --json --task-id "$TASK_ID" --task-name "step2_cancel_brand_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures paid_order_cancel_num_refund_shop_res \
  --date {current_start}~{current_end} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10

# 查对比期（多日）
kdata --json --task-id "$TASK_ID" --task-name "step2_cancel_brand_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures paid_order_cancel_num_refund_shop_res \
  --date {prev_start}~{prev_end} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10
```

**触发门店下钻条件**：品牌级 `paid_order_cancel_rate_merchant_reason`（取消**率**）PoP > +10pp，**或** `paid_order_cancel_num_refund_shop_res`（取消**量**）PoP > +20%，两者满足其一即触发

> ⚠️ 取消率是率类型，PoP 用 pp（百分点差值）；取消量是值类型，PoP 用 %（相对变化）。优先以取消率为主判断依据，取消量上升但取消率小幅变动时（如基数极低），综合判断后决定是否下钻。

### step2_cancel_shop_query：门店级商责取消量 WoW（数据集）

> 品牌级触发后，查门店粒度，找出哪些门店取消量在升。

**单日模式**：
```bash
kdata --json --task-id "$TASK_ID" --task-name "step2_cancel_shop_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures paid_order_cancel_num_refund_shop_res \
  --date {current_dt}~{current_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id \
  --page-size 500

kdata --json --task-id "$TASK_ID" --task-name "step2_cancel_shop_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures paid_order_cancel_num_refund_shop_res \
  --date {last_week_dt}~{last_week_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id \
  --page-size 500
```

**多日模式**：将 `--date` 分别换为 `{current_start}~{current_end}` 和 `{prev_start}~{prev_end}`。

**代码层逻辑**：找出 PoP > +10% 的门店，记录 shop_id + 负责人 + 取消量 curr/prev/PoP。

### step2_cancel_reason_query：门店商责取消原因明细（数据集，所有角色可用）

> ⚠️ **2026-06-10 更新**：原 Hive SQL 方案废弃，改用数据集 62059636 的 `order_cancel_code` + `order_cancellation_reason` 维度下钻，**前线/后线所有角色均可执行**，无需 Hive 权限。
>
> 触发条件：上方 step2_cancel_shop_query 确认存在门店 `paid_order_cancel_num_refund_shop_res` PoP > +10% 后，对这些**异常门店逐个**执行本查询。
> 不得默认执行，必须先确认门店级取消量异常再下钻。

**单日模式**（对每个异常门店查当期取消原因分布）：
```bash
# 查当期取消原因分布（单日）
kdata --json --task-id "$TASK_ID" --task-name "step2_cancel_reason_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures paid_order_cancel_num_refund_shop_res \
  --date {current_dt}~{current_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --filter "shop_id={shop_id}" \
  --group-by shop_id,shop_name,order_cancel_code,order_cancellation_reason \
  --order-by paid_order_cancel_num_refund_shop_res=DESC \
  --page-size 50

# 查上周同期取消原因分布（单日）
kdata --json --task-id "$TASK_ID" --task-name "step2_cancel_reason_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures paid_order_cancel_num_refund_shop_res \
  --date {last_week_dt}~{last_week_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --filter "shop_id={shop_id}" \
  --group-by shop_id,shop_name,order_cancel_code,order_cancellation_reason \
  --order-by paid_order_cancel_num_refund_shop_res=DESC \
  --page-size 50
```

**多日模式**：将 `--date` 分别换为 `{current_start}~{current_end}` 和 `{prev_start}~{prev_end}`。

**代码层逻辑**：
- JOIN 两期结果，按当期取消量降序，取 Top 5 原因
- 输出格式：`{order_cancellation_reason}（code: {order_cancel_code}）：当期 X 单 vs 上期 Y 单，PoP +Z%`
- 若某原因当期有但上期无（新出现），标注「🆕 新增原因」
- 若 `order_cancellation_reason` 为空，直接展示 `order_cancel_code`

### step2_cook_shop_query：门店级出餐时长（kdata 数据集查询）

> ⚠️ **不再使用 Hive SQL**，改用数据集 62059636。

```bash
# 查当期
kdata --json --task-id "$TASK_ID" --task-name "step2_cook_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures shop_oavg_readied_duration \
  --date {current_dt}~{current_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id \
  --page-size 500

# 查上周同期
kdata --json --task-id "$TASK_ID" --task-name "step2_cook_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures shop_oavg_readied_duration \
  --date {last_week_dt}~{last_week_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id \
  --page-size 500
```

**代码层异常判断**：当期 `shop_oavg_readied_duration` > 15 分钟，或 WoW > +10%

---

## 模块 3: 活动参与情况

> ⚠️ **不再使用 Hive SQL**，改用数据集 62059636 按门店粒度对比当期与上周同期，直接找出活动脱落门店。
> `step3_fulldiscount_lapse_query`、`step3_reduceshipfee_lapse_query`、`step3_discount_product_change_query` 已废弃。

### step3_activity_lapse_query：活动脱落门店（kdata 数据集查询）

> ⚠️ **单日/多日模式，指标 Code 不同**，见下方两套命令。

**单日模式**：
```bash
# 查当期（单日）
kdata --json --task-id "$TASK_ID" --task-name "step3_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures fulldisc_open_shop_coverage,reduceshipfee_open_shop_coverage,discount_product_shop_ratio \
  --date {current_dt}~{current_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id \
  --page-size 500

# 查上周同期（单日）
kdata --json --task-id "$TASK_ID" --task-name "step3_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures fulldisc_open_shop_coverage,reduceshipfee_open_shop_coverage,discount_product_shop_ratio \
  --date {last_week_dt}~{last_week_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id \
  --page-size 500
```

**多日模式**：
```bash
# 查当期（多日）
kdata --json --task-id "$TASK_ID" --task-name "step3_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures davg_fulldisc_open_shop_coverage,davg_reduceshipfee_shop_coverage,davg_discount_spu_shop_coverage \
  --date {current_start}~{current_end} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id \
  --page-size 500

# 查对比期（多日）
kdata --json --task-id "$TASK_ID" --task-name "step3_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures davg_fulldisc_open_shop_coverage,davg_reduceshipfee_shop_coverage,davg_discount_spu_shop_coverage \
  --date {prev_start}~{prev_end} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id \
  --page-size 500
```

**代码层对比逻辑**（以 shop_id 为 key JOIN 两次查询结果）：

```python
# 单日模式：精确判断（0% vs 100%）
def check_lapsed_single(curr, prev):
    lapsed = []
    if prev.get('fulldisc_open_shop_coverage') == '100.00%' and curr.get('fulldisc_open_shop_coverage') == '0.00%':
        lapsed.append('满折')
    if prev.get('reduceshipfee_open_shop_coverage') == '100.00%' and curr.get('reduceshipfee_open_shop_coverage') == '0.00%':
        lapsed.append('减配')
    if prev.get('discount_product_shop_ratio') == '100.00%' and curr.get('discount_product_shop_ratio') == '0.00%':
        lapsed.append('折扣菜')
    return lapsed

# 多日模式：阈值判断（WoW 下降 > 50pp）
def check_lapsed_multi(curr, prev):
    lapsed = []
    pairs = [
        ('davg_fulldisc_open_shop_coverage', '满折'),
        ('davg_reduceshipfee_shop_coverage', '减配'),
        ('davg_discount_spu_shop_coverage', '折扣菜'),
    ]
    for code, name in pairs:
        c = float(curr.get(code) or 0)
        p = float(prev.get(code) or 0)
        if p - c > 50:  # 百分点差值（如 85 - 25 = 60 > 50）
            lapsed.append(f'{name}（日均覆盖率 {p:.1f}%→{c:.1f}%，-{p-c:.1f}pp）')
    return lapsed

lapsed_shops = []
for shop_id, curr in curr_dict.items():
    prev = prev_dict.get(shop_id, {})
    lapsed = check_lapsed_multi(curr, prev) if is_multi_day else check_lapsed_single(curr, prev)
    if lapsed:
        lapsed_shops.append({
            'shop_id': shop_id,
            'shop_name': curr.get('shop_name'),
            'shop_owner_mis_id': curr.get('shop_owner_mis_id'),
            'lapsed_activities': lapsed
        })
```

**输出字段**：shop_id、shop_name、shop_owner_mis_id、lapsed_activities（脱落活动类型列表）

---

## 模块 4: 流量情况（三步法：品牌级曝光UV+分渠道UV → 品牌级资源位CTR → 门店级下钻）

### 第零步：step4_brand_uv_query（品牌级总曝光UV + 7渠道曝光UV，同步查询）

> 目标：先判断总曝光UV是否下降，同步拆解各渠道曝光UV，定位是哪个渠道的曝光量问题。
> UV 是**值类型**，PoP 用 `(curr - prev) / prev × 100`，展示为 **+X% / -X%**，不用 pp。
> ⚠️ **单日/多日模式，指标 Code 不同**。

**单日模式**（总UV + 7渠道UV 合并一次查询）：
```bash
# 查当期（单日）
kdata --json --task-id "$TASK_ID" --task-name "step4_brand_uv_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures shop_avg_ad_position_shop_entry_exposure_uv,shop_avg_brand_wall_shop_entry_exposure_uv,shop_avg_feeds_shop_entry_exposure_uv,shop_avg_search_shop_entry_exposure_uv,shop_avg_gundam_business_card_shop_entry_exposure_uv,shop_avg_homepage_discount_dish_shop_entry_exposure_uv,shop_avg_zone_landing_page_shop_entry_exposure_uv,shop_avg_discount_dish_channelpage_shop_entry_exposure_uv \
  --date {current_dt}~{current_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10

# 查上周同期（单日）
kdata --json --task-id "$TASK_ID" --task-name "step4_brand_uv_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures shop_avg_ad_position_shop_entry_exposure_uv,shop_avg_brand_wall_shop_entry_exposure_uv,shop_avg_feeds_shop_entry_exposure_uv,shop_avg_search_shop_entry_exposure_uv,shop_avg_gundam_business_card_shop_entry_exposure_uv,shop_avg_homepage_discount_dish_shop_entry_exposure_uv,shop_avg_zone_landing_page_shop_entry_exposure_uv,shop_avg_discount_dish_channelpage_shop_entry_exposure_uv \
  --date {last_week_dt}~{last_week_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10
```

**多日模式**（总UV + 7渠道UV 合并一次查询）：
```bash
# 查当期（多日）
kdata --json --task-id "$TASK_ID" --task-name "step4_brand_uv_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures davg_shop_avg_ad_position_shop_entry_exposure_uv,davg_shop_avg_brand_wall_shop_entry_exposure_uv,davg_shop_avg_feeds_shop_entry_exposure_uv,davg_shop_avg_search_shop_entry_exposure_uv,davg_shop_avg_gundam_business_card_shop_entry_exposure_uv,davg_shop_avg_homepage_discount_dish_shop_entry_exposure_uv,davg_shop_avg_zone_landing_page_shop_entry_exposure_uv,davg_shop_avg_discount_dish_channelpage_shop_entry_exposure_uv \
  --date {current_start}~{current_end} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10

# 查对比期（多日）
kdata --json --task-id "$TASK_ID" --task-name "step4_brand_uv_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures davg_shop_avg_ad_position_shop_entry_exposure_uv,davg_shop_avg_brand_wall_shop_entry_exposure_uv,davg_shop_avg_feeds_shop_entry_exposure_uv,davg_shop_avg_search_shop_entry_exposure_uv,davg_shop_avg_gundam_business_card_shop_entry_exposure_uv,davg_shop_avg_homepage_discount_dish_shop_entry_exposure_uv,davg_shop_avg_zone_landing_page_shop_entry_exposure_uv,davg_shop_avg_discount_dish_channelpage_shop_entry_exposure_uv \
  --date {prev_start}~{prev_end} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10
```

**指标 Code 对照**（总UV + 7渠道UV）：

| 渠道 | 单日 Code | 多日 Code |
|------|-----------|-----------|
| 总 | `shop_avg_ad_position_shop_entry_exposure_uv` | `davg_shop_avg_ad_position_shop_entry_exposure_uv` |
| 品牌墙 | `shop_avg_brand_wall_shop_entry_exposure_uv` | `davg_shop_avg_brand_wall_shop_entry_exposure_uv` |
| Feeds | `shop_avg_feeds_shop_entry_exposure_uv` | `davg_shop_avg_feeds_shop_entry_exposure_uv` |
| 大搜 | `shop_avg_search_shop_entry_exposure_uv` | `davg_shop_avg_search_shop_entry_exposure_uv` |
| 高达商卡 | `shop_avg_gundam_business_card_shop_entry_exposure_uv` | `davg_shop_avg_gundam_business_card_shop_entry_exposure_uv` |
| 首页折扣菜卡片 | `shop_avg_homepage_discount_dish_shop_entry_exposure_uv` | `davg_shop_avg_homepage_discount_dish_shop_entry_exposure_uv` |
| 金刚区落地页 | `shop_avg_zone_landing_page_shop_entry_exposure_uv` | `davg_shop_avg_zone_landing_page_shop_entry_exposure_uv` |
| 频道页折扣菜卡片 | `shop_avg_discount_dish_channelpage_shop_entry_exposure_uv` | `davg_shop_avg_discount_dish_channelpage_shop_entry_exposure_uv` |

**代码层输出格式（第零步）**：
```
曝光UV（总）：curr vs prev，PoP X%
  ├ 品牌墙：curr vs prev，PoP X%
  ├ Feeds：curr vs prev，PoP X%
  ├ 大搜：curr vs prev，PoP X%
  ├ 高达商卡：curr vs prev，PoP X%
  ├ 首页折扣菜卡片：curr vs prev，PoP X%
  ├ 金刚区落地页：curr vs prev，PoP X%
  └ 频道页折扣菜卡片：curr vs prev，PoP X%
```
触发条件：总曝光UV PoP < -10% 时，继续第一步 CTR 分析。

---

### 第一步：step4_brand_ctr_query（品牌级 7 个渠道 CTR，定位下降资源位）

> 目标：找出哪个资源位的 CTR 降了，只查品牌粒度（brand_id），不下钻门店。
> CTR 是**率类型**，PoP 用 `curr_pct - prev_pct` 计算百分点差值，展示为 **+Xpp / -Xpp**，不用 %。
> ⚠️ **数据集优先级**：**首选 62059636**（品牌集团分析）查各渠道 CTR；仅当 62059636 返回 0 行或执行报错时，才 fallback 到 60041382（供给大盘数据集）。两个数据集的渠道 CTR Code 不同，见下方映射表。
> ⚠️ **单日/多日模式，指标 Code 不同**，见下方两套命令。

#### 方案 A：使用 62059636（首选）

**单日模式**：
```bash
# 查当期品牌级 7 个渠道 CTR（单日，62059636）
kdata --json --task-id "$TASK_ID" --task-name "step4_brand_ctr_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures brand_wall_shop_entry_exposure_visit_ratio,feeds_shop_entry_expose_visit_ratio,search_shop_entry_expose_visit_ratio,gundam_business_card_shop_entry_expose_visit_ratio,homepage_discount_dish_shop_entry_expose_visit_ratio,zone_landing_page_shop_entry_expose_visit_ratio,discount_dish_channelpage_shop_entry_expose_visit_ratio \
  --date {current_dt}~{current_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10

# 查上周同期品牌级 7 个渠道 CTR（单日，62059636）
kdata --json --task-id "$TASK_ID" --task-name "step4_brand_ctr_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures brand_wall_shop_entry_exposure_visit_ratio,feeds_shop_entry_expose_visit_ratio,search_shop_entry_expose_visit_ratio,gundam_business_card_shop_entry_expose_visit_ratio,homepage_discount_dish_shop_entry_expose_visit_ratio,zone_landing_page_shop_entry_expose_visit_ratio,discount_dish_channelpage_shop_entry_expose_visit_ratio \
  --date {last_week_dt}~{last_week_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10
```

**多日模式**：
```bash
# 查当期品牌级 7 个渠道 CTR（多日，62059636）
kdata --json --task-id "$TASK_ID" --task-name "step4_brand_ctr_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures davg_shop_avg_brand_wall_shop_entry_exposure_visit_ratio,davg_feeds_shop_entry_expose_visit_ratio,davg_search_shop_entry_expose_visit_ratio,davg_gundam_business_card_shop_entry_expose_visit_ratio,davg_homepage_discount_dish_shop_entry_expose_visit_ratio,davg_zone_landing_page_shop_entry_expose_visit_ratio,davg_discount_dish_channelpage_shop_entry_expose_visit_ratio \
  --date {current_start}~{current_end} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10

# 查对比期品牌级 7 个渠道 CTR（多日，62059636）
kdata --json --task-id "$TASK_ID" --task-name "step4_brand_ctr_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures davg_shop_avg_brand_wall_shop_entry_exposure_visit_ratio,davg_feeds_shop_entry_expose_visit_ratio,davg_search_shop_entry_expose_visit_ratio,davg_gundam_business_card_shop_entry_expose_visit_ratio,davg_homepage_discount_dish_shop_entry_expose_visit_ratio,davg_zone_landing_page_shop_entry_expose_visit_ratio,davg_discount_dish_channelpage_shop_entry_expose_visit_ratio \
  --date {prev_start}~{prev_end} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10
```

#### 方案 B：fallback 到 60041382（仅当 62059636 返回 0 行或报错时）

> ⚠️ fallback 触发条件：62059636 查询返回空结果（rows=0）或抛出错误。fallback 时在输出中注明「使用 60041382 备用数据」。

**单日模式**：
```bash
# 查当期品牌级 7 个渠道 CTR（单日，60041382 fallback）
kdata --json --task-id "$TASK_ID" --task-name "step4_brand_ctr_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 60041382 \
  --measures brand_wall_shop_entry_exposure_visit_ratio,feeds_shop_entry_expose_visit_ratio,search_shop_entry_expose_visit_ratio,gundam_business_card_shop_entry_expose_visit_ratio,homepage_discount_dish_shop_entry_expose_visit_ratio,zone_landing_page_shop_entry_expose_visit_ratio,discount_dish_channelpage_shop_entry_expose_visit_ratio \
  --date {current_dt}~{current_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10

# 查上周同期（单日，60041382 fallback）
kdata --json --task-id "$TASK_ID" --task-name "step4_brand_ctr_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 60041382 \
  --measures brand_wall_shop_entry_exposure_visit_ratio,feeds_shop_entry_expose_visit_ratio,search_shop_entry_expose_visit_ratio,gundam_business_card_shop_entry_expose_visit_ratio,homepage_discount_dish_shop_entry_expose_visit_ratio,zone_landing_page_shop_entry_expose_visit_ratio,discount_dish_channelpage_shop_entry_expose_visit_ratio \
  --date {last_week_dt}~{last_week_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10
```

**多日模式（60041382 fallback）**：
```bash
# 查当期（多日，60041382 fallback）
kdata --json --task-id "$TASK_ID" --task-name "step4_brand_ctr_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 60041382 \
  --measures davg_shop_avg_brand_wall_shop_entry_exposure_visit_ratio,davg_feeds_shop_entry_expose_visit_ratio,davg_search_shop_entry_expose_visit_ratio,davg_gundam_business_card_shop_entry_expose_visit_ratio,davg_homepage_discount_dish_shop_entry_expose_visit_ratio,davg_zone_landing_page_shop_entry_expose_visit_ratio,davg_discount_dish_channelpage_shop_entry_expose_visit_ratio \
  --date {current_start}~{current_end} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10

# 查对比期（多日，60041382 fallback）
kdata --json --task-id "$TASK_ID" --task-name "step4_brand_ctr_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 60041382 \
  --measures davg_shop_avg_brand_wall_shop_entry_exposure_visit_ratio,davg_feeds_shop_entry_expose_visit_ratio,davg_search_shop_entry_expose_visit_ratio,davg_gundam_business_card_shop_entry_expose_visit_ratio,davg_homepage_discount_dish_shop_entry_expose_visit_ratio,davg_zone_landing_page_shop_entry_expose_visit_ratio,davg_discount_dish_channelpage_shop_entry_expose_visit_ratio \
  --date {prev_start}~{prev_end} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by brand_id,brand_name \
  --page-size 10
```

**渠道 Code → 资源位名称映射**（62059636 和 60041382 共用相同 Code，映射一致）：

| 单日 Code | 多日 Code | 资源位名称 |
|----------|----------|-----------|
| `brand_wall_shop_entry_exposure_visit_ratio` | `davg_shop_avg_brand_wall_shop_entry_exposure_visit_ratio` | 品牌墙 |
| `feeds_shop_entry_expose_visit_ratio` | `davg_feeds_shop_entry_expose_visit_ratio` | Feeds |
| `search_shop_entry_expose_visit_ratio` | `davg_search_shop_entry_expose_visit_ratio` | 大搜 |
| `gundam_business_card_shop_entry_expose_visit_ratio` | `davg_gundam_business_card_shop_entry_expose_visit_ratio` | 高达商卡 |
| `homepage_discount_dish_shop_entry_expose_visit_ratio` | `davg_homepage_discount_dish_shop_entry_expose_visit_ratio` | 首页折扣菜卡片 |
| `zone_landing_page_shop_entry_expose_visit_ratio` | `davg_zone_landing_page_shop_entry_expose_visit_ratio` | 金刚区商卡 |
| `discount_dish_channelpage_shop_entry_expose_visit_ratio` | `davg_discount_dish_channelpage_shop_entry_expose_visit_ratio` | 频道页折扣菜卡片 |

**代码层逻辑**：算各渠道 WoW，找出 WoW < -10% 的资源位，记录为 `declined_channels`（list of codes）。

---

### 第二步：step4_shop_ctr_query（门店级下钻，仅对 declined_channels 中的资源位）

> 对每个下降的资源位，查门店粒度 CTR，找出哪些门店这个资源位的 CTR 降了。
> ⚠️ `{declined_channel_code_list}` 须使用与当前模式一致的 Code（单日用单日 Code，多日用多日 Code）。

```bash
# 查当期门店粒度（仅传入下降的渠道 code，逗号分隔）
kdata --json --task-id "$TASK_ID" --task-name "step4_shop_ctr_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures {declined_channel_code_list} \
  --date {current_dt}~{current_dt}    # 单日模式 / {current_start}~{current_end} 多日模式
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id \
  --page-size 500

# 查同期门店粒度
kdata --json --task-id "$TASK_ID" --task-name "step4_shop_ctr_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures {declined_channel_code_list} \
  --date {last_week_dt}~{last_week_dt}  # 单日模式 / {prev_start}~{prev_end} 多日模式
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id \
  --page-size 500
```

**代码层对比**（以 shop_id 为 key JOIN 两次结果）：

```python
# 单日模式映射
CHANNEL_MAP_SINGLE = {
    'brand_wall_shop_entry_exposure_visit_ratio': '品牌墙',
    'feeds_shop_entry_expose_visit_ratio': 'Feeds',
    'search_shop_entry_expose_visit_ratio': '大搜',
    'gundam_business_card_shop_entry_expose_visit_ratio': '高达商卡',
    'homepage_discount_dish_shop_entry_expose_visit_ratio': '首页折扣菜卡片',
    'zone_landing_page_shop_entry_expose_visit_ratio': '金刚区商卡',
    'discount_dish_channelpage_shop_entry_expose_visit_ratio': '频道页折扣菜卡片',
}
# 多日模式映射
CHANNEL_MAP_MULTI = {
    'davg_shop_avg_brand_wall_shop_entry_exposure_visit_ratio': '品牌墙',
    'davg_feeds_shop_entry_expose_visit_ratio': 'Feeds',
    'davg_search_shop_entry_expose_visit_ratio': '大搜',
    'davg_gundam_business_card_shop_entry_expose_visit_ratio': '高达商卡',
    'davg_homepage_discount_dish_shop_entry_expose_visit_ratio': '首页折扣菜卡片',
    'davg_zone_landing_page_shop_entry_expose_visit_ratio': '金刚区商卡',
    'davg_discount_dish_channelpage_shop_entry_expose_visit_ratio': '频道页折扣菜卡片',
}
CHANNEL_MAP = CHANNEL_MAP_MULTI if is_multi_day else CHANNEL_MAP_SINGLE

abnormal_shops = []
for shop_id, curr in curr_dict.items():
    prev = prev_dict.get(shop_id, {})
    shop_issues = []
    for code in declined_channels:  # 只遍历第一步定位到的下降渠道
        c = float(curr.get(code) or 0)
        p = float(prev.get(code) or 0)
        if p > 0 and (c - p) / p < -0.1:
            wow_pct = round((c - p) / p * 100, 1)
            shop_issues.append(f'{CHANNEL_MAP[code]} CTR {wow_pct}%（{round(p,2)}→{round(c,2)}）')
    if shop_issues:
        abnormal_shops.append({
            'shop_id': shop_id,
            'shop_name': curr.get('shop_name'),
            'shop_owner_mis_id': curr.get('shop_owner_mis_id'),
            'ctr_issues': shop_issues
        })
```

**输出**：
- 品牌级：各资源位 CTR WoW 汇总，标注异常渠道
- 门店级：异常门店 id、负责人、具体下降资源位名称 + CTR 当期值及 WoW
---

## 模块 5: 补贴情况（门店级下钻）

> ⚠️ **不再使用 Hive SQL**，改用数据集 62059636。
> ⚠️ **指标变更（2026-04-21）**：触发指标和分析指标均改为 `actual_shop_charge_amt_ratio`（实付商补率），不再使用 `actual_disc_ratio`（实付补贴率）或 `shop_charge_amt_gmv`（商补金额）。

### step5_subsidy_shop_query：实付商补率下降的门店（kdata 数据集查询）

```bash
# 查当期
kdata --json --task-id "$TASK_ID" --task-name "step5_subsidy_curr:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures actual_shop_charge_amt_ratio \
  --date {current_dt}~{current_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id \
  --page-size 500

# 查上周同期
kdata --json --task-id "$TASK_ID" --task-name "step5_subsidy_prev:{REGION}:{date_or_range}" \
  standard query \
  --dataset 62059636 \
  --measures actual_shop_charge_amt_ratio \
  --date {last_week_dt}~{last_week_dt} \
  --region {REGION} \
  --filter "brand_id={brand_id}" \
  --group-by shop_id,shop_name,shop_owner_mis_id \
  --page-size 500
```

**代码层对比**：按 `actual_shop_charge_amt_ratio` WoW 降幅排序，取 Top 10 门店输出明细（shop_id、门店名称、shop_owner_mis_id、实付商补率当期值、上周值、WoW）

---

## 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `{current_dt}` | 当期查询日期（单日），格式 YYYYMMDD | 20260330 |
| `{current_start}~{current_end}` | 当期查询区间（多日），格式 YYYYMMDD~YYYYMMDD | 20260420~20260421 |
| `{last_week_dt}` | 上周同期日期（单日，current_dt - 7天） | 20260323 |
| `{prev_start}~{prev_end}` | 对比期查询区间（多日，与当期对应） | 20260320~20260321 |
| `{two_weeks_ago_dt}` | 两周前日期（用于活动失效趋势查询） | 20260316 |
| `{region}` | 目标 Region | QA |
| `{brand_id}` | 品牌 id | 374471 |
| `{shop_id}` | 单个门店 id | 1234567 |
| `{shop_id_list}` | 多个门店 id，逗号分隔 | 123,456,789 |

> ⚠️ **多日区间时口径一致性要求**：Step 1（大盘）、Step 0（品牌总览）、模块 1~5（门店下钻）**必须使用同一时间区间**（均用 `{current_start}~{current_end}` 和 `{prev_start}~{prev_end}`）。禁止大盘用区间、品牌/门店下钻只用结束日单天，否则口径不一致，分析结论不可信。

---

## 指标多语言名称对照表（数据集 62059636）

> 数据来源：`kdata --locale en/pt-BR standard measures --dataset 62059636`（2026-05-06 拉取）
> **非中文环境下输出指标名称时，必须使用此表中对应语言的名称，禁止自行翻译。**
> 若用户语言为英文，输出 English 列；若为葡萄牙语，输出 Português (BR) 列；`—` 表示该语言暂无官方名称，退而用英文名。

| Code | 中文 | English | Português (BR) |
|------|------|---------|----------------|
| `fin_ord_num` | 订单量 | Orders Number | Número de pedidos |
| `actual_pay_no_tip_gmv` | 实付交易额 | Actual GMV | GMV Efetivo |
| `paid_order_cancel_num_refund_shop_res` | 支付成功后订单取消量（商家责任） | Number of post-payment cancelled orders (merchant responsibility) | Número de pedidos cancelados após o pagamento (responsabilidade da loja) |
| `paid_order_cancel_rate_merchant_reason` | 支付成功后订单取消率（商家责任） | Post-payment order cancellation rate (merchant responsibility) | Taxa de cancelamento de pedidos após o pagamento (responsabilidade da loja) |
| `open_shop_num` | 营业商家数 | Operating Merchants Number | Número de comerciante operacional |
| `online_shop_num` | 在线商家数 | Online Merchants Number | Número de comerciante online |
| `shop_open_ratio` | 在线商家营业率 | Online Operating Merchant Rate | Percentual de lojas online em operação |
| `shop_avg_open_dura` | 店均营业时长(小时) | Operating Duration (Avg Merchant) (h) | Tempo médio de operação por loja (horas) |
| `shop_avg_peaktime_open_dura` | 店均高峰期营业时长(小时) | Average Operating Peak Hours Per Store | Média de horas de operação em horário de pico por loja |
| `davg_open_shop_num` | 日均营业商家数 | Average Daily Operating Merchants Number | Número médio diário de comerciantes ativos |
| `davg_online_shop_num` | 日均在线商家数 | Average Daily Online Merchants Num | Número médio diário de vendedores online |
| `davg_shop_avg_open_dura` | 日均店均营业时长 (小时) | Average Daily Operating Duration (Avg Merchant) (h) | Duração média diária de operação por loja (horas) |
| `davg_shop_avg_peaktime_open_dura` | 日均店均高峰期营业时长 (小时) | Average Daily Peak Period Operating Duration (Avg Merchant) (h) | Duração média diária de operação no horário de pico por loja (horas) |
| `shop_oavg_readied_duration` | 商家单均出餐时长(分) | Merchant Preparation Time (min) | Tempo médio de preparo de pedidos (min) |
| `davg_shop_oavg_readied_duration` | 日均商家单均出餐时长 (分) | Average Daily Merchant Preparation Time per Order (min) | Duração média diária de preparação de pedidos por vendedor (minutos) |
| `fin_ord_num` | 订单量 | — |
| `paid_order_cancel_num_refund_shop_res` | 支付成功后订单取消量（商家责任） | Number of post-payment cancelled orders (merchant responsibility) |
| `paid_order_cancel_rate_merchant_reason` | 支付成功后商责取消率（商家责任） | Post-payment order cancellation rate (merchant responsibility) |
| `fulldisc_open_shop_coverage` | 外卖满折活动生效营业商家覆盖率 | Coverage of merchants with active percentage off campaigns for delivery orders | Cobertura de lojas com campanhas ativas de desconto para pedidos de entrega |
| `davg_fulldisc_open_shop_coverage` | 日均外卖满折活动生效营业商家覆盖率 | Avg_Operating Merchant Prop with Percentage-off Discount | — |
| `davg_fulldiscount_shop_num` | 日均外卖满折活动生效营业商家数 | Daily Operating Merchants (Percentage-off Discount) | — |
| `reduceshipfee_open_shop_coverage` | 减配活动生效营业商家覆盖率 | Operating Merchants Coverage Rate (Delivery Fee Effective) | Percentual de lojas operando com promoção de Delivery Fee Ativa |
| `davg_reduceshipfee_shop_coverage` | 日均减配活动生效营业商家覆盖率 | Average Daily Operating Delivery Fee Effective Merchants Coverage Rate | Cobertura média diária de vendedores em operação com promoções de redução de configuração ativas |
| `discount_product_shop_ratio` | 折扣菜活动生效营业商家覆盖率 | Operating Merchants Coverage Rate (Promo Items Effective) | Percentual de lojas operando com promoções de itens ativas |
| `davg_discount_spu_shop_coverage` | 日均折扣菜活动生效营业商家覆盖率 | Average Daily Operating Promo Items Effective Merchants Coverage Rate | Cobertura média diária de vendedores em operação com promoções de pratos com desconto ativas |
| `fixedprice_open_shop_ratio` | 一人食活动生效营业商家覆盖率 | Coverage of merchants with active meals-for-one campaigns | Cobertura de lojas com campanhas ativas de refeições para um |
| `shop_avg_ad_position_shop_entry_exposure_uv` | 店均商家入口曝光UV | Merchant Entry Exposure UV (Avg Merchant) | — |
| `davg_shop_avg_ad_position_shop_entry_exposure_uv` | 日均店均商家入口曝光UV | Avg_Merchant Entry Exposure UV (Avg Merchant) | — |
| `shop_entry_exposure_visit_ratio` | 商家入口曝光->进店转化率（CTR） | Merchant Entry Exposure -> Homepage Expose Rate (CTR) | Taxa de conversão de exibição da loja para visita à loja (CTR) |
| `davg_shop_entry_exposure_visit_ratio` | 日均店均商家入口曝光->进店转化率（CTR） | Average Daily Merchant Entry Exposure -> Homepage CTR (Avg Merchant) | Taxa média diária de conversão de exposição para entrada por recursos de entrada de vendedores (CTR) |
| `brand_wall_shop_entry_exposure_uv` | 商家入口品牌墙曝光UV | Merchant Entrance Brand Wall Exposure UV | — |
| `davg_brand_wall_shop_entry_exposure_uv` | 日均商家入口品牌墙曝光UV | Avg_Merchant Entrance Brand Wall Exposure UV | — |
| `feeds_shop_entry_exposure_uv` | 商家入口Feeds曝光UV | Merchant Entrance Feeds Exposure UV | — |
| `davg_feeds_shop_entry_exposure_uv` | 日均商家入口Feeds曝光UV | Avg_Merchant Entrance Feeds Exposure UV | — |
| `search_shop_entry_exposure_uv` | 商家入口大搜曝光UV | Merchant Entry Big Search Exposure UV | — |
| `davg_search_shop_entry_exposure_uv` | 日均商家入口大搜曝光UV | Avg_Merchant Entry Search Exposure UV | — |
| `gundam_business_card_shop_entry_exposure_uv` | 商家入口高达商卡曝光UV | Merchant Entry Gundam Business Card Exposure UV | — |
| `davg_gundam_business_card_shop_entry_exposure_uv` | 日均商家入口高达商卡曝光UV | Avg_Merchant Entry Gundam Business Card Exposure UV | — |
| `homepage_discount_dish_shop_entry_exposure_uv` | 首页商家入口折扣菜卡片曝光UV | Homepage Merchant Entry Discount Dish Card Exposure UV | — |
| `davg_homepage_discount_dish_shop_entry_exposure_uv` | 日均首页商家入口折扣菜卡片曝光UV | Avg_Homepage Merchant Entry Discount Dish Card Exposure UV | — |
| `zone_landing_page_shop_entry_exposure_uv` | 商家入口金刚区商卡曝光UV | Merchant Entrance King Kong Zone Merchant Card Exposure UV | — |
| `davg_zone_landing_page_shop_entry_exposure_uv` | 日均商家入口金刚区商卡曝光UV | Avg_Merchant Entrance King Kong Zone Merchant Card Exposure UV | — |
| `discount_dish_channelpage_shop_entry_exposure_uv` | 频道页商家入口折扣菜卡片曝光UV | Exposure UV of discount dish cards on the merchant entrance of the channel page | Exposição de UV do cartão de desconto no cartão do comerciante da página do canal |
| `davg_discount_dish_channelpage_shop_entry_exposure_uv` | 日均商家入口折扣菜频道页曝光UV | Avg_Merchant Entry Discount Dish Channel Page Exposure UV | — |
| `brand_wall_shop_entry_exposure_visit_ratio` | 店均商家入口品牌墙曝光->进店转化率 (CTR) | Brand Wall Merchant Entry Exposure -> Homepage Expose Rate (CTR) | Exposição da parede da marca na entrada por loja média -> Taxa de conversão de entrada na loja (CTR) |
| `davg_shop_avg_brand_wall_shop_entry_exposure_visit_ratio` | 日均店均商家入口品牌墙曝光->进店转化率 (CTR) | Average Daily Brand Wall Merchant Entry Exposure -> Homepage Expose Rate (CTR) | Exposição diária média da parede de marcas na entrada do comerciante por loja -> Taxa de conversão para entrada na loja (CTR) |
| `feeds_shop_entry_expose_visit_ratio` | 店均商家入口Feeds曝光->进店转化率 (CTR) | Feeds Merchant Entry Exposure -> Homepage Expose Rate (CTR) | Exposição de feeds na entrada média de comerciantes -> Taxa de conversão para entrada na loja (CTR) |
| `davg_feeds_shop_entry_expose_visit_ratio` | 日均店均商家入口Feeds曝光->进店转化率 (CTR) | Average Daily Feeds Merchant Entry Exposure -> Homepage Expose Rate (CTR) | Taxa de conversão (CTR) da exposição de Feeds na entrada do comerciante por loja por dia para visita à loja |
| `search_shop_entry_expose_visit_ratio` | 店均商家入口大搜曝光->进店转化率 (CTR) | Big Search Merchant Entry Exposure -> Homepage Expose Rate (CTR) | Exposição na Busca Principal de Lojas por Comerciante Médio -> Taxa de Conversão de Entrada na Loja (CTR) |
| `davg_search_shop_entry_expose_visit_ratio` | 日均店均商家入口大搜曝光->进店转化率 (CTR) | Average Daily Big Search Merchant Entry Exposure -> Homepage Expose Rate (CTR) | Taxa de conversão de entrada na loja (CTR) de exposição média diária por comerciante por loja no grande mecanismo de busca |
| `gundam_business_card_shop_entry_expose_visit_ratio` | 店均商家入口高达商卡曝光->进店转化率 (CTR) | Gundam Business Card Merchant Entry Exposure -> Homepage Expose Rate (CTR) | A exposição do cartão comercial na entrada média da loja elevada -> taxa de conversão de entrada na loja (CTR) |
| `davg_gundam_business_card_shop_entry_expose_visit_ratio` | 日均店均商家入口高达商卡曝光->进店转化率 (CTR) | Avg_Gundam Business Card Merchant Entry Exposure -> Homepage Expose Rate (CTR) | — |
| `homepage_discount_dish_shop_entry_expose_visit_ratio` | 店均首页商家入口折扣菜卡片曝光->进店转化率 (CTR) | Discount Dish Card Merchant Entry Exposure -> Homepage Expose Rate (CTR) | — |
| `davg_homepage_discount_dish_shop_entry_expose_visit_ratio` | 日均店均首页商家入口折扣菜卡片曝光->进店转化率 (CTR) | Avg_Discount Dish Card Merchant Entry Exposure -> Homepage Expose Rate (CTR) | — |
| `zone_landing_page_shop_entry_expose_visit_ratio` | 店均商家入口金刚区商卡曝光->进店转化率 (CTR) | King Kong Zone Merchant Card Merchant Entry Exposure -> Homepage Expose Rate (CTR) | — |
| `davg_zone_landing_page_shop_entry_expose_visit_ratio` | 日均店均商家入口金刚区商卡曝光->进店转化率 (CTR) | Avg_King Kong Zone Merchant Card Merchant Entry Exposure -> Homepage Expose Rate (CTR) | — |
| `discount_dish_channelpage_shop_entry_expose_visit_ratio` | 店均商家入口频道页折扣菜卡片曝光->进店转化率 (CTR) | Channel Page Discount Dish Card Merchant Entry Exposure -> Homepage Expose Rate (CTR) | — |
| `davg_discount_dish_channelpage_shop_entry_expose_visit_ratio` | 日均店均商家入口频道页折扣菜卡片曝光->进店转化率 (CTR) | Avg_Channel Page Discount Dish Card Merchant Entry Exposure -> Homepage Expose Rate (CTR) | — |
| `actual_shop_charge_amt_ratio` | 实付商补率 | Actual Price M-Subsidy Rate | Taxa de Subsídio M de Preço Real |
| `shop_charge_amt_gmv` | 商补金额 | Merchant Subsidy | Subsídio ao comerciante |
