# 4. Shadow Visit 拜访记录

> 每周拜访记录数据分析，用于周报Section 3和竞对情报

## 数据源
- 用户每周一发Excel (`visit_record_*.xlsx`)
- 本期: `visit_record_20260823.xlsx` (2250行, 19列, BRT 8.17-8.23)

## 参考文档：巴西拜访周报（全区域AI分析报告）
- contentId: 2782195539 / https://km.sankuai.com/page/2782195539
- 本期: 2026-08-17~08-22
- 覆盖全区域(Central Eastern/Western, Metropolitan, Rio de Janeiro, smbX)，AI自动生成
- **Metropolitan Region数据与本团队Excel完全一致**（81 BD / 2,234次 / 新签186次），可交叉验证
- 额外提供口径: KP触达率(Metro 45.6%)、意向率(43.8%)、时段分布、漏斗(核实160→KP73→沟通35→跟进32)
- Metro下属城市: Southern(37BD/1,075次), Western(32BD/661次), Santos(12BD/498次)
- 竞对情报: IFOOD 260次提及/245门店/35独家, 99FOOD 193次提及/185门店/34独家; 7家竞对锁定松动商机
- KP触达率Metro 45.6% vs Central Eastern 64.6% — 存在≥19pp差距，有改进空间

## Excel字段
| 列 | 字段 | 说明 |
|----|------|------|
| A | 拜访日期 | 格式"YYYY年MM月DD日" |
| B | BD姓名 | |
| C | 区域 | |
| D | 拜访时间 | |
| E-G | 商户信息 | 名称/类型/品类 |
| H | 拜访方式 | 上门/电话 |
| I-N | 竞对/商情 | 99/Yellow/iFood/Red等 |
| O-S | 其他 | 备注/图片/定位 |

## 产出
1. **独立拜访分析Wiki**: contentId 2782275898 / https://km.sankuai.com/collabpage/2782275898
   - 本期(BRT 8.17-8.22)已创建，8个分析章节、6张图表
   - 后续每周可更新为该区域拜访的深度分析沉淀
   - ⚠️ 标题必须双语英文在前: "SP Metro Visit Analysis Report (BRT X.X-X.X) 拜访分析报告"

2. **周报Section 3** (本月关键过程指标分析):
   - 总拜访数 / 日均 / 人均(BD/天) / 线下率 / 活跃BD数
   - 每日拜访量图表 (matplotlib, JPEG, 600px宽)
   - 拜访要点 (3-4条bullet)
   
3. **周报Section 4** (竞对动态):
   - 高风险商户TOP5 (从拜访记录中提取竞对关联)
   - 正面防御案例 (BD成功防御/挽回)
   
4. **新签/运营拜访占比拆分**:
   - 新签拜访 vs 运营拜访的分布

## 分析要点
- 日期范围筛选: BRT 周一到周六 (周日通常无数据)
- 线下率 = 上门拜访数 / 总拜访数
- 人均 = 总拜访数 / 活跃BD数 / 天数
- 目标: 人均≥5次/BD/天，线下率≥95%
- Santos区域虽人少但执行力强(关注亮点)
- 可参考"巴西拜访周报"(contentId 2782195539)交叉验证数据与补充KPI(KP触达率/意向率)
- Metro区域KP触达率45.6%偏低(标杆区64.6%)，漏斗收敛较快(意向率43.8%领先)——拜访质量高但KP触达有提升空间
