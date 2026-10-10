#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A guard before publishing: does this repository hold anything it should not?

    python3 tools/check_public.py
    python3 tools/check_public.py --range <git log revision arguments>

Four things are checked:

1. **No records are tracked.** The layout under journal/ is held by .gitkeep
   files and nothing else may live there, nor in .trash/ or .drafts/, because
   one careless `git add -A` would be enough to publish somebody's trading
   history. With `--range`, the commits a push would publish are looked
   through as well (`git log --name-only` over the given revisions), so a
   record that was added and removed again is still found in the history.
2. **No Cyrillic anywhere.** The project is written in English throughout,
   code, comments, documents and commit messages alike, so any Cyrillic in a
   tracked file means text from the records or from private notes has leaked in.
   A blunt rule on purpose: it fires on an honest slip rather than trying to be
   clever.
3. **No obvious private markers**: absolute home paths and 32-character
   hexadecimal ids from the previous system.
4. **No long dashes.** The punctuation here is plain: a comma, a colon, a
   semicolon or a full stop carries the clause instead. The rule covers the
   interface as well, where a plain hyphen stands for an empty value.

Exits non-zero when something is found, so CI and a pre-push hook can lean on it.
"""
import os
import re
import subprocess
import sys

CYRILLIC = re.compile(r"[Ѐ-ӿ]")
HOME_PATH = re.compile(r"/home/[a-z0-9_-]+/")
FOREIGN_ID = re.compile(r"\b[0-9a-f]{32}\b")
# written as escapes so that the guard does not trip over its own pattern
LONG_DASH = re.compile("[\u2014\u2013]")

# No exceptions: this repository is written in English, full stop. The one file
# that used to need Cyrillic, a migration tool naming the old header keys, now
# lives with the records it converted, in the private data repository.
CYRILLIC_ALLOWED = {"tools/check_public.py"}
# A placeholder id in the tests is not a real one.
FOREIGN_ID_ALLOWED = {"tests/test_store.py", "tools/check_public.py"}
SKIP_DIRS = {".git", "__pycache__", ".trash", ".drafts", "journal"}
SKIP_SUFFIX = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".bundle")


def is_layout(path):
    """The only thing allowed under journal/: the file that holds a folder."""
    return path.startswith("journal/") and path.endswith(".gitkeep")


def tracked_records():
    try:
        files = subprocess.run(["git", "ls-files", "journal", ".trash", ".drafts"],
                               text=True, capture_output=True, check=True).stdout.split("\n")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [f for f in files if f and not is_layout(f)]


def history_records(revisions):
    """Records in the commits that `git log <revisions>` names, even when a
    later commit removed them again. Returns (paths, error or None)."""
    try:
        out = subprocess.run(["git", "log", "--name-only", "--format=", *revisions,
                              "--", "journal", ".trash", ".drafts"],
                             text=True, capture_output=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        detail = (getattr(e, "stderr", "") or str(e)).strip()
        return [], detail or "git log failed"
    seen = []
    for f in out.split("\n"):
        if f and not is_layout(f) and f not in seen:
            seen.append(f)
    return seen, None


def scan():
    found = []
    for base, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            # the slash of the lists above on every system, Windows included
            path = os.path.relpath(os.path.join(base, name), ".").replace(os.sep, "/")
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
                elif LONG_DASH.search(line):
                    found.append(f"{path}:{n}: long dash: {line.strip()[:70]}")
    return found


def main():
    # a Windows console may not know the letter a finding quotes; better a
    # question mark in the report than a crash before the report
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    args = sys.argv[1:]
    problems = [f"a record is tracked: {f}" for f in tracked_records()]
    if args and args[0] == "--range":
        if len(args) < 2:
            problems.append("--range needs the revisions to look through")
        else:
            paths, error = history_records(args[1:])
            if error:
                problems.append(f"the history could not be read: {error}")
            problems += [f"a record is in history: {f}" for f in paths]
    problems += scan()
    for p in problems:
        print("FOUND:", p)
    if problems:
        n = len(problems)
        print(f"\n{n} problem{'' if n == 1 else 's'}, this must not be published")
        return 1
    print("clean: no records tracked, nothing private in the tree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
