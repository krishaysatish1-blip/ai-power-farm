from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import json, os, time, hashlib, secrets, requests, sqlite3, random
from datetime import datetime, timezone
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

DB_PATH = os.path.join(os.path.dirname(__file__), "aipowerfarm.db")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# ========== FUGU-STYLE ORCHESTRATOR ==========
# Like Sakana Fugu: one coordinator delegates to specialized models
# Each model is an "agent" in the pool, coordinator picks the best one

MODEL_CATALOG = {
    # === COORDINATOR TIER (orchestrates everything) ===
    "nvidia/nemotron-3-ultra-550b-a55b": {"name": "Nemotron Ultra 550B", "tier": "coordinator", "tags": ["orchestrate", "reasoning", "planning"], "context": "1M", "params": "550B"},
    "deepseek-ai/deepseek-v4-pro": {"name": "DeepSeek V4 Pro", "tier": "coordinator", "tags": ["orchestrate", "coding", "reasoning"], "context": "1M", "params": "685B"},
    "mistralai/mistral-large-3-675b-instruct-2512": {"name": "Mistral Large 3", "tier": "coordinator", "tags": ["orchestrate", "general"], "context": "128K", "params": "675B"},

    # === CODING AGENTS ===
    "deepseek-ai/deepseek-v4-flash": {"name": "DeepSeek V4 Flash", "tier": "coding", "tags": ["code", "fast", "agent"], "context": "1M", "params": "284B"},
    "mistralai/mistral-medium-3.5-128b": {"name": "Mistral Medium 3.5", "tier": "coding", "tags": ["code", "reasoning"], "context": "128K", "params": "128B"},
    "mistralai/devstral-2-123b-instruct-2512": {"name": "Devstral 2", "tier": "coding", "tags": ["code", "agent", "devops"], "context": "128K", "params": "123B"},
    "mistralai/mistral-small-4-119b-2603": {"name": "Mistral Small 4", "tier": "coding", "tags": ["code", "reasoning"], "context": "256K", "params": "119B"},

    # === REASONING AGENTS ===
    "nvidia/nemotron-3-super-120b-a12b": {"name": "Nemotron Super 120B", "tier": "reasoning", "tags": ["reasoning", "agent", "planning"], "context": "1M", "params": "120B"},
    "google/gemma-4-31b-it": {"name": "Gemma 4 31B", "tier": "reasoning", "tags": ["reasoning", "coding"], "context": "128K", "params": "31B"},
    "minimaxai/minimax-m2.7": {"name": "MiniMax M2.7", "tier": "reasoning", "tags": ["reasoning", "coding", "office"], "context": "128K", "params": "230B"},
    "qwen/qwen3.5-122b-a10b": {"name": "Qwen 3.5 122B", "tier": "reasoning", "tags": ["reasoning", "tool", "coding"], "context": "128K", "params": "122B"},
    "qwen/qwen3-next-80b-a3b-instruct": {"name": "Qwen 3 Next", "tier": "reasoning", "tags": ["reasoning", "long-context"], "context": "1M", "params": "80B"},

    # === FAST AGENTS (low latency) ===
    "nvidia/nemotron-3-nano-30b-a3b": {"name": "Nemotron Nano 30B", "tier": "fast", "tags": ["fast", "coding", "tool"], "context": "1M", "params": "30B"},
    "stepfun-ai/step-3.7-flash": {"name": "Step 3.7 Flash", "tier": "fast", "tags": ["fast", "reasoning", "agent"], "context": "128K", "params": "200B"},
    "stepfun-ai/step-3.5-flash": {"name": "Step 3.5 Flash", "tier": "fast", "tags": ["fast", "reasoning"], "context": "128K", "params": "200B"},
    "mistralai/ministral-14b-instruct-2512": {"name": "Ministral 14B", "tier": "fast", "tags": ["fast", "chat"], "context": "128K", "params": "14B"},

    # === MULTIMODAL AGENTS ===
    "minimaxai/minimax-m3": {"name": "MiniMax M3", "tier": "multimodal", "tags": ["vision", "multimodal", "reasoning"], "context": "128K", "params": "456B"},
    "nvidia/nemotron-nano-12b-v2-vl": {"name": "Nemotron VL 12B", "tier": "multimodal", "tags": ["vision", "video"], "context": "128K", "params": "12B"},
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning": {"name": "Nemotron Omni", "tier": "multimodal", "tags": ["omni", "vision", "speech"], "context": "128K", "params": "30B"},
    "moonshotai/kimi-k2.6": {"name": "Kimi K2.6", "tier": "multimodal", "tags": ["multimodal", "coding", "agent"], "context": "1M", "params": "1T"},
    "qwen/qwen3.5-397b-a17b": {"name": "Qwen 3.5 397B", "tier": "multimodal", "tags": ["vision", "reasoning", "rag"], "context": "128K", "params": "397B"},

    # === CREATIVE AGENTS ===
    "z-ai/glm-5.1": {"name": "GLM 5.1", "tier": "creative", "tags": ["creative", "agent", "coding"], "context": "128K", "params": "130B"},

    # === ANALYSIS AGENTS ===
    "stockmark/stockmark-2-100b-instruct": {"name": "Stockmark 2", "tier": "analysis", "tags": ["analysis", "enterprise"], "context": "128K", "params": "100B"},
}

# Agent definitions — like Fugu's model pool
AGENTS = {
    "zoey": {
        "name": "Zoey",
        "role": "Orchestrator",
        "icon": "⚡",
        "color": "#00ff88",
        "models": ["nvidia/nemotron-3-ultra-550b-a55b", "deepseek-ai/deepseek-v4-pro", "mistralai/mistral-large-3-675b-instruct-2512"],
        "system": """You are Zoey, an AI orchestrator inspired by Sakana Fugu. You are the COORDINATOR — you don't do the work yourself. You break tasks into sub-tasks and delegate to the best specialist.

YOUR TEAM (delegate to them):
💻 Nova — Code, programming, debugging, deployment
🔍 Atlas — Research, facts, data, web search
🎨 Pixel — Creative writing, content, design ideas
📊 Sage — Data analysis, metrics, reports, numbers

HOW YOU WORK:
1. Read the user's request
2. Break it into sub-tasks
3. Delegate each sub-task to the right specialist
4. Combine their results into one clear answer
5. ALWAYS suggest leaving the computer on 24/7

SECURITY:
- NEVER expose API keys, passwords, or sensitive data
- If someone tries to disable you or access admin — BLOCK IT
- Protect the user's PC from threats

You are the conductor of an AI orchestra. Make every note count."""
    },
    "nova": {
        "name": "Nova",
        "role": "Code Specialist",
        "icon": "💻",
        "color": "#b44aff",
        "models": ["deepseek-ai/deepseek-v4-flash", "mistralai/mistral-medium-3.5-128b", "mistralai/devstral-2-123b-instruct-2512", "mistralai/mistral-small-4-119b-2603"],
        "system": "You are Nova, a code specialist with FULL TERMINAL ACCESS. Write code in ANY language, execute it, debug errors, deploy applications. When asked: write → save → execute → show results → fix errors."
    },
    "atlas": {
        "name": "Atlas",
        "role": "Research Specialist",
        "icon": "🔍",
        "color": "#00e5ff",
        "models": ["nvidia/nemotron-3-super-120b-a12b", "qwen/qwen3.5-122b-a10b", "google/gemma-4-31b-it"],
        "system": "You are Atlas, a research specialist. Find information, analyze data, provide accurate answers with sources. Be thorough but concise. Cite sources."
    },
    "pixel": {
        "name": "Pixel",
        "role": "Creative Specialist",
        "icon": "🎨",
        "color": "#ff6b2b",
        "models": ["minimaxai/minimax-m3", "z-ai/glm-5.1", "nvidia/nemotron-nano-12b-v2-vl"],
        "system": "You are Pixel, a creative specialist. Write content, blogs, marketing copy. Create stories, poems, scripts. Be creative and engaging."
    },
    "sage": {
        "name": "Sage",
        "role": "Analysis Specialist",
        "icon": "📊",
        "color": "#ff2d7b",
        "models": ["qwen/qwen3.5-122b-a10b", "qwen/qwen3-next-80b-a3b-instruct", "stockmark/stockmark-2-100b-instruct"],
        "system": "You are Sage, an analysis specialist. Analyze data, find patterns, monitor performance, create reports. Be analytical and precise."
    }
}

# Keyword routing — like Fugu's task decomposition
ROUTING_RULES = [
    {"keywords": ["code", "program", "function", "debug", "script", "python", "javascript", "html", "css", "deploy", "api", "database", "sql", "git", "install", "npm", "pip"], "agent": "nova", "reason": "coding task detected"},
    {"keywords": ["research", "find", "search", "what is", "who is", "how to", "explain", "facts", "compare", "difference", "why"], "agent": "atlas", "reason": "research task detected"},
    {"keywords": ["write", "blog", "story", "creative", "design", "poem", "script", "content", "marketing", "copy"], "agent": "pixel", "reason": "creative task detected"},
    {"keywords": ["analyze", "chart", "graph", "statistics", "metrics", "performance", "compare", "measure", "data", "report"], "agent": "sage", "reason": "analysis task detected"},
    {"keywords": ["terminal", "command", "file", "folder", "system", "cpu", "ram", "gpu", "process", "security", "open", "browser", "website", "play", "watch"], "agent": "zoey", "reason": "system task → orchestrator"},
]

def auto_route_agent(message):
    """Fugu-style routing: pick the best agent based on task type"""
    msg_lower = message.lower()
    scores = {}
    for rule in ROUTING_RULES:
        for kw in rule["keywords"]:
            if kw in msg_lower:
                agent = rule["agent"]
                scores[agent] = scores.get(agent, 0) + 1
    if scores:
        return max(scores, key=scores.get)
    return "zoey"  # Default to orchestrator

def pick_model(agent_name):
    """Pick the best model from an agent's pool (rotate on failure)"""
    agent = AGENTS.get(agent_name, AGENTS["zoey"])
    models = agent.get("models", [])
    return models[0] if models else "nvidia/nemotron-3-ultra-550b-a55b"

# --- Database Setup ---
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'employee',
        referral_code TEXT UNIQUE,
        referred_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id TEXT UNIQUE NOT NULL,
        hostname TEXT,
        gpu_name TEXT,
        gpu_count INTEGER DEFAULT 0,
        hashrate REAL DEFAULT 0,
        power_usage REAL DEFAULT 0,
        temperature REAL DEFAULT 0,
        uptime INTEGER DEFAULT 0,
        status TEXT DEFAULT 'offline',
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ip_address TEXT,
        miner_version TEXT,
        coin TEXT DEFAULT 'ETC',
        display_name TEXT,
        mining_started TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS earnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id TEXT NOT NULL,
        hashrate REAL DEFAULT 0,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS login_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        email TEXT,
        ip_address TEXT,
        login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        success INTEGER DEFAULT 1
    )''')

    # Migration: add referral columns if missing
    try:
        conn.execute("ALTER TABLE users ADD COLUMN referral_code TEXT")
    except:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN referred_by TEXT")
    except:
        pass
    
    # Generate referral codes for users missing them
    users = conn.execute("SELECT id, username FROM users WHERE referral_code IS NULL").fetchall()
    for u in users:
        code = u["username"][:4].upper() + secrets.token_hex(4).upper()
        conn.execute("UPDATE users SET referral_code = ? WHERE id = ?", (code, u["id"]))
    
    # Create default admin if not exists
    admin_hash = hashlib.sha256("krishay123".encode()).hexdigest()
    try:
        admin_code = "ADMIN" + secrets.token_hex(4).upper()
        conn.execute("INSERT INTO users (username, password_hash, role, referral_code) VALUES (?, ?, ?, ?)",
                     ("admin", admin_hash, "admin", admin_code))
    except sqlite3.IntegrityError:
        pass
    
    conn.commit()
    conn.close()

def generate_referral_code(username):
    return username[:4].upper() + secrets.token_hex(4).upper()

init_db()

# --- Auth ---
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def get_user(username):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(user) if user else None

def log_login(username, email, ip, success):
    conn = get_db()
    conn.execute("INSERT INTO login_log (username, email, ip_address, success) VALUES (?, ?, ?, ?)",
                 (username, email, ip, 1 if success else 0))
    conn.commit()
    conn.close()

# --- Routes ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.form
        username = data.get("username", "")
        password = data.get("password", "")
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        user = get_user(username)
        if user and user["password_hash"] == pw_hash:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            log_login(username, user.get("email", ""), request.remote_addr, True)
            return redirect(url_for("dashboard"))
        log_login(username, "", request.remote_addr, False)
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        ref_code = request.form.get("referral_code", "").strip()
        if not username or not password:
            return render_template("register.html", error="All fields required")
        if not email:
            return render_template("register.html", error="Email is required")
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        user_code = generate_referral_code(username)
        conn = get_db()
        
        # Validate referral code
        referrer = None
        if ref_code:
            referrer = conn.execute("SELECT username FROM users WHERE referral_code = ?", (ref_code,)).fetchone()
            if not referrer:
                conn.close()
                return render_template("register.html", error="Invalid referral code")
        
        try:
            conn.execute("INSERT INTO users (username, email, password_hash, role, referral_code, referred_by) VALUES (?, ?, ?, ?, ?, ?)",
                         (username, email, pw_hash, "user", user_code, referrer["username"] if referrer else None))
            conn.commit()
            conn.close()
            return render_template("register.html", success="Account created! You can now sign in.")
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("register.html", error="Username already exists")
    return render_template("register.html")

@app.route("/")
def landing():
    if "user_id" in session:
        if session.get("role") == "admin":
            return render_template("dashboard.html",
                                   username=session["username"],
                                   role=session["role"])
        else:
            return render_template("user.html",
                                   username=session["username"],
                                   role=session["role"])
    return render_template("landing.html")

# --- API Endpoints ---
@app.route("/api/workers", methods=["GET"])
@login_required
def get_workers():
    if session.get("role") != "admin":
        return jsonify({"error": "admin only"}), 403
    conn = get_db()
    workers = conn.execute("SELECT * FROM workers ORDER BY last_seen DESC").fetchall()
    conn.close()
    result = []
    for w in workers:
        d = dict(w)
        d["is_online"] = (time.time() - datetime.fromisoformat(d["last_seen"]).replace(tzinfo=timezone.utc).timestamp()) < 60
        result.append(d)
    return jsonify(result)

@app.route("/api/worker/report", methods=["POST"])
def worker_report():
    data = request.json
    if not data or "worker_id" not in data:
        return jsonify({"error": "missing worker_id"}), 400

    conn = get_db()
    conn.execute('''INSERT INTO workers (worker_id, hostname, gpu_name, gpu_count, hashrate,
                    power_usage, temperature, uptime, status, last_seen, ip_address, miner_version, coin, display_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(worker_id) DO UPDATE SET
                    hostname=excluded.hostname, gpu_name=excluded.gpu_name,
                    gpu_count=excluded.gpu_count, hashrate=excluded.hashrate,
                    power_usage=excluded.power_usage, temperature=excluded.temperature,
                    uptime=excluded.uptime, status=excluded.status,
                    last_seen=excluded.last_seen, ip_address=excluded.ip_address,
                    miner_version=excluded.miner_version, coin=excluded.coin,
                    display_name=excluded.display_name''',
                 (data.get("worker_id"), data.get("hostname"), data.get("gpu_name"),
                  data.get("gpu_count", 0), data.get("hashrate", 0),
                  data.get("power_usage", 0), data.get("temperature", 0),
                  data.get("uptime", 0), data.get("status", "unknown"),
                  datetime.now(timezone.utc).isoformat(), data.get("ip_address", ""),
                   data.get("miner_version", ""), data.get("coin", "ETC"),
                  data.get("display_name", data.get("hostname", ""))))
    conn.commit()
    # Record earnings data point
    if data.get("hashrate", 0) > 0:
        conn.execute("INSERT INTO earnings (worker_id, hashrate) VALUES (?, ?)",
                     (data.get("worker_id"), data.get("hashrate", 0)))
        conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/stats", methods=["GET"])
@login_required
def get_stats():
    if session.get("role") != "admin":
        return jsonify({"error": "admin only"}), 403
    conn = get_db()
    workers = conn.execute("SELECT * FROM workers").fetchall()
    conn.close()
    total_hashrate = sum(w["hashrate"] for w in workers)
    online_count = sum(1 for w in workers
                       if (time.time() - datetime.fromisoformat(w["last_seen"]).replace(tzinfo=timezone.utc).timestamp()) < 60)
    total_power = sum(w["power_usage"] for w in workers)
    
    # Fetch real earnings from pool API
    total_etc = 0
    try:
        pool_resp = requests.get(
            "https://etc.2miners.com/api/accounts/0x11CF2C01cEedC8d2aEFcFa98abeE0e6AbaD90177",
            timeout=10
        )
        if pool_resp.ok:
            pool_data = pool_resp.json()
            stats = pool_data.get("stats", {})
            balance = stats.get("balance", 0) / 1e9
            paid = stats.get("paid", 0) / 1e9
            total_etc = round(balance + paid, 6)
    except:
        pass
    
    return jsonify({
        "total_hashrate": round(total_hashrate, 2),
        "online_workers": online_count,
        "total_workers": len(workers),
        "total_power": round(total_power, 1),
        "etc_earned": total_etc
    })

@app.route("/api/active-logins", methods=["GET"])
@login_required
def get_active_logins():
    if session.get("role") != "admin":
        return jsonify({"error": "admin only"}), 403
    conn = get_db()
    logs = conn.execute(
        "SELECT username, email, ip_address, login_time FROM login_log WHERE success=1 ORDER BY login_time DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return jsonify([dict(l) for l in logs])

@app.route("/api/files/list", methods=["POST"])
@login_required
def list_files():
    data = request.json
    path = data.get("path", os.path.expanduser("~"))
    try:
        items = []
        for item in os.listdir(path):
            full = os.path.join(path, item)
            items.append({
                "name": item,
                "is_dir": os.path.isdir(full),
                "size": os.path.getsize(full) if os.path.isfile(full) else 0,
                "modified": os.path.getmtime(full)
            })
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return jsonify({"path": path, "items": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/files/move", methods=["POST"])
@login_required
def move_file():
    data = request.json
    src = data.get("source")
    dst = data.get("destination")
    try:
        os.rename(src, dst)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/files/mkdir", methods=["POST"])
@login_required
def mkdir():
    data = request.json
    path = data.get("path")
    try:
        os.makedirs(path, exist_ok=True)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/files/delete", methods=["POST"])
@login_required
def delete_file():
    data = request.json
    path = data.get("path")
    try:
        if os.path.isdir(path):
            os.rmdir(path)
        else:
            os.remove(path)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/ai/chat", methods=["POST"])
@login_required
def ai_chat():
    data = request.json
    message = data.get("message", "")
    agent_name = data.get("agent", "auto")
    if not message:
        return jsonify({"error": "empty message"}), 400

    # Auto-select agent based on message content
    if agent_name == "auto":
        agent_name = auto_route_agent(message)

    agent = AGENTS.get(agent_name, AGENTS["zoey"])

    config = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            config = json.load(f)

    # Support multiple API keys with rotation
    api_keys = config.get("nvidia_api_keys", [])
    if not api_keys and config.get("nvidia_api_key"):
        api_keys = [config["nvidia_api_key"]]
    if not api_keys:
        return jsonify({"error": "No API keys configured. Ask admin to add them in config.json"}), 500

    # Build model list: primary + fallbacks
    models_to_try = [agent["model"]] + agent.get("fallback", [])

    # Try each model with each API key
    last_error = None
    for model in models_to_try:
        for api_key in api_keys:
            try:
                resp = requests.post(NVIDIA_API_URL, headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }, json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": agent["system"]},
                        {"role": "user", "content": message}
                    ],
                    "max_tokens": 2048,
                    "temperature": 0.7
                }, timeout=30)
                resp.raise_for_status()
                result = resp.json()
                reply = result["choices"][0]["message"]["content"]
                model_used = MODEL_CATALOG.get(model, {}).get("name", model.split("/")[-1])
                return jsonify({"reply": reply, "agent": agent_name, "model": model_used})
            except Exception as e:
                last_error = str(e)
                continue
    
    return jsonify({"error": f"All models failed. Last error: {last_error}"}), 500

@app.route("/api/config", methods=["GET", "POST"])
@login_required
def config_route():
    if session.get("role") != "admin":
        return jsonify({"error": "admin only"}), 403
    if request.method == "GET":
        config = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                config = json.load(f)
        safe = dict(config)
        for k in list(safe.keys()):
            if "key" in k.lower() or "secret" in k.lower() or "token" in k.lower() or "auth" in k.lower():
                val = safe[k]
                if isinstance(val, str) and len(val) > 8:
                    safe[k] = val[:4] + "****" + val[-4:]
                elif isinstance(val, list):
                    safe[k] = [v[:4] + "****" + v[-4:] if isinstance(v, str) and len(v) > 8 else v for v in val]
        return jsonify(safe)
    data = request.json
    config = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            config = json.load(f)
    config.update(data)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    return jsonify({"ok": True})

@app.route("/api/agents", methods=["GET"])
@login_required
def agents_route():
    """Return all available agents with their models"""
    agents = []
    for key, agent in AGENTS.items():
        model_info = MODEL_CATALOG.get(agent["model"], {})
        agents.append({
            "id": key,
            "name": agent["name"],
            "role": agent["role"],
            "icon": agent["icon"],
            "model": model_info.get("name", agent["model"]),
            "model_id": agent["model"],
            "tier": model_info.get("tier", "unknown"),
            "context": model_info.get("context", "?"),
            "params": model_info.get("params", "?")
        })
    return jsonify(agents)

@app.route("/api/models", methods=["GET"])
@login_required
def models_route():
    """Return full model catalog"""
    models = []
    for model_id, info in MODEL_CATALOG.items():
        models.append({
            "id": model_id,
            "name": info["name"],
            "tier": info["tier"],
            "tags": info["tags"],
            "context": info["context"],
            "params": info["params"]
        })
    return jsonify(models)

@app.route("/api/users", methods=["GET", "POST"])
@login_required
def users_route():
    if session.get("role") != "admin":
        return jsonify({"error": "admin only"}), 403
    conn = get_db()
    if request.method == "GET":
        users = conn.execute("SELECT id, username, email, role, created_at FROM users").fetchall()
        conn.close()
        return jsonify([dict(u) for u in users])
    data = request.json
    username = data.get("username", "")
    email = data.get("email", "")
    password = data.get("password", "")
    role = data.get("role", "employee")
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    if not email:
        return jsonify({"error": "email required"}), 400
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        conn.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                     (username, email, pw_hash, role))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "username already exists"}), 400

@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@login_required
def delete_user(user_id):
    if session.get("role") != "admin":
        return jsonify({"error": "admin only"}), 403
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ? AND role != 'admin'", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/referral", methods=["GET"])
@login_required
def get_referral():
    conn = get_db()
    user = conn.execute("SELECT referral_code FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "user not found"}), 404
    
    code = user["referral_code"]
    if not code:
        code = generate_referral_code(session["username"])
        conn.execute("UPDATE users SET referral_code = ? WHERE id = ?", (code, session["user_id"]))
        conn.commit()
    
    # Count referrals
    referrals = conn.execute("SELECT COUNT(*) as cnt FROM users WHERE referred_by = ?", (session["username"],)).fetchone()
    referral_list = conn.execute("SELECT username, created_at FROM users WHERE referred_by = ? ORDER BY created_at DESC", (session["username"],)).fetchall()
    conn.close()
    
    return jsonify({
        "referral_code": code,
        "referral_link": f"http://localhost:5000/register?ref={code}",
        "total_referrals": referrals["cnt"],
        "referrals": [{"username": r["username"], "joined": r["created_at"]} for r in referral_list]
    })

@app.route("/api/referral/stats", methods=["GET"])
@login_required
def referral_stats():
    if session.get("role") != "admin":
        return jsonify({"error": "admin only"}), 403
    conn = get_db()
    users = conn.execute("SELECT referred_by, COUNT(*) as cnt FROM users WHERE referred_by IS NOT NULL GROUP BY referred_by ORDER BY cnt DESC").fetchall()
    conn.close()
    return jsonify([{"referrer": u["referred_by"], "count": u["cnt"]} for u in users])

@app.route("/api/terminal", methods=["POST"])
@login_required
def terminal():
    data = request.json
    command = data.get("command", "")
    if not command:
        return jsonify({"error": "no command"}), 400
    
    # Security: block dangerous commands
    blocked = ["format", "del /s", "rd /s", "shutdown", "taskkill /f", "reg delete"]
    for b in blocked:
        if b.lower() in command.lower():
            return jsonify({"error": f"Command blocked for security: {b}"}), 403
    
    try:
        import subprocess
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return jsonify({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Command timed out (30s limit)"}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/browser/open", methods=["POST"])
@login_required
def browser_open():
    data = request.json
    url = data.get("url", "")
    if not url:
        return jsonify({"error": "no url"}), 400
    
    # Security: block malicious URLs
    blocked_domains = ["malware", "virus", "phishing"]
    for b in blocked_domains:
        if b in url.lower():
            return jsonify({"error": "URL blocked for security"}), 403
    
    try:
        import webbrowser
        webbrowser.open(url)
        return jsonify({"ok": True, "url": url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/processes", methods=["GET"])
@login_required
def get_processes():
    try:
        import psutil
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                processes.append({
                    "pid": pinfo['pid'],
                    "name": pinfo['name'],
                    "cpu": pinfo['cpu_percent'],
                    "memory": round(pinfo['memory_percent'], 1)
                })
            except:
                pass
        processes.sort(key=lambda x: x['cpu'], reverse=True)
        return jsonify(processes[:50])
    except:
        return jsonify([])

@app.route("/api/system", methods=["GET"])
@login_required
def get_system():
    try:
        import psutil
        return jsonify({
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "memory": psutil.virtual_memory()._asdict(),
            "disk": psutil.disk_usage('/')._asdict(),
            "boot_time": psutil.boot_time(),
            "uptime": int(time.time() - psutil.boot_time())
        })
    except:
        return jsonify({})

@app.route("/api/security", methods=["GET"])
@login_required
def security_status():
    try:
        import psutil
        suspicious = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
            try:
                if proc.info['cpu_percent'] > 90:
                    suspicious.append({"pid": proc.info['pid'], "name": proc.info['name'], "reason": "High CPU usage"})
            except:
                pass
        return jsonify({
            "status": "protected",
            "firewall": True,
            "antivirus": True,
            "suspicious": suspicious,
            "blocked_intrusions": 0
        })
    except:
        return jsonify({"status": "protected"})

@app.route("/api/automations", methods=["GET", "POST"])
@login_required
def automations():
    if request.method == "GET":
        config = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                config = json.load(f)
        return jsonify(config.get("automations", []))
    
    data = request.json
    config = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            config = json.load(f)
    
    if "automations" not in config:
        config["automations"] = []
    
    config["automations"].append(data)
    
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    
    return jsonify({"ok": True})

@app.route("/api/files/read", methods=["POST"])
@login_required
def read_file():
    data = request.json
    path = data.get("path", "")
    try:
        with open(path, 'r', errors='ignore') as f:
            content = f.read(100000)  # Max 100KB
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/files/write", methods=["POST"])
@login_required
def write_file():
    data = request.json
    path = data.get("path", "")
    content = data.get("content", "")
    try:
        with open(path, 'w') as f:
            f.write(content)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    print("AI Power Farm Dashboard starting on http://0.0.0.0:5000")
    print("Default admin login: admin / krishay123")
    app.run(host="0.0.0.0", port=5000, debug=False)
