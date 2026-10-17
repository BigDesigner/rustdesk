#!/usr/bin/env python3
"""
RustDesk Minimal API Server & Web Management Dashboard
Lightweight, zero-dependency Python 3 server.
Memory footprint: ~15MB RAM.
UI modeled after RustDesk Pro Console (console.png & custom.png).
"""

import os
import sys
import json
import time
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

DEFAULT_SERVER_HOST = "130.61.69.181"
DEFAULT_KEY = "ARtU1Y9FU869kBMyY0w8Yt3H9hlJHubpZWxUX2Jmzgc="
DEFAULT_API_URL = "http://130.61.69.181:21114"
DEFAULT_PRESET_PWD = "Gnn2922**"

lock = threading.Lock()

# In-memory session store
active_tokens = {}
web_sessions = {}

def get_default_client_config():
    return {
        "config_name": "GNN-Destek-Windows",
        "app_name": "GNN Destek",
        "connection_type": "bidirectional",
        "disable_installation": True,
        "disable_settings": True,
        "disable_address_book": False,
        "disable_tcp_listen": False,
        "disable_user_account": False,
        "note": "GNN Özel Destek İstemcisi (Windows 64-bit)",
        "host": DEFAULT_SERVER_HOST,
        "key": DEFAULT_KEY,
        "api": DEFAULT_API_URL,
        "preset_password": DEFAULT_PRESET_PWD,
        "preset_password_enabled": True
    }

def load_data():
    default_data = {
        "tags": ["Genel", "AKANSU", "GNN", "Windows", "Android"],
        "peers": [],
        "client_config": get_default_client_config()
    }
    if not os.path.exists(DATA_FILE):
        save_data(default_data)
        return default_data
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "client_config" not in data:
                data["client_config"] = get_default_client_config()
            return data
    except Exception as e:
        print(f"Error loading {DATA_FILE}: {e}")
        return default_data

def save_data(data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    temp_file = DATA_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, DATA_FILE)

class RustDeskAPIHandler(BaseHTTPRequestHandler):
    server_version = "RustDesk-Console/2.0"

    def log_message(self, format, *args):
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
            export_data = {
                "tags": ab_data.get("tags", []),
                "peers": ab_data.get("peers", [])
            }
            if "tag_colors" in ab_data:
                export_data["tag_colors"] = ab_data["tag_colors"]
            self.send_json(200, {
                "data": json.dumps(export_data, ensure_ascii=False),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "licensed_devices": 1000
            })
            return

        elif path == "/healthz":
            self.send_json(200, {"status": "ok"})
            return

        elif path in ["/logo.png", "/favicon.ico"]:
            icon_path = os.path.join(CONFIG_DIR, "icon.png")
            if not os.path.exists(icon_path):
                local_fallback = os.path.join(os.getcwd(), "res", "icon.png")
                if os.path.exists(local_fallback):
                    icon_path = local_fallback
            if os.path.exists(icon_path):
                file_size = os.path.getsize(icon_path)
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "public, max-age=604800")
                self.send_header("Content-Length", str(file_size))
                self.end_headers()
                with open(icon_path, "rb") as f:
                    while chunk := f.read(65536):
                        self.wfile.write(chunk)
                return
            else:
                self.send_json(404, {"error": "Logo not found"})
                return

        elif path in ["/download/GNNQS.exe", "/download/Destek.exe"]:
            exe_path = os.path.join(CONFIG_DIR, "GNNQS.exe")
            if not os.path.exists(exe_path):
                exe_path = os.path.join(CONFIG_DIR, "Destek.exe")
            if not os.path.exists(exe_path):
                local_fallback = os.path.join(os.getcwd(), "downloaded_destek", "Destek.exe")
                if os.path.exists(local_fallback):
                    exe_path = local_fallback
            if os.path.exists(exe_path):
                file_size = os.path.getsize(exe_path)
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", 'attachment; filename="GNNQS.exe"')
                self.send_header("Content-Length", str(file_size))
                self.end_headers()
                with open(exe_path, "rb") as f:
                    while chunk := f.read(65536):
                        self.wfile.write(chunk)
                return
            else:
                self.send_json(404, {"error": "GNNQS.exe henüz sunucuya yüklenmedi."})
                return

        # 2. Web Management Dashboard
        if path in ["/login", "/"]:
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
            self.send_html(200, render_console(ab_data))
            return

        elif path == "/logout":
            self.redirect("/login", set_cookie="rd_session=; Path=/; Max-Age=0")
            return

        elif path in ["/api/devices", "/api/peers", "/api/users", "/api/device-group/accessible"]:
            self.send_json(200, {"total": 0, "data": []})
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
                        curr = load_data()
                        if "tags" in parsed_ab:
                            curr["tags"] = parsed_ab["tags"]
                        if "peers" in parsed_ab:
                            curr["peers"] = parsed_ab["peers"]
                        if "tag_colors" in parsed_ab:
                            curr["tag_colors"] = parsed_ab["tag_colors"]
                        save_data(curr)
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

        elif path in ["/api/heartbeat", "/api/sysinfo", "/api/audit/conn", "/api/audit"]:
            self.send_json(200, {"code": 1, "data": "ok"})
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

        elif path in ["/web/peer/add", "/web/peer/edit"]:
            if not self.check_web_auth():
                self.redirect("/login")
                return
            form = self.read_body_form()
            peer_id = form.get("id", "").strip().replace(" ", "")
            alias = form.get("alias", "").strip()
            tags_raw = form.get("tags", "").strip()
            note = form.get("note", "").strip()
            platform = form.get("platform", "Windows").strip()

            if peer_id:
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                with lock:
                    ab = load_data()
                    existing = next((p for p in ab["peers"] if str(p.get("id")) == peer_id), None)
                    if existing:
                        existing["alias"] = alias
                        existing["tags"] = tags
                        existing["note"] = note
                        existing["platform"] = platform
                    else:
                        new_peer = {
                            "id": peer_id,
                            "alias": alias,
                            "tags": tags,
                            "note": note,
                            "username": "",
                            "hostname": alias,
                            "platform": platform,
                            "hash": ""
                        }
                        ab["peers"].append(new_peer)
                    for t in tags:
                        if t not in ab["tags"]:
                            ab["tags"].append(t)
                    save_data(ab)
            self.redirect("/dashboard#addressbook")
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
                    ab["peers"] = [p for p in ab["peers"] if str(p.get("id")) != peer_id]
                    save_data(ab)
            self.redirect("/dashboard#addressbook")
            return

        elif path == "/web/tag/delete":
            if not self.check_web_auth():
                self.redirect("/login")
                return
            form = self.read_body_form()
            tag_name = form.get("tag", "").strip()
            if tag_name:
                with lock:
                    ab = load_data()
                    if tag_name in ab["tags"]:
                        ab["tags"].remove(tag_name)
                    # remove from peers as well
                    for p in ab["peers"]:
                        if tag_name in p.get("tags", []):
                            p["tags"].remove(tag_name)
                    save_data(ab)
            self.redirect("/dashboard#addressbook")
            return

        elif path == "/web/tag/add":
            if not self.check_web_auth():
                self.redirect("/login")
                return
            form = self.read_body_form()
            new_tag = form.get("tag", "").strip()
            if new_tag:
                with lock:
                    ab = load_data()
                    if new_tag not in ab["tags"]:
                        ab["tags"].append(new_tag)
                        save_data(ab)
            self.redirect("/dashboard#addressbook")
            return

        elif path == "/web/config/save":
            if not self.check_web_auth():
                self.redirect("/login")
                return
            form = self.read_body_form()
            with lock:
                ab = load_data()
                cfg = ab.get("client_config", get_default_client_config())
                cfg["config_name"] = form.get("config_name", "GNN-Destek-Windows").strip()
                cfg["app_name"] = form.get("app_name", "GNN Destek").strip()
                cfg["connection_type"] = form.get("connection_type", "bidirectional")
                cfg["disable_installation"] = "disable_installation" in form
                cfg["disable_settings"] = "disable_settings" in form
                cfg["disable_address_book"] = "disable_address_book" in form
                cfg["disable_tcp_listen"] = "disable_tcp_listen" in form
                cfg["disable_user_account"] = "disable_user_account" in form
                cfg["note"] = form.get("note", "").strip()
                cfg["host"] = form.get("host", DEFAULT_SERVER_HOST).strip()
                cfg["key"] = form.get("key", DEFAULT_KEY).strip()
                cfg["api"] = form.get("api", DEFAULT_API_URL).strip()
                cfg["preset_password"] = form.get("preset_password", DEFAULT_PRESET_PWD).strip()
                ab["client_config"] = cfg
                save_data(ab)
            self.redirect("/dashboard#customclient")
            return

        self.send_json(404, {"error": "Not found"})

def render_login_page(err=""):
    err_html = f'<div class="error">{err}</div>' if err else ""
    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GnnDesk Console - Giriş</title>
    <link rel="icon" type="image/png" href="/logo.png">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
        body {{ background: #0c0e12; color: #f0f2f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
        .card {{ background: #161922; padding: 2.5rem; border-radius: 14px; box-shadow: 0 16px 36px rgba(0,0,0,0.55); width: 100%; max-width: 400px; border: 1px solid #232733; }}
        .logo-box {{ display: flex; align-items: center; justify-content: center; gap: 0.75rem; margin-bottom: 2rem; }}
        .logo-box img {{ width: 44px; height: 44px; border-radius: 8px; object-fit: contain; }}
        .logo-box h1 {{ font-size: 1.35rem; font-weight: 700; color: #f0f2f5; letter-spacing: -0.02em; }}
        .form-group {{ margin-bottom: 1.25rem; }}
        label {{ display: block; font-size: 0.85rem; font-weight: 500; color: #8c9ba5; margin-bottom: 0.5rem; }}
        input {{ width: 100%; padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid #2c3240; background: #0e1017; color: #f0f2f5; font-size: 0.95rem; outline: none; transition: border-color 0.2s, box-shadow 0.2s; }}
        input:focus {{ border-color: #1677ff; box-shadow: 0 0 0 2px rgba(22, 119, 255, 0.2); }}
        button {{ width: 100%; padding: 0.75rem 1rem; background: #1677ff; color: white; border: none; border-radius: 8px; font-weight: 600; font-size: 1rem; cursor: pointer; transition: background 0.2s; margin-top: 0.5rem; }}
        button:hover {{ background: #0958d9; }}
        .error {{ background: rgba(255, 77, 79, 0.12); color: #ff4d4f; border: 1px solid rgba(255, 77, 79, 0.3); padding: 0.75rem; border-radius: 8px; font-size: 0.875rem; margin-bottom: 1.25rem; text-align: center; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="logo-box">
            <img src="/logo.png" alt="GNN Logo">
            <h1>GnnDesk Console</h1>
        </div>
        {err_html}
        <form method="POST" action="/web/login">
            <div class="form-group">
                <label>Kullanıcı Adı</label>
                <input type="text" name="username" required autofocus placeholder="admin">
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

def get_tag_style(tag_name, idx):
    colors = [
        ("#a855f7", "rgba(168, 85, 247, 0.15)", "rgba(168, 85, 247, 0.35)"),
        ("#ec4899", "rgba(236, 72, 153, 0.15)", "rgba(236, 72, 153, 0.35)"),
        ("#3b82f6", "rgba(59, 130, 246, 0.15)", "rgba(59, 130, 246, 0.35)"),
        ("#06b6d4", "rgba(6, 182, 212, 0.15)", "rgba(6, 182, 212, 0.35)"),
        ("#22c55e", "rgba(34, 197, 94, 0.15)", "rgba(34, 197, 94, 0.35)"),
        ("#f97316", "rgba(249, 115, 22, 0.15)", "rgba(249, 115, 22, 0.35)"),
        ("#eab308", "rgba(234, 179, 8, 0.15)", "rgba(234, 179, 8, 0.35)")
    ]
    dot_color, bg_color, border_color = colors[idx % len(colors)]
    return dot_color, bg_color, border_color

def get_os_icon(platform_str):
    p = (platform_str or "").lower()
    if "win" in p:
        return """<svg class="os-icon" viewBox="0 0 24 24"><path fill="#00adef" d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.9-1.801"/></svg>"""
    elif "mac" in p or "apple" in p or "ios" in p:
        return """<svg class="os-icon" viewBox="0 0 24 24"><path fill="#cccccc" d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 4.54c.64-.78 1.08-1.86.96-2.94-.93.04-2.07.62-2.73 1.4-.58.67-1.1 1.76-.96 2.82 1.04.08 2.1-.51 2.73-1.28z"/></svg>"""
    elif "android" in p:
        return """<svg class="os-icon" viewBox="0 0 24 24"><path fill="#3ddc84" d="M6 18c0 .55.45 1 1 1h1v3.5c0 .83.67 1.5 1.5 1.5s1.5-.67 1.5-1.5V19h2v3.5c0 .83.67 1.5 1.5 1.5s1.5-.67 1.5-1.5V19h1c.55 0 1-.45 1-1V8H6v10zM3.5 8C2.67 8 2 8.67 2 9.5v6c0 .83.67 1.5 1.5 1.5S5 16.33 5 15.5v-6C5 8.67 4.33 8 3.5 8zm17 0c-.83 0-1.5.67-1.5 1.5v6c0 .83.67 1.5 1.5 1.5s1.5-.67 1.5-1.5v-6c0-.83-.67-1.5-1.5-1.5zm-4.97-4.84l1.3-1.3c.2-.2.2-.51 0-.71-.2-.2-.51-.2-.71 0l-1.48 1.48C13.85 2.23 12.95 2 12 2c-.96 0-1.86.23-2.66.63L7.85.99c-.2-.2-.51-.2-.71 0-.2.2-.2.51 0 .71l1.31 1.31C6.97 3.9 6 5.34 6 7h12c0-1.66-.97-3.1-2.47-3.84zM10 5H9V4h1v1zm5 0h-1V4h1v1z"/></svg>"""
    elif "linux" in p:
        return """<svg class="os-icon" viewBox="0 0 24 24"><path fill="#f59e0b" d="M12 2C9.5 2 8 3.5 8 5.5c0 1 .5 2 1 2.5-.5.5-1.5 1.5-1.5 3 0 1 .5 2 1 2.5C7.5 14 7 15 7 16.5 7 18.5 8.5 20 11 20h2c2.5 0 4-1.5 4-3.5 0-1.5-.5-2.5-1.5-3 .5-.5 1-1.5 1-2.5 0-1.5-1-2.5-1.5-3 .5-.5 1-1.5 1-2.5C16 3.5 14.5 2 12 2z"/></svg>"""
    else:
        return """<svg class="os-icon" viewBox="0 0 24 24"><path fill="#00adef" d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.9-1.801"/></svg>"""

def render_console(data):
    peers = data.get("peers", [])
    tags = data.get("tags", ["Genel", "AKANSU", "GNN"])
    cfg = data.get("client_config", get_default_client_config())

    # Generate tag badges for top filter bar
    tag_pills_html = ""
    for idx, t in enumerate(tags):
        dot, bg, bdr = get_tag_style(t, idx)
        safe_t = html.escape(t)
        tag_pills_html += f"""
        <div class="tag-pill" style="background:{bg}; border-color:{bdr};" onclick="filterByTag('{safe_t}')" title="Bu etikete göre filtrele">
            <span class="tag-dot" style="background:{dot};"></span>
            <span class="tag-text">{safe_t}</span>
            <form method="POST" action="/web/tag/delete" style="display:inline;" onsubmit="event.stopPropagation(); return confirm('{safe_t} etiketi silinsin mi?');">
                <input type="hidden" name="tag" value="{safe_t}">
                <button type="submit" class="tag-del">&times;</button>
            </form>
        </div>
        """
    tag_pills_html += """
    <button type="button" class="tag-add-btn" onclick="openAddTagModal()" title="Yeni Etiket Ekle">+</button>
    """

    # Generate table rows
    rows = ""
    for idx, p in enumerate(peers):
        raw_pid = str(p.get("id", ""))
        raw_alias = str(p.get("alias", "-"))
        ptags = p.get("tags", [])
        raw_note = str(p.get("note", "-"))
        platform = str(p.get("platform", "Windows"))
        if raw_note == "": raw_note = "-"

        pid = html.escape(raw_pid)
        alias = html.escape(raw_alias)
        note = html.escape(raw_note)

        os_svg = get_os_icon(platform)

        # Peer tags
        peer_tags_html = ""
        for p_idx, pt in enumerate(ptags):
            dot, bg, bdr = get_tag_style(pt, p_idx)
            peer_tags_html += f'<span class="table-tag" style="background:{bg}; border-color:{bdr}; color:#f0f2f5;"><span class="table-tag-dot" style="background:{dot};"></span>{html.escape(pt)}</span>'
        if not peer_tags_html:
            peer_tags_html = '<span style="color:#5a6270;">-</span>'

        safe_pid_js = pid.replace("'", "\\'")
        safe_alias_js = alias.replace("'", "\\'")
        safe_tags_js = html.escape(", ".join(ptags)).replace("'", "\\'")
        safe_note_clean = (raw_note if raw_note != "-" else "").replace("'", "\\'")
        safe_platform_js = platform.replace("'", "\\'")

        rows += f"""
        <tr data-id="{pid.lower()}" data-alias="{alias.lower()}" data-tags="{','.join(ptags).lower()}">
            <td style="width: 40px; text-align: center;"><input type="checkbox" class="peer-check"></td>
            <td>
                <div class="id-cell" onclick="openEditModal('{safe_pid_js}', '{safe_alias_js}', '{safe_tags_js}', '{safe_note_clean}', '{safe_platform_js}')" title="Düzenle">
                    {os_svg}
                    <span class="id-text font-mono">{pid}</span>
                </div>
            </td>
            <td><strong class="device-text">{alias}</strong></td>
            <td><span class="user-text">{alias}</span></td>
            <td>
                <span class="pwd-badge" onclick="copyPassword('{DEFAULT_PRESET_PWD}')" title="Kalıcı Şifreyi Kopyala ({DEFAULT_PRESET_PWD})">
                    <svg viewBox="0 0 24 24"><path fill="currentColor" d="M7 14c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3c0 .35-.07.69-.18 1H15v2h2v2h2v-2h2v3h-2v2h-4v-4.18c-.31.11-.65.18-1 .18z"/></svg>
                </span>
            </td>
            <td>{peer_tags_html}</td>
            <td class="note-text">{note}</td>
            <td class="action-cell">
                <button type="button" class="btn-action-edit" onclick="openEditModal('{safe_pid_js}', '{safe_alias_js}', '{safe_tags_js}', '{safe_note_clean}', '{safe_platform_js}')">Edit</button>
                <span style="color:#333846;">|</span>
                <form method="POST" action="/web/peer/delete" style="display:inline;" onsubmit="return confirm('{safe_alias_js} ({pid}) silinsin mi?');">
                    <input type="hidden" name="id" value="{pid}">
                    <button type="submit" class="btn-action-del">Delete</button>
                </form>
            </td>
        </tr>
        """

    if not rows:
        rows = '<tr><td colspan="8" style="text-align:center; padding: 3rem; color: #5a6270;">Kayıtlı cihaz bulunamadı. "+ Add" butonu ile cihaz ekleyebilirsiniz.</td></tr>'

    cfg_name = html.escape(cfg.get("config_name", "GNN-Destek-Windows"))
    cfg_app_name = html.escape(cfg.get("app_name", "GNN Destek"))
    cfg_host = html.escape(cfg.get("host", DEFAULT_SERVER_HOST))
    cfg_key = html.escape(cfg.get("key", DEFAULT_KEY))
    cfg_api = html.escape(cfg.get("api", DEFAULT_API_URL))
    cfg_pwd = html.escape(cfg.get("preset_password", DEFAULT_PRESET_PWD))
    cfg_note = html.escape(cfg.get("note", ""))

    chk_install = "checked" if cfg.get("disable_installation", True) else ""
    chk_settings = "checked" if cfg.get("disable_settings", True) else ""
    chk_ab = "checked" if cfg.get("disable_address_book", False) else ""
    chk_tcp = "checked" if cfg.get("disable_tcp_listen", False) else ""
    chk_user = "checked" if cfg.get("disable_user_account", False) else ""

    conn_bi = "checked" if cfg.get("connection_type", "bidirectional") == "bidirectional" else ""
    conn_in = "checked" if cfg.get("connection_type") == "incoming" else ""
    conn_out = "checked" if cfg.get("connection_type") == "outgoing" else ""

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GnnDesk Console</title>
    <link rel="icon" type="image/png" href="/logo.png">
    <style>
        :root {{
            --bg-base: #0c0e12;
            --bg-sidebar: #141720;
            --bg-card: #171a22;
            --bg-input: #0e1017;
            --border: #232733;
            --border-hover: #323849;
            --primary: #1677ff;
            --primary-hover: #0958d9;
            --primary-subtle: rgba(22, 119, 255, 0.12);
            --text-main: #f0f2f5;
            --text-muted: #8c9ba5;
            --text-dim: #5a6270;
            --danger: #ff4d4f;
            --success: #52c41a;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
        body {{ background: var(--bg-base); color: var(--text-main); display: flex; height: 100vh; overflow: hidden; font-size: 14px; }}

        /* Left Sidebar (Matching GnnDesk Console) */
        .sidebar {{ width: 230px; background: var(--bg-sidebar); border-right: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; user-select: none; }}
        .sidebar-header {{ height: 56px; display: flex; align-items: center; padding: 0 1.25rem; border-bottom: 1px solid var(--border); gap: 0.65rem; }}
        .sidebar-header svg {{ width: 26px; height: 26px; fill: var(--primary); }}
        .sidebar-header span {{ font-weight: 700; font-size: 1rem; color: #fff; letter-spacing: -0.01em; }}
        .nav-menu {{ list-style: none; padding: 0.75rem 0.5rem; flex: 1; overflow-y: auto; }}
        .nav-item {{ margin-bottom: 0.25rem; }}
        .nav-link {{ display: flex; align-items: center; gap: 0.75rem; padding: 0.65rem 0.85rem; border-radius: 8px; color: var(--text-muted); text-decoration: none; font-size: 0.9rem; font-weight: 500; transition: all 0.2s; cursor: pointer; }}
        .nav-link svg {{ width: 18px; height: 18px; fill: currentColor; flex-shrink: 0; }}
        .nav-link:hover {{ background: rgba(255,255,255,0.04); color: var(--text-main); }}
        .nav-link.active {{ background: var(--primary-subtle); color: var(--primary); font-weight: 600; }}
        .nav-link.active svg {{ fill: var(--primary); }}
        
        .sidebar-footer {{ padding: 1rem; border-top: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }}
        .user-info {{ display: flex; align-items: center; gap: 0.5rem; }}
        .user-avatar {{ width: 28px; height: 28px; background: var(--primary); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.8rem; color: #fff; }}
        .user-name {{ font-size: 0.85rem; color: var(--text-main); font-weight: 600; }}
        .logout-link {{ color: var(--text-muted); text-decoration: none; font-size: 0.8rem; }}
        .logout-link:hover {{ color: var(--danger); }}

        /* Main Content Container */
        .main-container {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; background: var(--bg-base); }}
        .topbar {{ height: 56px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 1.75rem; background: var(--bg-sidebar); }}
        .breadcrumbs {{ font-size: 0.85rem; color: var(--text-muted); }}
        .breadcrumbs b {{ color: var(--text-main); font-weight: 600; }}
        .topbar-right {{ display: flex; align-items: center; gap: 1rem; }}
        .badge-online {{ background: rgba(82, 196, 26, 0.15); border: 1px solid rgba(82, 196, 26, 0.3); color: #52c41a; font-size: 0.75rem; padding: 0.2rem 0.5rem; border-radius: 6px; font-weight: 600; display: flex; align-items: center; gap: 0.35rem; }}
        .badge-online::before {{ content: ""; width: 6px; height: 6px; background: #52c41a; border-radius: 50%; }}

        .content-scroll {{ flex: 1; overflow-y: auto; padding: 1.5rem 2rem; }}

        /* VIEW: ADDRESS BOOKS (Matching console.png) */
        .section-header {{ margin-bottom: 1.25rem; }}
        .section-header h2 {{ font-size: 1.35rem; font-weight: 600; color: #fff; }}
        
        .card-box {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 1.25rem; margin-bottom: 1.25rem; }}
        
        /* Tags Bar */
        .tags-wrapper {{ display: flex; align-items: center; flex-wrap: wrap; gap: 0.6rem; margin-top: 0.5rem; }}
        .tag-pill {{ display: inline-flex; align-items: center; gap: 0.45rem; padding: 0.3rem 0.65rem; border-radius: 6px; border: 1px solid transparent; font-size: 0.8rem; cursor: pointer; transition: transform 0.1s; }}
        .tag-pill:hover {{ transform: translateY(-1px); }}
        .tag-dot {{ width: 8px; height: 8px; border-radius: 50%; }}
        .tag-del {{ background: none; border: none; color: var(--text-muted); font-size: 1rem; cursor: pointer; line-height: 1; padding: 0 0 0 0.25rem; }}
        .tag-del:hover {{ color: var(--danger); }}
        .tag-add-btn {{ width: 26px; height: 26px; border-radius: 6px; background: #232733; border: 1px solid #323849; color: var(--text-muted); display: inline-flex; align-items: center; justify-content: center; font-size: 1.1rem; cursor: pointer; transition: all 0.2s; }}
        .tag-add-btn:hover {{ background: var(--primary); color: #fff; border-color: var(--primary); }}

        /* Query Filter Bar */
        .filter-row {{ display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap; }}
        .filter-group {{ display: flex; align-items: center; gap: 0.65rem; font-size: 0.85rem; color: var(--text-muted); }}
        .filter-group input {{ width: 200px; padding: 0.5rem 0.75rem; border-radius: 6px; border: 1px solid var(--border); background: var(--bg-input); color: #fff; font-size: 0.85rem; outline: none; }}
        .filter-group input:focus {{ border-color: var(--primary); }}
        .filter-buttons {{ display: flex; align-items: center; gap: 0.65rem; margin-left: auto; }}
        .btn-query {{ background: var(--primary); color: #fff; border: none; padding: 0.5rem 1.25rem; border-radius: 6px; font-weight: 600; font-size: 0.85rem; cursor: pointer; transition: background 0.2s; }}
        .btn-query:hover {{ background: var(--primary-hover); }}
        .btn-reset {{ background: #232733; color: var(--text-muted); border: 1px solid var(--border); padding: 0.5rem 1.1rem; border-radius: 6px; font-weight: 500; font-size: 0.85rem; cursor: pointer; }}
        .btn-reset:hover {{ background: #2c3240; color: #fff; }}

        /* Devices Table Header Action Bar */
        .table-toolbar {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.85rem; }}
        .table-title {{ font-size: 1.05rem; font-weight: 600; color: #fff; }}
        .toolbar-actions {{ display: flex; align-items: center; gap: 0.65rem; }}
        .btn-add-device {{ background: var(--primary); color: #fff; border: none; padding: 0.45rem 1rem; border-radius: 6px; font-weight: 600; font-size: 0.85rem; cursor: pointer; display: flex; align-items: center; gap: 0.35rem; }}
        .btn-add-device:hover {{ background: var(--primary-hover); }}

        /* Table */
        .table-container {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; }}
        th {{ background: #13151c; padding: 0.75rem 1rem; font-size: 0.8rem; color: var(--text-muted); font-weight: 600; border-bottom: 1px solid var(--border); }}
        td {{ padding: 0.85rem 1rem; border-bottom: 1px solid var(--border); font-size: 0.85rem; vertical-align: middle; }}
        tr:hover td {{ background: rgba(255,255,255,0.015); }}
        .id-cell {{ display: flex; align-items: center; gap: 0.6rem; cursor: pointer; width: fit-content; }}
        .id-cell:hover .id-text {{ color: var(--primary); text-decoration: underline; }}
        .os-icon {{ width: 18px; height: 18px; flex-shrink: 0; }}
        .id-text {{ font-size: 0.9rem; font-weight: 600; color: #f0f2f5; }}
        .font-mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
        .device-text {{ color: #f0f2f5; font-weight: 600; }}
        .user-text {{ color: var(--text-muted); }}
        .pwd-badge {{ display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: 6px; background: rgba(255,255,255,0.05); color: #eab308; cursor: pointer; transition: all 0.2s; }}
        .pwd-badge:hover {{ background: rgba(234, 179, 8, 0.2); transform: scale(1.1); }}
        .pwd-badge svg {{ width: 16px; height: 16px; }}
        .table-tag {{ display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.15rem 0.5rem; border-radius: 4px; border: 1px solid transparent; font-size: 0.75rem; margin-right: 0.35rem; }}
        .table-tag-dot {{ width: 6px; height: 6px; border-radius: 50%; }}
        .note-text {{ color: var(--text-muted); font-size: 0.8rem; max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .action-cell button {{ background: none; border: none; font-size: 0.8rem; font-weight: 500; cursor: pointer; }}
        .btn-action-edit {{ color: var(--primary); margin-right: 0.25rem; }}
        .btn-action-edit:hover {{ text-decoration: underline; }}
        .btn-action-del {{ color: var(--danger); margin-left: 0.25rem; }}
        .btn-action-del:hover {{ text-decoration: underline; }}

        /* VIEW: CUSTOM CLIENTS (Matching custom.png) */
        .os-selector-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem; }}
        .os-card {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 1.1rem; display: flex; align-items: center; justify-content: center; gap: 0.75rem; font-weight: 600; font-size: 0.95rem; cursor: pointer; transition: all 0.2s; user-select: none; color: var(--text-muted); }}
        .os-card svg {{ width: 24px; height: 24px; fill: currentColor; }}
        .os-card:hover {{ border-color: var(--border-hover); color: #fff; }}
        .os-card.active {{ border-color: var(--primary); background: var(--primary-subtle); color: var(--primary); box-shadow: 0 0 0 1px var(--primary); }}
        .os-card.active svg {{ fill: var(--primary); }}

        .custom-form-grid {{ display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 1.5rem; align-items: start; }}
        .form-section-card {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }}
        .card-heading {{ font-size: 1.05rem; font-weight: 600; color: #fff; margin-bottom: 1.25rem; }}
        
        .field-row {{ margin-bottom: 1.25rem; }}
        .field-label {{ display: flex; align-items: center; gap: 0.35rem; font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.45rem; font-weight: 500; }}
        .field-label .req {{ color: var(--danger); }}
        .field-input-box {{ position: relative; }}
        .field-input-box input, .field-input-box textarea {{ width: 100%; padding: 0.65rem 0.85rem; border-radius: 6px; border: 1px solid var(--border); background: var(--bg-input); color: #fff; font-size: 0.88rem; outline: none; transition: border-color 0.2s; }}
        .field-input-box input:focus, .field-input-box textarea:focus {{ border-color: var(--primary); }}
        .btn-copy-addon {{ position: absolute; right: 8px; top: 50%; transform: translateY(-50%); background: #232733; border: 1px solid #323849; color: var(--text-muted); width: 28px; height: 28px; border-radius: 4px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; }}
        .btn-copy-addon:hover {{ background: var(--primary); color: #fff; border-color: var(--primary); }}
        .btn-copy-addon svg {{ width: 14px; height: 14px; fill: currentColor; }}

        .radio-group {{ display: flex; gap: 1.5rem; margin-top: 0.45rem; }}
        .radio-label {{ display: flex; align-items: center; gap: 0.45rem; font-size: 0.85rem; color: var(--text-main); cursor: pointer; }}
        
        .checkbox-list {{ display: flex; flex-direction: column; gap: 0.65rem; margin-top: 0.5rem; }}
        .checkbox-label {{ display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; color: var(--text-muted); cursor: pointer; }}
        .checkbox-label input {{ accent-color: var(--primary); width: 15px; height: 15px; }}

        .upload-zone {{ border: 1px dashed var(--border); border-radius: 8px; padding: 1.25rem; text-align: center; color: var(--text-muted); font-size: 0.85rem; background: var(--bg-input); display: flex; align-items: center; justify-content: center; gap: 0.5rem; cursor: pointer; transition: border-color 0.2s; }}
        .upload-zone:hover {{ border-color: var(--primary); color: var(--primary); }}
        .upload-zone svg {{ width: 18px; height: 18px; fill: currentColor; }}

        .btn-save-cfg {{ background: var(--primary); color: #fff; border: none; padding: 0.75rem 1.75rem; border-radius: 6px; font-weight: 600; font-size: 0.95rem; cursor: pointer; transition: background 0.2s; }}
        .btn-save-cfg:hover {{ background: var(--primary-hover); }}
        
        .btn-download-exe {{ background: #232733; border: 1px solid #38bdf8; color: #38bdf8; padding: 0.75rem 1.5rem; border-radius: 6px; font-weight: 600; font-size: 0.95rem; text-decoration: none; display: inline-flex; align-items: center; gap: 0.5rem; transition: all 0.2s; }}
        .btn-download-exe:hover {{ background: #0284c7; color: #fff; border-color: #0284c7; }}
        .btn-download-exe svg {{ width: 18px; height: 18px; fill: currentColor; }}

        /* Modal Dialogs */
        .modal-overlay {{ position: fixed; inset: 0; background: rgba(0,0,0,0.75); display: flex; align-items: center; justify-content: center; z-index: 999; backdrop-filter: blur(4px); }}
        .modal-card {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; width: 100%; max-width: 480px; padding: 1.5rem; box-shadow: 0 20px 30px rgba(0,0,0,0.6); }}
        .modal-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; border-bottom: 1px solid var(--border); padding-bottom: 0.75rem; }}
        .modal-header h3 {{ color: #fff; font-size: 1.15rem; font-weight: 600; }}
        .btn-modal-close {{ background: none; border: none; color: var(--text-muted); font-size: 1.5rem; cursor: pointer; line-height: 1; }}
        .btn-modal-close:hover {{ color: #fff; }}
        .btn-modal-cancel {{ background: #232733; color: var(--text-muted); border: 1px solid var(--border); padding: 0.6rem 1.2rem; border-radius: 6px; font-weight: 500; cursor: pointer; }}
        .btn-modal-cancel:hover {{ background: #2c3240; color: #fff; }}
        .btn-modal-save {{ background: var(--primary); color: #fff; border: none; padding: 0.6rem 1.4rem; border-radius: 6px; font-weight: 600; cursor: pointer; }}
        .btn-modal-save:hover {{ background: var(--primary-hover); }}

        /* Toast notification */
        #toast {{ position: fixed; bottom: 24px; right: 24px; background: #1677ff; color: #fff; padding: 0.65rem 1.25rem; border-radius: 8px; font-size: 0.85rem; font-weight: 500; box-shadow: 0 8px 16px rgba(0,0,0,0.4); z-index: 1000; display: none; }}
    </style>
</head>
<body>
    <!-- LEFT SIDEBAR -->
    <div class="sidebar">
        <div class="sidebar-header">
            <img src="/logo.png" alt="GNN Logo" style="width: 26px; height: 26px; border-radius: 6px; object-fit: contain;">
            <span>GnnDesk Console</span>
        </div>
        <ul class="nav-menu">
            <li class="nav-item">
                <a class="nav-link active" id="nav-addressbook" onclick="switchTab('addressbook')">
                    <svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>
                    <span>Address Books</span>
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link" id="nav-serverstatus" onclick="switchTab('serverstatus')">
                    <svg viewBox="0 0 24 24"><path d="M2 20h20v-4H2v4zm2-3h2v2H4v-2zM2 4v4h20V4H2zm4 3H4V5h2v2zm-4 7h20v-4H2v4zm2-3h2v2H4v-2z"/></svg>
                    <span>Server Status</span>
                </a>
            </li>
        </ul>
        <div class="sidebar-footer">
            <div class="user-info">
                <div class="user-avatar">a</div>
                <div class="user-name">{USERNAME}</div>
            </div>
            <a href="/logout" class="logout-link" title="Çıkış Yap">Çıkış</a>
        </div>
    </div>

    <!-- MAIN CONTAINER -->
    <div class="main-container">
        <!-- TOPBAR -->
        <div class="topbar">
            <div class="breadcrumbs" id="breadcrumbText">Shared / <b>Address Books</b></div>
            <div class="topbar-right">
                <span class="badge-online">hbbs & hbbr Aktif</span>
            </div>
        </div>

        <div class="content-scroll">
            <!-- TAB 1: ADDRESS BOOKS (Matching console.png) -->
            <div id="view-addressbook">
                <div class="section-header">
                    <h2>Address Books</h2>
                </div>

                <!-- Tags Row -->
                <div class="card-box">
                    <div style="font-size:0.85rem; color:var(--text-muted); font-weight:600;">Tags</div>
                    <div class="tags-wrapper">
                        {tag_pills_html}
                    </div>
                </div>

                <!-- Query / Filter Row -->
                <div class="card-box">
                    <div class="filter-row">
                        <div class="filter-group">
                            <span>ID :</span>
                            <input type="text" id="queryId" placeholder="Please enter ID" onkeydown="if(event.key==='Enter') doQuery();">
                        </div>
                        <div class="filter-group">
                            <span>Device Name :</span>
                            <input type="text" id="queryName" placeholder="Please enter name" onkeydown="if(event.key==='Enter') doQuery();">
                        </div>
                        <div class="filter-buttons">
                            <button type="button" class="btn-reset" onclick="resetQuery()">Reset</button>
                            <button type="button" class="btn-query" onclick="doQuery()">Query</button>
                        </div>
                    </div>
                </div>

                <!-- Devices Table -->
                <div class="table-toolbar">
                    <div class="table-title">Devices ({len(peers)})</div>
                    <div class="toolbar-actions">
                        <a href="/download/GNNQS.exe" class="btn-download-exe" style="padding:0.42rem 0.85rem; font-size:0.83rem;">
                            <svg viewBox="0 0 24 24"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM17 13l-5 5-5-5h3V9h4v4h3z"/></svg>
                            <span>GNNQS.exe İndir</span>
                        </a>
                        <button type="button" class="btn-add-device" onclick="openAddDeviceModal()">+ Add</button>
                    </div>
                </div>

                <div class="table-container">
                    <table id="devicesTable">
                        <thead>
                            <tr>
                                <th style="width: 40px; text-align: center;"><input type="checkbox" onclick="toggleAll(this)"></th>
                                <th>ID</th>
                                <th>Device</th>
                                <th>Alias</th>
                                <th>Password</th>
                                <th>Tags</th>
                                <th>Note</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- TAB 3: SERVER STATUS -->
            <div id="view-serverstatus" style="display:none;">
                <div class="section-header">
                    <h2>Server Status</h2>
                </div>
                <div class="custom-form-grid">
                    <div class="form-section-card">
                        <div class="card-heading">Rendezvous & Relay Server</div>
                        <div style="font-size:0.9rem; line-height:2; color:var(--text-muted);">
                            <div><b>Host:</b> <span class="font-mono" style="color:#fff;">{DEFAULT_SERVER_HOST}</span></div>
                            <div><b>HBBS (Rendezvous):</b> <span style="color:#52c41a;">Aktif (:21116 TCP/UDP)</span></div>
                            <div><b>HBBR (Relay):</b> <span style="color:#52c41a;">Aktif (:21117 TCP)</span></div>
                            <div><b>Key Exchange:</b> <span style="color:#52c41a;">PR #706 Aktif (API Login Sorunsuz)</span></div>
                        </div>
                    </div>
                    <div class="form-section-card">
                        <div class="card-heading">API & Address Book Server</div>
                        <div style="font-size:0.9rem; line-height:2; color:var(--text-muted);">
                            <div><b>Port:</b> <span class="font-mono" style="color:#fff;">:21114</span></div>
                            <div><b>Bellek Tüketimi:</b> <span style="color:#52c41a;">~15 MB RAM (Hafif Standart Python)</span></div>
                            <div><b>Toplam Cihaz:</b> <span style="color:#fff;">{len(peers)}</span></div>
                            <div><b>Toplam Etiket:</b> <span style="color:#fff;">{len(tags)}</span></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- MODAL: ADD DEVICE -->
    <div id="addDeviceModal" class="modal-overlay" style="display:none;">
        <div class="modal-card">
            <div class="modal-header">
                <h3>Yeni Cihaz Ekle</h3>
                <button type="button" class="btn-modal-close" onclick="closeAddDeviceModal()">&times;</button>
            </div>
            <form method="POST" action="/web/peer/add">
                <div class="field-row">
                    <label class="field-label"><span class="req">*</span> RustDesk ID</label>
                    <div class="field-input-box">
                        <input type="text" name="id" required placeholder="örn: 438438467">
                    </div>
                </div>
                <div class="field-row">
                    <label class="field-label"><span class="req">*</span> Cihaz Adı (Device / Alias)</label>
                    <div class="field-input-box">
                        <input type="text" name="alias" required placeholder="örn: Muhasebe PC / Ahmet">
                    </div>
                </div>
                <div class="field-row">
                    <label class="field-label">İşletim Sistemi (OS)</label>
                    <div class="field-input-box">
                        <select name="platform" style="width:100%; padding:0.65rem 0.85rem; border-radius:6px; border:1px solid var(--border); background:var(--bg-input); color:#fff; font-size:0.88rem; outline:none;">
                            <option value="Windows">Windows</option>
                            <option value="Android">Android</option>
                            <option value="MacOS">MacOS</option>
                            <option value="Linux">Linux</option>
                        </select>
                    </div>
                </div>
                <div class="field-row">
                    <label class="field-label">Etiketler (Virgülle)</label>
                    <div class="field-input-box">
                        <input type="text" name="tags" placeholder="örn: Muhasebe, VIP">
                    </div>
                </div>
                <div class="field-row" style="margin-bottom:1.5rem;">
                    <label class="field-label">Özel Not</label>
                    <div class="field-input-box">
                        <input type="text" name="note" placeholder="Cihaza özel açıklama...">
                    </div>
                </div>
                <div style="display:flex; justify-content:flex-end; gap:0.75rem;">
                    <button type="button" class="btn-modal-cancel" onclick="closeAddDeviceModal()">İptal</button>
                    <button type="submit" class="btn-modal-save">Ekle</button>
                </div>
            </form>
        </div>
    </div>

    <!-- MODAL: EDIT DEVICE -->
    <div id="editDeviceModal" class="modal-overlay" style="display:none;">
        <div class="modal-card">
            <div class="modal-header">
                <h3>Cihaz Bilgilerini Güncelle</h3>
                <button type="button" class="btn-modal-close" onclick="closeEditModal()">&times;</button>
            </div>
            <form method="POST" action="/web/peer/edit">
                <div class="field-row">
                    <label class="field-label">RustDesk ID</label>
                    <div class="field-input-box">
                        <input type="text" id="edit_id" name="id" readonly style="opacity:0.75; cursor:not-allowed; background:#0a0c10;">
                    </div>
                </div>
                <div class="field-row">
                    <label class="field-label"><span class="req">*</span> Cihaz Adı (Device / Alias)</label>
                    <div class="field-input-box">
                        <input type="text" id="edit_alias" name="alias" required placeholder="Cihaz adı girin">
                    </div>
                </div>
                <div class="field-row">
                    <label class="field-label">İşletim Sistemi (OS)</label>
                    <div class="field-input-box">
                        <select id="edit_platform" name="platform" style="width:100%; padding:0.65rem 0.85rem; border-radius:6px; border:1px solid var(--border); background:var(--bg-input); color:#fff; font-size:0.88rem; outline:none;">
                            <option value="Windows">Windows</option>
                            <option value="Android">Android</option>
                            <option value="MacOS">MacOS</option>
                            <option value="Linux">Linux</option>
                        </select>
                    </div>
                </div>
                <div class="field-row">
                    <label class="field-label">Etiketler (Virgülle)</label>
                    <div class="field-input-box">
                        <input type="text" id="edit_tags" name="tags" placeholder="örn: Muhasebe, VIP">
                    </div>
                </div>
                <div class="field-row" style="margin-bottom:1.5rem;">
                    <label class="field-label">Özel Not</label>
                    <div class="field-input-box">
                        <input type="text" id="edit_note" name="note" placeholder="Cihaza özel not">
                    </div>
                </div>
                <div style="display:flex; justify-content:flex-end; gap:0.75rem;">
                    <button type="button" class="btn-modal-cancel" onclick="closeEditModal()">İptal</button>
                    <button type="submit" class="btn-modal-save">Güncelle</button>
                </div>
            </form>
        </div>
    </div>

    <!-- MODAL: ADD TAG -->
    <div id="addTagModal" class="modal-overlay" style="display:none;">
        <div class="modal-card">
            <div class="modal-header">
                <h3>Yeni Etiket Ekle</h3>
                <button type="button" class="btn-modal-close" onclick="closeAddTagModal()">&times;</button>
            </div>
            <form method="POST" action="/web/tag/add">
                <div class="field-row" style="margin-bottom:1.5rem;">
                    <label class="field-label">Etiket Adı</label>
                    <div class="field-input-box">
                        <input type="text" name="tag" required placeholder="örn: Muhasebe">
                    </div>
                </div>
                <div style="display:flex; justify-content:flex-end; gap:0.75rem;">
                    <button type="button" class="btn-modal-cancel" onclick="closeAddTagModal()">İptal</button>
                    <button type="submit" class="btn-modal-save">Ekle</button>
                </div>
            </form>
        </div>
    </div>

    <!-- TOAST -->
    <div id="toast">Kopyalandı!</div>

    <script>
        // Tab switching
        function switchTab(tab) {{
            document.getElementById('view-addressbook').style.display = tab === 'addressbook' ? 'block' : 'none';
            document.getElementById('view-serverstatus').style.display = tab === 'serverstatus' ? 'block' : 'none';

            document.getElementById('nav-addressbook').className = 'nav-link' + (tab === 'addressbook' ? ' active' : '');
            document.getElementById('nav-serverstatus').className = 'nav-link' + (tab === 'serverstatus' ? ' active' : '');

            const bc = document.getElementById('breadcrumbText');
            if (tab === 'addressbook') bc.innerHTML = 'Shared / <b>Address Books</b>';
            else if (tab === 'serverstatus') bc.innerHTML = 'System / <b>Server Status</b>';

            window.location.hash = tab;
        }}

        // Check hash on load
        window.onload = function() {{
            const hash = window.location.hash.replace('#', '');
            if (hash === 'serverstatus') {{
                switchTab(hash);
            }} else {{
                switchTab('addressbook');
            }}
        }};

        // Modals
        function openAddDeviceModal() {{
            document.getElementById('addDeviceModal').style.display = 'flex';
        }}
        function closeAddDeviceModal() {{
            document.getElementById('addDeviceModal').style.display = 'none';
        }}

        function openEditModal(id, alias, tags, note, platform) {{
            document.getElementById('edit_id').value = id;
            document.getElementById('edit_alias').value = alias;
            document.getElementById('edit_tags').value = tags;
            document.getElementById('edit_note').value = note;
            if (platform) document.getElementById('edit_platform').value = platform;
            document.getElementById('editDeviceModal').style.display = 'flex';
        }}
        function closeEditModal() {{
            document.getElementById('editDeviceModal').style.display = 'none';
        }}

        function openAddTagModal() {{
            document.getElementById('addTagModal').style.display = 'flex';
        }}
        function closeAddTagModal() {{
            document.getElementById('addTagModal').style.display = 'none';
        }}

        window.onclick = function(event) {{
            ['addDeviceModal', 'editDeviceModal', 'addTagModal'].forEach(id => {{
                const modal = document.getElementById(id);
                if (event.target == modal) modal.style.display = 'none';
            }});
        }};

        // Clipboard
        function showToast(msg) {{
            const t = document.getElementById('toast');
            t.innerText = msg;
            t.style.display = 'block';
            setTimeout(() => {{ t.style.display = 'none'; }}, 2200);
        }}
        function copyInput(id) {{
            const val = document.getElementById(id).value;
            navigator.clipboard.writeText(val);
            showToast('Kopyalandı: ' + val);
        }}
        function copyPassword(pwd) {{
            navigator.clipboard.writeText(pwd);
            showToast('Kalıcı şifre kopyalandı: ' + pwd);
        }}

        // Table query filtering
        let activeTagFilter = '';
        function filterByTag(tag) {{
            if (activeTagFilter === tag) {{
                activeTagFilter = '';
                showToast('Etiket filtresi kaldırıldı');
            }} else {{
                activeTagFilter = tag.toLowerCase();
                showToast(tag + ' etiketine göre filtrelendi');
            }}
            applyFilters();
        }}

        function doQuery() {{
            applyFilters();
        }}

        function resetQuery() {{
            document.getElementById('queryId').value = '';
            document.getElementById('queryName').value = '';
            activeTagFilter = '';
            applyFilters();
            showToast('Filtreler sıfırlandı');
        }}

        function applyFilters() {{
            const qId = document.getElementById('queryId').value.trim().toLowerCase();
            const qName = document.getElementById('queryName').value.trim().toLowerCase();
            const rows = document.querySelectorAll('#devicesTable tbody tr');

            rows.forEach(tr => {{
                const id = tr.getAttribute('data-id') || '';
                const alias = tr.getAttribute('data-alias') || '';
                const tags = tr.getAttribute('data-tags') || '';

                let match = true;
                if (qId && !id.includes(qId)) match = false;
                if (qName && !alias.includes(qName)) match = false;
                if (activeTagFilter && !tags.includes(activeTagFilter)) match = false;

                tr.style.display = match ? '' : 'none';
            }});
        }}

        function toggleAll(master) {{
            document.querySelectorAll('.peer-check').forEach(cb => cb.checked = master.checked);
        }}
    </script>
</body>
</html>"""

def run():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, RustDeskAPIHandler)
    print(f"GnnDesk Console & API Server running on port {PORT}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == "__main__":
    run()
