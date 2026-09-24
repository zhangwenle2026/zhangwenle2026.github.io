#!/usr/bin/env python3
"""Shared table-result filters for metadata search."""

from __future__ import annotations

import re
from typing import Any

_UNUSABLE_TABLE_RE = re.compile(r"(?<![a-z0-9_])h?mart_sailor_etl(?:\.|$)", re.IGNORECASE)


def contains_unusable_table_ref(value: Any) -> bool:
    if value is None:
        return False
    return bool(_UNUSABLE_TABLE_RE.search(str(value)))


def is_unusable_table_item(item: dict[str, Any]) -> bool:
    return any(
        contains_unusable_table_ref(item.get(field))
        for field in ("name", "fullName", "tableName", "dsn", "dsnName")
    )


def is_unusable_rag_document(document: Any) -> bool:
    if isinstance(document, dict):
        fields = ("content", "text", "title", "name", "tableName", "fullName", "dsn", "dsnName")
        return any(contains_unusable_table_ref(document.get(field)) for field in fields)
    return contains_unusable_table_ref(document)


def filter_rag_result(result: dict[str, Any]) -> dict[str, Any]:
    documents = result.get("documents")
    if not isinstance(documents, list):
        return result

    kept = [doc for doc in documents if not is_unusable_rag_document(doc)]
    if len(kept) == len(documents):
        return result

    filtered = dict(result)
    filtered["documents"] = kept
    filtered["documentCount"] = len(kept)
    if isinstance(filtered.get("combinedContent"), str):
        contents = []
        for doc in kept:
            if isinstance(doc, dict):
                content = doc.get("content") or doc.get("text") or ""
            else:
                content = str(doc)
            if content:
                contents.append(content)
        filtered["combinedContent"] = "\n\n".join(contents)
    return filtered
