# SP Metropolitan Weekly Report Standard / 圣保罗都市圈周报标准规范

> **Golden Standard**: contentId 2782484753 (BRT 8.17-8.23 定版)
> **Parent Doc**: contentId 2762619043 (周报合集)
> **Performance Wiki**: contentId 2782863123 (BDM/CM绩效排名, 每周更新)
> **Last Updated**: 2026-08-23
> **Owner**: zhangwenle (文乐)
> **Version**: v2.0 (8月结构改版)

---

## 1. Document Purpose / 文档定位

面向 **BDM/CM团队领导** 和 **上级管理层** 的周度绩效回顾，提供：
- 本周关键数据变化（KRI 5项核心指标）
- 月度重点任务执行进展（用户指定1-3个最重要项目）
- 关键过程指标分析（拜访数据）
- 竞对威胁和防御动态
- 团队人力配置情况

与KPI进展文档的区别：KPI文档面向全体BD/BDM看自己排名，周报面向管理层看团队全貌。
与绩效Wiki的区别：绩效Wiki包含完整BDM排名/热力图/CM业绩，周报1.3节压缩总结并链接到绩效Wiki。

---

## 2. Language / 语言规范

- **全文英中双语**
- 标题格式: `中文 English` (e.g. `核心概要 Executive Summary`)
- 正文中文为主体 + 斜体英文翻译段落
- 不使用葡萄牙语
- **结论先行**（金字塔原则）
- **不写数据来源行**（用户明确要求删除"数据来源 Data Source"行）

---

## 3. Document Structure / 完整文档结构

### 3.1 Title / 标题

```
SP Metropolitan Weekly Review 圣保罗都市圈周报 (BRT M.DD-M.DD)
```

### 3.2 Complete Section Layout / 完整章节布局

```
📊 1 核心概要 Executive Summary (BRT M.DD-M.DD)          ← h1
  ├─ 1.1 一周小结 Weekly Summary                          ← h2
  │    └─ 管理视角总结，聚焦两部分：①1.2 KRI核心数据 ②2 本月重点任务进展
  │       结论先行，不罗列流水账，不写数据来源
  ├─ 1.2 关键结果指标 Key Result Indicators (KRI)         ← h2
  │    └─ KRI总表 (5行×4列，每行含图表)                    ← table
  │       列: 指标Metric | 目标Target | 图表&数据Chart&Data | 分析与改善Analysis&Actions
  │       8月5个KPI行: NS(20%) | OpRate(15%) | CI(35%) | Orders(20%) | Management(10%)
  ├─── 1.3 管理者绩效结果进展 Manager Performance Progress ← h4 (在KRI表后、城市级前)
  │     └─ 压缩式总结(Top3/Bottom3/团队均值/CI亮点/营业率短板)
  │        + 链接到独立绩效Wiki (contentId 2782863123, 每周更新)
  ├─── 城市级汇总 City-Level Summary                       ← h4
  │     └─ 城市表格 + 3张城市图(新签/营业率/订单)
  │     注意：8月起无DD，所以3张图而非4张
  │     区域: eastern_metro / western_others / west_special

📋 2 本月重点任务 Key Priorities This Month                ← h1
  └─ 订单渗透率提升专项 Order Penetration Rate Improvement  ← h2
       └─ 项目概述 + 相关链接(4个) + 进展表格(维度|进展|下一步)
       不再有Priority Progress表格(与KRI重复)
       不固定任务内容，每月用户给出1-3个最重要任务

📊 3 本月关键过程指标分析 Key Process Indicators Analysis   ← h1
  └─ 拜访数据 Visit Statistics (BRT M.DD-M.DD)             ← h2
       └─ 图表 + 拜访数据表格 + 拜访要点
       (从原Section 5移出，独立成章)

🛡️ 4 竞对动态 Competitor Intelligence                      ← h1
  ├── ⚠️ 警示引用块 + xtable链接
  ├── 高风险商户 TOP 5 High-Risk Merchants                 ← h3
  │    表列: 商户|上期状态|本周更新|风险
  └── ✅ 本周正面防御案例 Positive Defense Cases            ← h3

👥 5 团队人员简报 Team Personnel Briefing                  ← h1
  └─ 人力配置表 + 人力要点(仅HC相关，拜访要点已移到S3)
```

### 3.3 与旧版的关键差异（v1→v2）

| # | 变更 | 说明 |
|---|------|------|
| 1 | KPI从6个变5个 | 8月起移除DD和Visit作为KPI，新增Management(10%)。CI权重最大35% |
| 2 | 1.1 一周小结 | 管理视角，聚焦KRI+重点任务两部分总结，不写数据来源 |
| 3 | 1.3 管理者绩效结果进展 | 压缩BDM排名/热力图/CM业绩三块为一段总结+链接到独立绩效Wiki |
| 4 | Section 2 | 不固定Priority Progress表格，改为当月最重要项目进展(用户给1-3个任务) |
| 5 | Section 3 | 新增"本月关键过程指标分析"，拜访数据从S5移出独立成章 |
| 6 | Section 5 | 只保留HC相关，拜访要点移到S3 |
| 7 | 图表数量 | 从15张调整为12张(周报)+5张(绩效Wiki) |
| 8 | 不写数据来源行 | 用户明确要求删除"数据来源 Data Source"行 |
| 9 | 独立绩效Wiki | contentId 2782863123，每周更新，周报1.3链接到它 |
| 10 | 区域命名 | 改为eastern_metro/western_others/west_special |

---

## 4. Section Details / 各板块详细规范

### 4.1 Section 1.1 — 一周小结 Weekly Summary

**格式**:
```
段落1 (中文): 本周核心结论聚焦两项：①KRI层面[关键数据]；②[本月重点任务]层面[进展]
段落2 (英文斜体): 段落1的英文翻译
```

**内容要点**（必须包含）:
- 聚焦两部分：①KRI核心数据 ②本月重点任务进展
- 结论先行，不罗列流水账
- **不写数据来源行**

### 4.2 Section 1.2 — KRI 总表

**表格结构**: 5行 × 4列（8月，不再6行）

| 列 | 内容 |
|---|------|
| **指标 Metric** | `**# KPI名 (权重%)**` |
| **目标 Target** | 关键数据点 + 斜体英文 |
| **图表 & 数据 Chart & Data** | 内嵌图表 + 补充数据 |
| **分析与改善 Analysis & Actions** | 结论(中文) + Action(英文) |

**5个KPI行** (8月权重):

| 行 | KPI | 权重 | 图表 | 关键数据 |
|---|-----|------|------|---------|
| 1 | 新签 New Signing | 20% | New Signing柱状图 | MTD家数, MH数, 系数均值 |
| 2 | 营业率 Operation Rate | 15% | Op Rate柱状图 | 团队均值%, 系数, vs上期 |
| 3 | 智能营销 Campaign Intelligence | 35% | CI Achievement柱状图 | 分档分布(1.2×N, 1.0×N...) |
| 4 | 订单 Orders | 20% | Orders柱状图 | 达成率%, 实际/目标 |
| 5 | 管理评分 Management Score | 10% | Mgmt Score图表 | CM评定状态 |

**Recall为框架外指标**，不列入5个KPI行中，但可在分析中提及。

### 4.3 Section 1.3 — 管理者绩效结果进展

**格式**: h4标题，压缩为一段总结

**内容要点**:
- 团队综合系数均值 + vs上期变化
- Top3 BDM (名字+系数)
- Bottom3 BDM (名字+系数)
- CI亮点 / 营业率短板
- CM层面简述
- Management Score状态
- **链接到独立绩效Wiki**: [本月管理者绩效考核进展](https://km.sankuai.com/collabpage/2782863123)

### 4.4 城市级汇总 City-Level Summary

**格式**: h4标题（在1.3之后）

**表格**: 3个区域 × 核心指标

| Region | BDMs | Avg Coeff | New Sign | Aug Op Rate | Total Orders |
|--------|------|-----------|----------|-------------|-------------|
| eastern_metro | N | x.xxx | NN (Top, Mid, MH) | xx.x% | NNN,NNN |
| western_others | N | x.xxx | NN (Top, Mid, MH) | xx.x% | NNN,NNN |
| west_special | N | x.xxx | NN (Top, Mid, MH) | xx.x% | NNN,NNN |

**3张图**（8月起无DD，所以3张而非4张）:
1. City New Signing
2. City Op Rate
3. City Orders

**区域映射**:
- eastern_metro: Fernando, Tadeu, Eduardo, Adriana, Ali
- western_others: Thiago, Lucas F., Bianca, Igor, Cesar
- west_special: Renata, Sabrina

### 4.5 Section 2 — 本月重点任务

**不固定Priority Progress表格**。每月用户给出1-3个最重要任务。

**当前月（8月）示例结构**:
- 订单渗透率提升专项 Order Penetration Rate Improvement (h2)
  - 项目概述段落 + 斜体英文
  - 相关链接(4个): 作战方案/激励方案/每日排名看板/数据看板
  - 进展表格: 维度Dimension | 进展Progress | 下一步Next Steps
  - 8月KPI权重附注行

### 4.6 Section 3 — 关键过程指标分析

**新增章节**（从原Section 5移出，独立成章）

- 拜访数据 Visit Statistics (h2)
- 图表: Daily Visit Volume (1张)
- 拜访数据表格: 指标 | 数值
- 拜访要点: 3-4条bullet，每条中文+斜体英文

### 4.7 Section 4 — 竞对动态

- ⚠️ 警示引用块 + xtable链接
- 高风险商户 TOP 5 (h3): 表格 4列(商户|上期状态|本周更新|风险)
- ✅ 本周正面防御案例 (h3): bullet list

### 4.8 Section 5 — 团队人员简报

- 人力配置表: 4行(3区域+汇总) × 5列(区域|CM|实际在岗|BDM分布|异常)
- 人力要点: 仅HC相关（拜访要点已移到S3）

---

## 5. 8月KPI框架 / August KPI Framework

| KPI | 权重 | 目标 | 系数逻辑 |
|-----|------|------|---------|
| 新签 New Signing (NS) | 20% | 积分制K2标准 | MH=5pts, Top=3pts, Mid=1pt per sign |
| 智能营销 Campaign Intelligence (CI) | 35% | 68%达成=系数1.0 | 分档: 1.2x/1.0x/0.8x/0.5x/0.3x |
| 营业率 Operation Rate (OpRate) | 15% | S/A≥95% | 按比例计算 |
| 订单 Orders (ORD) | 20% | 双层系数 0.8~1.2 | Key store coefficient |
| 管理评分 Management (Mgmt) | 10% | CM评定 | 新增KPI |

**Recall**: 框架外指标，不列入5个KPI权重中，但可追踪转化率。

**vs 7月变化**: 移除DD(20%)和Visit(5%)作为KPI；CI从25%→35%；OpRate从10%→15%；新增Management(10%)。

---

## 6. Charts / 图表规范

### 6.1 周报图表清单 (12张)

| # | 图表名 | 类型 | 位置 | 数据来源 |
|---|--------|------|------|---------|
| 1 | New Signing | 柱状图 | KRI行1 | bdm_data.json |
| 2 | Op Rate | 柱状图 | KRI行2 | bdm_data.json |
| 3 | CI Achievement | 柱状图 | KRI行3 | bdm_data.json |
| 4 | Orders | 柱状图 | KRI行4 | bdm_data.json |
| 5 | Mgmt Score | 柱状图 | KRI行5 | bdm_data.json |
| 6 | City New Signing | 分组柱状图 | 城市汇总 | bdm_data.json |
| 7 | City Op Rate | 分组柱状图 | 城市汇总 | bdm_data.json |
| 8 | City Orders | 分组柱状图 | 城市汇总 | bdm_data.json |
| 9 | Daily Visit Volume | 柱状+趋势线 | S3拜访 | visit_record.xlsx |
| 10-12 | (预留位置，根据当月重点任务配置) | — | S2等 | — |

> 注：实际图表数量可能根据当月内容微调，但核心KRI 5张 + 城市级 3张 + 拜访 1张 = 9张固定。

### 6.2 绩效Wiki图表清单 (5张)

| # | 图表名 | 类型 | 位置 |
|---|--------|------|------|
| 1 | BDM Total Coefficient Ranking | 水平柱状图 | BDM排名 |
| 2 | KPI Coefficient Distribution | 热力图/分布图 | KPI拆解 |
| 3 | CI Coefficient Distribution | 分布图 | KPI拆解 |
| 4 | CM Performance Comparison | 分组柱状图 | CM概览 |
| 5 | WoW Progress | 趋势图 | 管理动作 |

### 6.3 图表技术规格

```yaml
尺寸: 600px宽, 330-470px高 (按内容自适应)
格式: JPEG
背景: 白色 #FFFFFF
字体: 英文标签, 10-11pt, 清晰可读
配色:
  绿(好, ≥1.0): #10b981
  浅绿(中上, 0.8): #84cc16
  黄(中, 0.5): #f59e0b
  红(差, ≤0.3): #ef4444
  均值虚线: 灰色 #888888
元素:
  - 每个柱子标注数值
  - 团队均值虚线 (如适用)
  - 目标线 (如适用)
  - BDM按系数降序排列
工具: matplotlib (Python)
```

### 6.4 图表生成与嵌入流程

```bash
# 1. 生成到临时目录
mkdir -p /tmp/files/weekly_charts/

# 2. 上传到当期文档
oa-skills citadel uploadImageToDocument --contentId <当期contentId> --filePath /tmp/files/weekly_charts/chart_xxx.jpg

# 3. 用返回的URL嵌入文档 (markdown image格式)
# ⚠️ 图片必须上传到当期文档的contentId，跨文档URL会被SSO拦截
```

---

## 7. Data Sources / 数据来源与解析

| 数据 | 来源 | 更新频率 |
|------|------|---------|
| BDM绩效 | BDM Excel (用户每周发送) | 周一 |
| 拜访记录 | visit_record_*.xlsx (用户发送或visit-record-query) | 周一 |
| 竞对动态 | 拜访记录中的竞对关联 + 黄页xtable | 周一 |
| 人力配置 | SMB HC Number表 (contentId: 2722032908) | 变动时 |
| 字段翻译 | Wiki (contentId: 2776140204) | 固定 |

**Excel解析注意事项**:
- 文件名格式: `BDM_YYYY-MM-DD-YYYY-MM-DD(dt)_*.xlsx`
- 区分BDM (role_level含"BDM") 和 CM (role_level含"CM")
- dd_region → 区域: eastern_metro / western_others / west_special
- order_target为null时，achievement_rate=1(100%)

**取数优先级**:
1. BI看板 300001446 (https://bi.keetapp.com/v2/dashboard/300001446)
2. 起源数据集 (keeta-data-query skill)
3. Data Center (https://data-center.mykeeta.com)
4. 禁止：记忆/估算值/上期数据延用

---

## 8. Update Workflow / 每周更新SOP

### 输入清单（用户提供）
- [ ] BDM绩效Excel (必须)
- [ ] 拜访记录Excel (必须)
- [ ] 竞对动态补充 (可选)
- [ ] 人力变动信息 (可选)

### 执行步骤

```
Step 1: 新建文档
  oa-skills citadel createDocument --title "SP Metropolitan Weekly Review ..." \
    --parentContentId 2762619043

Step 2: 同步更新绩效Wiki
  oa-skills citadel getDocumentXml --contentId 2782863123
  → 更新BDM排名表/CM表/图表
  → oa-skills citadel updateDocumentByXml --contentId 2782863123

Step 3: 下载解析数据
  - 下载Excel → /tmp/files/bdm_data_MMDD.json
  - 下载拜访记录 → /tmp/files/visit_record_MMDD.xlsx

Step 4: 生成图表 (周报12张 + 绩效Wiki 5张)
  - 保存到 /tmp/files/weekly_charts/
  - 上传到各自文档的contentId

Step 5: 组装周报文档
  - 按定版结构填充各Section
  - 1.3节链接到绩效Wiki
  - 城市级3张图(无DD)
  - S3拜访数据独立成章

Step 6: 上传并验证
  oa-skills citadel updateDocumentByMd --contentId <新contentId> --file <file>
  - [ ] 图表数量正确
  - [ ] 数据与Excel 100%一致
  - [ ] 无"待更新/待补充"占位符
  - [ ] 1.3链接到绩效Wiki可点击
  - [ ] 所有图片可正常显示
```

### ⚠️ 红线规则（5条）

1. **严禁覆盖历史周报** — 每期必须新建子文档
2. **图片必须上传到当期文档** — 跨文档图片被SSO拦截
3. **数据100%与Excel一致** — 不做四舍五入或调整
4. **不写数据来源行** — 用户明确要求删除
5. **新建文档挂在父文档下** — parentContentId: 2762619043

---

## 9. Status Indicators / 状态标识

| 标识 | 含义 | 使用场景 |
|------|------|---------|
| 🔴 | 高风险/远低于目标 | KPI系数≤0.3, 覆盖率<50% |
| 🟡 | 中风险/有改善但未达标 | KPI系数0.5-0.8, 进展中 |
| 🟢 | 达标/健康 | KPI系数≥1.0, 达成目标 |
| ⚠️ | 警示 | 需关注但非高风险 |
| ✅ | 完成/正面 | 防御成功, 任务完成 |

---

## 10. Related Documents / 关联文档

| 文档 | ContentId | 用途 |
|------|-----------|------|
| 周报合集(父文档) | 2762619043 | 所有周报挂在此下 |
| 绩效Wiki | 2782863123 | BDM/CM排名，每周更新，周报1.3链接到它 |
| KPI进展文档 | 2775586864 | BDM/CM看板 |
| 订单渗透看板 | UUID: c998d382-7874-4273-8867-1cfe183eed41 | HTML看板 |
| 排名Wiki | 2781368014 | 订单渗透激励赛排名 |
| 字段Wiki | 2776140204 | 字段中英对照 |
| 黄页竞对xtable | 2762258282 (table 2762634988) | 防御商户列表 |
| SMB HC Number | 2722032908 | 人力配置 |
| 激励方案 | 2778463728 | 8月激励方案 |

---

## 11. Version History / 版本历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-07-27 | v1.0 | 首版规范，基于BRT 7.19-7.25定版周报建立 |
| 2026-08-23 | v2.0 | 8月结构改版：5 KPI(移除DD/Visit, 新增Management)、1.3压缩+绩效Wiki链接、S3拜访独立成章、S5仅HC、12+5图表、不写数据来源行、区域命名更新 |

---

## 12. Appendix: XML Template Key Points / 附录：XML模板要点

基于黄金标准(contentId 2782484753)的结构要点：

1. **KRI表格**: 5行×4列 `:::table` 结构，每行第3列含 `![image](km-url){width height}` 图片节点
2. **1.3节**: h4标题，段落含链接 `[text](https://km.sankuai.com/collabpage/2782863123)`
3. **城市级**: h4标题，`:::table` 3行数据 + 3张图分别在不同 `:::paragraph` 节点
4. **S2进展表**: `:::table` 含"维度|进展|下一步"3列
5. **S3拜访**: h2标题，1张图 + `:::table` 指标表 + bullet list要点
6. **S4竞对**: `> ⚠️` 引用块 + h3子标题 + 表格 + bullet list
7. **S5人员**: `:::table` 4行(3区域+汇总) + bullet list要点
8. **颜色宏**: `:[color]{#009155}绿色[/color]` `:[color]{#D41E21}红色[/color]`
9. **图片语法**: `![alt](km-cdn-url){width height nodeId="..."}`
10. **标题层级**: h1(Section) → h2(子节) → h3(子子节) → h4(1.3/城市级)

**黄金标准文件**:
- Markdown: `templates/weekly_report_0817_0823_golden.md`
- XML: `templates/weekly_report_0817_0823_golden.xml`
