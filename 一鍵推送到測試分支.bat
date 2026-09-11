@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ===================================================
echo  LA-01 系統 - 一鍵推送到 GitHub 測試分支
echo ===================================================

python push_to_branch.py

if %errorlevel% neq 0 (
    echo.
    echo [提示] 執行過程遇到問題，請確認上方訊息。
    pause
)
