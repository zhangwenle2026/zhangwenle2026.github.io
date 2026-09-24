# 知识库同步 — citadel CLI 集成说明

> ⚠️ **已迁移**：不再依赖 meituan-km skill。改用系统自带 `oa-skills citadel` CLI 直接调用学城接口。

## 依赖

- `@it/oa-skills`（全局安装，内网源）：提供 `oa-skills citadel` 命令
- **首次使用需安装**：`npm install -g @it/oa-skills@latest --registry=http://r.npm.sankuai.com`
- **认证**：首次调用触发大象 CIBA 授权，点击大象 App 通知即可；之后 token 缓存约 8 分钟

## 核心命令

```bash
# 获取子文档列表（数据输出到 stderr！）
oa-skills citadel getChildContent --contentId <DOC_ID>

# 读取文档 Markdown 内容（数据输出到 stderr！）
oa-skills citadel getMarkdown --contentId <DOC_ID>
```

> ⚠️ **重要**：citadel CLI 将实际数据输出到 **stderr**，认证日志输出到 **stdout**。
> sync_km_docs.py 的 run_km() 函数已处理此问题：合并 stderr+stdout，过滤日志行。

## getChildContent 返回格式（JS 对象，非标准 JSON）

返回单引号 JS 对象，不是标准 JSON，用正则解析：

```python
cids = re.findall(r"contentId:\s*['\"](\d+)['\"]", raw)
titles = re.findall(r"title:\s*['\"](.*?)['\"]", raw)
```

## sync_km_docs.py 关键配置

```python
CITADEL_CMD = ["oa-skills", "citadel"]   # 不要用 npx oa-skills@latest（走公网 npm，会 404）
DEFAULT_ROOT = "1554815109"              # Keeta数据白皮书根文档
DEFAULT_MAX_DEPTH = 2
```

## 运行方式

```bash
cd ~/.openclaw/skills/keeta-data-finder

# 正常同步（当天已同步自动跳过）
python3 scripts/km/sync_km_docs.py

# 强制重新同步
python3 scripts/km/sync_km_docs.py --force
```

## 初始化检查流程

```bash
# Step 1：检查 oa-skills 是否安装
oa-skills citadel --help 2>/dev/null && echo "OK" || \
  npm install -g @it/oa-skills@latest --registry=http://r.npm.sankuai.com

# Step 2：同步知识库（当天已同步自动跳过）
cd ~/.openclaw/skills/keeta-data-finder && python3 scripts/km/sync_km_docs.py
```

## 降级策略

| 检查项 | 失败时处理 |
|--------|----------|
| oa-skills 未安装 | 自动安装（内网 npm 源） |
| 首次认证 | 等待用户在大象 App 点击授权通知 |
| mtcli 找表不可用 | 降级为知识库与常用表参考 |
| 知识库文件缺失 | 自动触发 sync_km_docs.py |
