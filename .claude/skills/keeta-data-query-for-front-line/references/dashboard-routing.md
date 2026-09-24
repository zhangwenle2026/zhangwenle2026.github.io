# 🔀 魔数看板取数（路由模式）

当用户需要从魔数看板（XBR / Dashboard 仪表板）取数时，本 skill 作为统一入口，自动检测/安装看板 skill 并转交执行。

## 触发条件

以下任一情况触发看板路由：
- 用户提供了 `bi.keetapp.com` 或 `mdbi.bi.st.keetapp.com` 的看板 URL
- 用户提到：魔数看板、XBR取数、dashboard取数、仪表板取数、看板数据

## 执行流程

**Step 1：调用 kdata-fl dashboard 检测/安装看板 skill**

```bash
# 带 URL
kdata-fl dashboard "https://bi.keetapp.com/v2/xbr/12345"

# 不带 URL（仅检测安装）
kdata-fl dashboard --check-only
```

输出 JSON 示例：
```json
{
  "status": "ready",
  "skill_name": "bi-query-dashboard-overseas",
  "skill_path": "<installed-skill-dir>/bi-query-dashboard-overseas/SKILL.md",
  "freshly_installed": false,
  "url": "https://bi.keetapp.com/v2/xbr/12345",
  "dashboard_type": "xbr",
  "instruction": "看板 skill 已就绪。请立即读取 SKILL.md 并按其流程完成取数。"
}
```

**Step 2：读取看板 skill 的 SKILL.md 并执行**

根据 `instruction` 字段，读取 `skill_path` 指向的 SKILL.md，按其流程完成取数。

## 支持的 URL 格式

| URL 格式 | 类型 |
|---|---|
| `{domain}/v2/xbr/{id}` | XBR 看板 |
| `{domain}/v2/dashboard/{id}` | Dashboard v2 仪表板 |
| `{domain}/dashboard/{id}` | Dashboard v1 仪表板 |

> 仅支持境外域名：bi.keetapp.com、mdbi.bi.st.keetapp.com
