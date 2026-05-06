"""
apps.trackerapp
~~~~~~~~~~~~~~~~~

Central Tracker Application for Decentralized Web Node architecture.
Only handles authentication and peer discovery. Does NOT contain PeerNode.
"""

import sys
import os
import json
import threading

from daemon.asynaprous import AsynapRous
from daemon.auth import (
    authenticate_request, authenticate_basic, authenticate_cookie,
    session_manager, build_login_success_response, USER_DB,
    register_user, change_password,
)
from daemon.utils import (
    decode_basic_auth, parse_cookies, get_timestamp, encode_basic_auth,
)

peer_tracker = {}
tracker_lock = threading.Lock()

def _parse_body(body_str):
    if not body_str or not body_str.strip():
        return {}
    try:
        return json.loads(body_str.strip())
    except json.JSONDecodeError:
        return {}

def _parse_headers_dict(headers_str):
    result = {}
    if not headers_str:
        return result
    try:
        if headers_str.startswith("{") or headers_str.startswith("{'"):
            import ast
            result = ast.literal_eval(headers_str)
            return result
    except Exception:
        pass
    for field in ["authorization", "cookie", "content-type", "host"]:
        idx = headers_str.lower().find("'" + field + "'")
        if idx == -1:
            idx = headers_str.lower().find('"' + field + '"')
        if idx >= 0:
            rest = headers_str[idx:]
            parts = rest.split(",", 1)
            kv = parts[0]
            if ":" in kv:
                val = kv.split(":", 1)[1].strip().strip("'\"} ")
                result[field] = val
    return result

def _auth_check(headers_str):
    from daemon.dictionary import CaseInsensitiveDict
    hdr = _parse_headers_dict(headers_str)
    ci_headers = CaseInsensitiveDict(hdr)
    username = authenticate_request(ci_headers)
    return username, hdr

def _json_response(data, status_code=200):
    return json.dumps(data).encode("utf-8")

def _error(msg, code=400):
    return json.dumps({"error": msg, "status": code}).encode("utf-8")

app = AsynapRous()

@app.route('/login', methods=['POST'])
def login(headers="", body=""):
    hdr = _parse_headers_dict(headers)
    auth_header = hdr.get("authorization", "")
    username = None

    if auth_header and auth_header.startswith("Basic "):
        encoded = auth_header[6:]
        user, pw = decode_basic_auth(encoded)
        if user and pw and USER_DB.get(user) == pw:
            username = user

    if not username:
        body_data = _parse_body(body)
        user = body_data.get("username", "")
        pw = body_data.get("password", "")
        if user and pw and USER_DB.get(user) == pw:
            username = user

    if not username:
        body = _json_response({"error": "Invalid credentials"})
        return (body, {"WWW-Authenticate": 'Basic realm="chat"'}, 401)

    session_id = session_manager.create_session(username)
    body = _json_response({
        "status": "success",
        "message": "Logged in as {}".format(username),
        "session_id": session_id,
    })
    return (body, {"Set-Cookie": "session_id={}; Path=/; HttpOnly".format(session_id)}, 200)

@app.route('/logout', methods=['POST'])
def logout(headers="", body=""):
    hdr = _parse_headers_dict(headers)
    sid = hdr.get("x-session-id", "")
    if not sid:
        cookie_str = hdr.get("cookie", "")
        cookies = parse_cookies(cookie_str)
        sid = cookies.get("session_id", "")
    if sid:
        session_manager.destroy_session(sid)
        return _json_response({"status": "logged_out"})
    return _json_response({"status": "no_active_session"})

@app.route('/users', methods=['GET'])
def list_users(headers="", body=""):
    from daemon.auth import _user_db_lock
    with _user_db_lock:
        users = [{"username": u, "password": p} for u, p in USER_DB.items()]
    return _json_response({"users": users, "count": len(users)})

@app.route('/register', methods=['POST'])
def register(headers="", body=""):
    body_data = _parse_body(body)
    username = body_data.get("username", "").strip()
    password = body_data.get("password", "")
    ok, msg = register_user(username, password)
    if ok:
        return _json_response({"status": "registered", "message": msg})
    return _json_response({"status": "error", "error": msg})

@app.route('/change-password', methods=['POST'])
def change_pwd(headers="", body=""):
    body_data = _parse_body(body)
    username = body_data.get("username", "").strip()
    old_pw = body_data.get("old_password", "")
    new_pw = body_data.get("new_password", "")
    ok, msg = change_password(username, old_pw, new_pw)
    if ok:
        return _json_response({"status": "changed", "message": msg})
    return _json_response({"status": "error", "error": msg})

@app.route('/submit-info', methods=['POST'])
def submit_info(headers="", body=""):
    body_data = _parse_body(body)
    peer_username = body_data.get("username", "anonymous")
    peer_ip = body_data.get("ip", "127.0.0.1")
    peer_port = body_data.get("port", 0)

    if not peer_port:
        return _error("Missing 'port' in request body")
    peer_port = int(peer_port)

    with tracker_lock:
        peer_tracker[peer_username] = {
            "ip": peer_ip,
            "port": peer_port,
            "last_seen": get_timestamp(),
        }

    return _json_response({
        "status": "registered",
        "username": peer_username,
        "ip": peer_ip,
        "port": peer_port,
    })

@app.route('/get-list', methods=['GET'])
def get_list(headers="", body=""):
    with tracker_lock:
        peers = []
        for uname, info in peer_tracker.items():
            peers.append({
                "username": uname,
                "ip": info["ip"],
                "port": info["port"],
                "last_seen": info["last_seen"],
            })

    return _json_response({
        "status": "ok",
        "peers": peers,
        "count": len(peers),
    })

@app.route('/add-list', methods=['POST'])
def add_list(headers="", body=""):
    body_data = _parse_body(body)
    peer_username = body_data.get("username")
    peer_ip = body_data.get("ip")
    peer_port = body_data.get("port")

    if not peer_username or not peer_ip or not peer_port:
        return _error("Missing username, ip, or port")

    with tracker_lock:
        peer_tracker[peer_username] = {
            "ip": peer_ip,
            "port": int(peer_port),
            "last_seen": get_timestamp(),
        }

    return _json_response({
        "status": "added",
        "username": peer_username,
        "total_peers": len(peer_tracker),
    })

def create_trackerapp(ip, port):
    app.prepare_address(ip, port)
    app.run()
