# 供给大盘看板操作指引

> **适用范围**：仅用于 Step 1（大盘整体表现分析），目标是**获取波动贡献 Top N 的品牌 id 列表**。
> 拿到品牌 id 后，后续 Step 0 + 模块 1-5 全部通过 SQL 完成，不再使用看板。

## 看板 URL

```
https://data-center-eu.mykeeta.com/#/dataPanel/sailor_data_tools_report_merchant_overview_new?region={REGION}&locale=zh&lang=zh
```

将 `{REGION}` 替换为实际 Region（大写，如 `QA`、`SA`、`AE`、`KW`）。

---

## 操作步骤（Step 1 专用）

### 1. 打开页面，切换 Region

使用 agent-browser 打开上述 URL（替换 region 参数），等待加载完成。

> ⚠️ 页面默认使用 SA Region。如果 URL 中 region 参数不生效，需要手动点击页面右上角的 Region 下拉框（如「科威特」）切换到目标 Region。

### 2. 定位「订单量」指标

页面处于**经营分析** tab（默认）。在指标列表中向下滚动，找到「订单量」行，读取当前 WoW 数值。

### 3. 点击「降维」按钮

点击「订单量」同一行右侧的「降维」按钮，等待降维面板弹出。

### 4. ⛔ 降维面板无法切换维度到品牌id（已验证，直接跳过）

**结论：降维面板的维度固定为「业务城市名称」，无法通过任何浏览器操作切换到「品牌id」。**

已尝试并失败的方式：
- JS click / dispatchEvent（click、mousedown、mouseup、pointerdown）
- 真实鼠标坐标点击（mouse move + down + up）
- 「保存当前组合」后再查询
- Vue 实例直接操作（无法访问 Vue 3 响应式状态）

「配置展示维度」弹窗控制的是**大盘主表格列**，不控制降维子面板的维度。

**→ 直接跳到步骤 5，改用 SQL 获取品牌波动贡献数据。**

### 5. 通过 SQL 获取品牌波动贡献 Top N

直接查 `topic_shop_supply_d`，按波动贡献排序：

```sql
SELECT
    brand_id, brand_name,
    SUM(CASE WHEN dt='{current_dt}' THEN fin_ord_num ELSE 0 END) AS ord_curr,
    SUM(CASE WHEN dt='{prev_dt}' THEN fin_ord_num ELSE 0 END) AS ord_prev,
    ROUND((SUM(CASE WHEN dt='{current_dt}' THEN fin_ord_num ELSE 0 END)
         - SUM(CASE WHEN dt='{prev_dt}' THEN fin_ord_num ELSE 0 END))
        / NULLIF((SELECT SUM(fin_ord_num) FROM mart_sailor_global.topic_shop_supply_d
                  WHERE dt='{prev_dt}' AND region='{REGION}'), 0) * 100, 2) AS contribution_wow_pct
FROM mart_sailor_global.topic_shop_supply_d
WHERE dt IN ('{current_dt}', '{prev_dt}') AND region = '{REGION}' AND brand_id != 0
GROUP BY brand_id, brand_name
ORDER BY contribution_wow_pct ASC
LIMIT 10
```

跳过 brand_id = 0 的行，取 Top 3 降幅最大的品牌。

### 6. 切换到 SQL 流程

将品牌 id 列表传给 Step 2，**立即切换到 SQL，不再操作看板**。

---

## 备选方案：从「品牌明细」tab 读取数据

如果「降维」→ 「配置展示维度」操作遇到阻碍，可改用品牌明细 tab：

1. 点击「品牌明细」tab
2. 确认日期为目标分析日期（WoW 自动计算）
3. 通过 CDP JS 直接读取 `document.querySelectorAll('table')[3]` 的 tbody 数据
4. 列映射：brand_id(0), brand_en(2), GMV WoW(10), 订单量指标值(29), 订单量 WoW(31)
5. 按订单量 WoW 升序排列，取 Top 3（降幅最大的）

> ⚠️ 读取后代码层过滤 `brand_id = 0` 的行，不纳入分析。
> 注意：品牌明细 tab 默认只显示第一页（30条），共 2533 个品牌，只取头部降幅最大的品牌即可。

---

## 错误处理

| 问题 | 解决方案 |
|------|----------|
| 页面需要登录 | 触发 sso-qrcode-login skill 完成扫码 |
| 页面加载超时 | 等待 5 秒后重试，最多 2 次 |
| 降维面板「配置展示维度」无法点击 | 使用 agent-browser 坐标点击（非 JS click），或改用品牌明细备选方案 |
| Service Worker 导致 fetch/XHR 拦截失效 | 直接读 DOM table 数据，无需网络拦截 |
