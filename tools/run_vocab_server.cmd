@echo off
cd /d C:\Users\ICN00069\PycharmProjects\ReleasePlanCheck
echo 启动词汇学习页服务...
echo 浏览器打开: http://localhost:8080/vocab/
echo 按 Ctrl+C 停止
py -m http.server 8080 --directory "C:\Users\ICN00069\Downloads\scripts"
