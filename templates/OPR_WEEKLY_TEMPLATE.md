# OPR Weekly Progress 模板与更新规范

## 文档定位
- **受众**: CM/BDM/RM（管理者）
- **用途**: 周会材料，可投影/转发
- **风格**: 结论先行、数据驱动、一页概览+详细排名
- **语言**: 中英双语

## 父文档
- 作战方案: contentId 2777384204
- 激励赛方案: contentId 2776855669

## 创建规则
- 每期新建子文档，挂在父文档 2777384204 下
- 标题格式: `OPR Weekly Progress BRT {开始日期}-{结束日期} #{期数}`
- 严禁覆盖历史文档

## 8模块结构

### 1. Executive Summary 执行摘要
- 一句话核心判断
- 3个关键数字表格（Operating / Score / Qualified）
- 🚦 城市状态（Western/Southern/Santos）

### 2. Week-over-Week 环比
- 7项指标: Operating / Score / BDs w score / Zero score / Qualified / Assigned / Unassigned
- 环比变化 + 变化率
- 速度分析（日均增量 + 8/15预测）

### 3. Progress vs Milestones
- 时间轴: 8/3 Kick-off → 8/6 City Review → 8/15 Mid(60%=3,307) → 8/18 Regional Review → 8/24 Final(100%=5,512)
- 当前位置标记
- Red Order数据待BI更新

### 4. City Performance
- 3城市: Target / Assigned / Assignment% / Operating / Op Rate / Score / Avg / Qualified
- 排名 + 一句话点评

### 5. BDM Leaderboard
- 12人统一排名（按Avg Score）
- 前3 🥇🥈🥉 / 后3 🔴
- 环比变化（↑↓）+ 一句话点评

### 6. BD Performance
- Top 5: 姓名/BDM/城市/主方向/得分/环比/亮点
- 达标分布: ≥15 / 11-14 / 6-10 / 1-5 / 0
- 零分/低分名单（需BDM介入）

### 7. Risk & Action
- Top 5风险，不发散
- 每条: 风险 + Owner + Deadline + 状态 + Action
- 管理层必须动作（一句话）

### 8. Next Week Focus
- 3-5个检查点 + 谁看
- 简洁到可抄进会议纪要

## 数据计算规则

### Roster过滤
- 仅统计固定名单内的12 BDM + 71 BD
- 非roster人员不计入排名

### 计分规则
- NS(not sign)→营业: 6分
- NO(not online)→营业: 4分  
- NOP(not operating)→恢复: 3分
- HV(red_order≥20): +2分
- 早鸟(8/15前): +1分（最终8/31仍有效）

### 达标标准
- BD个人: ≥15分
- BDM团队: 人均≥15分

### 环比基准
- 保留上期数据文件（命名: redtop2000_YYYYMMDD.xlsx）
- 对比上期计算变化

## 更新触发
用户发送新Excel → 解析 → 对比上期 → 生成citadelmd → createDocument(parent=2777384204) → 发链接

## 历史数据文件
- /tmp/files/redtop2000_0806.xlsx (上期)
- /tmp/files/redtop2000_0809.xlsx (当前)
- 每次更新后，新文件变为"当前"，原"当前"变为"上期"
