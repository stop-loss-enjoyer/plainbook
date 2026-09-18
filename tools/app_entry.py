#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The entry of the downloaded file.

The release workflow (.github/workflows/release.yml) hands this script to
PyInstaller, which packs it with a Python and the plainbook package into one
file per system. Run from the source, it is the same as the `plainbook`
command: the server, and the browser opened on it.

    python3 tools/app_entry.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook.server import app  # noqa: E402

app()
