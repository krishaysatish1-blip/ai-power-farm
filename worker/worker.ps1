# AI POWER FARM - WORKER AGENT
# Runs on employee PCs, reports status to main dashboard

param(
    [string]$ServerUrl = "http://127.0.0.1:5000"
)

$WORKER_ID = "$env:COMPUTERNAME"
$REPORT_INTERVAL = 30

function Get-GPUInfo {
    try {
        $gpus = Get-WmiObject Win32_VideoController | Where-Object { $_.Name -like "*NVIDIA*" -or $_.Name -like "*AMD*" -or $_.Name -like "*Radeon*" }
        if ($gpus) {
            $names = ($gpus | ForEach-Object { $_.Name }) -join ", "
            $count = $gpus.Count
            return @{ name = $names; count = $count }
        }
    } catch {}
    return @{ name = "Unknown GPU"; count = 0 }
}

function Get-MinerStatus {
    $processes = Get-Process -Name "lolMiner","nbminer","engine","miner","t-rex","gminer" -ErrorAction SilentlyContinue
    if ($processes) {
        return "mining"
    }
    return "idle"
}

function Get-Hashrate {
    # Estimate from GPU utilization (ETHW ~0.39 MH/s per 1% util on 5060 Ti)
    try {
        $util = & nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>$null
        if ($util) {
            $utilVal = [double]($util | Select-Object -First 1)
            if ($utilVal -gt 0) { return [math]::Round($utilVal * 0.39, 2) }
        }
    } catch {}
    # Fallback: try log files
    try {
        $logDir = "C:\ProgramData\AIPowerFarm\engine\logs"
        if (Test-Path $logDir) {
            $logFile = Get-ChildItem $logDir -Filter "*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
            if ($logFile) {
                $content = Get-Content $logFile.FullName -Tail 50
                $hashLine = $content | Where-Object { $_ -match "Speed|Hashrate|MH/s" } | Select-Object -Last 1
                if ($hashLine -match "([\d.]+)\s*M") { return [double]$Matches[1] }
            }
        }
    } catch {}
    return 0
}

function Get-GPUTemperature {
    try {
        $nvSmi = & nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>$null
        if ($nvSmi) { return [int]($nvSmi | Select-Object -First 1) }
    } catch {}
    return 0
}

function Get-GPUPower {
    try {
        $nvSmi = & nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits 2>$null
        if ($nvSmi) { return [double]($nvSmi | Select-Object -First 1) }
    } catch {}
    return 0
}

function Get-Uptime {
    $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
    return [int]((Get-Date) - $boot).TotalSeconds
}

Write-Host ""
Write-Host "  AI Power Farm Worker Agent" -ForegroundColor Cyan
Write-Host "  Reporting to: $ServerUrl" -ForegroundColor Gray
Write-Host ""

while ($true) {
    try {
        $gpu = Get-GPUInfo
        $status = Get-MinerStatus
        $hashrate = Get-Hashrate
        $temp = Get-GPUTemperature
        $power = Get-GPUPower
        $uptime = Get-Uptime
        $winUser = (Get-CimInstance Win32_ComputerSystem).UserName
        $displayName = if ($winUser -match "\\(.+)") { $Matches[1] } else { $env:COMPUTERNAME }

        $report = @{
            worker_id = $WORKER_ID
            hostname = $env:COMPUTERNAME
            display_name = $displayName
            gpu_name = $gpu.name
            gpu_count = $gpu.count
            hashrate = $hashrate
            power_usage = $power
            temperature = $temp
            uptime = $uptime
            status = $status
            ip_address = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" } | Select-Object -First 1).IPAddress
            miner_version = "Workstation Service v1.0"
            coin = "ETHW"
        } | ConvertTo-Json -Compress

        $response = Invoke-RestMethod -Uri "$ServerUrl/api/worker/report" -Method Post -Body $report -ContentType "application/json" -TimeoutSec 10
        Write-Host "  [$((Get-Date).ToString('HH:mm:ss'))] Reported - Hashrate: $hashrate MH/s - Status: $status" -ForegroundColor DarkGray
    } catch {
        Write-Host "  [$((Get-Date).ToString('HH:mm:ss'))] Connection error: $($_.Exception.Message)" -ForegroundColor Red
    }

    Start-Sleep -Seconds $REPORT_INTERVAL
}
