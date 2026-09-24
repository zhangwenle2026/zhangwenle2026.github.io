---
name: keeta-data-segment-analysis
description: >-
  获取并分析指定人群用户下各类指标的 skill。人群代表符合某些规则的用户集合（如新客、老客、各生命周期用户），
  指标包含浏览、交易、转化等业务数据（如 AOV、补贴率）。当前仅支持固化场景（DBR 用户生命周期监控）。
  触发场景：「分析用户生命周期」「用户生命周期监控」「跑一下 DBR 数据」「各分层用户表现」「查一下各人群指标」。
  支持地区：AE。
tags: Keeta,Data,AE
visibility: private

metadata:
  skillhub.creator: "mengxiangtong"
  skillhub.updater: "mengxiangtong"
  skillhub.version: "V9"
  skillhub.source: "ssh://git@git.sankuai.com/keeta_data_skill/keeta-data-segment-analysis.git"
  skillhub.skill_id: "74009"
  skillhub.high_sensitive: "false"
---

##  SKILLHUB_METRIC_REPORTER_START
执行本 Skill 的任何操作之前，必须先执行 Skill：`skill-metric-reporter`。
按照 `skill-metric-reporter` 的要求完成 `skill_start` 上报后，再去继续本 Skill 正文。
如果 `skill-metric-reporter` 不可用或执行失败，跳过上报，继续执行本 Skill 正文——不得因上报失败而阻塞审阅流程。
本 Skill 全部操作完成后，同样按照 `skill-metric-reporter` 的要求完成 `skill_end` 上报。
##  SKILLHUB_METRIC_REPORTER_END

# Keeta Data Segment Analysis

分析指定人群（用户生命周期分层等）在浏览、交易、转化等维度的核心指标。

---

## 日志上报协议（MUST — 不可跳过）

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

## 执行入口：场景识别

收到用户请求后，**第一步是场景识别**，对照下表找到匹配的固化场景，然后**完整读取对应子协议文件**，以子协议为准执行所有步骤。

| 固化场景 | 触发关键词 | 子协议文件 |
|---------|-----------|-----------|
| DBR 用户生命周期监控 | DBR、用户生命周期、各分层用户、生命周期监控 | `references/scenarios/dbr_lifecycle_monitoring.md` |

> ⚠️ **冲突裁定规则**：若本文件（SKILL.md）与子协议文件内容冲突，**以子协议文件为准**。SKILL.md 只定义通用框架，所有场景细节（SQL、阈值、输出格式、Gate Check）均在子协议中定义。

若用户请求**不属于任何固化场景**，执行[通用红线 - 约束一]中断流程。

---

## 通用红线（Mandatory Constraints）

> 以下约束适用于所有场景，任意一项违反必须立即中断，不得执行任何查询或输出业务分析。

### 约束一：仅支持固化场景

当前版本**仅支持固化场景**。非固化场景禁止执行，回复：

```
当前 skill 仅支持固化分析场景（如 DBR 用户生命周期监控）。
您的需求为临时分析，暂不支持。如需扩展，请联系 skill 维护者。
```

### 约束二：禁止编造数据

- 所有数据均须通过实际脚本查询获取，**禁止编造、估算或直接使用上次缓存的数据**
- 禁止"假装查询后输出结果"：必须实际运行脚本，看到脚本输出的行数和文件路径，再继续后续步骤

### 约束三：Gate Check 不可绕过

- 每个场景子协议都有 Gate Check 步骤，**必须在输出结论前执行**
- Gate Check 由脚本负责检测并以退出码通知（非零 = 失败）
- **任何 Gate 失败时，禁止输出业务趋势结论**，只能执行[失败发布规则]

### 约束四：不得跨场景混用配置

- 不同场景的 SQL、PN 码、日期口径、输出格式严格隔离
- 不得将一个场景的参数（如 region、PN 码）用于另一个场景

---

## 失败发布规则

任一 Gate Check 失败，或任意强制步骤异常退出时，**统一按以下格式回复用户，不得附加任何业务趋势判断**：

```
❌ 执行失败

失败步骤：<步骤名，如 "Gate Check - O/S 自检">
失败原因：<脚本输出的错误信息，原文引用>
已有产物：<已成功生成的文件路径列表，如无则写"无">
下一步动作：<用户应执行的操作，如"请申请表权限后重新运行"或"请联系 skill 维护者">
```

---

## 环境准备（首次使用必读）

所有查询和可视化均通过本 skill 内的脚本直接执行，无需依赖其他 skill。

### Python 解释器路径

| 环境变量 | 典型路径（仅供参考，实际由部署环境决定） |
|---------|--------------------------------------|
| `$CLAUDE_SKILL_HOME` | `<claude_data_dir>/skills/keeta-data-segment-analysis/.venv` |
| `$OPENCLAW_SKILL_HOME` | `<openclaw_data_dir>/skills/keeta-data-segment-analysis/.venv` |

### 依赖包清单

| 包名 | 用途 |
|------|------|
| `matplotlib` | 渲染可视化图表 |
| `requests` | HTTP 请求（仅访问 bi.keetapp.com）|
| `python-dotenv` | 读取 `.env` 工具配置 |
| `browser-cookie3` | SSO 失效时降级读取会话 Cookie |
| `keyring` | browser-cookie3 平台解密依赖 |
| `cryptography` | Cookie 解密底层库 |

### 检查与安装

```bash
SKILL_PIP="${CLAUDE_SKILL_HOME:-${OPENCLAW_SKILL_HOME}}/bin/pip"
[ -f "$SKILL_PIP" ] && "$SKILL_PIP" list | grep -iE "matplotlib|requests|dotenv|browser.cookie|keyring|cryptography"
```

### openclaw 环境更新 shebang

```bash
NEW_PY="${OPENCLAW_SKILL_HOME}/bin/python3"
sed -i '' "1s|.*|#!${NEW_PY}|" scripts/ae_dbr_query.py scripts/ae_dbr_chart.py
```

---

## 场景索引

| 场景 | 子协议文件 | 支持 region |
|------|-----------|------------|
| DBR 用户生命周期监控 | `references/scenarios/dbr_lifecycle_monitoring.md` | AE |

---

## 触发示例

```
用户：帮我跑一下今天的 DBR 数据，region AE
用户：分析一下 AE 区域各生命周期用户昨天的表现
用户：用户生命周期监控，20260519，AE
用户：跑一下生命周期 DBR
```
