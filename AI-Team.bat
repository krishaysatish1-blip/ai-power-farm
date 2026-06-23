@echo off
title AI Power Farm - Team Setup
color 0B
echo.
echo ============================================
echo         AI POWER FARM - TEAM INSTALLER
echo ============================================
echo.
echo This will set up your AI assistant.
echo It runs silently in the background.
echo.
echo Requirements:
echo   - Run as Administrator (right-click - Run as admin)
echo   - Internet connection
echo.
echo ============================================
echo.

:: Check admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Please run as Administrator!
    echo     Right-click this file - Run as administrator
    echo.
    pause
    exit /b 1
)

echo Starting setup...
echo.

:: Run the installer silently
powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0setup_config.ps1"

echo.
echo Setup complete! You can close this window.
echo.
timeout /t 3 >nul
