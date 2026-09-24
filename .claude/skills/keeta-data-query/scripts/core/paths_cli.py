#!/usr/bin/env python3
"""Print resolved kdata paths for shell scripts."""

from __future__ import annotations

import sys
from pathlib import Path

_CORE_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _CORE_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from core import paths


_VALUES = {
    "skill-name": lambda: paths.SKILL_NAME,
    "skill-root": lambda: str(paths.SKILL_ROOT),
    "scripts-dir": lambda: str(paths.SCRIPTS_DIR),
    "cache-dir": lambda: str(paths.CACHE_DIR),
    "workspace-dir": lambda: str(paths.WORKSPACE_DIR),
    "bin-dir": lambda: str(paths.BIN_DIR),
    "kdata-bin": lambda: str(paths.KDATA_BIN),
    "skill-search-dirs": paths.skill_search_dirs_str,
}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in _VALUES:
        names = ", ".join(sorted(_VALUES))
        print(f"usage: paths_cli.py <{names}>", file=sys.stderr)
        return 2
    print(_VALUES[argv[1]]())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
