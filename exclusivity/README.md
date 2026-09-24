# Exclusivity Review Pages 独家盘点网页项目

> 负责人: zhangwenle | 创建: 2026-09-24 | 数据源: SMB Dashboard Exclusividade Tracking (mirror-success-next.mynocode.host/#/exclusivity-tracking)

## 已发布页面

| 区域 | 上线日期 | 链接 | UUID | Owner |
|------|---------|------|------|-------|
| Western (西部) 43案 | 2026-09-22 | https://html-hosting-hub.mynocode.host/#/preview/89889587-4507-4ad2-a658-db1ec5dca8c6 | 89889587-4507-4ad2-a658-db1ec5dca8c6 | zhangwenle (公开) |
| Southern (南部) 23案 | 2026-09-24 | https://html-hosting-hub.mynocode.host/#/preview/2209bad0-0c7a-45d2-bdcd-9e43adf292d5 | **2209bad0-0c7a-45d2-bdcd-9e43adf292d5** | zhangwenle (公开) |

⚠️ 南部旧 UUID 6cc05a5e-8023-4ce6-b01e-50561f9f51b6 已作废（owner zhangwenya06 私有，权限问题无法改公开）。

## 文件清单

- `scrape_excl.py` — 全表抓取（3页，agent-browser eval，"próxima"翻页）→ `excl_fresh2.json`
- `scrape_attitude3.py` — 逐商家点行读 "Status do Contrato"（仅西部用过）→ `excl_attitude3.json`
- `excl_fresh2.json` — 82行原始底表（16列，rm/cm 字段分区域）
- `cases_fresh.json` — 西部43案结构化
- `cases_southern.json` — 南部23案结构化（cm=danielalbuquerque）
- `build_html.py` / `build_western_v3.py` — 西部页构建
- `build_southern.py` — **南部页构建（v1，2026-09-24 定版）**
- `southern_review.html` — 南部页成品 v1
- `western_review.html` — 西部页成品

## 南部 v1 口径（2026-09-24 定版保存）

- 数据: excl_fresh2.json 中 cm=danielalbuquerque 23案（2026-09-19/21 更新）
- **无逐案态度抓取**（当会话浏览器故障），风险分类用 etapa+KP 字段推断:
  - Encerrado → LOST (6案, R$1.79M)
  - KP aceitou → RESOLVED (1案)
  - 大额 Reportado/aprovado → HIGH (3案)
  - 有金额在谈 → MEDIUM (9案)
  - 无情报 → PENDING (4案)
- 头部大案: Gaúcho Figueiras Grill R$1.10M 失守、BAETA GRILL R$450K 失守
- 总已知预付 R$4.01M（失守 1.79M / 争夺中 1.97M）
- KP态度列 = 案件阶段推断（非逐案核实），与西部页有差异

## 更新方式

1. 重新抓取: `python3 scrape_excl.py`（需浏览器可用）→ 更新 excl_fresh2.json
2. 南部重跑: `python3 build_southern.py` → southern_review.html
3. 发布: `cd exclusivity && python3 ~/.openclaw/skills/keeta-data-html-publish/scripts/publish.py publish southern_review.html --name southern-exclusivity-review --mis zhangwenle --creator-name "张文乐" --update 2209bad0-0c7a-45d2-bdcd-9e43adf292d5 --public`
   （更新数据用 --update 同 UUID；**权限必须保持公开**，若权限异常则全新发布换 UUID）

## 教训

- 公开页必须 `--mis zhangwenle --public` 发布；`--update` 不更新 is_private（服务端 bug）
- "2125" 是大象ID不是MIS，加 viewer 无效
