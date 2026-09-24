# 🎯 桑托斯破独 / Santos X — 重点项目

> Santos Exclusivity-Breaking Project
> 最后更新: 2026-07-16

---

## 项目概况 Overview

| 维度 | 内容 |
|---|---|
| **目标** | 破除 Santos 区 iFood/99Food 独家合作商户，转签 Keeta |
| **商户池** | 42 家高优先级 (Santos High) |
| **BDM** | caioguijarro |
| **BD团队** | Victor、Rafael、Pedro、Douglas、Milena |
| **核心BD** | Victor、Pedro、Marcelo、Vinicius |
| **Pipeline 健康度** | 62/100 |
| **Win Rate** | ~19% (8/42 signed) |
| **日均潜力** | 3,926 单/天 |

---

## 🛠 工具平台 Tools & Platforms

| # | 工具 | 地址 | 项目ID | 状态 |
|---|---|---|---|---|
| 1 | **Santos X 作战平台** (客户盘点表) | https://ete0ca.mynocode.host | cli-5687tpoamkafh1g7 | ✅ 在线 |
| 2 | **BD 周日程工具** (周会日历) | https://santos-schedule-tool.mynocode.host | cli-26ik01z7nuhkg8da | ✅ 在线 |
| 3 | ~~客户盘点看板 (横向卡片版)~~ | ~~key-client-analytics.mynocode.host~~ | cli-dq4sc9xrr9cvvmfl | ❌ 已删除 6/29 |
| 4 | **Santos X High 商户跟进盘点表** (看板+表格+BD视图) | https://merchant-status-grid.mynocode.host | cli-egkgjhisnllc8mgd | ✅ 在线 7/16 |

---

## 📝 学城文档 Wiki Documents

| # | 文档名 | 链接 | 说明 |
|---|---|---|---|
| 1 | W4 Santos 破独客户盘点 (Jun 23-27) | https://km.sankuai.com/collabpage/2770731447 | 8客户 Pipeline/CFPPS/Action Matrix |
| 2 | CFPPS & 1 Group, 2 Meetings | (桑托斯核心推进下) | 商机转化管理机制 |
| 3 | BD 本周客户 KP 谈判/签约日程表 | (桑托斯核心推进下) | 周一至周五日历 |
| 4 | 桑托斯作战计划（应对99进场6-7月） | (桑托斯核心推进下) | 战略计划 |
| 5 | 42家高优商户盘点表 (Wiki) | https://km.sankuai.com/collabpage/2775001967 | 7/16更新，8签约/17推进/13高风险/4丢失 |
| 6 | Santos X High List review (盘点会议) | https://km.sankuai.com/collabpage/2771977727 | 盘点会议模板 |

---

## 📊 Santos X 平台迭代历史

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 6/21 | 白色 Material 基础版，3 Tab（商机总览/商家分析/客户盘点） |
| v2.0 | 6/21 | 暗色 Linear/Vercel 风格 |
| v2.1 | 6/21 | Apple/Google 浅色设计，三语 i18n (中/英/葡) |
| v2.7 | 6/21 | 数据修正（42商户）、筛选器 |
| v3.0 | 6/23 | 新增 Tab 0 周会日历 + Tab 1 W4 客户盘点，原 Tab 顺延 |
| **当前** | 6/24 | 精简为仅**客户盘点表**（42家商户，7个筛选器） |
| v4.0 | 7/16 | 新建 merchant-status-grid 项目：看板+表格+BD视图，数据库驱动，SSO认证，三语，Excel导出 |

---

## 🏆 已签约商户 Signed

| 商户 | BD | 日期 |
|---|---|---|
| La Banoffeeria | pedrorosanovaes | 6月 |
| Temakeria Poke | victorvasques | 6月 |
| Guadalupe Restaurante | pedrorosanovaes | 6月 |
| Estrada do Nordeste | victorvasques | 7/16 |
| Esfiharia Santista 2 Original | milenasilva02 | 7/16 |
| O Temakeiro - Zona Noroeste | douglasaraujo | 7/16 |
| O Temakeiro 013 - Marapé | douglasaraujo | 7/16 |
| O Temakeiro - Ponta da Praia | douglasaraujo | 7/16 |

---

## 📁 本地文件

```
/root/.openclaw/workspace/santos-x/
├── README.md              ← 本文件（项目目录）
└── (后续文件放这里)

/tmp/santos_x_repo/        ← NoCode 代码仓库（临时，重启丢失）
├── src/pages/tabs/
│   ├── OpportunityOverview.jsx
│   ├── MerchantAnalysis.jsx
│   └── CustomerInventory.jsx
├── public/dashboard.html
└── ...
```

---

## ⚠️ 注意事项

- NoCode 代码仓库在 `/tmp/` 下，重启后丢失，需重新 `nocode clone`
- Santos X 平台当前仅保留客户盘点表 Tab
- BD 周日程工具支持三语（PT 模式为葡|英|中）、时间延至 22:00
- 42 家商户数据来源: Santos High 客户池
