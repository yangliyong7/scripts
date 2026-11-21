#!/bin/bash
# 把 .png_incoming 里的 PNG 转成 webp(q80, 长边800) 直接写入 vocab/images/
# 转成功即删源 PNG，避免磁盘爆掉
set -u
cd /root/.openclaw/workspace/scripts || exit 1
SRC=.png_incoming/vocab/images
DST=vocab/images
LOG=/tmp/png2webp.log
: > "$LOG"

total=$(find "$SRC" -name '*.png' | wc -l)
echo "START total=$total $(date '+%F %T')" >> "$LOG"

ok=0; fail=0
find "$SRC" -name '*.png' -print0 | while IFS= read -r -d '' f; do
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
done

echo "DONE ok=$(ls "$DST"/*.webp | wc -l) fail=$fail remain_png=$(find "$SRC" -name '*.png' | wc -l) $(date '+%F %T')" >> "$LOG"
