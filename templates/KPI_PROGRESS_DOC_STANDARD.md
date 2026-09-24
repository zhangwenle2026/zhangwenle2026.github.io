# KPI Progress Document Standard / KPI进展文档规范

> **Golden Standard**: contentId 2775586864 (July 2026 version)
> **Template File**: `~/.openclaw/workspace/templates/kpi_progress_golden_standard.md`
> **Last Updated**: 2026-07-27
> **Owner**: zhangwenle (文乐)

---

## 1. Document Purpose / 文档定位

面向 **CM 和 BDM** 阅读的绩效考核进展文档。让每个人一目了然地看到：
- 本月考核标准是什么
- 自己和团队目前的达成情况
- 需要改进的方向

**NOT** a policy manual（不是政策手册）。规则只保留最核心的1-2句话。

---

## 2. Language / 语言规范

- **全文英中双语**
- 标题格式: `English / 中文` (e.g. `Target / 目标`)
- 正文以英文为主，关键术语后跟中文注释
- 不使用葡萄牙语（与旧版不同）
- 语言**精炼专业**，不啰嗦

---

## 3. Document Structure / 文档结构

### 3.1 Header / 文档头

```
Title: [Month Year] Metro KPI Progress / [X]月Metro绩效考核进展
---
Data as of: YYYY-MM-DD | 数据截至YYYY年M月D日
Audience: BD, BDM & CM
Update: Weekly on Monday / 每周一更新
Source: Official incentive plan reference
```

### 3.2 Section Layout / 章节布局

```
📊 Overall Performance Summary / 整体绩效概览       ← h2
  ├─ 综合系数公式（一行）
  ├─ 团队平均系数
  ├─ BDM Overall Ranking / BDM综合排名              ← h3 + 图表
  └─ BDM KPI Coefficient Heatmap / 五维系数热力图   ← h3 + 图表

1️⃣ [KPI Name] / 中文名 (Weight%)                   ← h2
  ├─ Target / 目标                                  ← h3（不超过4行）
  ├─ Progress / 达成进展                            ← h3 + 图表
  └─ Analysis & Actions / 分析与改进                ← h3（不超过3行）

2️⃣ ... (same pattern for each KPI)
3️⃣ ...
4️⃣ ...
5️⃣ ...
6️⃣ ...

📋 BDM Full Data Table / BDM完整数据表              ← h2 + 排名表
📋 CM Performance / CM绩效                          ← h2 + CM表 + 图表
```

### 3.3 KPI Section Rules / KPI板块规则

每个KPI **严格统一**为三个 h3 子节：

| 子节 | 要求 |
|------|------|
| **Target / 目标** | 不超过4行，只写核心规则，不写详细政策 |
| **Progress / 达成进展** | 团队汇总数据 + **必须有图表** + BDM明细 |
| **Analysis & Actions / 分析与改进** | 不超过3行，结论先行，给出具体action |

### 3.4 Current 6 KPIs (July 2026) / 当前6项考核指标

| # | KPI | Weight | Key Metric |
|---|-----|--------|-----------|
| 1️⃣ | New Sign / 新签激活 | 20% | newsign_coefficient |
| 2️⃣ | Op Rate / 营业率 | 10% | op_coefficient |
| 3️⃣ | Campaign Intel / 智能营销 | 25% | campaign_intel_coefficient |
| 4️⃣ | Deep Discount / 深折覆盖 | 20% | deep_discount_coefficient |
| 5️⃣ | Orders / 订单量 | 20% | order_coefficient |
| 6️⃣ | Merchant Visit / 商户拜访 | 5% | (visit data) |

> ⚠️ KPI指标和权重可能每月调整，以官方激励计划为准。

---

## 4. Charts / 图表规范

### 4.1 必须图表 (8张)

| # | 图表名 | 类型 | 位置 |
|---|--------|------|------|
| 1 | BDM Overall Ranking | 水平柱状图 | Overall Summary |
| 2 | BDM KPI Heatmap | 热力图 | Overall Summary |
| 3 | New Sign Progress | 柱状图 | KPI 1 Progress |
| 4 | Operation Rate | 柱状图 | KPI 2 Progress |
| 5 | Campaign Intelligence | 柱状图 | KPI 3 Progress |
| 6 | Deep Discount Coverage | 柱状图 | KPI 4 Progress |
| 7 | Order Achievement | 柱状图 | KPI 5 Progress |
| 8 | CM Performance | 分组柱状图 | CM Section |

### 4.2 图表技术规格

```
尺寸: 600px宽, 350-470px高（按内容自适应）
格式: JPEG
背景: 白色 (#FFFFFF)
字体: 英文标签, 10-11pt, 清晰可读
配色: 
  - 好(≥1.0): 绿色 #10b981
  - 中(0.5-0.8): 黄色/橙色 #f59e0b / #84cc16
  - 差(≤0.3): 红色 #ef4444
元素:
  - 每个柱子标注数值
  - 团队均值虚线
  - 目标线（如适用）
  - BDM按系数降序排列
工具: matplotlib (Python)
```

### 4.3 图表嵌入规则

```
1. 先生成到 /tmp/files/kpi_charts/ 目录
2. 上传到 contentId 2775586864:
   oa-skills citadel uploadImageToDocument --contentId 2775586864 --filePath <path>
3. 用返回的URL嵌入文档（markdown image格式）
4. 不得使用跨文档图片URL（会被SSO拦截）
```

---

## 5. Data Tables / 数据表规范

### 5.1 BDM Full Data Table

列定义（按顺序）：

| 列 | 英文 | 中文 | 数据字段 |
|----|------|------|---------|
| 1 | Rank | 排名 | 按total_coefficient排序 |
| 2 | Name | 姓名 | mis_id |
| 3 | Overall | 综合系数 | total_coefficient |
| 4 | NS(20%) | 新签 | newsign_coefficient |
| 5 | OP(10%) | 营业率 | op_coefficient |
| 6 | CI(25%) | 智能营销 | campaign_intel_coefficient |
| 7 | DD(20%) | 深折 | deep_discount_coefficient |
| 8 | ORD(20%) | 订单 | order_coefficient |

### 5.2 CM Table

同上结构 + 管理权重(5%)

---

## 6. Content Rules / 内容规则

### ✅ 必须遵守

1. **聚焦当月** — 不与上月对比，不出现"vs June/6月"
2. **数据100%准确** — 必须与Excel原表完全一致
3. **精炼** — Target不超过4行, Analysis不超过3行
4. **结论先行** — 金字塔原则，先说结论再展开
5. **双语** — 全文英中双语
6. **图表必备** — 每个KPI的Progress必须配图
7. **排名清晰** — BDM能一眼看到自己在哪个位置

### ❌ 禁止

1. 不写详细政策规则（那是政策文档的事）
2. 不做月度对比（这是进展文档，不是对比报告）
3. 不写冗长分析（3行以内）
4. 不用葡萄牙语
5. 图片不要过大（600px宽度限制）
6. 不hardcode图片URL（每次更新需重新上传）

---

## 7. Update Workflow / 更新流程

### 每周更新（周一）

```
Input:  用户发送最新 BDM 绩效 Excel
Steps:
  1. 下载解析 Excel → /tmp/files/bdm_data_MMDD.json
  2. 生成 8 张图表 → /tmp/files/kpi_charts/
  3. 上传图表到 contentId 2775586864
  4. 更新文档内容（保持结构不变，刷新数据+图表URL）
  5. 更新 "Data as of" 日期
  6. 验证: 数据准确 + 图表显示正常
Output: 更新后的文档链接
```

### 每月初（新月）

```
1. 获取新月的官方激励计划
2. 检查KPI指标和权重是否变化
3. 如有变化: 调整section结构 + 更新Target描述
4. 创建新文档（挂在父文档 2762619043 下）
5. 用新数据填充
```

---

## 8. Data Source / 数据来源

```
Primary:   BDM 绩效 Excel (由用户每周发送)
           文件名格式: BDM_YYYY-MM-DD-YYYY-MM-DD(dt)_*.xlsx
           字段数: 63个 (详见学城Wiki contentId: 2776140204)
           
Secondary: 拜访数据 Excel (visit_record_*.xlsx) → 仅用于KPI 6
           
Reference: 官方激励计划 (学城文档)
           字段Wiki: https://km.sankuai.com/collabpage/2776140204
```

---

## 9. Related Documents / 关联文档

| 文档 | ContentId | 用途 |
|------|-----------|------|
| KPI Progress (本文档) | 2775586864 | 进展展示 |
| 父文档 | 2762619043 | 周报合集 |
| 字段Wiki | 2776140204 | 63字段中英翻译 |
| 绩效看板 | NoCode cli-tg1mfgtxgxzf3o46 | 可视化看板 |
| 周报 (最新) | 2777212009 | BRT 7.19-7.25 |

---

## 10. Version History / 版本历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-07-27 | v3.0 (Golden Standard) | 全面整改: 去除6月对比, 统一结构, 8张图表, 英中双语, 精炼内容 |
| 2026-07-26 | v2.x | 数据更新至7/25, 新增Lucas/Marcio |
| 2026-07-20 | v1.x | 初版, 含6月对比和详细规则 |
