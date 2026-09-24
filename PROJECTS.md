# SP Metropolitan Region — 业务管理总控

> 负责人: zhangwenle (文乐)
> 区域: SP Metropolitan Region (圣保罗都市圈)
> 更新: 2026-08-24

---

## 核心职责（5大板块）

| # | 板块 | 目录 | 频率 | 关键产出 |
|---|------|------|------|---------|
| 1 | 周报项目 | `projects/1_weekly_report/` | 每周一 | 周报文档 + 标准规范Wiki |
| 2 | 月度绩效考核 | `projects/2_performance_review/` | 每周更新 | 绩效考核进展Wiki |
| 3 | 月度重点项目 | `projects/3_order_penetration/` | 每日/周 | 看板 + 排名Wiki + 激励赛 |
| 4 | Shadow Visit拜访记录 | `projects/4_shadow_visit/` | 每周 | 拜访数据分析Wiki + 周报S3 |
| 5 | 桑托斯破独项目 | `projects/5_santos_breakthrough/` | 持续 | 破独进展追踪 |

---

## 1. 周报项目 `projects/1_weekly_report/`

**定义**: SP Metropolitan Weekly Review，面向BDM/CM团队领导和上级管理层的周度绩效回顾

**关键文档**:
- 父文档(周报合集): contentId 2762619043
- 本期定版(BRT 8.17-8.23): contentId 2782484753 / https://km.sankuai.com/collabpage/2782484753
- 黄金标准(BRT 7.19-7.25): contentId 2777212009
- 周报标准规范Wiki: contentId 2782912177 / https://km.sankuai.com/collabpage/2782912177
- Skill: `~/.openclaw/skills/weekly-report/SKILL.md` (v2.0)
- 本期黄金模板: `templates/weekly_report_0817_0823_golden.md` + `.xml`
- 规范文档: `templates/WEEKLY_REPORT_STANDARD.md`

**周报结构(v2.0)**:
1. 核心概要(1.1管理视角小结 + 1.2 KRI 5行×4列表格 + 1.3管理者绩效压缩版+Wiki链接 + 城市级汇总)
2. 本月重点任务(当月最重要项目进展，不固定Priority Progress)
3. 本月关键过程指标分析(拜访数据独立成章)
4. 竞对动态(⚠️警示+xtable+TOP5+防御案例)
5. 团队人员简报(仅HC相关)

**历史周报**:
| 期次 | contentId | 链接 |
|------|-----------|------|
| 5.17-5.23 | 2764006928 | https://km.sankuai.com/collabpage/2764006928 |
| 6.28-7.4 | 2772488088 | https://km.sankuai.com/collabpage/2772488088 |
| 7.5-7.11 | 2774162871 | https://km.sankuai.com/collabpage/2774162871 |
| 7.19-7.25 (黄金标准) | 2777212009 | https://km.sankuai.com/collabpage/2777212009 |
| 8.3-8.9 | 2779832454 | https://km.sankuai.com/collabpage/2779832454 |
| 8.10-8.16 | 2781403523 | https://km.sankuai.com/collabpage/2781403523 |
| 8.17-8.23 (本期定版) | 2782484753 | https://km.sankuai.com/collabpage/2782484753 |

---

## 2. 月度绩效考核 `projects/2_performance_review/`

**定义**: BDM/CM月度绩效考核进展Wiki，每周更新，周报1.3链接到它

**关键文档**:
- 绩效Wiki: contentId 2782863123 / https://km.sankuai.com/collabpage/2782863123
- 激励方案文档: contentId 2778463728
- 8月KPI权重: NS 20% | CI 35% | Op Rate 15% | Orders 20% | Management 10%
- Recall为框架外指标

**BDM区域映射**:
- eastern_metro: adriananaves, alisaeed, fernandooliveira, tadeumoraes, eduardoalbuquerque
- western_others: thiagoscavazini, lucasferreira, biancaceotto, igorfeitosa, cesararraes
- west_special (Santos): renataleite, sabrinafernandes
- CM: danielalbuquerque(EM), marciojaroslavsky(WO), jaylin(WS)

**更新节奏**: 每周一用户发BDM Excel后触发，5张图表+排名表+KPI拆解+CM对比+行动项

---

## 3. 月度重点项目 — 订单渗透率 `projects/3_order_penetration/`

**定义**: 8月核心专项，SP Metro订单渗透率激励赛(7/27-8/31)，覆盖818家头部商户

**关键文档与工具**:
- 作战方案: contentId 2777384204
- 激励方案: contentId 2776855669
- 每日排名看板Wiki: contentId 2781368014 / https://km.sankuai.com/collabpage/2781368014
- 数据看板(HTML): https://html-hosting-hub.mynocode.host/#/preview/c998d382-7874-4273-8867-1cfe183eed41
- HTML文件: `order_penetration_dashboard_v4.html`
- 规范文档: `templates/ORDER_PENETRATION_DASHBOARD_STANDARD.md`
- 数据文件: `order_penetration_data_0820_final.json` (最新)

**人员**: 12 BDMs / 71 BDs（固定名单，cristianedasilva在fernandooliveira名下）

**计分规则**: 🔴未签约→营业=6分, 🟡未上线→营业=4分, 🟢未营业→恢复=3分, HV(iFood≥20)+2
**达标线**: BD≥15分, BDM人均≥15分

**更新节奏**: 每天，用户发新Excel后触发。同时更新两处：①数据看板(HTML) ②排名Wiki

---

## 4. Shadow Visit 拜访记录 `projects/4_shadow_visit/`

**定义**: 每周拜访记录数据分析，用于周报Section 3和竞对情报

**数据源**: 用户每周一发Excel (`visit_record_*.xlsx`)
- 本期: `visit_record_20260823.xlsx` (2250行, 19列, BRT 8.17-8.23)

**产出**:
- 独立拜访分析Wiki: contentId 2782275898 / https://km.sankuai.com/collabpage/2782275898
- 拜访数据统计(总量/日均/人均/线下率/活跃BD) → 周报S3
- 竞对情报提取(高风险商户TOP5 + 防御案例) → 周报S4
- 每日拜访量图表 → 周报S3

---

## 5. 桑托斯破独项目 `projects/5_santos_breakthrough/`（已并入 7_sushi_day 的 Sushi 部分）

**定义**: Santos区域打破竞对垄断的专项攻坚

**关键文档**:
- 桑托斯42家高库存商户: `santos_42_high_inventory.md`
- Santos跨平台看板: `santos-x-platform-v3.1.html`
- 桑托斯区域总览图: `santos_overall.png`
- Santos区域BDM: renataleite, sabrinafernandes (CM: jaylin)

**状态**: 持续推进中，数据待补充

---

## 7. Santos Sushi Day 专项 `projects/7_sushi_day/`（2026-09-11 新建）

**定义**: Santos 9月头号专项，Sushi 高品质专区（Keeta Premier Zone）招商，10家高偏好商户攻坚

**关键文档**:
- 招商计划(用户定版v1): contentId 2784904100 / https://km.sankuai.com/collabpage/2784904100
- 202608 Sushi Day 复盘: contentId 2783486630 / https://km.sankuai.com/collabpage/2783486630
- 招商资源模板: contentId 2784636204
- 计划快照: `projects/7_sushi_day/sushi_recruit_plan_v1_user_final.md`

**目标**: 10家各拿 ≥6个 40%off+折扣菜 + ≥1独家套餐；首签2家（Renata: Nakazumy / Sabrina: Temakeria Tropical）

**待决**: Premier套餐补贴口径（Mia/Ron）、奖金池R$10,000定档、售罄策略（看首周数据）

**节奏**: 9/11起每周五17:00-23:00上线；随项目推进持续更新本目录

---

## 文件结构总览

```
workspace/
├── PROJECTS.md                          ← 本文件（总控）
├── SOUL.md                              ← 人格定义
├── USER.md                              ← 用户信息
├── TOOLS.md                             ← 工具配置与规范
├── AGENTS.md                            ← 工作规则（禁止修改）
├── MEMORY.md                            ← 长期记忆（主会话读）
├── HEARTBEAT.md                         ← 心跳任务
├── projects/                            ← 5大业务专区
│   ├── 1_weekly_report/                 ← 周报项目
│   ├── 2_performance_review/            ← 月度绩效考核
│   ├── 3_order_penetration/             ← 订单渗透率项目
│   ├── 4_shadow_visit/                  ← 拜访记录项目
│   ├── 5_santos_breakthrough/           ← 桑托斯破独
│   ├── 6_bml_project/                  ← BML项目
│   └── 7_sushi_day/                    ← Santos Sushi Day 专项（Keeta Premier Zone 招商）
├── templates/                           ← 模板与黄金标准
│   ├── weekly_report_0817_0823_golden.md
│   ├── weekly_report_0817_0823_golden.xml
│   ├── WEEKLY_REPORT_STANDARD.md
│   ├── weekly_report_golden_standard.md
│   ├── KPI_PROGRESS_DOC_STANDARD.md
│   ├── kpi_progress_golden_standard.md
│   ├── ORDER_PENETRATION_DASHBOARD_STANDARD.md
│   └── OPR_WEEKLY_TEMPLATE.md
├── memory/                              ← 每日记忆日志
│   └── 2026-MM-DD.md
└── [历史脚本/图表/Excel等]              ← 待整理归档
```

---

## 记忆机制

### 每日记忆 `memory/YYYY-MM-DD.md`
- 每天的工作日志：做了什么、决策、问题、待办
- 由Agent在每个工作session结束时自动写入

### 长期记忆 `MEMORY.md`
- 从每日记忆中提炼的长期价值信息
- 仅在主会话中读取和更新
- 定期维护：清理过时信息，补充新洞察

### 项目记忆 `projects/*/README.md`
- 每个项目目录下有独立README，记录该项目的上下文、数据源、产出、历史
- Agent每次处理该项目时先读对应README

### 工具记忆 `TOOLS.md`
- 各项目的工具配置、链接、contentId等
- 已按板块组织

---

## 版本历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-08-24 | v1.0 | 初始创建，5大业务板块结构化，文件目录建立 |
