# 埋点评测用例建议

## 目录

- 覆盖目标
- 用例清单
- 验收口径

## 覆盖目标

这些用例用于后续接入 `keeta-data-eval-manager` 或人工回归，重点验证埋点链路，不替代真实 BI 查询评测。

## 用例清单

| 类型 | 用户问题 / 操作 | 期望 |
|---|---|---|
| routing | 启动商家流量效果分析看板 | 触发本 Skill，先执行 `skill_tracker.py start` |
| script | 通过看板执行 `/keeta-bi-query` SQL | 上报 `skill-script`，input 包含原始 SQL，output 包含原始 stdout 或解析结果 |
| failure | Cookie 未登录时查询 | 用户可见错误，上报 `skill-script` FAIL，最终 `skill-output` 应为 FAIL |
| feedback | 用户回复 👍 | 执行 `skill_tracker.py feedback --rating 1` |
| feedback | 用户回复 👎 并给出意见 | 执行 `skill_tracker.py feedback --rating -1 --comment <原文>` |
| evidence gate | 查询失败或部分失败后输出报告 | 不写确定性归因，最终输出包含数据缺口，并按 FAIL 上报 |

## 验收口径

- 每个用户问题有完整 `user-input -> skill-script* -> skill-output` 链路。
- 成功查询的脚本节点状态为 `SUCCESS`，失败、权限不足、解析失败为 `FAIL`。
- 输入输出由 `skill_tracker.py` 统一截断和脱敏；业务接入层不提前改写成摘要。
- 埋点失败只输出 stderr，不阻塞看板、查询或用户回答。
