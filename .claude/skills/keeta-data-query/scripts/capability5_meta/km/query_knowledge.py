#!/usr/bin/env python3
"""
在本地知识库中搜索相关内容（语义扩展检索）

用法:
    python3 query_knowledge.py "订单量的定义"
    python3 query_knowledge.py "订单量的定义" --top 10
"""

import json
import sys
import re
import os
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent.parent
KNOWLEDGE_DIR = SKILL_DIR / "knowledge"
INDEX_FILE = KNOWLEDGE_DIR / "index.json"

# 语义扩展词典（关键业务词 → 相关词）
SEMANTIC_EXPAND = {
    "订单": ["order", "ord", "成单", "提单", "完单", "支付", "交易", "gmv"],
    "补贴": ["promotion", "subsidy", "优惠", "券", "coupon", "折扣", "discount"],
    "用户": ["user", "cust", "customer", "新客", "老客", "首单"],
    "骑手": ["courier", "rider", "配送", "delivery"],
    "商家": ["shop", "merchant", "门店", "store"],
    "履约": ["delivery", "配送", "任务单", "接单", "完单"],
    "时段": ["period", "peak", "高峰", "早餐", "午高峰", "晚高峰"],
    "指标": ["metric", "口径", "定义", "统计", "计算"],
    "宽表": ["wide", "topic", "宽", "明细"],
    "region": ["区域", "地区", "HK", "SA", "AE", "BR", "QA", "KW"],
}


def expand_query(query: str) -> set:
    """对查询词进行语义扩展"""
    terms = set(query.lower().split())
    # 中文字符分词（简单切分）
    cn_terms = set(re.findall(r'[\u4e00-\u9fff]+', query))
    terms.update(cn_terms)
    terms.update([c for c in query.lower() if not c.isspace()])

    # 语义扩展
    expanded = set(terms)
    for key, synonyms in SEMANTIC_EXPAND.items():
        if key in query or any(s in query.lower() for s in synonyms):
            expanded.add(key)
            expanded.update(synonyms)

    return expanded


def search_knowledge(query: str, top_k: int = 5) -> list:
    """语义扩展搜索（默认启用）"""
    if not KNOWLEDGE_DIR.exists():
        return []

    results = []
    base_terms = set(re.findall(r'[\u4e00-\u9fff]+|[a-z0-9_]+', query.lower()))
    search_terms = expand_query(query)

    for md_file in KNOWLEDGE_DIR.glob("*.md"):
        if md_file.name.startswith("_"):
            continue
        try:
            content = md_file.read_text(encoding='utf-8')
            content_lower = content.lower()
            lines = content.split('\n')

            score = 0
            matched_lines = []

            # 精确短语匹配（高权重）
            if query.lower() in content_lower:
                score += 200

            # 标题匹配（高权重）
            title = lines[0].replace('# ', '').strip() if lines else md_file.stem
            if any(t in title.lower() for t in base_terms):
                score += 150

            # 逐词匹配
            for term in search_terms:
                if len(term) < 2:
                    continue
                cnt = content_lower.count(term)
                # 语义扩展词权重低一些
                weight = 1 if term in base_terms else 0.3
                score += cnt * weight

            if score > 0:
                # 提取相关段落（含前后上下文）
                for i, line in enumerate(lines):
                    line_lower = line.lower()
                    if any(t in line_lower for t in base_terms if len(t) >= 2):
                        start = max(0, i - 2)
                        end = min(len(lines), i + 5)
                        context = '\n'.join(lines[start:end]).strip()
                        if context and len(context) > 10:
                            matched_lines.append(context)

                # 去重段落
                seen = set()
                unique_lines = []
                for ctx in matched_lines:
                    key = ctx[:50]
                    if key not in seen:
                        seen.add(key)
                        unique_lines.append(ctx)

                results.append({
                    "file": md_file.name,
                    "score": int(score),
                    "title": title,
                    "contexts": unique_lines[:5],
                    "full_path": str(md_file)
                })
        except Exception:
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def main():
    if len(sys.argv) < 2:
        print("用法: python3 query_knowledge.py <查询内容> [--top N]")
        sys.exit(1)

    args = sys.argv[1:]
    top_k = 5
    for i, a in enumerate(args):
        if a == "--top" and i + 1 < len(args):
            top_k = int(args[i + 1])
    query_parts = [a for a in args if not a.startswith("--") and not a.isdigit()]
    query = " ".join(query_parts)

    if not KNOWLEDGE_DIR.exists() or not any(KNOWLEDGE_DIR.glob("*.md")):
        print("知识库为空，请先运行 sync_km_docs.py 同步文档")
        sys.exit(1)

    results = search_knowledge(query, top_k=top_k)

    if not results:
        print(f"未找到与「{query}」相关的内容")
        print("当前这个问题在数仓知识库中还没有录入，请进行人工咨询。")
        sys.exit(0)

    print(f"查询: {query} [语义扩展模式]")
    print(f"找到 {len(results)} 个相关文档:\n")

    for i, r in enumerate(results, 1):
        print(f"{'='*60}")
        print(f"[{i}] {r['title']} (匹配度: {r['score']})")
        print(f"    文件: {r['file']}")
        print(f"{'='*60}")
        for ctx in r['contexts']:
            print(ctx)
            print("---")
        print()


if __name__ == "__main__":
    main()
