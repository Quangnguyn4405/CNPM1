#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#

"""
daemon.utils
~~~~~~~~~~~~~~~~~

Utility functions for URL parsing, authentication extraction, and helpers.
"""

from urllib.parse import urlparse, unquote
import base64
import hashlib
import uuid
import time
import json


def get_auth_from_url(url):
    """Given a url with authentication components, extract them into a tuple.

    :rtype: (str, str)
    """
    parsed = urlparse(url)
    try:
        auth = (unquote(parsed.username), unquote(parsed.password))
    except (AttributeError, TypeError):
        auth = ("", "")
    return auth


def encode_basic_auth(username, password):
    """Encode username:password into Base64 for HTTP Basic Auth.

    :param username (str): The username.
    :param password (str): The password.
    :rtype: str
    """
    credentials = "{}:{}".format(username, password)
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    return encoded


def decode_basic_auth(encoded):
    """Decode a Base64-encoded Basic Auth string.

    :param encoded (str): The Base64-encoded credentials.
    :rtype: (str, str)
    """
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, password = decoded.split(":", 1)
        return username, password
    except Exception:
        return None, None


def generate_session_id():
    """Generate a unique session identifier.

    :rtype: str
    """
    return hashlib.sha256(
        "{}{}".format(uuid.uuid4().hex, time.time()).encode()
    ).hexdigest()[:32]


def parse_cookies(cookie_header):
    """Parse a Cookie header string into a dictionary.

    :param cookie_header (str): The raw Cookie header value.
    :rtype: dict
    """
    cookies = {}
    if not cookie_header:
        return cookies
    for pair in cookie_header.split(";"):
        pair = pair.strip()
        if "=" in pair:
            key, value = pair.split("=", 1)
            cookies[key.strip()] = value.strip()
    return cookies


def build_json_bytes(data):
    """Serialize a dict/list to JSON bytes.

    :param data: The data to serialize.
    :rtype: bytes
    """
    return json.dumps(data).encode("utf-8")


def get_timestamp():
    """Return current UTC timestamp as ISO string.

    :rtype: str
    """
    import datetime
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
