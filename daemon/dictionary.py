#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#

"""
daemon.dictionary
~~~~~~~~~~~~~~~~~

Provides CaseInsensitiveDict for managing HTTP headers and cookies.
"""

from collections.abc import MutableMapping


class CaseInsensitiveDict(MutableMapping):
    """A case-insensitive dictionary for HTTP headers.

    Usage::
      >>> d = CaseInsensitiveDict(Content_Type='text/html')
      >>> d['content-type']
      'text/html'
    """

    def __init__(self, *args, **kwargs):
        self.store = {}
        if args:
            if isinstance(args[0], dict):
                for k, v in args[0].items():
                    self.store[k.lower()] = v
            elif hasattr(args[0], 'items'):
                for k, v in args[0].items():
                    self.store[k.lower()] = v
        for k, v in kwargs.items():
            self.store[k.lower()] = v

    def __getitem__(self, key):
        return self.store[key.lower()]

    def __setitem__(self, key, value):
        self.store[key.lower()] = value

    def __delitem__(self, key):
        del self.store[key.lower()]

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

    def __contains__(self, key):
        return key.lower() in self.store

    def __repr__(self):
        return str(dict(self.store))

    def get(self, key, default=None):
        return self.store.get(key.lower(), default)
