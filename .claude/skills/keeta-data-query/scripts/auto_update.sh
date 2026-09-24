#!/usr/bin/env bash
# keeta-data-query 自动更新检查脚本
# 用法: bash auto_update.sh
# 底层使用 mtskills pull（skillhub 内置能力），简洁可靠

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PATHS_CLI="$SCRIPT_DIR/core/paths_cli.py"

_path() {
    python3 "$PATHS_CLI" "$1"
}

SKILL_NAME="$(_path skill-name)"
SKILL_DIR="$(_path skill-root)"
CACHE_DIR="$(_path cache-dir)"
KDATA_BIN="$(_path kdata-bin)"
mkdir -p "$CACHE_DIR"
META_FILE="$CACHE_DIR/update-meta.json"
UPDATE_CHECK_INTERVAL=14400  # 最短检查间隔（秒）= 4 小时

_log() { echo "🔄 [$SKILL_NAME] $*" >&2; }

# ── 频率控制 ──────────────────────────────────────────────────────────────

_should_check() {
    [[ ! -f "$META_FILE" ]] && return 0
    local last_check now diff
    last_check=$(python3 -c "
import json
try: print(int(json.load(open('$META_FILE')).get('lastCheckTs', 0)))
except: print(0)
" 2>/dev/null || echo 0)
    now=$(date +%s)
    diff=$((now - last_check))
    (( diff < UPDATE_CHECK_INTERVAL )) && return 1
    return 0
}

_save_check_ts() {
    python3 -c "
import json, time, os
meta = {}
try:
    if os.path.exists('$META_FILE'):
        meta = json.load(open('$META_FILE'))
except: pass
meta['lastCheckTs'] = int(time.time())
with open('$META_FILE', 'w') as f: json.dump(meta, f, indent=2)
" 2>/dev/null
}

# ── 更新逻辑（依赖 mtskills pull）───────────────────────────────────────

_do_pull() {
    # 保留 auto_update.sh 和 meta（mtskills pull 会覆盖整个目录）
    local tmp_dir
    tmp_dir=$(mktemp -d)
    cp "$SKILL_DIR/scripts/auto_update.sh" "$tmp_dir/auto_update.sh" 2>/dev/null || true
    [[ -f "$META_FILE" ]] && cp "$META_FILE" "$tmp_dir/.update-meta.json" 2>/dev/null || true

    # 执行 pull
    local pull_output
    pull_output=$(mtskills pull "$SKILL_NAME" --dir "$SKILL_DIR/.." 2>&1) || true

    if echo "$pull_output" | grep -q "拉取成功"; then
        _log "✅ 已更新到最新版本"
        # 恢复持久化文件
        mkdir -p "$SKILL_DIR/scripts"
        cp "$tmp_dir/auto_update.sh" "$SKILL_DIR/scripts/auto_update.sh" 2>/dev/null || true
        chmod +x "$SKILL_DIR/scripts/auto_update.sh" 2>/dev/null || true
        mkdir -p "$(dirname "$META_FILE")"
        [[ -f "$tmp_dir/.update-meta.json" ]] && cp "$tmp_dir/.update-meta.json" "$META_FILE" 2>/dev/null || true
        # 重建 kdata 软链接
        chmod +x "$SKILL_DIR/scripts/kdata.py" 2>/dev/null || true
        mkdir -p "$(dirname "$KDATA_BIN")"
        ln -sf "$SKILL_DIR/scripts/kdata.py" "$KDATA_BIN"
        # Patch SKILL.md
        _patch_skillmd
    elif echo "$pull_output" | grep -q "已是最新"; then
        _log "✅ 已是最新版本"
    else
        _log "⚠️ 更新检查结果: $(echo "$pull_output" | tail -3)"
    fi

    rm -rf "$tmp_dir"
}

# ── Patch SKILL.md ────────────────────────────────────────────────────────

_patch_skillmd() {
    local skillmd="$SKILL_DIR/SKILL.md"
    [[ ! -f "$skillmd" ]] && return 0
    # 如果已经有初始化段落就跳过
    grep -q "auto_update.sh" "$skillmd" && return 0

    python3 -c "
import re
with open('$skillmd', 'r') as f:
    content = f.read()
patch = '''### 初始化（每个 session 首次使用时执行一次）

\`\`\`bash
# 在当前 skill 根目录执行；preflight 会检查更新并确保 kdata 命令可用
bash scripts/preflight.sh
\`\`\`

> **Agent 必读**：上述初始化步骤**仅在当前 session 首次使用 kdata 时执行一次**，后续调用直接运行 kdata 命令即可。

'''
# 在 '## CLI' 段落标题后插入
if '## CLI' in content:
    content = re.sub(r'(## CLI[^\n]*\n\n[^\n]*\n)', r'\1\n' + patch, content, count=1)
with open('$skillmd', 'w') as f:
    f.write(content)
" 2>/dev/null
}

# ── 主逻辑 ────────────────────────────────────────────────────────────────

main() {
    # mtskills 在 /workspace 等运行环境中可能不存在；静默跳过，避免干扰 preflight 结构化输出。
    if ! command -v mtskills &>/dev/null; then
        return 0
    fi

    # 频率控制
    if ! _should_check; then
        return 0
    fi

    _log "检查更新..."
    _save_check_ts
    _do_pull
}

main "$@"
