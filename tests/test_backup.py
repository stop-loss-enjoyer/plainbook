#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The backup: the whole journal into one file and back, byte for byte; a
file that is not whole, or tries to write outside the journal, is refused
with the journal untouched; the journal a restore replaces goes to the trash
and comes back from there. Then the same through the server: the card, the
download, the form, a double click on the file, and Lite."""
import filecmp
import hashlib
import importlib
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime

TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TESTS))
sys.path.insert(0, TESTS)

from plainbook import backup, store
from plainbook.model import Account, Trade


def journal(root, trades=3):
    store.make_layout(root)
    store.save_account(root, Account(id="broker", name="Broker", start_balance=10000))
    for i in range(trades):
        t = Trade(id=f"2026-03-0{i + 1}-eurusd", pair="EURUSD", account="broker",
                  opened=datetime(2026, 3, i + 1, 10), closed=datetime(2026, 3, i + 1, 15),
                  direction="long", style="swing", risk=1.0, pnl=50.0 * (i + 1), result="Win")
        store.save_trade(root, t)
        shots = store.shots_dir(root, t.id)
        os.makedirs(shots, exist_ok=True)
        with open(os.path.join(shots, "idea-01.png"), "wb") as f:
            f.write(b"\x89PNG picture " + bytes([i]) * 2000)
    with open(store.settings_file(root), "w", encoding="utf-8", newline="\n") as f:
        f.write("---\nclock: Europe/Prague\n---\n\nBy hand, kept.\n")


def tree(root):
    """{relative path: sha256} of every file under root."""
    out = {}
    for here, _, files in os.walk(root):
        for name in files:
            path = os.path.join(here, name)
            with open(path, "rb") as f:
                out[os.path.relpath(path, root)] = hashlib.sha256(f.read()).hexdigest()
    return out


def made(root):
    out = io.BytesIO()
    backup.make(root, out)
    return out.getvalue()


def rewrite(data, change):
    """The backup with its zip rebuilt by `change(entries)`, where entries is
    a list of [name, bytes] the change edits in place."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        entries = [[i.filename, z.read(i)] for i in z.infolist()]
    change(entries)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, body in entries:
            z.writestr(name, body)
    return out.getvalue()


class BackupFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.a = os.path.join(self.tmp.name, "a")
        self.b = os.path.join(self.tmp.name, "b")
        journal(self.a)
        journal(self.b, trades=1)
        self.data = made(self.a)

    def tearDown(self):
        self.tmp.cleanup()

    def take(self, data, root=None):
        root = root or self.b
        path = os.path.join(self.tmp.name, "file" + backup.SUFFIX)
        with open(path, "wb") as f:
            f.write(data)
        token, _ = backup.new_stage(root)
        backup.unpack(root, token, path)
        return token

    def test_round_trip_is_byte_for_byte(self):
        before = tree(os.path.join(self.b, "journal"))
        aside = backup.restore(self.b, self.take(self.data))
        self.assertEqual(tree(os.path.join(self.a, "journal")),
                         tree(os.path.join(self.b, "journal")))
        # the journal it replaced is in the trash, whole
        self.assertEqual(before, tree(os.path.join(self.b, ".trash", aside, "journal")))
        self.assertFalse(os.listdir(os.path.join(self.b, backup.STAGE)))

    def test_the_pictures_of_a_card_go_with_a_backup_and_come_back(self):
        from test_card_pictures import png
        store.save_card_picture(self.a, "mine.png", png(4, 4))
        store.save_card_picture(self.a, "other.png", png(5, 5))
        self.assertEqual(store.card_pictures(self.b), [])
        backup.restore(self.b, self.take(made(self.a)))
        self.assertEqual(store.card_pictures(self.b), ["mine.png", "other.png"])
        with open(store.card_picture_path(self.b, "mine.png"), "rb") as f:
            self.assertEqual(f.read(), png(4, 4))
        self.assertEqual(tree(os.path.join(self.a, "journal")),
                         tree(os.path.join(self.b, "journal")))

    def test_a_removed_picture_of_a_card_stays_out_of_a_backup(self):
        from test_card_pictures import png
        store.save_card_picture(self.a, "kept.png", png())
        store.save_card_picture(self.a, "gone.png", png(3, 3))
        store.trash_card_picture(self.a, "gone.png")
        with zipfile.ZipFile(io.BytesIO(made(self.a))) as z:
            names = z.namelist()
        self.assertIn("journal/card-pictures/kept.png", names)
        self.assertEqual([n for n in names if "gone" in n], [])

    def test_the_counts_are_written_and_read(self):
        manifest, found, problems = backup.staged(self.b, self.take(self.data))
        self.assertEqual(found["trades"], 3)
        self.assertEqual(found["screenshots"], 3)
        self.assertEqual(manifest["counts"]["trades"], 3)
        self.assertEqual(problems, [])

    def test_pictures_are_stored_and_text_is_deflated(self):
        with zipfile.ZipFile(io.BytesIO(self.data)) as z:
            kinds = {i.filename.rsplit(".", 1)[-1]: i.compress_type for i in z.infolist()}
        self.assertEqual(kinds["png"], zipfile.ZIP_STORED)
        self.assertEqual(kinds["md"], zipfile.ZIP_DEFLATED)

    def test_the_trash_goes_with_it_and_comes_back(self):
        store.delete_trade(self.a, "2026-03-01-eurusd")
        old = [x[0] for x in store.trash_list(self.b)]
        store.delete_trade(self.b, "2026-03-01-eurusd")
        old = [x[0] for x in store.trash_list(self.b)]
        aside = backup.restore(self.b, self.take(made(self.a)))
        self.assertEqual([x[0] for x in store.trash_list(self.b)],
                         [x[0] for x in store.trash_list(self.a)])
        self.assertEqual(sorted(os.listdir(os.path.join(self.b, ".trash", aside, "trash"))),
                         sorted(old))
        # the journal put aside is not a record of the trash list
        self.assertNotIn(aside, [x[0] for x in store.trash_list(self.b)])

    def test_put_back_swaps_again(self):
        before = tree(os.path.join(self.b, "journal"))
        aside = backup.restore(self.b, self.take(self.data))
        self.assertEqual([n for n, _ in backup.replaced(self.b)], [aside])
        again = backup.put_back(self.b, aside)
        self.assertEqual(before, tree(os.path.join(self.b, "journal")))
        self.assertEqual([n for n, _ in backup.replaced(self.b)], [again])
        self.assertEqual(tree(os.path.join(self.a, "journal")),
                         tree(os.path.join(self.b, ".trash", again, "journal")))

    def test_put_back_takes_only_a_replaced_journal(self):
        with self.assertRaises(backup.BackupError):
            backup.put_back(self.b, "../a")

    def refused(self, data):
        before = tree(self.b)
        with self.assertRaises(backup.BackupError) as e:
            self.take(data)
        self.assertEqual(before, {k: v for k, v in tree(self.b).items()
                                  if not k.startswith(backup.STAGE)})
        return str(e.exception)

    def test_not_a_zip(self):
        self.assertIn("not a Plainbook backup", self.refused(b"hello"))

    def test_a_zip_with_no_manifest(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("journal/settings.md", "x")
        self.assertIn("no manifest", self.refused(out.getvalue()))

    def test_a_changed_file(self):
        def change(entries):
            for e in entries:
                if e[0].endswith(".png"):
                    e[1] = e[1][:-1] + b"!"
                    return
        self.assertIn("damaged", self.refused(rewrite(self.data, change)))

    def test_a_missing_file(self):
        def change(entries):
            entries[:] = [e for e in entries if not e[0].endswith(".png")]
        self.assertIn("incomplete", self.refused(rewrite(self.data, change)))

    def test_a_name_out_of_the_journal(self):
        for bad in ("../evil.md", "journal/../../evil.md", "/etc/evil",
                    "elsewhere/x.md", "journal\\..\\evil.md", "trash/../x"):
            def change(entries, bad=bad):
                manifest = json.loads(entries[-1][1])
                manifest["files"][bad] = {"sha256": "0" * 64, "size": 1}
                entries[-1][1] = json.dumps(manifest).encode()
                entries.insert(0, [bad, b"x"])
            said = self.refused(rewrite(self.data, change))
            # zipfile on Windows reads a backslash in a name as a slash, so
            # there the name no longer matches its manifest: refused all the same
            self.assertTrue("may not" in said or "changed after" in said, (bad, said))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "evil.md")))

    def test_a_newer_format(self):
        def change(entries):
            manifest = json.loads(entries[-1][1])
            manifest["format"] = backup.FORMAT + 1
            entries[-1][1] = json.dumps(manifest).encode()
        self.assertIn("newer Plainbook", self.refused(rewrite(self.data, change)))

    def test_a_record_that_does_not_read_is_named_and_restored(self):
        with open(os.path.join(store.trade_dir(self.a, "2026-03-02-eurusd"),
                               "trade.md"), "w") as f:
            f.write("---\nopened: someday\n---\n")
        manifest, found, problems = backup.staged(self.b, self.take(made(self.a)))
        self.assertTrue(problems)

    def test_two_restores_at_once_lose_nothing(self):
        before = tree(os.path.join(self.b, "journal"))
        tokens = [self.take(self.data) for _ in range(4)]
        out = []

        def go(token):
            try:
                out.append(backup.restore(self.b, token))
            except backup.BackupError:
                out.append(None)
        threads = [threading.Thread(target=go, args=(t,)) for t in tokens]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(tree(os.path.join(self.a, "journal")),
                         tree(os.path.join(self.b, "journal")))
        # every swap put a whole journal aside, the first one the owner's
        asides = [n for n, _ in backup.replaced(self.b)]
        self.assertEqual(len(asides), len([x for x in out if x]))
        self.assertIn(before, [tree(os.path.join(self.b, ".trash", n, "journal"))
                               for n in asides])

    def test_the_same_restore_twice(self):
        token = self.take(self.data)
        backup.restore(self.b, token)
        with self.assertRaises(backup.BackupError):
            backup.restore(self.b, token)
        self.assertTrue(backup.taken(token))
        self.assertEqual(len(backup.replaced(self.b)), 1)

    def test_a_file_from_1970_does_not_stop_the_backup(self):
        path = os.path.join(store.trade_dir(self.a, "2026-03-01-eurusd"), "trade.md")
        os.utime(path, (0, 0))
        backup.restore(self.b, self.take(made(self.a)))
        self.assertEqual(tree(os.path.join(self.a, "journal")),
                         tree(os.path.join(self.b, "journal")))

    def test_a_link_is_named_and_left_out(self):
        try:
            os.symlink(self.tmp.name, os.path.join(self.a, "journal", "elsewhere"))
        except OSError:
            self.skipTest("no links on this system without rights")
        manifest = json.loads(zipfile.ZipFile(io.BytesIO(made(self.a))).read("manifest.json"))
        self.assertEqual(manifest["skipped"], ["journal/elsewhere"])

    def test_made_up_names_are_refused(self):
        for bad in ("journal/.git/config", "journal/notes/.GIT/x",
                    "trash/whatever/x.md",
                    "trash/journal-20991231-000000.before-restore/journal/a.md"):
            def change(entries, bad=bad):
                manifest = json.loads(entries[-1][1])
                manifest["files"][bad] = {"sha256": "0" * 64, "size": 1}
                entries[-1][1] = json.dumps(manifest).encode()
                entries.insert(0, [bad, b"x"])
            self.assertIn("may not", self.refused(rewrite(self.data, change)), bad)

    def test_names_that_differ_in_capitals_are_refused(self):
        def change(entries):
            manifest = json.loads(entries[-1][1])
            for name in ("journal/notes/A.md", "journal/notes/a.md"):
                manifest["files"][name] = {"sha256": hashlib.sha256(b"x").hexdigest(),
                                           "size": 1}
                entries.insert(0, [name, b"x"])
            entries[-1][1] = json.dumps(manifest).encode()
        self.assertIn("capitals", self.refused(rewrite(self.data, change)))

    def test_a_trash_name_that_is_no_date_is_refused(self):
        bad = "trash/card-x-99999999-999999.md"
        def change(entries):
            manifest = json.loads(entries[-1][1])
            manifest["files"][bad] = {"sha256": hashlib.sha256(b"x").hexdigest(), "size": 1}
            entries[-1][1] = json.dumps(manifest).encode()
            entries.insert(0, [bad, b"x"])
        self.assertIn("may not", self.refused(rewrite(self.data, change)))

    def test_a_trash_name_that_is_no_date_does_not_stop_a_restore(self):
        # put in by hand: the trash leaves it unlisted, and a restore must
        # still put the journal in place and keep the old one to put back
        os.makedirs(os.path.join(self.b, ".trash"), exist_ok=True)
        with open(os.path.join(self.b, ".trash", "card-x-99999999-999999.md"), "w") as f:
            f.write("x")
        self.assertEqual(store.trash_list(self.b), [])
        before = tree(os.path.join(self.b, "journal"))
        aside = backup.restore(self.b, self.take(self.data))
        self.assertEqual(tree(os.path.join(self.a, "journal")),
                         tree(os.path.join(self.b, "journal")))
        backup.put_back(self.b, aside)
        self.assertEqual(before, tree(os.path.join(self.b, "journal")))

    def test_a_failed_swap_of_any_kind_goes_back(self):
        before = tree(os.path.join(self.b, "journal"))
        token = self.take(self.data)
        real = os.rename
        calls = []
        def rename(a, b):
            calls.append(a)
            if len(calls) == 2:
                raise ValueError("not a file system error")
            return real(a, b)
        backup.os.rename = rename
        try:
            with self.assertRaises(backup.BackupError):
                backup.restore(self.b, token)
        finally:
            backup.os.rename = real
        self.assertEqual(before, tree(os.path.join(self.b, "journal")))

    def test_the_trash_of_a_backup_is_counted_before_it_is_taken(self):
        store.delete_trade(self.a, "2026-03-01-eurusd")
        _, found, _ = backup.staged(self.b, self.take(made(self.a)))
        self.assertEqual(found["trash"], 1)
        self.assertEqual(found["trades"], 2)

    def test_a_name_another_system_cannot_keep_is_left_out_and_named(self):
        for bad in ("journal/notes/note 12:30.txt", "journal/notes/a\\b.md",
                    "journal/notes/caf\udce9.txt", "journal/.git"):
            self.assertFalse(backup._writable_name(bad), bad)
        self.assertTrue(backup._writable_name("journal/notes/café.txt"))
        # on the disk, as far as this one lets such names be made: Windows
        # takes a colon for a stream of another file, and macOS keeps one
        # file for two names that differ in capitals
        notes = os.path.join(self.a, "journal", "notes")
        os.makedirs(notes, exist_ok=True)
        for name in ("note 12:30.txt", "Chart.png", "chart.png"):
            with open(os.path.join(notes, name), "wb") as f:
                f.write(b"x")
        there = os.listdir(notes)
        data = made(self.a)
        manifest = json.loads(zipfile.ZipFile(io.BytesIO(data)).read("manifest.json"))
        if "note 12:30.txt" in there:
            self.assertIn("journal/notes/note 12:30.txt", manifest["skipped"])
        if {"Chart.png", "chart.png"} <= set(there):
            self.assertEqual(sum(1 for n in manifest["skipped"]
                                 if n.lower() == "journal/notes/chart.png"), 1)
        backup.restore(self.b, self.take(data))         # and it restores

    def test_any_failure_of_the_zip_is_a_reason(self):
        real = backup._unpack
        def broken(*_):
            raise RuntimeError("File is encrypted, password required")
        backup._unpack = broken
        try:
            self.assertIn("encrypted", self.refused(self.data))
        finally:
            backup._unpack = real

    def test_an_old_restore_is_swept(self):
        token, path = backup.new_stage(self.b)
        os.utime(path, (0, 0))
        backup.sweep(self.b)
        self.assertFalse(os.path.exists(path))

    def test_a_bad_token(self):
        for token in ("../x", "", "ABC", "0" * 15):
            with self.assertRaises(backup.BackupError):
                backup.stage_dir(self.b, token)


class BackupServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = os.path.join(cls.tmp.name, "root")
        journal(cls.root, trades=2)
        os.environ["PLAINBOOK_ROOT"] = cls.root
        import plainbook.server
        cls.S = importlib.reload(plainbook.server)
        cls.server = cls.S.Server(("127.0.0.1", 0), cls.S.Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()
        os.environ.pop("PLAINBOOK_ROOT", None)

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def fetch(self, path, data=None, headers=None):
        req = urllib.request.Request(self.url(path), data=data, headers=headers or {})
        with urllib.request.urlopen(req) as r:
            return r.read(), r.geturl(), r.headers

    def upload(self, data, name="Plainbook" + backup.SUFFIX):
        mark = "----plainbook-test"
        body = (f"--{mark}\r\nContent-Disposition: form-data; name=\"backup\"; "
                f"filename=\"{name}\"\r\nContent-Type: application/octet-stream\r\n\r\n"
                ).encode() + data + f"\r\n--{mark}--\r\n".encode()
        return self.fetch("/backup/upload", body,
                          {"Content-Type": f"multipart/form-data; boundary={mark}"})

    def test_the_card_is_on_accounts(self):
        page = self.fetch("/accounts")[0].decode()
        self.assertIn('id="backup"', page)
        self.assertIn('href="/backup.plainbook"', page)
        self.assertIn('enctype="multipart/form-data"', page)

    def test_download_upload_restore(self):
        data, _, headers = self.fetch("/backup" + backup.SUFFIX)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertIn(backup.SUFFIX, headers["Content-Disposition"])
        before = tree(os.path.join(self.root, "journal"))
        store.delete_trade(self.root, "2026-03-01-eurusd")
        page, where, _ = self.upload(data)
        self.assertIn("/restore/", where)
        page = page.decode()
        self.assertIn("Restore this journal", page)
        token = where.rsplit("/", 1)[1]
        self.fetch(f"/restore/{token}", b"")
        self.assertEqual(before, tree(os.path.join(self.root, "journal")))
        self.assertEqual(len(self.S.journal().trades), 2)
        self.assertIn("Put back", self.fetch("/accounts")[0].decode())

    def test_a_bad_file_says_why_and_changes_nothing(self):
        before = tree(os.path.join(self.root, "journal"))
        page, where, _ = self.upload(b"not a backup at all")
        self.assertIn("cannot be restored", page.decode())
        self.assertIn("not a Plainbook backup", page.decode())
        self.assertEqual(before, tree(os.path.join(self.root, "journal")))
        token = where.rsplit("/", 1)[1]
        page, where, _ = self.fetch(f"/restore/{token}", b"")     # nothing to take
        self.assertIn("/accounts", where)
        self.assertIn('class="notice', page.decode())
        self.assertEqual(before, tree(os.path.join(self.root, "journal")))
        self.fetch(f"/restore/{token}/cancel", b"")
        self.assertFalse(os.path.exists(backup.stage_dir(self.root, token)))

    def test_a_second_press_lands_on_the_journal(self):
        data = self.fetch("/backup" + backup.SUFFIX)[0]
        token = self.upload(data)[1].rsplit("/", 1)[1]
        self.fetch(f"/restore/{token}", b"")
        _, where, _ = self.fetch(f"/restore/{token}", b"")
        self.assertEqual(urllib.parse.urlsplit(where).path, "/")

    def test_a_made_up_manifest_still_draws_the_page(self):
        data = self.fetch("/backup" + backup.SUFFIX)[0]

        def change(entries):
            manifest = json.loads(entries[-1][1])
            manifest["made"], manifest["counts"], manifest["skipped"] = 5, [], "x"
            entries[-1][1] = json.dumps(manifest).encode()
        page = self.upload(rewrite(data, change))[0].decode()
        self.assertIn("Restore this journal", page)

    def test_cancel(self):
        data = self.fetch("/backup" + backup.SUFFIX)[0]
        token = self.upload(data)[1].rsplit("/", 1)[1]
        _, where, _ = self.fetch(f"/restore/{token}/cancel", b"")
        self.assertIn("/accounts", where)
        self.assertFalse(os.path.exists(backup.stage_dir(self.root, token)))

    def test_a_double_click_hands_the_file_over(self):
        data = self.fetch("/backup" + backup.SUFFIX)[0]
        path = os.path.join(self.tmp.name, "given" + backup.SUFFIX)
        with open(path, "wb") as f:
            f.write(data)
        opened = []
        real = self.S.open_journal
        self.S.open_journal = opened.append
        try:
            self.S.hand_over(f"http://localhost:{self.port}", path)
        finally:
            self.S.open_journal = real
        self.assertEqual(len(opened), 1)
        self.assertIn("/restore/", opened[0])
        page = self.fetch(urllib.parse.urlsplit(opened[0]).path)[0].decode()
        self.assertIn("Restore this journal", page)
        self.assertTrue(os.path.exists(path))         # the owner's file stays

    def test_another_site_cannot_start_a_download_or_an_upload(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.fetch("/backup" + backup.SUFFIX, headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(e.exception.code, 403)
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.fetch("/backup/upload", b"x", {"Origin": "http://evil.example"})
        self.assertEqual(e.exception.code, 403)

    def test_an_unknown_restore(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.fetch("/restore/0123456789abcdef")
        self.assertEqual(e.exception.code, 404)
        with self.assertRaises(urllib.error.HTTPError):
            self.fetch("/restore/..%2F..%2Fetc")

    def test_lite_shows_the_card_and_restores(self):
        settings = store.settings_file(self.root)
        with open(settings, encoding="utf-8") as f:
            kept = f.read()
        try:
            with open(settings, "w", encoding="utf-8", newline="\n") as f:
                f.write("---\nedition: lite\n---\n")
            self.S.drop_cache()
            self.assertIn('id="backup"', self.fetch("/accounts")[0].decode())
        finally:
            with open(settings, "w", encoding="utf-8", newline="\n") as f:
                f.write(kept)
            self.S.drop_cache()


class Multipart(unittest.TestCase):
    def test_the_file_comes_out_whole(self):
        with tempfile.TemporaryDirectory() as tmp:
            body = os.path.join(tmp, "body")
            payload = bytes(range(256)) * 50 + b"\r\n--x"
            with open(body, "wb") as f:
                f.write(b"--B\r\nContent-Disposition: form-data; name=\"backup\"; "
                        b"filename=\"a.plainbook\"\r\n\r\n" + payload + b"\r\n--B--\r\n")
            out = os.path.join(tmp, "out")
            importlib.import_module("plainbook.server").multipart_file(
                body, "multipart/form-data; boundary=B", out)
            with open(out, "rb") as f:
                self.assertEqual(f.read(), payload)


if __name__ == "__main__":
    unittest.main()
