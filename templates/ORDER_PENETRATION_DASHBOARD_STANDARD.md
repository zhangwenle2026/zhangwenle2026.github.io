# 订单渗透激励赛看板 — 标准规范
# Order Penetration Incentive Race Dashboard — Standard Specification

> **创建日期**: 2026-08-07
> **看板链接**: https://html-hosting-hub.mynocode.host/#/preview/c998d382-7874-4273-8867-1cfe183eed41
> **UUID**: c998d382-7874-4273-8867-1cfe183eed41
> **HTML文件**: `order_penetration_dashboard_v4.html`

---

## 一、赛制规则 Scoring Rules

### 1.1 三大攻坚方向 Three Attack Directions

| Direction 方向 | Condition 条件 | Base Score 基础分 | HV Bonus 高价值加分 |
|---|---|---|---|
| 🔴 Not Signed 未签约 | 未签约 → 有效营业 | **6** | iFood orders ≥ 20: **+2** |
| 🟡 Not Online 未上线 | 已签未上线 → 有效营业 | **4** | iFood orders ≥ 20: **+2** |
| 🟢 Not Operating 未营业 | 已签不营业 → 恢复营业 | **3** | iFood orders ≥ 20: **+2** |

### 1.2 有效营业判定 Operating Validation
- 最近7天营业 ≥ 15小时
- 且 ≥ 1个订单

### 1.3 高价值商家 HV (High Value) Merchant
- 判定标准: `red_order ≥ 20`（iFood订单数 ≥ 20）
- 满足条件时基础分额外 +2

### 1.4 达标门槛 Qualification Threshold
- **BD个人达标**: 总积分 ≥ 15分
- **BDM团队达标**: 人均积分 ≥ 15分

### 1.5 BDM人均计算规则
- 人均积分 = 团队总分 ÷ 8月1日实际在职BD人数
- BD增减规则以8月1日在职人数为准（即下方固定名单）

### 1.6 早鸟加分 Early Bird Bonus
- 8月15日前完成转化: 额外 +1 分
- **但**必须在最终截止日(8月31日)仍满足有效性标准
- 若8月31日未达标，基础分和早鸟分均不计入

---

## 二、作战池 Battle Pool — Target Merchants

| City 城市 | Target Merchants 目标商家数 |
|---|---|
| Southern | 413 |
| Western | 331 |
| Santos | 74 |
| **Total 合计** | **818** |

### 城市作战列表文档
- Southern SP Metropolitan (413家): https://km.sankuai.com/collabpage/2777035121
- Western SP Metropolitan (331家): https://km.sankuai.com/collabpage/2776785924
- Santos City (74家): https://km.sankuai.com/collabpage/2777591485

---

## 三、人员名单 Personnel Roster（固定，以8月1日在职为准）

### 3.1 组织架构 Organization Structure

**Metropolitan Region — 3 Cities, 3 CMs, 12 BDMs, 71 BDs**

#### Southern São Paulo Metropolitan — CM: danielalbuquerque (5 BDMs, 35 BDs)

| BDM | BD Count | BD Names |
|---|---|---|
| adriananaves | 9 | brunacrelien, elisangelasouza, evaldosilva, ivanfelizardo, josenascimento, murilosilva, rodrigoalmeida, tiagodangelo, wanessasilva |
| fernandooliveira | 8 | brunapadilha, carlosmotta, cristianedasilva, erikboilesen, felipesanches, pedrosaccone, wainnergonzales, wellingtonsantos |
| eduardoalbuquerque | 6 | allanmaalouli, felipesilva, fernandoquintiliano, joycepurificacao, otaviomazzega, thaisvasconcelos |
| alisaeed | 6 | camilabatista, davidcaramaschi, eduardosantos, marciajesuino, ricardoaraujo, rodrigocorreia |
| tadeumoraes | 6 | leandroresende, lucasreis, matheuscoelho, paulosantos, paulosilva, ricardoalmeida |

#### Western São Paulo Metropolitan — CM: marciojaroslavsky (5 BDMs, 28 BDs)

| BDM | BD Count | BD Names |
|---|---|---|
| biancaceotto | 7 | caiolorencato, karinacolomina, luizmoreira, nayannedias, nicolemenezes, nilmaxfranca, rodrigopoli |
| cesararraes | 6 | guilhermesantos, jadycarvalho, johnataguimaraes, kevinberti, renansilva, williamhenrique |
| thiagoscavazini | 6 | barbaraoliveira, claudiareis, felipecruz, heloisamagnani, marialisboa, milenasantana |
| igorfeitosa | 5 | alexlima, igorsouza, marcelofeitosa, tamirislopes, tatianarodrigues |
| lucasferreira | 4 | clebersoares, lucasnada, tatianeribeiro, valeriachacon |

#### Santos City — CM: jaylin (2 BDMs, 8 BDs)

| BDM | BD Count | BD Names |
|---|---|---|
| sabrinafernandes | 4 | brunosalmaso, ericabarbosa, felipebarbosa, giovanabareno |
| renataleite | 4 | jessicarossi, joaocastro, luizmarques, nathaliabernardino |

### 3.2 汇总 Summary

| 维度 | 数量 |
|---|---|
| CMs | 3 (danielalbuquerque, marciojaroslavsky, jaylin) |
| BDMs | 12 |
| BDs (WS赛区: Southern + Western) | 63 |
| BDs (Santos赛区) | 8 |
| **BDs Total** | **71** |

---

## 四、赛区划分 Race Divisions

### 4.1 BD个人排名 BD Personal Rankings (MODULE 3)
- **Tab 1 — Western + Southern 联合赛区**: 63 BDs，按Total总分排名
- **Tab 2 — Santos 赛区**: 8 BDs，按Total总分排名

### 4.2 BDM团队排名 BDM Team Rankings (MODULE 4)
- **统一排名**: 全部12名BDM一起排名，按Avg人均积分排序
- 不分赛区，不分Tab

---

## 五、看板结构 Dashboard Structure

### MODULE 1: Regional Overview 区域总览
- KPI 卡片 (4张): Target Merchants / Assigned to BD / Operating / Total Score
- Day-over-Day 日环比变化 (vs 前一天)
- 三大攻坚方向卡片 (3张): Not Signed / Not Online / Not Operating

### MODULE 2: City Battle Overview 城市作战概况
- 三张城市卡片: Southern / Western / Santos
- 每张包含: Target / Assigned / Unassigned / Operating / Score / Operating Rate
- 每张包含三大方向细分数据

### MODULE 3: BD Personal Rankings BD个人排名
- **两个Tab**: WS联合赛区 / Santos赛区
- 排名列: Rank / BD / BDM / City / 🔴Not Sign / 🟡Not Online / 🟢Not Oper. / HV+2 / Total / Status / Prize
- 点击BD行可展开详情面板 (Lead Name / Direction / Base / HV / Subtotal)

### MODULE 4: BDM Team Rankings BDM团队排名
- **无Tab，统一排名12人**
- 排名列: Rank / BDM / City / BD Count / Team Score / Avg / Status
- 按Avg人均积分降序排列

### MODULE 5: Scoring Rules 得分规则
- 规则速查表

---

## 六、数据更新流程 Daily Update Process

### 6.1 输入
用户每天提供**新数据**（具体格式待确认，可能为Excel或直接数据）

### 6.2 处理
1. 解析新数据，计算每个BD的各方向得分
2. 按固定人员名单过滤（仅本文档名单内的BDM/BD参与排名）
3. 汇总城市和区域级指标
4. 计算日环比变化 (DOD)
5. 生成排名 (BD个人排名 + BDM团队排名)

### 6.3 输出
1. 更新 `order_penetration_dashboard_v4.html`
2. 通过 publish.py 上传至 html-hosting-hub，复用同一UUID
3. 链接不变

---

## 七、预算参考 Budget Reference

| 奖项 | 预算 |
|---|---|
| BD 个人奖 (WS赛区) | R$ 12,500 |
| BD 个人奖 (Santos赛区) | R$ 4,500 |
| BDM 团队奖 | R$ 6,000 |
| **总预算** | **R$ 23,000** |

> 实际支出取决于达标人数

---

## 八、相关文档 Related Documents

- 作战方案: https://km.sankuai.com/collabpage/2777384204
- 激励赛方案: https://km.sankuai.com/collabpage/2776855669
