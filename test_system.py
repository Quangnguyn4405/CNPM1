"""
test_system.py
~~~~~~~~~~~~~~~~~

Automated test script for the hybrid chat application.
Tests: authentication, peer registration, P2P connection, messaging.

Usage:
    1. Start the chat server: python start_chatapp.py --server-port 8000
    2. Run tests: python test_system.py
"""

import socket
import json
import time
import base64
import threading
import sys


SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000


def http_request(method, path, body=None, headers=None, host=None):
    """Send a raw HTTP request and return (status_code, response_body).

    :param method (str): HTTP method.
    :param path (str): URL path.
    :param body (dict): JSON body to send.
    :param headers (dict): Extra headers.
    :param host (str): Target host (default SERVER_HOST:SERVER_PORT).
    :rtype: (int, dict)
    """
    if host is None:
        host_addr = SERVER_HOST
        port = SERVER_PORT
    else:
        parts = host.split(":")
        host_addr = parts[0]
        port = int(parts[1]) if len(parts) > 1 else SERVER_PORT

    body_str = ""
    if body:
        body_str = json.dumps(body)

    request_lines = [
        "{} {} HTTP/1.1".format(method, path),
        "Host: {}:{}".format(host_addr, port),
        "Content-Type: application/json",
        "Content-Length: {}".format(len(body_str)),
        "Connection: close",
    ]
    if headers:
        for k, v in headers.items():
            request_lines.append("{}: {}".format(k, v))
    request_lines.append("")
    request_lines.append(body_str)

    raw = "\r\n".join(request_lines)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect((host_addr, port))
        sock.sendall(raw.encode("utf-8"))

        response = b""
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            except socket.timeout:
                break

        resp_str = response.decode("utf-8", errors="replace")

        # Parse status code
        status_code = 0
        if resp_str.startswith("HTTP/"):
            first_line = resp_str.split("\r\n", 1)[0]
            parts = first_line.split(" ", 2)
            if len(parts) >= 2:
                status_code = int(parts[1])

        # Parse body
        if "\r\n\r\n" in resp_str:
            body_part = resp_str.split("\r\n\r\n", 1)[1]
            try:
                return status_code, json.loads(body_part)
            except json.JSONDecodeError:
                return status_code, {"raw": body_part}
        return status_code, {}
    except Exception as e:
        return 0, {"error": str(e)}
    finally:
        sock.close()


def test_login():
    """Test authentication endpoints."""
    print("\n=== Test 1: Authentication ===")

    # Test login with JSON body
    code, resp = http_request("POST", "/login", body={
        "username": "user1", "password": "password1"
    })
    print("  Login (JSON body): status={} resp={}".format(code, resp))
    assert resp.get("status") == "success", "Login should succeed"
    session_id = resp.get("session_id", "")
    assert session_id, "Should return session_id"
    print("  Session ID: {}".format(session_id))

    # Test login with Basic Auth header
    creds = base64.b64encode(b"admin:admin123").decode()
    code2, resp2 = http_request("POST", "/login", headers={
        "Authorization": "Basic {}".format(creds)
    })
    print("  Login (Basic Auth): status={} resp={}".format(code2, resp2))
    assert resp2.get("status") == "success", "Basic Auth login should succeed"

    # Test login with wrong password
    code3, resp3 = http_request("POST", "/login", body={
        "username": "user1", "password": "wrongpass"
    })
    print("  Login (wrong pw): status={} resp={}".format(code3, resp3))
    assert "error" in resp3 or resp3.get("status") != "success"

    print("  [PASS] Authentication tests passed")
    return session_id


def test_peer_registration(session_id):
    """Test peer registration and discovery."""
    print("\n=== Test 2: Peer Registration ===")

    # Register peer 1
    code, resp = http_request("POST", "/submit-info", body={
        "username": "user1", "ip": "127.0.0.1", "port": 7001
    }, headers={"Cookie": "session_id={}".format(session_id)})
    print("  Submit-info: status={} resp={}".format(code, resp))
    assert resp.get("status") == "registered"

    # Add another peer
    code2, resp2 = http_request("POST", "/add-list", body={
        "username": "user2", "ip": "127.0.0.1", "port": 7002
    })
    print("  Add-list: status={} resp={}".format(code2, resp2))
    assert resp2.get("status") == "added"

    # Get peer list
    code3, resp3 = http_request("GET", "/get-list")
    print("  Get-list: status={} resp={}".format(code3, resp3))
    assert resp3.get("count", 0) >= 2, "Should have at least 2 peers"

    print("  [PASS] Peer registration tests passed")


def test_chat_features():
    """Test chat feature endpoints."""
    print("\n=== Test 3: Chat Features ===")

    # Get channels
    code, resp = http_request("GET", "/channels")
    print("  Channels: status={} resp={}".format(code, resp))
    assert "channels" in resp

    # Get messages
    code2, resp2 = http_request("GET", "/messages", body={"channel": "general"})
    print("  Messages: status={} resp={}".format(code2, resp2))
    assert "messages" in resp2

    # Get notifications
    code3, resp3 = http_request("GET", "/notifications")
    print("  Notifications: status={} resp={}".format(code3, resp3))
    assert "notifications" in resp3

    # Peer status
    code4, resp4 = http_request("GET", "/peer-status")
    print("  Peer status: status={} resp={}".format(code4, resp4))

    print("  [PASS] Chat features tests passed")


def test_broadcast():
    """Test broadcast messaging."""
    print("\n=== Test 4: Broadcast ===")

    code, resp = http_request("POST", "/broadcast-peer", body={
        "message": "Hello everyone!", "channel": "general"
    })
    print("  Broadcast: status={} resp={}".format(code, resp))
    assert resp.get("status") == "broadcast_sent"

    # Check message appears
    time.sleep(0.5)
    code2, resp2 = http_request("GET", "/messages", body={"channel": "general"})
    print("  Messages after broadcast: count={}".format(resp2.get("count", 0)))
    assert resp2.get("count", 0) > 0, "Should have messages after broadcast"

    print("  [PASS] Broadcast test passed")


def test_static_files():
    """Test static file serving."""
    print("\n=== Test 5: Static File Serving ===")

    code, resp = http_request("GET", "/index.html")
    print("  index.html: status={}".format(code))
    assert code == 200, "Should serve index.html"

    code2, resp2 = http_request("GET", "/chat.html")
    print("  chat.html: status={}".format(code2))
    assert code2 == 200, "Should serve chat.html"

    print("  [PASS] Static file tests passed")


def main():
    print("=" * 60)
    print("  System Test - Hybrid Chat Application")
    print("  Target: {}:{}".format(SERVER_HOST, SERVER_PORT))
    print("=" * 60)

    try:
        # Quick connectivity check
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((SERVER_HOST, SERVER_PORT))
        sock.close()
    except Exception:
        print("\n  [ERROR] Cannot connect to {}:{}".format(
            SERVER_HOST, SERVER_PORT
        ))
        print("  Start the server first:")
        print("    python start_chatapp.py --server-port {}".format(SERVER_PORT))
        sys.exit(1)

    try:
        session_id = test_login()
        test_peer_registration(session_id)
        test_chat_features()
        test_broadcast()
        test_static_files()

        print("\n" + "=" * 60)
        print("  ALL TESTS PASSED")
        print("=" * 60)
    except AssertionError as e:
        print("\n  [FAIL] {}".format(e))
        sys.exit(1)
    except Exception as e:
        print("\n  [ERROR] {}".format(e))
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
