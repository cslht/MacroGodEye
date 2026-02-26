@echo off
:: 切换编码防止乱码
chcp 65001 >nul
cd /d %~dp0

echo ------------------------------------------
echo 正在启动 (Activating qt environment)...
echo ------------------------------------------

:: 使用 call conda.bat activate
call conda.bat activate qt
if errorlevel 1 (
    call activate qt
)

echo.
echo 正在自动抓取数据并推送到飞书...
echo.

:: 运行 Python 推送脚本
python monitor_feishu.py

echo.
echo ==========================================
timeout /t 5
