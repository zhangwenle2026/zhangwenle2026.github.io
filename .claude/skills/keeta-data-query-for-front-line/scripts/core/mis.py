#!/usr/bin/env python3
"""Resolve the current user MIS through mtcli."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    from core.paths import KDATA_CONF, USER_MD
except ImportError:
    from paths import KDATA_CONF, USER_MD

_MIS_CACHE: str | None = None
_CONFIG_FILE = KDATA_CONF
_ENV_MIS_KEYS = ("KDATA_MIS", "SANDBOX_MIS", "OPENCLAW_MIS", "MEITUAN_MIS")


def no_proxy_env() -> dict:
    drop = {"HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"}
    return {k: v for k, v in os.environ.items() if k not in drop}


def _candidate_commands() -> list[list[str]]:
    commands: list[list[str]] = []
    mtcli = shutil.which("mtcli")
    if mtcli:
        commands.append([mtcli, "kdata", "log", "get-mis"])
    npx = shutil.which("npx")
    if npx:
        commands.append([npx, "mtcli", "kdata", "log", "get-mis"])
    return commands


def _normalise_mis(value: str) -> str:
    mis = value.strip()
    if mis.lower() in {"", "unknown", "none", "null"}:
        return ""
    return mis


def _extract_mis(value: Any) -> str:
    if isinstance(value, str):
        return _normalise_mis(value)
    if isinstance(value, dict):
        if "data" in value:
            return _extract_mis(value["data"])
        for key in ("mis", "user", "username", "userMis"):
            mis = _extract_mis(value.get(key))
            if mis:
                return mis
    return ""


def _parse_output(text: str) -> str:
    raw = text.strip()
    if not raw:
        return ""
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    candidates = [raw] + [line for line in reversed(lines) if line != raw]
    for candidate in candidates:
        try:
            mis = _extract_mis(json.loads(candidate))
            if mis:
                return mis
        except Exception:
            pass
    if len(lines) == 1 and not raw.startswith("{"):
        return _normalise_mis(raw)
    return ""


def _read_config_mis() -> str:
    try:
        data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        return _normalise_mis(str(data.get("mis", "")))
    except Exception:
        return ""


def _read_user_md_mis() -> str:
    try:
        import re
        text = USER_MD.read_text(encoding="utf-8")
        match = re.search(r"MIS[^::。]*[::：]\s*([a-zA-Z0-9_]+)", text)
        if match:
            return _normalise_mis(match.group(1))
    except Exception:
        return ""
    return ""


def _write_config_mis(mis: str) -> str:
    value = _normalise_mis(mis)
    if not value:
        raise ValueError("MIS 不能为空")
    try:
        data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8")) if _CONFIG_FILE.exists() else {}
    except Exception:
        data = {}
    data["mis"] = value
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return value


def _get_env_mis() -> str:
    for key in _ENV_MIS_KEYS:
        mis = _normalise_mis(os.environ.get(key, ""))
        if mis:
            return mis
    return ""


def set_manual_mis(mis: str) -> str:
    value = _write_config_mis(mis)
    global _MIS_CACHE
    _MIS_CACHE = value
    return value


def get_mis(default: str = "", timeout: int = 10, retries: int = 1) -> str:
    """Resolve current user MIS via mtcli; fall back to env or user-provided MIS."""
    global _MIS_CACHE
    if _MIS_CACHE is not None:
        return _MIS_CACHE or default

    configured_mis = _read_config_mis()
    commands = _candidate_commands()
    attempts = max(1, retries + 1)
    for attempt in range(attempts):
        for command in commands:
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=no_proxy_env(),
                )
            except Exception:
                continue
            if result.returncode != 0:
                continue
            mis = _parse_output(result.stdout) or _parse_output(result.stderr)
            if mis:
                if mis != configured_mis:
                    try:
                        _write_config_mis(mis)
                    except Exception:
                        pass
                _MIS_CACHE = mis
                return mis
        if commands and attempt < attempts - 1:
            time.sleep(1)

    env_mis = _get_env_mis()
    if env_mis:
        try:
            _write_config_mis(env_mis)
        except Exception:
            pass
        _MIS_CACHE = env_mis
        return env_mis

    user_md_mis = _read_user_md_mis()
    if user_md_mis:
        try:
            _write_config_mis(user_md_mis)
        except Exception:
            pass
        _MIS_CACHE = user_md_mis
        return user_md_mis

    if configured_mis:
        _MIS_CACHE = configured_mis
        return configured_mis

    _MIS_CACHE = ""
    return default


def main() -> int:
    mis = get_mis(default="")
    if not mis:
        return 1
    print(mis)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
