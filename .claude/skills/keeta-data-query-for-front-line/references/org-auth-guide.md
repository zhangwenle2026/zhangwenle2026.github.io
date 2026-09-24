# 组织架构权限查询（`kdata-fl org`）

查询当前用户的组织架构权限，了解自己有哪些业务线/层级/维值的访问权限。

底层通过 `mtcli kdata standard list-org-lines/list-org-nodes/list-org-node-values` 查询，不再直接调用 data-center 鉴权接口。

## 命令一览

```bash
# 1. 查询我有权限的业务线
kdata-fl org lines

# 2. 查询某业务线下的层级维度
kdata-fl org nodes --biz-type 1001

# 3. 查询某层级下我有权限的维值
kdata-fl org values --biz-type 1001 --node-type 10001

# 4. 校验特定维值是否有权限（传 --org-ids 过滤）
kdata-fl org values \
  --biz-type 1001 --node-type 10001 --org-ids 北京 上海 广州
```

## 典型调用流程

```
kdata-fl org lines
  → 拿到 bizType（如 1001）

kdata-fl org nodes --biz-type 1001
  → 拿到有权限的 orgNodeType（如 10001=大区）

kdata-fl org values --biz-type 1001 --node-type 10001
  → 拿到所有有权限的维值
```

## 输出示例

`org values` 输出会标记每个维值的权限状态：

```
共 1 个维值（其中 0 个有权限）：
  ❌ orgId=BR  BR

共 1 个维值（其中 1 个有权限）：
  ✅ orgId=BR_SA_felipegomez_joaocardoso  João Cardoso
```

> ⚠️ `org values` 会返回该层级下所有维值（含无权限的），必须看 ✅/❌ 标记判断真实权限，只有 ✅ 的维值才能用于查询。

## 查询时的权限校验与数据过滤

### `--biz-type`：仅做权限校验（不过滤数据）

`--biz-type` 只校验用户是否有该业务线的权限，不会按组织架构维值过滤数据。

### `--filter <dimCode>=<orgId>`：鉴权维度过滤（一线权限用户必传）

一线权限用户不传鉴权维度 filter，API 会直接报错：`当前登录用户为一线权限, 筛选条件中必须包含组织架构鉴权维度`。

dimCode 和 orgId 来自 `org values` 输出中标记为 ✅ 的维值。
CLI 会从 `--filter <dimCode>=<orgId>` 自动反推 orgNodeType 并校验该维值权限；不需要用户额外传 `--org-node-type` / `--org-ids`。

```bash
# ✅ 正确：--biz-type 校验 + --filter 传入 ✅ 有权限的鉴权维值
kdata-fl standard query --dataset <数据集ID> --measures fin_ord_num \
  --date 20260318~20260318 --region <Region> \
  --biz-type <bizType> \
  --filter <dimCode>=<orgId>

# ❌ 错误：不传 filter → 一线权限用户直接报错
# ❌ 错误：传了 ❌ 无权限的维值 → 报错「无维度 xxx 维值 xxx 的权限」
```

> ⚠️ **注意**：
> - `--biz-type` 为必传参数，不可跳过
> - `--filter <dimCode>=<orgId>` 一线权限用户必传，dimCode 和 orgId 必须来自 ✅ 有权限的维值
> - 传入 ❌ 无权限的维值会报错
