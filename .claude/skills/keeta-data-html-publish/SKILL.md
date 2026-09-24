---
name: keeta-data-html-publish
description: 将本地 HTML 文件发布到内部托管平台（基于 Supabase，数据存储在 *.database.sankuai.com）。当用户需要将生成的 HTML 页面/报告/看板发布上线、分享 HTML 链接、部署静态页面、管理页面访问权限时使用。触发词：发布 HTML、上传 HTML、部署页面、分享页面链接、把这个 HTML 传上去、页面权限、访问权限。

metadata:
  skillhub.creator: "wanghao192"
  skillhub.updater: "wanghao192"
  skillhub.version: "V5"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "16355"
  skillhub.high_sensitive: "false"
---

# keeta-data-html-publish

将本地 HTML 文件一键发布到内部 HTML 托管平台（基于 Supabase，数据存储在 `*.database.sankuai.com`），返回可访问的预览链接。支持新建发布、更新已有页面和权限管理。

## 快速使用

```bash
# 新建发布
python3 <skill-dir>/scripts/publish.py publish <html文件路径> --mis <your_mis> --creator-name "<你的名字>"

# 更新已有页面（保持原链接不变）
python3 <skill-dir>/scripts/publish.py publish <html文件路径> --mis <your_mis> --creator-name "<你的名字>" --update <uuid>

# 兼容旧用法（省略 publish 子命令）
python3 <skill-dir>/scripts/publish.py <html文件路径> --mis <your_mis> --creator-name "<你的名字>"
```

> `<skill-dir>` 为 skill 安装目录，Claude Code 中通常为 `~/.claude/skills/keeta-data-html-publish`。

### 发布参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `--name` | 发布文件名（不含 .html） | 原文件名 |
| `--mis` | 创建者 MIS 账号（必填） | — |
| `--creator-name` | 创建者名称（必填） | — |
| `--public` | 设为公开文件 | 否（默认私有） |
| `--update UUID` | 更新已有页面，传入目标 UUID | 无（默认新建） |

示例：

```bash
# 发布并自定义名称
python3 <skill-dir>/scripts/publish.py publish /path/to/report.html --name "hk-v2r-report-w12" --mis mis1 --creator-name "张三"

# 更新已发布的日报
python3 <skill-dir>/scripts/publish.py publish /path/to/report_v2.html --mis mis1 --creator-name "张三" --update "a1b2c3d4-e5f6-..."
```

## 权限管理

通过 `access` 子命令管理文件的访问权限和管理权限。

### 权限模型

| 角色 | 说明 | 权限 |
|------|------|------|
| **owner** | 文件创建者 | 全部操作（发布/更新/授权/转让） |
| **manager** | 管理员 | 添加/移除 viewer 和 manager |
| **viewer** | 访问者 | 查看文件内容 |

- 添加 manager 时自动加入 viewer
- owner 不可被 remove，只能通过 transfer 转让
- transfer 后旧 owner 降为 manager

### 权限命令

```bash
# 查看权限列表
python3 <skill-dir>/scripts/publish.py access list --uuid <UUID> --operator mis1

# 添加 viewer
python3 <skill-dir>/scripts/publish.py access add --uuid <UUID> --mis mis2,mis3 --role viewer --operator mis1

# 添加 manager
python3 <skill-dir>/scripts/publish.py access add --uuid <UUID> --mis mis2 --role manager --operator mis1

# 移除权限
python3 <skill-dir>/scripts/publish.py access remove --uuid <UUID> --mis mis3 --operator mis1

# 转让所有权
python3 <skill-dir>/scripts/publish.py access transfer --uuid <UUID> --to mis2 --operator mis1
```

### 权限参数

| 参数 | 说明 |
|---|---|
| `--uuid` | 文件 UUID（发布时返回） |
| `--mis` | 目标 MIS（多个用逗号分隔） |
| `--role` | 角色：`viewer`（默认）或 `manager` |
| `--operator` | 操作者 MIS（需为 owner 或 manager） |
| `--to` | transfer 时新 owner 的 MIS |

## 工作流

1. 读取本地 HTML 文件
2. 通过 multipart/form-data POST 到 Supabase Edge Function
3. Edge Function 内部完成：生成 UUID → 上传到 Storage → 写入元数据（原子操作）
4. 返回预览链接（由服务端生成）

更新模式下，Edge Function 会查找已有记录，覆盖 Storage 文件并更新元数据，链接保持不变。

## 访问权限说明

**默认私有**：发布的文件默认为私有（`is_private=true`），仅通过链接可访问，不会出现在公开列表中。
如需设为公开文件，传入 `--public` 参数。

发布后可通过 `access add` 命令为特定用户授予访问权限。

## 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `PUBLISH_FUNCTION_URL` | Edge Function 端点 URL | `https://dblgj1nam8vwyfgtgs.database.sankuai.com/functions/v1/publish-html` |

如果 Edge Function 部署到不同地址，通过此环境变量覆盖。

## 注意事项

- **必须先询问用户的 MIS 账号和姓名**，再调用脚本。`--mis` 和 `--creator-name` 为必填参数，不得假设或编造
- API Key 不在客户端脚本中，由 Edge Function 服务端持有
- 上传成功后链接即可访问，无需额外部署步骤
- 发布后告知用户完整访问链接
- 更新时使用之前发布返回的 UUID
- 权限管理操作需提供操作者 MIS（`--operator`），服务端校验操作者是否为 owner 或 manager
