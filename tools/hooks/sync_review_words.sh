#!/bin/sh
# 每次更新代码时自动把 review.xlsx 的 A 列同步进 spelling-trainer.html
#
# 由 git hooks (post-merge / post-checkout / pre-commit) 调用，
# 也可手动执行:  sh tools/hooks/sync_review_words.sh
#
# 行为:
# - Excel 或 HTML 不存在 -> 安静跳过（不影响 git 操作）
# - 词表无变化 -> 什么都不做
# - 词表有变化 -> 覆盖写入 HTML 并提示
# - 任何失败都不阻断 git 操作（永远 exit 0），但会打印警告

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$ROOT" || exit 0

[ -f vocab/review.xlsx ] || exit 0
[ -f vocab/spelling-trainer.html ] || exit 0

python3 tools/sync_review_words.py 2>&1 || \
  echo >&2 "[sync-review] 警告: 词表同步失败，已跳过（不影响本次 git 操作）"

exit 0
