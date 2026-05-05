#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#

"""
daemon.request
~~~~~~~~~~~~~~~~~

This module provides a Request object to manage and persist
request settings (cookies, auth, headers, body).
"""

from .dictionary import CaseInsensitiveDict
from .utils import parse_cookies, decode_basic_auth


class Request:
    """The fully mutable Request object, containing parsed HTTP request data.

    Usage::
      >>> req = Request()
      >>> req.prepare(raw_http_message, routes)
    """

    __attrs__ = [
        "method", "url", "path", "version", "headers", "body",
        "_raw_headers", "_raw_body", "reason", "cookies",
        "routes", "hook", "auth_user", "query_params",
    ]

    def __init__(self):
        self.method = None
        self.url = None
        self.path = None
        self.version = None
        self.headers = CaseInsensitiveDict()
        self.body = ""
        self._raw_headers = ""
        self._raw_body = ""
        self.cookies = {}
        self.routes = {}
        self.hook = None
        self.auth_user = None
        self.query_params = {}

    def extract_request_line(self, request):
        """Parse the first line: METHOD PATH VERSION.

        :param request (str): Raw HTTP request string.
        :rtype: (str, str, str) or (None, None, None)
        """
        try:
            lines = request.splitlines()
            if not lines:
                return None, None, None
            first_line = lines[0]
            parts = first_line.split()
            if len(parts) < 3:
                return None, None, None
            method, path, version = parts[0], parts[1], parts[2]
            if path == '/':
                path = '/index.html'
            return method, path, version
        except Exception:
            return None, None, None

    def prepare_headers(self, request):
        """Parse HTTP headers into a CaseInsensitiveDict.

        :param request (str): Raw HTTP request string.
        :rtype: CaseInsensitiveDict
        """
        headers = CaseInsensitiveDict()
        lines = request.split('\r\n')
        for line in lines[1:]:
            if ': ' in line:
                key, val = line.split(': ', 1)
                headers[key] = val
            elif ':' in line and not line.startswith(' '):
                key, val = line.split(':', 1)
                headers[key] = val.strip()
        return headers

    def fetch_headers_body(self, request):
        """Split request into header section and body section.

        :param request (str): Raw HTTP request string.
        :rtype: (str, str)
        """
        parts = request.split("\r\n\r\n", 1)
        _headers = parts[0]
        _body = parts[1] if len(parts) > 1 else ""
        return _headers, _body

    def _parse_query_params(self, path):
        """Extract query parameters from path.

        :param path (str): The URL path possibly containing '?key=val&...'.
        :rtype: (str, dict) - clean path and query params dict
        """
        params = {}
        if '?' in path:
            path_part, query_string = path.split('?', 1)
            for pair in query_string.split('&'):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    params[k] = v
            return path_part, params
        return path, params

    def prepare(self, request, routes=None):
        """Prepare the entire request from raw HTTP message.

        :param request (str): Raw HTTP request string.
        :param routes (dict): Route handlers mapping.
        """
        if not request or not request.strip():
            self.method = None
            self.path = None
            self.version = None
            return

        # Parse request line
        self.method, self.path, self.version = self.extract_request_line(request)
        if not self.method:
            return

        # Parse query params from path
        self.path, self.query_params = self._parse_query_params(self.path)

        # Parse headers and body
        self._raw_headers, self._raw_body = self.fetch_headers_body(request)
        self.headers = self.prepare_headers(request)
        self.body = self._raw_body

        # Parse cookies from header
        cookie_header = self.headers.get('cookie', '')
        self.cookies = parse_cookies(cookie_header)

        # Parse Basic Auth if present
        auth_header = self.headers.get('authorization', '')
        if auth_header.startswith('Basic '):
            encoded = auth_header[6:]
            username, password = decode_basic_auth(encoded)
            self.auth_user = (username, password)

        # Hook into routes if available
        if routes and routes != {}:
            self.routes = routes
            self.hook = routes.get((self.method, self.path))

        self.url = self.path

    def prepare_body(self, data, files=None, json_data=None):
        """Prepare request body."""
        self.body = data or ""

    def prepare_content_length(self, body):
        """Set Content-Length header."""
        if body:
            self.headers["Content-Length"] = str(len(body))
        else:
            self.headers["Content-Length"] = "0"

    def prepare_auth(self, auth, url=""):
        """Prepare auth tuple (username, password)."""
        self.auth_user = auth

    def prepare_cookies(self, cookies):
        """Set cookies from dict or string."""
        if isinstance(cookies, dict):
            cookie_str = "; ".join(
                "{}={}".format(k, v) for k, v in cookies.items()
            )
            self.headers["Cookie"] = cookie_str
        else:
            self.headers["Cookie"] = str(cookies)
