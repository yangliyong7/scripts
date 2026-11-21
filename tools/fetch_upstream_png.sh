#!/bin/bash
# 后台拉取上游 10f70e2 新增 PNG（partial-clone 单对象拉取）
# 策略：单次短超时 + 失败快跳过，多轮扫描，先拉能拉的，卡住的最后重试
set -u
META=/tmp/meta_clone
DONE_DIR=/root/.openclaw/workspace/scripts/.png_incoming
LOG=/tmp/fetchpng.progress
TARGET=10f70e2
NAMELIST=/tmp/pnglist.txt

mkdir -p "$DONE_DIR"
total=$(wc -l < "$NAMELIST")

get_oid() { GIT_DIR=$META/.git git rev-parse "$TARGET:$1" 2>/dev/null; }

# 单次尝试：25 秒超时，避免在一个对象上吊死
try_one() {
  local f="$1" oid="$2"
  local out="$DONE_DIR/$f"
  [ -s "$out" ] && return 0
  mkdir -p "$(dirname "$out")"
  rm -f "$out.tmp"
  if GIT_DIR=$META/.git timeout 25 git cat-file -p "$oid" > "$out.tmp" 2>/dev/null && [ -s "$out.tmp" ]; then
    mv "$out.tmp" "$out"; return 0
  fi
  rm -f "$out.tmp"; return 1
}

count_done() { find "$DONE_DIR" -name "*.png" -size +1k 2>/dev/null | wc -l; }

echo "START total=$total initial=$(count_done) $(date '+%F %T')" >> "$LOG"

for round in 1 2 3 4 5 6 7 8 9 10 11 12; do
  got=0; failed=0
  while read -r f; do
    [ -s "$DONE_DIR/$f" ] && continue
    oid=$(get_oid "$f")
    [ -z "$oid" ] && { failed=$((failed+1)); continue; }
    if try_one "$f" "$oid"; then
      got=$((got+1))
      echo "ROUND$round +$f done=$(count_done)/$total $(date '+%T')" >> "$LOG"
    else
      failed=$((failed+1))
    fi
  done < "$NAMELIST"
  echo "ROUND$round END got=$got failed=$failed done=$(count_done)/$total $(date '+%F %T')" >> "$LOG"
  [ "$failed" -eq 0 ] && break
  sleep 30
done

echo "DONE total=$(count_done)/$total $(date '+%F %T')" >> "$LOG"
