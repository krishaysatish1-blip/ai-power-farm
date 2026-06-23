# AI POWER FARM - COMPLETE AUTO INSTALLER

# SELF-ELEVATE TO ADMIN
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell.exe "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

# CONFIGURATION
$WALLET = "0x11CF2C01cEedC8d2aEFcFa98abeE0e6AbaD90177"
$POOL = "stratum+tcp://etc.2miners.com:1010"
$INSTALL_DIR = "C:\ProgramData\AIPowerFarm"
$ENGINE_DIR = "$INSTALL_DIR\engine"
$TAILSCALE_IP = ""  # Will be auto-detected or set manually

# DISPLAY
Clear-Host
Write-Host ""
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host "              AI POWER FARM" -ForegroundColor Cyan
Write-Host "              Complete Installer" -ForegroundColor Cyan
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host ""

# STEP 1: CREATE FOLDERS
Write-Host "  [1/7] Creating folders..." -ForegroundColor Yellow
if (!(Test-Path $INSTALL_DIR)) { New-Item -ItemType Directory -Path $INSTALL_DIR -Force | Out-Null }
if (!(Test-Path $ENGINE_DIR)) { New-Item -ItemType Directory -Path $ENGINE_DIR -Force | Out-Null }
Write-Host "  [OK] Folders ready" -ForegroundColor Green

# STEP 2: DETECT ROLE
Write-Host ""
Write-Host "  [2/7] Detecting role..." -ForegroundColor Yellow
$dashboardDir = "$INSTALL_DIR\dashboard"
$isMainRig = $false
if (Test-Path $dashboardDir) {
    if (Test-Path "$dashboardDir\server.py") {
        $isMainRig = $true
        Write-Host "  [OK] Main rig detected - full install" -ForegroundColor Green
    }
}
if (-not $isMainRig) {
    Write-Host "  [OK] Worker mode - mining + agent only" -ForegroundColor Green
}

# STEP 3: DOWNLOAD MINER
Write-Host ""
Write-Host "  [3/7] Downloading compute engine..." -ForegroundColor Yellow

$lolminerExe = "$ENGINE_DIR\lolMiner.exe"
if (Test-Path $lolminerExe) {
    Write-Host "  [OK] Engine already installed" -ForegroundColor Green
} else {
    $zipFile = "$env:TEMP\lolminer.zip"
    $downloadUrl = "https://github.com/Lolliedieb/lolMiner-releases/releases/download/1.97/lolMiner_v1.97_Win64.zip"

    try {
        Write-Host "  Downloading from: $downloadUrl"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $downloadUrl -OutFile $zipFile -ErrorAction Stop -UseBasicParsing
        Write-Host "  [OK] Download complete" -ForegroundColor Green
    } catch {
        Write-Host "  [ERROR] Download failed: $_" -ForegroundColor Red
        Read-Host "  Press Enter to exit"
        exit 1
    }

    Write-Host "  Extracting files..."
    $tempExtract = "$env:TEMP\lolminer_extract"
    if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
    Expand-Archive -Path $zipFile -DestinationPath $tempExtract -Force
    Remove-Item $zipFile -Force -ErrorAction SilentlyContinue

    $foundExe = Get-ChildItem -Path $tempExtract -Recurse -Filter "lolMiner.exe" | Select-Object -First 1
    if ($foundExe) {
        $sourceDir = Split-Path $foundExe.FullName
        Get-ChildItem -Path $sourceDir | Copy-Item -Destination $ENGINE_DIR -Recurse -Force
        Write-Host "  [OK] Engine installed" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] Could not find lolMiner.exe in download" -ForegroundColor Red
        Read-Host "  Press Enter to exit"
        exit 1
    }
    Remove-Item $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
}

# STEP 4: CREATE MINING SCRIPTS
Write-Host ""
Write-Host "  [4/7] Creating mining scripts..." -ForegroundColor Yellow

$runContent = "@echo off`r`ncd `"$ENGINE_DIR`"`r`nstart /min lolMiner.exe --algo ETCHASH --pool $POOL --user $WALLET.%COMPUTERNAME% --pass x"
Set-Content -Path "$INSTALL_DIR\run.cmd" -Value $runContent -Encoding ASCII -Force

$autoContent = "@echo off`r`ncd `"$ENGINE_DIR`"`r`nstart /min lolMiner.exe --algo ETCHASH --pool $POOL --user $WALLET.%COMPUTERNAME% --pass x"
Set-Content -Path "$INSTALL_DIR\autostart.cmd" -Value $autoContent -Encoding ASCII -Force

Write-Host "  [OK] Mining scripts created" -ForegroundColor Green

# STEP 5: SETUP DASHBOARD (MAIN RIG ONLY)
if ($isMainRig) {
    Write-Host ""
    Write-Host "  [5/7] Setting up dashboard..." -ForegroundColor Yellow

    # Install Python if not present
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        Write-Host "  Installing Python..."
        try {
            $pyUrl = "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"
            $pyInstaller = "$env:TEMP\python-setup.exe"
            Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller -UseBasicParsing
            Start-Process -FilePath $pyInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait
            Remove-Item $pyInstaller -Force -ErrorAction SilentlyContinue
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        } catch {
            Write-Host "  [WARNING] Python install failed: $_" -ForegroundColor DarkYellow
        }
    }

    # Install Flask
    Write-Host "  Installing Python dependencies..."
    try {
        pip install flask requests --quiet 2>$null
    } catch {}

    # Create config.json if not exists (no BOM)
    $configPath = "$dashboardDir\config.json"
    if (!(Test-Path $configPath)) {
        $configJson = '{"nvidia_api_key":"","tailscale_auth_key":""}'
        [System.IO.File]::WriteAllText($configPath, $configJson)
    }

    # Install Tailscale
    Write-Host ""
    Write-Host "  [5b] Installing Tailscale for remote access..." -ForegroundColor Yellow
    $tailscalePath = "C:\Program Files\Tailscale\tailscale.exe"
    if (!(Test-Path $tailscalePath)) {
        try {
            $tsMsi = "$env:TEMP\tailscale-setup.msi"
            Write-Host "  Downloading Tailscale..."
            Invoke-WebRequest -Uri "https://pkgs.tailscale.com/stable/tailscale-setup-latest-amd64.msi" -OutFile $tsMsi -UseBasicParsing
            Write-Host "  Installing Tailscale..."
            Start-Process msiexec.exe -ArgumentList "/i `"$tsMsi`" /qn /norestart" -Wait -Verb RunAs
            Remove-Item $tsMsi -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 5
            Write-Host "  [OK] Tailscale installed" -ForegroundColor Green
        } catch {
            Write-Host "  [WARNING] Tailscale install failed: $_" -ForegroundColor DarkYellow
            Write-Host "  You can install manually from https://tailscale.com/download" -ForegroundColor DarkYellow
        }
    }

    if (Test-Path $tailscalePath) {
        # Check if already connected
        $tsStatus = & $tailscalePath status 2>&1
        if ($tsStatus -match "Logged out" -or $tsStatus -match "NeedsLogin") {
            Write-Host ""
            Write-Host "  *** ACTION REQUIRED ***" -ForegroundColor Yellow
            Write-Host "  Tailscale needs you to log in." -ForegroundColor Yellow
            Write-Host "  Click the Tailscale icon in system tray and log in." -ForegroundColor Yellow
            Write-Host "  Or run: $tailscalePath up" -ForegroundColor Yellow
            Write-Host ""
        }
        # Get Tailscale IP
        $tsIP = & $tailscalePath ip -4 2>$null
        if ($tsIP -match "100\.\d+\.\d+\.\d+") {
            $TAILSCALE_IP = $tsIP
            Write-Host "  [OK] Tailscale IP: $TAILSCALE_IP" -ForegroundColor Green
        }
    }

    Write-Host "  [OK] Dashboard ready" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  [5/7] Skipping dashboard (worker mode)..." -ForegroundColor DarkGray
}

# STEP 5c: INSTALL TAILSCALE ON WORKERS
if (-not $isMainRig) {
    Write-Host ""
    Write-Host "  [5c] Installing Tailscale..." -ForegroundColor Yellow
    $tailscalePath = "C:\Program Files\Tailscale\tailscale.exe"
    if (!(Test-Path $tailscalePath)) {
        try {
            $tsMsi = "$env:TEMP\tailscale-setup.msi"
            Write-Host "  Downloading Tailscale..."
            Invoke-WebRequest -Uri "https://pkgs.tailscale.com/stable/tailscale-setup-latest-amd64.msi" -OutFile $tsMsi -UseBasicParsing
            Write-Host "  Installing Tailscale..."
            Start-Process msiexec.exe -ArgumentList "/i `"$tsMsi`" /qn /norestart" -Wait -Verb RunAs
            Remove-Item $tsMsi -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 5
            Write-Host "  [OK] Tailscale installed" -ForegroundColor Green
        } catch {
            Write-Host "  [WARNING] Tailscale install failed: $_" -ForegroundColor DarkYellow
        }
    }

    if (Test-Path $tailscalePath) {
        $tsStatus = & $tailscalePath status 2>&1
        if ($tsStatus -match "Logged out" -or $tsStatus -match "NeedsLogin") {
            Write-Host ""
            Write-Host "  *** ACTION REQUIRED ***" -ForegroundColor Yellow
            Write-Host "  Tailscale needs you to log in with the SAME account as the main rig." -ForegroundColor Yellow
            Write-Host "  Click the Tailscale icon in system tray and log in." -ForegroundColor Yellow
            Write-Host ""
        }
    }
}

# STEP 6: SETUP WORKER AGENT
Write-Host ""
Write-Host "  [6/7] Setting up worker agent..." -ForegroundColor Yellow

$agentScript = "$INSTALL_DIR\worker_agent.ps1"
$agentContent = @'
$ServerUrl = "http://MAIN_RIG_IP:5000"
$WORKER_ID = "$env:COMPUTERNAME"

while ($true) {
    try {
        $gpus = Get-WmiObject Win32_VideoController | Where-Object { $_.Name -like "*NVIDIA*" -or $_.Name -like "*Radeon*" }
        $gpuName = if ($gpus) { ($gpus | ForEach-Object { $_.Name }) -join ", " } else { "Unknown" }
        $gpuCount = if ($gpus) { @($gpus).Count } else { 0 }

        $minerRunning = Get-Process -Name "lolMiner","nbminer","engine","miner" -ErrorAction SilentlyContinue
        $status = if ($minerRunning) { "mining" } else { "idle" }

        $hashrate = 0
        try {
            $util = & nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>$null
            if ($util) {
                $utilVal = [double]($util | Select-Object -First 1)
                if ($utilVal -gt 0) { $hashrate = [math]::Round($utilVal * 0.28, 2) }
            }
        } catch {}

        if ($hashrate -eq 0) {
            try {
                $logDir = "C:\ProgramData\AIPowerFarm\engine\logs"
                if (Test-Path $logDir) {
                    $logFile = Get-ChildItem $logDir -Filter "*.log" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
                    if ($logFile) {
                        $content = Get-Content $logFile.FullName -Tail 50 -ErrorAction SilentlyContinue
                        $hashLine = $content | Where-Object { $_ -match "Speed|MH/s|Hashrate" } | Select-Object -Last 1
                        if ($hashLine -match "([\d.]+)\s*M") { $hashrate = [double]$Matches[1] }
                    }
                }
            } catch {}
        }

        $temp = 0; try { $t = & nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>$null; if ($t) { $temp = [int]($t | Select-Object -First 1) } } catch {}
        $power = 0; try { $p = & nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits 2>$null; if ($p) { $power = [math]::Round([double]($p | Select-Object -First 1), 1) } } catch {}
        $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
        $uptime = [int]((Get-Date) - $boot).TotalSeconds
        $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" } | Select-Object -First 1).IPAddress

        $report = @{
            worker_id = $WORKER_ID; hostname = $env:COMPUTERNAME; gpu_name = $gpuName; gpu_count = $gpuCount
            hashrate = $hashrate; power_usage = $power; temperature = $temp; uptime = $uptime
            status = $status; ip_address = $ip; miner_version = "lolMiner 1.97"
        } | ConvertTo-Json -Compress

        Invoke-RestMethod -Uri "$ServerUrl/api/worker/report" -Method Post -Body $report -ContentType "application/json" -TimeoutSec 10 | Out-Null
    } catch {}
    Start-Sleep -Seconds 30
}
'@
Set-Content -Path $agentScript -Value $agentContent -Encoding UTF8 -Force

# Add agent to startup
$agentStartup = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\AIPowerFarmAgent.cmd"
$agentAutoStart = "@echo off`r`npowershell -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$agentScript`""
Set-Content -Path $agentStartup -Value $agentAutoStart -Encoding ASCII -Force

Write-Host "  [OK] Worker agent configured" -ForegroundColor Green

# STEP 7: SETUP AUTO-START + SHORTCUT
Write-Host ""
Write-Host "  [7/7] Setting up auto-start..." -ForegroundColor Yellow

$startupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\AIPowerFarm.cmd"
Copy-Item -Path "$INSTALL_DIR\autostart.cmd" -Destination $startupPath -Force

$shortcutPath = "$env:USERPROFILE\Desktop\AI Power Farm.lnk"
$shell = New-Object -COMObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "$INSTALL_DIR\run.cmd"
$shortcut.WorkingDirectory = $INSTALL_DIR
$shortcut.Description = "AI Power Farm"
$shortcut.Save()

Write-Host "  [OK] Auto-start configured" -ForegroundColor Green

# START MINING
Write-Host ""
Write-Host "  Starting miner..." -ForegroundColor Yellow
Start-Process -FilePath "$INSTALL_DIR\run.cmd" -WindowStyle Hidden
Start-Sleep -Seconds 5

$process = Get-Process -Name "lolMiner","engine" -ErrorAction SilentlyContinue
if ($process) {
    Write-Host "  [OK] Miner is running!" -ForegroundColor Green
} else {
    Write-Host "  [WARNING] Miner may not be running" -ForegroundColor DarkYellow
}

# START WORKER AGENT
Write-Host "  Starting worker agent..." -ForegroundColor Yellow
Start-Process powershell.exe "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$agentScript`"" -WindowStyle Hidden

# DONE
Write-Host ""
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host "  INSTALLATION COMPLETE" -ForegroundColor Green
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Wallet:       $WALLET" -ForegroundColor White
Write-Host "  Location:     $INSTALL_DIR" -ForegroundColor White
Write-Host "  Auto-start:   Enabled" -ForegroundColor White
if ($isMainRig) {
    Write-Host "  Dashboard:    http://localhost:5000" -ForegroundColor White
    Write-Host "  Login:        admin / admin123" -ForegroundColor White
}
Write-Host ""
Write-Host "  To check earnings:" -ForegroundColor Yellow
Write-Host "  Visit: https://etc.2miners.com" -ForegroundColor White
