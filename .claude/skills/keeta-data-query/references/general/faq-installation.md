# FAQ - 安装与初始化

[← 返回目录](faq.md)

---

### Q1：这个 Skill 怎么安装？
在 Friday SkillHub 的当前 Skill 详情页点击安装或加入个人助理。不要沿用旧 FAQ 里的固定历史链接；以当前分享的 SkillHub 页面或 SkillHub 搜索结果为准。

---

### Q2：第一次使用前需要做什么？
在 Skill 根目录执行一次：

```bash
bash scripts/preflight.sh
export PATH="$(python3 scripts/core/paths_cli.py bin-dir):$PATH"
```

`preflight.sh` 会检查依赖、修复 `kdata` 软链、确认 mtcli/MIS 状态，并提示是否存在冲突 Skill。

---

### Q3：`kdata: command not found` 怎么办？
优先重新执行初始化命令。如果仍不可用，直接使用脚本入口兜底：

```bash
python3 scripts/kdata.py --help
python3 scripts/kdata.py standard datasets
```

所有 `kdata <subcommand>` 都可以替换为 `python3 scripts/kdata.py <subcommand>`。

---

### Q4：数据权限按什么口径判断？
权限以当前用户个人账号为准：

| 能力 | 权限来源 |
|---|---|
| 标准数据集 | 起源标准数据集、指标、维度和 Region 权限 |
| Hive 查询 | 表权限、字段权限、项目空间、队列权限 |
| 元数据找表 | DataMap/RAG/XT/Origin 对当前用户开放的查询权限 |
| BI 看板 | 当前用户在 `bi.keetapp.com` 上对该看板的查看权限 |

Skill 不会绕过权限系统；能查到的数据应与用户自己登录对应平台可见的数据一致。
