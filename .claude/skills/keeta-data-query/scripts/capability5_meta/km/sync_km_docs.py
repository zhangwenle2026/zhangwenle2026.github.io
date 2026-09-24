#!/usr/bin/env python3
"""
同步 KM 数仓指南文档到本地知识库（使用 meituan-km / km-operator skill）

用法:
    python3 sync_km_docs.py [ROOT_DOC_ID] [--max-depth N] [--force]

默认拉取 Keeta数据白皮书(1554815109) 及其所有下级文档。

特性:
- 自动检查知识库是否当天已同步，是则跳过同步
- 使用 --force 强制重新同步
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

# 设置允许访问 C4 文档（需用户有权限）
os.environ.setdefault("MEITUAN_KM_MAX_SECRET_LEVEL_THRESHOLD", "4")

SKILL_DIR = Path(__file__).parent.parent.parent
KNOWLEDGE_DIR = SKILL_DIR / "knowledge"
INDEX_FILE = KNOWLEDGE_DIR / "index.json"
# 使用 citadel CLI（oa-skills）替代 meituan-km skill
CITADEL_CMD = ["oa-skills", "citadel"]

DEFAULT_ROOT = "1554815109"  # Keeta数据白皮书
DEFAULT_MAX_DEPTH = 2  # 降低默认深度避免超时


def is_knowledge_base_synced_today() -> bool:
    """检查知识库是否当天已同步"""
    if not INDEX_FILE.exists():
        return False
    try:
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            index = json.load(f)
        if not index:
            return False
        # 检查任意一个文档的同步时间是否为今天
        today = date.today().strftime("%Y-%m-%d")
        for doc_id, info in index.items():
            synced_at = info.get("synced_at", "")
            if synced_at.startswith(today):
                return True
        return False
    except Exception:
        return False


def run_km(args: list, timeout: int = 120) -> tuple:
    """调用 citadel CLI 获取文档信息。
    注意：citadel 把实际数据输出到 stderr，日志输出到 stdout。
    返回 (combined_output, error_msg)
    """
    try:
        r = subprocess.run(CITADEL_CMD + args,
                           capture_output=True, text=True, timeout=timeout)
        # citadel 将数据写入 stderr，将认证日志写入 stdout
        # 合并两者，get_children / get_doc_content 会自行过滤日志行
        combined = r.stderr.strip() + "\n" + r.stdout.strip()
        return combined.strip(), ""
    except subprocess.TimeoutExpired:
        return "", f"timeout after {timeout}s"
    except Exception as e:
        return "", str(e)


def get_children(doc_id: str) -> list:
    """获取子文档列表，失败时返回空列表
    citadel getChildContent 返回 JS 对象格式（非标准 JSON），用正则解析
    """
    out, err = run_km(["getChildContent", "--contentId", doc_id], timeout=30)
    if not out:
        return []
    try:
        # 过滤 citadel 的 ANSI/认证输出行，只保留 { ... } 块
        lines = out.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            # 跳过 citadel 的日志行
            if any(x in line for x in ["✓", "✅", "❌", "🔐", "[citadel]", "npm", "sso", "auth",
                                        "步骤", "轮询", "缓存", "认证", "初始", "策略", "提示", "目标"]):
                continue
            if "{" in line:
                in_block = True
            if in_block:
                json_lines.append(line)
        raw = "\n".join(json_lines)
        # 用正则提取所有 contentId 和 title 对
        import re as _re
        cids = _re.findall(r"contentId:\s*['\"](\d+)['\"]", raw)
        titles = _re.findall(r"title:\s*['\"](.*?)['\"]", raw)
        result = []
        for i, cid in enumerate(cids):
            title = titles[i] if i < len(titles) else f"doc_{cid}"
            result.append({"contentId": cid, "title": title})
        return result
    except Exception as e:
        return []


def collect_all_docs(root_id: str, max_depth: int = 2, depth: int = 0, visited: set = None) -> list:
    """递归收集所有文档ID和标题，带去重和进度显示"""
    if visited is None:
        visited = set()
    if depth > max_depth or root_id in visited:
        return []
    
    visited.add(root_id)
    
    children = get_children(root_id)
    docs = []
    for c in children:
        cid = str(c["contentId"])
        title = c["title"]
        docs.append((cid, title, depth + 1))
        # 递归获取子文档
        sub = collect_all_docs(cid, max_depth, depth + 1, visited)
        docs.extend(sub)
    return docs


def get_doc_content(doc_id: str) -> tuple:
    """返回 (content, error_msg)，使用 citadel getMarkdown，过滤日志行"""
    out, err = run_km(["getMarkdown", "--contentId", doc_id], timeout=60)
    if not out:
        return "", err
    # 过滤 citadel 的 ANSI/认证日志，保留 Markdown 内容
    skip_prefixes = ("✓", "✅", "❌", "🔐", "[citadel]", "npm", "sso-",
                     "[sso", "[auth", "📌", "⚠️", "步骤", "轮询", "认证成功",
                     "目标 Client", "认证策略", "提示：", "初始化")
    lines = out.split("\n")
    md_lines = [l for l in lines if not any(l.strip().startswith(p) for p in skip_prefixes)]
    # 找到第一行真正的 Markdown（# 开头或非空内容）
    start = 0
    for i, l in enumerate(md_lines):
        if l.strip() and not l.strip().startswith("["):
            start = i
            break
    return "\n".join(md_lines[start:]).strip(), err


def sanitize_title(title: str, doc_id: str = "") -> str:
    """清理标题，只保留 ASCII 字母数字、CJK 中文、日文假名、韩文、空格，其余一律替换为下划线。
    明确排除西里尔字符（U+0400-U+04FF）、拉丁扩展等乱码区段。
    """
    safe = re.sub(
        r'[^a-zA-Z0-9'
        r'\u4e00-\u9fff'   # CJK 统一汉字
        r'\u3400-\u4dbf'   # CJK 扩展 A
        r'\uf900-\ufaff'   # CJK 兼容汉字
        r'\u3040-\u30ff'   # 日文平/片假名
        r'\uac00-\ud7af'   # 韩文音节
        r' ]',
        '_', title
    )
    safe = safe[:50].strip('_')
    safe = re.sub(r'_+', '_', safe)  # 合并连续下划线
    return safe or (f"doc_{doc_id}" if doc_id else "doc_unknown")


def save_doc(doc_id: str, title: str, content: str, index: dict) -> Path:
    safe = sanitize_title(title, doc_id)
    fn = f"{safe}_{doc_id}.md"
    fp = KNOWLEDGE_DIR / fn
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(f"# {title}\n\n> 来源: https://km.sankuai.com/page/{doc_id}\n\n")
        f.write(content)
    index[doc_id] = {
        "title": title,
        "path": fn,
        "synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "size": len(content)
    }
    return fp


def main():
    root_id = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else DEFAULT_ROOT
    max_depth = DEFAULT_MAX_DEPTH
    force_sync = False
    for i, a in enumerate(sys.argv):
        if a == '--max-depth' and i + 1 < len(sys.argv):
            max_depth = int(sys.argv[i + 1])
        if a == '--force':
            force_sync = True

    print("=" * 60)
    print(f"Keeta 数仓指南知识库同步")
    print(f"根文档: {root_id}, 最大深度: {max_depth}")
    print("=" * 60)

    # 检查是否当天已同步
    if not force_sync and is_knowledge_base_synced_today():
        print(f"\n✅ 知识库已在今天同步，跳过同步步骤")
        print(f"知识库目录: {KNOWLEDGE_DIR}")
        print("如需强制重新同步，请使用 --force 参数")
        print("=" * 60)
        return

    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    index = {}
    if INDEX_FILE.exists():
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            index = json.load(f)

    # 1. 收集文档树
    print("\n[1/3] 收集文档树...")
    all_docs = [(root_id, "根文档", -1)]
    # 获取根文档标题
    root_content, _ = get_doc_content(root_id)
    if root_content:
        first_line = root_content.split('\n')[0].strip('# ').strip()
        if first_line:
            all_docs[0] = (root_id, first_line, -1)

    tree = collect_all_docs(root_id, max_depth)
    all_docs.extend(tree)
    print(f"  ✓ 共 {len(all_docs)} 个文档")
    for d in all_docs:
        indent = "  " * (d[2] + 1)
        print(f"    {indent}• {d[1]} ({d[0]})")

    # 2. 逐个拉取内容
    print(f"\n[2/3] 拉取文档内容...")
    ok = 0
    fail = 0
    no_permission_docs = []  # 记录无权限文档（含C4权限不足）

    for i, (did, title, _depth) in enumerate(all_docs, 1):
        print(f"  [{i}/{len(all_docs)}] {title}...", end=" ", flush=True)
        content, err = get_doc_content(did)

        # 检测权限不足（C4或其他权限问题）
        if any(kw in err for kw in ["密级为C4", "超过阈值", "无权限", "权限不足", "403", "forbidden"]):
            print("⏭️ 权限不足，跳过")
            no_permission_docs.append({
                "doc_id": did,
                "title": title,
                "url": f"https://km.sankuai.com/page/{did}",
                "reason": err[:100]
            })
            continue

        if content and len(content) > 10:
            fp = save_doc(did, title, content, index)
            print(f"✓ {len(content)}字符")
            ok += 1
        else:
            print("✗ 空")
            fail += 1
        time.sleep(0.5)

    # 3. 保存索引（含无权限文档清单）
    print(f"\n[3/3] 保存索引...")
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    # 保存无权限文档清单，供 skill 调用时向用户反馈
    no_perm_file = KNOWLEDGE_DIR / "_no_permission_docs.json"
    with open(no_perm_file, 'w', encoding='utf-8') as f:
        json.dump(no_permission_docs, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"完成: {ok} 成功 / {fail} 失败 / {len(no_permission_docs)} 权限不足跳过 / 共 {len(all_docs)}")
    print(f"知识库: {KNOWLEDGE_DIR}")

    if no_permission_docs:
        print(f"\n⚠️  以下 {len(no_permission_docs)} 篇文档因权限不足未能同步：")
        for doc in no_permission_docs:
            print(f"   • [{doc['doc_id']}] {doc['title']}")
            print(f"     {doc['url']}")
        print(f"\n📋 缺失文档清单已保存至: {no_perm_file}")
        print("   可通过 km.sankuai.com 申请对应文档的阅读权限")

    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
