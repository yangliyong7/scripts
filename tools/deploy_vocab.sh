#!/bin/sh
# 部署 vocab 站点到 /var/www/vocab/
#
# 用法:  sh tools/deploy_vocab.sh [文件名...]
#        不带参数 = 部署 spelling-trainer.html
#
# 部署前自动执行 review.xlsx -> REVIEW_WORDS 同步，
# 保证线上永远是「最新 Excel 词表 + 现有代码逻辑」。
# 部署后做 JS 语法检查，失败则不覆盖线上文件。

set -e

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || ROOT=$(pwd)
cd "$ROOT"

DEST=/var/www/vocab
FILES=${*:-spelling-trainer.html}

# 1) 先同步词表
echo "[deploy] 同步 review.xlsx 词表..."
sh tools/hooks/sync_review_words.sh

# 2) 只部署指定文件
for f in $FILES; do
  src="vocab/$f"
  if [ ! -f "$src" ]; then
    echo "[deploy] 跳过（不存在）: $src" >&2
    continue
  fi

  # 3) 单文件 HTML 先查 JS 语法
  case "$f" in
    *.html)
      tmp=$(mktemp /tmp/deployjs.XXXXXX.js)
      python3 - "$src" "$tmp" <<'PY'
import re, sys
html = open(sys.argv[1], encoding="utf-8").read()
blocks = re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)
open(sys.argv[2], "w", encoding="utf-8").write("\n".join(blocks))
PY
      if command -v node >/dev/null 2>&1; then
        if ! node --check "$tmp" 2>/dev/null; then
          echo "[deploy] JS 语法检查失败，已中止，线上文件未改动: $src" >&2
          rm -f "$tmp"
          exit 1
        fi
      fi
      rm -f "$tmp"
      ;;
  esac

  install -o www-data -g www-data -m 644 "$src" "$DEST/$f"
  echo "[deploy] 已部署 $src -> $DEST/$f"
done

# 4) 校验公开访问
if command -v curl >/dev/null 2>&1; then
  code=$(curl -s -o /dev/null -w '%{http_code}' http://www.easybuyvip.com/vocab/spelling-trainer.html || echo 000)
  echo "[deploy] 线上 HTTP $code"
fi
