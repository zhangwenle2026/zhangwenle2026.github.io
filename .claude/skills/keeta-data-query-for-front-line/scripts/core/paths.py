#!/usr/bin/env python3
"""Shared path resolution for keeta-data-query-for-front-line."""

from __future__ import annotations

import os
from pathlib import Path

_THIS_FILE = Path(__file__).resolve()
SCRIPTS_DIR = _THIS_FILE.parent.parent
SKILL_ROOT = SCRIPTS_DIR.parent
SKILL_NAME = os.environ.get("KDATA_SKILL_NAME", SKILL_ROOT.name).strip() or SKILL_ROOT.name


def _split_env_paths(value: str) -> list[Path]:
    return [Path(item).expanduser() for item in value.split(os.pathsep) if item.strip()]


def _dedupe(paths: list[Path]) -> tuple[Path, ...]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        p = path.expanduser()
        try:
            key = str(p.resolve())
        except Exception:
            key = str(p)
        if key in seen:
            continue
        seen.add(key)
        result.append(p)
    return tuple(result)


def _resolve_workspace_dir() -> Path:
    env_ws = os.environ.get("KDATA_WORKSPACE", "").strip()
    if env_ws:
        path = Path(env_ws).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path

    candidates = [
        Path.home() / ".openclaw" / "workspace" / SKILL_NAME,
        Path.home() / ".catpaw" / "workspace" / SKILL_NAME,
    ]
    for path in candidates:
        if path.is_dir():
            return path

    fallback = candidates[0]
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _resolve_bin_dir() -> Path:
    env_bin = os.environ.get("KDATA_BIN_DIR", "").strip()
    if env_bin:
        return Path(env_bin).expanduser()
    return Path.home() / "bin"


def _resolve_skill_search_dirs() -> tuple[Path, ...]:
    env_dirs = _split_env_paths(os.environ.get("KDATA_SKILL_SEARCH_DIRS", ""))
    candidates = env_dirs + [
        SKILL_ROOT.parent,
        Path.home() / ".openclaw" / "skills",
        Path.home() / ".catpaw" / "skills",
        Path.home() / ".codex" / "skills",
        Path.home() / ".keetai" / "profiles" / "codex" / "Default" / ".codex" / "skills",
    ]
    return _dedupe(candidates)


WORKSPACE_DIR = _resolve_workspace_dir()
BIN_DIR = _resolve_bin_dir()
KDATA_BIN = BIN_DIR / "kdata-fl"
KDATA_CONF = WORKSPACE_DIR / "kdata.conf"
USER_MD = WORKSPACE_DIR / "USER.md"
SKILL_SEARCH_DIRS = _resolve_skill_search_dirs()


def workspace_file(rel: str) -> Path:
    return WORKSPACE_DIR / rel


def workspace_state(rel: str) -> Path:
    path = WORKSPACE_DIR / "state" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
