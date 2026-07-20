@echo off
setlocal
cd /d C:\Users\ICN00069\PycharmProjects\ReleasePlanCheck
echo 图片搜索下载（Bing，可选 GOOGLE_API_KEY+GOOGLE_CSE_ID）
py fetch_vocab_images_search.py --missing-only --engine auto --delay 1.5 %*
