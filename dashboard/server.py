from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import json, os, time, hashlib, secrets, requests, sqlite3
from datetime import datetime, timezone
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

DB_PATH = os.path.join(os.path.dirname(__file__), "aipowerfarm.db")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
USERS_PATH = os.path.join(os.path.dirname(__file__), "users.json")

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1"

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
        coin TEXT DEFAULT 'ETHW',
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

    # Create default admin if not exists
    admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
    try:
        conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                     ("admin", admin_hash, "admin"))
    except sqlite3.IntegrityError:
        pass
    conn.commit()
    conn.close()

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
        if not username or not password:
            return render_template("register.html", error="All fields required")
        if not email:
            return render_template("register.html", error="Email is required")
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        conn = get_db()
        try:
            conn.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                         (username, email, pw_hash, "employee"))
            conn.commit()
            conn.close()
            return render_template("register.html", success="Account created! You can now sign in.")
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("register.html", error="Username already exists")
    return render_template("register.html")

@app.route("/")
@login_required
def dashboard():
    if session["role"] == "admin":
        return render_template("dashboard.html",
                               username=session["username"],
                               role=session["role"])
    else:
        return render_template("employee.html",
                               username=session["username"],
                               role=session["role"])

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
                  data.get("miner_version", ""), data.get("coin", "ETHW"),
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
            "https://ethw.2miners.com/api/accounts/0x11CF2C01cEedC8d2aEFcFa98abeE0e6AbaD90177",
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
    if not message:
        return jsonify({"error": "empty message"}), 400

    config = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            config = json.load(f)

    api_key = config.get("nvidia_api_key", "")
    if not api_key:
        return jsonify({"error": "API key not configured. Ask admin to set it in config.json"}), 500

    try:
        system_msg = """You are a helpful AI assistant with file management capabilities. You can:
- List files in any directory
- Move/rename files
- Create folders
- Delete files

When a user asks you to organize files, suggest specific actions like:
"Move report.pdf to the Reports folder" or "Create a folder called Projects"

Be helpful, concise, and friendly. You can also help with general questions, coding, writing, and more."""

        resp = requests.post(NVIDIA_API_URL, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }, json={
            "model": NVIDIA_MODEL,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": message}
            ],
            "max_tokens": 1024,
            "temperature": 0.7
        }, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        reply = result["choices"][0]["message"]["content"]
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        return jsonify(config)
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

if __name__ == "__main__":
    print("AI Power Farm Dashboard starting on http://0.0.0.0:5000")
    print("Default admin login: admin / admin123")
    app.run(host="0.0.0.0", port=5000, debug=False)
