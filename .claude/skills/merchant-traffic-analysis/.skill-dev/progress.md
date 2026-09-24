# 分析 Skill 流程进度

## 元信息

- 模式：Mode C 迭代实施已有 Skill（埋点合规修复）
- 状态文件：/Users/tiantian/workspace/keeta-data-analyze-skill/merchant-traffic-analysis/.skill-dev/progress.md
- 目标 Skill：merchant-traffic-analysis
- 目标目录：/Users/tiantian/workspace/keeta-data-analyze-skill/merchant-traffic-analysis
- 当前步骤：Step 5 发布闭环
- 下一步：开发分支已推送后等待合并/发布确认
- 最近更新：2026-06-23 21:20:00 CST

## 已确认信息

- 仓库已存在本地：/Users/tiantian/workspace/keeta-data-analyze-skill/merchant-traffic-analysis
- 当前分支：master
- 远端：ssh://git@git.sankuai.com/keeta_data_skill/merchant-traffic-analysis.git
- 最新代码：2026-06-23 已执行 `git pull --ff-only`，结果为 `Already up to date.`
- 规范注意：Skill 名称不是 `keeta-data-*` 前缀，但按用户指定使用 `keeta-data-skill-dev-spec` 做埋点合规审查。

## 步骤状态

| Step | 状态 | 完成条件 | 备注 |
|------|------|----------|------|
| Step 0 初始化/恢复流程状态 | done | 已读取并更新状态文件 | 旧记录为 Mode D 实施流程，本次切换为 Mode B 审查 |
| Step 1 收集材料 | done | 已读取 SKILL.md、scripts、assets 和 .skill-dev | 无 references/data-query-protocol/eval 材料 |
| Step 2 逐项检查 | done | 已按埋点规范、review-scoring、checklist 对照 | 发现 P1/P2 问题，无 P0 |
| Step 3 输出审查诊断报告 | done | 已形成埋点合规结论 | 结论：基本接入，但未完全符合最新规范 |
| Step 4 输出迭代计划与交接 | done | 已形成建议修复范围 | 用户已确认全部修复 |
| Mode C Step 1 收集目标、计划和基线 | done | 已确认按审查报告修复并推开发分支 | 开发分支 `dev/fix-merchant-tracking-compliance-20260623` |
| Mode C Step 2 影响分析 | done | 已映射必改文件和验证计划 | 只改埋点协议、tracker、代理上报、tracking plan、preflight、治理材料 |
| Mode C Step 3 实施改动 | done | 已完成埋点合规修复 | 详见本文件“本轮迭代实施” |
| Mode C Step 4 验证回归 | done | 本地验证通过 | unittest、preflight、tracking plan、diff check 通过 |
| Mode C Step 5 发布闭环 | done | 提交并推送开发分支 | 分支：`dev/fix-merchant-tracking-compliance-20260623` |

## 埋点审查结论

- 通过项：SKILLHUB_METRIC_REPORTER 块存在；`scripts/skill_tracker.py` 存在；task start/end、feedback、skill-script、skill-llm API 具备；Python BI 客户端和 Node 代理已接入 `skill-script`；埋点失败不阻塞业务；本地语法验证通过。
- P1：`SKILL.md` 和 tracker CLI 仍要求最终输出摘要，不符合最新模板“尽量原文上报，由 tracker 统一截断”的要求。
- P1：脚本节点在业务接入层主动降采样 SQL、输出和错误信息，使用 `sql_len`、`rows`、`query_id` 摘要，不符合 add-tracking 规则中“输入输出尽量使用原文全文”的要求。
- P1：缺少 `.skill-dev/tracking-plan.json`，无法用 `validate_tracking_plan.py` 复核自动插入计划，也缺少 idempotency_key 注释证据。
- P2：没有 `scripts/preflight.sh`，无法按规范一键回归。
- P2：未提供 references/data-query-protocol.md 和 eval 材料；本次仅审查埋点实现，不给完整分析 Skill 发布绿灯。

## 验证记录

- `python3 -m py_compile scripts/skill_tracker.py assets/scripts/keeta_bi_skill.py`：通过
- `python3 scripts/skill_tracker.py --help`：通过
- `node --check assets/bi-proxy-server.js`：通过
- `bash -n assets/start-dashboard.sh`：通过
- `validate_tracking_plan.py`：未运行，原因是目标仓库没有 `.skill-dev/tracking-plan.json`

## 迭代建议

| 优先级 | 问题 | 建议改动 | 建议文件 |
|--------|------|----------|----------|
| P1 | 输出上报仍要求摘要 | 改为最终回答原文或关键错误全文，失败和 partial/fail 规则对齐模板 | SKILL.md, scripts/skill_tracker.py |
| P1 | 业务接入层提前摘要化 | 将 SQL/请求/响应原文交给 tracker，统一由 tracker 按环境变量截断和脱敏 | assets/bi-proxy-server.js, assets/scripts/keeta_bi_skill.py, scripts/skill_tracker.py |
| P1 | 缺少可验证埋点计划 | 补 `.skill-dev/tracking-plan.json` 并跑 `validate_tracking_plan.py` | .skill-dev/tracking-plan.json |
| P2 | 缺少一键回归 | 增加 `scripts/preflight.sh`，纳入 py_compile、tracker help、node check、bash -n | scripts/preflight.sh |
| P2 | 缺少完整治理材料 | 后续补 data-query-protocol / eval 后再做完整发布审查 | references/, eval |

## 本轮迭代实施

- 开发分支：`dev/fix-merchant-tracking-compliance-20260623`
- 修复范围：
  - `SKILL.md`：日志协议改为最终回答全文上报，补 partial/fail 可见失败规则和环境变量截断说明。
  - `scripts/skill_tracker.py`：改为 tracker 统一做截断、脱敏和可见失败推断；新增 `--params-file`、`--output-file`、`--error-file`，避免业务层提前截断。
  - `assets/bi-proxy-server.js`：脚本节点上报改为原始 SQL、请求体、stdout/解析结果；通过临时文件传给 tracker。
  - `assets/scripts/keeta_bi_skill.py`：保留原始 payload 和 output 给 `report_script`，不再把 SQL 替换成长度摘要。
  - `.skill-dev/tracking-plan.json`：补可校验埋点计划。
  - `scripts/preflight.sh`：补一键回归。
  - `tests/test_tracking_compliance.py`：补埋点合规回归测试，并验证 red-green。
  - `references/data-query-protocol.md`、`references/tracking-eval-cases.md`：补取数协议和埋点评测建议。
- TDD 记录：
  - 红灯：`python3 -m unittest tests/test_tracking_compliance.py` 初次失败 5 项，覆盖旧摘要逻辑、硬编码截断、缺 tracking plan、缺 preflight。
  - 绿灯：修复后 `python3 -m unittest tests/test_tracking_compliance.py` 通过。
- 验证结果：
  - `python3 -m unittest tests/test_tracking_compliance.py`：通过，5 tests OK。
  - `bash scripts/preflight.sh`：通过，输出 `READY`。
  - `python3 /Users/tiantian/.keetai/profiles/codex/Default/.codex/skills/keeta-data-skill-dev-spec/scripts/validate_tracking_plan.py .skill-dev/tracking-plan.json`：通过，`items=5`。
  - `git diff --check`：通过。
- 未执行项：未做真实 BI 查询和真实 mtcli 上报，避免触发线上查询/上报；合并前建议用小日期范围做一次端到端实跑。

## 阻塞项

- 无执行阻塞。
- `skill-metric-reporter` 本地不可用，已按 Skill 说明跳过，不阻塞审查。

## 下一次继续时

- 先做：如需合并 master 或发布 SkillHub，确认合并/发布流程。
- 需要用户提供：是否继续合并、发布或做真实 BI 小范围端到端实跑。
