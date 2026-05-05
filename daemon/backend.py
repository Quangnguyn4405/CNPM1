#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#

"""
daemon.backend
~~~~~~~~~~~~~~~~~

Backend server supporting three non-blocking concurrency models:
  - threading: one thread per connection
  - callback: selector-based event-driven I/O
  - coroutine: asyncio async/await
"""

import socket
import threading
import argparse
import asyncio
import inspect
import selectors

from .response import Response
from .httpadapter import HttpAdapter
from .dictionary import CaseInsensitiveDict

# Selector for callback mode
sel = selectors.DefaultSelector()

# Default concurrency mode: 'threading', 'callback', or 'coroutine'
mode_async = "coroutine"


def handle_client(ip, port, conn, addr, routes):
    """Handle client in threading mode.

    :param ip (str): Server IP.
    :param port (int): Server port.
    :param conn (socket): Client socket.
    :param addr (tuple): Client address.
    :param routes (dict): Route handlers.
    """
    try:
        daemon = HttpAdapter(ip, port, conn, addr, routes)
        daemon.handle_client(conn, addr, routes)
    except Exception as e:
        print("[Backend] handle_client error: {}".format(e))
        try:
            conn.close()
        except Exception:
            pass


def handle_client_callback(server, ip, port, conn, addr, routes):
    """Handle client in callback/selector mode.

    :param server: Server socket (unused but required by selector).
    :param ip (str): Server IP.
    :param port (int): Server port.
    :param conn (socket): Client socket.
    :param addr (tuple): Client address.
    :param routes (dict): Route handlers.
    """
    try:
        daemon = HttpAdapter(ip, port, conn, addr, routes)
        daemon.handle_client(conn, addr, routes)
    except Exception as e:
        print("[Backend] callback error: {}".format(e))
        try:
            conn.close()
        except Exception:
            pass


async def handle_client_coroutine(reader, writer, routes):
    """Handle client as asyncio coroutine.

    :param reader (StreamReader): Async reader.
    :param writer (StreamWriter): Async writer.
    :param routes (dict): Route handlers.
    """
    addr = writer.get_extra_info("peername")
    try:
        daemon = HttpAdapter(None, None, None, addr, routes)
        await daemon.handle_client_coroutine(reader, writer)
    except Exception as e:
        print("[Backend] coroutine error for {}: {}".format(addr, e))
        try:
            writer.close()
        except Exception:
            pass


async def async_server(ip="0.0.0.0", port=7000, routes={}):
    """Start asyncio-based server.

    :param ip (str): Bind IP.
    :param port (int): Bind port.
    :param routes (dict): Route handlers.
    """
    print("[Backend] async_server **ASYNC** listening on {}:{}".format(ip, port))
    _log_routes(routes)

    async def client_handler(reader, writer):
        await handle_client_coroutine(reader, writer, routes)

    server = await asyncio.start_server(client_handler, ip, port)
    async with server:
        await server.serve_forever()


def _log_routes(routes):
    """Print registered routes."""
    if routes:
        print("[Backend] route settings:")
        for key, value in routes.items():
            co = "**ASYNC** " if inspect.iscoroutinefunction(value) else ""
            print("   + ('{}', '{}'): {}{}".format(
                key[0], key[1], co, str(value)
            ))


def run_backend(ip, port, routes):
    """Start backend server with configured concurrency mode.

    :param ip (str): Bind IP.
    :param port (int): Bind port.
    :param routes (dict): Route handlers.
    """
    global mode_async

    print("[Backend] Starting with mode='{}' on {}:{}".format(mode_async, ip, port))
    _log_routes(routes)

    # ---- Coroutine mode (asyncio) ----
    if mode_async == "coroutine":
        asyncio.run(async_server(ip, port, routes))
        return

    # ---- Socket-based modes (threading / callback) ----
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((ip, port))
        server.listen(50)
        print("[Backend] Listening on {}:{}".format(ip, port))

        if mode_async == "callback":
            # Event-driven with selectors
            server.setblocking(False)
            sel.register(
                server, selectors.EVENT_READ,
                data=("accept", ip, port, routes)
            )
            print("[Backend] Running in callback/selector mode")

            while True:
                events = sel.select(timeout=1)
                for key, mask in events:
                    action = key.data[0]
                    if action == "accept":
                        _ip, _port, _routes = key.data[1], key.data[2], key.data[3]
                        conn, addr = key.fileobj.accept()
                        conn.setblocking(False)
                        # Register the new connection for reading
                        sel.register(
                            conn, selectors.EVENT_READ,
                            data=("handle", _ip, _port, _routes, addr)
                        )
                    elif action == "handle":
                        _ip = key.data[1]
                        _port = key.data[2]
                        _routes = key.data[3]
                        _addr = key.data[4]
                        conn = key.fileobj
                        sel.unregister(conn)
                        conn.setblocking(True)
                        # Handle in a thread to avoid blocking the loop
                        t = threading.Thread(
                            target=handle_client_callback,
                            args=(server, _ip, _port, conn, _addr, _routes),
                            daemon=True
                        )
                        t.start()

        else:
            # Threading mode (default)
            print("[Backend] Running in threading mode")
            while True:
                conn, addr = server.accept()
                t = threading.Thread(
                    target=handle_client,
                    args=(ip, port, conn, addr, routes),
                    daemon=True
                )
                t.start()

    except socket.error as e:
        print("[Backend] Socket error: {}".format(e))
    except KeyboardInterrupt:
        print("[Backend] Shutting down...")
    finally:
        server.close()


def create_backend(ip, port, routes={}):
    """Entry point for creating and running the backend server.

    :param ip (str): IP address to bind.
    :param port (int): Port to listen on.
    :param routes (dict): Route handlers.
    """
    run_backend(ip, port, routes)
