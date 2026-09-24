# FAQ - 版本与更新

[← 返回目录](faq.md)

---

### Q15：怎么确认用的是最新版本？
以 Friday SkillHub 当前详情页显示的版本为准。当前本地 Skill 也会在 `preflight.sh` 中执行自动更新检查。

可用下面命令确认本地入口是否可用：

```bash
bash scripts/preflight.sh
kdata --help
```

---

### Q16：更新后需要重启吗？
通常不需要重启平台，但建议开新会话，避免旧上下文继续引用过时 FAQ 或旧命令。

如果当前 shell 找不到 `kdata`，重新执行：

```bash
export PATH="$(python3 scripts/core/paths_cli.py bin-dir):$PATH"
```

---

### Q17：自动更新失败怎么办？
先看 `preflight.sh` 输出：

| 输出 | 处理 |
|---|---|
| `DEPS_REQUIRED` | 检查 Node.js/npm/npx，按终端错误处理后重新执行 |
| `MIS_REQUIRED` | 按输出的 `MIS_ACTION` 提供用户 MIS 后重试 |
| `CONFLICT:` | 询问用户是否卸载冲突 Skill |
| `READY` | 初始化已完成，可以查询 |

如果自动更新失败但命令可用，可以继续使用当前版本，并把错误输出反馈给维护者。
