# 输出格式规范 — keeta-data-finder

## 找表回答：四段总-分-总结构

所有找表回答**必须严格**按以下四段输出，不得省略。

---

### 第一段：结论摘要（总）

2-4 句话直接回答：
- 需求能否满足？
- 推荐哪几张表，各适合什么场景？
- 有无明显注意事项？

---

### 第二段：推荐表详情（分 - 表格）

从候选表中语义相关性选出最推荐的 **3 张**。

**选表优先级：** 匹配度 > topic > dim > aggr > fact（禁用 origindb）> 热度

候选 > 3 张时截断并注明：
> 共找到 N 张相关表，已筛选最相关的 3 张。如需查看更多，请说"展开更多"。

**输出表格（列名和内容不加反引号，字段间用「、」分隔）：**

| 表名 | 描述 | 负责人 | 热度 | 权限 | 相关字段（3-5个） | 来源 | 诉求校验 |
|------|------|--------|------|------|----------------|------|--------|

- 权限列：`permission=true` → ✅；`permission=false` → ❌；未知 → —
- 诉求校验列：✅ 满足 / ⚠️ 部分满足 / ❌ 不满足 + 一句话结论

---

### 第三段：分析详情（分 - ETL）

**找完表后默认自动执行，无需用户要求。**

取推荐表前 3 张依次获取 ETL 代码，逐表按以下格式分析：

```
#### mart_sailor_global.topic_xxx
- 数据来源：上游依赖 xxx 表，关联 yyy 表
- 粒度：shop_id + region，天级分区
- 关键字段验证：字段 xxx ✅ 存在，含义符合预期；字段 yyy ⚠️ 存在但为原始量，需自行计算比率
- 注意事项：近365天滚动口径，非当天快照
```

ETL 获取命令：

```bash
python3 ~/.openclaw/skills/keeta-data-finder/scripts/etl/keeta_xt_etl_reader.py \
  fetch --task-name hmart_sailor_global.<表名> --from-source api --format json 2>&1 \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('etl_code','NO ETL CODE'))"
```

> ⚠️ 必须用 `--format json`，`--format text` 不输出完整 ETL 代码

---

### 第四段：最终推荐结论（总）

- **首选**：`<表名>`，原因：...
- **备选**：`<表名>`，适合场景：...
- 使用注意事项（时区、口径、权限申请等）

---

## 表详情卡片（用户要求查看某张表时）

```
**表名** mart_sailor_global.topic_ord_info_d
**描述** 境外订单宽表
**生产任务** hmart_sailor_global.topic_ord_info_d
**权限** ✅ 有权限
**分区字段** region（HK/SA/AE 等）、dt（yyyymmdd）
```

字段列表默认展示前 15 个，展示后询问：
> 以上仅展示部分字段（共 N 个），是否需要查看完整字段列表？

---

## 错误处理

| 错误情况 | 处理方式 |
|---------|---------|
| BI 返回 302/401 | 提示用户先登录 bi.keetapp.com |
| RAG 超时（>60s）或 status!=UP | 跳过 RAG，继续 BI + 知识库 |
| 知识库检索无结果 | 跳过，不影响主流程 |
| ETL 代码获取失败 | 标注「ETL获取失败」，不阻断推荐结果；提示用户登录 xt.keetapp.com 或确认任务名 |
| 三路均无结果 | 告知用户，建议描述更多业务场景，或联系 Keeta 数据组 |
| permission=false | 标注无权限，提示申请数据权限 |

---

## 拒答规则

| 触发条件 | 处理方式 |
|---------|---------|
| 竞对数据（Foodpanda/Uber Eats/Deliveroo 等） | 拒答，引导提 TT |
| 非 mart_sailor_global 库 | 拒答 |
| keemart/小象/O项目/osg 关键词 | 拒答 |
| 匹配度 < 55% 且无 ETL 代码支撑 | 提示用户补充指标/维度/场景 |
