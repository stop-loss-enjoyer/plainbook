#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A field the form did not send is left as it is (invariant 14), on a
journal of its own: the trade form posted as the page draws it changes not a
byte, and a form without the plan, the playbook or the management list keeps
what the trade holds there."""
import hashlib
import importlib
import os
import re
import sys
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request
from datetime import date, datetime

TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TESTS))
sys.path.insert(0, TESTS)

from formpost import form_fields
from plainbook import store
from plainbook.model import IdeaBlock, Account, Plan, Playbook, Rule, Setup, Trade

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6360000002000100ffff0300000600"
    "05572bd6a20000000049454e44ae426082")

# what a form that draws no plan, no playbook and no checklist leaves out
_PLAYBOOK_FIELD = re.compile(r"^(setup|met|held|why)_")


def without_playbook(fields):
    return {k: v for k, v in fields.items()
            if k not in ("plan", "playbook", "ticked", "ticked_exit")
            and not _PLAYBOOK_FIELD.match(k)}


class FormsCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        store.save_account(cls.root, Account(id="broker", name="Broker",
                                             start_balance=10000))
        store.save_plan(cls.root, Plan(id="2026-08-28-eurusd", title="Range break",
                                       pair="EURUSD", day=date(2026, 8, 28)))
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
        # each test revises the playbooks as it needs, from the same start
        store.save_playbook(self.root, Playbook(
            id="pull", name="Pullback", styles=["swing"], version="1.0",
            setups=[Setup(name="A", rules=[Rule(1, "Level on D1"),
                                           Rule(2, "Target 2R away")])],
            management=[Rule(3, "Stop never moved"), Rule(4, "Held to target")]))
        store.save_playbook(self.root, Playbook(
            id="bare", name="Bare", styles=["swing"], version="1.0",
            setups=[Setup(rules=[Rule(1, "One")])]))
        self.S.drop_cache()

    # --- helpers ---
    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path):
        with urllib.request.urlopen(self.url(path)) as r:
            return r.read().decode("utf-8")

    def post(self, path, fields):
        data = urllib.parse.urlencode(fields, doseq=True).encode("utf-8")
        with urllib.request.urlopen(urllib.request.Request(self.url(path), data=data)) as r:
            return r.geturl()

    def form(self, path):
        return form_fields(self.get(path), path)

    def trade(self, trade_id, closed=True, **over):
        """A trade with everything a form can hold: a plan, a playbook ticked
        at the entry and at the close, reasons, and a picture in every zone."""
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
            plan="2026-08-28-eurusd", playbook="pull", playbook_version="1.0",
            setup="A", deviations=[2], reasons={2: "took it anyway"},
            entry_price=1.1, stop_price=1.09, target_price=1.12,
            # drawn by no form: a save must carry them through untouched
            note="seen on the weekly first", preamble="written above by hand",
            breakeven=datetime(2026, 8, 29, 20, 0), notion_id="abc123",
            extra={"custom": "kept"},
            idea=[IdeaBlock(tf="H4", text="the pullback",
                            images=[shot("idea-01-01.png"), shot("idea-01-02.png")]),
                  IdeaBlock(tf="H1", text="the trigger", images=[shot("idea-02-01.png")])],
            updates=f"**2026-08-29 18:00**: stop under the low\n\n"
                    f"![]({shot('update-01.png')})")
        if closed:
            fields.update(
                result="Win", pnl=200.0, closed=date(2026, 8, 30), exit_price=1.12,
                exit_deviations=[4], reasons={2: "took it anyway", 4: "cut early"},
                exit_images=[shot("exit-01.png")], exit_text="trailed by hand",
                conclusions=f"patience paid\n\n![]({shot('conclusions-01.png')})")
        fields.update(over)
        t = Trade(**fields)
        store.save_trade(self.root, t)
        self.S.drop_cache()
        return t

    def tree(self, trade_id):
        """Every file of the trade's folder, by its path and its bytes."""
        folder = store.trade_dir(self.root, trade_id)
        out = {}
        for top, _, files in os.walk(folder):
            for name in files:
                path = os.path.join(top, name)
                with open(path, "rb") as f:
                    out[os.path.relpath(path, folder)] = hashlib.sha256(f.read()).hexdigest()
        return out

    def load(self, trade_id):
        return store.load_trade(self.root, trade_id)

    # --- the form as drawn ---
    def test_a_trade_saved_as_drawn_changes_not_a_byte(self):
        for trade_id, closed in (("2026-08-29-01-eurusd", True),
                                 ("2026-08-29-02-eurusd", False)):
            with self.subTest(closed=closed):
                self.trade(trade_id, closed=closed)
                before = self.tree(trade_id)
                self.assertEqual(len(before), 7 if closed else 5)
                fields = self.form(f"/edit/{trade_id}")
                # the form draws every field this test is about
                for key in ("plan", "playbook", "ticked", "setup_pull", "have_idea-1",
                            "have_idea-2", "have_update"):
                    self.assertIn(key, fields)
                if closed:
                    for key in ("ticked_exit", "held_pull", "have_exit", "have_concl"):
                        self.assertIn(key, fields)
                self.post(f"/edit/{trade_id}", fields)
                self.assertEqual(self.tree(trade_id), before)

    # --- a key absent leaves the value, a key blank clears it ---
    def test_the_plan_is_kept_when_not_sent_and_cleared_when_blank(self):
        trade_id = "2026-08-29-03-eurusd"
        self.trade(trade_id)
        fields = self.form(f"/edit/{trade_id}")
        self.post(f"/edit/{trade_id}", {k: v for k, v in fields.items() if k != "plan"})
        self.assertEqual(self.load(trade_id).plan, "2026-08-28-eurusd")
        self.post(f"/edit/{trade_id}", dict(self.form(f"/edit/{trade_id}"), plan=""))
        self.assertEqual(self.load(trade_id).plan, "")

    def test_the_playbook_is_kept_when_not_sent_and_cleared_when_blank(self):
        trade_id = "2026-08-29-04-eurusd"
        was = self.trade(trade_id)
        before = self.tree(trade_id)
        fields = self.form(f"/edit/{trade_id}")
        self.post(f"/edit/{trade_id}",
                  {k: v for k, v in fields.items() if k not in ("playbook", "ticked_exit")})
        # the checklist fields still sent are read by nobody without the key
        self.assertEqual(self.tree(trade_id), before)
        self.post(f"/edit/{trade_id}", without_playbook(fields))
        t = self.load(trade_id)
        self.assertEqual((t.plan, t.playbook, t.playbook_version, t.setup, t.deviations,
                          t.exit_deviations, t.reasons),
                         (was.plan, was.playbook, was.playbook_version, was.setup,
                          was.deviations, was.exit_deviations, was.reasons))
        self.post(f"/edit/{trade_id}", dict(self.form(f"/edit/{trade_id}"), playbook=""))
        t = self.load(trade_id)
        self.assertEqual((t.playbook, t.playbook_version, t.setup, t.deviations,
                          t.exit_deviations, t.reasons), ("", "", "", None, None, {}))

    # --- where the management guard stands: both of these must hold ---
    def test_a_move_to_a_playbook_without_management_lets_the_close_ticks_go(self):
        trade_id = "2026-08-29-05-eurusd"
        self.trade(trade_id)
        fields = self.form(f"/edit/{trade_id}")
        self.post(f"/edit/{trade_id}", dict(fields, playbook="bare", ticked="1",
                                            met_bare=["1"]))
        t = self.load(trade_id)
        self.assertEqual((t.playbook, t.deviations, t.reasons), ("bare", [], {}))
        self.assertIsNone(t.exit_deviations)

    def test_a_form_without_the_list_keeps_the_close_ticks_of_a_lost_version(self):
        trade_id = "2026-08-29-06-eurusd"
        self.trade(trade_id)
        # revised with no management rules and no copy of 1.0 kept: the
        # trade's version falls back to a playbook that draws no list
        store.save_playbook(self.root, Playbook(
            id="pull", name="Pullback", styles=["swing"], version="2.0",
            setups=[Setup(name="A", rules=[Rule(1, "Level on D1")])]))
        self.assertEqual(store.playbook_versions(self.root, "pull"), [])
        self.S.drop_cache()
        fields = self.form(f"/edit/{trade_id}")
        self.assertNotIn("ticked_exit", fields)
        self.post(f"/edit/{trade_id}", without_playbook(fields))
        t = self.load(trade_id)
        self.assertEqual((t.playbook_version, t.deviations, t.exit_deviations, t.reasons),
                         ("1.0", [2], [4], {2: "took it anyway", 4: "cut early"}))

    def test_a_close_without_the_list_leaves_the_trade_not_ticked(self):
        trade_id = "2026-08-29-07-eurusd"
        self.trade(trade_id, closed=False)
        fields = self.form(f"/close/{trade_id}")
        self.assertIn("ticked_exit", fields)
        fields = dict(without_playbook(fields), result="Win", pnl="150",
                      exit="2026-08-30T10:00")
        self.post(f"/close/{trade_id}", fields)
        t = self.load(trade_id)
        self.assertEqual(t.result, "Win")
        # not "every management rule not held": nothing was ticked
        self.assertIsNone(t.exit_deviations)
        self.assertEqual((t.playbook_version, t.deviations, t.reasons),
                         ("1.0", [2], {2: "took it anyway"}))


if __name__ == "__main__":
    unittest.main()
