@echo off
cd /d C:\Users\ICN00069\PycharmProjects\ReleasePlanCheck
py build_vocab_data.py
cd /d C:\Users\ICN00069\Downloads\scripts\vocab
echo.
echo 数据已更新。启动本地服务：
echo   cd C:\Users\ICN00069\Downloads\scripts
echo   py -m http.server 8080
echo 浏览器打开: http://localhost:8080/vocab/
pause
