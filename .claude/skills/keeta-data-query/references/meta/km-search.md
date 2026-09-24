# 模式③ 知识库检索 — 完整实现

## 调用方式

```bash
cd ~/.openclaw/workspace/skills/keeta-table-finder

# 语义检索（自动扩展同义词）
python3 scripts/km/query_knowledge.py "订单量的定义"

# 指定返回文档数
python3 scripts/km/query_knowledge.py "补贴口径" --top 10
```

## 知识库同步

知识库内容来自学城（km.sankuai.com），需定期同步：

```bash
# 同步（当天已同步自动跳过）
cd ~/.openclaw/workspace/skills/keeta-table-finder
python3 scripts/km/sync_km_docs.py

# 强制重新同步
python3 scripts/km/sync_km_docs.py --force
```

**同步依赖**：meituan-km skill（`/root/.openclaw/skills/meituan-km/scripts/km_skill.py`）

同步完成后检查无权限文档：
```bash
cat knowledge/_no_permission_docs.json
```
若有缺失权限文档，向用户反馈清单并询问是否申请权限。

## 语义扩展词典（自动生效）

| 查询词 | 自动扩展 |
|--------|---------|
| 订单 | order、ord、成单、支付、交易、gmv |
| 补贴 | promotion、subsidy、优惠、券、coupon、折扣 |
| 用户 | user、cust、customer、新客、老客 |
| 骑手 | courier、rider、配送、delivery |
| 商家 | shop、merchant、门店、store |
| 履约 | delivery、配送、任务单、完单 |

## 输出格式

```
查询: 订单量的定义 [语义扩展模式]
找到 3 个相关文档:

[1] 交易数据白皮书 (匹配度: 312)
    文件: 交易数据白皮书_2717554521.md
---
订单量：用户成功支付的订单数，以订单创建时间为准...
来源：km.sankuai.com/page/2717554521
```

## 知识库状态查看

```bash
ls knowledge/*.md | wc -l                 # 已同步文档数
cat knowledge/_no_permission_docs.json    # 无权限文档
```

## 错误处理

| 错误 | 处理 |
|------|------|
| `知识库为空` | 运行 `sync_km_docs.py` 同步 |
| `meituan-km skill 未找到` | 安装 meituan-km skill 后重新同步 |
| 检索无结果 | 换同义词重试，或告知用户当前知识库未收录 |

## ⚠️ 知识库文件名乱码修复（已修复，备查）

早期 `sync_km_docs.py` 用 `re.sub(r'[^\w\u4e00-\u9fff]','_',title)` 生成文件名，
`\w` 会匹配 Unicode 字母（含西里尔字母），导致乱码。已修复为只允许 ASCII + CJK 字符。

若发现 knowledge/ 下有乱码文件名：
```bash
python3 -c "
import os
from pathlib import Path
d = Path('knowledge')
for f in d.iterdir():
    if any(('\u2500'<=c<='\u25ff') or ('\u0400'<=c<='\u04ff') for c in f.name):
        f.unlink()
        print(f'deleted: {f.name}')
"
echo '{}' > knowledge/index.json
python3 scripts/km/sync_km_docs.py --force
```
