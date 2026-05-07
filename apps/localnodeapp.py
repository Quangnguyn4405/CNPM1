"""
apps.localnodeapp
~~~~~~~~~~~~~~~~~

Local Web Node with GUI combining client-server and peer-to-peer paradigms.

Client-Server Phase (Initialization):
  - /login          POST  - Authenticate user (Basic Auth -> Set-Cookie)
  - /logout         POST  - Destroy session
  - /submit-info    POST  - Register peer IP and port with tracker
  - /get-list       GET   - Get active peer list from tracker
  - /add-list       POST  - Add/update peer in tracker list

Peer-to-Peer Phase (Chat):
  - /connect-peer   POST  - Initiate direct TCP P2P connection to a peer
  - /broadcast-peer POST  - Broadcast message to all connected peers
  - /send-peer      POST  - Send direct message to a specific peer

Chat Features:
  - /channels       GET   - List channels
  - /messages       GET   - Get messages from a channel (?channel=xxx)
  - /notifications  GET   - Get new message notifications

All endpoints use JSON request/response bodies.
Protocol format:
  {
    "sender": "username",
    "channel": "channel_name",
    "message": "text content",
    "timestamp": "2026-05-04T12:00:00Z",
    "type": "chat" | "handshake" | "system"
  }
"""

import sys
import os
import json
import threading
import urllib.request
import urllib.error

TRACKER_URL = "http://127.0.0.1:8000"

def set_tracker_url(url):
    global TRACKER_URL
    TRACKER_URL = url


from daemon.asynaprous import AsynapRous
from daemon.auth import (
    authenticate_request, authenticate_basic, authenticate_cookie,
    session_manager, build_login_success_response, USER_DB,
    register_user, change_password,
)
from daemon.response import Response
from daemon.peer import PeerNode
from daemon.utils import (
    decode_basic_auth, parse_cookies, get_timestamp, encode_basic_auth,
)

# ============================================================
# Global state
# ============================================================

# Peer tracker: { "username": {"ip": ..., "port": ..., "last_seen": ...} }
peer_tracker = {}
tracker_lock = threading.Lock()

# Local peer node (fallback for non-session access)
local_peer = None
peer_lock = threading.Lock()

# Per-session peer nodes: {session_id: PeerNode}
session_peers = {}
session_peers_lock = threading.Lock()


def _parse_body(body_str):
    """Parse JSON body from request body string.

    :param body_str (str): Raw body text.
    :rtype: dict
    """
    if not body_str or not body_str.strip():
        return {}
    try:
        return json.loads(body_str.strip())
    except json.JSONDecodeError:
        return {}


def _parse_headers_dict(headers_str):
    """Reconstruct a minimal headers dict from the stringified headers.

    The AsynapRous framework passes headers as str(CaseInsensitiveDict).
    We need to extract useful fields.

    :param headers_str (str): Stringified headers.
    :rtype: dict
    """
    # The framework passes headers as a string repr of dict
    # Try to extract key fields
    result = {}
    if not headers_str:
        return result

    # Try eval-based parsing of the dict string
    try:
        if headers_str.startswith("{") or headers_str.startswith("{'"):
            # Safe parsing: replace single quotes
            import ast
            result = ast.literal_eval(headers_str)
            return result
    except Exception:
        pass

    # Fallback: scan for known headers
    for field in ["authorization", "cookie", "content-type", "host"]:
        idx = headers_str.lower().find("'" + field + "'")
        if idx == -1:
            idx = headers_str.lower().find('"' + field + '"')
        if idx >= 0:
            # Extract value after the colon
            rest = headers_str[idx:]
            parts = rest.split(",", 1)
            kv = parts[0]
            if ":" in kv:
                val = kv.split(":", 1)[1].strip().strip("'\"} ")
                result[field] = val

    return result


def _auth_check(headers_str):
    """Check authentication from headers string.

    :param headers_str: Raw headers string from framework.
    :rtype: (str, dict) - (username or None, headers_dict)
    """
    from daemon.dictionary import CaseInsensitiveDict
    hdr = _parse_headers_dict(headers_str)
    ci_headers = CaseInsensitiveDict(hdr)
    username = authenticate_request(ci_headers)
    return username, hdr


def _get_session_id(hdr):
    """Extract session_id from parsed headers dict.

    :param hdr (dict): Parsed headers.
    :rtype: str
    """
    sid = hdr.get("x-session-id", "")
    if not sid:
        cookies = parse_cookies(hdr.get("cookie", ""))
        sid = cookies.get("session_id", "")
    return sid


def _get_peer(hdr):
    """Get the PeerNode for the current session only — no global fallback.

    :param hdr (dict): Parsed headers dict.
    :rtype: PeerNode or None
    """
    sid = _get_session_id(hdr)
    if sid:
        with session_peers_lock:
            return session_peers.get(sid)
    return None


def _set_peer(hdr, peer):
    """Store PeerNode for the current session and update global fallback.

    :param hdr (dict): Parsed headers dict.
    :param peer (PeerNode): Peer node to store.
    """
    global local_peer
    sid = _get_session_id(hdr)
    if sid:
        with session_peers_lock:
            session_peers[sid] = peer
    # Always keep global as fallback for session-less requests
    with peer_lock:
        local_peer = peer


def _json_response(data, status_code=200):
    """Build JSON bytes response.

    :param data: Dict to serialize.
    :rtype: bytes
    """
    return json.dumps(data).encode("utf-8")


def _error(msg, code=400):
    """Build error JSON bytes.

    :param msg (str): Error message.
    :rtype: bytes
    """
    return json.dumps({"error": msg, "status": code}).encode("utf-8")


# ============================================================
# Create AsynapRous app
# ============================================================
app = AsynapRous()


# ============================================================
# Authentication endpoints
# ============================================================

@app.route('/login', methods=['POST'])
def login(headers="", body=""):
    """Authenticate user via HTTP Basic Auth, return session cookie.

    Request: Authorization header with Basic base64(user:pass)
             OR JSON body {"username": "...", "password": "..."}
    Response: JSON with session_id and Set-Cookie header.
    """
    hdr = _parse_headers_dict(headers)

    # Try Basic Auth from header
    auth_header = hdr.get("authorization", "")
    username = None

    if auth_header and auth_header.startswith("Basic "):
        encoded = auth_header[6:]
        user, pw = decode_basic_auth(encoded)
        if user and pw and USER_DB.get(user) == pw:
            username = user

    # Try from JSON body
    if not username:
        body_data = _parse_body(body)
        user = body_data.get("username", "")
        pw = body_data.get("password", "")
        if user and pw and USER_DB.get(user) == pw:
            username = user

    if not username:
        # RFC 7235: 401 with WWW-Authenticate challenge
        body = _json_response({"error": "Invalid credentials"})
        return (body, {"WWW-Authenticate": 'Basic realm="chat"'}, 401)

    # Create session, set RFC 6265 Set-Cookie header
    session_id = session_manager.create_session(username)
    body = _json_response({
        "status": "success",
        "message": "Logged in as {}".format(username),
        "session_id": session_id,
    })
    return (body, {"Set-Cookie": "session_id={}; Path=/; HttpOnly".format(session_id)}, 200)


@app.route('/logout', methods=['POST'])
def logout(headers="", body=""):
    """Destroy the current session.

    Request: Cookie header with session_id.
    Response: JSON confirmation.
    """
    hdr = _parse_headers_dict(headers)

    # Check X-Session-Id header (browser fetch blocks Cookie header)
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
    """List all registered users (dev/debug endpoint).

    Response: JSON list of {username, password}.
    """
    from daemon.auth import _user_db_lock
    with _user_db_lock:
        users = [{"username": u, "password": p} for u, p in USER_DB.items()]
    return _json_response({"users": users, "count": len(users)})


@app.route('/register', methods=['POST'])
def register(headers="", body=""):
    """Register a new user account.

    Request body: {"username": "...", "password": "..."}
    Response: JSON confirmation.
    """
    body_data = _parse_body(body)
    username = body_data.get("username", "").strip()
    password = body_data.get("password", "")
    ok, msg = register_user(username, password)
    if ok:
        return _json_response({"status": "registered", "message": msg})
    return _json_response({"status": "error", "error": msg})


@app.route('/change-password', methods=['POST'])
def change_pwd(headers="", body=""):
    """Change password for an existing user.

    Request body: {"username": "...", "old_password": "...", "new_password": "..."}
    Response: JSON confirmation.
    """
    body_data = _parse_body(body)
    username = body_data.get("username", "").strip()
    old_pw = body_data.get("old_password", "")
    new_pw = body_data.get("new_password", "")
    ok, msg = change_password(username, old_pw, new_pw)
    if ok:
        return _json_response({"status": "changed", "message": msg})
    return _json_response({"status": "error", "error": msg})


# ============================================================
# Client-Server Phase: Peer Registration & Discovery
# ============================================================

@app.route('/submit-info', methods=['POST'])
def submit_info(headers="", body=""):
    """Register this peer's IP and port with the centralized tracker.

    Request body: {"username": "...", "ip": "...", "port": 12345}
    Response: JSON confirmation.
    """
    username, hdr = _auth_check(headers)

    body_data = _parse_body(body)
    peer_username = body_data.get("username", username or "anonymous")
    peer_ip = body_data.get("ip", "127.0.0.1")
    peer_port = body_data.get("port", 0)

    if not peer_port:
        return _error("Missing 'port' in request body")

    peer_port = int(peer_port)

    # Notify central tracker
    try:
        payload = json.dumps({"username": peer_username, "ip": peer_ip, "port": peer_port}).encode("utf-8")
        req = urllib.request.Request(TRACKER_URL + "/submit-info", data=payload, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=3.0)
        print("[LocalNode] Registered with Tracker at", TRACKER_URL)
    except Exception as e:
        print("[LocalNode] Failed to notify tracker:", e)

    # Initialize per-session peer node — only look at THIS session, never global fallback,
    # to avoid stopping another user's PeerNode when a new session registers.
    sid = _get_session_id(hdr)
    with session_peers_lock:
        existing = session_peers.get(sid) if sid else None
    if existing is None or existing.username != peer_username or existing.port != peer_port:
        if existing is not None:
            existing.stop()
        new_peer = PeerNode(peer_ip, peer_port, peer_username)
        new_peer.start()
        _set_peer(hdr, new_peer)

    return _json_response({
        "status": "registered",
        "username": peer_username,
        "ip": peer_ip,
        "port": peer_port,
    })


@app.route('/get-list', methods=['GET'])
def get_list(headers="", body=""):
    """Proxy request to get active peers from the tracker."""
    try:
        req = urllib.request.Request(TRACKER_URL + "/get-list")
        resp = urllib.request.urlopen(req, timeout=3.0)
        return resp.read()
    except Exception as e:
        print("[LocalNode] Failed to reach tracker for list:", e)
        return _json_response({"status": "error", "error": "Tracker offline", "peers": [], "count": 0})

@app.route('/add-list', methods=['POST'])
def add_list(headers="", body=""):
    """Proxy request to add peer to tracker."""
    try:
        req = urllib.request.Request(TRACKER_URL + "/add-list", data=body.encode('utf-8') if isinstance(body, str) else body, headers={'Content-Type': 'application/json'})
        resp = urllib.request.urlopen(req, timeout=3.0)
        return resp.read()
    except Exception as e:
        return _error("Cannot reach tracker")

# ============================================================
# Peer-to-Peer Phase: Direct Communication
# ============================================================

@app.route('/connect-peer', methods=['POST'])
def connect_peer(headers="", body=""):
    """Initiate direct TCP P2P connection to another peer.

    Request body: {"ip": "...", "port": 12345}
    Response: JSON success/failure.
    """
    _, hdr = _auth_check(headers)
    peer = _get_peer(hdr)
    if peer is None:
        return _error("Peer not initialized. Call /submit-info first.")

    body_data = _parse_body(body)
    target_ip = body_data.get("ip")
    target_port = body_data.get("port")

    if not target_ip or not target_port:
        return _error("Missing 'ip' or 'port'")

    target_port = int(target_port)

    if target_port == peer.port and target_ip in (peer.ip, "127.0.0.1", "0.0.0.0", "localhost"):
        return _json_response({
            "status": "failed",
            "error": "Cannot connect to your own peer address. Your peer is at {}:{}, connect to another peer's port instead.".format(peer.ip, peer.port),
        })

    success = peer.connect_to_peer(target_ip, target_port)

    if success:
        return _json_response({
            "status": "connected",
            "target_ip": target_ip,
            "target_port": target_port,
        })
    else:
        return _json_response({
            "status": "failed",
            "error": "Could not connect to {}:{}".format(target_ip, target_port),
        })


@app.route('/broadcast-peer', methods=['POST'])
def broadcast_peer(headers="", body=""):
    """Broadcast a message to all connected peers.

    Request body: {"message": "...", "channel": "general"}
    Response: JSON with number of peers reached.
    """
    username, hdr = _auth_check(headers)
    if not username:
        return _error("Authentication required", 401)
    peer = _get_peer(hdr)
    if peer is None:
        return _error("Peer not initialized. Call /submit-info first.")

    body_data = _parse_body(body)
    message = body_data.get("message", "")
    channel = body_data.get("channel", "general")

    if not message:
        return _error("Missing 'message'")

    sender = username or peer.username
    count = peer.broadcast_message(message, channel, sender=sender)

    return _json_response({
        "status": "broadcast_sent",
        "peers_reached": count,
        "channel": channel,
        "message": message,
    })


@app.route('/send-peer', methods=['POST'])
def send_peer(headers="", body=""):
    """Send a direct message to a specific peer.

    Request body: {"ip": "...", "port": ..., "message": "...", "channel": "general"}
    Response: JSON success/failure.
    """
    username, hdr = _auth_check(headers)
    if not username:
        return _error("Authentication required", 401)
    peer = _get_peer(hdr)
    if peer is None:
        return _error("Peer not initialized. Call /submit-info first.")

    body_data = _parse_body(body)
    target_ip = body_data.get("ip")
    target_port = body_data.get("port")
    message = body_data.get("message", "")
    channel = body_data.get("channel", "general")

    if not target_ip or not target_port or not message:
        return _error("Missing 'ip', 'port', or 'message'")

    target_port = int(target_port)
    sender = username or peer.username
    success = peer.send_message(target_ip, target_port, message, channel, sender=sender)

    return _json_response({
        "status": "sent" if success else "failed",
        "target": "{}:{}".format(target_ip, target_port),
        "channel": channel,
    })


# ============================================================
# Chat Feature Endpoints
# ============================================================

@app.route('/channels', methods=['GET'])
def channels(headers="", body=""):
    """List all channels the user has joined.

    Response: JSON list of channel names.
    """
    _, hdr = _auth_check(headers)
    peer = _get_peer(hdr)
    if peer is None:
        return _json_response({"channels": ["general"]})
    ch_list = peer.get_channels()
    return _json_response({"channels": ch_list})


@app.route('/messages', methods=['GET'])
def messages(headers="", body=""):
    """Get messages from a channel.

    Query: ?channel=general&limit=50 (via body as fallback)
    Response: JSON list of messages.
    """
    global local_peer

    # Parse channel from body (since query params go through body in this framework)
    _, hdr = _auth_check(headers)
    body_data = _parse_body(body)
    channel = body_data.get("channel", "general")
    limit = int(body_data.get("limit", 50))

    peer = _get_peer(hdr)
    if peer is None:
        return _json_response({"channel": channel, "messages": [], "count": 0})

    msgs = peer.get_messages(channel, limit)
    return _json_response({
        "channel": channel,
        "messages": msgs,
        "count": len(msgs),
    })


@app.route('/notifications', methods=['GET'])
def notifications(headers="", body=""):
    """Get new message notifications.

    Response: JSON list of notification objects.
    """
    _, hdr = _auth_check(headers)
    peer = _get_peer(hdr)
    if peer is None:
        return _json_response({"notifications": [], "count": 0})

    notifs = peer.get_notifications(clear=True)
    return _json_response({
        "notifications": notifs,
        "count": len(notifs),
    })


@app.route('/peer-status', methods=['GET'])
def peer_status(headers="", body=""):
    """Get current peer connection status.

    Response: JSON with connected peers info.
    """
    _, hdr = _auth_check(headers)
    peer = _get_peer(hdr)
    if peer is None:
        return _json_response({
            "status": "not_initialized",
            "connected_peers": [],
        })

    peers = peer.get_connected_peers_info()
    return _json_response({
        "status": "active",
        "username": peer.username,
        "listen_address": "{}:{}".format(peer.ip, peer.port),
        "connected_peers": peers,
        "peer_count": len(peers),
    })


# ============================================================
# Entry point
# ============================================================

def create_localnodeapp(ip, port, tracker_url=None):
    if tracker_url:
        set_tracker_url(tracker_url)
    """Launch the chat application on the given IP and port.

    :param ip (str): Bind IP.
    :param port (int): Bind port.
    """
    app.prepare_address(ip, port)
    app.run()
