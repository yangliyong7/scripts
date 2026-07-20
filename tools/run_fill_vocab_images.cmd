@echo off
cd /d C:\Users\ICN00069\PycharmProjects\ReleasePlanCheck
set PYTHONUNBUFFERED=1
py -u -X utf8 generate_vocab_images.py --missing-only --root C:\Users\ICN00069\Downloads\scripts --delay 3 --rebuild-every 50
pause
