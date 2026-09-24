# MEMORY.md — 长期记忆

> 从每日记忆中提炼的长期价值信息
> 仅在主会话中读取和更新

---

## 用户
- **Name**: zhangwenle (文乐)
- **Role**: SP Metropolitan Region业务管理
- **Timezone**: Asia/Shanghai (BRT+11h)
- **偏好**: 结论先行、不要废话、直接给干净内容

## 核心工作（5大板块）

### 1. 周报
- v2.0结构定版: 5 Section结构（核心概要→重点任务→过程指标→竞对动态→团队简报）
- 8月KPI: 5个(NS 20% | CI 35% | OpRate 15% | Orders 20% | Mgmt 10%)，DD和Visit不再是KPI
- 标准规范Wiki: contentId 2782912177
- Skill v2.0: `~/.openclaw/skills/weekly-report/SKILL.md`
- 黄金模板: BRT 8.17-8.23 (contentId 2782484753)

### 2. 绩效考核
- 独立Wiki: contentId 2782863123 (每周更新)
- 周报1.3链接到绩效Wiki，不在周报堆详细排名
- Management Score是8月新增KPI(10%)，CM评定

### 3. 订单渗透率
- ✅ **已结项 (2026-09-15)**：激励赛7/27-8/31，预算R$23,000=实发R$23,000
- 最终: 20/71 BD达标(28.2%)，2/12 BDM达标(igorfeitosa/adriananaves)
- BD R$18,500 (WS 17人+Santos 3人双金并列) + BDM R$4,500
- 发放明细Wiki: contentId 2787412306；结项存档: projects/3_order_penetration/
- 若9月出新激励赛再开新篇章
### 4. Shadow Visit
- 拜访数据从原Section 5移出，独立为Section 3
- 独立拜访分析Wiki: contentId 2782275898（每周更新）
- 线下率98.3%保持高位；5工作日口径人均5.5次/BD/天，57% BD达标
- Santos执行最强(8.3次/BD/天)，Western产能最低(4.1次/BD/天)
- Santos新签同意率8.6% vs Southern 27.7%，转化是破独瓶颈

### 5. 桑托斯破独
- **Sushi Day 目标口径 (2026-09-18 定版)**: 10家目标商户，本月至少签约6家；每签约商户≥2个40%OFF折扣菜+≥2个Keeta独家套餐（命名必须含"Só no Keeta"）；基础目标12+折扣菜和12+套餐（最低门槛非上限）。两份Wiki(2784904100招商计划/2786704416 BDM Briefing)已全量对齐该口径，完成定义=签约≥6家+taskid绑定
- **Sushi Day Combo工具 (2026-09-15)**: 稳定外链 https://sushi-combo-creator.mynocode.host (PT/中文切换 + 单商家直链 ?m=<商户ID>)
  - 10商家×4套餐(Hive真实SKU)；浅色主题终版 commitId 34268e94929ad165f0faf9ecc7490223bbfa3b87
  - 宣讲Wiki 2786704416 §3已挂'Ver Plano'链接列(浅色版稳定地址)
- **两份Wiki已英中双语化 (2026-09-16, 英语会议用)**:
  - 招商计划 2784904100: EN主文+灰色CN，stepVersion 465
  - BDM Briefing 2786704416: blocker配对/§8交叉引用/R$10,000加粗已修复，工具链接指向浅色稳定地址
- Santos 10人团队，拜访量498次(人均41.5次)执行力最强
- 42家高库存商户清单已建
- 转化率是瓶颈：执行力→签约转化需要策略支持

## Business Platform 看板
- **Dashboard ID**: BI #300001446
- **NoCode URL**: https://html-hosting-hub.mynocode.host/#/preview/7fb461e7-0c98-4440-bcf6-bfceca5c17aa
- **UUID**: 7fb461e7-0c98-4440-bcf6-bfceca5c17aa
- **更新节奏**: 每日
- **生成脚本**: `fetch_bi_v2_fast.py` → `gen_bp_dashboard.py` (正常) / `gen_bp_dashboard_v2.py` (workaround)
- **已知问题 (2026-09-12起)**: "Last 10 Days" 系列图表全部返回 0 行，疑似 BI 后端数据管道问题
- **Workaround**: 改用 Merchant List 图表数据（~12,000行单日快照），数据会有几天滞后
- **最新更新**: 2026-09-15 (v3.2, 使用 2026-09-11 Merchant List 数据)

## 项目目录结构
```
workspace/projects/
├── 1_weekly_report/       — 周报
├── 2_performance_review/  — 绩效考核
├── 3_order_penetration/   — 订单渗透率
├── 4_shadow_visit/        — 拜访记录
└── 5_santos_breakthrough/ — 桑托斯破独
```
每个目录有README.md记录项目上下文。
总控文件: `PROJECTS.md`

## 重要教训
- **严禁覆盖历史周报**：每期必须新建子文档（血泪教训2026-05-31）
- **图片上传到当期文档**：跨文档图片被SSO拦截
- **不写数据来源行**：用户明确要求删除
- **周报1.1管理视角**：聚焦KRI+重点任务两部分，不罗列流水账
- **Excel列名会变**：处理时按前缀匹配，不要硬编码完整列名
- **文档标题必须英语或双语（英文在前）**：如 "SP Metro Visit Analysis Report (BRT 8.17-8.22) 拜访分析报告"（2026-08-24确认）

## 8月结构改版关键决策
1. KRI从6个→5个(移除DD/Visit，新增Management)
2. 1.3压缩BDM排名/热力图/CM业绩，链接到独立绩效Wiki
3. Section 2不固定Priority Progress，改为当月最重要项目
4. Section 3新增"关键过程指标分析"，拜访独立成章
5. Section 5只保留HC相关
6. 图表: 周报12张 + 绩效Wiki 5张
