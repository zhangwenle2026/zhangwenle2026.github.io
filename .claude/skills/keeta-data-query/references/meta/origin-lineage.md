# 起源指标血缘查询

## 能力说明

给定指标名称/code 或 kpiId，自动追溯完整血缘链路：

```
指标名/code → kpiId → 原子指标（派生指标递归展开）→ 数据模型 → 底层 Hive 表 + 字段
```

## 前置条件

- busiLineId 固定为 **274**（Keeta 业务线）
- 起源业务接口通过 `mtcli kdata meta origin-*` 调用。
- 当前 `origin-kpi-list` 的 mtcli schema 仍强制要求 `access-token` header；脚本仅在这一步通过 mtsso/CIBA 获取 token 后传给 mtcli。
- 其他登录态由 mtcli SSO 链路处理；不要通过 CDP 或浏览器 Cookie 读取起源登录态。

---

## 用法

```bash
SCRIPT=scripts/capability5_meta/origin.py

# 直接用 kpiId 查血缘
python3 $SCRIPT <kpiId>
python3 $SCRIPT <kpiId> --json

# 用英文代码精确查（推荐，走起源平台接口）
python3 $SCRIPT --code actual_mt_charge_amt_ratio

# 用中文名模糊查（走起源平台接口）
python3 $SCRIPT --name 实付美补率

# 用本地缓存关键词搜索（兜底，匹配范围更广）
python3 $SCRIPT --search 美补率

# 仅列出搜索结果，不查血缘
python3 $SCRIPT --name 美补率 --list-only
python3 $SCRIPT --search 美补率 --list-only

# 显示指标基础信息（默认关闭，--info 开启）
python3 $SCRIPT --code actual_mt_charge_amt_ratio --info

# JSON 格式输出（供程序解析）
python3 $SCRIPT --code actual_mt_charge_amt_ratio --json

# 查询模型 JOIN 关系
python3 $SCRIPT --code actual_mt_charge_amt_ratio --joins --json
```

---

## 指标查询标准工作流（Agent 遵循）

### Step 1：起源平台直接搜索（优先）
- 用用户提供的指标名/英文 code，调 `--name` 或 `--code` 走起源平台接口
- 精准命中 → 直接进入 Step 4

### Step 2：起源平台无结果 → 改写搜索词
- 结合理解做同义词/英文拼写扩写（如：AOV → 单均价、客单价）
- 继续走起源平台接口重新搜索

### Step 3：仍无结果 → 本地缓存关键词搜索（兜底）
- `--search <keyword>` 查本地 measures 缓存（8860 条）
- LLM 理解选最佳匹配，拿 code → `get_kpi_id_from_origin`

### Step 4：展示候选，确认后查血缘
- 展示：kpiId、code、中文名、口径简述
- 有把握 → 直接查；不确定 → 列候选供用户选择，等确认后再执行

### Step 5：过滤表 + 替换 + 生成样例 SQL
- **只保留** `mart_sailor_global.*` 和 `sailor_analysis_global.*` 的表
- **替换**：向用户展示时 `sailor_analysis_global` 统一替换为 `mart_sailor_global`
- 基于底层表生成 **Presto SQL** 样例（遵循 `references/sql-spec.md` 规范）

---

## 指标基础信息（`--info` 模式输出字段）

| 字段 | 说明 |
|------|------|
| 指标名称/英文名 | 中英文名 |
| 英文代码 | kpiCode |
| kpiId | 起源平台唯一 ID |
| 指标类型 | 原子指标 / 派生指标 |
| 数据类型 | BIGINT / DOUBLE 等 |
| 单位 | %、元、单、无 等 |
| 认证状态 | 已认证 / 未认证 |
| 优化方向 | 越大越好 / 越小越好 |
| 业务/技术负责人 | owner / techOwner |
| 创建/更新时间 | createTime / updateTime |
| 计算公式 | formula（派生指标） |
| 口径定义 | kpiDefine |

---

## 血缘输出图例

```
📐 派生指标（有依赖原子指标）
📊 原子指标（有底层模型表）
❓ 无模型信息

  ├── 模型:  模型名称 (id=xxxxx)
  ├── 引擎:  hive / doris
  ├── 底层表: schema.table_name
  └── 字段:  field_name  |  聚合: sum / count_distinct
```

---

## 错误处理

| 错误 | 原因 | 处理 |
|------|------|------|
| `mtcli 命令失败` | mtcli 登录态缺失、权限不足或服务异常 | 执行 `mtcli auth sso whoami`，必要时执行 `mtcli auth sso login` |
| `无法获取 Origin access-token` | Origin schema 强制 token header，mtsso/CIBA 均失败 | 确认 MOA/大象登录态后重试 |
| `无法获取 kpiId` | origin 平台搜索接口无结果 | 尝试改写搜索词，或手动获取 kpiId 直接传入 |
| 起源平台搜索返回 0 条 | 指标名与平台注册名有差异，或不在 busiLineId=274 | 尝试 Step 2 改写词 / Step 3 本地缓存兜底 |
| 派生指标无原子指标数据 | 起源侧无依赖或接口返回不完整 | 查看 `--json` 输出手动确认 |
| 底层表为空字符串 | formula 格式不标准 | 查看 `--json` 输出里的 `formula` 字段手动确认 |
| access-token 失效 | mtsso/CIBA token 过期或权限不足 | 重新执行命令触发换票，必要时检查权限 |

---

## 标准输出格式（Agent 向用户返回时遵循）

每次指标查询完成后，按以下结构输出：

```
📊/📐 指标名称（英文名）
- kpiId：xxxxx
- 英文代码：xxx_xxx
- 口径：一句话描述
- 指标类型：原子指标 / 派生指标
- 起源链接：https://origin.keetapp.com/kpi/detail/<kpiId>?busiLineId=274

【计算公式】（派生指标必填）
  指标名 = 原子指标A / 原子指标B
  原子指标A（code_a）：xxx 的口径说明
  原子指标B（code_b）：xxx 的口径说明

【推荐底层表】
| 表名 | 字段 | 聚合 | 字段说明 |
|------|------|------|----------|
| mart_sailor_global.xxx | field_name | sum | 说明，金额字段注明单位（如：最小辅币，÷精度=元） |

【可用维度】
  dt（yyyymmdd）、region（SA/HK/AE/QA/KW/BR/BH）、shop_id、...

【样例 SQL】（Presto SQL，遵循 sql-spec.md）
  SELECT ...
  FROM mart_sailor_global.xxx
  WHERE dt >= '20260301' ...

⚠️ 此 SQL 为参考模板，字段名需结合实际表结构确认后再执行。
```

### 字段单位说明规范
- 金额类字段（`*_amt`、`*_gmv`、`*_fee`）：注明「单位：最小辅币，如需展示元需除以对应精度」
- 比率类字段（`*_rate`、`*_ratio`）：注明「单位：小数，如需百分比 ×100」
- 数量类字段（`*_num`、`*_cnt`）：无需换算

### 可用维度推断规则
根据表名推断常见维度，不确定时不列：
- `topic_ord_info_d` → dt、region、shop_id、user_id、order_view_id
- `app_shop_supply_d` → dt、region、shop_id
- `app_cs_service_merged_record_d` → dt、region、order_view_id
- `app_ord_after_sale_refund_compensation_d` → dt、region、order_view_id

---

## 起源模型关系构建查询

### 能力说明

给定起源平台 modelId，获取该模型的：
- **主表**：tableName、dbName、customFilterCondition（主表过滤条件）
- **关联表**：JOIN 类型、关联表名、关联字段对、附加过滤条件（filterConditions）

**原理：** 通过 `mtcli kdata meta origin-model-detail` 获取模型关系构建详情，
解析 `data.modelInfo.detailModel.tableConfig` 中的字段。

### 用法

```bash
SCRIPT=scripts/capability5_meta/origin.py

# 查模型关系构建（表格输出）
python3 $SCRIPT <kpiId> --joins
python3 $SCRIPT --code actual_mt_charge_amt_ratio --joins

# JSON 格式输出（供程序解析）
python3 $SCRIPT --code actual_mt_charge_amt_ratio --joins --json
```

### 响应结构（`--json` 输出）

```json
{
  "main_table": {
    "db": "sailor_analysis_global",
    "table": "app_shop_supply_d",
    "dsn": "doris_default_cluster_sailor_analysis_global",
    "filter": "${...}.dt >= ${...}.operation_date"
  },
  "joins": [
    {
      "seq": 1,
      "join_type": "left join",
      "join_db": "sailor_analysis_global",
      "join_table": "dim_city_region",
      "join_keys": [{"main": "operation_city_id", "join": "city_id", "custom_sql": ""}],
      "filter_conditions": []
    }
  ]
}
```

### filterConditions 说明

`filter_conditions` 是关联表上的附加 WHERE 条件，例如：
```json
{"column": "dim_name", "rule": "=", "value": "'time_period_distribution'"}
```
等价于 SQL：`... ON ... AND dim_com_dimension_label_full.dim_name = 'time_period_distribution'`

---

## 推荐模型选择规则（派生指标有多模型时）

当一个派生指标的多个原子指标各自被多个模型支持时，按以下优先级选模型：

### 规则 1：最少模型原则
- 优先找**同一张底层表/同一个模型同时覆盖所有原子指标**的情况
- 避免多表 JOIN 引入口径差异，减少取数复杂度
- 操作：取各原子指标的模型集合做**交集**，从交集中按规则 2/3 选

### 规则 2：官方模型优先

含以下关键字的模型**优先考虑**（按优先级排序）：

| 优先级 | 关键字 |
|--------|--------|
| 高 | 经营沙盘 |
| 高 | 供给大盘、履约大盘、体验大盘、搜索大盘、补贴大盘 |
| 中 | 罗盘 |

- 相同关键字下，选**不带"SA"、"日"、"new"、"Copy"、"测试"等后缀**的基础版本
- 经营沙盘 > 供给大盘/履约大盘等大盘 > 罗盘

### 规则 3：推荐度（storageUnit）

起源平台 `kpi/tech/get` 接口返回的 `storageUnit` 字段表示模型推荐度：
- `storageUnit=7`：高推荐度
- `storageUnit=2`：普通推荐度
- `storageUnit=None`：未设置

**优先选 storageUnit 更高的模型**，但粒度合适性优先于推荐度数字。

### 查询推荐度的方法

通过 `mtcli kdata meta origin-kpi-tech-get` 查询：

```bash
python3 scripts/capability5_meta/origin.py <kpiId> --json
# 响应路径：tech.data.basicModels[].storageUnit + modelName + modelId
```

或在已有血缘查询结果后，对候选模型逐个核实 storageUnit。

### 综合决策示例（实付补贴率）

```
派生指标：实付补贴率 = 总补贴金额 / 实付交易额

Step1（交集）：
  实付交易额支持模型 ∩ 总补贴金额支持模型
  → 15个同时覆盖的模型，官方模型8个（均指向 app_shop_supply_d 或 topic_ord_promotion_extend_info_d）

Step2（官方关键字）：
  经营沙盘-global-供给（id=60087948）> 供给大盘-doris（id=60057897）

Step3（推荐度）：
  两者 storageUnit 均为2；经营沙盘名称更官方，选 60087948

最终结论：
  1张表（mart_sailor_global.app_shop_supply_d）同时出数
  字段：fin_actual_amt_no_tip（实付交易额）、charge_fee = mt_charge_fee + shop_charge_fee（总补贴）
```
