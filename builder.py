import os

# Read the original chatapp.py
with open("apps/chatapp.py", "r", encoding="utf-8") as f:
    code = f.read()

# Modify module docstring
code = code.replace("apps.chatapp", "apps.localnodeapp")
code = code.replace("Hybrid chat application combining", "Local Web Node with GUI combining")

# Add Tracker configuration
import_section = "import threading"
tracker_config = """import threading
import urllib.request
import urllib.error

TRACKER_URL = "http://127.0.0.1:8000"

def set_tracker_url(url):
    global TRACKER_URL
    TRACKER_URL = url
"""
code = code.replace(import_section, tracker_config)

# Find and replace submit-info
start_submit = code.find("@app.route('/submit-info', methods=['POST'])")
end_submit = code.find("@app.route('/get-list', methods=['GET'])")
submit_code = code[start_submit:end_submit]

# We need to replace the `peer_tracker` local update with an HTTP call
old_tracker_code = """    # Register in tracker
    with tracker_lock:
        peer_tracker[peer_username] = {
            "ip": peer_ip,
            "port": peer_port,
            "last_seen": get_timestamp(),
        }"""

new_tracker_code = """    # Notify central tracker
    try:
        payload = json.dumps({"username": peer_username, "ip": peer_ip, "port": peer_port}).encode("utf-8")
        req = urllib.request.Request(TRACKER_URL + "/submit-info", data=payload, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=3.0)
        print("[LocalNode] Registered with Tracker at", TRACKER_URL)
    except Exception as e:
        print("[LocalNode] Failed to notify tracker:", e)"""

new_submit_code = submit_code.replace(old_tracker_code, new_tracker_code)
code = code.replace(submit_code, new_submit_code)

# Find and replace get-list
start_get = code.find("@app.route('/get-list', methods=['GET'])")
end_get = code.find("@app.route('/add-list', methods=['POST'])")
old_get_code = code[start_get:end_get]

new_get_code = """@app.route('/get-list', methods=['GET'])
def get_list(headers="", body=""):
    \"\"\"Proxy request to get active peers from the tracker.\"\"\"
    try:
        req = urllib.request.Request(TRACKER_URL + "/get-list")
        resp = urllib.request.urlopen(req, timeout=3.0)
        return resp.read()
    except Exception as e:
        print("[LocalNode] Failed to reach tracker for list:", e)
        return _json_response({"status": "error", "error": "Tracker offline", "peers": [], "count": 0})

"""
code = code.replace(old_get_code, new_get_code)

# Find and replace add-list
start_add = code.find("@app.route('/add-list', methods=['POST'])")
end_add = code.find("# ============================================================\n# Peer-to-Peer Phase")
old_add_code = code[start_add:end_add]

new_add_code = """@app.route('/add-list', methods=['POST'])
def add_list(headers="", body=""):
    \"\"\"Proxy request to add peer to tracker.\"\"\"
    try:
        req = urllib.request.Request(TRACKER_URL + "/add-list", data=body.encode('utf-8') if isinstance(body, str) else body, headers={'Content-Type': 'application/json'})
        resp = urllib.request.urlopen(req, timeout=3.0)
        return resp.read()
    except Exception as e:
        return _error("Cannot reach tracker")

"""
code = code.replace(old_add_code, new_add_code)

# Update entry point
code = code.replace("def create_chatapp(ip, port):", "def create_localnodeapp(ip, port, tracker_url=None):\n    if tracker_url:\n        set_tracker_url(tracker_url)")

with open("apps/localnodeapp.py", "w", encoding="utf-8") as f:
    f.write(code)

print("localnodeapp.py generated successfully.")
