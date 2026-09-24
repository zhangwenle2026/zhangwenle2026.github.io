#!/usr/bin/env python3
"""Keeta RAG semantic table search via mtcli."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

_CORE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "core"))
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

try:
    from core.mtcli import run as _mtcli_run
except ImportError:
    from mtcli import run as _mtcli_run

try:
    from capability5_meta.table_filters import filter_rag_result
except ImportError:
    from table_filters import filter_rag_result


def _unwrap_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(payload, dict) and payload.get("success") is True and isinstance(payload.get("data"), dict):
        return payload["data"]
    if isinstance(payload, dict) and payload.get("code", 0) not in (0, 200, None):
        raise RuntimeError(payload.get("message") or payload.get("msg") or payload)
    return payload if isinstance(payload, dict) else None


def rag_search(query: str, qtype: str = "table", force_refresh_cookie: bool = False, timeout: int = 60) -> dict | None:
    del force_refresh_cookie
    payload = _mtcli_run(
        ["kdata", "meta", "rag-table-search"],
        params={"query": query, "type": qtype},
        timeout=timeout,
    )
    result = _unwrap_payload(payload)
    return filter_rag_result(result) if result else result


def main() -> None:
    parser = argparse.ArgumentParser(description="Keeta RAG 语义找表（mtcli）")
    parser.add_argument("query")
    parser.add_argument("--type", choices=["table", "business", "metric"], default="table")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--refresh-cookie", action="store_true")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()
    run(args)


def run(args: argparse.Namespace) -> None:
    result = rag_search(
        args.query,
        qtype=args.type,
        force_refresh_cookie=getattr(args, "refresh_cookie", False),
        timeout=args.timeout,
    )
    if not result:
        print("RAG 检索无结果或服务不可用", file=sys.stderr)
        raise SystemExit(1)

    duration_s = result.get("duration", 0) / 1000
    doc_count = result.get("documentCount", 0)
    print(f"[RAG 耗时 {duration_s:.1f}s，召回 {doc_count} 个切片]", file=sys.stderr)

    if args.format == "json":
        print(json.dumps({
            "query": result.get("query"),
            "documentCount": doc_count,
            "documents": result.get("documents", []),
        }, ensure_ascii=False, indent=2))
    else:
        print(result.get("combinedContent", ""))


if __name__ == "__main__":
    main()
