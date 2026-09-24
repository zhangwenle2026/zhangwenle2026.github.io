---
name: keeta-data-logistics-realtime-alert
description: Keeta 履约实时异动告警配置与管理，适用于三种场景：(1) 履约体验异动告警——基于C端准时率、最近1小时ATA/ME、即将超时任务单占比、接单后取消率等体验指标+阈值，定时查询，异动时触发推送，快速发现体验恶化的地区；(2) 运力供需异动监控——基于实时供需压力指标+阈值，定时查询，异动时触发推送，并结合订单需求、运力总量和运力效率判断供需紧张程度并给出归因方向；(3) 商家出餐体验异动告警——基于积压任务单数、近20分钟平均等餐时长等指标定时查询，触发异动时推送，并返回 Top N 问题商家名单。支持新增/修改/删除告警任务、调整阈值、修改轮询间隔、修改推送目标、查看已有配置，覆盖业务城市和配送区域粒度，支持所有 Keeta 地区。修改已有任务参数无需删旧建新，直接用 --update-job 原地更新。触发词："配置告警"、"新增告警任务"、"设置定时告警"、"修改告警阈值"、"更新告警配置"、"修改告警任务参数"、"调整告警阈值"、"修改轮询间隔"、"调整轮询间隔"、"修改推送目标"、"update-job"、"查看告警任务"、"列出告警配置"、"告警任务列表"、"关掉告警"、"停止告警推送"、"删除告警任务"、"取消自动推送"、"运力异动"、"供需告警"、"出勤监控"、"商家出餐告警"、"卡餐告警"、"商家体验异动"。不适用：历史数据分析（用 keeta-data-query）、离线报表生成、非 Keeta 业务告警、Kafka 实时流消费、数据集/指标定义查询（用 keeta-origin-query）。

appkey: com.sankuai.raptor.iconfont.websdk

metadata:
  skillhub.creator: "liusuwen02"
  skillhub.updater: "liusuwen02"
  skillhub.version: "V21"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "63980"
  skillhub.high_sensitive: "true"
---

# keeta-data-logistics-realtime-alert — Keeta 履约实时异动告警

---

## 依赖 Skill（自动安装）

| Skill | 用途 | 自动安装 |
|---|---|---|
| `keeta-data-query` | Hive/起源数据集查询（核心依赖） | ✅ 自动 |
| `claw-group-speaker` | 群消息推送（仅群推送时需要） | ✅ 自动 |

---

## Skill 介绍（触发时必须先展示）

当用户触发本 skill 时，**必须先主动介绍以下内容**，然后询问用户选择哪个功能：

---

> 🚨 **Keeta 履约实时异动告警** 适用于三种场景：
>
> **场景1：履约体验异动告警**
> 基于C端准时率、最近1小时ATA/ME、即将超时任务单占比、接单后取消率等体验指标+阈值，定时查询，异动时触发推送，快速发现体验恶化的地区。
> 支持粒度：业务城市 / 配送区域 | 覆盖地区：SA / AE / QA / KW / BH / BR（暂不适用于HK）
>
> **场景2：运力供需异动监控**
> 基于预设的供需压力指标+阈值，定时查询，异动时触发推送，并结合订单需求、运力总量和运力效率判断供需紧张程度并给出归因方向。
> 支持粒度：业务城市 / 配送区域 | 覆盖地区：SA / AE / QA / KW / BH / HK / BR
>
> **场景3：商家出餐体验异动监控**
> 基于积压任务单数、近20分钟平均等餐时长作为触发条件，异动时推送并返回 Top N 问题商家名单；同时附带展示卡餐商家数/占比供运营参考。
> 支持粒度：业务城市 / 配送区域 | 覆盖地区：SA / AE / QA / KW / BH / HK / BR
>
> 请问你想创建哪种告警任务？（输入 1、2 或 3）

---

## ⚠️ Agent 执行纪律

**每次触发本 Skill 时，Agent 必须首先执行 `read SKILL.md`，然后再开口回复用户。禁止凭历史对话上下文或记忆直接进入向导流程。**

配置向导中的所有展示内容（指标名称、阈值、表格格式、引导话术）**必须严格从本 SKILL.md 读取或从 `--print-defaults` 命令输出获取**，禁止依赖 Agent 记忆或推测。每次触发向导时必须重新读取本文件，不得凭历史对话上下文给出阈值或指标信息。

**禁止在向导4轮未全部走完前执行 `--setup-cron`（无 `--dry-run`）。所有参数必须通过向导收集完毕，经用户在第4轮明确确认后，才能执行正式注册。**

---

## 配置向导

### 场景1 — 履约体验异动告警

**最少3轮，修改阈值时4轮。**

---

**【第1轮】选地区 + 选粒度 + 确认频率**

询问：
1. 选择国家（单选）：SA / AE / QA / KW / BH / HK / BR
2. 选择监控粒度：业务城市 or 配送区域
3. 告警推送频率（默认10分钟，最低10分钟，低于此值直接拒绝）
4. 告警活跃时段（可选，默认全天 00:00-24:00）：**请填写所选 Region 的本地时间**（如 AE 填 UTC+4 本地时间）

> 📌 **推送语言提示：** 告警推送卡片内容为**英文**（指标名称、归因标签等均为英文展示）。

说明：每个任务只能单选国家（数据集有 Region 权限校验，跨 Region 无权限会跑不出数）。

根据粒度自动匹配数据集（内部映射，**不要向用户展示数据集 ID**）：
- 业务城市 → 内部数据集 A
- 配送区域 → 内部数据集 B

---

**【第2轮】展示可告警指标 + 默认阈值，让用户确认**

内部执行以下命令获取默认阈值（命令输出不展示给用户，仅供 Agent 内部使用）：
```bash
python3 ~/.openclaw/skills/keeta-data-logistics-realtime-alert/scripts/alert.py --print-defaults --dataset <dataset_id>
```

将以下表格展示给用户（**只展示中文名，不展示字段代码**），让用户：① 直接确认全选，② 删减不需要的指标，③ 修改阈值，④ 针对特定城市/区域设置差异化阈值：

| # | 指标 | 默认阈值 | 告警方向 |
|---|---|---|---|
| 1 | C端准时率 | < 87% | 低告警 |
| 2 | 大订单C端准时率 | < 86% | 低告警 |
| 3 | 配送中即将超时任务单占比 | > 12% | 高告警 |
| 4 | L1H C端准时率 | < 88% | 低告警 |
| 5 | L1H 大订单C端准时率 | < 83% | 低告警 |
| 6 | L1H 单均ME（分） | > -6 | 高告警 |
| 7 | L1H ATA（分） | > 36 | 高告警 |
| 8 | L2H 接单后取消率 | > 5% | 高告警 |
| 9 | 降水量（mm） | > 0 | 高告警 |
| 10 | L1H 在线骑手效率 | > 1.5 | 高告警 |

如用户需要修改，进入第2.5轮收集修改内容，再进入第3轮。

---

**【第3轮】推送目标配置**

询问：
> 告警推送给谁？
> - **本人**：输入"本人"，通过你的个人助理发送
> - **大象群**：输入群 ID，格式 `group:<群ID>`，例如 `group:xxxxxxxxxxx`
>
> 一个任务只支持一个推送目标。

**分支 A — 用户选择推送给本人：** 直接进入第4轮确认。

**分支 B — 用户选择群推送：**

第一步：检查配置文件中是否存在 `group_client_id`。

```python
import json, os
path = os.path.expanduser("~/.openclaw/config/keeta-data-logistics-realtime-alert-config.json")
cfg = json.load(open(path))
has_creds = bool(cfg.get("group_client_id", "").strip() and cfg.get("group_client_secret", "").strip())
```

**若凭证已存在（`has_creds == True`）：** 让用户提供群 ID，并主动确认机器人是否已拉入该群，进入第4轮。

**若凭证不存在（`has_creds == False`）：** 展示以下引导，**停留在本轮，等用户提供凭证后再继续**：

> ⚠️ 群推送需要你先在大象开放平台注册一个企业内部应用机器人，作为传声筒。请按以下步骤完成（一次性操作）：
>
> **步骤1：** 打开 [https://dxopen.sankuai.com/home](https://dxopen.sankuai.com/home)，创建「企业内部应用」，记下 `client_id` 和 `client_secret`
>
> **步骤2：** 在应用设置中：开启「机器人」开关 → 开通「用户身份添加机器人」权限 → 开通「发送单聊、群组消息」权限 → 发布应用
>
> **步骤3：** 在目标大象群中，点「添加成员」，搜索机器人名称，将其拉入群
>
> **步骤4：** 把 `client_id`、`client_secret` 和群 ID 发给我，我帮你写入配置

用户提供三个信息后，Agent 执行写入：

```python
import json, os
path = os.path.expanduser("~/.openclaw/config/keeta-data-logistics-realtime-alert-config.json")
os.makedirs(os.path.dirname(path), exist_ok=True)
cfg = json.load(open(path)) if os.path.exists(path) else {}
cfg["group_client_id"] = "<client_id>"
cfg["group_client_secret"] = "<client_secret>"
with open(path, "w") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
```

写入完成后，继续进入第4轮确认。

---

**【第4轮】汇总确认 + dry-run**

内部执行 `--dry-run`，然后将参数摘要（**不含数据集 ID**）展示给用户确认：

```bash
python3 ~/.openclaw/skills/keeta-data-logistics-realtime-alert/scripts/alert.py --setup-cron \
  --dataset <id> --regions <SA,AE,...> --mis-id <用户MIS> \
  --metrics <all 或逗号分隔字段名> --thresholds '<JSON>' --dim-thresholds '<JSON>' \
  --interval <分钟> --push-daxiang --daxiang-target <self 或 group:群ID> --dry-run
```

> **注意：** `--mis-id` 用于 Region 权限校验（将军令）。若用户无所选 Region 的权限，配置流程会在 Round 1 完成后立即中断并提示"无对应Region权限，请重新进行Region选择"。

用户确认后，去掉 `--dry-run` 正式注册。

---

### 场景2 — 运力供需异动监控

**最少3轮，修改阈值时4轮。**

场景2 内部使用两个数据集：`60051927`（供需判断 + 大部分归因指标）和 `60009475`（排班在线率）。数据集 ID 不展示给用户。
第3轮推送目标配置、第4轮汇总确认，逻辑与场景1完全一致。

---

**【第1轮】选地区 + 选粒度 + 确认频率**

询问：
1. 选择国家（单选）：SA / AE / QA / KW / BH / HK / BR
2. 选择监控粒度：业务城市 or 配送区域（配送区域输出按推单量降序 Top 5）
3. 告警推送频率（默认10分钟，最低10分钟）
4. 告警活跃时段（可选，默认全天）：**请填写所选 Region 的本地时间**
5. 推单量过滤门槛（可选）：推单量低于该值的城市/区域不触发告警（`--min-push-ord-num <数值>`）

---

> 📌 **推送语言提示：** 告警推送卡片内容为**英文**（指标名称、归因标签等均为英文展示）。

**【第2轮】展示运力监控指标 + 默认阈值，让用户确认**

**运力实时供需异动分析思路：**

**第一步：供需紧张判断（触发指标，任一超阈值即触发）**

| # | 指标 | 简要说明 | 默认阈值 |
|---|---|---|---|
| 1 | 实时供需比（近20分钟）| 近20min支付订单量/在线骑手数，越高越紧张 | >0.6 |
| 2 | 骑手负载 | 骑手负载任务单量/配送中骑手数 | >0.8 |
| 3 | 未完成超时任务占比 | 超时未完成任务单量/未完成任务单量 | >12% |

**参考指标（仅展示，无阈值）：** ATA（截止当前时段累计值）、已指派未接起超时任务单量。

**第二步：归因方向分析（近10分钟，WoW ±5%/5pp + 3个slot持续性判定异常）**

| 方向 | 指标 | 异常判定 |
|---|---|---|
| 📈 需求激增 | 推单量 | 周同比显著上升 |
| 👥 运力总量不足 | 在线骑手数 | 周同比显著下降 |
| 👥 排班出勤不足 | 排班在线率 | 周同比显著下降 |
| 👥 FL出勤不足 | FL骑手在线率 | 周同比显著下降 |
| 👥 骑手无坐标 | 骑手坐标上报率 | 周同比显著下降 |
| ⚙️ 利用效率偏低 | 配送中骑手数 / 骑手利用率 | 周同比显著下降 |
| ⚙️ 骑手拒单 | 一对一指派拒绝量占比 | 周同比显著上升 |

让用户选择：① 直接确认，② 修改触发指标阈值，③ 对特定城市设置差异化阈值。

如用户需要修改，进入第2.5轮收集修改内容，再进入第3轮。

---

**【第3轮】推送目标配置 / 【第4轮】汇总确认 + dry-run**

同场景1第3、4轮，逻辑完全一致。

---

### 场景3 — 商家出餐体验异动告警

**最少3轮，修改阈值时4轮。**

---

**【第1轮】选地区 + 选粒度 + 确认频率**

询问：
1. 选择国家（单选）：SA / AE / QA / KW / BH / HK / BR
2. 选择监控粒度：业务城市 or 配送区域
3. 告警推送频率（默认10分钟，最低10分钟）
4. 告警活跃时段（可选，默认全天）：**请填写所选 Region 的本地时间**
5. Top N 商家数量（默认5，范围1-20）
> 📌 **推送语言提示：** 告警推送卡片内容为**英文**（指标名称、归因标签等均为英文展示）。

---

**【第2轮】展示可告警指标 + 默认阈值，让用户确认**

内部执行以下命令获取默认阈值（不展示给用户）：
```bash
python3 ~/.openclaw/skills/keeta-data-logistics-realtime-alert/scripts/alert.py --print-defaults
```

**触发指标（任一超阈值即触发告警 + Top N 商家明细下钻）**

| # | 指标 | 默认阈值 | 说明 |
|---|---|---|---|
| 1 | 积压任务单数 | 城市粒度 >100 / 区域粒度 >10 | 当前区域/城市内长时间未被骑手接取的任务单数 |
| 2 | 近20分钟平均等餐时长（分） | > 12 | 骑手到店等待商家出餐的平均时长 |

**补充展示指标（不参与触发，告警卡片中附带展示）**

| # | 指标 | 参考阈值 |
|---|---|---|
| 3 | 卡餐上报商家数 | 城市 >100 / 区域 >10 |
| 4 | 卡餐上报商家占比 | > 10% |

让用户选择：① 直接确认全选，② 删减/修改阈值，③ 修改 Top N 数量。

---

**【第3轮】推送目标配置**

同场景1第3轮，逻辑完全一致。

---

**【第4轮】汇总确认 + dry-run**

内部执行 `--dry-run`，向用户展示确认摘要（**不含数据集 ID**），用户确认后正式注册：

```bash
python3 ~/.openclaw/skills/keeta-data-logistics-realtime-alert/scripts/alert.py --setup-cron \
  --feature 3 --regions <SA,...> --mis-id <用户MIS> --f2-granularity <city/zone> \
  --thresholds '<JSON>' --interval <分钟> --active-hours <HH:MM-HH:MM> \
  --top-n <数字，默认5> --push-daxiang --daxiang-target <self 或 group:群ID>
```

---

## 数据来源（Agent 内部参考，不展示给用户）

> ⚠️ **数据集 ID 属于内部实现细节，在与用户的所有交互中一律不展示。** 仅展示粒度名称（"业务城市" / "配送区域"）。

| 场景 | 数据集 ID | 粒度 | 维度字段 |
|---|---|---|---|
| 场景1 | `60038303` | 业务城市 | `op_city_name` |
| 场景1 | `62059270` | 配送区域 | `delivery_area_name` |
| 场景2 | `60051927` | 城市/区域 | 供需判断 + 大部分归因 |
| 场景2 | `60009475` | 城市/区域 | 排班在线率 |
| 场景3 | `60038303`/`62059270` | 城市/区域 | 卡餐商家数/占比（第一组） |
| 场景3 | `60051927` | 城市/区域 | 积压单数/等餐时长 + Top N 下钻（第二组） |

粒度选择：场景2/3 通过 `--f2-granularity city/zone` 参数选择。

---

## 支持地区及时区

| 地区 | 时区 | 地区 | 时区 |
|---|---|---|---|
| SA | UTC+3（沙特） | HK | UTC+8（香港） |
| AE | UTC+4（阿联酋） | BR | UTC-3（巴西） |
| QA | UTC+3（卡塔尔） | KW | UTC+3（科威特） |
| BH | UTC+3（巴林） | | |

消息头时间戳显示所选地区的**本地时间**。

---

## 占位值过滤规则

数据集在前置条件不满足时返回占位值，alert.py 自动过滤（显示 `-`，不触发告警）：
- `rate >= 9`（900%+）或 `num >= 9000`：高位占位值
- `num <= -999` 或 `rate <= -999`：低位占位值
- 率类指标 `val == 0`：前置条件不满足（`meal_preparation_delay_merchant_ratio` 除外）

---

## 停止/查看任务

```bash
python3 ~/.openclaw/skills/keeta-data-logistics-realtime-alert/scripts/alert.py --list-jobs
python3 ~/.openclaw/skills/keeta-data-logistics-realtime-alert/scripts/alert.py --stop-cron --job-id <job-id>
openclaw cron list / openclaw cron rm <cron-id>
```

---

## 修改任务参数（--update-job）

无需删旧建新，可直接修改已有告警任务的参数。**仅覆盖命令行显式传入的字段**，其余字段保持不变。

```bash
python3 ~/.openclaw/skills/keeta-data-logistics-realtime-alert/scripts/alert.py \
  --update-job --job-id <job-id> [可修改参数...] [--dry-run]
```

### 可修改参数（按 feature 生效）

| 参数 | 说明 | 生效 feature | 备注 |
|---|---|---|---|
| `--thresholds` | 阈值覆盖（JSON） | 全部 | 按指标 merge，F2 可改3个触发指标、F3 可改2个触发指标 |
| `--dim-thresholds` | 差异化阈值（JSON） | F1/F2/F3 | 按城市/区域差异化设置阈值 |
| `--interval` | 轮询间隔（分钟） | 全部 | 变更会**重新注册 cron** |
| `--active-hours` | 活跃时段 | 全部 | 如 `"18:00-22:00"`；格式有误时报错退出 |
| `--metrics` | 监控指标 | 仅 F1 | 新增指标补默认阈值，已有指标保留原阈值 |
| `--daxiang-target` | 推送目标 | 全部 | 变更会**重新注册 cron** |
| `--top-n` | 商家明细 Top N | 仅 F3 | — |
| `--min-push-ord-num` | 推单量过滤门槛 | 仅 F2 | 低于此值的城市/区域不触发告警 |

> ⚠ **不支持修改：** `--regions`（地区）和 `--f2-granularity`（粒度）传入会报错退出，请停旧任务后重建。

**行为说明：**
- 未传入参数或与原值相同 → 提示「未检测到任何参数变更」，不写入
- 改了 `--interval` / `--daxiang-target` → 先删旧 cron 再用新参数重注册
- 建议先用 `--dry-run` 预览变更摘要再正式执行

```bash
# 示例：把 F3 任务活跃时段改为 17:30-21:30、Top N 改为 20
python3 .../alert.py --update-job --job-id f3-ae-05290011-hwdr --active-hours "17:30-21:30" --top-n 20

# 示例：把 F1 任务某个指标阈值调整（其余不变）
python3 .../alert.py --update-job --job-id <job-id> --thresholds '{"ontime_task_ratio":0.86}'
```

---

## Cron Job 注册规范

### 基本参数
- 注册时必须加 `--no-deliver`，告警由脚本内部的 daxiang-sender 负责发送，cron agent 不做二次推送
- 超时设置 **90s**（`--timeout-seconds 90`）
- 时区使用各 Region 本地时区（如 SA 用 `Asia/Riyadh`）

### ⚠️ --message 必须是 LLM prompt（非裸 shell 命令）

**规则1：prompt 格式**
- ✅ `--message 'Execute this shell command exactly once, then reply "DONE" (nothing else): ...'`
- ❌ `--message "export PATH=... && python3 alert.py --cron-run ..."`（agent 不理解裸命令）

**规则2：禁止让 agent 回复 `NO_REPLY`**
- `NO_REPLY` 会让 cron 系统强制重跑 → 脚本被执行两次 → 大象推送两条消息
- ✅ 正确回复：`"DONE"` | ❌ 错误回复：`NO_REPLY`

**规则3：强调"只执行一次"**
- prompt 中必须明确"Do NOT re-run even if output is empty or the command produces no visible output"

### 标准 prompt 模板

```
Execute this shell command exactly once, then reply "DONE" (nothing else). Do NOT re-run even if output is empty or the command produces no visible output:

export PATH="$HOME/bin:$PATH" && python3 ~/.openclaw/skills/keeta-data-logistics-realtime-alert/scripts/alert.py --cron-run --job-id <JOB_ID> 2>/dev/null
```

### 故障恢复

如 cron 因连续错误进入退避，执行以下命令恢复：
```bash
openclaw cron disable <id> && openclaw cron enable <id>
```

---

## 大象推送

**个人推送：** 凭证从 `~/.openclaw/openclaw.json` 的 `channels.daxiang` 字段读取，调用 daxiang-sender，**必须加 `--markdown`**。

**群推送：** 调用 claw-group-speaker。凭证（`group_client_id` / `group_client_secret`）从 `~/.openclaw/config/keeta-data-logistics-realtime-alert-config.json` 读取。

---

## 数据查询权限

实时数据的查询权限由数据侧统一预授权管理。如遇到无查询权限相关的报错，请联系数据 PM Soon Liu（liusuwen02）处理。

---

## 🚨 日志上报协议（MUST — 不可跳过）

> **声明：本 Skill 的埋点数据仅用于优化 Skill 使用体验。只上报配置/执行摘要，不上报 `client_secret`、token、cookie、access key 等凭证；推送目标只记录 `self/group/none` 类型，不记录群 ID 或 UID。用户反馈文字必须原文复制，不要改写。**

本 Skill 通过 `scripts/cli_logger.py` 向 `data.mykeeta.sankuai.com/api/data/ai/cli/log` 上报以下事件：

| cliCommand | 触发时机 | 关键字段 |
|-----------|---------|---------|
| `alert --setup-cron --job-id <id>` | 创建定时任务成功/失败 | feature, regions, granularity, daxiang_target(self/group/none), metrics_codes |
| `alert --update-job --job-id <id>` | 修改已有告警任务成功/失败 | job_id, feature, requested_fields, changed_fields, interval, daxiang_target(self/group/none), metrics_codes, thresholds_custom / dim_thresholds / top_n |
| `alert --cron-run --job-id <id>` | 每次 cron 执行完成 | feature, granularity, total_alerts, kdata_queries, alerted_dims / tense_zone_names |
| `skill-script` | 每次 kdata 查询（节点粒度） | dataset_id, region, cost_ms, rows_count |
| `feedback` | 用户标记告警有效/误报（规划中） | rating(1/-1), comment（用户反馈原文，原文复制，不要改写） |

**去重规则：** `alert --cron-run` 是命令级结果，`skill-script` 是同一次任务内每个 kdata 查询的节点级结果，二者不是重复埋点。

**feedback 事件（告警有效性反馈）**（规划中，接口已就绪）：当用户在对话中对某条告警作出评价时，Agent 应主动调用反馈记录命令：

```bash
python3 scripts/alert.py --feedback --job-id <job_id> --rating 1        # 有用/准确
python3 scripts/alert.py --feedback --job-id <job_id> --rating -1 --comment "用户反馈原文"  # 误报
```

触发词示例：「这条告警有用」「告警准确」「误报了」「这个告警没意义」
