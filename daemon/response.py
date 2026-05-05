#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#

"""
daemon.response
~~~~~~~~~~~~~~~~~

This module provides a Response object to construct HTTP responses
including headers, content, status codes, and cookies.
"""

import datetime
import os
import mimetypes
import json

from .dictionary import CaseInsensitiveDict

BASE_DIR = ""


class Response:
    """HTTP Response builder.

    Constructs full HTTP responses with status line, headers, and body.
    Supports static file serving, JSON responses, redirects, and auth challenges.
    """

    __attrs__ = [
        "_content", "_header", "status_code", "method", "headers",
        "url", "history", "encoding", "reason", "cookies",
        "elapsed", "request", "body",
    ]

    def __init__(self, request=None):
        self._content = b""
        self._header = b""
        self._content_consumed = False
        self.status_code = 200
        self.headers = CaseInsensitiveDict()
        self.url = None
        self.encoding = "utf-8"
        self.history = []
        self.reason = "OK"
        self.cookies = CaseInsensitiveDict()
        self.elapsed = datetime.timedelta(0)
        self.request = request
        self.extra_headers = {}

    def get_mime_type(self, path):
        """Determine MIME type from file path.

        :param path (str): File path.
        :rtype: str
        """
        try:
            mime_type, _ = mimetypes.guess_type(path)
        except Exception:
            return 'application/octet-stream'
        return mime_type or 'application/octet-stream'

    def prepare_content_type(self, mime_type='text/html'):
        """Set Content-Type and determine base directory for file serving.

        :param mime_type (str): MIME type string.
        :rtype: str - base directory path.
        """
        base_dir = ""
        if not hasattr(self, "headers") or self.headers is None:
            self.headers = CaseInsensitiveDict()

        main_type, sub_type = mime_type.split('/', 1)

        if main_type == 'text':
            self.headers['Content-Type'] = 'text/{}'.format(sub_type)
            if sub_type in ('plain', 'css'):
                base_dir = BASE_DIR + "static/"
            elif sub_type == 'html':
                base_dir = BASE_DIR + "www/"
            elif sub_type == 'javascript':
                base_dir = BASE_DIR + "static/"
            else:
                base_dir = BASE_DIR + "static/"
        elif main_type == 'image':
            base_dir = BASE_DIR + "static/"
            self.headers['Content-Type'] = 'image/{}'.format(sub_type)
        elif main_type == 'application':
            if sub_type == 'javascript':
                base_dir = BASE_DIR + "static/"
            else:
                base_dir = BASE_DIR + "apps/"
            self.headers['Content-Type'] = 'application/{}'.format(sub_type)
        else:
            base_dir = BASE_DIR + "static/"
            self.headers['Content-Type'] = '{}/{}'.format(main_type, sub_type)

        return base_dir

    def build_content(self, path, base_dir):
        """Load file content from disk.

        :param path (str): Relative file path.
        :param base_dir (str): Base directory.
        :rtype: (int, bytes)
        """
        filepath = os.path.join(base_dir, path.lstrip('/'))
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            return len(content), content
        except Exception as e:
            print("[Response] build_content exception: {}".format(e))
            return -1, b""

    def build_response_header(self, status_code=200, reason="OK",
                              content_type="text/html",
                              content_length=0,
                              extra_headers=None):
        """Build HTTP response header bytes.

        :param status_code (int): HTTP status code.
        :param reason (str): Status reason phrase.
        :param content_type (str): Content-Type header value.
        :param content_length (int): Content-Length value.
        :param extra_headers (dict): Additional headers to include.
        :rtype: bytes
        """
        now = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        header_lines = [
            "HTTP/1.1 {} {}".format(status_code, reason),
            "Date: {}".format(now),
            "Content-Type: {}".format(content_type),
            "Content-Length: {}".format(content_length),
            "Connection: close",
            "Cache-Control: no-cache",
        ]

        if extra_headers:
            for key, value in extra_headers.items():
                header_lines.append("{}: {}".format(key, value))

        header_str = "\r\n".join(header_lines) + "\r\n\r\n"
        return header_str.encode("utf-8")

    def build_notfound(self):
        """Construct a 404 Not Found response.

        :rtype: bytes
        """
        body = b"404 Not Found"
        header = self.build_response_header(
            status_code=404, reason="Not Found",
            content_type="text/html",
            content_length=len(body)
        )
        return header + body

    def build_json(self, data, status_code=200, reason="OK",
                   extra_headers=None):
        """Build a JSON HTTP response.

        :param data: Dict/list to serialize as JSON body.
        :param status_code (int): HTTP status code.
        :param reason (str): Reason phrase.
        :param extra_headers (dict): Extra headers.
        :rtype: bytes
        """
        body = json.dumps(data).encode("utf-8")
        header = self.build_response_header(
            status_code=status_code, reason=reason,
            content_type="application/json",
            content_length=len(body),
            extra_headers=extra_headers
        )
        return header + body

    def build_unauthorized(self, realm="Restricted"):
        """Build 401 Unauthorized with WWW-Authenticate challenge.

        :param realm (str): The authentication realm.
        :rtype: bytes
        """
        body = b"401 Unauthorized"
        header = self.build_response_header(
            status_code=401, reason="Unauthorized",
            content_type="text/html",
            content_length=len(body),
            extra_headers={"WWW-Authenticate": 'Basic realm="{}"'.format(realm)}
        )
        return header + body

    def build_forbidden(self):
        """Build 403 Forbidden response.

        :rtype: bytes
        """
        body = b"403 Forbidden"
        header = self.build_response_header(
            status_code=403, reason="Forbidden",
            content_type="text/html",
            content_length=len(body)
        )
        return header + body

    def build_redirect(self, location, status_code=302):
        """Build a redirect response.

        :param location (str): Redirect target URL.
        :param status_code (int): 301 or 302.
        :rtype: bytes
        """
        body = b""
        header = self.build_response_header(
            status_code=status_code, reason="Found",
            content_type="text/html",
            content_length=0,
            extra_headers={"Location": location}
        )
        return header + body

    def build_response(self, request, envelop_content=None):
        """Build full HTTP response for a given request.

        Serves static files (HTML, CSS, images, JS) based on path and MIME type.

        :param request: The Request object.
        :param envelop_content: Optional pre-built content.
        :rtype: bytes
        """
        path = request.path
        if not path:
            return self.build_notfound()

        mime_type = self.get_mime_type(path)

        # Route to correct base directory
        if path.endswith('.html') or mime_type == 'text/html':
            base_dir = self.prepare_content_type(mime_type='text/html')
        elif mime_type == 'text/css':
            base_dir = self.prepare_content_type(mime_type='text/css')
        elif 'javascript' in mime_type:
            base_dir = self.prepare_content_type(mime_type=mime_type)
        elif mime_type.startswith('image/'):
            base_dir = self.prepare_content_type(mime_type=mime_type)
        elif mime_type in ('application/json', 'application/octet-stream'):
            if envelop_content:
                body = envelop_content
                if isinstance(body, str):
                    body = body.encode("utf-8")
                header = self.build_response_header(
                    content_type="application/octet-stream",
                    content_length=len(body)
                )
                return header + body
            base_dir = self.prepare_content_type(mime_type='application/json')
        else:
            return self.build_notfound()

        # Load file content
        content_len, content = self.build_content(path, base_dir)
        if content_len < 0:
            return self.build_notfound()

        self._content = content
        ct = self.headers.get('Content-Type', 'text/html')
        self._header = self.build_response_header(
            content_type=ct, content_length=content_len,
            extra_headers=self.extra_headers
        )

        return self._header + self._content
