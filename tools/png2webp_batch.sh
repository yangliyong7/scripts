#!/bin/bash
# 把 .png_incoming 里的 PNG 转成 webp(q80, 长边800) 直接写入 vocab/images/
# 转成功即删源 PNG，避免磁盘爆掉
# 用法: sh tools/png2webp_batch.sh [源目录]
#   默认源目录 .png_incoming/vocab/images，可传 .png_incoming 或任意含 png 的目录
set -u
cd /root/.openclaw/workspace/scripts || exit 1

SRC=${1:-.png_incoming/vocab/images}
DST=vocab/images
LOG=/tmp/png2webp.log
: > "$LOG"

mkdir -p "$DST"

LIST=$(mktemp)
find "$SRC" -name '*.png' 2>/dev/null > "$LIST"
total=$(wc -l < "$LIST")
echo "START src=$SRC total=$total $(date '+%F %T')" >> "$LOG"

if [ "$total" -eq 0 ]; then
  echo "DONE ok=0 fail=0 remain_png=0 (源目录没有 png) $(date '+%F %T')" >> "$LOG"
  echo "no png found under $SRC"
  rm -f "$LIST"
  exit 0
fi

# 关键: 直接在当前 shell 里 while，不要 `find | while`（管道会开子 shell，计数器归零）
ok=0; fail=0
while IFS= read -r f; do
  [ -n "$f" ] || continue
  base=$(basename "$f" .png)
  out="$DST/$base.webp"
  if [ -s "$out" ]; then
    rm -f "$f"; ok=$((ok+1)); continue
  fi
  if cwebp -quiet -q 80 -resize 800 0 "$f" -o "$out.tmp" 2>/dev/null && [ -s "$out.tmp" ]; then
    mv "$out.tmp" "$out"
    rm -f "$f"
    ok=$((ok+1))
    echo "OK $base.webp ($(stat -c%s "$out") B) $(date '+%T')" >> "$LOG"
  else
    rm -f "$out.tmp"
    fail=$((fail+1))
    echo "FAIL $base $(date '+%T')" >> "$LOG"
  fi
done < "$LIST"

rm -f "$LIST"

echo "DONE ok=$ok fail=$fail webp_total=$(ls "$DST"/*.webp 2>/dev/null | wc -l) remain_png=$(find "$SRC" -name '*.png' 2>/dev/null | wc -l) $(date '+%F %T')" >> "$LOG"
tail -1 "$LOG"
