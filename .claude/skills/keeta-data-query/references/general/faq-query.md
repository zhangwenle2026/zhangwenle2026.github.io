# FAQ - 查询与使用

[← 返回目录](faq.md)

---

### Q9：现在支持哪些查询能力？
当前主要能力如下：

| 能力 | 入口 | 适用场景 |
|---|---|---|
| 起源标准数据集 | `kdata standard ...` | 经营指标、维度下钻、环比同比、占比和波动贡献 |
| 元数据找表 | `kdata table ...` / `kdata meta ...` | 搜表、查字段、查血缘、看 ETL、找指标来源 |
| Hive SQL | `kdata hive ...` | 标准数据集无法覆盖的自定义 SQL 口径 |
| 魔数资源 | `kdata dataset ...` / `kdata template ...` | 个人数据集指标/维度/SQL 源码、SQL 模板列表/内容 |
| BI 看板 | `references/moshu/dashboard-v2.md` / `xbr.md` / `dashboard-v1.md` | XBR、Dashboard v2/v1 取数，或读取仪表板结构和筛选器元数据 |

标准数据集、Hive、元数据找表、魔数资源都通过 mtcli 调用；看板取数通过浏览器页面自动化。

---

### Q10：该优先用标准数据集还是 Hive？
经营指标优先用标准数据集，因为口径稳定、速度快、权限申请更清晰。

只有在以下情况切到 Hive：

- 标准数据集没有覆盖用户口径。
- 用户明确给出 SQL、表名或要求自定义明细口径。
- 需要查原始表字段、分区或 ETL 逻辑。

写 Hive SQL 前必须先用 `kdata table info` 或 `kdata meta table ...` 验证表名和字段。

---

### Q11：魔数个人数据集和 SQL 模板还能查吗？
能。继续使用历史兼容的 `kdata dataset ...` / `kdata template ...` 命令；底层走 `mtcli kdata moshu ...`，不再走直连 BI HTTP 或浏览器登录态。

常用命令：

- 个人数据集列表：`kdata dataset list`
- 个人数据集详情：`kdata dataset info <subjectId>`
- SQL 模板列表：`kdata template list`
- SQL 模板详情：`kdata template show <templateId>`

---

### Q12：怎么读取魔数看板？
把 `bi.keetapp.com` 或 `mdbi.bi.st.keetapp.com` 看板链接发给 AI，并说明要读哪些 KPI、表格或截图。Skill 会按 URL 路由到 `dashboard-v2.md`、`dashboard-v1.md` 或 `xbr.md`；只查结构、筛选器、指标/维度定义时走 `dashboard-meta.md`。

看板数据适合“读取已有页面展示内容”，不适合替代标准数据集或 Hive 做大范围明细查询。

---

### Q13：查询慢怎么办？
先确认是否走了 Hive。Hive 需要排队、预检、提交、轮询和拉结果，天然比标准数据集慢。

提速方式：

- 经营指标尽量改用 `kdata standard query`。
- Hive 查询先限制日期、Region 和字段，避免全表扫。
- 只需要找表、字段或口径时，不要执行 SQL，使用 `kdata table` / `kdata meta`。

---

### Q14：AI 没有真正调用 Skill 怎么办？
如果回复没有命令、没有数据来源、没有 task 生命周期提示，可能是普通对话模型在猜答案。处理方式：

1. 开新会话或发送 `/new`。
2. 明确要求“使用 keeta-data-query 查询”。
3. 指定目标能力，例如“先用标准数据集查”或“先找 Hive 表，再生成 SQL”。
