# AI Power Farm

Crypto mining dashboard with AI chat and employee management.

## Quick Start

### Main Rig (Admin)
1. Download `AI-Power-Farm.bat`
2. Right-click → Run as Administrator
3. Wait for installation to complete
4. Dashboard opens at: `http://localhost:5000`
5. Login: `admin` / `admin123`

### Employee PCs
1. Download `AI-Team.bat`
2. Right-click → Run as Administrator
3. Everything installs automatically (mining + AI chat)
4. Access dashboard via browser: `http://YOUR_SERVER_IP:5000`

## Features

- **Dashboard** - Monitor workers, hashrate, earnings
- **AI Chat** - NVIDIA Nemotron Ultra powered assistant
- **Auto-Installer** - One-click setup on any PC
- **Employee Management** - Register, track activity
- **File Manager** - Organize files through AI chat

## Requirements

- Windows 10/11
- NVIDIA GPU (RTX series recommended)
- Internet connection

## Configuration

Edit `dashboard/config.json`:
```json
{
  "nvidia_api_key": "your_nvidia_api_key",
  "tailscale_auth_key": "your_tailscale_key"
}
```

## Default Login

- **Admin**: admin / admin123
- **Employees**: Register at `/register`

## Support

- Dashboard: http://localhost:5000
- Pool: https://ethw.2miners.com
- Wallet: Check `AI-Power-Farm.ps1` for current wallet address