#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
The whole journal in one file, to keep somewhere else, and back again.

A backup is a ZIP under a name of its own (`.plainbook`), so that a double
click on it can find the journal, and any archiver still opens it renamed:
the records stay plain files even there. Inside:

    manifest.json          what made it, when, the counts, a sha256 per file
    journal/...            the journal folder as it is
    trash/<entry>/...      the records of the trash, restorable as before

Restoring never writes over anything. The file is unpacked into a folder of
its own under `.restore/`, checked against its manifest and shown before it
is taken; taken, the journal it replaces goes to the trash whole, as
`journal-<stamp>.before-restore/`, and can be put back the same way.
"""
import hashlib
import json
import os
import re
import secrets
import shutil
import tempfile
import threading
import unicodedata
import time
import zipfile
from datetime import datetime, timedelta

from . import __version__, store

SUFFIX = ".plainbook"
MANIFEST = "manifest.json"
FORMAT = 1                  # raised when an older journal could not read the file
STAGE = ".restore"          # a file being restored, unpacked, until it is taken
ASIDE = ".before-restore"   # the end of a journal a restore has put in the trash
ERROR = "refused.txt"       # why a file was not taken, for the page that says so
JOURNAL, TRASH = "journal", "trash"
KEEP_STAGED = 24 * 3600     # a restore not taken in a day is not going to be
# a screenshot does not shrink in a zip; passing it through as it is makes a
# backup of a few hundred megabytes take seconds instead of a minute
STORED = (".png", ".jpg", ".jpeg", ".gif", ".webp")
_CHUNK = 1 << 20
_TOKEN = re.compile(r"^[0-9a-f]{16}$")
# One swap at a time: two presses of Restore, or Restore and Put back from
# two tabs, would otherwise move the same folders under each other's hands
_LOCK = threading.Lock()
_TAKEN = {}                 # token: when it was restored, for a second press


class BackupError(Exception):
    """The file is not a backup this journal can take; the message says why."""


def _hash_copy(source, target, limit=None):
    """Copies one open file into another and returns the sha256 of what went."""
    digest = hashlib.sha256()
    copied = 0
    while True:
        chunk = source.read(_CHUNK)
        if not chunk:
            return digest.hexdigest(), copied
        copied += len(chunk)
        if limit is not None and copied > limit:
            raise BackupError("a file inside is larger than the manifest says")
        digest.update(chunk)
        target.write(chunk)


def _files(root, skipped):
    """(name in the backup, path on disk) of everything a backup carries:
    the journal folder and the records of the trash. A repository inside the
    journal and links are left out: neither is a record, and a link would
    carry whatever it points at. A link is named in `skipped`, so the restore
    page can say what the backup does not hold."""
    out = []

    def walk(base, prefix):
        for here, dirs, files in os.walk(base):
            rel_here = os.path.relpath(here, base).replace(os.sep, "/")
            links = [d for d in dirs if os.path.islink(os.path.join(here, d))]
            skipped.extend(f"{prefix}/{rel_here}/{d}".replace("/./", "/") for d in links)
            dirs[:] = sorted(d for d in dirs if d != ".git" and d not in links)
            for name in sorted(files):
                path = os.path.join(here, name)
                rel = os.path.relpath(path, base).replace(os.sep, "/")
                if os.path.islink(path) or not os.path.isfile(path):
                    skipped.append(f"{prefix}/{rel}")
                    continue
                out.append((f"{prefix}/{rel}", path))

    walk(os.path.join(root, store.JOURNAL), JOURNAL)
    trash = os.path.join(root, store.TRASH)
    for name, _, _, _ in sorted(store.trash_list(root)):
        path = os.path.join(trash, name)
        if os.path.isdir(path):
            walk(path, f"{TRASH}/{name}")
        elif os.path.isfile(path):
            out.append((f"{TRASH}/{name}", path))
    return out


def counts(root, trash=None):
    """What a journal holds, in the words the restore page shows it by.
    Every reader takes a problems list, so a record that does not read is
    named and not counted, the way every page of the journal does it.
    `trash` is the folder of the trash records when it is not the root's
    own: a backup being looked at keeps them in trash/."""
    problems = store.unread_lists(root, [])
    found = {}
    for name, reader in (("trades", store.all_trades), ("accounts", store.all_accounts),
                         ("adjustments", store.all_adjustments),
                         ("plans", store.all_plans), ("playbooks", store.all_playbooks),
                         ("notes", store.all_notes), ("cards", store.all_cards),
                         ("weeks", store.all_weeks)):
        found[name] = len(reader(root, problems))
    pictures = 0
    for _, dirs, files in os.walk(os.path.join(root, store.JOURNAL)):
        pictures += sum(1 for f in files if f.lower().endswith(STORED))
    found["screenshots"] = pictures
    found["trash"] = len(store.trash_list(root, trash))
    return found, problems


def _stamp(mtime):
    """The time of a file as a zip can hold it. A file copied by some tools
    says 1970, and a zip holds nothing before 1980 or after 2107: one such
    file must not stop the backup of the rest."""
    try:
        when = time.localtime(mtime)[:6]
    except (OverflowError, OSError, ValueError):
        when = (1980, 1, 1, 0, 0, 0)
    return max((1980, 1, 1, 0, 0, 0), min(when, (2107, 12, 31, 23, 59, 58)))


def make(root, out, now=None):
    """Writes the backup of the journal under root into `out`, an open
    binary file, and returns its manifest. A file that went away or does not
    open while the backup is made (a save in another tab) is named in the
    manifest and left out, rather than costing the backup of the rest."""
    now = now or datetime.now()
    with _LOCK:
        return _make(root, out, now)


def _make(root, out, now):
    files, skipped, seen = {}, [], set()
    with zipfile.ZipFile(out, "w", allowZip64=True) as z:
        for name, path in _files(root, skipped):
            # a name the restore would refuse (a colon, a backslash, a .git,
            # two names one in capitals, bytes that are no text) is left out
            # and named now, not found out on the day the backup is needed
            # a Mac writes a name with its accents apart (NFD) and keeps the
            # two forms as one file, like two names one in capitals
            key = unicodedata.normalize("NFC", name).casefold()
            if not _writable_name(name) or key in seen:
                skipped.append(name)
                continue
            # the file is read whole into a spool before the member is
            # opened: a member the zip has begun is committed even when the
            # read fails halfway, and a member the manifest does not list
            # makes the whole backup unrestorable
            try:
                stamp = _stamp(os.stat(path).st_mtime)
                with open(path, "rb") as f, \
                        tempfile.SpooledTemporaryFile(max_size=8 * _CHUNK) as spool:
                    digest, size = _hash_copy(f, spool)
                    spool.seek(0)
                    info = zipfile.ZipInfo(name, stamp)
                    info.compress_type = (zipfile.ZIP_STORED if name.lower().endswith(STORED)
                                          else zipfile.ZIP_DEFLATED)
                    with z.open(info, "w", force_zip64=True) as target:
                        shutil.copyfileobj(spool, target, _CHUNK)
            except OSError:
                skipped.append(name)
                continue
            seen.add(key)
            files[name] = {"sha256": digest, "size": size}
        found, _ = counts(root)
        manifest = {"app": "plainbook", "format": FORMAT, "version": __version__,
                    "made": now.replace(microsecond=0).isoformat(),
                    "counts": found, "files": files, "skipped": skipped}
        z.writestr(MANIFEST, json.dumps(manifest, indent=1, sort_keys=True),
                   zipfile.ZIP_DEFLATED)
    return manifest


def file_name(now=None):
    return f"Plainbook-{(now or datetime.now()):%Y-%m-%d}{SUFFIX}"


# --- restoring --------------------------------------------------------------

def stage_dir(root, token):
    if not _TOKEN.match(token or ""):
        raise BackupError("no such restore")
    return os.path.join(root, STAGE, token)


def new_stage(root):
    """A fresh folder for one file being restored: (token, path)."""
    sweep(root)
    token = secrets.token_hex(8)
    path = stage_dir(root, token)
    os.makedirs(path)
    return token, path


def sweep(root, now=None):
    """Takes away the restores started and never taken, after a day. They
    are copies of a backup file the owner still has, never records."""
    base = os.path.join(root, STAGE)
    now = now or time.time()
    for name in os.listdir(base) if os.path.isdir(base) else []:
        path = os.path.join(base, name)
        try:
            old = now - os.stat(path).st_mtime > KEEP_STAGED
        except OSError:
            continue
        if old and _TOKEN.match(name):
            shutil.rmtree(path, ignore_errors=True)


def refuse(root, token, reason):
    """Leaves only the reason in the restore folder of a file that was not
    taken, for the page that says so."""
    base = stage_dir(root, token)
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(base, exist_ok=True)
    with open(os.path.join(base, ERROR), "w", encoding="utf-8") as f:
        f.write(reason)


def refused(root, token):
    """Why the file of a restore was not taken, or None."""
    try:
        with open(os.path.join(stage_dir(root, token), ERROR), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def discard(root, token):
    """Takes away a restore that was not taken. It holds copies from a file
    the owner still has, never records, and a cancel that comes while the
    file is still arriving must not fail on what is going away under it."""
    path = stage_dir(root, token)
    with _LOCK:
        shutil.rmtree(path, ignore_errors=True)


def _writable_name(name):
    """A name that can go into the zip and come back out of it."""
    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return _safe_name(name)


def _safe_name(name):
    """A name inside the backup that may be written: under journal/ or under
    one entry of trash/, with no way out of the folder it lands in."""
    if not name or "\\" in name or ":" in name or name.startswith("/"):
        return False
    parts = name.split("/")
    # a .git a backup never carries could only come from a made-up file, and
    # its config runs commands the moment git is used in the folder
    if any(p in ("", ".", "..") or p.casefold() == ".git" for p in parts):
        return False
    if parts[0] == JOURNAL:
        return len(parts) >= 2
    if parts[0] == TRASH:
        return (len(parts) >= 2 and bool(store.safe_dir_name(parts[1]))
                and store.trashed(parts[1]) is not None)
    return False


def _version(text):
    return tuple(int(x) for x in re.findall(r"\d+", str(text))[:3])


def unpack(root, token, source):
    """Checks the backup file at `source` and unpacks it into the restore
    folder of `token`. Raises BackupError with the reason when the file is
    not a whole backup; nothing of the journal is touched either way."""
    try:
        return _unpack(root, token, source)
    except BackupError:
        raise
    except Exception as e:
        # an encrypted part, a packing zipfile does not know: the zip module
        # says so with errors of its own, and the owner should get the reason
        raise BackupError(f"this file cannot be restored ({e})")


def _unpack(root, token, source):
    base = stage_dir(root, token)
    try:
        z = zipfile.ZipFile(source)
    except (zipfile.BadZipFile, OSError):
        raise BackupError("this file is not a Plainbook backup")
    with z:
        try:
            manifest = json.loads(z.read(MANIFEST).decode("utf-8"))
        except (KeyError, ValueError, UnicodeDecodeError, zipfile.BadZipFile):
            raise BackupError("this file is not a Plainbook backup: it has no manifest")
        if not isinstance(manifest, dict) or manifest.get("app") != "plainbook":
            raise BackupError("this file is not a Plainbook backup")
        if not isinstance(manifest.get("format"), int) or manifest["format"] > FORMAT:
            raise BackupError(f"this backup was made by a newer Plainbook "
                              f"({manifest.get('version', '?')}); update this one first")
        files = manifest.get("files")
        if not isinstance(files, dict):
            raise BackupError("the manifest of this backup does not read")
        listed = [i for i in z.infolist() if i.filename != MANIFEST and not i.is_dir()]
        members = {i.filename: i for i in listed}
        if len(members) != len(listed) or set(members) != set(files):
            raise BackupError("this backup is incomplete or was changed after it was made")
        # Windows and macOS see A.md and a.md as one file: the second would
        # write over the first, and each would still pass its own check
        # an accent written apart (NFD) is the same name on a Mac as one
        # written whole, which is how _make compares them
        if len({unicodedata.normalize("NFC", n).casefold() for n in members}) != len(members):
            raise BackupError("this backup holds two files whose names differ only "
                              "in capitals or accents, which this computer cannot keep apart")
        for name, info in members.items():
            entry = files[name]
            if (not _safe_name(name) or not isinstance(entry, dict)
                    or not isinstance(entry.get("size"), int)
                    or info.file_size != entry["size"]):
                raise BackupError(f"this backup holds a file it may not: {name[:80]}")
            # a link inside a zip is a file whose text is where it points
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise BackupError(f"this backup holds a link: {name[:80]}")
        need = sum(i.file_size for i in members.values())
        if shutil.disk_usage(root).free < need + 64 * _CHUNK:
            raise BackupError(f"not enough free space to restore it "
                              f"({need // _CHUNK + 1} MB needed)")
        for name, info in members.items():
            target = os.path.join(base, *name.split("/"))
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with z.open(info) as part, open(target, "wb") as out:
                    digest, _ = _hash_copy(part, out, info.file_size)
                    # the journal is fsynced on every save (store._write); a
                    # restored one should survive a power cut the same way
                    out.flush()
                    os.fsync(out.fileno())
                when = time.mktime(info.date_time + (0, 0, -1))
                os.utime(target, (when, when))
            except (zipfile.BadZipFile, OSError, EOFError, OverflowError, ValueError) as e:
                raise BackupError(f"this backup is damaged or does not fit this disk ({e})")
            if digest != files[name].get("sha256"):
                raise BackupError("this backup is damaged: a file does not match "
                                  "its manifest")
    for name in (JOURNAL, TRASH):
        os.makedirs(os.path.join(base, name), exist_ok=True)
    keep = {k: manifest.get(k) for k in ("version", "made", "counts", "skipped")}
    with open(os.path.join(base, MANIFEST), "w", encoding="utf-8") as f:
        json.dump(keep, f)
    return keep


def staged(root, token):
    """What a restore that is waiting holds: (manifest, counts, problems), or
    None when there is no such restore."""
    base = stage_dir(root, token)
    try:
        with open(os.path.join(base, MANIFEST), encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError):
        return None
    found, problems = counts(base, os.path.join(base, TRASH))
    return manifest, found, problems


def newer(manifest):
    """True when the backup was made by a Plainbook newer than this one."""
    return _version(manifest.get("version", "")) > _version(__version__)


def _claim_aside(root):
    """A new folder in the trash for the journal a swap puts aside, made at
    once, so that no other swap can be given the same name."""
    when = datetime.now().replace(microsecond=0)
    while True:
        path = os.path.join(root, store.TRASH, f"journal-{when:%Y%m%d-%H%M%S}{ASIDE}")
        try:
            os.mkdir(path)
            return path
        except FileExistsError:
            when += timedelta(seconds=1)


def _drop_empty(path):
    """Takes away a folder a swap emptied, and only if it is empty: rmdir
    refuses a folder with anything in it, which is the point."""
    for folder in (os.path.join(path, TRASH), path):
        try:
            os.rmdir(folder)
        except OSError:
            pass


def _swap(root, source):
    """Moves the journal and the trash records of `source` (a folder holding
    `journal/` and `trash/`) into root, and the ones of root into a new folder
    of the trash. Returns that folder's name. Every move is a rename on one
    disk and never lands on anything; if one fails, the ones made are taken
    back, and what cannot be taken back is named, never deleted."""
    trash = os.path.join(root, store.TRASH)
    os.makedirs(trash, exist_ok=True)
    aside = _claim_aside(root)
    done = []

    def move(a, b):
        if os.path.lexists(b):
            raise FileExistsError(f"{b} is there already")
        os.makedirs(os.path.dirname(b), exist_ok=True)
        os.rename(a, b)
        done.append((a, b))

    # read before the first move: a failure past that point must find the
    # journal still standing in one of its two places
    leaving = [name for name, _, _, _ in store.trash_list(root)]
    try:
        journal = os.path.join(root, store.JOURNAL)
        if os.path.isdir(journal):
            move(journal, os.path.join(aside, JOURNAL))
        for name in leaving:
            move(os.path.join(trash, name), os.path.join(aside, TRASH, name))
        move(os.path.join(source, JOURNAL), journal)
        incoming = os.path.join(source, TRASH)
        for name in sorted(os.listdir(incoming)) if os.path.isdir(incoming) else []:
            move(os.path.join(incoming, name), os.path.join(trash, name))
    except Exception as e:
        stuck = []
        for a, b in reversed(done):
            try:
                if os.path.lexists(a):
                    raise FileExistsError(a)
                os.rename(b, a)
            except OSError:
                stuck.append(b)
        _drop_empty(aside)
        if stuck:
            raise BackupError(
                f"the journal could not be moved ({getattr(e, 'strerror', None) or e}) and not "
                f"everything went back: nothing is deleted, and what stayed "
                f"behind is in .trash/{os.path.basename(aside)}")
        raise BackupError(f"the journal could not be moved ({getattr(e, 'strerror', None) or e}); "
                          f"it stays as it was")
    store.make_layout(root)
    return os.path.basename(aside)


def restore(root, token):
    """Takes the waiting restore of `token`. Returns the name in the trash of
    the journal it replaced."""
    base = stage_dir(root, token)
    with _LOCK:
        if not (os.path.isfile(os.path.join(base, MANIFEST))
                and os.path.isdir(os.path.join(base, JOURNAL))):
            raise BackupError("no such restore: it was taken or cancelled already")
        aside = _swap(root, base)
        _TAKEN[token] = time.time()
        # what is left are the manifest and empty folders: the swap moved
        # the journal out, and a rollback never puts the owner's files here
        shutil.rmtree(base, ignore_errors=True)
    return aside


def taken(token):
    """True when this restore was taken already: a second press of the
    button lands on the journal instead of an error."""
    return token in _TAKEN


def replaced(root):
    """[(name in the trash, when it was replaced)] of the journals a restore
    has put aside, newest first."""
    trash = os.path.join(root, store.TRASH)
    out = []
    for name in os.listdir(trash) if os.path.isdir(trash) else []:
        m = re.match(r"^journal-(\d{8}-\d{6})" + re.escape(ASIDE) + "$", name)
        if m and os.path.isdir(os.path.join(trash, name, JOURNAL)):
            out.append((name, datetime.strptime(m.group(1), "%Y%m%d-%H%M%S")))
    out.sort(key=lambda x: x[1], reverse=True)
    return out


def put_back(root, name):
    """Brings back a journal a restore replaced; the one standing now goes
    aside in its turn. Returns the name it went under."""
    with _LOCK:
        if not any(n == name for n, _ in replaced(root)):
            raise BackupError("no such journal in the trash: it was put back already")
        source = os.path.join(root, store.TRASH, name)
        aside = _swap(root, source)
        _drop_empty(source)
    return aside
