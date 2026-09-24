# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

---

## 📊 KPI进展文档规范

- **规范文档**: `~/.openclaw/workspace/templates/KPI_PROGRESS_DOC_STANDARD.md`
- **黄金模板 (citadelmd)**: `~/.openclaw/workspace/templates/kpi_progress_golden_standard.md`
- **目标文档**: contentId 2775586864
- **更新节奏**: 每周一，用户发Excel后触发
- **图表**: 8张 (matplotlib, 600px宽, JPEG)
- **结构**: 每个KPI = Target + Progress(含图) + Analysis
- **语言**: 英中双语，精炼专业
- **禁止**: 月度对比、冗长规则、葡萄牙语

## 📊 订单渗透激励赛看板规范

- **规范文档**: `~/.openclaw/workspace/templates/ORDER_PENETRATION_DASHBOARD_STANDARD.md`
- **看板链接**: https://html-hosting-hub.mynocode.host/#/preview/c998d382-7874-4273-8867-1cfe183eed41
- **UUID**: c998d382-7874-4273-8867-1cfe183eed41
- **HTML文件**: `order_penetration_dashboard_v4.html`
- **更新节奏**: 每天，用户发新Excel后触发。**同时更新两处**：①数据看板(HTML) ②排名Wiki
- **排名Wiki**: https://km.sankuai.com/collabpage/2781368014 (contentId: 2781368014，同文档更新，标题日期同步改)
- **Wiki更新方式**: citadel getDocumentXml → 改表格数据 → updateDocumentByXml（Top15 BD + 8 Santos BD + 12 BDM + Summary；注意 XML 中 nodeId 保留、达标总分加粗、✅/⚠️/❌ 状态）
- **最近一次**: 2026-08-24 完成 0823 数据（Excel: redtop2000merchantsstatus-0823.xlsx）
- **人员名单**: 12 BDMs / 71 BDs（固定，详见规范文档；cristianedasilva 在 fernandooliveira 名下）
- **排名结构**: BD分赛区(WS/Santos两Tab)；BDM全部12人统一排名无Tab
- **计分**: 🔴未签约→营业=6分, 🟡未上线→营业=4分, 🟢未营业→恢复=3分, HV(iFood≥20)+2
- **达标**: BD≥15分, BDM人均≥15分
- **Excel列名会变**: 如 `sign-0819`→`sign-0820`、`0813-0819 operating`→`0814-0820 operating`，处理时按列名前缀匹配

## 📊 BDM/CM绩效排名Wiki规范

- **文档 contentId**: 2781772631
- **文档链接**: https://km.sankuai.com/collabpage/2781772631
- **数据源**: BDM Excel (dt=20260816, 12 BDM + 3 CM)
- **更新节奏**: 每周一次，用户发新Excel后触发
- **图表**: 7张 (matplotlib, 600px宽, JPEG)
- **结构**: 5大板块 (Overview→BDM Ranking→KPI Breakdown→CM Summary→Action Items)
- **语言**: 英文为主 + 斜体中文翻译
- **KPI权重**: NS 20% + Op Rate 15% + CI 35% + Orders 20% + Mgmt 10% + Recall(额外)
- **颜色标注**: 🟢≥1.0 | 🟡0.5-1.0 | 🔴<0.5
- **激励方案文档**: contentId 2778463728
- **8月激励变更**: Campaign 35%(最大), Op Rate 15%↑, Management 10%(新), DD/Visit移除

## 📋 周报规范 (v3.0 — 9月BML新政格式)

- **规范文档**: `~/.openclaw/workspace/templates/WEEKLY_REPORT_STANDARD_V3.md`
- **Skill文档**: `~/.openclaw/skills/weekly-report/SKILL.md`
- **黄金标准 (9月新政首周)**: contentId 2786831023 (BRT 9.7-9.13)
- **黄金模板文件**: `templates/weekly_report_0907_0913_golden.md` + `.xml`
- **8月黄金标准 (月报/周报)**: contentId 2785450878 / 2783167547 (BRT 8.24-8.30)
- **旧黄金模板**: `templates/weekly_report_0824_0830_golden.md`
- **父文档**: contentId 2762619043（每期新建子文档，严禁覆盖历史）
- **独立绩效Wiki**: contentId 2782863123（每周更新，周报1.3链接到它）
- **更新节奏**: 每周一，用户发Excel+拜访记录后触发
- **图表**: 周报12张 (matplotlib, 600px宽, JPEG)
- **9月KPI权重**: BML 25% | Orders 20% | NS/OpRate/CI 各15% | Management 10%（框架外: 防独500/KM免运50/堂食+3%/召回120）
- **语言**: 中英双语，结论先行，不写数据来源行
- **区域命名**: Southern/Western São Paulo Metropolitan + Santos City（CM: daniel/marcio/jaylin, HC 40/30/12）
- **红线**: 新建不覆盖、图片传当期文档、数据100%准确、不写数据来源行

## 🚨 周报写作红线（血泪教训 2026-05-31）

### ❌ 绝对禁止
- **严禁覆盖历史周报文档**。每期周报必须新建子文档，挂在父文档下，不得 updateDocumentByXml/Md 到上期的 contentId。
- subagent 写周报前必须明确传入"新建文档"指令，而不是"更新文档"。

### ✅ 正确流程
1. **新建子文档**：`oa-skills citadel createDocument` 挂在父文档 contentId: 2762619043 下
2. 每期周报对应独立的 contentId，历史周报 contentId 永远不动
3. 图表必须先生成 → 上传到**新文档**的 contentId 下 → 再嵌入（跨文档图片会被 SSO 拦截）
4. Target 列、格式严格对照黄金标准（BRT 8.17-8.23，contentId: 2782484753）

### 周报黄金标准参考
- 当前定版：https://km.sankuai.com/collabpage/2782484753（BRT 8.17-8.23）
- 绩效Wiki：https://km.sankuai.com/collabpage/2782863123
- 父文档：contentId 2762619043
- 图表用 matplotlib 生成后 uploadImageToDocument 上传至**当期新文档**
- 绩效Wiki图表上传至 contentId 2782863123

## 👥 SP Metro 区域城市/CM/HC 定版映射（2026-09-08 文乐确认）

> 月报/周报 S5 团队人员简报必须使用此城市命名和HC编制，不再用 eastern_metro/western_others/west_special 旧命名

| 城市名 | CM | HC编制 |
|---|---|---|
| Southern São Paulo Metropolitan | danielalbuquerque | 40 |
| Western São Paulo Metropolitan | marciojaroslavsky | 30 |
| Santos City | jaylin | 12 |
| **Metro Total** | — | **82** |

- 在岗数据(2026-08): Southern 39, Western 28, Santos 10, 合计77 (93.9%)
- HC底表: SMB HC Number (contentId 2722032908)


