#!/usr/bin/env python3
"""
RustDesk Minimal API Server & Web Management Dashboard
Lightweight, zero-dependency Python 3 server.
Memory footprint: ~15MB RAM.
"""

import os
import sys
import json
import time
import hmac
import hashlib
import secrets
import threading
import html
from urllib.parse import parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie

CONFIG_DIR = os.environ.get("RUSTDESK_API_DIR", "/opt/rustdesk-api")
DATA_FILE = os.path.join(CONFIG_DIR, "data.json")
PORT = int(os.environ.get("RUSTDESK_API_PORT", 21114))

# Credentials
USERNAME = os.environ.get("RUSTDESK_API_USER", "bigdesign3r")
PASSWORD = os.environ.get("RUSTDESK_API_PASS", "Pantyhose.2020*-*")

lock = threading.Lock()

# In-memory session store: token -> expiry timestamp
active_tokens = {}
web_sessions = {}

def get_password_hash(pwd):
    salt = "gnn_rustdesk_salt_2026"
    return hashlib.sha256((pwd + salt).encode('utf-8')).hexdigest()

PASSWORD_HASH = get_password_hash(PASSWORD)

def load_data():
    if not os.path.exists(DATA_FILE):
        default_data = {
            "tags": ["Genel", "VIP", "Muhasebe"],
            "peers": []
        }
        save_data(default_data)
        return default_data
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {DATA_FILE}: {e}")
        return {"tags": [], "peers": []}

def save_data(data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    temp_file = DATA_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, DATA_FILE)

class RustDeskAPIHandler(BaseHTTPRequestHandler):
    server_version = "RustDesk-API/1.0"

    def log_message(self, format, *args):
        # Concise logging
        print(f"[{self.log_date_time_string()}] {self.command} {self.path} - {args[0]}")

    def send_json(self, status_code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "*")
        self.end_headers()
        self.wfile.write(data)

    def send_html(self, status_code, html_content, set_cookie=None):
        data = html_content.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location, set_cookie=None):
        self.send_response(302)
        self.send_header("Location", location)
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def read_body_json(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def read_body_form(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length).decode("utf-8")
        return {k: v[0] for k, v in parse_qs(raw).items()}

    def check_auth(self):
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            with lock:
                if token in active_tokens and active_tokens[token] > time.time():
                    return True
        return False

    def check_web_auth(self):
        cookie_header = self.headers.get("Cookie", "")
        if cookie_header:
            cookie = SimpleCookie()
            try:
                cookie.load(cookie_header)
                if "rd_session" in cookie:
                    token = cookie["rd_session"].value
                    with lock:
                        if token in web_sessions and web_sessions[token] > time.time():
                            return True
            except Exception:
                pass
        return False

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. RustDesk Client API endpoints
        if path == "/api/login-options":
            self.send_json(200, {"type": "account"})
            return

        elif path == "/api/ab":
            if not self.check_auth():
                self.send_json(401, {"error": "Unauthorized"})
                return
            with lock:
                ab_data = load_data()
            self.send_json(200, {
                "data": json.dumps(ab_data, ensure_ascii=False),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "licensed_devices": 1000
            })
            return

        elif path == "/healthz":
            self.send_json(200, {"status": "ok"})
            return

        # 2. Web Management Dashboard
        if path == "/login" or path == "/":
            if self.check_web_auth():
                self.redirect("/dashboard")
                return
            self.send_html(200, render_login_page())
            return

        elif path == "/dashboard":
            if not self.check_web_auth():
                self.redirect("/login")
                return
            with lock:
                ab_data = load_data()
            self.send_html(200, render_dashboard(ab_data))
            return

        elif path == "/logout":
            self.redirect("/login", set_cookie="rd_session=; Path=/; Max-Age=0")
            return

        self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. RustDesk Client Login
        if path == "/api/login":
            body = self.read_body_json()
            user = body.get("username", "")
            pwd = body.get("password", "")

            if user == USERNAME and pwd == PASSWORD:
                token = secrets.token_hex(32)
                with lock:
                    # Token valid for 30 days
                    active_tokens[token] = time.time() + (30 * 86400)
                self.send_json(200, {
                    "access_token": token,
                    "type": "access_token",
                    "user": {
                        "name": USERNAME,
                        "display_name": USERNAME,
                        "is_admin": True,
                        "status": 1
                    }
                })
            else:
                self.send_json(400, {"error": "Kullanıcı adı veya şifre hatalı!"})
            return

        elif path == "/api/currentUser":
            if not self.check_auth():
                self.send_json(401, {"error": "Unauthorized"})
                return
            self.send_json(200, {
                "name": USERNAME,
                "display_name": USERNAME,
                "is_admin": True,
                "status": 1
            })
            return

        elif path == "/api/logout":
            auth_header = self.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
                with lock:
                    active_tokens.pop(token, None)
            self.send_json(200, {"code": 1})
            return

        # 2. RustDesk Address Book Update
        elif path == "/api/ab":
            if not self.check_auth():
                self.send_json(401, {"error": "Unauthorized"})
                return
            body = self.read_body_json()
            raw_data = body.get("data", "")
            if raw_data:
                try:
                    parsed_ab = json.loads(raw_data)
                    with lock:
                        save_data(parsed_ab)
                except Exception as e:
                    print(f"Error parsing ab data: {e}")
            self.send_json(200, {"data": raw_data})
            return

        # Legacy / Compatibility fallbacks
        elif path == "/api/ab/personal":
            self.send_json(404, {"error": "Legacy mode"})
            return

        elif path == "/api/ab/settings":
            self.send_json(200, {"max_peer_one_ab": 1000})
            return

        elif path in ["/api/devices", "/api/peers", "/api/ab/shared/profiles"]:
            self.send_json(200, {"total": 0, "data": []})
            return

        elif path == "/api/users":
            self.send_json(200, {"total": 1, "data": [{"name": USERNAME, "display_name": USERNAME}]})
            return

        elif path == "/api/device-group/accessible":
            self.send_json(200, {"total": 0, "data": []})
            return

        # 3. Web Panel Endpoints
        elif path == "/web/login":
            form = self.read_body_form()
            user = form.get("username", "")
            pwd = form.get("password", "")
            if user == USERNAME and pwd == PASSWORD:
                token = secrets.token_hex(32)
                with lock:
                    web_sessions[token] = time.time() + (7 * 86400)
                self.redirect("/dashboard", set_cookie=f"rd_session={token}; Path=/; HttpOnly; Max-Age=604800")
            else:
                self.send_html(400, render_login_page("Kullanıcı adı veya şifre hatalı!"))
            return

        elif path == "/web/peer/add":
            if not self.check_web_auth():
                self.redirect("/login")
                return
            form = self.read_body_form()
            peer_id = form.get("id", "").strip().replace(" ", "")
            alias = form.get("alias", "").strip()
            tags_raw = form.get("tags", "").strip()
            note = form.get("note", "").strip()

            if peer_id:
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                with lock:
                    ab = load_data()
                    # Check existing
                    existing = next((p for p in ab["peers"] if p["id"] == peer_id), None)
                    if existing:
                        existing["alias"] = alias
                        existing["tags"] = tags
                        if note: existing["note"] = note
                    else:
                        new_peer = {
                            "id": peer_id,
                            "alias": alias,
                            "tags": tags,
                        }
                        if note: new_peer["note"] = note
                        ab["peers"].append(new_peer)
                    for t in tags:
                        if t not in ab["tags"]:
                            ab["tags"].append(t)
                    save_data(ab)
            self.redirect("/dashboard")
            return

        elif path == "/web/peer/delete":
            if not self.check_web_auth():
                self.redirect("/login")
                return
            form = self.read_body_form()
            peer_id = form.get("id", "").strip()
            if peer_id:
                with lock:
                    ab = load_data()
                    ab["peers"] = [p for p in ab["peers"] if p["id"] != peer_id]
                    save_data(ab)
            self.redirect("/dashboard")
            return

        self.send_json(404, {"error": "Not found"})

def render_login_page(err=""):
    err_html = f'<div class="error">{err}</div>' if err else ""
    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RustDesk Rehber Yönetim Paneli</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{ background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
        .card {{ background: #1e293b; padding: 2.5rem; border-radius: 16px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5); width: 100%; max-width: 400px; border: 1px solid #334155; }}
        .header {{ text-align: center; margin-bottom: 2rem; }}
        .header h1 {{ font-size: 1.5rem; font-weight: 700; color: #38bdf8; margin-bottom: 0.5rem; }}
        .header p {{ color: #94a3b8; font-size: 0.875rem; }}
        .form-group {{ margin-bottom: 1.25rem; }}
        label {{ display: block; font-size: 0.875rem; font-weight: 500; color: #cbd5e1; margin-bottom: 0.5rem; }}
        input {{ width: 100%; padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: #f8fafc; font-size: 0.95rem; outline: none; transition: border-color 0.2s; }}
        input:focus {{ border-color: #38bdf8; }}
        button {{ width: 100%; padding: 0.75rem 1rem; background: #0284c7; color: white; border: none; border-radius: 8px; font-weight: 600; font-size: 1rem; cursor: pointer; transition: background 0.2s; }}
        button:hover {{ background: #0369a1; }}
        .error {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid #ef4444; padding: 0.75rem; border-radius: 8px; font-size: 0.875rem; margin-bottom: 1rem; text-align: center; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <h1>RustDesk Rehber</h1>
            <p>Yönetici Paneli Girişi</p>
        </div>
        {err_html}
        <form method="POST" action="/web/login">
            <div class="form-group">
                <label>Kullanıcı Adı</label>
                <input type="text" name="username" required autofocus placeholder="Kullanıcı adınız">
            </div>
            <div class="form-group">
                <label>Şifre</label>
                <input type="password" name="password" required placeholder="••••••••">
            </div>
            <button type="submit">Giriş Yap</button>
        </form>
    </div>
</body>
</html>"""

def render_dashboard(data):
    peers = data.get("peers", [])
    tags = data.get("tags", [])
    total_peers = len(peers)

    rows = ""
    for p in peers:
        raw_pid = p.get("id", "")
        raw_alias = p.get("alias", "-")
        ptags = p.get("tags", [])
        raw_note = p.get("note", "-")

        pid = html.escape(str(raw_pid))
        alias = html.escape(str(raw_alias))
        note = html.escape(str(raw_note))
        tag_badges = "".join([f'<span class="badge">{html.escape(str(t))}</span>' for t in ptags]) or '<span class="text-muted">-</span>'
        
        safe_alias_js = alias.replace("'", "\\'")
        rows += f"""
        <tr>
            <td class="font-mono font-bold text-sky">{pid}</td>
            <td><strong>{alias}</strong></td>
            <td>{tag_badges}</td>
            <td class="text-muted">{note}</td>
            <td>
                <form method="POST" action="/web/peer/delete" style="display:inline;" onsubmit="return confirm('{safe_alias_js} ({pid}) silinsin mi?');">
                    <input type="hidden" name="id" value="{pid}">
                    <button type="submit" class="btn-del">Sil</button>
                </form>
            </td>
        </tr>
        """

    if not rows:
        rows = '<tr><td colspan="5" style="text-align:center; padding: 2rem; color: #64748b;">Henüz kayıtlı müşteri yok. Yukarıdan ekleyebilirsiniz.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RustDesk Rehber Yönetim Paneli</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{ background: #0f172a; color: #f8fafc; min-height: 100vh; padding: 2rem; }}
        .container {{ max-width: 1100px; margin: 0 auto; }}
        .nav {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; border-bottom: 1px solid #334155; padding-bottom: 1rem; }}
        .nav h1 {{ font-size: 1.5rem; color: #38bdf8; font-weight: 700; }}
        .nav .user {{ color: #94a3b8; font-size: 0.9rem; }}
        .nav a {{ color: #f87171; text-decoration: none; margin-left: 1rem; font-weight: 600; font-size: 0.875rem; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .stat-card {{ background: #1e293b; border: 1px solid #334155; padding: 1.25rem; border-radius: 12px; }}
        .stat-card .val {{ font-size: 1.8rem; font-weight: 700; color: #38bdf8; }}
        .stat-card .label {{ color: #94a3b8; font-size: 0.85rem; margin-top: 0.25rem; }}
        .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; }}
        .card h2 {{ font-size: 1.15rem; margin-bottom: 1rem; color: #e2e8f0; }}
        .form-grid {{ display: grid; grid-template-columns: 1.5fr 2fr 2fr 2fr 1fr; gap: 0.75rem; align-items: end; }}
        input {{ padding: 0.65rem 0.85rem; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: #f8fafc; font-size: 0.9rem; outline: none; width: 100%; }}
        input:focus {{ border-color: #38bdf8; }}
        label {{ display: block; font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.35rem; }}
        button.btn-add {{ background: #0284c7; color: white; border: none; padding: 0.65rem 1rem; border-radius: 8px; font-weight: 600; cursor: pointer; height: 38px; }}
        button.btn-add:hover {{ background: #0369a1; }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; }}
        th {{ padding: 0.85rem; background: #0f172a; color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #334155; }}
        td {{ padding: 0.85rem; border-bottom: 1px solid #334155; font-size: 0.9rem; }}
        .badge {{ background: #0369a1; color: #e0f2fe; padding: 0.2rem 0.5rem; border-radius: 6px; font-size: 0.75rem; margin-right: 0.35rem; display: inline-block; }}
        .text-muted {{ color: #64748b; }}
        .text-sky {{ color: #38bdf8; }}
        .font-mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
        .font-bold {{ font-weight: 600; }}
        .btn-del {{ background: transparent; border: 1px solid #ef4444; color: #ef4444; padding: 0.35rem 0.65rem; border-radius: 6px; font-size: 0.75rem; cursor: pointer; }}
        .btn-del:hover {{ background: #ef4444; color: white; }}
        .search-box {{ margin-bottom: 1rem; }}
        .search-box input {{ max-width: 300px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="nav">
            <div>
                <h1>RustDesk Rehber</h1>
                <span class="user">Sunucu: 130.61.69.181 &bull; Kullanıcı: {USERNAME}</span>
            </div>
            <div>
                <a href="/logout">Çıkış Yap</a>
            </div>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="val">{total_peers}</div>
                <div class="label">Kayıtlı Müşteri Sayısı</div>
            </div>
            <div class="stat-card">
                <div class="val">{len(tags)}</div>
                <div class="label">Tanımlı Etiket</div>
            </div>
            <div class="stat-card">
                <div class="val" style="color: #4ade80;">Aktif</div>
                <div class="label">API Durumu (:21114)</div>
            </div>
        </div>

        <div class="card">
            <h2>Hızlı Müşteri Ekle</h2>
            <form method="POST" action="/web/peer/add">
                <div class="form-grid">
                    <div>
                        <label>RustDesk ID *</label>
                        <input type="text" name="id" required placeholder="örn: 438438467">
                    </div>
                    <div>
                        <label>Müşteri / Cihaz Adı *</label>
                        <input type="text" name="alias" required placeholder="örn: Ahmet Bey - Muhasebe">
                    </div>
                    <div>
                        <label>Etiketler (Virgülle)</label>
                        <input type="text" name="tags" placeholder="örn: Muhasebe, VIP">
                    </div>
                    <div>
                        <label>Özel Not</label>
                        <input type="text" name="note" placeholder="örn: Pazartesi bakım yapılacak">
                    </div>
                    <div>
                        <button type="submit" class="btn-add">+ Ekle</button>
                    </div>
                </div>
            </form>
        </div>

        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h2>Kayıtlı Müşteriler (Rehber)</h2>
                <div class="search-box">
                    <input type="text" id="searchInput" onkeyup="filterTable()" placeholder="Rehberde ara...">
                </div>
            </div>
            <table id="peersTable">
                <thead>
                    <tr>
                        <th>RustDesk ID</th>
                        <th>Müşteri Adı</th>
                        <th>Etiketler</th>
                        <th>Not</th>
                        <th>İşlem</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function filterTable() {{
            var input = document.getElementById("searchInput");
            var filter = input.value.toLowerCase();
            var table = document.getElementById("peersTable");
            var tr = table.getElementsByTagName("tr");
            for (var i = 1; i < tr.length; i++) {{
                var text = tr[i].textContent || tr[i].innerText;
                if (text.toLowerCase().indexOf(filter) > -1) {{
                    tr[i].style.display = "";
                }} else {{
                    tr[i].style.display = "none";
                }}
            }}
        }}
    </script>
</body>
</html>"""

def run():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, RustDeskAPIHandler)
    print(f"RustDesk Minimal API Server running on port {PORT}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == "__main__":
    run()
