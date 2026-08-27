@echo off
echo ===================================================
echo  LA-01 System GitHub Auto Deploy Tool
echo ===================================================

git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [Error] Git not found! Please install Git.
    pause
    exit /b
)

set REPO_URL=https://github.com/ReadWeng/LA-01-Analyzer.git

if not exist .git (
    echo.
    echo [*] Initializing Git repository...
    git init
    git branch -M main
)

git remote remove origin >nul 2>&1
git remote add origin "%REPO_URL%"

:: Configure local git user to prevent "Author identity unknown" error
git config user.name "LA-01 Auto Deployer"
git config user.email "deploy@la01.local"

echo.
echo [*] Adding files to version control...
git add .

echo.
echo [*] Creating Commit...
git commit -m "Auto-deploy update: %date% %time%"

echo.
echo [*] Pushing to GitHub... (A browser window may pop up for login)
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo [Success] Your code has been successfully pushed to GitHub!
) else (
    echo.
    echo [Error] Push failed! Please check your network connection or GitHub permissions.
    echo Hint: You can open CMD in this folder and manually type 'git push -u origin main' to troubleshoot.
)

echo ===================================================
pause
