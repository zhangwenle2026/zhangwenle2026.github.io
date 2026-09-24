# 更新README: Sushi Combo Nocode工具 + Wiki联动

## 新增产出 (2026-09-15)
- **Nocode线上工具**: https://nocode.sankuai.com/dqsbwh_fd3697d (chatId cli-0wwmvsfk5tuha1md, 版本fd3697df8b6189a2)
  - Metodologia方法论主页 (定价公式/毛利安全线/1+2+1选品/价格阶梯)
  - 10个商家Tab: 每家4个套餐卡片(角色徽章+价格拆解+设计思路) + 完整菜单表
  - PT/中文语言切换 (顶栏胶囊按钮, localStorage)
  - 单商家直链: ?m=<商户ID> 隐藏Tab导航, 适合KP现场演示
- **学城Wiki 2786704416 step-version 5**: 第3节商家表格加"Combo Plan 套餐方案"列 + 工具使用说明段(双语)
- **数据**: merchant_plans_v2.json (10商家×4套餐, Hive dt=20260912, 618 SKU); gen_v3.py 双语字段生成脚本
- **商家ID速查**: 159578880 Nakazumy, 159551458 Temakeria Tropical, 159480919 Taira, 159401806 Hunoo, 159546958 Fujita San, 159427500 Temaki da Lagoa, 159412112 Lega Lega, 159399427 Gendai, 159529587 Sushi na Praça, 159426181 Koji

## 待办
- Mia确认平台补贴率s(10-30%) → 刷新10家到手价
- Wiki权限: 待Santos BDM mis IDs / 大象群ID
- ⚠️ Nocode重新部署生成新URL → 学城表格链接要同步改
