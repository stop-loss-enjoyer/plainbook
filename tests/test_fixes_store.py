#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What a file holds survives a save: the owner's settings and lists that do
not parse, a typed line that looks like a heading, the text written by hand
around the sections of a trade, a trade renamed under the notes and cards
that cite it, and the ids taken from an address."""
import importlib
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import stats, store
from plainbook.balances import Journal
from plainbook.model import (Account, Card, Graded, IdeaBlock, Note, Plan,
                             RecordError, Trade, Week, _WEEK_ID)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class TypedHeadingsTest(unittest.TestCase):
    def test_a_heading_typed_behind_a_space_comes_back_as_typed(self):
        k = Plan(id="p", day=datetime(2026, 1, 31),
                 updates="a\n ## Exit\nfoo\n  ## Review\nbar")
        back = store.text_to_plan(store.plan_to_text(k))
        self.assertEqual(back.updates, k.updates)

    def test_a_card_and_a_week_keep_what_stands_above_their_sections(self):
        k = Card(day=datetime(2026, 1, 2).date(), focus="f",
                 preamble="Written above, by hand.\n## Focus typed")
        back = store.text_to_card(store.card_to_text(k))
        self.assertEqual((back.preamble, back.focus), (k.preamble, "f"))
        w = Week(week="2026-W02", lesson="l", preamble="By hand.")
        self.assertEqual(store.text_to_week(store.week_to_text(w)).preamble, "By hand.")

    def test_a_known_heading_typed_in_a_plan_stays_where_it_was_typed(self):
        k = Plan(id="p", day=datetime(2026, 1, 31), plan="x\n## y\nz",
                 review="r\n## Plan\nboom",
                 analysis=[IdeaBlock(tf="H4", text="a\n## Review\nb")])
        back = store.text_to_plan(store.plan_to_text(k))
        self.assertEqual(back.plan, "x\n## y\nz")
        self.assertEqual(back.review, "r\n## Plan\nboom")
        self.assertEqual(back.analysis[0].text, "a\n## Review\nb")
        # written with a space in front, so the file is still cut right
        self.assertIn("\n ## Plan\n", store.plan_to_text(k))

    def test_a_heading_typed_in_the_conclusions_of_a_trade_is_kept(self):
        t = Trade(id="t", account="a", direction="long", style="s",
                  opened=datetime(2026, 1, 1),
                  conclusions="keep\n## Lessons\nlost text\n## Idea\nnot an idea",
                  updates="u\n## Exit\nstill an update")
        back = store.text_to_trade(store.trade_to_text(t))
        self.assertEqual(back.conclusions, t.conclusions)
        self.assertEqual(back.updates, t.updates)
        self.assertEqual(back.idea, [])

    def test_cards_keep_a_typed_heading(self):
        c = Card(day=datetime(2026, 2, 3), learned="one\n## Errors\ntwo",
                 errors="real errors",
                 assessment=[Graded(trade="EURUSD", grade="A", result="win",
                                    id="2026-02-03-01-eurusd")])
        back = store.text_to_card(store.card_to_text(c))
        self.assertEqual(back.learned, "one\n## Errors\ntwo")
        self.assertEqual(back.errors, "real errors")
        self.assertEqual(back.assessment[0].id, "2026-02-03-01-eurusd")
        w = Week(week="2026-W05", lesson="l\n## Trades\nm", missed="n")
        back = store.text_to_week(store.week_to_text(w))
        self.assertEqual(back.lesson, "l\n## Trades\nm")
        self.assertEqual(back.missed, "n")

    def test_hand_written_text_around_the_sections_of_a_trade_survives(self):
        text = ("---\nid: 2026-01-05-01-eurusd\naccount: broker\npair: EURUSD\n"
                "direction: long\nstyle: swing\nexecution:\nrisk %: 1\nentry: 2026-01-05\n---\n\n"
                "Written on the train.\n\n## Idea\n\n### H4\n\nbreakout\n\n"
                "## Exit\n\nClosed by hand before the news.\n\n![](shots/exit-1.png)\n\n"
                "## Conclusions\n\nwell done\n\n## Mistakes\n\nEntered before the candle closed.\n")
        t = store.text_to_trade(text)
        self.assertEqual(t.preamble, "Written on the train.")
        self.assertEqual(t.exit_text, "Closed by hand before the news.")
        self.assertEqual(t.exit_images, ["shots/exit-1.png"])
        self.assertIn("## Mistakes\n\nEntered before", t.conclusions)
        self.assertEqual(store.trade_to_text(t), text)

    def test_a_file_with_only_its_own_headings_reads_as_before(self):
        text = ("---\nid: 2026-01-05-01-eurusd\naccount: broker\npair: EURUSD\n"
                "direction: long\nstyle: swing\nexecution:\nrisk %: 1\nentry: 2026-01-05\n---\n\n"
                "## Idea\n\n### H4\n\nbreakout\n\n![](shots/idea-1.png)\n\n### D1\n\ntrend\n\n"
                "## Updates\n\n**06.01.2026**: moved the stop\n\n"
                "## Exit\n\n![](shots/exit-1.png)\n\n## Conclusions\n\nwell done\n")
        t = store.text_to_trade(text)
        self.assertEqual([(b.tf, b.text, b.images) for b in t.idea],
                         [("H4", "breakout", ["shots/idea-1.png"]),
                          ("D1", "trend", [])])
        self.assertEqual(t.updates, "**06.01.2026**: moved the stop")
        self.assertEqual(t.exit_images, ["shots/exit-1.png"])
        self.assertEqual((t.exit_text, t.preamble), ("", ""))
        self.assertEqual(t.conclusions, "well done")
        self.assertEqual(store.trade_to_text(t), text)


class OwnerFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        store.save_account(self.root, Account(id="broker", name="Broker",
                                              start_balance=10000))

    def tearDown(self):
        self.tmp.cleanup()

    def break_all(self):
        j = os.path.join(self.root, store.JOURNAL)
        write(os.path.join(j, "settings.md"), "---\nclock: Europe/Prague\nstop_edge 1.3\n---\n")
        write(os.path.join(j, "vocabulary.md"), "---\nstyles\n  - swing\n---\n")
        write(os.path.join(j, "pairs.md"), "---\npairs:\n  - EURUSD\n")

    def test_a_broken_list_is_named_and_the_defaults_stand_in(self):
        self.break_all()
        j = Journal.load(self.root)
        self.assertEqual(sorted(p for p, _ in j.problems),
                         ["journal/pairs.md", "journal/settings.md",
                          "journal/vocabulary.md"])
        self.assertEqual(j.stop_edge, store.STOP_EDGE)
        self.assertEqual(j.clock, "")
        self.assertEqual(store.all_words(self.root, "styles"),
                         store.VOCABULARY["styles"])
        self.assertEqual(store.all_pairs(self.root), [])
        # a save refuses to write over a file it cannot read, which still
        # holds what the typo hid, and leaves the file as it was
        for path, save in (("settings.md", lambda: store.save_stop_edge(self.root, "1.5")),
                           ("settings.md", lambda: store.save_clock(self.root, "")),
                           ("vocabulary.md", lambda: store.save_words(self.root, "styles", ["news"])),
                           ("pairs.md", lambda: store.save_pairs(self.root, ["AUDUSD"]))):
            full = os.path.join(self.root, "journal", path)
            before = open(full, encoding="utf-8").read()
            with self.assertRaises(RecordError):
                save()
            self.assertEqual(open(full, encoding="utf-8").read(), before)

    def test_check_journal_names_a_broken_list(self):
        self.break_all()
        run = subprocess.run([sys.executable, os.path.join(HERE, "tools", "check_journal.py"),
                              self.root], capture_output=True, text=True)
        self.assertEqual(run.returncode, 1)
        for name in ("settings", "vocabulary", "pairs"):
            self.assertIn(f"CANNOT READ journal/{name}.md", run.stdout)


class KeysTest(unittest.TestCase):
    def test_a_newline_at_the_end_of_a_key_is_refused(self):
        self.assertEqual(stats.grain_of("2026-09"), "month")
        self.assertIsNone(stats.grain_of("2026-09\n"))
        self.assertIsNone(_WEEK_ID.match("2026-W01\n"))

    def test_a_week_past_the_calendar_is_refused(self):
        with self.assertRaises(RecordError):
            Week(week="9999-W52").check()
        Week(week="9998-W52").check()


class FixesServerCase(unittest.TestCase):
    """The same fixes walked through the routes, on a journal of their own."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        store.save_account(cls.root, Account(id="broker", name="Broker",
                                             start_balance=10000))
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

    def get(self, path):
        with urllib.request.urlopen(self.url(path)) as r:
            return r.status, r.read().decode("utf-8")

    def post(self, path, fields):
        data = urllib.parse.urlencode(fields, doseq=True).encode("utf-8")
        with urllib.request.urlopen(urllib.request.Request(self.url(path), data=data)) as r:
            return r.status, r.geturl()

    def status(self, path, fields=None):
        """The code a route answers with, an error page included."""
        data = (None if fields is None
                else urllib.parse.urlencode(fields, doseq=True).encode("utf-8"))
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url(path), data=data)) as r:
                return r.status
        except urllib.error.HTTPError as e:
            e.close()
            return e.code

    def form_token(self, html):
        return re.search(r'name="token" value="([0-9a-f]{16})"', html).group(1)

    def new_trade_fields(self, html, **over):
        fields = {"token": self.form_token(html), "blocks": "1", "account": "broker",
                  "pair": "EURUSD", "direction": "long", "style": "swing",
                  "entry_tf": "H4", "risk": "1", "entry": "2026-08-12T10:00",
                  "idea_tf_1": "H4", "idea_text_1": "a plain idea"}
        fields.update(over)
        return fields

    def test_a_broken_settings_file_is_named_on_the_page(self):
        path = store.settings_file(self.root)
        write(path, "---\nstop_edge 1.3\n---\n")
        try:
            self.S.drop_cache()
            code, html = self.get("/")
            self.assertEqual(code, 200)
            self.assertIn('class="notice"', html)
            self.assertIn("<code>journal/settings.md</code>", html)
            self.assertEqual(self.get("/new")[0], 200)
            # the slider refuses to write over it, and the file stays
            self.assertEqual(self.status("/settings/stop-edge",
                                         {"stop_edge": "1.4", "back": "/"}), 400)
            self.assertEqual(open(path, encoding="utf-8").read(),
                             "---\nstop_edge 1.3\n---\n")
        finally:
            os.remove(path)
            self.S.drop_cache()

    def test_a_save_from_the_interface_keeps_what_was_written_by_hand(self):
        t = Trade(id="2026-08-03-01-gbpusd", account="broker", pair="GBPUSD",
                  direction="long", style="swing", risk=1.0,
                  opened=datetime(2026, 8, 3, 9, 0), opened_time=True,
                  idea=[IdeaBlock(tf="H4", text="idea")],
                  preamble="Written on the train.",
                  conclusions="keep\n## Lessons\nlost text")
        store.save_trade(self.root, t)
        self.S.drop_cache()
        self.post(f"/trade/{t.id}/breakeven", {})
        back = store.load_trade(self.root, t.id)
        self.assertIsNotNone(back.breakeven)
        self.assertEqual(back.preamble, "Written on the train.")
        self.assertEqual(back.conclusions, "keep\n## Lessons\nlost text")

    def test_a_renamed_trade_is_followed_by_its_notes_and_cards(self):
        _, html = self.get("/new")
        _, where = self.post("/new", self.new_trade_fields(html, entry="2026-08-20T10:00"))
        old = urllib.parse.unquote(urllib.parse.urlparse(where).path.rsplit("/", 1)[1])
        other = "2026-08-01-01-usdjpy"
        store.save_note(self.root, Note(id="sweep", title="Sweep",
                                        day=datetime(2026, 8, 21),
                                        trades=[other, old]))
        store.save_card(self.root, Card(day=datetime(2026, 8, 20),
                                        preamble="Written above, by hand.", assessment=[
            Graded(trade="EURUSD", grade="A", result="open", id=old)]))
        store.save_week(self.root, Week(week="2026-W34", assessment=[
            Graded(trade="EURUSD", grade="B", result="open", id=old)]))
        _, html = self.get(f"/edit/{old}")
        self.post(f"/edit/{old}", self.new_trade_fields(html, entry="2026-08-19T10:00"))
        new = "2026-08-19-01-eurusd"
        self.assertTrue(os.path.isdir(store.trade_dir(self.root, new)))
        self.assertEqual(store.load_note(self.root, "sweep").trades, [other, new])
        card = store.load_card(self.root, datetime(2026, 8, 20))
        self.assertEqual([r.id for r in card.assessment], [new])
        self.assertEqual(card.preamble, "Written above, by hand.")
        week = store.load_week(self.root, "2026-W34")
        self.assertEqual([r.id for r in week.assessment], [new])

    def test_a_risk_with_a_minus_is_refused(self):
        for text in ("-1", "−1", "-150$"):
            with self.assertRaises(self.S.RecordError, msg=text):
                self.S.parse_risk(text, 10000)
        before = len(store.all_trades(self.root))
        _, html = self.get("/new")
        self.assertEqual(self.status("/new", self.new_trade_fields(
            html, risk="-1", entry="2026-08-05T10:00")), 400)
        self.assertEqual(len(store.all_trades(self.root)), before)

    def test_a_period_with_a_newline_writes_no_report(self):
        self.assertEqual(self.status("/report/2026-09%0A", {"conclusions": ""}), 400)
        folder = os.path.join(self.root, store.JOURNAL, store.REPORTS)
        names = os.listdir(folder) if os.path.isdir(folder) else []
        self.assertEqual([n for n in names if "\n" in n], [])

    def test_a_week_past_the_calendar_answers_with_a_page(self):
        self.assertEqual(self.status("/week/9999-W52"), 404)
        self.assertEqual(self.status("/week/save", {"week": "9999-W52"}), 400)


if __name__ == "__main__":
    unittest.main()
