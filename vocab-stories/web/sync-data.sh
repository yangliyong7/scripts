#!/usr/bin/env bash
# 从上级 data/ 同步词表到 web/data/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB="$(cd "$(dirname "$0")" && pwd)"
cp -f "$ROOT/data/units.json" "$WEB/data/units.json"
cp -f "$ROOT/data/word_to_unit.json" "$WEB/data/word_to_unit.json" 2>/dev/null || true
echo "已同步 units.json（及 word_to_unit.json）"
