# 1. 周报项目 Weekly Report

> SP Metropolitan Weekly Review 圣保罗都市圈周报

## 核心
- **父文档**: contentId 2762619043 (周报合集)
- **本期定版**: contentId 2782484753 (BRT 8.17-8.23)
- **黄金标准**: contentId 2777212009 (BRT 7.19-7.25)
- **标准规范Wiki**: contentId 2782912177
- **Skill**: `~/.openclaw/skills/weekly-report/SKILL.md` (v2.0)
- **黄金模板文件**: `templates/weekly_report_0817_0823_golden.md` + `.xml`

## 触发
每周一用户发BDM Excel + 拜访记录后触发

## 周报结构 (v2.0)
1. 核心概要 (1.1管理视角小结 + 1.2 KRI 5行×4列 + 1.3绩效压缩+Wiki链接 + 城市级汇总)
2. 本月重点任务 (当月最重要项目，不固定Priority Progress)
3. 本月关键过程指标分析 (拜访数据独立成章)
4. 竞对动态 (⚠️警示 + xtable + TOP5 + 防御案例)
5. 团队人员简报 (仅HC相关)

## 8月KPI框架
NS 20% | CI 35% | Op Rate 15% | Orders 20% | Management 10%
Recall为框架外指标，DD和Visit不再是KPI

## 图表
- 周报: 12张 (matplotlib, JPEG, 600px宽)
- 绩效Wiki: 5张 (独立上传到2782863123)

## 红线
1. 严禁覆盖历史周报 — 必须新建子文档
2. 图片上传到当期文档 — 跨文档被SSO拦截
3. 数据100%与Excel一致
4. 不写数据来源行
5. 新建文档挂在父文档2762619043下

## 历史周报
| 期次 | contentId |
|------|-----------|
| 5.17-5.23 | 2764006928 |
| 6.28-7.4 | 2772488088 |
| 7.5-7.11 | 2774162871 |
| 7.19-7.25 | 2777212009 |
| 8.3-8.9 | 2779832454 |
| 8.10-8.16 | 2781403523 |
| 8.17-8.23 | 2782484753 |
| 8.24-8.30 | 2783167547 |
| 9.7-9.13 | 2786831023 |

## 本期 (BRT 9.7-9.13)
- **contentId**: 2786831023 — https://km.sankuai.com/collabpage/2786831023
- **状态**: 定稿v1 (2026-09-13 用户确认保存；BML数据9.12口径，KRI其余行待BDM Excel)
- **数据目录**: data/20260913/ (visit_record.xlsx, bml_org_summary.json, charts/6张图)
- **注意**: XML推送必须走 updateDocumentByXml（updateDocumentByMd 表格宏会乱）——详见 memory/weekly_report_20260913.md
