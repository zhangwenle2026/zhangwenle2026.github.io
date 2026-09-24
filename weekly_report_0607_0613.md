:::title
SP Metropolitan Weekly Review 圣保罗都市圈周报 (BRT 6.7-6.13)
:::

## 1 本周进展 Weekly Progress (BRT 6.7-6.13)

### 1.1 一周小结 Weekly Summary

本周Metro四城总订单757,715单（WoW -9.8%），GMV R$67.70M（WoW -11.2%），周五6/12创本周峰值165,547单。订单下滑主要受6月中旬季节性波动影响，四城均呈同步下行趋势。营业率方面，MH维持86-90%高位，Top tier全面突破60%达标线（NE 59.3%微差），Mid tier整体偏低（29.8%-49.0%）。6月新签本周新增合计300家（Top+MH 64家，Mid 239家），MTD累计595家。DD覆盖率持续承压，1+DD全城低于50%目标（22.4%-35.1%），需重点关注。

*Metro 4-city total orders 757,715 (WoW -9.8%), GMV R$67.70M (WoW -11.2%), with Friday 6/12 peaking at 165,547 orders. Order decline driven by mid-June seasonal softness, synchronized across all cities. Operating rate: MH holds 86-90%, Top tier broadly above 60% target (NE at 59.3% marginally short), Mid tier remains low (29.8%-49.0%). June new signing: 300 this week (Top+MH 64, Mid 239), MTD 595 total. DD coverage under pressure — 1+DD below 50% target across all cities (22.4%-35.1%), requiring urgent focus.*

### 1.2 关键结果指标 Key Result Indicators

#### 1.2.1 新签进度 New Signing Progress

6月目标待定（TBD），本节仅展示进展数据。
*June targets pending (TBD). This section presents progress data only.*

**本周新签 Weekly New Signing (6.7-6.13)**

| 区域 City | MH | Top | Mid | 合计 Total |
|---|---|---|---|---|
| Northeast | 0 | 8 | 81 | 89 |
| Western | 3 | 17 | 74 | 94 |
| Santos | 0 | 5 | 5 | 10 |
| Southern | 0 | 31 | 79 | 110 |
| **Metro Total** | **3** | **61** | **239** | **303** |

**6月MTD累计 June MTD (6.1-6.13)**

| 区域 City | MH | Top | Mid | 合计 Total |
|---|---|---|---|---|
| Northeast | 0 | 12 | 176 | 188 |
| Western | 3 | 27 | 143 | 173 |
| Santos | 0 | 11 | 19 | 30 |
| Southern | 0 | 38 | 166 | 204 |
| **Metro Total** | **3** | **88** | **504** | **595** |

![New Signing Weekly & MTD](https://km.sankuai.com/api/file/cdn/2768296355/241819399369?contentType=0&isNewContent=false){width=1335 height=548}

**分析 Analysis：**
1. Southern本周新签最多（110家），Top tier贡献31家领先各城。
*Southern leads weekly signing (110), with 31 Top tier — highest among all cities.*
2. Santos持续偏弱（仅10家/周），需针对性支持。
*Santos remains weak (only 10/week), requires targeted support.*
3. MH新签接近冻结（仅Western 3家），符合MH存量饱和预期。
*MH signing near zero (only 3 in Western), consistent with MH saturation.*

数据来源：Hive SQL, mart_sailor_global.topic_shop_supply_d + topic_supply_lead_wide_d, dt=20260613

---

#### 1.2.2 营业率 Operating Rate

目标：≥60%（全优先级）
*Target: ≥60% (all priorities)*

| 区域 City | MH | Top | Mid |
|---|---|---|---|
| Northeast | 86.4% ✅ | 59.3% ⚠️ | 42.4% ❌ |
| Western | 86.5% ✅ | 63.2% ✅ | 49.0% ❌ |
| Santos | 90.5% ✅ | 64.9% ✅ | 29.8% ❌ |
| Southern | 86.5% ✅ | 64.5% ✅ | 43.9% ❌ |

![Operating Rate by Priority](https://km.sankuai.com/api/file/cdn/2768296355/241820551664?contentType=0&isNewContent=false){width=1335 height=659}

**分析 Analysis：**
1. MH营业率全城86%+，表现稳定。
*MH operating rate 86%+ across all cities, stable.*
2. Top tier整体达标（3/4城≥60%），Northeast 59.3%微差0.7pp需关注。
*Top tier broadly on target (3/4 cities ≥60%); NE at 59.3% — 0.7pp short, monitor closely.*
3. Mid tier全城未达标，Santos仅29.8%为最薄弱环节。改善方向：聚焦Mid tier激活。
*Mid tier below target everywhere; Santos at 29.8% is the weakest link. Focus: Mid tier activation.*

数据来源：Hive SQL, dt=20260613, pool=online shops with lead_type=1, visible=1, status 3-4

---

#### 1.2.3 深折扣覆盖率 Deep Discount Coverage

目标：1+DD ≥50% / 3+DD ≥30%（T+M pool）
*Target: 1+DD ≥50% / 3+DD ≥30% (T+M pool)*

| 区域 City | Pool | 1+DD | 3+DD |
|---|---|---|---|
| Northeast | 4,097 | 34.2% ❌ | 17.7% ❌ |
| Western | 3,708 | 30.0% ❌ | 13.8% ❌ |
| Santos | 944 | 22.4% ❌ | 8.7% ❌ |
| Southern | 5,025 | 35.1% ❌ | 16.5% ❌ |
| **Metro** | **13,774** | **32.6%** ❌ | **15.5%** ❌ |

![Deep Discount Coverage](https://km.sankuai.com/api/file/cdn/2768296355/241818314431?contentType=0&isNewContent=false){width=1335 height=824}

**分析 Analysis：**
1. 全城1+DD均大幅低于50%目标（差15-28pp），3+DD低于30%目标（差12-21pp）。
*1+DD significantly below 50% target across all cities (gap 15-28pp); 3+DD below 30% (gap 12-21pp).*
2. ⚠️ 6月政策调整：原价门槛从R$30降至R$15，理论上会扩大符合条件的SPU池，但本周数据尚未体现明显改善。
*⚠️ June policy change: original price threshold reduced from R$30 to R$15, which should expand eligible SPU pool — but improvement not yet visible in this week's data.*
3. Santos最弱（1+DD 22.4%），需BD重点跟进hotsell SPU折扣配置。
*Santos weakest (1+DD 22.4%); BD follow-up on hotsell SPU discount setup needed.*

数据来源：Hive SQL, aggr_product_sku_info_d + aggr_product_spu_info_d, dt=20260613, pool=online+operated≥60min

---

#### 1.2.4 订单趋势 Order Trend

| 区域 City | 本周订单 | 上周订单 | WoW | 本周GMV(M) | 上周GMV(M) | WoW |
|---|---|---|---|---|---|---|
| Northeast | 204,506 | 230,929 | -11.4% | R$18.00 | R$20.58 | -12.5% |
| Western | 212,704 | 232,216 | -8.4% | R$19.05 | R$21.17 | -10.0% |
| Santos | 50,791 | 53,168 | -4.5% | R$4.64 | R$4.90 | -5.3% |
| Southern | 289,714 | 323,351 | -10.4% | R$26.01 | R$29.61 | -12.2% |
| **Metro** | **757,715** | **839,664** | **-9.8%** | **R$67.70** | **R$76.26** | **-11.2%** |

![Daily Orders Trend](https://km.sankuai.com/api/file/cdn/2768296355/241818828538?contentType=0&isNewContent=false){width=1335 height=658}

**分析 Analysis：**
1. 四城订单同步下行约10%，GMV降幅略大（-11.2%）因AOV也微降。
*All 4 cities orders declined ~10% WoW; GMV drop slightly larger (-11.2%) due to minor AOV compression.*
2. 周五（6/12）仍为峰值日（165,547单），周末保持强劲。
*Friday (6/12) remains peak day (165,547 orders); weekend stays strong.*
3. 下滑可能与6月中旬季节性、Festa Junina准备期消费转移有关，需持续观察。
*Decline possibly linked to mid-June seasonality and Festa Junina preparation spending shift; monitor.*

数据来源：Hive SQL, mart_sailor_global.topic_shop_supply_d, dt 20260607-20260613 vs 20260531-20260606

---

## 2 本月重点任务 Priorities

| # | 任务 Task | 当前进度 Current Progress | 截止 & 行动 Deadline & Action |
|---|---|---|---|
| 1 | 6月新签推进 June New Signing | MTD 595家（Top+MH 91, Mid 504）；目标待定 *MTD 595 (Top+MH 91, Mid 504); target TBD* | 6.30 / 持续每日跟进 *Daily tracking* |
| 2 | 营业率提升 Operating Rate Improvement | Top 60%+达标（3/4城）；Mid全城未达 *Top on target (3/4); Mid below everywhere* | 6.30 / Mid tier专项激活计划 *Mid tier activation plan* |
| 3 | DD覆盖率攻坚 DD Coverage Push | 1+DD 32.6%（目标50%，差17pp） *1+DD 32.6% vs 50% target, gap 17pp* | 6.30 / 政策调整后BD重推hotsell配置 *Post-policy BD push on hotsell setup* |
| 4 | 6月考核政策落地 June Incentive Policy Rollout | 已完成全员宣导，原价门槛降至R$15、管理评分降至5% *Full team briefed; price threshold to R$15, mgmt score to 5%* | 6.15 / 确认各CM理解新规则 *Confirm all CMs understand new rules* |
| 5 | 拜访效率提升 Visit Efficiency | 数据待本周拉取 *Data pending this week's pull* | 6.30 / 拜访人效分析 *Visit productivity analysis* |

---

## 3 最大障碍 Major Obstacles

1. **DD覆盖率持续低迷**：尽管6月政策放宽原价门槛（R$30→R$15），1+DD仍全城远低于50%目标。核心卡点：BD端hotsell SPU折扣配置动力不足，商家自主配置率低。
*DD coverage remains far below target despite June price threshold relaxation. Core blocker: BD motivation for hotsell SPU discount setup is insufficient; merchant self-configuration rate is low.*

2. **Mid tier营业率全城未达标**：Mid tier平均营业率约41%（目标60%），Santos仅29.8%。需要区分"已签约未开店"vs"已开店但营业时长不足"两类问题针对性解决。
*Mid tier operating rate averages ~41% (target 60%); Santos at 29.8%. Need to differentiate "signed but not opened" vs "opened but insufficient hours" for targeted solutions.*

3. **订单WoW下行10%**：全城同步下滑，非单城问题。需排查是否有季节性因素（Festa Junina）、竞争加剧或平台侧变动。
*Orders down 10% WoW across all cities — not city-specific. Need to investigate seasonality (Festa Junina), competitive intensification, or platform-side changes.*

---

## 4 竞对动态 Competitor Intelligence

⚠️ 本周拜访记录数据待拉取，竞对分析将在数据到位后补充。
*⚠️ Visit record data pending extraction; competitor analysis will be supplemented once data is available.*

---

## 5 团队人员简报 Team Personnel Briefing

⚠️ 待各CM输入。
*⚠️ Pending CM inputs.*
