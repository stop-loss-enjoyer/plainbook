#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A guard before publishing: does this repository hold anything it should not?

    python3 tools/check_public.py
    python3 tools/check_public.py --range <git log revision arguments>

It works from the top of the repository, whatever folder it is started in.
Five things are checked:

1. **No records are tracked.** The layout under journal/ is held by .gitkeep
   files and nothing else may live there, nor in .trash/, .drafts/ or
   .restore/ (a backup being restored, unpacked), nor in a folder of one of
   these names further down, because one careless `git add -A` would be
   enough to publish somebody's trading history. A backup of a journal, a
   `.plainbook` file, is refused wherever it stands.
2. **No Cyrillic anywhere.** The project is written in English throughout,
   code, comments, documents, file names and commit messages alike, so any
   Cyrillic in a tracked file means text from the records or from private
   notes has leaked in. A blunt rule on purpose: it fires on an honest slip
   rather than trying to be clever.
3. **No obvious private markers**: absolute home paths of Linux, macOS and
   Windows (NAME, the placeholder of the samples in desktop/, is not a
   person) and 32-character hexadecimal ids from the previous system.
4. **No long dashes.** The punctuation here is plain: a comma, a colon, a
   semicolon or a full stop carries the clause instead. The rule covers the
   interface as well, where a plain hyphen stands for an empty value.
5. **Nothing goes unread.** A tracked file that is not UTF-8 text is refused
   unless it is a picture whose first bytes say so. A file that cannot be
   opened, a blob git does not hand over, a repository git will not read:
   each is a finding, never a pass.

With `--range`, what a push would publish is looked through as well: every
file the commits of the given revisions add or change, as each of them holds
it, so text committed and cleaned afterwards, or added and removed within the
range, is still found; the tree of the newest of them; their messages and the
message of an annotated tag named; and every path they touch in a folder of
rule 1, a removal included. A shallow checkout that does not hold the whole
range is refused rather than half read.

Exits non-zero when something is found, so CI and a pre-push hook can lean on it.
"""
import os
import re
import subprocess
import sys

# written as escapes so that the guard does not trip over its own patterns
CYRILLIC = re.compile("[\u0400-\u04ff]")
HOME_PATH = re.compile(r"/home/[a-z0-9_-]+/"
                       r"|/Users/(?!(?:NAME|Shared)/)[A-Za-z0-9._-]+/"
                       r"|\\[Uu][Ss][Ee][Rr][Ss]\\+(?!NAME\\)[A-Za-z0-9._ -]+\\")
FOREIGN_ID = re.compile(r"\b[0-9a-f]{32}\b")
LONG_DASH = re.compile("[\u2012-\u2015\u2e3a\u2e3b]")
# What each pattern needs in the bytes, cheap to look for: a whole history is
# read on a new branch, and most of it holds none of them.
CYRILLIC_MARKS = tuple(bytes([lead]) for lead in range(0xD0, 0xD4))
DASH_MARKS = tuple(chr(dash).encode("utf-8") for dash in (0x2012, 0x2013, 0x2014, 0x2015, 0x2E3A, 0x2E3B))
HOME_MARKS = (b"/home/", b"/users/", b"users\\")     # looked for in lower case
HEX = bytes(b"x"[0] if chr(c) in "0123456789abcdef" else b" "[0] for c in range(256))

# No exceptions: this repository is written in English, full stop. The one file
# that used to need Cyrillic, a migration tool naming the old header keys, now
# lives with the records it converted, in the private data repository; older
# copies of this file held the letters of their pattern as they are.
CYRILLIC_ALLOWED = {"tools/check_public.py"}
# A placeholder id in the tests is not a real one.
FOREIGN_ID_ALLOWED = {"tests/test_store.py", "tools/check_public.py"}
PRIVATE_DIRS = {"journal", ".trash", ".drafts", ".restore"}
NEVER_LOOKED_IN = {".git", "__pycache__"}
PICTURES = {".png": (b"\x89PNG\r\n\x1a\n",), ".jpg": (b"\xff\xd8\xff",),
            ".jpeg": (b"\xff\xd8\xff",), ".gif": (b"GIF87a", b"GIF89a"), ".webp": ()}
GITLINK = "160000"

# The first six commits, up to the one that brought this guard in, were
# published before its rules and keep the long dashes and the Cyrillic header
# names of the old format. They were looked through by hand on 10.11.2026 and
# hold no record, so their content is not read again, or a whole history (a
# new branch in CI, a new remote) could never pass. The paths they touch are
# still looked at for records.
PUBLISHED_BEFORE_THE_RULES = "5b912b8eb8ed66904708f43d1c5df3b37e9259b8"


class GitError(Exception):
    pass


def git(*args):
    """What git prints, as bytes: on Windows a text pipe would read UTF-8 as
    the local code page and the Cyrillic it carries would slip past."""
    try:
        done = subprocess.run(["git", "-c", "core.quotePath=false", *args],
                              stdin=subprocess.DEVNULL, capture_output=True)
    except OSError as e:
        raise GitError(f"git could not be run: {e}")
    if done.returncode:
        said = done.stderr.decode("utf-8", "replace").strip()
        raise GitError(said or f"git {args[0]} failed")
    return done.stdout


def name_of(raw, problems):
    """A path as git spells it. One that is not UTF-8 is named, not dropped."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        name = raw.decode("utf-8", "surrogateescape")
        problems.append(f"a file name that is not UTF-8: {name!r}")
        return name


def held_by_a_repository():
    if os.environ.get("GIT_DIR"):
        return True
    here = os.path.abspath(os.getcwd())
    while True:
        if os.path.lexists(os.path.join(here, ".git")):
            return True
        up = os.path.dirname(here)
        if up == here:
            return False
        here = up


def find_root():
    """(the top of the repository, None); (None, None) for a folder that no
    repository holds, where there is nothing to publish; (None, the reason)
    when there is a repository and git cannot be asked about it."""
    try:
        top = git("rev-parse", "--show-toplevel").decode("utf-8", "surrogateescape").rstrip("\r\n")
        return top, None
    except GitError as e:
        if held_by_a_repository():
            return None, f"git could not read this repository: {e}"
        return None, None


def is_layout(path):
    """The only thing allowed under journal/: the file that holds a folder."""
    parts = path.split("/")
    return (parts[0] == "journal" and parts[-1] == ".gitkeep"
            and not PRIVATE_DIRS.intersection(parts[1:-1]))


def is_record(path):
    parts = path.split("/")
    if parts[-1].lower().endswith(".plainbook"):
        return True
    return bool(PRIVATE_DIRS.intersection(parts[:-1])) and not is_layout(path)


def is_picture(path, data):
    kind = os.path.splitext(path)[1].lower()
    if kind == ".webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return data.startswith(PICTURES[kind])


def markers_possible(data):
    """Which patterns can match the text of these bytes: a pattern left out
    cannot match it, so its search is spared."""
    lower = data.lower()
    return (any(mark in data for mark in CYRILLIC_MARKS),
            any(mark in lower for mark in HOME_MARKS),
            b"x" * 32 in data.translate(HEX),
            any(mark in data for mark in DASH_MARKS))


def look_at(path, data, where, strict):
    """The findings of one file: its path as published, its bytes, how to name
    it in a finding. Strict is for a file that is or would be published."""
    found = [f"{where}: {what} in the file name" for what, rx in
             (("cyrillic", CYRILLIC), ("long dash", LONG_DASH)) if rx.search(path)]
    if strict and is_record(path):
        return found                    # named as a record already
    if os.path.splitext(path)[1].lower() in PICTURES:
        if strict and not is_picture(path, data):
            found.append(f"{where}: not the picture its name says, so it cannot be looked through")
        return found
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        if strict:
            found.append(f"{where}: not UTF-8 text, so it cannot be looked through")
        return found
    cyrillic, home, foreign, dash = markers_possible(data)
    cyrillic = cyrillic and path not in CYRILLIC_ALLOWED and CYRILLIC.search(text)
    home = home and HOME_PATH.search(text)
    foreign = foreign and path not in FOREIGN_ID_ALLOWED and FOREIGN_ID.search(text)
    dash = dash and LONG_DASH.search(text)
    if not (cyrillic or home or foreign or dash):
        return found
    for n, line in enumerate(text.split("\n"), 1):
        if cyrillic and CYRILLIC.search(line):
            found.append(f"{where}:{n}: cyrillic: {line.strip()[:70]}")
        elif home and HOME_PATH.search(line):
            found.append(f"{where}:{n}: home path: {line.strip()[:70]}")
        elif foreign and FOREIGN_ID.search(line):
            found.append(f"{where}:{n}: foreign id: {line.strip()[:70]}")
        elif dash and LONG_DASH.search(line):
            found.append(f"{where}:{n}: long dash: {line.strip()[:70]}")
    return found


def tracked_files(problems):
    """Every path in the index with its mode, conflicts and staged files included."""
    entries = {}
    for item in git("ls-files", "-z", "-s").split(b"\0"):
        if item:
            meta, _, raw = item.partition(b"\t")
            entries[name_of(raw, problems)] = meta.split()[0].decode("ascii")
    return entries


def read_file(path, strict):
    try:
        if os.path.islink(path):
            # a link is published as the place it points to, not what is there
            data = os.readlink(path).encode("utf-8", "surrogateescape")
        else:
            with open(path, "rb") as f:
                data = f.read()
    except OSError as e:
        return [f"{path}: could not be read ({e.strerror or e})"] if strict else []
    return look_at(path, data, path, strict)


def scan_tree(tracked):
    """The files on the disk: every tracked one, and the untracked ones that
    could be added next. The record folders are passed over at the top only,
    where the journal of a checkout run from source lives."""
    found, seen = [], set()
    for base, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in NEVER_LOOKED_IN
                   and not (base == "." and d in PRIVATE_DIRS)]
        for name in files:
            # the slash of the lists above on every system, Windows included
            path = os.path.relpath(os.path.join(base, name), ".").replace(os.sep, "/")
            seen.add(path)
            found += read_file(path, path in tracked)
    # a tracked file the walk did not reach (a folder it may not enter, a
    # link to a folder) is read by its own path, or named
    for path, mode in tracked.items():
        if path in seen or mode == GITLINK or is_record(path) or not os.path.lexists(path):
            continue
        found += read_file(path, True)
    return found


def blobs(ids):
    """(id, bytes) for each id, the bytes None when git does not hand it over."""
    proc = subprocess.Popen(["git", "cat-file", "--batch"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        for blob in ids:
            proc.stdin.write(blob.encode("ascii") + b"\n")
            proc.stdin.flush()
            head = proc.stdout.readline().split()
            if len(head) != 3 or head[1] != b"blob":
                yield blob, None
                continue
            size = int(head[2])
            data = proc.stdout.read(size)
            proc.stdout.read(1)
            yield blob, data if len(data) == size else None
    finally:
        proc.stdin.close()
        proc.stdout.close()
        proc.wait()


def published_before_the_rules():
    try:
        return set(git("rev-list", PUBLISHED_BEFORE_THE_RULES).decode("ascii").split())
    except GitError:
        return set()                    # not this history: nothing is spared


def shallow_commits(problems):
    """The commits a shallow checkout holds without their parents."""
    try:
        where = git("rev-parse", "--git-path", "shallow").decode("utf-8", "surrogateescape").rstrip("\r\n")
        with open(where, encoding="ascii") as f:
            return set(f.read().split())
    except FileNotFoundError:
        return set()
    except (GitError, OSError, ValueError) as e:
        problems.append(f"whether the checkout is shallow could not be read: {e}")
        return set()


def parse_log(out, problems):
    """The commits of `git log -z --raw` with their parents and messages, and
    each path it shows as (commit, path, mode, blob, status)."""
    commits, touched = {}, []
    tokens = out.split(b"\0")
    i, commit = 0, None
    while i < len(tokens):
        token = tokens[i].lstrip(b"\n")
        i += 1
        if token.startswith(b"\x01"):
            head, _, message = token[1:].partition(b"\x02")
            ids = head.decode("ascii").split()
            commit = ids[0]
            commits[commit] = (ids[1:], message)
        elif token.startswith(b":") and len(token[1:].split()) == 5 and i < len(tokens):
            meta = token[1:].decode("ascii").split()
            touched.append((commit, name_of(tokens[i], problems), meta[1], meta[3], meta[4][:1]))
            i += 1
        elif token:
            problems.append(f"the history could not be read: git printed {token[:40]!r}")
    return commits, touched


def check_message(named, message):
    try:
        text = message.decode("utf-8")
    except UnicodeDecodeError:
        return [f"{named}: the message is not UTF-8, so it cannot be looked through"]
    found = []
    for what, rx in (("cyrillic", CYRILLIC), ("long dash", LONG_DASH)):
        for line in text.split("\n"):
            if rx.search(line):
                found.append(f"{named}: {what} in the message: {line.strip()[:70]}")
                break
    return found


def tag_messages(revisions):
    """An annotated tag named on the command line is published with its message."""
    found = []
    for arg in revisions:
        if arg.startswith("-"):
            continue
        for side in re.split(r"\.\.\.?", arg):
            side = side.lstrip("^")
            try:
                if not side or git("cat-file", "-t", side).strip() != b"tag":
                    continue
                body = git("cat-file", "tag", side).partition(b"\n\n")[2]
            except GitError:
                continue                # git log has named a bad revision already
            found += check_message(f"tag {side}", body)
    return found


def history(revisions):
    """The findings in what `git log <revisions>` names."""
    problems = []
    try:
        # one diff of a merge against each parent, whatever log.diffMerges says,
        # so that a change made in the merge itself is read too
        out = git("-c", "log.diffMerges=separate", "log", "-z", "--raw", "--no-abbrev",
                  "--no-renames", "-m", "--root",
                  "--no-color", "--no-show-signature", "--format=%x01%H %P%x02%B", *revisions)
    except GitError as e:
        return [f"the history could not be read: {e}"]
    commits, touched = parse_log(out, problems)
    for path in dict.fromkeys(p for _, p, _, _, _ in touched):
        if is_record(path):
            problems.append(f"a record is in history: {path}")
    spared = published_before_the_rules()
    fresh = [c for c in commits if c not in spared]
    cut = shallow_commits(problems).intersection(fresh)
    if cut:
        problems.append(f"the checkout is shallow: the history behind {sorted(cut)[0][:9]} is not "
                        "here to be looked through; fetch it whole (fetch-depth: 0)")
    for commit in fresh:
        problems += check_message(f"commit {commit[:9]}", commits[commit][1])
    problems += tag_messages(revisions)
    where = {}                          # blob: {path: the commit that brought it}
    for commit, path, mode, blob, status in touched:
        if status != "D" and mode != GITLINK and commit not in spared:
            where.setdefault(blob, {})[path] = commit   # the log runs newest first
    parents = {p for c in fresh for p in commits[c][0]}
    for tip in (c for c in fresh if c not in parents):
        try:
            listing = git("ls-tree", "-r", "-z", "--full-tree", tip)
        except GitError as e:
            problems.append(f"the tree of {tip[:9]} could not be read: {e}")
            continue
        for item in listing.split(b"\0"):
            meta, _, raw = item.partition(b"\t")
            meta = meta.decode("ascii").split()
            if len(meta) == 3 and meta[1] == "blob":
                where.setdefault(meta[2], {}).setdefault(name_of(raw, problems), tip)
    try:
        for blob, data in blobs(sorted(where)):
            for path, commit in where[blob].items():
                named = f"{path} in {commit[:9]}"
                if data is None:
                    problems.append(f"{named}: git did not hand it over, so it cannot be looked through")
                else:
                    problems += look_at(path, data, named, True)
    except OSError as e:
        problems.append(f"the files of the history could not be read: {e}")
    return problems


def main():
    # a Windows console may not know the letter a finding quotes; better a
    # question mark in the report than a crash before the report
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    args = sys.argv[1:]
    problems = []
    root, trouble = find_root()
    if trouble:
        problems.append(trouble)
    tracked = {}
    if root:
        os.chdir(root)
        try:
            tracked = tracked_files(problems)
        except GitError as e:
            problems.append(f"the tracked files could not be listed: {e}")
    problems += [f"a record is tracked: {f}" for f in tracked if is_record(f)]
    if args and args[0] == "--range":
        if len(args) < 2:
            problems.append("--range needs the revisions to look through")
        else:
            problems += history(args[1:])
    problems += scan_tree(tracked)
    problems = list(dict.fromkeys(problems))
    for p in problems:
        print("FOUND:", p)
    if problems:
        n = len(problems)
        print(f"\n{n} problem{'' if n == 1 else 's'}, this must not be published")
        return 1
    if root:
        print("clean: no records tracked, nothing private in the tree")
    else:
        print("clean: not a git repository, so nothing is tracked; nothing private in these files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
