#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reading and writing a markdown file with a front matter header.

The format is deliberately simple, a subset of YAML, so the project needs no
dependencies and the files stay readable by eye:

    ---
    account: bybit
    pair: EURUSD
    execution:
      - M15
      - M5
    ---

    body in markdown

Values are not typed here: everything comes back as a string (or a list of
strings). Turning them into numbers and dates is model.py's job.
"""

SEP = "---"


def parse(text):
    """Split a file into (header: dict, body: str). The header may be absent."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != SEP:
        return {}, text.strip("\n")

    head, i = {}, 1
    key = None                      # the key the list items below belong to
    while i < len(lines) and lines[i].strip() != SEP:
        line = lines[i]
        i += 1
        if not line.strip():
            continue
        if line.lstrip().startswith("- ") and key is not None:
            head.setdefault(key, [])
            if not isinstance(head[key], list):
                head[key] = [head[key]] if head[key] else []
            head[key].append(unescape(line.lstrip()[2:].strip()))
            continue
        if ":" not in line:
            raise ValueError(f"header: line without a colon: {line!r}")
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        head[key] = unescape(value) if value else []
    if i >= len(lines):
        raise ValueError("unterminated header: no closing --- line")

    body = "\n".join(lines[i + 1:]).strip("\n")
    return head, body


def dump(head, body=""):
    """Put the file back together. Key order follows the dict given."""
    out = [SEP]
    for key, value in head.items():
        if isinstance(value, (list, tuple)):
            out.append(f"{key}:")
            out.extend(f"  - {escape(str(v))}" for v in value)
        else:
            out.append(f"{key}: {escape(str(value))}")
    out.append(SEP)
    text = "\n".join(out)
    if body.strip():
        text += "\n\n" + body.strip("\n")
    return text + "\n"


# Values go in as they are, but blank and multi-line ones would break the format.
def escape(value):
    return value.replace("\n", " ").strip()


def unescape(value):
    return value.strip()
