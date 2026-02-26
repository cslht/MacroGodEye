@echo off
:: 切换编码防止乱码
chcp 65001 >nul
cd /d %~dp0

echo ------------------------------------------
echo 正在启动 (Activating qt environment)...
echo ------------------------------------------

:: 【修正点】根据报错提示，使用 call conda.bat activate
call conda.bat activate qt

:: 如果上面那句失败了，尝试旧版写法
if errorlevel 1 (
    call activate qt
)

echo.
echo 正在获取数据 (Running script)...
echo.

:: 运行 Python
python monitor_ashare.py

echo.
echo ==========================================
pause