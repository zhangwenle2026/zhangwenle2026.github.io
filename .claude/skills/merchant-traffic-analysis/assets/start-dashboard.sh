#!/bin/bash
# 商家流量效果分析看板 - 一键启动脚本
# 用法：bash start-dashboard.sh
#
# Cookie 自动刷新：服务器启动时会自动从 catdesk 浏览器读取最新 Cookie
# 无需手动更新，Cookie 过期后重启服务器即可

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER="$DIR/bi-proxy-server.js"
SCRIPTS_DIR="$DIR/scripts"
KEETA_BI_PY="$SCRIPTS_DIR/keeta_bi_skill.py"
REQUIREMENTS="$SCRIPTS_DIR/requirements.txt"
PORT=7788
CATDESK="$HOME/.catpaw/bin/catdesk"

echo ""
echo "🚀 商家流量效果分析看板"
echo "────────────────────────────────────"

# 检查 Node.js
if ! command -v node &>/dev/null; then
  echo "❌ 未找到 Node.js，请先安装：https://nodejs.org"
  exit 1
fi

# 检查 catdesk
if [ ! -f "$CATDESK" ]; then
  echo "❌ 未找到 catdesk：$CATDESK"
  echo "   请确保 CatPaw Desk 已安装"
  exit 1
fi

# 检查 keeta-bi Python 依赖
if [ -f "$KEETA_BI_PY" ]; then
  echo "🐍 检查 keeta-bi Python 依赖..."
  PYTHON3_BIN=""
  for py in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    if command -v "$py" &>/dev/null 2>&1; then
      PYTHON3_BIN="$py"
      break
    fi
  done
  if [ -z "$PYTHON3_BIN" ]; then
    echo "⚠️  未找到 python3，keeta-bi 直连模式不可用（将回退到 mtdata 模式）"
  else
    # 检查核心依赖是否已安装
    if ! "$PYTHON3_BIN" -c "import requests, browser_cookie3" &>/dev/null 2>&1; then
      echo "📦 安装 keeta-bi 依赖（$REQUIREMENTS）..."
      "$PYTHON3_BIN" -m pip install -r "$REQUIREMENTS" -q && \
        echo "   ✅ 依赖安装完成" || \
        echo "   ⚠️  依赖安装失败，keeta-bi 直连模式可能不可用"
    else
      echo "   ✅ keeta-bi 依赖已就绪（$PYTHON3_BIN）"
    fi
  fi
else
  echo "⚠️  keeta_bi_skill.py 未找到，将使用 mtdata 模式"
fi

# 停止旧进程
if lsof -ti:$PORT &>/dev/null; then
  echo "⚠️  端口 $PORT 已被占用，正在停止旧进程..."
  lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
  sleep 1
fi

# 启动代理服务器（前台，输出日志）
# 服务器启动时会自动从浏览器读取最新 Cookie
echo "📡 启动代理服务器（端口 $PORT）..."
echo "   Cookie 将自动从 catdesk 浏览器读取，无需手动更新"
echo ""

# 等服务器打印"服务器已启动"后再开浏览器
node "$SERVER" &
SERVER_PID=$!

# 等待服务器就绪（最多 20 秒）
echo "⏳ 等待服务器就绪..."
for i in $(seq 1 20); do
  sleep 1
  if curl -sf "http://localhost:$PORT/" -o /dev/null 2>/dev/null; then
    break
  fi
  if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo "❌ 服务器启动失败，请检查日志"
    exit 1
  fi
done

# 打开看板
echo "🌐 打开看板：http://localhost:$PORT"
"$CATDESK" browser-action "{\"action\":\"navigate\",\"url\":\"http://localhost:$PORT\"}" &>/dev/null || \
  open "http://localhost:$PORT" 2>/dev/null || \
  echo "   请手动在浏览器中打开：http://localhost:$PORT"

echo ""
echo "✅ 看板已就绪：http://localhost:$PORT"
echo "   手动刷新 Cookie：http://localhost:$PORT/refresh-cookie"
echo "   按 Ctrl+C 停止服务器"
echo ""

# 等待 Ctrl+C
trap "echo ''; echo '🛑 停止服务器...'; kill $SERVER_PID 2>/dev/null; exit 0" INT
wait $SERVER_PID
