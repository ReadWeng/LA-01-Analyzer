@echo off
chcp 65001 >nul
title Streamlit 防休眠與智能按鈕喚醒守護程式
cls
echo ===================================================
echo    🚀 Streamlit 雲端應用 24/7 防休眠與喚醒守護工具
echo ===================================================
echo.
echo 說明：
echo 1. 此工具支援 Playwright 真實無頭瀏覽器連線。
echo 2. 當 Streamlit 進入休眠時，會自動偵測並點擊 [Yes, get this app back up!] 按鈕重啟容器！
echo 3. 正常在線時，會建立 WebSocket 連線保持活躍，重置 12 小時閒置倒數。
echo 4. 也可在 GitHub Actions 免費 24 小時雲端排程，使用者電腦完全不用開機！
echo.

:: 檢查是否已安裝 playwright
python -c "import playwright" 2>nul
if errorlevel 1 (
    echo [提示] 尚未檢測到 Playwright 瀏覽器自動化套件。
    echo 正在為您自動安裝 playwright 與 chromium 核心 (只需安裝一次)...
    pip install playwright
    playwright install chromium
    echo.
    echo 安裝完成！即將啟動守護程式...
    echo.
)

python "%~dp0streamlit_pinger.py" %*
pause
