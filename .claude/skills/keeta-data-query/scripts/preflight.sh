#!/usr/bin/env bash
# keeta-data-query preflight - environment checks and initialization.
#
# Structured output consumed by the Agent:
#   CONFLICT: skill1 skill2 ...       -> ask user whether to uninstall conflicts
#   DEPS_REQUIRED                     -> npm dependency install failed
#   MIS_REQUIRED                      -> automatic MIS resolution failed after one retry
#   READY                             -> safe to start querying

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PATHS_CLI="$SCRIPT_DIR/core/paths_cli.py"

_path() {
  python3 "$PATHS_CLI" "$1"
}

SKILL_DIR="$(_path skill-root)"
CACHE_DIR="$(_path cache-dir)"
KDATA_BIN="$(_path kdata-bin)"
SKILL_SEARCH_DIRS="$(_path skill-search-dirs)"

_ensure_kdata_cli() {
  local kdata_py="$SCRIPT_DIR/kdata.py"
  local kdata_link="$KDATA_BIN"

  chmod +x "$kdata_py" 2>/dev/null || true
  mkdir -p "$(dirname "$kdata_link")"

  if [ ! -L "$kdata_link" ] || [ "$(readlink "$kdata_link" 2>/dev/null)" != "$kdata_py" ]; then
    ln -sf "$kdata_py" "$kdata_link"
  fi

  export PATH="$(dirname "$kdata_link"):$PATH"
}

_skill_exists() {
  local skill="$1"
  local root
  local old_ifs="$IFS"

  IFS=":"
  for root in $SKILL_SEARCH_DIRS; do
    if [ -d "$root/$skill" ]; then
      IFS="$old_ifs"
      return 0
    fi
  done
  IFS="$old_ifs"
  return 1
}

# This must always run and cannot be skipped by preflight throttling.
_ensure_kdata_cli

# npm dependencies must be installed before MIS detection so mtcli is available.
if ! PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 -c "from core.bootstrap import ensure_runtime_deps; ensure_runtime_deps()"; then
  echo "DEPS_REQUIRED"
  echo "DEPS_MESSAGE: kdata npm 依赖安装失败。请确认 Node.js/npm/npx 可用，并按上方错误提示处理后重试。"
  exit 0
fi

# core/mis.py retries once; if it still fails, the Agent should ask the user for MIS.
if ! python3 "$SCRIPT_DIR/core/mis.py" >/dev/null 2>&1; then
  echo "MIS_REQUIRED"
  echo "MIS_ACTION:KDATA_MIS=<MIS> bash scripts/preflight.sh"
  echo "MIS_MESSAGE: 自动获取当前用户 MIS 失败，已重试一次仍未成功。请向用户询问他的 MIS，然后执行 MIS_ACTION 后重试。"
  exit 0
fi

# ── Frequency control: skip lower-priority checks within 30 minutes ─────────

mkdir -p "$CACHE_DIR"
_PREFLIGHT_TS_FILE="${CACHE_DIR}/preflight-ts"
_PREFLIGHT_INTERVAL=1800

if [ -f "$_PREFLIGHT_TS_FILE" ]; then
  _last_run=$(cat "$_PREFLIGHT_TS_FILE" 2>/dev/null || echo 0)
  _now=$(date +%s)
  _diff=$((_now - _last_run))
  if [ "$_diff" -lt "$_PREFLIGHT_INTERVAL" ]; then
    echo "READY"
    exit 0
  fi
fi

date +%s > "$_PREFLIGHT_TS_FILE" 2>/dev/null || true

# ── Conflicting skill detection ─────────────────────────────────────────────

CONFLICT_SKILLS="mt-data-tools bi-query-sql bi-query-dashboard bi-data-query-chat sql-query bi-viz-moshu bi-analysis-calculation-toolkit bi-query-dataset-overseas"
FOUND=""
for s in $CONFLICT_SKILLS; do
  if _skill_exists "$s"; then
    FOUND="$FOUND $s"
  fi
done
if [ -n "$FOUND" ]; then
  echo "CONFLICT:$FOUND"
fi

# ── Auto-update check, throttled inside the script ──────────────────────────

bash "$SCRIPT_DIR/auto_update.sh" || true

echo "READY"
