#!/usr/bin/env python3
"""
core/bootstrap.py - kdata initialization and dependency bootstrap.

Keep kdata.py focused on CLI routing and query lifecycle; this module owns
first-run initialization, SSO Node dependency checks, mtcli availability, and
the deps_checked marker.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

try:
    from core.mis import get_mis as _get_current_mis
    from core.mis import set_manual_mis as _set_manual_mis
    from core.paths import KDATA_BIN, SCRIPTS_DIR, WORKSPACE_DIR
except ImportError:
    from mis import get_mis as _get_current_mis
    from mis import set_manual_mis as _set_manual_mis
    from paths import KDATA_BIN, SCRIPTS_DIR, WORKSPACE_DIR


_NPM_PKG = "@mtfe/mtsso-auth-official"
_MTCLI_NPM_PKG = "@dp/mtcli"
_NPM_REGISTRY = "http://r.npm.sankuai.com"
_NPM_CMD = "mtsso-moa-local-exchange"
_MTCLI_CMD = "mtcli"
_DEPS_CHECK_FILE = str(WORKSPACE_DIR / "deps_checked")
_DEPS_CHECK_INTERVAL = 86400  # 24 hours


def _debug_warn(message: str) -> None:
    if os.environ.get("KDATA_BOOTSTRAP_DEBUG", "").strip():
        print(message, file=sys.stderr)


def ensure_cli_path() -> None:
    """Add common user bin directories so non-interactive shells can find kdata/npx."""
    extra_paths = [
        os.path.expanduser("~/.local/bin"),
        os.path.expanduser("~/bin"),
        "/usr/local/bin",
    ]
    current = os.environ.get("PATH", "/usr/bin:/bin")
    parts = current.split(os.pathsep)
    prepend = [p for p in extra_paths if p and p not in parts]
    if prepend:
        os.environ["PATH"] = os.pathsep.join(prepend + parts)


def ensure_cli_installed() -> None:
    """Idempotently repair kdata.py executable bit, kdata symlink, and process PATH."""
    ensure_cli_path()
    try:
        kdata_py = SCRIPTS_DIR / "kdata.py"
        try:
            kdata_py.chmod(kdata_py.stat().st_mode | 0o111)
        except Exception as e:
            _debug_warn(f"[kdata][WARN] kdata.py 权限修复失败: {e}")

        KDATA_BIN.parent.mkdir(parents=True, exist_ok=True)
        if KDATA_BIN.is_symlink():
            try:
                if KDATA_BIN.resolve() == kdata_py.resolve():
                    return
            except Exception:
                pass
            KDATA_BIN.unlink()
        elif KDATA_BIN.exists():
            KDATA_BIN.unlink()
        KDATA_BIN.symlink_to(kdata_py)
    except Exception as e:
        _debug_warn(f"[kdata][WARN] kdata 软链修复失败: {e}")


def cmd_init(args) -> None:
    """Initialize kdata runtime dependencies and optional manual MIS fallback."""
    manual_mis = (getattr(args, "mis", "") or "").strip()
    if manual_mis:
        try:
            manual_mis = _set_manual_mis(manual_mis)
        except ValueError as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)

    ensure_runtime_deps()

    mis = manual_mis or _get_current_mis(default="")

    print("✅ kdata 初始化完成")
    if mis:
        source = "用户提供" if manual_mis else "mtcli"
        print(f"  MIS: {mis}（{source}）")
    else:
        print("  MIS: 未获取到。可通过 KDATA_MIS=<MIS> bash scripts/preflight.sh 保存备用 MIS")


def check_deps() -> None:
    """
    Dependency check for query commands.

    init/task commands handle their own paths and should not be intercepted here.
    """
    import shutil

    if shutil.which("npx") is None:
        print("❌ 未找到 npx，请先安装 Node.js (https://nodejs.org)", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(_DEPS_CHECK_FILE):
        ensure_runtime_deps()
        return

    try:
        last_checked = float(open(_DEPS_CHECK_FILE, encoding="utf-8").read().strip())
    except Exception:
        last_checked = 0.0

    if time.time() - last_checked < _DEPS_CHECK_INTERVAL:
        return

    _check_updates_in_background()


def _mark_deps_checked() -> None:
    """Record dependency check time; failure should not block init or queries."""
    try:
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_DEPS_CHECK_FILE, "w", encoding="utf-8") as fh:
            fh.write(str(time.time()))
    except Exception as e:
        print(f"[kdata][WARN] 依赖检查时间写入失败: {e}", file=sys.stderr)


def _no_proxy_env() -> dict:
    env = {**os.environ}
    for k in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        env.pop(k, None)
    return env


def _npm_install(package: str, env: dict, timeout: int = 120) -> bool:
    """Install or update a global npm package."""
    import shutil

    npm = shutil.which("npm")
    if not npm:
        return False
    try:
        r = subprocess.run(
            [npm, "install", "-g", package, "--registry", _NPM_REGISTRY],
            timeout=timeout, env=env, capture_output=True, text=True,
        )
        return r.returncode == 0
    except Exception:
        return False


def _sso_exchange_available(env: dict) -> bool:
    """Return whether mtsso-moa-local-exchange is globally executable."""
    import shutil

    cmd = shutil.which(_NPM_CMD)
    if not cmd:
        return False
    try:
        # The command has no --version; without args it exits non-zero but proves install.
        r = subprocess.run([cmd], timeout=15, env=env, capture_output=True, text=True)
        return r.returncode in (0, 1, 2)
    except Exception:
        return False


def _mtcli_available(env: dict) -> bool:
    """Return whether mtcli is globally executable."""
    import shutil

    cmd = shutil.which(_MTCLI_CMD)
    if not cmd:
        return False
    try:
        r = subprocess.run([cmd, "--version"], timeout=15, env=env, capture_output=True, text=True)
        return r.returncode == 0
    except Exception:
        return False


def _install_deps() -> None:
    """Synchronously install runtime deps and write deps_checked."""
    import shutil

    if shutil.which("npx") is None:
        print("❌ 未找到 npx，请先安装 Node.js (https://nodejs.org)", file=sys.stderr)
        sys.exit(1)

    env = _no_proxy_env()

    if not _sso_exchange_available(env):
        print(f"[kdata] 正在安装依赖 {_NPM_PKG} ...", file=sys.stderr)
        if not _npm_install(f"{_NPM_PKG}@latest", env):
            print(
                f"❌ 安装失败，请手动运行：\n"
                f"  npm install -g {_NPM_PKG}@latest --registry {_NPM_REGISTRY}",
                file=sys.stderr,
            )
            sys.exit(1)
        print("[kdata] 依赖安装完成 ✅", file=sys.stderr)

    if not _mtcli_available(env):
        print(f"[kdata] 正在安装依赖 {_MTCLI_NPM_PKG} ...", file=sys.stderr)
        if not _npm_install(_MTCLI_NPM_PKG, env):
            print(
                f"❌ 安装失败，请手动运行：\n"
                f"  npm install -g {_MTCLI_NPM_PKG} --registry {_NPM_REGISTRY}",
                file=sys.stderr,
            )
            sys.exit(1)
        print("[kdata] mtcli 依赖安装完成 ✅", file=sys.stderr)

    _mark_deps_checked()


def ensure_runtime_deps() -> None:
    """Synchronously ensure required npm packages are available."""
    ensure_cli_path()
    _install_deps()


def _check_updates_in_background() -> None:
    """Refresh SSO dependency asynchronously after the check interval."""
    env = _no_proxy_env()
    subprocess.Popen(
        [sys.executable, "-c",
         f"import subprocess,os,time;"
         f"env={{k:v for k,v in os.environ.items() if k not in ('HTTP_PROXY','http_proxy','HTTPS_PROXY','https_proxy','ALL_PROXY','all_proxy')}};"
         f"r=subprocess.run(['npm','install','-g','{_NPM_PKG}@latest','--registry','{_NPM_REGISTRY}'],timeout=120,env=env,capture_output=True);"
         f"open('{_DEPS_CHECK_FILE}','w').write(str(time.time())) if r.returncode==0 else None"
         ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
