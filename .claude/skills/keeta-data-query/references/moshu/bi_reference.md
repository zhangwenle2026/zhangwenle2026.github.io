# 魔数个人数据集与 SQL 模板链路

## 当前状态

对外 `kdata` 命令保持历史兼容，继续使用顶层 `dataset` 和 `template`。
内部业务调用已切换到 `mtcli kdata moshu ...`，不再由 Skill 直连 BI HTTP 接口。

当前可用命令：

```bash
kdata dataset list [--query <keyword>]
kdata dataset info <subjectId> [subjectId...]
kdata template list [--query <keyword>] [--shared] [--managed]
kdata template show <templateId> [templateId...] [--ver-no 1]
```

这些命令底层只调用 `mtcli kdata moshu dataset-list/dataset-info/template-list/template-info`，不再直接请求 `bi.keetapp.com` 业务 HTTP 接口，也不读取浏览器 Cookie / CDP 登录态。

## Agent 处理规则

- 查魔数个人数据集时，使用 `kdata dataset list` / `kdata dataset info`。
- 查魔数 SQL 模板时，使用 `kdata template list` / `kdata template show`。
- 不再复用历史 `requests`、`browser_cookie3`、CDP Cookie 读取方式访问魔数个人数据集或 SQL 模板接口。
- 用户需要 BI 看板取数时，按 URL 类型使用 [dashboard-v2.md](dashboard-v2.md)、[dashboard-v1.md](dashboard-v1.md) 或 [xbr.md](xbr.md)；只查结构和筛选器时使用 [dashboard-meta.md](dashboard-meta.md)。
- 用户需要 Hive SQL 或表结构信息时，优先使用 `kdata hive ...`、`kdata table ...`、`kdata meta ...`，业务接口调用交给 `mtcli`。
