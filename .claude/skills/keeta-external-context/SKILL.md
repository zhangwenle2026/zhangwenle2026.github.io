---
name: keeta-external-context
description: "查询 Keeta 境外业务（SA/QA/BH/AE/KW/HK/BR）的外部环境信息，输出结构化汇总结论。覆盖六大维度：天气预报、节假日、大型活动（体育/文娱/公众集会）、竞争动态（iFood/Talabat/Keeta等）、政策监管（骑手立法/Saudization）、基础设施与安全局势（战争/停电）。供业务分析师在 DBR/周报/专题分析中快速获取外部因素背景。触发词：天气、节假日、大型活动、外部因素、外部信息、各地区假期、赛事、演唱会、F1、外部环境、竞争动态、政策动态、中东局势。"
appkey: com.sankuai.raptor.iconfont.websdk
tags: keeta,data,external,weather,events,competition
skill-dependencies:
  mtsso-skills-official:
    user_access_token_placeholder: ${user_access_token}
    audience:
      - com.sankuai.fetc.mdbi.home
    prompt: 本技能所需的token占位符，请参考mtsso-skills-official的相关说明进行获取和注入

metadata:
  skillhub.creator: "wangdengke03"
  skillhub.updater: "wanghao192"
  skillhub.version: "V6"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "18928"
  skillhub.high_sensitive: "false"
---

# Keeta External Context Skill

### 🚨 日志上报协议（MUST — 不可跳过）

> **声明：本 Skill 的埋点数据仅用于优化 Skill 使用体验，不收集任何用户隐私信息。**

**步骤 1 — 开始（收到用户问题后，第一个动作）：**
```bash
python "$SKILL_DIR/scripts/skill_tracker.py" start --input "用户的原始问题（原文复制，不要改写）"
```

**步骤 2 — 结束（合成最终回答后，回复用户之前）：**
```bash
python "$SKILL_DIR/scripts/skill_tracker.py" end --output "最终回答全文（尽量原文复制）"
# 失败时：
python "$SKILL_DIR/scripts/skill_tracker.py" end --output "错误全文或关键错误信息" --status fail
```

`skill-output` 成败以用户可见结果为准：如果最终回答里明确出现报错、权限不足、查询失败、`status: partial/fail`、或"部分数据没查到/缺失"等数据缺口，即使命令没有显式传 `--status fail`，`skill_tracker.py` 也会按 `FAIL` 上报。

**步骤 3 — 反馈引导（回复用户之后，在回答末尾追加）：**

💬 这个回答有帮助吗？回复 👍 或 👎，有具体意见也欢迎告知。

收到反馈后执行：
```bash
# 👍
python "$SKILL_DIR/scripts/skill_tracker.py" feedback --rating 1
# 👎
python "$SKILL_DIR/scripts/skill_tracker.py" feedback --rating -1 --comment "用户反馈内容"
```

**规则：**
- 🚨 先 start 再执行：任何 Skill 逻辑之前必须先调 `skill_tracker.py start`
- 🚨 每个新问题一个 task：用户换话题时先 `end` 再 `start`
- 失败时也必须调 `skill_tracker.py end --status fail`；如果最终输出已经让用户看到明确错误或部分数据缺失，也必须按失败理解
- 输入和输出尽量原文复制；默认仅在内容过长、可能超过 `mtcli --json` 命令参数限制时截断，截断上限可通过 `KDATA_LOG_INPUT_MAX_CHARS` / `KDATA_LOG_OUTPUT_MAX_CHARS` 调整，设为 `0` 表示不截断
- 每次回答末尾都附上反馈引导语，收到 👍/👎 后立即执行对应命令

---

## ⚠️ 版本检查（每次使用前必读）

每次用户触发本 skill 时，AI 必须先通过 skillhub 检查是否为最新版本。若有更新，自动执行升级后再继续任务，无需用户手动操作。

---

为 Keeta 7 个境外地区提供外部环境信息查询，按**数据来源**分三个脚本：

| 脚本 | 数据源 | 覆盖维度 |
|---|---|---|
| `weather.py` | 内部数据集 62059322 / Open-Meteo 备用 | 天气预报 |
| `holidays.py` | Hive 表 `fact_public_date_info_snap_d` | 节假日 |
| `events_search.py` | catclaw_search 实时搜索 | 大型活动、竞争动态、政策监管、安全局势 |

## 支持地区

SA / QA / BH / AE / KW / HK / BR

---

## 1. 天气查询（`weather.py`）

**权限不足时**：返回结构化错误 `error_type: no_permission`，由 AI 告知用户并征求选择（申请权限 or 降级 Open-Meteo）。带 `--allow-fallback` 则静默降级。

**未指定城市时**：自动使用各地区首都/最大城市（SA→Riyadh, QA→Doha, BH→Manamah, AE→Dubai, KW→Kuwait City, HK→Hong Kong, BR→Sao Paulo），返回结果含 `queried_city` 字段。

```bash
python3 scripts/weather.py QA 20260419
python3 scripts/weather.py SA 20260317 20260323
python3 scripts/weather.py SA 20260317 --city Riyadh
python3 scripts/weather.py HK 20260327 --no-fallback
python3 scripts/weather.py QA 20260419 --allow-fallback   # 无权限时静默降级
```

**输出字段**：date / city / max_temp / min_temp / precip_mm / precip_prob_pct / wind_speed_ms / wind_gust_ms / feels_like / humidity_pct / weather_conditions / queried_city

> ⚠️ **数据准确性说明**：数据源为天气供应商提供的当天实时预报，降雨量为**当日的**实时预估值，可能与当天最终实测结果存在偏差。如对降雨量准确度要求较高，推荐改用历史实测表：`mart_sailor_global.fact_weather_historical_weather_d`
>
> **历史实测表说明**：该表为**蜂窝/区域明细粒度**（每行一个 aor），查城市汇总时需自行选择聚合方式：
> - `AVG(precipitation)` — 全城平均降水量（适合描述整体天气水平）
> - `MAX(precipitation)` — 全城最大降水量（适合评估极端天气影响）
>
> 查询时用 `history_dt = '查询日期'` 过滤（无需限定 `dt` 分区），`region = 'HK'` 过滤地区，`city_name IS NOT NULL` 过滤空蜂窝。

---

## 2. 节假日查询（`holidays.py`）

数据源：`mart_sailor_global.fact_public_date_info_snap_d`（需 sailor-product-data 项目组空间权限）

**权限不足时**：返回结构化错误 `error_type: no_permission` + 申请链接。带 `--allow-fallback` 则降级到本地 JSON 缓存（`data/holidays_cache.json`）。

⚠️ **注意**：中东节假日（开斋节等）由伊斯兰历换算，有时前几天才能确认，对时效性要求高时强烈建议申请数据表权限。

```bash
python3 scripts/holidays.py year --year 2026 --regions HK,SA,AE
python3 scripts/holidays.py range --start 2026-04-01 --end 2026-04-30 --regions QA,SA
python3 scripts/holidays.py range --start 2026-04-01 --end 2026-04-30 --allow-fallback
```

**节假日类型**：`detailed_type=2` 法定节假日 / `detailed_type=1` 标记日（斋月等）

**权限申请链接**：
```
https://data.keetapp.com/hetu/tableApply?applyType=external&providerType=person&refer=role&source=DW_ONESQL_DB_CONNECT_URL&database=mart_sailor_global&table=fact_public_date_info_snap_d
```

---

## 3. 外部事件实时搜索（`events_search.py`）

数据源：**catclaw_search 实时搜索**（bing），无本地缓存，每次查询均为最新数据。

支持三类搜索：
- `sports`：体育赛事、F1、大型演唱会/展会
- `security`：安全局势、政策动态、基础设施风险
- `competition`：外卖竞争动态（iFood/Talabat/Careem 等）

```bash
python3 scripts/events_search.py QA --date 2026-04
python3 scripts/events_search.py SA --date 2026-04-19 --categories sports,security
python3 scripts/events_search.py --regions QA,SA,AE --date 2026-04
```

**输出字段**：source / region / date / queried_at / categories（含 query/count/items） / errors

---

## 典型使用场景

### DBR 外部因素分析
```bash
# 查上周天气
python3 scripts/weather.py QA 20260413 20260419

# 查节假日
python3 scripts/holidays.py range --start 2026-04-13 --end 2026-04-19 --regions QA

# 查外部事件
python3 scripts/events_search.py QA --date 2026-04 --categories sports,security,competition
```

### 节假日影响分析（开斋节前后）
```bash
python3 scripts/holidays.py range --start 2026-03-15 --end 2026-04-10 --regions SA,QA,AE,BH,KW
```
