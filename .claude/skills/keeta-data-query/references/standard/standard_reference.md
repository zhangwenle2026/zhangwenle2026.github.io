# 起源标准数据集参考

`kdata standard` 用于查询起源数据集数据，无需写 SQL。

## 常用数据集

按用户问题先定位领域，再在对应领域行内选择数据集。

| 领域 | 常用数据集 | 选用规则 |
|---|---|---|
| 经营 | - 经营沙盘 60049761：默认经营大盘，适合查订单量、GMV、营业商家、用户和履约概览。 | 经营、订单、GMV、商家、城市下钻等问题默认优先用经营沙盘。 |
| C端 | - 用增大盘 60051108：适合查新客、老客、访问设备、交易设备、订单/GMV 和 C 端补贴。<br>- SA-C端经营数据简报 60049127：适合查 SA C 端访问用户、外卖订单、新客、AOV、补贴率和城市下钻。<br>- 访购诊断分析 60051984：适合查访问 UV、访购率、支付/完单转化和品类/门店/城市漏斗诊断。<br>- 搜索整体概览 60052634：适合查搜索带来的订单、GMV、补贴、访问和首次访问表现。<br>- 搜索功能分析 60052636：适合查搜索模块曝光/点击、资源位交易用户和页面/取餐方式分析。<br>- 搜索无结果分析 60052638：适合查搜索 QV、无结果 QV、无结果率和无结果问题定位。<br>- 搜索结果分析 60052643：适合查搜索结果页曝光/点击、资源位交易 UV、资源位 GMV/订单和品牌/门店/品类下钻。<br>- 渠道流量分析 62055197：适合查渠道访问、交易用户、提交/支付/完单 UV、访购率和访客分层。<br>- C端-离线-投放渠道Timebase看板 62059244：适合查投放渠道下载、注册、转化、曝光、点击、消耗和新客获取。<br>- 高达资源位归因-hive 60048075：适合查高达资源位曝光/点击、访问、补贴和商家/品牌/品类归因。<br>- 高达投放资源位分析 62052245：适合查高达投放资源位曝光点击、CVR、资源位订单和 GMV。<br>- 资源位归因Doris-首页资源位流量分析 62059514：适合查首页资源位曝光/点击、访问、补贴、GMV 和商家/品牌/品类细分。<br>- 商家入口流量分析-资源位 60048404：适合按资源位查商家入口曝光、进店、支付、完单、CTR/CVR/CXR。<br>- 商家入口流量分析-商家 60048406：适合按商家粒度查入口曝光、进店、支付、完单转化。 | 新客/老客/设备选增长；访购率/转化漏斗选访购；搜索词/无结果/结果页选搜索；渠道/投放/资源位/商家入口选流量投放。 |
| B端供给 | - 商家主题 60008094：适合查商家基础画像、营业时长、在售 SPU、菜品图片、堂食价和活动配置。<br>- 供给大盘 60041382：适合查供给全球大盘、营业商家、高峰有效营业、商家交易、订单/GMV 和补贴。<br>- 新城上单监控 60048831：适合查新城开城、新签商家、Preopen、合同承诺、菜品和价格配置。<br>- 连锁品牌新签 62055215：适合查连锁品牌新签、Preopen 完成、SPU/图片和品牌/门店粒度跟踪。<br>- 线索分析 60052164：适合查线索池、公海线索、认领、拜访、Priority/KA/SMB 线索和组织架构下钻。<br>- 商家产品分析 62059238：适合查商家产品、营业商家、交易商家、动销率、订单/GMV 和产品维度分析。<br>- 供给-商补分析看板-global 62059524：适合查满折、减配送费、美补/商补金额、补贴率和单均补贴。<br>- BML分析 62059604：适合查 BML/商家分层线索、Red/Must Have 线索、预估订单和组织架构跟踪。 | 供给经营默认选供给大盘；商家基础信息选商家主题；上单/新签/线索/商补/BML 按关键词选对应数据集。 |
| D端履约 | - Logistic Batch Metrics 60008590：适合查推单、接单、配送完成、准时率、配送取消、超 55 分钟和品牌/门店下钻。<br>- Logistic XBR Core Metrics 60008226：适合查 XBR 履约核心指标、准时率、配送取消、骑手上线/有单时长和配送区域/载具维度。<br>- D端-离线-3PL后台 60011906：适合查 3PL 商后台考核准时、虚假配送剔除、排班/未排班有效骑手和加盟商维度。<br>- Logistics Partner Manager Batch 60011506：适合查 3PL PMM 上卷粒度任务单、取消、准时、超时、上线时长和距离段/骑手类型。<br>- 3PL PMM By Courier (Batch) 60011696：适合查 3PL PMM 骑手粒度接单、完单、取消、上线时长、排班班次和配送区域。<br>- D端-离线-3PL-3PL过程管理 60020806：适合查 3PL 过程管理、派单接受率、人均上线时长、配送时长、骑手类型和城市商管理。<br>- Keeta Logistic Overview 60009423：适合查履约大盘、配送完成、支付订单、上线/完单骑手、准时率和超 55 分钟。<br>- D端-离线-履约-爆单复盘看板 62052236：适合查履约异常、爆单复盘、活动复盘和配送区域/时段/业务城市下钻。 | 履约核心默认选 Logistic Batch Metrics；XBR/3PL/PMM/骑手粒度/爆单按问题对象选对应数据集。 |
| 客服/售后 | - 服务体验数据 62052307：适合查客服体验、人工入队量、人工 CPO、退款、赔付、支付订单和 GTV。 | 客服体验、退款、赔付、售后成本相关问题优先用服务体验数据。 |

## 标准查询流程

1. 先执行 `mtcli kdata user whoami`，查看 `regionPermissions` 中 `regionHqAuth=true` 的 Region 列表；后续 `--region` 只从该列表与固定枚举 SA/HK/AE/QA/KW/BR/BH 的交集中选择。
2. 再按用户问题从常用数据集表选择数据集；无法判断时再用 `kdata standard datasets` 探索。默认 `kdata standard datasets --json` 只用于轻量探索候选数据集；需要完整 measure/dim code list 时再用 `kdata standard datasets --json --full`。
3. 用 `kdata standard measures --dataset <ID> --search <指标关键词>` 确认真实指标 code；搜索会覆盖 code、名称、口径描述、多语言名称/描述和分类信息，并按匹配强度排序。
4. 用 `kdata standard dims --dataset <ID> --search <维度关键词>` 确认真实维度 code。
5. 提交查询前检查日期格式：日期必须使用 `yyyyMMdd` 或 `yyyyMMdd~yyyyMMdd`，例如 `20260615` 或 `20260601~20260615`；不要使用 `yyyy-MM-dd`，例如 `2026-06-15`。
6. 需要过滤时，用 `kdata standard dim-values <dim_code> --search <关键词>` 确认可用维值；地区例外，`--region` 固定枚举：SA/HK/AE/QA/KW/BR/BH，用户已明确地区时直接使用对应 code，不要为了已知地区调用 `kdata standard dim-values global_region_code`。
7. 先跑最小查数命令，只带 `--dataset`、`--measures`、`--date`、`--region`，确认能出数；CLI 也会在查询前自动执行 `mtcli kdata user whoami`，把当前账号具备区域总部权限的 Region 加入上下文。
8. 再逐步增加 `--group-by`、`--filter`、`--order-by`、`--pops`、`--proportion`、`--gini`、`--fluctuation`。

## 指标候选排序与歧义消解

`kdata standard measures --search` 是意图消解的低成本探查步骤，不是简单的 code/name 关键词命中列表。召回候选后按指标元数据动态排序；Agent 仍需结合用户问题判断候选是否真的覆盖意图，禁止把某个业务词固定映射到某个指标 code，也不要因为某个候选排在 CLI 输出第一行就直接使用。

排序时按以下信号判断：

- 用户原词覆盖：指标 name/desc 是否覆盖用户说的核心对象、动作和业务场景。
- 限定词覆盖：用户说了支付、提单、配送完成、取消、新客、老客、外卖、活动、补贴、日均等限定时，候选必须覆盖这些限定。
- 额外限定惩罚：候选 name/desc 中出现用户没有表达的限定词时降权；例如用户只说“订单”，但候选强调支付、提单、配送完成、优惠券、新客、取消等更窄口径，不能自动当作默认口径。
- 指标类型匹配：用户问“量/数”优先 additive 或 deduplicative，“率/占比”优先 ratio，“单均/均值”优先 ratio 或 avg 类口径，“金额/GMV/补贴”优先金额类指标。
- 数据集业务域：候选指标所在数据集必须和用户问题领域一致；经营总览、C 端、供给、履约、客服、搜索、投放等场景不要混用。
- 可用性与上下文：优先选择有权限且能用最小查询验证的候选；只有用户明确沿用上一轮口径，才复用上一轮指标或数据集。

决策规则：

- top1 候选明显领先，且其他候选主要是额外限定或更窄细分：直接用 top1 查数，并在取数口径中说明采用的指标含义。
- 候选接近，或多个候选都完整覆盖用户问题但口径会导致不同结论：先列出 2-4 个自然语言候选让用户选，不要先查。
- 用户问题只有表层模糊但可以通过数据集和指标元数据收敛时，不要机械追问；先完成低成本探查。

常用地区 code：

| 地区 | `--region` |
|---|---|
| 沙特 | `SA` |
| 香港 | `HK` |
| 阿联酋 | `AE` |
| 卡塔尔 | `QA` |
| 科威特 | `KW` |
| 巴西 | `BR` |
| 巴林 | `BH` |

追问指标路由：

- 用户追问另一个指标时，不要默认沿用上一轮数据集；先重新判断新指标所属领域和最合适的数据集。
- 只有用户明确要求沿用上一口径，或用 `standard measures` 确认新指标属于上一轮数据集时，才复用上一轮数据集。
- 如果新指标在上一轮数据集找不到，或明显属于履约、客服、搜索、供给等其他领域，应按常用数据集表重新选择数据集。

过滤字段选择：

- 构造 `--filter` 时，优先使用 ID/code 类维度过滤，例如业务城市优先用 `op_city_id`，品牌优先用 `brand_id`，门店优先用 `shop_id`。
- 谨慎使用 name 类维度过滤，例如 `op_city_name`、`brand_name`、`shop_name`。name 可能存在中文、英文、本地语言等多语言差异，跨数据集查询时尤其容易出现同一业务对象在 A 数据集能命中、B 数据集无数据的问题。
- 同一过滤字段有多个取值时，优先写成一个 `--filter key=value1,value2`；如果重复传同一个过滤字段，CLI 会按多值过滤合并处理。不同过滤字段同时限制时，再多次传 `--filter`。
- 如果用户只提供中文名称，先用 `dim-values` 查到对应 ID/code，再用 ID/code 过滤；给用户展示口径时仍使用自然语言名称。

| 用户意图 | 应使用命令 |
|---|---|
| 查看可用区域总部权限 Region | `mtcli kdata user whoami` |
| 不确定数据集 | 先看常用数据集表；仍不确定再 `kdata standard datasets` |
| 找指标 code | `kdata standard measures --dataset <ID> --search <关键词>` |
| 找维度 code | `kdata standard dims --dataset <ID> --search <关键词>` |
| 找过滤值 | `kdata standard dim-values <dim_code> --search <关键词>` |
| 查数 | `kdata standard query --dataset <ID> --measures <code> --date <yyyyMMdd 或 yyyyMMdd~yyyyMMdd> --region <REGION>` |
| 下钻 | 在 query 后追加 `--group-by <dim_code>` |
| 过滤 | 在 query 后追加一个或多个 `--filter key=value` |
| 排序 | 在 query 后追加 `--order-by <measure>=DESC` |
| 环比/同比 | 在 query 后追加 `--pops dod,wow` |
| 占比/集中度/贡献 | 在 query 后追加 `--proportion <measure>` / `--gini <measure>` / `--fluctuation <measure>` |

## 结果回复口径

每次执行 `kdata standard query` 并向用户展示结果时，必须在结果后补充“取数口径”。口径只基于本次命令参数和 CLI 返回列，不补充未验证的业务解释。

取数口径必须包含：

- 数据来源：优先写数据集中文名，不默认展示数据集 ID。
- 指标：优先写指标中文名，不默认展示指标 code。
- 时间：用结构化日期区间表达，例如 `2026-06-01 ~ 2026-06-07`。
- 地区：写国家/地区中文名；如果有城市、门店、品牌等过滤，写自然语言过滤条件。
- 粒度：写“按日期”“按业务城市”“按品牌”等自然语言；未指定时写“总体”。
- 对比/算子：仅在使用环比、同比、占比、基尼系数、波动贡献时，用中文说明含义，不展示返回列名。
- 结果范围：仅在指定排序或展示条数时，用自然语言说明“按订单量降序展示前 10 个”等。

给用户展示时避免堆砌 ID、code、字段名。只有在用户需要复现命令、排查问题、申请权限，或中文名称无法确认时，才补充必要的 ID/code。
没有使用的参数或算子不要写入口径，例如未做环比/同比时，不需要说明“没有计算环比/同比”。

回复格式：

```text
取数口径：本次结果来自 <数据集中文名>，统计指标为 <指标中文名>，时间范围为 <YYYY-MM-DD ~ YYYY-MM-DD>，地区为 <国家/地区中文名>，统计粒度为 <自然语言粒度>，过滤条件为 <自然语言过滤条件或“无额外过滤”>。<如有排序、分页、环比、同比、占比、基尼系数或波动贡献，用自然语言补充说明；未使用则不写。>
```

## 常用维度

| 维度 | 字段名 dim_code |
|---|---|
| Region | `global_region_code`、`global_region_name` |
| 门店 | `shop_id`、`shop_name` |
| 品牌 | `brand_id`、`brand_name` |
| 日期 | `dt` |
| 业务城市 | `op_city_id`、`op_city_name` |
| 取餐方式 | `user_get_mode_id`、`user_get_mode_name` |

## 鉴权与权限

- `kdata standard query` 会先执行 `mtcli kdata user whoami`，只读取 `regionPermissions` 中 `regionHqAuth=true` 的 Region 列表，用于提示和提前拦截无区域总部权限的查询。
- 如果查询提示无 Region 权限，例如 `no permission for region`、`region 权限不足`，或目标 Region 不在当前可用区域总部权限列表中，引导用户使用 `keeta-data-query-for-front-line` skill。
- 如果指标无权限或查询失败，优先查看 CLI 输出的权限申请链接，让用户按链接申请对应指标或 Region 权限。

## 常用命令

```bash
# 查看当前账号具备区域总部权限的 Region
mtcli kdata user whoami

# 列出所有数据集
kdata standard datasets

# 查经营沙盘中和“订单”相关的指标
kdata standard measures --dataset 60049761 --search 订单

# 查经营沙盘中和“城市”相关的维度
kdata standard dims --dataset 60049761 --search 城市

# 查数命令必须指定 --region，可选值：SA / HK / AE / QA / KW / BR / BH
# 查 SA 2026-06-15 的订单量；--date 使用 yyyyMMdd，不写 2026-06-15
kdata standard query \
  --dataset 60049761 --measures fin_ord_num \
  --date 20260615 --region SA

# 查 SA 2026-03-14 至 2026-03-20 的每日订单量，并带日环比/周同比
kdata standard query \
  --dataset 60049761 --measures fin_ord_num \
  --date 20260314~20260320 --region SA \
  --group-by dt --order-by dt=ASC --pops dod,wow

# 按业务城市下钻 SA 2026-03-18 的订单量和实付交易额
kdata standard query \
  --dataset 60049761 --measures fin_ord_num actual_pay_no_tip_gmv \
  --date 20260318~20260318 --region SA \
  --group-by op_city_name --order-by fin_ord_num=DESC --page-size 10

# 过滤利雅得后按品牌下钻订单量和实付交易额；过滤优先使用业务城市 ID
kdata standard query \
  --dataset 60049761 --measures fin_ord_num actual_pay_no_tip_gmv \
  --date 20260318~20260318 --region SA \
  --filter op_city_id=1150000081 \
  --group-by brand_name --order-by fin_ord_num=DESC --page-size 10

# 同一过滤字段多个取值时，用逗号分隔；重复传同一个 --filter 字段时 CLI 会合并为多值过滤
kdata standard query \
  --dataset 60049761 --measures fin_ord_num \
  --date 20260609~20260609 --region SA \
  --filter op_city_id=1150000081,1150000078 \
  --group-by op_city_name --order-by fin_ord_num=DESC

# 输出 JSON，便于后续程序处理
kdata --json standard query \
  --dataset 60049761 --measures fin_ord_num \
  --date 20260318~20260318 --region SA

# 分析类触发词：分析、结构分析、构成分析、分布分析、占比、比例、份额、分布、集中度、基尼、基尼系数、波动贡献、贡献度、贡献分析、驱动、拆解
# 命中分析类请求时必须指定 --group-by；涉及波动贡献时只能读取 {measure}_{pop}_fluctuation_value，不能手算
# --proportion <指标> 输出 {measure}_proportion，占比值为 0 到 1 的小数
# --gini <指标> 会自动计算波动贡献，并基于 {measure}_{pop}_fluctuation_value 的绝对值计算贡献集中度
# --gini 默认输出 {measure}_{pop}_normalized_gini，归一化基尼系数为 0 到 1 的小数，越接近 1 表示波动贡献越集中，适合跨维度比较
# --gini-mode standard 输出 {measure}_{pop}_gini；--gini-mode both 同时输出标准基尼和归一化基尼
# --gini 必须配合 --group-by；即使 --page-size 只展示部分行，也会按完整分组结果计算和输出
# --fluctuation <指标> 输出 {measure}_{pop}_fluctuation_value，正值表示正向拉动，负值表示拖累
# 波动贡献自检失败最多重试 1 次；仍失败时停止重试且不展示贡献列
# 计算 KA 自取订单按业务城市拆分的订单量占比、集中度和日环比波动贡献
kdata standard query \
  --dataset 60049761 --measures fin_ord_num \
  --date 20260318~20260318 --region SA \
  --filter shop_type_name=KA --filter is_pickup=1 \
  --group-by op_city_name --order-by fin_ord_num=DESC --page-size 20 \
  --proportion fin_ord_num --gini fin_ord_num --pops dod
```
