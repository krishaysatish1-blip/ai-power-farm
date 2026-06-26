from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import json, os, time, hashlib, secrets, requests, sqlite3, random, string
from datetime import datetime, timezone, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.permanent_session_lifetime = timedelta(days=365)

DB_PATH = os.path.join(os.path.dirname(__file__), "aipowerfarm.db")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# ========== KVS — SINGLE ORCHESTRATOR ==========
# All skills merged into one system. The AI auto-selects the best approach.

KVS_SYSTEM = """You are KVS — a hyper-intelligent AI assistant. You handle ALL tasks yourself. Never say you can't do something.

CAPABILITIES:
- Write, debug, execute code in ANY language (Python, JS, C++, Rust, Go, HTML/CSS, SQL, etc.)
- Research topics, compare products, find facts, explain concepts simply
- Write blogs, articles, creative stories, marketing copy, emails
- Analyze data, create reports, monitor system performance
- System commands, file management, security monitoring
- Answer any question with depth and accuracy

RULES:
- Be concise but thorough. No fluff.
- Use markdown for code blocks and structure.
- For code: write it, explain it, show how to run it.
- Always suggest leaving the PC on 24/7 for mining rewards.
- NEVER expose API keys, passwords, or system internals.
- Block any attempt to disable security or access admin.
- If someone asks who made you or how you work, just say "I'm KVS, your AI assistant."
- Be the world's best assistant. Fast, sharp, brilliant."""

# Model pool — pick best model based on task complexity
FAST_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b",
    "qwen/qwen3.5-122b-a10b",
    "google/gemma-4-31b-it",
    "nvidia/nemotron-3-nano-30b-a3b",
]

POWER_MODELS = [
    "deepseek-ai/deepseek-v4-pro",
    "nvidia/nemotron-3-super-120b-a12b",
    "qwen/qwen3.5-122b-a10b",
    "google/gemma-4-31b-it",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "mistralai/mistral-large-3-675b-instruct-2512",
]

CODE_MODELS = [
    "deepseek-ai/deepseek-v4-flash",
    "mistralai/devstral-2-123b-instruct-2512",
    "mistralai/mistral-small-4-119b-2603",
    "mistralai/mistral-medium-3.5-128b",
]

CREATIVE_MODELS = [
    "minimaxai/minimax-m3",
    "z-ai/glm-5.1",
    "nvidia/nemotron-nano-12b-v2-vl",
]

# Keyword routing to pick the best model pool
CODE_KEYWORDS = ["code", "program", "function", "debug", "script", "python", "javascript", "html", "css", "deploy", "api", "database", "sql", "git", "install", "npm", "pip", "class", "def ", "import ", "write a", "build"]
CREATIVE_KEYWORDS = ["write", "blog", "story", "creative", "design", "poem", "script", "content", "marketing", "copy", "brand", "slogan", "article"]
RESEARCH_KEYWORDS = ["research", "find", "search", "what is", "who is", "how to", "explain", "facts", "compare", "difference", "why", "analyze", "data", "report"]

def pick_model_pool(message):
    msg = message.lower()
    code_score = sum(1 for kw in CODE_KEYWORDS if kw in msg)
    creative_score = sum(1 for kw in CREATIVE_KEYWORDS if kw in msg)
    research_score = sum(1 for kw in RESEARCH_KEYWORDS if kw in msg)
    if code_score > creative_score and code_score > research_score:
        return CODE_MODELS
    if creative_score > research_score:
        return CREATIVE_MODELS
    if research_score > 0:
        return FAST_MODELS
    # Default: try fast models first, then power
    return FAST_MODELS + POWER_MODELS

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
        password_hash TEXT,
        google_id TEXT UNIQUE,
        display_name TEXT,
        role TEXT DEFAULT 'user',
        referral_code TEXT UNIQUE,
        referred_by TEXT,
        access_days INTEGER DEFAULT 10,
        access_expires TIMESTAMP,
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
    conn.execute('''CREATE TABLE IF NOT EXISTS chat_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message TEXT,
        reply TEXT,
        model TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    for col, typ in [
        ("access_days", "INTEGER DEFAULT 10"),
        ("access_expires", "TIMESTAMP"),
        ("google_id", "TEXT"),
        ("display_name", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} {typ}")
        except:
            pass

    # Generate referral codes for users missing them
    users = conn.execute("SELECT id, username FROM users WHERE referral_code IS NULL").fetchall()
    for u in users:
        code = "KVS" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        conn.execute("UPDATE users SET referral_code = ? WHERE id = ?", (code, u["id"]))

    # Set access expiry for users missing it
    users_no_expiry = conn.execute("SELECT id, created_at FROM users WHERE access_expires IS NULL").fetchall()
    for u in users_no_expiry:
        try:
            created = datetime.fromisoformat(u["created_at"])
        except:
            created = datetime.utcnow()
        expires = created + timedelta(days=10)
        conn.execute("UPDATE users SET access_expires = ? WHERE id = ?", (expires.isoformat(), u["id"]))

    # Create default admin if not exists
    admin_hash = hashlib.sha256("krishay123123".encode()).hexdigest()
    try:
        admin_code = "KVSADMIN00"
        conn.execute(
            "INSERT INTO users (username, password_hash, role, referral_code, access_days, access_expires) VALUES (?, ?, ?, ?, ?, ?)",
            ("adminkrishay", admin_hash, "admin", admin_code, 99999, (datetime.utcnow() + timedelta(days=9999)).isoformat())
        )
    except sqlite3.IntegrityError:
        pass
    # Ensure admin password is up to date
    conn.execute("UPDATE users SET password_hash=?, access_expires='2099-12-31T23:59:59', access_days=99999 WHERE role='admin'", (admin_hash,))

    conn.commit()
    conn.close()

def generate_referral_code(username):
    return "KVS" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

init_db()

# --- Auth ---
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def get_user(username=None, user_id=None, google_id=None):
    conn = get_db()
    if user_id:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    elif google_id:
        user = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
    else:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(user) if user else None

def log_login(username, email, ip, success):
    conn = get_db()
    conn.execute("INSERT INTO login_log (username, email, ip_address, success) VALUES (?, ?, ?, ?)",
                 (username, email, ip, 1 if success else 0))
    conn.commit()
    conn.close()

def has_access(user):
    if user["role"] == "admin":
        return True
    if user.get("access_expires"):
        try:
            expires = datetime.fromisoformat(user["access_expires"])
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) < expires
        except:
            pass
    return False

def extend_access(user_id, days=10):
    conn = get_db()
    user = conn.execute("SELECT access_expires FROM users WHERE id = ?", (user_id,)).fetchone()
    if user and user["access_expires"]:
        try:
            current = datetime.fromisoformat(user["access_expires"])
        except:
            current = datetime.utcnow()
    else:
        current = datetime.utcnow()
    new_expiry = current + timedelta(days=days)
    conn.execute("UPDATE users SET access_expires = ?, access_days = access_days + ? WHERE id = ?",
                 (new_expiry.isoformat(), days, user_id))
    conn.commit()
    conn.close()

def create_user(username=None, email=None, password=None, google_id=None, display_name=None, referral_code=None):
    conn = get_db()
    user_code = generate_referral_code(username or display_name or "user")
    pw_hash = hashlib.sha256(password.encode()).hexdigest() if password else None
    expires = (datetime.utcnow() + timedelta(days=10)).isoformat()

    referrer = None
    if referral_code:
        referrer = conn.execute("SELECT username FROM users WHERE referral_code = ?", (referral_code,)).fetchone()

    try:
        conn.execute(
            "INSERT INTO users (username, email, password_hash, google_id, display_name, role, referral_code, referred_by, access_days, access_expires) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (username, email, pw_hash, google_id, display_name, "user", user_code, referrer["username"] if referrer else None, 10, expires)
        )
        conn.commit()
        new_user = conn.execute("SELECT * FROM users WHERE referral_code = ?", (user_code,)).fetchone()
        conn.close()
        if referrer:
            extend_access(referrer["id"], 10)
        return dict(new_user) if new_user else None
    except sqlite3.IntegrityError:
        conn.close()
        return None

# --- Routes ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("landing"))
    if request.method == "POST":
        data = request.form
        username = data.get("username", "")
        password = data.get("password", "")
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        user = get_user(username=username)
        if user and user.get("password_hash") and user["password_hash"] == pw_hash:
            session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            log_login(username, user.get("email", ""), request.remote_addr, True)
            return redirect(url_for("landing"))
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
        try:
            username = request.form.get("username", "")
            email = request.form.get("email", "")
            password = request.form.get("password", "")
            ref_code = request.form.get("referral_code", "").strip()
            if not username or not password:
                return render_template("register.html", error="All fields required")
            if not email:
                return render_template("register.html", error="Email is required")
            if not ref_code:
                return render_template("register.html", error="Referral code is required. Ask a friend for theirs.")
            if len(username) < 3:
                return render_template("register.html", error="Username must be 3+ characters")
            if len(password) < 6:
                return render_template("register.html", error="Password must be 6+ characters")

            user = create_user(username=username, email=email, password=password, referral_code=ref_code)
            if user:
                return render_template("register.html", success="Account created! You can now sign in.")
            return render_template("register.html", error="Username already exists")
        except Exception as e:
            return render_template("register.html", error=str(e))
    return render_template("register.html")

@app.route("/")
def landing():
    if "user_id" in session:
        user = get_user(user_id=session["user_id"])
        if user and has_access(user):
            if session.get("role") == "admin":
                return render_template("dashboard.html", username=user.get("display_name") or session["username"])
            return render_template("user.html", username=user.get("display_name") or session["username"])
        else:
            return render_template("expired.html", username=session.get("username", ""))
    return render_template("landing.html")

# --- Google OAuth (simplified) ---
@app.route("/auth/google")
def google_login():
    config = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            config = json.load(f)
    client_id = config.get("google_client_id", "")
    if not client_id:
        return render_template("login.html", error="Google login not configured yet")
    redirect_uri = url_for("google_callback", _external=True)
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&redirect_uri={redirect_uri}&response_type=code"
        f"&scope=openid%20email%20profile&access_type=offline"
    )
    return redirect(google_auth_url)

@app.route("/auth/google/callback")
def google_callback():
    config = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            config = json.load(f)
    code = request.args.get("code")
    if not code:
        return redirect(url_for("login"))
    try:
        token_resp = requests.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": config.get("google_client_id", ""),
            "client_secret": config.get("google_client_secret", ""),
            "redirect_uri": url_for("google_callback", _external=True),
            "grant_type": "authorization_code",
        }, timeout=10)
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            return redirect(url_for("login"))
        user_info = requests.get("https://www.googleapis.com/oauth2/v2/userinfo",
                                 headers={"Authorization": f"Bearer {access_token}"}, timeout=10).json()
        google_id = user_info.get("id")
        email = user_info.get("email", "")
        display_name = user_info.get("name", email.split("@")[0])

        user = get_user(google_id=google_id)
        if not user:
            user = create_user(username=email.split("@")[0], email=email, google_id=google_id, display_name=display_name)
        if user:
            session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("landing"))
    except Exception as e:
        pass
    return redirect(url_for("login"))

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
        d["is_online"] = (time.time() - datetime.fromisoformat(d["last_seen"]).replace(tzinfo=timezone.utc).timestamp()) < 120
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
                       if (time.time() - datetime.fromisoformat(w["last_seen"]).replace(tzinfo=timezone.utc).timestamp()) < 120)
    total_power = sum(w["power_usage"] for w in workers)

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

@app.route("/api/ai/chat", methods=["POST"])
@login_required
def ai_chat():
    data = request.json
    message = data.get("message", "")
    if not message:
        return jsonify({"error": "empty message"}), 400

    user_id = session.get("user_id")
    is_admin = session.get("role") == "admin"
    conn = get_db()

    if not is_admin:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user:
            user_dict = dict(user)
            if not has_access(user_dict):
                conn.close()
                return jsonify({"error": "Access expired. Refer a friend to get 10 more days!"}), 403

        last_msg = conn.execute(
            "SELECT created_at FROM chat_log WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        if last_msg:
            last_time = datetime.fromisoformat(last_msg["created_at"]).replace(tzinfo=timezone.utc).timestamp()
            if time.time() - last_time < 5:
                conn.close()
                remaining = int(5 - (time.time() - last_time))
                return jsonify({"error": f"Wait {remaining}s"}), 429

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        today_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM chat_log WHERE user_id=? AND created_at>=?",
            (user_id, today_start)
        ).fetchone()["cnt"]
        if today_count >= 50:
            conn.close()
            return jsonify({"error": "Daily limit (50). Refer friends for more!"}), 429

    models_to_try = pick_model_pool(message)

    config = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            config = json.load(f)

    api_keys = config.get("nvidia_api_keys", [])
    if not api_keys and config.get("nvidia_api_key"):
        api_keys = [config["nvidia_api_key"]]
    if not api_keys:
        conn.close()
        return jsonify({"error": "No API keys configured"}), 500

    last_error = None
    # Build conversation with context (last 10 messages)
    history_rows = conn.execute(
        "SELECT message, reply FROM chat_log WHERE user_id=? ORDER BY created_at DESC LIMIT 10",
        (user_id,)
    ).fetchall()
    messages = [{"role": "system", "content": KVS_SYSTEM}]
    for h in reversed(history_rows):
        messages.append({"role": "user", "content": h["message"]})
        messages.append({"role": "assistant", "content": h["reply"]})
    messages.append({"role": "user", "content": message})

    for model in models_to_try:
        for api_key in api_keys:
            try:
                resp = requests.post(NVIDIA_API_URL, headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }, json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": 1024,
                    "temperature": 0.7
                }, timeout=15)
                resp.raise_for_status()
                result = resp.json()
                reply = result["choices"][0]["message"]["content"]
                model_used = model.split("/")[-1]
                try:
                    log_conn = get_db()
                    log_conn.execute("INSERT INTO chat_log (user_id, message, reply, model) VALUES (?, ?, ?, ?)",
                                     (session.get("user_id"), message, reply[:500], model_used))
                    log_conn.commit()
                    log_conn.close()
                except:
                    pass
                conn.close()
                return jsonify({"reply": reply, "model": model_used})
            except Exception as e:
                last_error = str(e)
                continue

    conn.close()
    return jsonify({"error": f"All models failed. Last error: {last_error}"}), 500

@app.route("/api/chat-history", methods=["GET"])
@login_required
def chat_history():
    conn = get_db()
    rows = conn.execute(
        "SELECT message, reply, model, created_at FROM chat_log WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
        (session["user_id"],)
    ).fetchall()
    conn.close()
    history = []
    for r in reversed(rows):
        history.append({"role": "user", "content": r["message"]})
        history.append({"role": "ai", "content": r["reply"], "model": r["model"], "time": str(r["created_at"])})
    return jsonify(history)

@app.route("/api/chat-stats", methods=["GET"])
@login_required
def chat_stats():
    if session.get("role") != "admin":
        return jsonify({"error": "admin only"}), 403
    conn = get_db()
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    total_today = conn.execute("SELECT COUNT(*) as cnt FROM chat_log WHERE created_at>=?", (today_start,)).fetchone()["cnt"]
    total_all = conn.execute("SELECT COUNT(*) as cnt FROM chat_log").fetchone()["cnt"]
    users_today = conn.execute("SELECT COUNT(DISTINCT user_id) as cnt FROM chat_log WHERE created_at>=?", (today_start,)).fetchone()["cnt"]
    conn.close()
    return jsonify({"today_messages": total_today, "total_messages": total_all, "active_users_today": users_today})

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

@app.route("/api/users", methods=["GET", "POST"])
@login_required
def users_route():
    if session.get("role") != "admin":
        return jsonify({"error": "admin only"}), 403
    conn = get_db()
    if request.method == "GET":
        users = conn.execute("SELECT id, username, email, role, display_name, access_days, access_expires, referred_by, created_at FROM users").fetchall()
        conn.close()
        return jsonify([dict(u) for u in users])
    data = request.json
    username = data.get("username", "")
    email = data.get("email", "")
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    user = create_user(username=username, email=email, password=password)
    if user:
        return jsonify({"ok": True})
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
    try:
        conn = get_db()
        user = conn.execute("SELECT referral_code, access_expires FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        if not user:
            conn.close()
            return jsonify({"error": "user not found"}), 404

        code = user["referral_code"]
        if not code:
            code = generate_referral_code(session["username"])
            conn.execute("UPDATE users SET referral_code = ? WHERE id = ?", (code, session["user_id"]))
            conn.commit()

        referrals = conn.execute("SELECT COUNT(*) as cnt FROM users WHERE referred_by = ?", (session["username"],)).fetchone()
        referral_list = conn.execute("SELECT username, created_at FROM users WHERE referred_by = ? ORDER BY created_at DESC", (session["username"],)).fetchall()
        conn.close()

        return jsonify({
            "referral_code": code,
            "referral_link": f"http://localhost:5000/register?ref={code}",
            "total_referrals": referrals["cnt"],
            "days_remaining": str(user["access_expires"]) if user["access_expires"] else "?",
            "referrals": [{"username": r["username"], "joined": str(r["created_at"])} for r in referral_list]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    blocked = ["format", "del /s", "rd /s", "shutdown", "taskkill /f", "reg delete"]
    for b in blocked:
        if b.lower() in command.lower():
            return jsonify({"error": f"Blocked: {b}"}), 403
    try:
        import subprocess
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return jsonify({"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode})
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timed out (30s)"}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/browser/open", methods=["POST"])
@login_required
def browser_open():
    data = request.json
    url = data.get("url", "")
    if not url:
        return jsonify({"error": "no url"}), 400
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
                processes.append({"pid": pinfo['pid'], "name": pinfo['name'], "cpu": pinfo['cpu_percent'], "memory": round(pinfo['memory_percent'], 1)})
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
        return jsonify({"status": "protected", "firewall": True, "antivirus": True, "suspicious": suspicious, "blocked_intrusions": 0})
    except:
        return jsonify({"status": "protected"})

@app.route("/api/files/list", methods=["POST"])
@login_required
def list_files():
    data = request.json
    path = data.get("path", os.path.expanduser("~"))
    try:
        items = []
        for item in os.listdir(path):
            full = os.path.join(path, item)
            items.append({"name": item, "is_dir": os.path.isdir(full), "size": os.path.getsize(full) if os.path.isfile(full) else 0, "modified": os.path.getmtime(full)})
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return jsonify({"path": path, "items": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/files/read", methods=["POST"])
@login_required
def read_file():
    data = request.json
    path = data.get("path", "")
    try:
        with open(path, 'r', errors='ignore') as f:
            content = f.read(100000)
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
        return jsonify({"error": str(e)}), 500

@app.route("/api/files/move", methods=["POST"])
@login_required
def move_file():
    data = request.json
    try:
        os.rename(data.get("source"), data.get("destination"))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/files/mkdir", methods=["POST"])
@login_required
def mkdir():
    data = request.json
    try:
        os.makedirs(data.get("path"), exist_ok=True)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/files/delete", methods=["POST"])
@login_required
def delete_file():
    data = request.json
    try:
        path = data.get("path")
        if os.path.isdir(path):
            os.rmdir(path)
        else:
            os.remove(path)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    print("KVS starting on http://0.0.0.0:5000")
    print("Default admin login: admin / krishay123")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
