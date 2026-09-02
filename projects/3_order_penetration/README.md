# 3. 订单渗透率项目 Order Penetration

> SP Metro订单渗透率激励赛 (7/27-8/31)，覆盖818家头部商户

## 核心
- **作战方案**: contentId 2777384204
- **激励方案**: contentId 2776855669
- **每日排名Wiki**: contentId 2781368014 / https://km.sankuai.com/collabpage/2781368014
- **数据看板(HTML)**: https://html-hosting-hub.mynocode.host/#/preview/c998d382-7874-4273-8867-1cfe183eed41
- **UUID**: c998d382-7874-4273-8867-1cfe183eed41
- **HTML文件**: `order_penetration_dashboard_v4.html`
- **规范文档**: `templates/ORDER_PENETRATION_DASHBOARD_STANDARD.md`
- **最新数据**: `order_penetration_data_0827_final.json`
- **最近一次**: 2026-08-28 完成 0827 数据（Excel: redtop2000merchantsstatus-0827.xlsx）

## 人员
- 12 BDMs / 71 BDs
- cristianedasilva 在 fernandooliveira 名下
- 排名结构: BD分赛区(WS/Santos两Tab) + BDM全部12人统一排名无Tab

## 计分规则
| 状态 | 转化目标 | 得分 |
|------|---------|------|
| 🔴未签约 | 营业 | 6分 |
| 🟡未上线 | 营业 | 4分 |
| 🟢未营业 | 恢复 | 3分 |
| HV (iFood≥20) | 加分 | +2分 |

**达标线**: BD ≥ 15分 | BDM 人均 ≥ 15分

## 排名Wiki更新方式
`oa-skills citadel getDocumentXml` → 改表格数据 → `updateDocumentByXml`
- Top15 BD + 8 Santos BD + 12 BDM + Summary
- XML中nodeId保留、达标总分加粗、✅/⚠️/❌状态标注

## 更新节奏
**每天**，用户发新Excel后触发。同时更新两处：
1. 数据看板(HTML) — 更新HTML文件并部署
2. 排名Wiki(contentId 2781368014) — 更新表格数据

## Excel列名变化
列名会随日期变化：如 `sign-0819`→`sign-0820`、`0813-0819 operating`→`0814-0820 operating`
处理时按列名前缀匹配（sign-、operating、musthave等）
