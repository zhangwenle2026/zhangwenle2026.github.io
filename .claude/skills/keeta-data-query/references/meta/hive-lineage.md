# Hive 数据地图血缘查询（补充能力）

> ⚠️ **补充能力，平时不主动触发。**
> 仅当用户明确提到「血缘」、「上下游依赖」、「字段来源」、「ETL链路」等关键词时才调用。
> 不要在常规找表/找指标流程中自动插入此步骤。

---

## 能力说明

通过 `mtcli kdata meta datamap-*` 查询：
- **表级血缘**：上游依赖表、下游被依赖表（多层）
- **字段列表**：获取 columnId，为字段血缘查询做准备
- **字段级血缘**：逐层追溯字段的计算来源

登录态由 mtcli SSO 链路处理，不读取浏览器 Cookie。

---

## 核心命令

```bash
SCRIPT=scripts/capability5_meta/lineage.py

# 按表名查血缘（自动搜索 tableId，优先 Keeta dep-sailor 表）
python3 $SCRIPT --table mart_sailor_global.topic_ord_info_d

# 按 tableId 精确查（推荐，避免歧义）
python3 $SCRIPT --table-id 5485

# 只看上游
python3 $SCRIPT --table-id 5485 --upstream-only

# 只看下游
python3 $SCRIPT --table-id 5485 --downstream-only

# 列出字段（获取 columnId）
python3 $SCRIPT --table-id 5485 --columns

# 查字段血缘
python3 $SCRIPT --table-id 5485 --column fin_actual_amt_no_tip

# JSON 输出
python3 $SCRIPT --table-id 5485 --json
```

---

## 场景映射表

| 用户说 | 执行方式 |
|--------|---------|
| 查 topic_ord_info_d 的血缘 | `--table mart_sailor_global.topic_ord_info_d` |
| 查 tableId=5485 的血缘 | `--table-id 5485` |
| 只看上游依赖 | 加 `--upstream-only` |
| 只看下游影响 | 加 `--downstream-only` |
| 列出字段 | 加 `--columns` |
| 查字段 fin_actual_amt_no_tip 来源 | `--table-id <id> --column fin_actual_amt_no_tip` |

---

## 输出格式规范

### 表级血缘输出

```
### 表血缘：mart_sailor_global.topic_ord_info_d（tableId=5485）

**上游表（N 张）**
| tableId | 表名 | 层级 | 描述 |
|---------|------|------|------|

**下游表（N 张，显示前 20）**
| tableId | 表名 | 层级 | 描述 |
|---------|------|------|------|

**关键节点分析**
- 最关键上游：xxx（层级1，所有数据的来源）
- 注意事项：下游 N 张表依赖此表，修改需评估影响范围
```

### 字段血缘输出

```
### 字段血缘：fin_actual_amt_no_tip（columnId=xxxxx）

第0层：mart_sailor_global.topic_ord_info_d.fin_actual_amt_no_tip
第1层：← aggr_xxx.fin_actual_amt_no_tip（直接继承）
第2层：← fact_xxx.actual_pay（计算派生）
...
最终来源：业务系统 xxx，加工层级：N 层
```

---

## 错误处理

| 错误 | 原因 | 处理 |
|------|------|------|
| `mtcli 命令失败` / 401 | mtcli 登录态缺失、权限不足或服务异常 | 执行 `mtcli auth sso whoami`，必要时执行 `mtcli auth sso login` |
| 未找到表 | 表名不存在或不在 dep-sailor | 加全路径 `mart_sailor_global.表名` 重试 |
| 共 N 个匹配 | 表名不唯一 | 用 `--table-id` 精确查询 |
| 字段血缘为空 | 未被血缘系统收录 | 建议用 ETL 代码人工追溯 |

---

## 注意事项

- 搜索接口对 Keeta 表覆盖不全，建议用完整路径：`mart_sailor_global.表名`
- 字段血缘通过 `mtcli kdata meta datamap-lineages` 查询，`type=column`
- 下游表数量可能很大（100+），默认显示前 50，用 `--json` 获取全量
