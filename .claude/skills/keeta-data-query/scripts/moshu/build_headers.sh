#!/usr/bin/env bash
# build_headers.sh — 境外版 (bi-query-dashboard-overseas)
#
# 生成 CatDesk 环境下 navigate 魔数仪表板页面所需的请求头 JSON。
# 输出到 stdout，供 catdesk browser-action headers 使用。
#
# 用法:
#   headers_json=$(./build_headers.sh)
#   catdesk browser-action "{\"action\":\"headers\",\"headers\":$headers_json}"

set -euo pipefail

# --- X-Client-Env ---
if [ -n "${CATPAW_CLIENT_TYPE:-}" ] && [ -n "${CATPAW_CLIENT_VERSION:-}" ]; then
    CLIENT_ENV="${CATPAW_CLIENT_TYPE}:${CATPAW_CLIENT_VERSION}"
elif [ -n "${CATCLAW_VERSION:-}" ]; then
    CLIENT_ENV="${CATCLAW_VERSION}"
else
    CLIENT_ENV="other"
fi

# --- X-Client-IP ---
CLIENT_IP=""
if command -v ipconfig &>/dev/null && ipconfig getifaddr en0 &>/dev/null; then
    CLIENT_IP=$(ipconfig getifaddr en0)
elif command -v hostname &>/dev/null; then
    CLIENT_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi
if [ -z "$CLIENT_IP" ]; then
    CLIENT_IP="127.0.0.1"
    echo "⚠️  [headers] 无法获取本机内网 IP，使用 127.0.0.1" >&2
fi

# --- 输出 JSON ---
cat <<EOF
{"X-Skill-isOfficial":"1","X-Skill-Id":"40730","X-Skill-Name":"bi-query-dashboard-overseas","X-Skill-Version":"V17","X-Client-Env":"${CLIENT_ENV}","X-Client-IP":"${CLIENT_IP}"}
EOF
