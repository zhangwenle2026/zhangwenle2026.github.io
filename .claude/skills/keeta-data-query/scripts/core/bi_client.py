#!/usr/bin/env python3
"""Compatibility wrapper for legacy `core.bi_client` imports.

Hive execution now lives in `capability2_hive.hive_client`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from capability2_hive import hive_client as _hive_client

BI_BASE = _hive_client.BI_BASE
STATUS_RUNNING = _hive_client.STATUS_RUNNING
STATUS_SUCCESS = _hive_client.STATUS_SUCCESS
STATUS_DONE = _hive_client.STATUS_DONE
BiClient = _hive_client.BiClient
_normalize_project_name = _hive_client._normalize_project_name
_resolve_sql_text = _hive_client._resolve_sql_text
_extract_apply_links = _hive_client._extract_apply_links

__all__ = [
    "BI_BASE",
    "STATUS_RUNNING",
    "STATUS_SUCCESS",
    "STATUS_DONE",
    "BiClient",
    "_normalize_project_name",
    "_resolve_sql_text",
    "_extract_apply_links",
]
