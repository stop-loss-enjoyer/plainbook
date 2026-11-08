#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The backgrounds of a trade card: the pictures of the owner's, kept in their
data (`journal/card-pictures/`), and the card page that chooses among them.

A picture is theirs and leaves with every card made on it, so what is kept is
checked by its bytes, and a name that arrives in an address or a form is only
ever looked for in the listing, never made into a path."""
import importlib
import os
import re
import shutil
import struct
import subprocess
import sys
import socket
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zlib
from datetime import datetime
from unittest import mock

TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TESTS))

from plainbook import balances, store
from plainbook.model import Account, RecordError, Trade


def chunk(kind, data):
    body = kind + data
    return (struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body)))


def png(width=2, height=2, pad=0):
    """A real small PNG, written by hand from the standard library; `pad`
    bytes of a text chunk make it as big as a test needs."""
    rows = b"".join(b"\x00" + bytes([40, 120, 200]) * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows))
            + (chunk(b"tEXt", b"k\x00" + b"x" * pad) if pad else b"")
            + chunk(b"IEND", b""))


def png_of_size(total):
    """A PNG of exactly `total` bytes."""
    return png(pad=total - len(png()) - 12 - 2)


def broken_png():
    """The signature and the end of a PNG with nothing between them that a
    browser can open: it passes what the server checks and not what a page
    does."""
    return (b"\x89PNG\r\n\x1a\n" + b"this is no picture, only the shape of one"
            + chunk(b"IEND", b""))


JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 40 + b"\xff\xd9"
GIF = b"GIF89a" + b"\x00" * 40 + b";"
_webp_body = b"WEBPVP8 " + b"\x00" * 40
WEBP = b"RIFF" + struct.pack("<I", len(_webp_body)) + _webp_body
# the picture a phone writes: a main image with a thumbnail of its own inside
# (a JPEG itself, ending in a marker), and the trailers phones add after it
_THUMB = b"\xff\xd8\xff\xdb" + b"t" * 20 + b"\xff\xd9"
_MAIN = b"\xff\xd8\xff\xe1" + _THUMB + b"m" * 200 + b"\xff\xd9"
PIXEL_MOTION = _MAIN + b"\x00\x00\x00\x18ftypmp42" + b"v" * 60
SAMSUNG = (_MAIN + b"x" * 30 + b"SEFH" + b"d" * 24 + struct.pack("<I", 28) + b"SEFT")
SAMSUNG_MOTION = _MAIN + b"\x00\x00\x00\x18ftypmp42" + b"v" * 60 + b"SEFH" + b"d" * 24 + b"SEFT"
# "my chart" in Russian, written as escapes because the repository keeps
# Cyrillic out of its files (check_public.py); the name a space turns to a hyphen
MY_CHART = "\u041c\u043e\u0439 \u0433\u0440\u0430\u0444\u0438\u043a"
MY_CHART_KEPT = MY_CHART.replace(" ", "-")
ANOTHER = "\u0415\u0449\u0451 \u043e\u0434\u0438\u043d"       # "one more"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
HTML_AS_PNG = b"<html><script>alert(1)</script></html>"


class CardPictureStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_picture_is_known_by_its_bytes_and_not_by_its_name(self):
        for raw, kept in ((png(), "a.png"), (JPEG, "a.jpg"), (GIF, "a.gif"),
                          (WEBP, "a.webp")):
            self.assertEqual(store.save_card_picture(self.root, "a.png", raw), kept)
            os.remove(os.path.join(store.card_pictures_dir(self.root), kept))
        for name, raw in (("a.png", SVG), ("a.svg", SVG), ("a.png", HTML_AS_PNG),
                          ("a.png", b""), ("a.jpg", b"RIFF1234WAVEfmt "),
                          ("a.png", b"\x89PNG")):
            with self.assertRaises(RecordError, msg=(name, raw[:12])):
                store.save_card_picture(self.root, name, raw)
        self.assertEqual(store.card_pictures(self.root), [])

    def test_a_picture_that_stops_short_or_is_cut_is_refused(self):
        for name, raw in (("a.png", png()[:-12]), ("a.png", png()[:-1]),
                          ("a.jpg", JPEG[:-2]), ("a.gif", GIF[:-1]),
                          ("a.webp", WEBP[:-1]), ("a.webp", WEBP + b"\x00\x01"),
                          ("a.png", png()[:40])):
            with self.assertRaises(RecordError, msg=(name, len(raw))):
                store.save_card_picture(self.root, name, raw)
        self.assertEqual(store.card_pictures(self.root), [])
        # what a picture may be padded with after its end is not held against it
        self.assertEqual(store.save_card_picture(self.root, "a.jpg", JPEG + b"\x00\x00"),
                         "a.jpg")

    def test_a_phone_photo_with_data_after_its_end_is_kept(self):
        for name, raw in (("pixel.jpg", PIXEL_MOTION), ("samsung.jpg", SAMSUNG),
                          ("motion.jpg", SAMSUNG_MOTION)):
            self.assertEqual(store.save_card_picture(self.root, name, raw), name, name)

    def test_a_jpeg_cut_short_is_refused_even_with_a_thumbnail_inside(self):
        # the thumbnail ends in a marker of its own, which must not pass for the end
        for cut in (60, 90, 120):
            raw = _MAIN[:len(_MAIN) * cut // 100] if cut < 100 else _MAIN[:-2]
            self.assertIn(b"\xff\xd9", raw)
            with self.assertRaises(RecordError, msg=cut) as refused:
                store.save_card_picture(self.root, "cut.jpg", raw)
            self.assertIn("That JPEG does not end the way a JPEG does",
                          str(refused.exception))
        # a Samsung block with no picture end before it, and a video box with none
        for raw in (b"\xff\xd8\xff\xe0" + b"m" * 50 + b"SEFH" + b"d" * 24 + b"SEFT",
                    b"\xff\xd8\xff\xe0" + b"m" * 50 + b"\x00\x00\x00\x18ftypmp42"):
            with self.assertRaises(RecordError):
                store.save_card_picture(self.root, "cut.jpg", raw)
        self.assertEqual(store.card_pictures(self.root), [])

    def test_a_gif_and_a_png_may_end_in_zeros(self):
        self.assertEqual(store.save_card_picture(self.root, "a.gif", GIF + b"\x00\x00"),
                         "a.gif")
        self.assertEqual(store.save_card_picture(self.root, "a.png", png() + b"\x00\x00"),
                         "a.png")

    def test_a_webp_may_be_padded_with_zeros_and_not_with_anything_else(self):
        self.assertEqual(store.save_card_picture(self.root, "a.webp", WEBP + b"\x00" * 3),
                         "a.webp")
        with self.assertRaises(RecordError) as refused:
            store.save_card_picture(self.root, "b.webp", WEBP + b"\x00\x01")
        self.assertIn("That WEBP does not end the way a WEBP does", str(refused.exception))

    def test_a_refusal_says_whether_it_is_the_start_or_the_end(self):
        for raw in (SVG, HTML_AS_PNG, b"", b"RIFF1234WAVEfmt "):
            with self.assertRaises(RecordError) as refused:
                store.save_card_picture(self.root, "a.png", raw)
            self.assertEqual(str(refused.exception),
                             "That is not a picture Plainbook can use: "
                             "PNG, JPEG, GIF or WEBP only.")
        for raw, named in ((png()[:-12], "PNG"), (JPEG[:-2], "JPEG"),
                           (GIF[:-1], "GIF"), (WEBP[:-1], "WEBP")):
            with self.assertRaises(RecordError, msg=named) as refused:
                store.save_card_picture(self.root, "a.png", raw)
            self.assertEqual(str(refused.exception),
                             f"That {named} does not end the way a {named} does, "
                             "so it may be cut short: save it again or pick another.")

    def test_a_name_of_any_alphabet_is_kept(self):
        # MY_CHART is Russian for "my chart", written as escapes: the
        # repository keeps Cyrillic out of its files (check_public.py)
        self.assertEqual(store.save_card_picture(self.root, MY_CHART + ".png", png()),
                         MY_CHART_KEPT + ".png")
        self.assertEqual(store.save_card_picture(self.root, MY_CHART + ".png", png()),
                         MY_CHART_KEPT + "-2.png")
        self.assertEqual(store.save_card_picture(self.root, "\u65e5\u672c.png", png()),
                         "\u65e5\u672c.png")
        # a Mac may send a letter and its accent apart: the short i of
        # Russian kept as one letter, not as a letter and a hyphen
        self.assertEqual(store.save_card_picture(self.root, "\u0438\u0306.png", png()),
                         "\u0439.png")

    def test_a_name_windows_keeps_for_itself_gets_a_suffix(self):
        for name, kept in (("con.png", "con-1.png"), ("NUL.png", "NUL-1.png"),
                           ("com1.png", "com1-1.png"), ("lpt9.jpg", "lpt9-1.png"),
                           ("aux.tar.png", "aux.tar-1.png"), ("console.png", "console.png")):
            self.assertEqual(store.save_card_picture(self.root, name, png()), kept, name)

    def test_a_link_is_not_a_picture(self):
        store.save_card_picture(self.root, "real.png", png())
        base = store.card_pictures_dir(self.root)
        outside = os.path.join(self.root, "journal", "secret.png")
        with open(outside, "wb") as f:
            f.write(png())
        try:
            os.symlink(outside, os.path.join(base, "link.png"))
        except (OSError, NotImplementedError):
            self.skipTest("this system makes no symbolic links")
        self.assertEqual(store.card_pictures(self.root), ["real.png"])
        self.assertIsNone(store.card_picture_path(self.root, "link.png"))

    def test_two_removals_at_once_are_one_removal(self):
        store.save_card_picture(self.root, "a.png", png())
        real_move = store.shutil.move

        def lost_to_the_other_one(src, dst):
            os.remove(src)                # the other press got there first
            return real_move(src, dst)
        with mock.patch.object(store.shutil, "move", lost_to_the_other_one):
            self.assertIsNone(store.trash_card_picture(self.root, "a.png"))
        self.assertIsNone(store.trash_card_picture(self.root, "a.png"))

    def test_eight_megabytes_is_the_most(self):
        most = png_of_size(store.CARD_PICTURE_MAX)
        self.assertEqual(len(most), store.CARD_PICTURE_MAX)
        self.assertEqual(store.save_card_picture(self.root, "most.png", most),
                         "most.png")
        with self.assertRaises(RecordError):
            store.save_card_picture(self.root, "more.png",
                                    png_of_size(store.CARD_PICTURE_MAX + 1))
        self.assertEqual(store.card_pictures(self.root), ["most.png"])

    def test_the_name_is_cleaned_and_a_taken_one_is_not_written_over(self):
        first = store.save_card_picture(self.root, "My chart (1).png", png(2, 2))
        self.assertEqual(first, "My-chart-1-.png".replace("-1-.png", "-1.png"))
        again = store.save_card_picture(self.root, "My chart (1).png", png(3, 3))
        self.assertNotEqual(again, first)
        self.assertRegex(again, r"^[A-Za-z0-9._-]+\.png$")
        with open(os.path.join(store.card_pictures_dir(self.root), first), "rb") as f:
            self.assertEqual(f.read(), png(2, 2))                  # the first one stands
        for odd in ("../../x.png", "..\\..\\x.png", "日本.png", "", ".png", "..png"):
            kept = store.save_card_picture(self.root, odd, png())
            self.assertRegex(kept, r"^[^\W_][\w.-]*\.png$", odd)
            self.assertEqual(os.path.dirname(os.path.join(
                store.card_pictures_dir(self.root), kept)),
                store.card_pictures_dir(self.root))

    def test_the_listing_is_sorted_and_holds_only_pictures(self):
        for name in ("b.png", "a.png"):
            store.save_card_picture(self.root, name, png())
        base = store.card_pictures_dir(self.root)
        open(os.path.join(base, ".gitkeep"), "w").close()
        open(os.path.join(base, "notes.txt"), "w").close()
        os.mkdir(os.path.join(base, "folder.png"))
        self.assertEqual(store.card_pictures(self.root), ["a.png", "b.png"])
        self.assertEqual(store.card_pictures(os.path.join(self.root, "nowhere")), [])

    def test_a_name_is_looked_for_never_built_into_a_path(self):
        store.save_card_picture(self.root, "a.png", png())
        secret = os.path.join(self.root, "journal", "secret.png")
        with open(secret, "wb") as f:
            f.write(png())
        self.assertEqual(store.card_picture_path(self.root, "a.png"),
                         os.path.join(store.card_pictures_dir(self.root), "a.png"))
        for name in ("../secret.png", "..", "", "A.png", "a.png/", "./a.png",
                     "a.png\0", "../card-pictures/a.png", "/etc/passwd"):
            self.assertIsNone(store.card_picture_path(self.root, name), name)
            self.assertIsNone(store.trash_card_picture(self.root, name), name)
        self.assertTrue(os.path.exists(secret))

    def test_removing_moves_the_file_to_the_trash_and_leaves_nothing(self):
        store.save_card_picture(self.root, "a.png", png(4, 4))
        target = store.trash_card_picture(self.root, "a.png")
        self.assertEqual(store.card_pictures(self.root), [])
        self.assertEqual(os.listdir(store.card_pictures_dir(self.root)), [])
        self.assertTrue(target.startswith(os.path.join(self.root, store.TRASH)))
        with open(target, "rb") as f:
            self.assertEqual(f.read(), png(4, 4))
        # the Trash tab restores records: a picture is not one of them
        self.assertEqual(store.trash_list(self.root), [])
        # the same name again, removed again, takes a place of its own
        store.save_card_picture(self.root, "a.png", png(5, 5))
        again = store.trash_card_picture(self.root, "a.png")
        self.assertNotEqual(again, target)
        self.assertEqual(len(os.listdir(os.path.join(self.root, store.TRASH))), 2)

    def test_the_journal_reads_with_the_folder_there(self):
        store.save_account(self.root, Account(id="broker", name="Broker",
                                              start_balance=1000))
        store.save_trade(self.root, Trade(
            id="2026-03-01-eurusd", pair="EURUSD", account="broker",
            opened=datetime(2026, 3, 1, 10), closed=datetime(2026, 3, 1, 15),
            direction="long", style="swing", risk=1.0, pnl=50.0, result="Win"))
        store.save_card_picture(self.root, "a.png", png())
        problems = []
        self.assertEqual(len(store.all_trades(self.root, problems)), 1)
        self.assertEqual(problems, [])
        self.assertEqual(len(balances.Journal.load(self.root).trades), 1)
        script = os.path.join(os.path.dirname(TESTS), "tools", "check_journal.py")
        done = subprocess.run([sys.executable, script, self.root],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


def multipart(field, filename, raw, mark="----plainbook-card-test"):
    body = (f'--{mark}\r\nContent-Disposition: form-data; name="{field}"; '
            f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'
            ).encode() + raw + f"\r\n--{mark}--\r\n".encode()
    return body, {"Content-Type": f"multipart/form-data; boundary={mark}"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class CardPictureServer(unittest.TestCase):
    """A journal and a server of its own: the pictures and the trash here are
    not the shared story of test_server.py."""
    ID, SHORT = "2026-08-12-01-eurusd", "2026-08-12-02-gbpusd"
    DOOMED = "2026-08-15-01-audusd"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        store.save_account(cls.root, Account(id="zq-fund", name="Zebra Quartz Fund",
                                             start_balance=87654.0))
        base = dict(account="zq-fund", style="swing", entry_tf="H4", risk=0.77,
                    opened=datetime(2026, 8, 12, 10, 30), opened_time=True,
                    closed=datetime(2026, 8, 14), result="Win", pnl=13579.0,
                    note="notewordzx", conclusions="conclusionzx held")
        store.save_trade(cls.root, Trade(id=cls.ID, pair="EURUSD", direction="long", **base))
        store.save_trade(cls.root, Trade(id=cls.SHORT, pair="GBPUSD",
                                         direction="short", **{**base, "pnl": -2000.0,
                                                               "result": "Lose"}))
        store.save_trade(cls.root, Trade(id=cls.DOOMED, pair="AUDUSD", direction="long", **base))
        store.save_trade(cls.root, Trade(
            id="2026-08-13-01-xauusd", pair="XAUUSD", direction="long",
            **{**base, "result": None, "pnl": None, "closed": None}))
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

    def setUp(self):
        # every test starts with no pictures and an empty trash
        for folder in (store.card_pictures_dir(self.root),
                       os.path.join(self.root, store.TRASH)):
            for name in (os.listdir(folder) if os.path.isdir(folder) else []):
                full = os.path.join(folder, name)
                shutil.rmtree(full) if os.path.isdir(full) else os.remove(full)

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path):
        with urllib.request.urlopen(self.url(path)) as r:
            return r.status, r.read().decode("utf-8"), r.headers

    def post(self, path, data, headers=None):
        """The answer without following it: the redirect is what is looked at."""
        opener = urllib.request.build_opener(NoRedirect)
        req = urllib.request.Request(self.url(path), data=data, headers=headers or {})
        try:
            with opener.open(req) as r:
                return r.status, r.headers.get("Location"), r.read()
        except urllib.error.HTTPError as e:
            try:
                return e.code, e.headers.get("Location"), e.read()
            finally:
                e.close()

    def add(self, name, raw, query=""):
        body, headers = multipart("picture", name, raw)
        return self.post(f"/card-picture/add?card={self.ID}{query}", body, headers)

    def remove(self, name, bg="", query=""):
        data = urllib.parse.urlencode({"name": name, "bg": bg}).encode()
        return self.post(f"/card-picture/remove?card={self.ID}{query}", data)

    def card(self, query="", trade=None):
        return self.get(f"/share/card/{trade or self.ID}{query}")[1]

    def drawn(self, query="", trade=None):
        """The picture itself, apart from the strip over it: the thumbnails
        of the strip draw a rocket of their own."""
        page = self.card(query, trade)
        return page[page.index('<div class="cardpic">'):]

    def folder(self):
        return store.card_pictures(self.root)

    def trash(self):
        base = os.path.join(self.root, store.TRASH)
        return sorted(os.listdir(base)) if os.path.isdir(base) else []

    # --- which background ---
    def test_a_card_stands_on_the_rocket_of_its_side_by_default(self):
        long_page, short_page = self.drawn(), self.drawn(trade=self.SHORT)
        for page in (long_page, short_page):
            self.assertIn("M0 -320C92 -222", page)               # the rocket
            self.assertNotIn("<image", page)
            self.assertNotIn("radient", page)
        self.assertIn("rotate(42)", long_page)
        self.assertIn("rotate(138)", short_page)
        self.assertNotIn("rotate(138)", long_page)

    def test_plain_is_the_ruled_page(self):
        page = self.drawn("?bg=plain")
        self.assertNotIn("M0 -320C92 -222", page)
        self.assertIn('d="M0 75H1200"', page)
        self.assertNotIn("<image", page)
        self.assertNotIn("<linearGradient", page)

    def test_a_picture_of_the_owners_is_the_background(self):
        kept = store.save_card_picture(self.root, "mine.png", png())
        page = self.drawn(f"?bg={kept}")
        self.assertIn('<image href="data:image/png;base64,', page)
        self.assertNotIn("M0 -320C92 -222", page)
        self.assertEqual(page.count('id="card-fade"'), 1)   # its one gradient
        self.assertEqual(page.count("<linearGradient"), 1)

    def test_the_row_of_backgrounds_takes_any_number_and_stays_one_row(self):
        for n in range(30):
            store.save_card_picture(self.root, f"mine-{n}.png", png())
        page = self.card()
        rail = page[page.index('<div class="rail">'):page.index('<form class="up"')]
        self.assertEqual(rail.count('class="pic"'), 32)     # the two standard ones and 30
        self.assertIn(".bar .rail{flex:1 1 240px;min-width:0;display:flex", page)

    def test_a_name_that_is_not_in_the_listing_gives_the_rocket_and_reads_nothing(self):
        store.save_card_picture(self.root, "mine.png", png())
        secret = os.path.join(self.root, "journal", "secret.png")
        with open(secret, "wb") as f:
            f.write(png(7, 7))
        default = self.drawn()
        for bad in ("nothing.png", "../secret.png", "..%2Fsecret.png", "MINE.PNG",
                    "mine.png/", "%2e%2e%2f%2e%2e%2fsecret.png", "plain%00"):
            page = self.drawn(f"?bg={bad}")
            self.assertNotIn("<image", page, bad)
            self.assertIn("M0 -320C92 -222", page, bad)
            self.assertNotIn("data:image/png;base64,", page, bad)

    # --- the page ---
    def test_the_row_of_backgrounds_is_part_of_the_strip(self):
        store.save_card_picture(self.root, "mine.png", png())
        page = self.card("?bg=mine.png")
        strip = page[page.index('<div class="bar">'):page.index('<div class="cardpic">')]
        for part in ("Background", "Standard", "Plain", "mine.png", "Add picture",
                     'type="file"', 'enctype="multipart/form-data"',
                     'src="/card-picture/mine.png"', "confirm("):
            self.assertIn(part, strip, part)
        self.assertEqual(strip.count('aria-current="true"'), 1)
        self.assertRegex(strip, r'class="thumb on" href="/share/card/[^"]+\?bg=mine.png"')
        self.assertNotIn("Background", page[page.index('<div class="cardpic">'):])

    def test_the_links_keep_the_way_back(self):
        store.save_card_picture(self.root, "mine.png", png())
        page = self.card("?report=2026-08&bg=plain")
        trade = f"/share/card/{self.ID}?report=2026-08"
        self.assertIn(f'href="{trade}"', page)                            # Standard
        self.assertIn(f'href="{trade}&amp;bg=plain"', page)
        self.assertIn(f'href="{trade}&amp;bg=mine.png"', page)
        self.assertIn(f'<a href="/trade/{self.ID}?report=2026-08">Back</a>', page)
        self.assertIn(f'action="/card-picture/add?card={self.ID}&amp;report=2026-08"', page)
        self.assertIn(f'action="/card-picture/remove?card={self.ID}&amp;report=2026-08"',
                      page)

    def test_the_page_of_a_card_on_a_picture_holds_nothing_of_the_trade_but_the_card(self):
        store.save_card_picture(self.root, "mine.png", png())
        for query in ("", "?bg=plain", "?bg=mine.png"):
            page = self.card(query)
            page = re.sub(r"data:image/[a-z]+;base64,[A-Za-z0-9+/=]+", "PICTURE", page)
            for word in ("13579", "87654", "Zebra", "Quartz", "zq-fund", "notewordzx",
                         "conclusionzx", "0.77", "swing", "H4"):
                self.assertNotIn(word, page, (query, word))

    def test_open_and_unknown_trades_have_no_card_whatever_the_background(self):
        for trade in ("2026-08-13-01-xauusd", "nothing"):
            for query in ("", "?bg=plain"):
                with self.assertRaises(urllib.error.HTTPError) as gone:
                    self.card(query, trade)
                self.assertEqual(gone.exception.code, 404)
                gone.exception.close()

    # --- serving a picture ---
    def test_a_picture_is_served_under_its_name_with_its_type(self):
        for name, raw, kind in (("a.png", png(), "image/png"), ("b.jpg", JPEG, "image/jpeg"),
                                ("c.gif", GIF, "image/gif"), ("d.webp", WEBP, "image/webp")):
            kept = store.save_card_picture(self.root, name, raw)
            with urllib.request.urlopen(self.url(f"/card-picture/{kept}")) as r:
                self.assertEqual(r.headers.get("Content-Type"), kind)
                self.assertEqual(r.read(), raw)
        for bad in ("nothing.png", "..%2Fsecret.png", "%2e%2e", "A.png"):
            with self.assertRaises(urllib.error.HTTPError) as gone:
                self.get(f"/card-picture/{bad}")
            self.assertEqual(gone.exception.code, 404, bad)
            gone.exception.close()

    def test_a_name_in_russian_is_served_and_shown_in_the_row_of_backgrounds(self):
        kept = store.save_card_picture(self.root, "\u041c\u043e\u0439 \u0433\u0440\u0430\u0444\u0438\u043a.png", png())
        self.assertEqual(kept, "\u041c\u043e\u0439-\u0433\u0440\u0430\u0444\u0438\u043a.png")
        with urllib.request.urlopen(
                self.url(f"/card-picture/{urllib.parse.quote(kept, safe='')}")) as r:
            self.assertEqual(r.headers.get("Content-Type"), "image/png")
            self.assertEqual(r.read(), png())
        page = self.card()
        self.assertIn(f'<img src="/card-picture/{urllib.parse.quote(kept, safe="")}"', page)
        self.assertIn('<span class="cap">\u041c\u043e\u0439-\u0433\u0440\u0430\u0444\u0438\u043a.png</span>', page)
        # and the card stands on it
        self.assertIn('<image href="data:image/png;base64,',
                      self.drawn(f"?bg={urllib.parse.quote(kept, safe='')}"))
        # the form takes such a name too and lands on the card with it chosen
        code, where, _ = self.add("\u0415\u0449\u0451 \u043e\u0434\u0438\u043d.png", png(3, 3))
        self.assertEqual(code, 303)
        self.assertIn("bg=" + urllib.parse.quote("\u0415\u0449\u0451-\u043e\u0434\u0438\u043d.png", safe=""), where)

    # --- adding ---
    def test_adding_keeps_the_picture_and_shows_the_card_on_it(self):
        code, where, _ = self.add("My Chart.png", png(), "&report=2026-08")
        self.assertEqual(code, 303)
        self.assertEqual(self.folder(), ["My-Chart.png"])
        self.assertEqual(
            where, f"/share/card/{self.ID}?report=2026-08&bg=My-Chart.png"
                   "&said=Picture%20added")
        _, page, _ = self.get(where.split("&said=")[0])
        self.assertIn('<image href="data:image/png;base64,', page)
        # the word the form left is said once, in the strip
        _, said, _ = self.get(where)
        self.assertIn('class="word said"', said)

    def test_a_clash_takes_a_free_name(self):
        self.add("a.png", png(2, 2))
        code, where, _ = self.add("a.png", png(3, 3))
        self.assertEqual(code, 303)
        self.assertEqual(self.folder(), ["a-2.png", "a.png"])
        self.assertIn("bg=a-2.png", where)
        with open(os.path.join(store.card_pictures_dir(self.root), "a.png"), "rb") as f:
            self.assertEqual(f.read(), png(2, 2))

    def test_what_is_not_a_picture_is_refused_and_nothing_is_kept(self):
        for name, raw in (("fake.png", HTML_AS_PNG), ("logo.svg", SVG), ("logo.png", SVG),
                          ("empty.png", b"")):
            code, _, body = self.add(name, raw)
            self.assertEqual(code, 400, name)
            self.assertIn(b"not a picture", body, name)
        code, _, _ = self.post(f"/card-picture/add?card={self.ID}", b"not a form",
                               {"Content-Type": "text/plain"})
        self.assertEqual(code, 400)
        self.assertEqual(self.folder(), [])
        self.assertFalse(os.path.isdir(store.card_pictures_dir(self.root))
                         and os.listdir(store.card_pictures_dir(self.root)))

    def test_eight_megabytes_and_a_byte_is_refused(self):
        most = png_of_size(store.CARD_PICTURE_MAX)
        code, _, body = self.add("more.png", png_of_size(store.CARD_PICTURE_MAX + 1))
        self.assertEqual(code, 400)
        self.assertIn(b"8 MB", body)
        self.assertEqual(self.folder(), [])
        code, _, _ = self.add("most.png", most)
        self.assertEqual(code, 303)
        self.assertEqual(self.folder(), ["most.png"])

    def test_a_form_from_another_site_is_not_taken(self):
        body, headers = multipart("picture", "a.png", png())
        headers["Origin"] = "http://evil.example"
        code, _, _ = self.post(f"/card-picture/add?card={self.ID}", body, headers)
        self.assertEqual(code, 403)
        self.assertEqual(self.folder(), [])
        data = urllib.parse.urlencode({"name": "a.png"}).encode()
        store.save_card_picture(self.root, "a.png", png())
        code, _, _ = self.post(f"/card-picture/remove?card={self.ID}", data,
                               {"Origin": "http://evil.example"})
        self.assertEqual(code, 403)
        self.assertEqual(self.folder(), ["a.png"])

    def test_a_picture_bigger_than_the_most_is_refused_before_it_is_parsed(self):
        body = b"x" * (store.CARD_PICTURE_MAX + (64 << 10) + 1)
        code, _, answer = self.post(f"/card-picture/add?card={self.ID}", body,
                                    {"Content-Type": "multipart/form-data; boundary=zz"})
        self.assertEqual(code, 400)
        self.assertIn(b"8 MB", answer)
        self.assertIn(b"Not saved", answer)
        self.assertEqual(self.folder(), [])

    def test_a_picture_that_does_not_decode_is_kept_and_said_so_by_the_page(self):
        # it has the signature and the end of a PNG, which is all the server can
        # tell; the page opens it before it makes a file, see browser_check.mjs
        code, where, _ = self.add("odd.png", broken_png())
        self.assertEqual(code, 303)
        page = self.card("?bg=odd.png")
        self.assertIn("This picture does not open", page)          # the script's word
        self.assertIn("card_opens", page)

    # --- a body left on the connection ---
    def raw(self, request, wait=1.5):
        """What the server answers to bytes sent as they are: the responses it
        gave, and whether it closed the connection afterwards."""
        with socket.create_connection(("127.0.0.1", self.port), timeout=wait) as c:
            c.sendall(request)
            got = b""
            closed = False
            try:
                while True:
                    more = c.recv(65536)
                    if not more:
                        closed = True
                        break
                    got += more
            except socket.timeout:
                pass
        return len(re.findall(rb"HTTP/1\.[01] \d{3} ", got)), closed, got

    def inner(self, host=None):
        """Two whole requests a page of another site could carry in a body: the
        removal of a picture and the deletion of a trade, as the owner's own
        browser would send them."""
        host = host or f"127.0.0.1:{self.port}"
        out = b""
        for path, body in ((f"/card-picture/remove?card={self.ID}", b"name=a.png&bg="),
                           (f"/trade/{self.DOOMED}/delete", b"")):
            out += (f"POST {path} HTTP/1.1\r\nHost: {host}\r\n"
                    f"Content-Type: application/x-www-form-urlencoded\r\n"
                    f"Content-Length: {len(body)}\r\n\r\n").encode() + body
        return out

    def outer(self, path, headers, body):
        head = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
        return (f"POST {path} HTTP/1.1\r\n{head}Content-Length: {len(body)}\r\n\r\n"
                ).encode() + body

    def untouched(self):
        self.assertEqual(self.folder(), ["a.png"])
        self.assertEqual(self.trash(), [])
        self.assertTrue(os.path.isdir(store.trade_dir(self.root, self.DOOMED)))

    def test_a_refusal_closes_the_connection_so_a_body_is_never_read_as_requests(self):
        """A page of another site can put whole requests into the body of a
        form it sends. The refusal does not read that body, so a connection
        left open would read it as the next requests, with no Origin and a
        Host of its own choosing."""
        store.save_card_picture(self.root, "a.png", png())
        own = f"127.0.0.1:{self.port}"
        cases = {
            "foreign origin": self.outer("/card-picture/add", {
                "Host": own, "Origin": "http://evil.example"}, self.inner()),
            "foreign origin on a form": self.outer("/card-picture/remove", {
                "Host": own, "Origin": "http://evil.example",
                "Content-Type": "text/plain"}, self.inner()),
            "foreign host": self.outer("/card-picture/add", {"Host": "evil.example"},
                                       self.inner()),
            "foreign host and origin": self.outer("/card-picture/add", {
                "Host": "evil.example", "Origin": "http://evil.example"}, self.inner()),
            "chunked": (f"POST /card-picture/add HTTP/1.1\r\nHost: {own}\r\n"
                        f"Transfer-Encoding: chunked\r\n\r\n").encode()
                       + f"{len(self.inner()):x}\r\n".encode() + self.inner()
                       + b"\r\n0\r\n\r\n",
            "a length that is no number": (
                f"POST /card-picture/add HTTP/1.1\r\nHost: {own}\r\n"
                f"Content-Length: many\r\n\r\n").encode() + self.inner(),
            "a negative length": (
                f"POST /card-picture/add HTTP/1.1\r\nHost: {own}\r\n"
                f"Content-Length: -5\r\n\r\n").encode() + self.inner(),
            "a body over the limit": (
                f"POST /card-picture/add HTTP/1.1\r\nHost: {own}\r\n"
                f"Content-Length: {self.S.SHOT_LIMIT + 1}\r\n\r\n").encode()
                + self.inner(),
            "a body over the limit elsewhere": (
                f"POST /draft/upload HTTP/1.1\r\nHost: {own}\r\n"
                f"Content-Length: {self.S.SHOT_LIMIT + 1}\r\n\r\n").encode()
                + self.inner(),
            "a backup with no length": (
                f"POST /backup/upload HTTP/1.1\r\nHost: {own}\r\n"
                f"Content-Length: 0\r\n\r\n").encode() + self.inner(),
            "a get with a foreign host": (
                f"GET / HTTP/1.1\r\nHost: evil.example\r\nContent-Length: "
                f"{len(self.inner())}\r\n\r\n").encode() + self.inner(),
        }
        for what, request in cases.items():
            answers, closed, got = self.raw(request)
            self.assertEqual(answers, 1, (what, got[:300]))
            self.assertTrue(closed, what)
            self.untouched()

    def test_a_method_the_journal_does_not_have_closes_the_connection_too(self):
        store.save_card_picture(self.root, "a.png", png())
        own = f"127.0.0.1:{self.port}"
        for method in ("PUT", "DELETE", "PATCH"):
            request = (f"{method} /card-picture/add HTTP/1.1\r\nHost: {own}\r\n"
                       f"Content-Length: {len(self.inner())}\r\n\r\n").encode() + self.inner()
            answers, closed, _ = self.raw(request)
            self.assertEqual((answers, closed), (1, True), method)
            self.untouched()

    def test_an_honest_form_keeps_its_connection_for_the_next_one(self):
        """The cost of the above is only on refusals: two forms of the owner on
        one connection are both answered."""
        store.save_card_picture(self.root, "a.png", png())
        store.save_card_picture(self.root, "b.png", png(3, 3))
        own = f"127.0.0.1:{self.port}"
        forms = b"".join(
            (f"POST /card-picture/remove?card={self.ID} HTTP/1.1\r\nHost: {own}\r\n"
             f"Content-Type: application/x-www-form-urlencoded\r\n"
             f"Content-Length: {len(body)}\r\n\r\n").encode() + body
            for body in (b"name=a.png&bg=", b"name=b.png&bg="))
        answers, closed, got = self.raw(forms, wait=1.0)
        self.assertEqual((answers, got.count(b"HTTP/1.1 303")), (2, 2))
        self.assertEqual(self.folder(), [])

    def test_over_the_general_limit_the_picture_form_gets_a_page_with_a_way_back(self):
        own = f"127.0.0.1:{self.port}"
        request = (f"POST /card-picture/add?card={self.ID} HTTP/1.1\r\nHost: {own}\r\n"
                   f"Content-Length: {self.S.SHOT_LIMIT + 1}\r\n\r\n").encode()
        answers, closed, got = self.raw(request)
        self.assertEqual(answers, 1)
        self.assertIn(b"HTTP/1.1 413", got)
        self.assertIn(b"Not saved", got)
        self.assertIn(b"Back to the form", got)
        self.assertIn(b"8 MB", got)
        self.assertTrue(closed)

    # --- removing ---
    def test_removing_moves_the_file_to_the_trash_and_lands_on_the_card(self):
        store.save_card_picture(self.root, "a.png", png())
        store.save_card_picture(self.root, "b.png", png(3, 3))
        code, where, _ = self.remove("a.png", bg="b.png", query="&report=2026-08")
        self.assertEqual(code, 303)
        self.assertEqual(where, f"/share/card/{self.ID}?report=2026-08&bg=b.png"
                                "&said=Picture%20removed")
        self.assertEqual(self.folder(), ["b.png"])
        self.assertEqual(len(self.trash()), 1)
        self.assertTrue(self.trash()[0].startswith("card-picture-a-"))
        self.assertEqual(os.listdir(store.card_pictures_dir(self.root)), ["b.png"])
        # taking off the one that was chosen goes back to the standard card
        code, where, _ = self.remove("b.png", bg="b.png")
        self.assertEqual(where, f"/share/card/{self.ID}?said=Picture%20removed")
        self.assertEqual(self.folder(), [])

    def test_only_a_name_of_the_listing_is_removed(self):
        store.save_card_picture(self.root, "a.png", png())
        outside = os.path.join(self.root, "journal", "secret.png")
        with open(outside, "wb") as f:
            f.write(png())
        for name in ("../secret.png", "nothing.png", "", "A.png"):
            code, _, _ = self.remove(name)
            self.assertEqual(code, 400, name)
        self.assertTrue(os.path.exists(outside))
        self.assertEqual(self.folder(), ["a.png"])
        self.assertEqual(self.trash(), [])

    def test_the_trash_tab_does_not_list_a_removed_picture(self):
        store.save_card_picture(self.root, "a.png", png())
        self.remove("a.png")
        _, page, _ = self.get("/accounts")
        self.assertNotIn("card-picture", page)
        self.assertNotIn("a.png", page)
