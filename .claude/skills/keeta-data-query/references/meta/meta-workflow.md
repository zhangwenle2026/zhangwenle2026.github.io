# 元数据查询工作流（找表/找指标）

**姿态**：你不是搜索引擎，你是数仓导航员。帮用户找到真正能用的表，结合 ETL 代码分析是否满足诉求。

---

## 初始化检查

```bash
kdata meta auth
```

> 鉴权详细说明 → [auth.md](auth.md)

---

## 意图路由

| 意图 | 触发信号 | 分支 |
|------|----------|------|
| **找表** | 表名（`_d/_w/_m`）、"哪张表"、"表结构"、"ETL"、"字段"、"DDL" | A/B/C |
| **找指标** | 指标名（含"率/量/额/价/数"）、"指标口径"、"血缘"、"底层表"、kpiId、英文指标 code | D |
| **可消解模糊** | 用户表达不完整，但可以通过数据集、指标或表元数据收敛 | 先做低成本探查 |
| **不可消解模糊** | 探查后仍无法区分找表/找指标/查数/诊断，或多个候选口径接近 | 先询问用户 |

不要把表层模糊直接等同于追问。先做低成本探查：列数据集/指标候选、`meta origin --list-only`、BI/DataMap/RAG 轻量检索，确认候选能否收敛。探查后仍无法区分任务类型或候选口径时，再向用户提 1-3 个选择题。

---

## 分支 A：用户给出明确表名

```bash
kdata meta table bi <表名>
```

- 有结果 → 进入 ETL 分析
- 无结果 → 提示表名可能有误，自动发起混合检索兜底

---

## 分支 B：用户描述业务场景（三路并行）

```bash
kdata meta table bi <kw1> [kw2...]       # BI + DataMap 关键词
kdata meta table rag "<查询问题>"         # RAG 语义
# 知识库检索见 km-search.md
```

**聚合规则：**
- 多路命中 → 优先推荐
- `permission=true` → 标注「✅ 可直接查询」
- 仅知识库命中 → 标注「来源：数仓文档」
- 三路矛盾时以 RAG 主表为准，BI 做字段验证

---

## 分支 C：用户指定检索方式

按用户指定执行，不强制混合流程。

---

## 分支 D：用户查指标血缘

```bash
kdata meta origin --code <英文code>      # 精确搜索
kdata meta origin --name <中文名>        # 按名称
kdata meta origin --search <关键词>      # 模糊搜索（本地缓存）
kdata meta origin --list-only            # 仅列候选，不查血缘
```

过滤规则：保留 `mart_sailor_global.*`，`sailor_analysis_global` → 替换为 `mart_sailor_global`

> 完整规则 → [origin-lineage.md](origin-lineage.md)

---

## ETL 分析（找完表自动执行，无需用户要求）

取推荐表前 3 张，逐表分析数据来源、粒度、关键字段。

```bash
kdata meta table etl <schema>.<table>
kdata meta table etl <schema>.<table> --code-only
```

> 参数说明 → [etl-reader.md](etl-reader.md)

---

## Hive 数据地图血缘（仅用户明确提到"血缘"时触发）

```bash
kdata meta lineage --table mart_sailor_global.<表名>
kdata meta lineage --table-id <id> --upstream-only
```

> 参数说明 → [hive-lineage.md](hive-lineage.md)

---

## 输出格式 & 拒答规则

> 详见 → [output-format.md](output-format.md)
