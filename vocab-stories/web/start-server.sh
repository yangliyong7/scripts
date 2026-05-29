#!/usr/bin/env bash
# 本地预览静态站点（Linux / macOS）
# 生产环境请用 Nginx 托管本目录，不要长期用此脚本对外服务。

set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8080}"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "未找到 python3，请先安装 Python。" >&2
  exit 1
fi

echo "词库故事 · http://0.0.0.0:${PORT}"
echo "本机: http://127.0.0.1:${PORT}"
echo "按 Ctrl+C 停止"
exec "$PY" -m http.server "$PORT" --bind 0.0.0.0
