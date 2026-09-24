# 商家流量效果分析取数协议

## 目录

- 范围和验证状态
- 数据源
- 核心指标
- 支持维度
- 固定查询入口
- 降级规则
- 脚本化边界

## 范围和验证状态

本协议沉淀 `merchant-traffic-analysis` 当前仓库中的看板取数路径，用于后续审查、回归和评测。内容来自 `SKILL.md`、`assets/商家流量效果分析看板.html`、`assets/bi-proxy-server.js` 和 `assets/scripts/keeta_bi_skill.py` 的静态实现。

本轮未执行 live BI 查询；合并前建议用小日期范围和单一 Region 做端到端实跑，确认权限、队列、字段和结果结构仍可用。

## 数据源

| 表 | 用途 |
|---|---|
| `mart_sailor_global.topic_flow_sdk_log_path_expose_d` | 商家入口曝光日志 |
| `mart_sailor_global.topic_flow_sdk_log_path_click_d` | 商家入口点击日志 |
| `mart_sailor_global.topic_flow_sdk_log_path_ord_d` | 商家入口成单日志 |

核心过滤条件：`is_shop_ent = '是'`，表示仅保留商家入口流量。

默认 BI 入口：`https://bi.keetapp.com`，默认数据源为 `dw_hive`，默认引擎为 `onesql`，看板代理默认 Spark 队列为 `root.fra02.hadoop-sailor.query`。

## 核心指标

| 指标 | 口径 |
|---|---|
| 曝光UV | 曝光表中 `union_id` 去重 |
| 点击UV | 点击表中 `union_id` 去重 |
| 成单UV | 成单表中 `is_arrange = 1` 的 `union_id` 去重 |
| 订单量 | 成单表中 `is_arrange = 1` 的 `order_view_id` 去重 |
| CTR | 点击UV / 曝光UV |
| CVR | 成单UV / 点击UV |
| CXR | 成单UV / 曝光UV |

异常分析默认比较窗口：本周日期与上周同期日期对齐，下降超过 20% 视为异常候选。

## 支持维度

基础筛选维度：

- Region：`SA`、`HK`、`AE`、`KW`、`QA`、`BR`、`BH`
- 日期范围：默认昨日，支持自定义范围
- 品牌ID：支持多个品牌 ID
- 页面名称：可搜索下拉
- 资源位名称：级联页面名称筛选

模块维度：

- 品牌流量转化：品牌ID、品牌名称、生命周期分层、页面、资源位、SPU ID、SPU 商品名称
- 品牌流量入口分布：页面、资源位、SPU ID、SPU 商品名称、门店ID、门店名称、门店英文名称
- 品牌流量转化异常：日期、品牌ID、品牌名称、品牌英文名称

## 固定查询入口

| 入口 | 文件 | 说明 |
|---|---|---|
| 看板启动 | `assets/start-dashboard.sh` | 启动本地代理并打开看板 |
| keeta-bi 直连 | `assets/scripts/keeta_bi_skill.py run <SQL> -p <project> -q <queue> --json` | 推荐 SQL 执行入口 |
| 本地代理 | `POST /keeta-bi-query` | 写临时 SQL 文件后调用 `keeta_bi_skill.py run` |
| mtdata 兜底 | `POST /mtdata-query` | 使用 `mtdata bi run` 执行 SQL |
| 直接代理 | `/bi-api/*` | 兼容旧版 BI API 请求 |

## 降级规则

| 场景 | 行为 |
|---|---|
| Cookie 不可用 | 返回可操作错误，引导先登录或刷新 Cookie |
| keeta-bi 脚本缺失 | 返回错误，不继续伪造查询结果 |
| SQL 执行失败 | 返回失败状态和错误摘要，上报 `skill-script` 失败 |
| stdout 非 JSON | 返回解析失败或透传原始 stdout，上报解析结果 |
| mtdata 不可用 | 保留 keeta-bi 直连作为优先路径 |

## 脚本化边界

固定查询主路径已经脚本化在 `assets/scripts/keeta_bi_skill.py` 和 `assets/bi-proxy-server.js` 中。`scripts/skill_tracker.py` 负责 task 生命周期和脚本节点埋点，不参与业务 SQL 生成。

仍需后续补强：

- 用小范围 live 查询验证字段和队列权限。
- 将核心 SQL 构造从 HTML 中进一步抽出为可单测模块。
- 如接入 `keeta-data-eval-manager`，补 routing、data、e2e、failure、evidence gate 用例。
