#!/usr/bin/env python3
"""Meta capability auth adapters.

Most business calls are executed by mtcli and should let mtcli manage SSO.
This module only supplies explicit access-token headers for mtcli schemas or
services that still require them, such as Origin and XT fallback.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _load_core_auth():
    scripts_dir = Path(__file__).resolve().parents[1]
    scripts_str = str(scripts_dir)
    if scripts_str not in sys.path:
        sys.path.insert(0, scripts_str)
    try:
        return importlib.import_module("core.auth")
    except ImportError:
        return importlib.import_module("auth")


_core_auth = _load_core_auth()

_AUDIENCE = {
    "origin": "5af3aa3409",
    "xt": "xt",
}

# Compatibility for tests and callers that clear the meta auth cache directly.
_TOKEN_CACHE = getattr(_core_auth, "_token_cache", {})


def _mtsso_exchange(audience: str, timeout: int = 30) -> str:
    """Return an SSO token through the shared core auth chain."""
    del timeout
    return _core_auth.get_token(audience, cdp_fallback=False)


def invalidate_cache(audience: str) -> None:
    """Clear the shared process token cache for one audience."""
    _TOKEN_CACHE.pop(audience, None)


def get_origin_token() -> str:
    """Get the Origin access token required by current mtcli Origin schemas."""
    return _mtsso_exchange(_AUDIENCE["origin"])


def get_xt_token() -> str:
    """Get the XT access token used only when the XT service requires a header."""
    return _mtsso_exchange(_AUDIENCE["xt"])


def get_origin_headers(busi_line_id: int = 274) -> dict:
    """Build mtcli header params for Origin commands that require access-token."""
    return {
        "access-token": get_origin_token(),
        "X-BusilineId": str(busi_line_id),
        "x-locale": "zh",
        "x-i18n-lang": "1",
        "x-requested-with": "XMLHttpRequest",
    }


def check_all(verbose: bool = True) -> dict:
    """Check explicit-token services only."""
    results = {}
    checks = [
        ("origin", _AUDIENCE["origin"], "起源"),
        ("xt", _AUDIENCE["xt"], "XT ETL"),
    ]
    for key, audience, label in checks:
        token = _mtsso_exchange(audience)
        results[key] = {
            "ok": bool(token),
            "msg": (
                f"mtsso/CIBA 换票成功（{audience}）"
                if token
                else f"换票失败（{audience}），请确认 MOA/大象登录态"
            ),
        }
        if verbose:
            icon = "OK" if results[key]["ok"] else "FAIL"
            print(f"  [{icon}] [{label}] {results[key]['msg']}")
    return results


if __name__ == "__main__":
    print("keeta-data-query meta auth explicit-token check")
    print("=" * 50)
    status = check_all(verbose=True)
    failed = [k for k, v in status.items() if not v["ok"]]
    print("=" * 50)
    if failed:
        print(f"{len(failed)} 项失败: {', '.join(failed)}")
    else:
        print("所有显式 token 链路正常")
    sys.exit(1 if failed else 0)
