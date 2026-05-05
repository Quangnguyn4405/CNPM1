#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#

"""
daemon.proxy
~~~~~~~~~~~~~~~~~

Proxy server routing HTTP requests to backends based on hostname mappings.
Supports round-robin load balancing across multiple backends.
"""

import socket
import threading
from .response import Response
from .httpadapter import HttpAdapter
from .dictionary import CaseInsensitiveDict

PROXY_PASS = {
    "192.168.56.103:8080": ('192.168.56.103', 9000),
    "app1.local": ('192.168.56.103', 9001),
    "app2.local": ('192.168.56.103', 9002),
}

# Round-robin counter per hostname
_rr_counters = {}
_rr_lock = threading.Lock()


def forward_request(host, port, request):
    """Forward HTTP request to a backend and return its response.

    :param host (str): Backend IP.
    :param port (int): Backend port.
    :param request (str): Raw HTTP request.
    :rtype: bytes
    """
    backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    backend.settimeout(10)

    try:
        backend.connect((host, port))
        backend.sendall(request.encode())
        response = b""
        while True:
            chunk = backend.recv(4096)
            if not chunk:
                break
            response += chunk
        return response
    except socket.error as e:
        print("[Proxy] Forward error to {}:{}: {}".format(host, port, e))
        return Response().build_notfound()
    finally:
        backend.close()


def resolve_routing_policy(hostname, routes):
    """Resolve backend target using routing policy.

    :param hostname (str): Request hostname.
    :param routes (dict): Routing config.
    :rtype: (str, str) - (host, port)
    """
    global _rr_counters

    entry = routes.get(hostname)
    if not entry:
        print("[Proxy] No route for hostname: {}".format(hostname))
        return None, None

    proxy_map, policy = entry

    if isinstance(proxy_map, list):
        if len(proxy_map) == 0:
            return None, None
        elif len(proxy_map) == 1:
            host, port = proxy_map[0].split(":", 1)
            return host, port
        else:
            # Round-robin among multiple backends
            with _rr_lock:
                idx = _rr_counters.get(hostname, 0)
                target = proxy_map[idx % len(proxy_map)]
                _rr_counters[hostname] = idx + 1
            host, port = target.split(":", 1)
            return host, port
    else:
        host, port = proxy_map.split(":", 1)
        return host, port


def handle_client(ip, port, conn, addr, routes):
    """Handle a proxied client connection.

    :param ip (str): Proxy IP.
    :param port (int): Proxy port.
    :param conn (socket): Client socket.
    :param addr (tuple): Client address.
    :param routes (dict): Route mapping.
    """
    try:
        request = conn.recv(4096).decode("utf-8", errors="replace")

        # Extract Host header
        hostname = None
        for line in request.splitlines():
            if line.lower().startswith('host:'):
                hostname = line.split(':', 1)[1].strip()
                break

        if not hostname:
            hostname = "{}:{}".format(ip, port)

        resolved_host, resolved_port = resolve_routing_policy(hostname, routes)

        if resolved_host:
            try:
                resolved_port = int(resolved_port)
            except (ValueError, TypeError):
                resolved_port = 9000
            print("[Proxy] {} -> {}:{}".format(hostname, resolved_host, resolved_port))
            response = forward_request(resolved_host, resolved_port, request)
        else:
            response = Response().build_notfound()

        conn.sendall(response)
    except Exception as e:
        print("[Proxy] handle_client error: {}".format(e))
    finally:
        conn.close()


def run_proxy(ip, port, routes):
    """Start proxy server with multi-threaded client handling.

    :param ip (str): Bind IP.
    :param port (int): Bind port.
    :param routes (dict): Route mapping.
    """
    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        proxy.bind((ip, port))
        proxy.listen(50)
        print("[Proxy] Listening on {}:{}".format(ip, port))
        while True:
            conn, addr = proxy.accept()
            t = threading.Thread(
                target=handle_client,
                args=(ip, port, conn, addr, routes),
                daemon=True
            )
            t.start()
    except socket.error as e:
        print("[Proxy] Socket error: {}".format(e))
    except KeyboardInterrupt:
        print("[Proxy] Shutting down...")
    finally:
        proxy.close()


def create_proxy(ip, port, routes):
    """Entry point for launching proxy server.

    :param ip (str): Bind IP.
    :param port (int): Bind port.
    :param routes (dict): Route mapping.
    """
    run_proxy(ip, port, routes)
