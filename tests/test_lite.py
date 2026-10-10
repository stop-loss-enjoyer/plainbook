#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plainbook Lite, the reduced edition: the nav, the hidden addresses, and the
switch that takes the key in and out of settings.md. Its own journal, so the
shared story of test_server.py stays the full Plainbook."""
import difflib
import hashlib
import importlib
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime

TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TESTS))
sys.path.insert(0, TESTS)

from formpost import form_fields
from plainbook import store
from plainbook.model import (Account, Card, Graded, IdeaBlock, Note, Plan, Playbook,
                             Rule, Setup, Trade)

SETTINGS = "---\nclock: Europe/Prague\nstop_edge: 1.4\n---\n\nBy hand, kept.\n"


class LiteBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        store.save_account(cls.root, Account(id="broker", name="Broker",
                                             start_balance=10000))
        with open(store.settings_file(cls.root), "w", encoding="utf-8") as f:
            f.write(SETTINGS)
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
        self.write_settings(SETTINGS)

    def write_settings(self, text):
        with open(store.settings_file(self.root), "w", encoding="utf-8") as f:
            f.write(text)
        self.S.drop_cache()

    def settings(self):
        with open(store.settings_file(self.root), encoding="utf-8") as f:
            return f.read()

    def lite_on(self):
        self.post("/settings/edition", {"lite": "1"})

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
            return r.read().decode("utf-8")

    def post(self, path, fields):
        data = urllib.parse.urlencode(fields, doseq=True).encode("utf-8")
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data)
        with urllib.request.urlopen(req) as r:
            return r.geturl(), r.read().decode("utf-8")

    @staticmethod
    def nav(html):
        return re.findall(r'<nav>(.*?)</nav>', html, re.S)[0]


class LiteCase(LiteBase):
    def test_the_full_journal_is_the_default(self):
        html = self.get("/")
        self.assertEqual(len(re.findall(r"<a ", self.nav(html))), 9)
        self.assertIn("<title>Plainbook</title>", html)
        # the header offers Lite, switched off
        self.assertIn('class="lite-switch"', html)
        self.assertIn('aria-checked="false"', html)
        self.assertEqual(self.S.tabs_asking(), {"playbooks"})

    def test_lite_shrinks_the_nav_and_names_itself(self):
        self.lite_on()
        html = self.get("/")
        names = re.findall(r">([^<]+)</a>", self.nav(html))
        self.assertEqual(names, ["Journal", "Statistics", "Accounts", "Search"])
        self.assertIn("<title>Plainbook Lite</title>", html)
        # the switch beside the name is lit and turns Lite off
        switch = re.findall(r'<form[^>]*class="lite-switch".*?</form>', html, re.S)[0]
        self.assertIn('aria-checked="true"', switch)
        self.assertIn('name="lite" value=""', switch)
        # nothing waits in a tab that is not there
        self.assertEqual(self.S.tabs_asking(), set())

    def test_the_header_switch_leaves_the_reader_where_they_were(self):
        url, _ = self.post("/settings/edition", {"lite": "1", "back": "/stats?x=1"})
        self.assertEqual(urllib.parse.urlparse(url).path, "/stats")
        self.assertIn("edition: lite", self.settings())
        url, _ = self.post("/settings/edition", {"lite": "", "back": "/stats"})
        self.assertEqual(urllib.parse.urlparse(url).path, "/stats")
        self.assertNotIn("edition", self.settings())

    def test_the_header_switch_does_not_land_on_a_page_lite_turns_off(self):
        url, _ = self.post("/settings/edition", {"lite": "1", "back": "/playbooks"})
        self.assertEqual(urllib.parse.urlparse(url).path, "/")
        # and never leaves the journal for another site
        url, _ = self.post("/settings/edition", {"lite": "", "back": "//example.com/"})
        self.assertEqual(urllib.parse.urlparse(url).netloc, f"127.0.0.1:{self.port}")
        self.assertEqual(urllib.parse.urlparse(url).path, "/")

    def test_the_header_switch_refuses_a_backslash_host_as_the_other_switches_do(self):
        for back in ("/\\example.com/x", "/\\\\example.com/"):
            url, _ = self.post("/settings/edition", {"lite": "1", "back": back})
            parts = urllib.parse.urlparse(url)
            self.assertEqual(parts.netloc, f"127.0.0.1:{self.port}", back)
            self.assertEqual(parts.path, "/", back)

    def test_the_header_switch_names_an_unreadable_settings_file_on_accounts(self):
        self.write_settings("---\nstop_edge 1.3\n---\n")
        url, html = self.post("/settings/edition", {"lite": "1", "back": "/stats"})
        parts = urllib.parse.urlparse(url)
        self.assertEqual(parts.path, "/accounts")
        self.assertIn("bad=1", parts.query)
        self.assertIn('class="notice', html)
        self.assertEqual(self.settings(), "---\nstop_edge 1.3\n---\n")

    def test_every_visible_header_link_answers(self):
        self.lite_on()
        for href in re.findall(r'<a href="([^"]+)"', self.nav(self.get("/"))):
            self.assertEqual(self.get(href).count("Turned off in Plainbook Lite"), 0, href)

    def test_a_hidden_address_answers_the_short_page(self):
        self.lite_on()
        for prefix in self.S.LITE_HIDDEN_ROUTES:
            path = prefix + ("x" if prefix.endswith("/") else "")
            html = self.get(path)
            self.assertIn("Turned off in Plainbook Lite", html, path)
            self.assertIn('href="/accounts#edition"', html, path)

    def test_a_hidden_save_goes_through_and_lands_on_the_short_page(self):
        self.lite_on()
        url, html = self.post("/note/new", {
            "token": self.S.new_token(), "date": "2026-09-01", "title": "Pasted",
            "blocks": "1", "idea_text_1": "kept for later"})
        self.assertTrue(url.split("?")[0].endswith("/turned-off"), url)
        self.assertIn("Turned off in Plainbook Lite", html)
        self.assertEqual([n.title for n in store.all_notes(self.root, [])], ["Pasted"])
        # and it is the owner's again as soon as the switch is off
        self.post("/settings/edition", {})
        self.assertIn("Pasted", self.get("/notes"))

    def test_the_switch_round_trip_changes_nothing_but_its_key(self):
        self.lite_on()
        self.assertEqual(store.edition(self.root), "lite")
        self.assertIn("edition: lite", self.settings())
        self.assertIn("clock: Europe/Prague", self.settings())
        self.post("/settings/edition", {})
        self.assertEqual(store.edition(self.root), "")
        self.assertEqual(self.settings(), SETTINGS)
        # the key is taken out, never written empty (invariant 3)
        self.assertNotIn("edition", self.settings())

    def test_the_switch_card_shows_the_state(self):
        off = self.get("/accounts")
        self.assertIn('id="edition"', off)
        self.assertNotRegex(off, r'name="lite" value="1"\s+checked')
        self.lite_on()
        on = self.get("/accounts")
        self.assertRegex(on, r'name="lite" value="1"\s+checked')
        self.assertIn('action="/settings/edition"', on)


class LiteHides(LiteBase):
    """What Lite leaves out of the pages it shows, and what it leaves alone."""
    TRADE = "2026-08-29-01-eurusd"
    OPEN = "2026-08-29-02-eurusd"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        r = cls.root
        store.save_plan(r, Plan(id="2026-08-28-eurusd", title="Range break",
                                pair="EURUSD", day=date(2026, 8, 28)))
        store.save_playbook(r, Playbook(
            id="pull", name="Pullback", styles=["swing"], version="1.0",
            setups=[Setup(name="A", rules=[Rule(1, "Level on D1"),
                                           Rule(2, "Target 2R away")])],
            management=[Rule(3, "Stop never moved")]))
        for trade_id, closed in ((cls.TRADE, True), (cls.OPEN, False)):
            fields = dict(
                id=trade_id, account="broker", pair="EURUSD", direction="long",
                style="swing", entry_tf="H4", execution=["limit"], risk=1.0,
                opened=datetime(2026, 8, 29, 14, 30), opened_time=True,
                plan="2026-08-28-eurusd", playbook="pull", playbook_version="1.0",
                setup="A", deviations=[2], reasons={2: "took it anyway"},
                note="seen on the weekly first", preamble="written by hand",
                extra={"custom": "kept"},
                idea=[IdeaBlock(tf="H4", text="the pullback")])
            if closed:
                fields.update(result="Lose", pnl=-250.0, closed=date(2026, 8, 30),
                              exit_deviations=[], conclusions="late")
            store.save_trade(r, Trade(**fields))
        store.save_note(r, Note(id="2026-09-01-levels", title="Levels kept",
                                day=date(2026, 9, 1), trades=[cls.TRADE]))
        store.save_card(r, Card(day=date(2026, 8, 30), assessment=[
            Graded(trade="EURUSD", id=cls.TRADE)]))

    def setUp(self):
        super().setUp()
        self.S.drop_cache()

    def lite_off(self):
        self.post("/settings/edition", {})

    def form(self, path):
        return form_fields(self.get(path), path)

    def tree(self, trade_id):
        folder = store.trade_dir(self.root, trade_id)
        out = {}
        for top, _, files in os.walk(folder):
            for name in files:
                with open(os.path.join(top, name), "rb") as f:
                    out[os.path.relpath(os.path.join(top, name), folder)] = f.read()
        return out

    def both(self, path):
        """The page in the full journal, then in Lite."""
        self.lite_off()
        full = self.get(path)
        self.lite_on()
        return full, self.get(path)

    def test_the_front_page_loses_only_the_header_buttons(self):
        full, lite = self.both("/")
        for href in ('href="/plan/new"', 'href="/card/', 'href="/week/'):
            self.assertIn(href, full)
            self.assertNotIn(href, lite)
        self.assertIn('href="/new"', lite)
        self.assertIn('href="/export.csv', lite)

    def test_the_trade_page_names_no_plan_playbook_checklist_or_note(self):
        path = f"/trade/{self.TRADE}"
        full, lite = self.both(path)
        for marker in ('href="/plan/', 'href="/playbook/', 'href="/note/',
                       "<h2>Checklist</h2>"):
            self.assertIn(marker, full)
            self.assertNotIn(marker, lite)
        # the free line of the trade is the trader's own and stays
        self.assertIn("seen on the weekly first", lite)

    def test_no_way_back_to_a_report_or_a_note_that_is_turned_off(self):
        full, lite = self.both(f"/trade/{self.TRADE}?note=2026-09-01-levels")
        self.assertIn('class="btn" href="/note/', full)
        self.assertNotIn('class="btn" href="/note/', lite)
        full, lite = self.both(f"/trade/{self.TRADE}?report=2026-08")
        self.assertNotIn('class="btn" href="/report/', lite)

    def test_the_trade_form_draws_no_plan_playbook_or_checklist(self):
        for path in (f"/edit/{self.TRADE}", f"/edit/{self.OPEN}", "/new"):
            full, lite = self.both(path)
            for marker in ('name="plan"', 'name="playbook"', 'id="checklist-card"',
                           'name="ticked"', "function show_playbook"):
                self.assertNotIn(marker, lite, path)
            if path != "/new":
                self.assertIn('name="playbook"', full)
        full, lite = self.both(f"/edit/{self.TRADE}")
        self.assertIn('id="exit-checklist"', full)
        self.assertNotIn('id="exit-checklist"', lite)
        self.assertNotIn('name="ticked_exit"', lite)

    def test_the_close_form_draws_no_management_rules(self):
        full, lite = self.both(f"/close/{self.OPEN}")
        self.assertIn('id="exit-checklist"', full)
        self.assertNotIn('id="exit-checklist"', lite)
        self.assertNotIn("ticked_exit", lite)

    def test_a_save_in_lite_leaves_every_byte_of_what_it_does_not_show(self):
        self.lite_on()
        for trade_id in (self.TRADE, self.OPEN):
            before = self.tree(trade_id)
            self.post(f"/edit/{trade_id}", self.form(f"/edit/{trade_id}"))
            self.assertEqual(self.tree(trade_id), before)
        fields = dict(self.form(f"/close/{self.OPEN}"), result="Win", pnl="150",
                      exit="2026-08-30T10:00")
        self.post(f"/close/{self.OPEN}", fields)
        t = store.load_trade(self.root, self.OPEN)
        self.assertEqual(t.result, "Win")
        # nothing was ticked, so nothing is written as "every rule not held"
        self.assertIsNone(t.exit_deviations)
        self.assertEqual((t.plan, t.playbook, t.setup, t.deviations, t.reasons),
                         ("2026-08-28-eurusd", "pull", "A", [2],
                          {2: "took it anyway"}))

    def test_statistics_loses_the_rule_cards_and_the_wording_about_ticking(self):
        # a playbook that does not read is a banner in the full journal
        bad = store.playbook_dir(self.root, "torn")
        os.makedirs(bad, exist_ok=True)
        with open(os.path.join(bad, store.PLAYBOOK_FILE), "w", encoding="utf-8") as f:
            f.write("---\nlimits: [broken\n---\n")
        try:
            full, lite = self.both("/stats")
        finally:
            shutil.rmtree(bad)
            self.S.drop_cache()
        for heading in ("<h2>By playbook</h2>", "<h2>What a rule costs</h2>"):
            self.assertIn(heading, full)
            self.assertNotIn(heading, lite)
        self.assertIn("broke a rule", full)
        for words in ("broke a rule", "not ticked", "checklist ticked"):
            self.assertNotIn(words, lite)
        self.assertNotIn("torn", lite)
        self.assertIn("<h2>Past the stop</h2>", lite)

    def test_the_mistakes_tile_without_rules_counts_the_stop_alone(self):
        d = self.S.reports.discipline(self.root, self.S.journal(), self.S.journal().trades,
                                      [], playbooks=[], rules=False)
        self.assertEqual((d.ticked, d.unticked, d.rules), (0, 0, []))
        tile = self.S.mistakes_tile(d, self.S.stats.summary(self.S.journal(), []),
                                    rules=False)
        self.assertIn('class="tile', tile)
        self.assertNotIn("rule", tile)

    def test_search_looks_through_trades_only(self):
        full, lite = self.both("/search?q=Range")
        self.assertIn('<td class="muted">plan</td>', full)
        self.assertNotIn('<td class="muted">plan</td>', lite)
        full, lite = self.both("/search?q=Levels")
        self.assertIn('<td class="muted">note</td>', full)
        self.assertNotIn('<td class="muted">note</td>', lite)
        full, lite = self.both("/search?q=anyway")
        self.assertIn(self.TRADE, full)
        self.assertNotIn(self.TRADE, lite)
        found = self.get("/search?q=pullback")
        self.assertIn(f'href="/trade/{self.TRADE}"', found)
        self.assertNotIn("plan, note, playbook", self.get("/search"))

    def test_a_shared_trade_carries_no_checklist_plan_or_setup(self):
        for path in (f"/share/trade/{self.TRADE}", "/share/journal"):
            full, lite = self.both(path)
            self.assertIn("<h2>Checklist</h2>", full, path)
            self.assertIn('<td class="dim">plan</td>', full, path)
            for marker in ("<h2>Checklist</h2>", '<td class="dim">plan</td>',
                           '<td class="dim">setup</td>'):
                self.assertNotIn(marker, lite, path)
            self.assertIn("EURUSD", lite)

    def test_the_csv_keeps_every_column(self):
        full, lite = self.both("/export.csv")
        self.assertEqual(full, lite)
        self.assertIn("playbook", lite.splitlines()[0])

    def test_the_trash_of_lite_lists_three_kinds_and_restores_those(self):
        store.delete_plan(self.root, "2026-08-28-eurusd")
        try:
            self.S.drop_cache()
            full, lite = self.both("/accounts")
            self.assertIn('<td class="muted">plan</td>', full)
            self.assertNotIn('<td class="muted">plan</td>', lite)
            name = next(x[0] for x in store.trash_list(self.root) if x[1] == "plan")
            self.post("/trash/restore", {"name": name})
            self.assertIn(name, [x[0] for x in store.trash_list(self.root)])
            self.lite_off()
            self.post("/trash/restore", {"name": name})
            self.assertFalse([x for x in store.trash_list(self.root) if x[1] == "plan"])
        finally:
            self.lite_off()

    def test_the_trash_of_lite_says_what_waits_for_the_full_journal(self):
        store.delete_plan(self.root, "2026-08-28-eurusd")
        name = next(x[0] for x in store.trash_list(self.root) if x[1] == "plan")
        try:
            self.S.drop_cache()
            full, lite = self.both("/accounts")
            self.assertNotIn("Nothing has been deleted", lite)
            self.assertIn("1 more record of the full Plainbook", lite)
            self.assertNotIn("more record", full)
        finally:
            store.restore(self.root, name)
            self.lite_off()
        self.lite_on()
        try:
            self.assertIn("Nothing has been deleted", self.get("/accounts"))
        finally:
            self.lite_off()

    def test_the_short_page_leads_home_once_lite_is_off(self):
        self.lite_on()
        self.assertIn("Turned off in Plainbook Lite", self.get("/turned-off"))
        self.lite_off()
        with urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/turned-off?said=Plan+saved") as req:
            self.assertEqual(urllib.parse.urlparse(req.geturl()).path, "/")
            self.assertIn("Plan saved", req.read().decode("utf-8"))

    def test_a_missing_hidden_record_in_lite_leads_back_to_the_journal(self):
        self.lite_on()
        try:
            url, html = self.post("/card/2020-01-01/delete",
                                  {"token": self.S.new_token()})
        except urllib.error.HTTPError as e:
            with e:
                html = e.read().decode("utf-8")
        finally:
            self.lite_off()
        self.assertIn('<a href="/">Back</a>', html)
        self.assertNotIn('href="/cards"', html)
        self.assertEqual(self.S.broken_record([("x", "y")], "cards", "/cards")
                         .count('href="/cards">Back'), 1)

    def test_the_switch_is_announced_as_a_switch(self):
        self.assertIn('role="switch"', self.get("/accounts"))

    def test_the_accounts_captions_do_not_mention_reports(self):
        full, lite = self.both("/accounts")
        self.assertIn("the statistics and the reports", full)
        self.assertNotIn("and the reports", lite)

    def test_a_delete_in_lite_says_what_the_full_journal_still_names(self):
        full, lite = self.both(f"/trade/{self.TRADE}")
        self.assertNotIn("kept for the full journal", full)
        self.assertIn("also named in 1 note and 1 card kept for the full journal", lite)
        lone = self.get(f"/trade/{self.OPEN}")
        self.assertNotIn("kept for the full journal", lone)
        # a count of nothing is not said
        store.save_card(self.root, Card(day=date(2026, 8, 30), assessment=[]))
        try:
            self.S.drop_cache()
            self.lite_on()
            html = self.get(f"/trade/{self.TRADE}")
            self.assertIn("also named in 1 note kept for the full journal", html)
            self.assertNotIn("0 cards", html)
        finally:
            store.save_card(self.root, Card(day=date(2026, 8, 30), assessment=[
                Graded(trade="EURUSD", id=self.TRADE)]))
            self.S.drop_cache()

    def test_a_note_saved_in_the_full_journal_keeps_a_trade_in_the_trash(self):
        self.lite_off()
        store.delete_trade(self.root, self.TRADE)
        try:
            self.S.drop_cache()
            path = "/note/2026-09-01-levels/edit"
            fields = self.form(path)
            self.assertEqual(fields.get("trade"), [self.TRADE])
            self.post(path, fields)
            self.assertEqual(store.load_note(self.root, "2026-09-01-levels").trades,
                             [self.TRADE])
        finally:
            name = next(x[0] for x in store.trash_list(self.root) if x[2] == self.TRADE)
            store.restore(self.root, name)
            self.S.drop_cache()

    def test_a_renamed_trade_is_followed_in_lite_as_well(self):
        self.lite_on()
        store.retarget_trade(self.root, self.TRADE, "2026-08-29-09-eurusd")
        try:
            self.assertEqual(store.load_note(self.root, "2026-09-01-levels").trades,
                             ["2026-08-29-09-eurusd"])
        finally:
            store.retarget_trade(self.root, "2026-08-29-09-eurusd", self.TRADE)

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6360000002000100ffff0300000600"
    "05572bd6a20000000049454e44ae426082")


class LiteRoundTrip(LiteBase):
    """A trade of the full journal taken through Lite and back: saved, closed,
    moved to breakeven, renamed, deleted and restored, the switch flipped.
    "Nothing lost" is read off the disk, every file of the journal and of the
    trash by its hash, and the forms are posted as the page draws them."""
    NOTE = "2026-09-01-levels"
    DAY = date(2026, 8, 30)

    def setUp(self):
        # a journal of its own for every case, so a hash compares one story
        for name in (store.JOURNAL, store.TRASH):
            shutil.rmtree(os.path.join(self.root, name), ignore_errors=True)
        store.make_layout(self.root)
        store.save_account(self.root, Account(id="broker", name="Broker",
                                              start_balance=10000))
        store.save_playbook(self.root, Playbook(
            id="pull", name="Pullback", styles=["swing"], version="1.0",
            setups=[Setup(name="A", rules=[Rule(1, "Level on D1"),
                                           Rule(2, "Target 2R away")])],
            management=[Rule(3, "Stop never moved"), Rule(4, "Held to target")]))
        store.save_plan(self.root, Plan(id="2026-08-28-eurusd", title="Range break",
                                        pair="EURUSD", day=date(2026, 8, 28)))
        super().setUp()

    # --- the journal ---
    def trade(self, trade_id, closed=True, playbook="pull"):
        """A trade with everything Lite does not draw: a plan, a playbook
        ticked at the entry with every rule met and at the close, reasons,
        the free line of the header, a picture in every zone, and a note and
        a daily card that name it."""
        folder = store.trade_dir(self.root, trade_id)
        os.makedirs(os.path.join(folder, store.SHOTS), exist_ok=True)
        names = ["idea-01-01.png", "idea-01-02.png", "idea-02-01.png", "update-01.png"]
        if closed:
            names += ["exit-01.png", "conclusions-01.png"]
        for i, name in enumerate(names):
            with open(os.path.join(folder, store.SHOTS, name), "wb") as f:
                f.write(PNG + bytes([i]))
        shot = store.record_path
        fields = dict(
            id=trade_id, account="broker", pair="EURUSD", direction="long",
            style="swing", entry_tf="H4", execution=["limit"], risk=1.0,
            opened=datetime(2026, 8, 29, 14, 30), opened_time=True,
            plan="2026-08-28-eurusd", playbook=playbook, playbook_version="1.0",
            setup="A", deviations=[], entry_price=1.1, stop_price=1.09,
            target_price=1.12, note="seen on the weekly first",
            preamble="written above by hand", extra={"custom": "kept"},
            idea=[IdeaBlock(tf="H4", text="the pullback",
                            images=[shot("idea-01-01.png"), shot("idea-01-02.png")]),
                  IdeaBlock(tf="H1", text="the trigger", images=[shot("idea-02-01.png")])],
            updates=f"**29.08.2026 18:00**: stop under the low\n\n"
                    f"![]({shot('update-01.png')})")
        if closed:
            fields.update(
                result="Win", pnl=200.0, closed=self.DAY, exit_price=1.12,
                exit_deviations=[4], reasons={4: "cut early"},
                exit_images=[shot("exit-01.png")], exit_text="trailed by hand",
                conclusions=f"patience paid\n\n![]({shot('conclusions-01.png')})")
        store.save_trade(self.root, Trade(**fields))
        store.save_note(self.root, Note(id=self.NOTE, title="Levels kept",
                                        day=date(2026, 9, 1), trades=[trade_id]))
        store.save_card(self.root, Card(day=self.DAY, focus="patience", assessment=[
            Graded(trade="EURUSD", grade="A", id=trade_id)]))
        self.S.drop_cache()
        return trade_id

    def snapshot(self):
        """Every file of the journal and of the trash, by its path and hash."""
        out = {}
        for name in (store.JOURNAL, store.TRASH):
            base = os.path.join(self.root, name)
            for top, _, files in os.walk(base):
                for f in files:
                    path = os.path.join(top, f)
                    with open(path, "rb") as fh:
                        out[os.path.relpath(path, self.root)] = (
                            hashlib.sha256(fh.read()).hexdigest())
        return out

    def changed(self, before, after):
        return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))

    def text(self, rel):
        with open(os.path.join(self.root, rel), encoding="utf-8") as f:
            return f.read()

    def lines_diff(self, old, new):
        """(removed, added) lines between two texts."""
        removed, added = [], []
        for line in difflib.ndiff(old.splitlines(), new.splitlines()):
            if line.startswith("- "):
                removed.append(line[2:])
            elif line.startswith("+ "):
                added.append(line[2:])
        return removed, added

    def form(self, path, action=None):
        return form_fields(self.get(path), action or path)

    def trade_md(self, trade_id):
        return os.path.relpath(os.path.join(store.trade_dir(self.root, trade_id),
                                            store.TRADE_FILE), self.root)

    def edit_as_drawn(self, trade_id, **change):
        self.post(f"/edit/{trade_id}", dict(self.form(f"/edit/{trade_id}"), **change))

    # --- A: a save that changes nothing changes nothing ---
    def test_a_lite_edit_with_no_change_leaves_the_whole_tree(self):
        for closed in (True, False):
            with self.subTest(closed=closed):
                self.setUp()
                trade_id = self.trade("2026-08-29-01-eurusd", closed)
                self.lite_on()
                before = self.snapshot()
                fields = self.form(f"/edit/{trade_id}")
                for key in ("plan", "playbook", "ticked", "ticked_exit"):
                    self.assertNotIn(key, fields)
                self.post(f"/edit/{trade_id}", fields)
                self.assertEqual(self.changed(before, self.snapshot()), [])

    def test_the_full_edit_with_no_change_leaves_the_whole_tree(self):
        for closed in (True, False):
            with self.subTest(closed=closed):
                self.setUp()
                trade_id = self.trade("2026-08-29-01-eurusd", closed)
                before = self.snapshot()
                fields = self.form(f"/edit/{trade_id}")
                for key in ("plan", "playbook", "ticked"):
                    self.assertIn(key, fields)
                self.post(f"/edit/{trade_id}", fields)
                self.assertEqual(self.changed(before, self.snapshot()), [])

    # --- B: one field changed is one line changed ---
    def test_a_lite_edit_of_the_risk_changes_that_line_alone(self):
        trade_id = self.trade("2026-08-29-01-eurusd")
        self.lite_on()
        before, md = self.snapshot(), self.text(self.trade_md(trade_id))
        self.edit_as_drawn(trade_id, risk="0.5")
        self.assertEqual(self.changed(before, self.snapshot()), [self.trade_md(trade_id)])
        self.assertEqual(self.lines_diff(md, self.text(self.trade_md(trade_id))),
                         (["risk %: 1"], ["risk %: 0.5"]))

    # --- C: a close in Lite ticks nothing ---
    def test_a_lite_close_leaves_the_entry_ticks_and_every_picture(self):
        trade_id = self.trade("2026-08-29-01-eurusd", closed=False)
        self.lite_on()
        before = self.snapshot()
        fields = self.form(f"/close/{trade_id}")
        self.assertNotIn("ticked_exit", fields)
        self.post(f"/close/{trade_id}", dict(fields, result="Win", pnl="150",
                                             exit="2026-08-30T10:00"))
        t = store.load_trade(self.root, trade_id)
        self.assertEqual(t.result, "Win")
        self.assertIsNone(t.exit_deviations)
        self.assertEqual((t.plan, t.playbook, t.playbook_version, t.setup,
                          t.deviations, t.reasons, t.note, t.extra),
                         ("2026-08-28-eurusd", "pull", "1.0", "A", [], {},
                          "seen on the weekly first", {"custom": "kept"}))
        # the close writes the trade file and nothing else: the pictures of
        # the idea and of the updates keep their names and their bytes
        self.assertEqual(self.changed(before, self.snapshot()), [self.trade_md(trade_id)])

    # --- D: a rename in Lite is followed by the note and the card ---
    def test_a_lite_rename_retargets_the_note_and_the_card_and_loses_nothing(self):
        old = self.trade("2026-08-29-01-eurusd")
        self.lite_on()
        before = self.snapshot()
        md = self.text(self.trade_md(old))
        note_md = self.text(os.path.relpath(os.path.join(
            store.note_dir(self.root, self.NOTE), store.NOTE_FILE), self.root))
        card_md = self.text(os.path.relpath(store.card_path(self.root, self.DAY), self.root))
        self.edit_as_drawn(old, pair="GBPUSD")
        new = "2026-08-29-01-gbpusd"
        self.assertTrue(os.path.isdir(store.trade_dir(self.root, new)))
        self.assertFalse(os.path.exists(store.trade_dir(self.root, old)))
        after = self.snapshot()
        old_dir = os.path.relpath(store.trade_dir(self.root, old), self.root)
        new_dir = os.path.relpath(store.trade_dir(self.root, new), self.root)
        moved = {k.replace(new_dir, old_dir, 1): v for k, v in after.items()}
        note_rel = os.path.relpath(os.path.join(store.note_dir(self.root, self.NOTE),
                                                store.NOTE_FILE), self.root)
        card_rel = os.path.relpath(store.card_path(self.root, self.DAY), self.root)
        self.assertEqual(self.changed(before, moved),
                         sorted([self.trade_md(old), note_rel, card_rel]))
        self.assertEqual(self.lines_diff(md, self.text(self.trade_md(new))),
                         ([f"id: {old}", "pair: EURUSD"], [f"id: {new}", "pair: GBPUSD"]))
        removed, added = self.lines_diff(note_md, self.text(note_rel))
        self.assertEqual((removed, added), ([l for l in note_md.splitlines() if old in l],
                                            [l.replace(old, new) for l in note_md.splitlines()
                                             if old in l]))
        removed, added = self.lines_diff(card_md, self.text(card_rel))
        self.assertEqual(added, [l.replace(old, new) for l in removed])
        self.assertTrue(removed)
        self.assertEqual(store.load_note(self.root, self.NOTE).trades, [new])
        self.assertEqual([(g.trade, g.id) for g in
                          store.load_card(self.root, self.DAY).assessment],
                         [("EURUSD", new)])

    # --- E: the switch touches its own file only ---
    def test_lite_full_lite_changes_the_settings_alone(self):
        self.trade("2026-08-29-01-eurusd")
        before = self.snapshot()
        settings = os.path.relpath(store.settings_file(self.root), self.root)
        self.lite_on()
        self.assertEqual(self.changed(before, self.snapshot()), [settings])
        self.post("/settings/edition", {})
        self.assertEqual(self.changed(before, self.snapshot()), [])
        self.lite_on()
        self.assertEqual(self.changed(before, self.snapshot()), [settings])

    # --- F: breakeven and an update from Lite ---
    def test_breakeven_and_an_update_in_lite_only_add(self):
        trade_id = self.trade("2026-08-29-01-eurusd", closed=False)
        self.lite_on()
        md_rel = self.trade_md(trade_id)
        before, md = self.snapshot(), self.text(md_rel)
        page = self.get(f"/trade/{trade_id}")
        self.post(f"/trade/{trade_id}/breakeven",
                  form_fields(page, f"/trade/{trade_id}/breakeven"))
        self.assertEqual(self.changed(before, self.snapshot()), [md_rel])
        removed, added = self.lines_diff(md, self.text(md_rel))
        self.assertEqual(removed, [])
        self.assertEqual(len(added), 1)
        self.assertTrue(added[0].startswith("stop at breakeven: "), added)
        md = self.text(md_rel)
        page = self.get(f"/trade/{trade_id}")
        fields = form_fields(page, f"/trade/{trade_id}/update")
        self.post(f"/trade/{trade_id}/update", dict(fields, update="partial taken"))
        self.assertEqual(self.changed(before, self.snapshot()), [md_rel])
        removed, added = self.lines_diff(md, self.text(md_rel))
        self.assertEqual(removed, [])
        self.assertTrue(added and added[-1].endswith("**: partial taken"), added)
        t = store.load_trade(self.root, trade_id)
        self.assertEqual((t.plan, t.playbook, t.setup, t.deviations, t.exit_deviations,
                          t.reasons, t.extra),
                         ("2026-08-28-eurusd", "pull", "A", [], None, {},
                          {"custom": "kept"}))

    # --- G: delete and restore in Lite ---
    def test_a_trade_deleted_and_restored_in_lite_comes_back_whole(self):
        trade_id = self.trade("2026-08-29-01-eurusd")
        self.lite_on()
        before = self.snapshot()
        page = self.get(f"/trade/{trade_id}")
        self.post(f"/trade/{trade_id}/delete",
                  form_fields(page, f"/trade/{trade_id}/delete"))
        self.assertFalse(os.path.exists(store.trade_dir(self.root, trade_id)))
        # the note and the card are not touched by the delete
        self.assertEqual(store.load_note(self.root, self.NOTE).trades, [trade_id])
        name = next(x[0] for x in store.trash_list(self.root) if x[2] == trade_id)
        self.assertIn(name, self.get("/accounts"))
        self.post("/trash/restore", {"name": name})
        self.assertEqual(self.changed(before, self.snapshot()), [])
        self.S.drop_cache()
        self.post("/settings/edition", {})
        self.assertIn(f'href="/trade/{trade_id}', self.get(f"/note/{self.NOTE}"))
        # the card's line reads its result off the trade again
        self.assertIn("Win +2.00 R", self.get(f"/card/{self.DAY:%Y-%m-%d}"))

    def test_a_new_trade_in_lite_does_not_take_the_id_of_one_in_the_trash(self):
        trade_id = self.trade("2026-08-29-01-eurusd")
        self.lite_on()
        page = self.get(f"/trade/{trade_id}")
        self.post(f"/trade/{trade_id}/delete",
                  form_fields(page, f"/trade/{trade_id}/delete"))
        self.assertEqual(self.S.store.new_id(self.root, datetime(2026, 8, 29), "EURUSD"),
                         "2026-08-29-02-eurusd")
        name = next(x[0] for x in store.trash_list(self.root) if x[2] == trade_id)
        self.post("/trash/restore", {"name": name})
        self.assertTrue(os.path.isdir(store.trade_dir(self.root, trade_id)))

    # --- H: the version the trade was ticked against is gone ---
    def test_a_lite_edit_keeps_the_close_ticks_of_a_lost_version(self):
        store.save_playbook(self.root, Playbook(
            id="lost", name="Lost", styles=["swing"], version="1.0",
            setups=[Setup(name="A", rules=[Rule(1, "One"), Rule(2, "Two")])],
            management=[Rule(3, "Three"), Rule(4, "Four")]))
        trade_id = self.trade("2026-08-29-01-eurusd", playbook="lost")
        # revised to rules with no management and no copy of 1.0 kept
        store.save_playbook(self.root, Playbook(
            id="lost", name="Lost", styles=["swing"], version="2.0",
            setups=[Setup(name="A", rules=[Rule(1, "One")])]))
        self.assertEqual(store.playbook_versions(self.root, "lost"), [])
        self.S.drop_cache()
        self.lite_on()
        before = self.snapshot()
        self.edit_as_drawn(trade_id)
        self.assertEqual(self.changed(before, self.snapshot()), [])
        t = store.load_trade(self.root, trade_id)
        self.assertEqual((t.playbook_version, t.deviations, t.exit_deviations, t.reasons),
                         ("1.0", [], [4], {4: "cut early"}))

    # --- I: a form of the full journal sent while in Lite ---
    def test_a_card_and_a_plan_posted_in_lite_are_written(self):
        day = "2026-09-02"
        card = self.form(f"/card/{day}", "/card/save")
        card["focus"] = ["stayed flat"]
        plan = self.form("/plan/new")
        plan.update(title=["Late break"], pair=["GBPUSD"], **{"from": ["2026-09-02"]})
        self.lite_on()
        url, html = self.post("/card/save", card)
        self.assertTrue(url.split("?")[0].endswith("/turned-off"), url)
        self.assertEqual(store.load_card(self.root, date(2026, 9, 2)).focus, "stayed flat")
        url, html = self.post("/plan/new", plan)
        self.assertTrue(url.split("?")[0].endswith("/turned-off"), url)
        self.assertEqual([k.title for k in store.all_plans(self.root, [])
                          if k.pair == "GBPUSD"], ["Late break"])


class HeaderFormCase(unittest.TestCase):
    def test_a_page_script_never_takes_the_first_form(self):
        # every page opens with the form of the Lite switch in its header, so
        # a script reading the first form read the switch: the risk hint of
        # the trade form lost the balances and the last risks
        from plainbook import html, server
        bare = re.compile(r"querySelector\(['\"]form['\"]\)|document\.forms\[0\]")
        for module in (server, html):
            with open(module.__file__, encoding="utf-8") as f:
                self.assertIsNone(bare.search(f.read()), module.__name__)


if __name__ == "__main__":
    unittest.main()
