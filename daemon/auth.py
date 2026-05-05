"""
daemon.auth
~~~~~~~~~~~~~~~~~

Authentication module implementing:
  - HTTP Basic Authentication (RFC 2617 / RFC 7235)
  - Cookie-based session management (RFC 6265)

The SessionManager stores active sessions in-memory with expiration.
The auth_required decorator protects route handlers.
"""

import time
import threading
from .utils import decode_basic_auth, generate_session_id, parse_cookies


# ============================================================
# User database (in-memory, supports dynamic registration)
# ============================================================
import threading as _threading
USER_DB = {
    "admin": "admin123",
    "user1": "password1",
    "user2": "password2",
    "guest": "guest",
}
_user_db_lock = _threading.Lock()


def register_user(username, password):
    """Register a new user or update password.

    :param username (str): Username (3-32 chars, alphanumeric/underscore).
    :param password (str): Password (min 4 chars).
    :rtype: (bool, str) - (success, message)
    """
    if not username or len(username) < 3 or len(username) > 32:
        return False, "Username must be 3-32 characters"
    if not all(c.isalnum() or c in ('_', '-') for c in username):
        return False, "Username may only contain letters, digits, _ or -"
    if not password or len(password) < 4:
        return False, "Password must be at least 4 characters"
    with _user_db_lock:
        if username in USER_DB:
            return False, "Username '{}' already exists".format(username)
        USER_DB[username] = password
    return True, "User '{}' registered successfully".format(username)


def change_password(username, old_password, new_password):
    """Change password for an existing user.

    :rtype: (bool, str) - (success, message)
    """
    with _user_db_lock:
        if username not in USER_DB:
            return False, "User not found"
        if USER_DB[username] != old_password:
            return False, "Current password is incorrect"
        if not new_password or len(new_password) < 4:
            return False, "New password must be at least 4 characters"
        USER_DB[username] = new_password
    return True, "Password changed successfully"


class SessionManager:
    """Thread-safe in-memory session store with TTL expiration.

    Each session maps a session_id to user data (username, login time, etc.).
    Sessions expire after `ttl` seconds (default 3600 = 1 hour).

    Usage::
      >>> sm = SessionManager(ttl=3600)
      >>> sid = sm.create_session("admin")
      >>> sm.get_session(sid)
      {'username': 'admin', 'created_at': 1717000000.0}
    """

    def __init__(self, ttl=3600):
        self._sessions = {}
        self._lock = threading.Lock()
        self.ttl = ttl

    def create_session(self, username):
        """Create a new session for the given username.

        :param username (str): Authenticated username.
        :rtype: str - session ID.
        """
        session_id = generate_session_id()
        with self._lock:
            self._sessions[session_id] = {
                "username": username,
                "created_at": time.time(),
            }
        return session_id

    def get_session(self, session_id):
        """Retrieve session data if valid and not expired.

        :param session_id (str): The session identifier.
        :rtype: dict or None
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            # Check expiration
            if time.time() - session["created_at"] > self.ttl:
                del self._sessions[session_id]
                return None
            return session

    def destroy_session(self, session_id):
        """Remove a session.

        :param session_id (str): The session to destroy.
        """
        with self._lock:
            self._sessions.pop(session_id, None)

    def get_username(self, session_id):
        """Get username from session, or None.

        :param session_id (str): Session ID.
        :rtype: str or None
        """
        session = self.get_session(session_id)
        if session:
            return session["username"]
        return None

    def list_sessions(self):
        """List all active sessions (for debugging).

        :rtype: dict
        """
        with self._lock:
            now = time.time()
            return {
                sid: data for sid, data in self._sessions.items()
                if now - data["created_at"] <= self.ttl
            }


# Global session manager instance
session_manager = SessionManager(ttl=3600)


def authenticate_basic(auth_header):
    """Validate HTTP Basic Auth header against USER_DB.

    :param auth_header (str): Value of Authorization header.
    :rtype: str or None - username if valid, None otherwise.
    """
    if not auth_header or not auth_header.startswith("Basic "):
        return None
    encoded = auth_header[6:]
    username, password = decode_basic_auth(encoded)
    if username and password:
        stored_pw = USER_DB.get(username)
        if stored_pw and stored_pw == password:
            return username
    return None


def authenticate_cookie(cookie_header):
    """Validate session cookie.

    :param cookie_header (str): Raw Cookie header value.
    :rtype: str or None - username if valid session exists.
    """
    cookies = parse_cookies(cookie_header)
    session_id = cookies.get("session_id")
    if session_id:
        return session_manager.get_username(session_id)
    return None


def authenticate_request(headers):
    """Try authenticating via X-Session-Id header, cookie, then Basic Auth.

    :param headers (CaseInsensitiveDict): Request headers.
    :rtype: str or None - authenticated username.
    """
    # Try X-Session-Id header (used by browser fetch, which blocks Cookie header)
    x_session = headers.get("x-session-id", "")
    if x_session:
        username = session_manager.get_username(x_session)
        if username:
            return username

    # Try cookie-based auth
    cookie_header = headers.get("cookie", "")
    username = authenticate_cookie(cookie_header)
    if username:
        return username

    # Try Basic Auth
    auth_header = headers.get("authorization", "")
    username = authenticate_basic(auth_header)
    return username


def build_login_success_response(username, response_obj):
    """Build a 200 response with Set-Cookie header for new session.

    :param username (str): Authenticated username.
    :param response_obj: Response object for building headers.
    :rtype: bytes
    """
    session_id = session_manager.create_session(username)
    import json
    body_data = {
        "status": "success",
        "message": "Logged in as {}".format(username),
        "session_id": session_id,
    }
    return response_obj.build_json(
        body_data,
        status_code=200,
        reason="OK",
        extra_headers={
            "Set-Cookie": "session_id={}; Path=/; HttpOnly".format(session_id)
        }
    )
