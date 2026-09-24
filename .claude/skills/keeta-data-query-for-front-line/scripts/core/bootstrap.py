#!/usr/bin/env python3
"""Runtime bootstrap for the front-line kdata-fl CLI."""

from __future__ import annotations

import os
import sys

try:
    from core.paths import KDATA_BIN, SCRIPTS_DIR
except ImportError:
    from paths import KDATA_BIN, SCRIPTS_DIR


def _debug_warn(message: str) -> None:
    if os.environ.get("KDATA_BOOTSTRAP_DEBUG", "").strip():
        print(message, file=sys.stderr)


def ensure_cli_path() -> None:
    """Prepend common user bin directories for child processes."""
    extra_paths = [
        os.path.expanduser("~/bin"),
        os.path.expanduser("~/.local/bin"),
        "/usr/local/bin",
    ]
    parts = os.environ.get("PATH", "/usr/bin:/bin").split(os.pathsep)
    prepend = [path for path in extra_paths if path and path not in parts]
    if prepend:
        os.environ["PATH"] = os.pathsep.join(prepend + parts)


def ensure_cli_installed() -> None:
    """Repair executable bit and the user-level kdata-fl symlink when possible."""
    ensure_cli_path()
    main_py = SCRIPTS_DIR / "kdata_fl.py"
    wrapper_py = SCRIPTS_DIR / "kdata.py"
    for script_path in (main_py, wrapper_py):
        try:
            if script_path.exists():
                script_path.chmod(script_path.stat().st_mode | 0o111)
        except Exception as e:
            _debug_warn(f"[kdata-fl][WARN] {script_path.name} 权限修复失败: {e}")

    try:
        KDATA_BIN.parent.mkdir(parents=True, exist_ok=True)
        if KDATA_BIN.is_symlink():
            try:
                if KDATA_BIN.resolve() == main_py.resolve():
                    return
            except Exception:
                pass
            KDATA_BIN.unlink()
        elif KDATA_BIN.exists():
            _debug_warn(f"[kdata-fl][WARN] {KDATA_BIN} 已存在且不是软链，跳过覆盖")
            return
        KDATA_BIN.symlink_to(main_py)
    except Exception as e:
        _debug_warn(f"[kdata-fl][WARN] kdata-fl 软链修复失败: {e}")
