@echo off
chcp 65001 >nul
title Streamlit 防休眠保活守護程式
cls
echo ===================================================
echo    🚀 Streamlit 雲端應用防休眠保活守護工具
echo ===================================================
echo.
echo 說明：
echo 1. 此工具將定期向您的 Streamlit 網址發送保活探測。
echo 2. 若偵測到休眠狀態，將自動發送喚醒訊號。
echo 3. 請保持此視窗於背景執行，或使用 GitHub Actions 雲端免開機方案。
echo.
python "%~dp0streamlit_pinger.py" %*
pause
