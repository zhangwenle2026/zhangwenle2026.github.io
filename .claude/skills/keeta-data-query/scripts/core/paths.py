#!/usr/bin/env python3
"""
core/paths.py - unified path resolution for the keeta-data-query skill.

All paths are derived from __file__ and environment overrides instead of hard
coding OpenClaw/Catpaw installation prefixes.
"""

from __future__ import annotations

import os
from pathlib import Path

# This file lives at <skill_root>/scripts/core/paths.py.
_THIS_FILE = Path(__file__).resolve()
_SCRIPTS_DIR = _THIS_FILE.parent.parent
SKILL_ROOT = _SCRIPTS_DIR.parent
SCRIPTS_DIR = _SCRIPTS_DIR


def _default_skill_name() -> str:
    if SKILL_ROOT.name == "skill" and SKILL_ROOT.parent.name:
        return SKILL_ROOT.parent.name
    return SKILL_ROOT.name or "keeta-data-query"


_DEFAULT_SKILL_NAME = _default_skill_name()
SKILL_NAME = os.environ.get("KDATA_SKILL_NAME", _DEFAULT_SKILL_NAME).strip() or _DEFAULT_SKILL_NAME

CACHE_DIR = SKILL_ROOT / ".cache"


def skill_cache(filename: str) -> Path:
    """Return <skill_root>/.cache/<filename>, creating the parent directory."""
    path = CACHE_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    """Dedupe paths by resolved location while preserving input order."""
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        try:
            key = str(path.expanduser().resolve())
        except Exception:
            key = str(path.expanduser())
        if key in seen:
            continue
        seen.add(key)
        result.append(path.expanduser())
    return result


def _split_env_paths(value: str) -> list[Path]:
    """Parse an os.pathsep-separated environment path list."""
    return [Path(item).expanduser() for item in value.split(os.pathsep) if item.strip()]


def _path_entries() -> list[Path]:
    """Return current PATH directories."""
    return _split_env_paths(os.environ.get("PATH", ""))


def _is_stable_writable_bin_dir(path: Path) -> bool:
    """Return whether a directory is suitable for the kdata symlink."""
    try:
        p = path.expanduser()
        if not p.is_dir():
            return False
        resolved = str(p.resolve())
        if resolved in {"/bin", "/usr/bin", "/sbin", "/usr/sbin"}:
            return False
        unstable_markers = ("/tmp/", "/var/folders/", "/.codex/tmp/", "/node_modules/", "/.nvm/", "/.bun/")
        if any(marker in resolved for marker in unstable_markers):
            return False
        return os.access(str(p), os.W_OK | os.X_OK)
    except Exception:
        return False


def _path_contains(path_entries: list[Path], candidate: Path) -> bool:
    """Compare resolved paths to determine whether candidate is in PATH."""
    try:
        target = str(candidate.expanduser().resolve())
    except Exception:
        target = str(candidate.expanduser())
    for item in path_entries:
        try:
            key = str(item.expanduser().resolve())
        except Exception:
            key = str(item.expanduser())
        if key == target:
            return True
    return False


def _resolve_workspace_dir() -> Path:
    env_ws = os.environ.get("KDATA_WORKSPACE", "").strip()
    if env_ws:
        p = Path(env_ws).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p

    candidates = [
        Path.home() / ".openclaw" / "workspace" / SKILL_NAME,
        Path.home() / ".catpaw" / "workspace" / SKILL_NAME,
    ]
    for p in candidates:
        if p.is_dir():
            return p

    fallback = SKILL_ROOT / ".workspace"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _resolve_bin_dir() -> Path:
    env_bin = os.environ.get("KDATA_BIN_DIR", "").strip()
    if env_bin:
        return Path(env_bin).expanduser()

    path_entries = _path_entries()
    preferred = [
        Path.home() / ".openclaw" / "bin",
        Path.home() / ".catpaw" / "bin",
        Path.home() / ".catdesk" / "bin",
        Path.home() / ".local" / "bin",
        Path.home() / "bin",
        Path("/usr/local/bin"),
        Path("/opt/homebrew/bin"),
    ]
    for p in preferred:
        if _path_contains(path_entries, p) and _is_stable_writable_bin_dir(p):
            return p.expanduser()

    for p in path_entries:
        if _is_stable_writable_bin_dir(p):
            return p.expanduser()

    return Path.home() / "bin"


def _resolve_skill_search_dirs() -> tuple[Path, ...]:
    env_dirs = _split_env_paths(os.environ.get("KDATA_SKILL_SEARCH_DIRS", ""))
    candidates = env_dirs + [
        SKILL_ROOT.parent,
        Path.home() / ".openclaw" / "skills",
        Path.home() / ".catpaw" / "skills",
    ]
    return tuple(_dedupe_paths(candidates))


WORKSPACE_DIR: Path = _resolve_workspace_dir()
BIN_DIR: Path = _resolve_bin_dir()
KDATA_BIN: Path = BIN_DIR / "kdata"
SKILL_SEARCH_DIRS: tuple[Path, ...] = _resolve_skill_search_dirs()

# Kept for compatibility with existing auth/query code.
KDATA_CONF: Path = WORKSPACE_DIR / "kdata.conf"
USER_MD: Path = WORKSPACE_DIR / "USER.md"


def workspace_file(rel: str) -> Path:
    """Return <WORKSPACE_DIR>/<rel>."""
    return WORKSPACE_DIR / rel


def workspace_state(rel: str) -> Path:
    """Return <WORKSPACE_DIR>/state/<rel>, creating the parent directory."""
    path = WORKSPACE_DIR / "state" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def skill_name_str() -> str: return SKILL_NAME
def skill_root_str() -> str: return str(SKILL_ROOT)
def scripts_dir_str() -> str: return str(SCRIPTS_DIR)
def cache_dir_str() -> str: return str(CACHE_DIR)
def workspace_dir_str() -> str: return str(WORKSPACE_DIR)
def bin_dir_str() -> str: return str(BIN_DIR)
def kdata_bin_str() -> str: return str(KDATA_BIN)
def kdata_conf_str() -> str: return str(KDATA_CONF)
def user_md_str() -> str: return str(USER_MD)


def skill_search_dirs_str() -> str:
    return os.pathsep.join(str(path) for path in SKILL_SEARCH_DIRS)
