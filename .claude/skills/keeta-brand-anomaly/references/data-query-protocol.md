# 取数协议

## 目录

- 目标
- 数据源
- 指标与维度白名单
- 固定查询脚本
- 埋点要求
- 降级规则

## 目标

本协议沉淀 `keeta-brand-anomaly` 的固定取数主路径。发布后的品牌异动分析优先运行 `scripts/brand_anomaly_evidence.py` 生成 evidence packet，再由 Skill 按 `references/workflow.md` 和 `references/output-format.md` 输出结论。

## 数据源

| 数据源 | 用途 | 状态 |
|--------|------|------|
| 起源标准数据集 `62059636` | 供给侧品牌总览、品牌核心指标、营业/体验/活动/流量/商补主链路 | 固定主路径 |
| 起源标准数据集 `60041382` | 历史分渠道 CTR 补充口径 | 仅在 `references/sql-templates.md` 指定的降级/补充场景使用 |

所有查询通过 `kdata --json standard query` 执行。每条命令必须复用 `skill_tracker.py start` 生成的同一个 `TASK_ID`，并设置包含步骤、Region、日期范围的 `--task-name`。

## 指标与维度白名单

| 场景 | measures | group-by / filter |
|------|----------|-------------------|
| 品牌总览 | `fin_ord_num` | `group-by brand_id,brand_name` |
| 大盘总量 | `fin_ord_num` | 不带 `group-by`；再从品牌明细扣除 `brand_id=0` |
| 品牌五维概览 | `fin_ord_num`, `shop_avg_shop_actual_online_days`, `shop_avg_shop_actual_open_days`, `davg_shop_avg_open_dura`, `shop_oavg_readied_duration`, `paid_order_cancel_rate_merchant_reason`, `davg_fulldisc_open_shop_coverage`, `davg_discount_spu_shop_coverage`, `davg_reduceshipfee_shop_coverage`, `davg_shop_avg_ad_position_shop_entry_exposure_uv`, `davg_shop_entry_exposure_visit_ratio`, `actual_shop_charge_amt_ratio` | `filter brand_id=<brand_id>`, `group-by brand_id,brand_name` |
| 前线权限 | 同上 | 额外带 `--biz-type <bizType>` 与 `--filter <dimCode>=<orgId>` |

指标展示名称必须继续以 `references/sql-templates.md` 的多语言对照表为准，不得自行翻译或改写。

## 固定查询脚本

脚本入口：

```bash
python3 "$SKILL_DIR/scripts/brand_anomaly_evidence.py" \
  --region SA \
  --date-range 20260601~20260607 \
  --prev-date-range 20260525~20260531 \
  --brand-id 12345 \
  --task-id "$TASK_ID" \
  --format json \
  --output /tmp/brand-anomaly-evidence.json
```

本地验证：

```bash
python3 "$SKILL_DIR/scripts/brand_anomaly_evidence.py" --help
SKILL_TRACKER_DRY_RUN=1 python3 "$SKILL_DIR/scripts/brand_anomaly_evidence.py" --self-test --format json
```

脚本输出 JSON 至少包含：

- `status`
- `query_records`
- `sections`
- `summary`
- `errors`
- `data_gaps`

`query_records` 必须保留可复查的完整 kdata 命令、状态、耗时、行数和错误摘要。

## 埋点要求

- Skill 激活后先执行 `skill-metric-reporter` 的 start/end。
- 用户新问题进入业务分析前，先执行 `skill_tracker.py start` 并导出 `TASK_ID`。
- `brand_anomaly_evidence.py` 中每个 kdata 查询节点通过 `skill_tracker.report_script` 上报脱敏脚本节点信息。
- 最终回答前执行 `skill_tracker.py end`。
- 用户回复 👍/👎 后执行 `skill_tracker.py feedback`，反馈必须挂回最近一次已完成或仍活跃的 task。

## 降级规则

| 场景 | 降级方式 |
|------|----------|
| kdata 超时 | evidence packet 标记 `partial` 或 `fail`，`errors` 记录 `timeout`，报告只输出已验证证据和缺口 |
| 权限不足 | 标记 `auth_failed`，提示重新确认角色或申请权限 |
| 返回 0 行 | 写入 `data_gaps`，不得输出确定性归因 |
| 字段/维度不可用 | 写入 `errors`，按 query planning 和待补查项输出 |
| 埋点上报失败 | 仅 stderr 提示，不阻塞取数和报告输出 |
