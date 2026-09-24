# 分析 Skill 流程进度

## 元信息

- 模式：Mode A 创建/初始化分析 Skill 仓库 + Mode D 加埋点；本轮：Mode B 审查诊断分析 Skill（埋点合规）
- 状态文件：/Users/tiantian/workspace/keeta-data-analyze-skill/keeta-data-segment-analysis/.skill-dev/progress.md
- 目标 Skill：keeta-data-segment-analysis
- 目标目录：/Users/tiantian/workspace/keeta-data-analyze-skill/keeta-data-segment-analysis
- 当前步骤：Mode C Step 5 发布闭环
- 下一步：等待用户确认是否 commit/push 开发分支
- 最近更新：2026-06-23 Asia/Shanghai

## 已确认信息

- 分析问题：获取并分析指定人群用户下各类指标，当前固化为 AE DBR 用户生命周期监控。
- 核心指标/口径：生命周期分层、SAB 漏斗、浏览/交易/转化指标、AOV、补贴率；按 T1、T2、T8、T9 做 DoD/WoW 对比。
- 典型问题：分析用户生命周期、用户生命周期监控、跑 DBR 数据、各分层用户表现、查各人群指标。
- 支持范围：AE；默认 T-1；固化 DBR 生命周期场景。
- 输出形态：CSV 证据文件、Markdown 表格、PNG 图表、自然语言总结。
- 用户确认项：使用 Friday SkillHub id=74009 安装并以 Git source 初始化本地仓库。

## 步骤状态

| Step | 状态 | 完成条件 | 备注 |
|------|------|----------|------|
| Step 0 初始化/恢复流程状态 | done | 状态文件已创建 | 本文件记录 |
| Step 1 收集信息 | done | 必要输入已确认 | 信息来自 SkillHub 安装包与 SKILL.md |
| Step 2 生成分析设计和命名 | done | Skill 名称、场景名、分析蓝图已确认 | `keeta-data-segment-analysis`，场景为 segment / AE DBR lifecycle |
| Step 3 输出骨架文件 | done | 目标文件内容或改动方案已生成 | 已 clone Git source 并补齐线上 metadata |
| Step 4 Checklist 自查 | done | 所有检查项有状态 | 语法、CLI help、diff 检查通过 |
| Step 5 发布与建仓指引 | done | 发布、建仓、绑定 Git 指引已输出 | 仓库已存在并作为 origin 绑定 |
| Mode D Step 1 确认目标 Skill | done | 目标目录和 Skill 名已确认 | 本地 clone 目录 |
| Mode D Step 2 写入埋点模块 | done | `scripts/skill_tracker.py` 已写入 | 来自 dev-spec 模板 |
| Mode D Step 3 插入日志上报协议 | done | `SKILL.md` 已插入协议 | 同时补 Layer 1 reporter 块 |
| Mode D Step 4 接入节点埋点 | done | 业务脚本已接入并验证 | 查询和图表脚本已接入并通过静态验证 |
| Mode D Step 5 输出变更摘要 | done | 摘要输出给用户 | 本次交付完成 |
| Mode B Step 0 初始化/恢复流程状态 | done | 状态文件已读取并更新 | 2026-06-23 本轮埋点合规审查 |
| Mode B Step 1 收集材料 | done | SKILL.md、references、scripts、埋点文件已获得 | 已读取 dev-spec review/add-tracking/spec/template 与目标文件 |
| Mode B Step 2 逐项检查 | done | 按 dev-spec 与 add-tracking 规范检查埋点闭环 | 发现 0 个 P0、4 个 P1、2 个 P2 |
| Mode B Step 3 输出审查诊断报告 | done | 输出合规结论、问题分级和建议 | 结论：埋点基础可用，但未完全符合最新 dev-spec |
| Mode B Step 4 输出迭代计划与交接 | user_confirm | 输出可实施修复范围和验证方式 | 等待用户确认是否执行修复 |
| Mode C Step 0 初始化/恢复流程状态 | done | 状态文件已读取并更新 | 2026-06-23 本轮埋点修复 |
| Mode C Step 1 收集目标、计划和基线 | done | 目标目录、审查交接、当前分支和脏工作区已确认 | 开发分支 `dev/fix-segment-tracking-20260623` |
| Mode C Step 2 影响分析 | done | 必改文件和验证计划已确认 | 只改埋点相关文件 |
| Mode C Step 3 实施改动 | done | 最小必要改动已完成 | 更新 tracker、日志协议、tracking plan、Gate/report/chart 埋点 |
| Mode C Step 4 验证回归 | done | 本地验证、脚本验证完成并记录 | tracking plan、py_compile、help、failure inference、diff check 通过 |
| Mode C Step 5 发布闭环 | user_confirm | 输出 commit/push/PR 或同步建议 | 等待是否提交/推送开发分支 |

## 决策记录

- Skill 名称：keeta-data-segment-analysis
- 场景名：segment / AE DBR lifecycle
- 诊断链路：识别固化场景 → 收集 region/date → 执行 `ae_dbr_query.py` 生成 CSV → 可选执行 `ae_dbr_chart.py` 生成图表 → 读取 CSV 形成表格和总结。
- 证据门禁：禁止编造数据；所有数据必须通过脚本实际查询并保存本地文件；非固化场景直接中断。
- 输出规范：两张 Markdown 表格 + 两段总结 + 图表路径。
- 埋点粒度：Layer 1 使用 `skill-metric-reporter` 协议；Layer 2 使用 `skill_tracker.py`；脚本节点按 SQL 查询和图表生成粒度上报，不记录完整 SQL 或原始数据。

## 产物

- SKILL.md：已同步 SkillHub V3 metadata，并新增上报协议
- requirements.txt：沿用仓库声明
- scripts/skill_tracker.py：已新增
- scripts/ae_dbr_query.py：已接入 `report_script`
- scripts/ae_dbr_chart.py：已接入 `report_script`
- references/：沿用固化场景说明
- 评测/埋点：埋点已接入；评测未在本次请求范围内初始化

## 阻塞项

- `skill-metric-reporter` 未在当前本地 Skill 目录中找到，按规范跳过，不阻塞流程。
- Friday Skill 设置页是否已绑定 Git 需要在平台侧确认；本地仓库 origin 已指向 metadata 中的 Git source。

## 本轮审查结论（2026-06-23）

- 结论：埋点基础链路已具备，但不完全符合最新 `keeta-data-skill-dev-spec` 埋点规范。
- P0：无。
- P1：`skill_tracker.py` 落后最新模板；`SKILL.md` 日志协议要求输出摘要而非最终回答全文；图表 Gate 失败不会上报失败；缺少 `.skill-dev/tracking-plan.json`。
- P2：查询脚本只按 SQL 节点上报，未覆盖整体 Gate/report 节点；最终输出协议与反馈引导存在冲突。
- 已验证：`python3 -m py_compile scripts/skill_tracker.py scripts/ae_dbr_query.py scripts/ae_dbr_chart.py scripts/bi_client.py` 通过；`skill_tracker.py --help`、`ae_dbr_query.py --help`、`ae_dbr_chart.py --help` 通过。

## 本轮迭代实施（2026-06-23）

- 开发分支：`dev/fix-segment-tracking-20260623`。
- 执行范围：修复本轮审查 P1/P2 埋点问题。
- 改动文件：`SKILL.md`、`scripts/skill_tracker.py`、`scripts/ae_dbr_query.py`、`scripts/ae_dbr_chart.py`、`.skill-dev/tracking-plan.json`、`.skill-dev/progress.md`。
- 不改范围：不改 SQL、指标口径、图表渲染逻辑、SkillHub 发布配置。
- 已实施：`skill_tracker.py` 同步最新模板行为；`SKILL.md` 改为最终回答全文上报；新增 Gate/report/chart 节点失败上报；补充 tracking plan。
- 验证结果：
  - `python3 /Users/tiantian/.keetai/profiles/codex/Default/.codex/skills/keeta-data-skill-dev-spec/scripts/validate_tracking_plan.py .skill-dev/tracking-plan.json` 通过。
  - `python3 -m py_compile scripts/skill_tracker.py scripts/ae_dbr_query.py scripts/ae_dbr_chart.py scripts/bi_client.py` 通过。
  - `python3 scripts/skill_tracker.py --help`、`python3 scripts/ae_dbr_query.py --help`、`python3 scripts/ae_dbr_chart.py --help` 通过。
  - `skill_tracker._infer_visible_failure_reason` 针对正常输出、权限失败、partial/数据缺口的最小检查通过。
  - `git diff --check` 通过。
- 残余风险：未执行真实 BI 查询、图表渲染和真实 mtcli 上报，避免触发线上查询/上报；建议合并前用小范围日期做一次端到端实跑。

## 下一次继续时

- 先做：完成验证，视需要提交并推送开发分支。
- 需要用户提供：是否需要我继续 commit/push 或发起合并。
