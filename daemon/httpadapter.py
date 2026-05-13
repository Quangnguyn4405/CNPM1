#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#

"""
daemon.httpadapter
~~~~~~~~~~~~~~~~~

HTTP adapter managing client connections, routing requests to handlers,
and building responses. Supports both sync and async (coroutine) modes.
"""

from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict

import asyncio
import inspect
import json
import traceback


class HttpAdapter:
    """HTTP adapter for managing connections and dispatching requests.

    Reads HTTP requests, dispatches to route handlers or serves static files,
    builds responses, and sends them back. Supports sync socket and async
    StreamReader/StreamWriter modes.
    """

    __attrs__ = [
        "ip", "port", "conn", "connaddr", "routes",
        "request", "response",
    ]

    def __init__(self, ip, port, conn, connaddr, routes):
        self.ip = ip
        self.port = port
        self.conn = conn
        self.connaddr = connaddr
        self.routes = routes or {}
        self.request = Request()
        self.response = Response()

    def _invoke_hook(self, hook, req):
        """Invoke a route handler with parsed request data.

        :param hook: The route handler function.
        :param req: The Request object.
        :rtype: tuple - (body_bytes, extra_headers, status_code, reason)
        """
        headers_str = str(req.headers)
        body_str = req.body or ""
        if not body_str.strip() and req.query_params:
            body_str = json.dumps(req.query_params)

        try:
            if inspect.iscoroutinefunction(hook):
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(hook(headers_str, body_str))
                loop.close()
            else:
                result = hook(headers_str, body_str)
            return self._parse_hook_result(result)
        except Exception as e:
            print("[HttpAdapter] Hook error: {}".format(e))
            traceback.print_exc()
            body = json.dumps({"error": str(e)}).encode("utf-8")
            return body, {}, 500, "Internal Server Error"

    @staticmethod
    def _parse_hook_result(result):
        """Parse hook return value into (body, extra_headers, status_code, reason).

        Supports:
          bytes / str / dict          → body only, status 200
          (body, extra_headers)       → body + headers, status 200
          (body, extra_headers, code) → full tuple with custom status
        """
        _reasons = {
            200: "OK", 201: "Created", 204: "No Content",
            400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
            404: "Not Found", 500: "Internal Server Error",
        }
        extra_headers = {}
        status_code = 200

        if isinstance(result, tuple):
            body = result[0] if len(result) > 0 else b""
            extra_headers = result[1] if len(result) > 1 else {}
            if len(result) > 2:
                status_code = int(result[2])
        else:
            body = result

        reason = _reasons.get(status_code, "OK")

        if body is None:
            body = b""
        elif isinstance(body, str):
            body = body.encode("utf-8")
        elif isinstance(body, dict):
            body = json.dumps(body).encode("utf-8")

        return body, extra_headers, status_code, reason

    def handle_client(self, conn, addr, routes):
        """Handle an incoming client connection (sync mode).

        Reads request, parses it, dispatches to hook or serves static file,
        builds and sends response.

        :param conn (socket): Client socket.
        :param addr (tuple): Client address.
        :param routes (dict): Route mapping.
        """
        self.conn = conn
        self.connaddr = addr
        req = self.request
        resp = self.response

        try:
            # Read until complete headers + body
            data = b""
            conn.settimeout(30.0)
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\r\n\r\n" in data:
                    header_part, body_part = data.split(b"\r\n\r\n", 1)
                    content_length = 0
                    for line in header_part.decode("utf-8", errors="replace").split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            try:
                                content_length = int(line.split(":", 1)[1].strip())
                            except ValueError:
                                pass
                            break
                    if len(body_part) >= content_length:
                        break

            if not data:
                conn.close()
                return

            msg = data.decode("utf-8", errors="replace")
            req.prepare(msg, routes)

            if not req.method:
                conn.sendall(resp.build_notfound())
                conn.close()
                return

            # If there is a route hook, invoke it
            if req.hook:
                hook_body, hook_hdrs, hook_status, hook_reason = self._invoke_hook(req.hook, req)
                ct = hook_hdrs.get("Content-Type",
                    "application/json" if hook_body and hook_body[:1] in (b"{", b"[") else "application/octet-stream"
                )
                all_extra = dict(resp.extra_headers)
                all_extra.update({k: v for k, v in hook_hdrs.items() if k != "Content-Type"})
                response_bytes = resp.build_response_header(
                    status_code=hook_status, reason=hook_reason,
                    content_type=ct,
                    content_length=len(hook_body),
                    extra_headers=all_extra
                ) + hook_body
            else:
                # Serve static file
                response_bytes = resp.build_response(req)

            conn.sendall(response_bytes)

        except Exception as e:
            print("[HttpAdapter] handle_client error: {}".format(e))
            traceback.print_exc()
            try:
                conn.sendall(resp.build_notfound())
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    async def handle_client_coroutine(self, reader, writer):
        """Handle client connection asynchronously via StreamReader/Writer.

        :param reader (asyncio.StreamReader): Async stream reader.
        :param writer (asyncio.StreamWriter): Async stream writer.
        """
        req = self.request
        resp = self.response
        addr = writer.get_extra_info("peername")

        try:
            # Read until we have the full header section
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = await asyncio.wait_for(reader.read(4096), timeout=30.0)
                if not chunk:
                    writer.close()
                    return
                data += chunk

            # Then read body up to Content-Length
            header_part, body_part = data.split(b"\r\n\r\n", 1)
            content_length = 0
            for line in header_part.decode("utf-8", errors="replace").split("\r\n"):
                if line.lower().startswith("content-length:"):
                    try:
                        content_length = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                    break
            while len(body_part) < content_length:
                chunk = await asyncio.wait_for(reader.read(4096), timeout=30.0)
                if not chunk:
                    break
                body_part += chunk
            data = header_part + b"\r\n\r\n" + body_part

            if not data:
                writer.close()
                return

            msg = data.decode("utf-8", errors="replace")
            req.prepare(msg, self.routes)

            if not req.method:
                writer.write(resp.build_notfound())
                await writer.drain()
                writer.close()
                return

            if req.hook:
                hook = req.hook
                headers_str = str(req.headers)
                body_str = req.body or ""
                if not body_str.strip() and req.query_params:
                    body_str = json.dumps(req.query_params)

                if inspect.iscoroutinefunction(hook):
                    raw_result = await hook(headers_str, body_str)
                else:
                    loop = asyncio.get_event_loop()
                    raw_result = await loop.run_in_executor(None, hook, headers_str, body_str)

                hook_body, hook_hdrs, hook_status, hook_reason = self._parse_hook_result(raw_result)

                ct = "application/json" if hook_body and hook_body[:1] in (b"{", b"[") else "application/octet-stream"
                all_extra = dict(resp.extra_headers)
                all_extra.update(hook_hdrs)
                response_bytes = resp.build_response_header(
                    status_code=hook_status, reason=hook_reason,
                    content_type=ct,
                    content_length=len(hook_body),
                    extra_headers=all_extra
                ) + hook_body
            else:
                response_bytes = resp.build_response(req)

            writer.write(response_bytes)
            await writer.drain()

        except asyncio.TimeoutError:
            print("[HttpAdapter] Coroutine timeout for {}".format(addr))
        except Exception as e:
            print("[HttpAdapter] Coroutine error: {}".format(e))
            traceback.print_exc()
            try:
                writer.write(resp.build_notfound())
                await writer.drain()
            except Exception:
                pass
        finally:
            try:
                writer.close()
            except Exception:
                pass

    @property
    def extract_cookies(self):
        """Extract cookies from request headers.

        :rtype: dict
        """
        return self.request.cookies

    def add_headers(self, request):
        """Add headers to request (override in subclasses)."""
        pass

    def build_proxy_headers(self, proxy):
        """Build proxy authorization headers.

        :param proxy: Proxy URL.
        :rtype: dict
        """
        headers = {}
        username, password = ("user1", "password")
        if username:
            headers["Proxy-Authorization"] = (username, password)
        return headers
