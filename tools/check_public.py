#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A guard before publishing: does this repository hold anything private?

    python3 tools/check_public.py

Three things are checked:

1. **No records are tracked.** The layout under journal/ is held by .gitkeep
   files and nothing else may live there — one careless `git add -A` would be
   enough to publish somebody's trading history.
2. **No Cyrillic outside the migration tool.** The project is written in English
   throughout, so any Cyrillic in a tracked file means text from the records or
   from private notes has leaked in. A blunt rule on purpose: it fires on an
   honest slip rather than trying to be clever.
3. **No obvious private markers**: absolute home paths and 32-character
   hexadecimal ids from the previous system.

Exits non-zero when something is found, so CI and a pre-push hook can lean on it.
"""
import os
import re
import subprocess
import sys

CYRILLIC = re.compile(r"[Ѐ-ӿ]")
HOME_PATH = re.compile(r"/home/[a-z0-9_-]+/")
FOREIGN_ID = re.compile(r"\b[0-9a-f]{32}\b")

# Three files carry Cyrillic on purpose: the migration tool names the old keys,
# the changelog quotes them to explain the change, and one test feeds a non-latin
# id to check that it is refused.
CYRILLIC_ALLOWED = {"tools/migrate_ru_to_en.py", "tools/check_public.py",
                    "CHANGELOG.md", "tests/test_server.py"}
# A placeholder id in the tests is not a real one.
FOREIGN_ID_ALLOWED = {"tests/test_store.py", "tools/check_public.py"}
SKIP_DIRS = {".git", "__pycache__", ".trash", ".drafts", "journal"}
SKIP_SUFFIX = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".bundle")


def tracked_records():
    try:
        files = subprocess.run(["git", "ls-files", "journal"], text=True,
                               capture_output=True, check=True).stdout.split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [f for f in files if not f.endswith(".gitkeep")]


def scan():
    found = []
    for base, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            path = os.path.relpath(os.path.join(base, name), ".")
            if path.endswith(SKIP_SUFFIX):
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    lines = f.read().split("\n")
            except (UnicodeDecodeError, OSError):
                continue
            for n, line in enumerate(lines, 1):
                if CYRILLIC.search(line) and path not in CYRILLIC_ALLOWED:
                    found.append(f"{path}:{n}: cyrillic: {line.strip()[:70]}")
                elif HOME_PATH.search(line):
                    found.append(f"{path}:{n}: home path: {line.strip()[:70]}")
                elif FOREIGN_ID.search(line) and path not in FOREIGN_ID_ALLOWED:
                    found.append(f"{path}:{n}: foreign id: {line.strip()[:70]}")
    return found


def main():
    problems = [f"a record is tracked: {f}" for f in tracked_records()]
    problems += scan()
    for p in problems:
        print("PRIVATE:", p)
    if problems:
        print(f"\n{len(problems)} problems — this must not be published")
        return 1
    print("clean: no records tracked, nothing private in the tree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
