#!/bin/sh
# 每次更新代码时自动把 sentence.txt 的例句同步进 vocab/encyclopedia.html
#
# 由 git hooks (post-merge / post-checkout / pre-commit) 与 deploy_vocab.sh 调用，
# 也可手动执行:  sh tools/hooks/sync_sentences.sh
#
# 行为:
# - sentence.txt 或 encyclopedia.html 不存在 -> 安静跳过
# - 例句无变化 -> 什么都不做
# - 有变化 -> 覆盖写入 HTML 并提示
# - 任何失败都不阻断 git 操作（永远 exit 0），但会打印警告

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$ROOT" || exit 0

[ -f sentence.txt ] || exit 0
[ -f vocab/encyclopedia.html ] || exit 0

python3 tools/sync_sentences.py 2>&1 || \
  echo >&2 "[sync-sentences] 警告: 例句同步失败，已跳过（不影响本次 git 操作）"

exit 0
