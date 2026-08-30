#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round trip: object -> file -> object -> file."""
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import mdfile, store
from plainbook.model import (Trade, Account, Adjustment, IdeaBlock, Card, RecordError,
                      PAIR_NOT_SET)


def sample_trade(**kw):
    t = Trade(
        id="2025-06-25-01-eurusd",
        account="bybit",
        pair="EURUSD",
        direction="long",
        style="swing",
        entry_tf="H4",
        execution=["M15", "M5"],
        risk=1.0,
        opened=datetime(2025, 6, 25, 14, 30),
        opened_time=True,
        result="Win",
        pnl=174.0,
        closed=datetime(2025, 6, 27),
        idea=[
            IdeaBlock(tf="H4", text="Range breakout, waiting for a retest.",
                      images=["shots/idea-01.png", "shots/idea-02.png"]),
            IdeaBlock(tf="M15", text="Entry on confirmation.", images=[]),
        ],
        exit_images=["shots/exit-01.png"],
        conclusions="Held to target. Did not move the stop — right call.",
    )
    for k, v in kw.items():
        setattr(t, k, v)
    return t


class FileHeader(unittest.TestCase):
    def test_round_trip(self):
        head = {"account": "bybit", "risk %": "1", "execution": ["M15", "M5"]}
        text = mdfile.dump(head, "body")
        again, body = mdfile.parse(text)
        self.assertEqual(again, head)
        self.assertEqual(body, "body")

    def test_no_header(self):
        head, body = mdfile.parse("just text")
        self.assertEqual(head, {})
        self.assertEqual(body, "just text")

    def test_unterminated_header(self):
        with self.assertRaises(ValueError):
            mdfile.parse("---\naccount: bybit\nbody")


class TradeRoundTrip(unittest.TestCase):
    def round_trip(self, t):
        text = store.trade_to_text(t)
        again = store.text_to_trade(text)
        self.assertEqual(store.trade_to_text(again), text,
                         "the second pass changed the file")
        return again

    def test_closed_trade(self):
        t = sample_trade()
        again = self.round_trip(t)
        for name in ("id", "account", "pair", "direction", "style", "entry_tf",
                     "execution", "risk", "opened", "opened_time", "result",
                     "pnl", "closed", "exit_images", "conclusions"):
            self.assertEqual(getattr(again, name), getattr(t, name), name)
        self.assertEqual([(b.tf, b.text, b.images) for b in again.idea],
                         [(b.tf, b.text, b.images) for b in t.idea])

    def test_open_trade(self):
        t = sample_trade(result=None, pnl=None, closed=None,
                         exit_images=[], conclusions="")
        again = self.round_trip(t)
        self.assertTrue(again.is_open)
        self.assertIsNone(again.pnl)
        self.assertIsNone(again.closed)

    def test_date_without_time(self):
        t = sample_trade(opened=datetime(2025, 6, 25), opened_time=False)
        again = self.round_trip(t)
        self.assertFalse(again.opened_time)
        self.assertIn("entry: 2025-06-25\n", store.trade_to_text(t))

    def test_empty_fields_and_import_quirks(self):
        # a trade with no pair, no execution, a note and a fractional risk
        t = sample_trade(pair=None, execution=[], risk=1.3, note="pair not set",
                         notion_id="0123456789abcdef0123456789abcdef",
                         idea=[], exit_images=[], conclusions="")
        again = self.round_trip(t)
        self.assertEqual(again.pair, PAIR_NOT_SET)
        self.assertEqual(again.execution, [])
        self.assertEqual(again.risk, 1.3)
        self.assertEqual(again.notion_id, "0123456789abcdef0123456789abcdef")

    def test_unknown_keys_survive(self):
        text = store.trade_to_text(sample_trade())
        text = text.replace("id: ", "future field: value\nid: ", 1)
        again = store.text_to_trade(text)
        self.assertEqual(again.extra.get("future field"), "value")
        self.assertIn("future field: value", store.trade_to_text(again))

    def test_checks(self):
        with self.assertRaises(RecordError):
            sample_trade(direction="up").check()
        with self.assertRaises(RecordError):
            sample_trade(style="scalp").check()
        with self.assertRaises(RecordError):
            sample_trade(pnl=None).check()          # closed without PnL
        with self.assertRaises(RecordError):
            sample_trade(result=None).check()       # open with PnL
        sample_trade().check()


class AccountAndAdjustmentRoundTrip(unittest.TestCase):
    def test_account(self):
        a = Account(id="prop-50k", name="Prop 50k", start_balance=50000,
                    archived=True, notion_id="abcd", note="Closed.")
        text = store.account_to_text(a)
        again = store.text_to_account(text)
        self.assertEqual(store.account_to_text(again), text)
        self.assertTrue(again.archived)
        self.assertEqual(again.start_balance, 50000)
        self.assertEqual(again.note, "Closed.")

    def test_adjustment(self):
        c = Adjustment(id="2026-08-29-reconciliation-bybit", account="bybit",
                       kind="reconciliation", amount=-12.5,
                       day=datetime(2026, 8, 29),
                       comment="Reconciled while importing.")
        text = store.adjustment_to_text(c)
        again = store.text_to_adjustment(text)
        self.assertEqual(store.adjustment_to_text(again), text)
        self.assertEqual(again.amount, -12.5)
        self.assertEqual(again.day, datetime(2026, 8, 29))


class FilesOnDisk(unittest.TestCase):
    def test_write_read_and_list(self):
        with tempfile.TemporaryDirectory() as root:
            store.save_account(root, Account(id="bybit", name="Bybit",
                                             start_balance=10000))
            t = store.save_trade(root, sample_trade())
            again = store.load_trade(root, t.id)
            self.assertEqual(store.trade_to_text(again), store.trade_to_text(t))
            self.assertEqual([x.id for x in store.all_trades(root)], [t.id])
            self.assertEqual(list(store.all_accounts(root)), ["bybit"])

    def test_saving_twice_does_not_add_folders(self):
        with tempfile.TemporaryDirectory() as root:
            store.save_trade(root, sample_trade())
            store.save_trade(root, sample_trade(pnl=200.0))
            base = os.path.join(root, store.JOURNAL, store.TRADES)
            self.assertEqual(len(os.listdir(base)), 1)
            self.assertEqual(store.load_trade(root, "2025-06-25-01-eurusd").pnl, 200.0)

    def test_new_id(self):
        with tempfile.TemporaryDirectory() as root:
            day = datetime(2026, 8, 29)
            first = store.new_id(root, day, "EURUSD")
            self.assertEqual(first, "2026-08-29-01-eurusd")
            store.save_trade(root, sample_trade(id=first))
            self.assertEqual(store.new_id(root, day, "XAUUSD"),
                             "2026-08-29-02-xauusd")


class Cards(unittest.TestCase):
    def test_empty_card_fields_survive_a_write(self):
        """An empty key in the header parses into a LIST, not an empty string:
        `pnl $:` with no value crashed reading a card on float('[]')."""
        with tempfile.TemporaryDirectory() as root:
            k = Card(day=datetime(2026, 8, 30), grade="A", focus="pennies")
            store.save_card(root, k)
            text = open(store.card_path(root, k.day), encoding="utf-8").read()
            self.assertNotIn("pnl $:", text)          # no empty key in the file
            again = store.load_card(root, datetime(2026, 8, 30))
            self.assertEqual(again.grade, "A")
            self.assertIsNone(again.pnl)
            self.assertEqual(again.quality, "")       # not "[]"
            self.assertEqual(again.focus, "pennies")

    def test_empty_key_in_an_old_file_still_reads(self):
        """Files already written with empty keys have to keep working."""
        k = store.text_to_card(
            "---\ndate: 2026-08-30\nprocess grade: A\npnl $: \n"
            "opportunity quality: \n---\n\n## Focus\n\npennies\n")
        self.assertIsNone(k.pnl)
        self.assertEqual(k.quality, "")
        self.assertEqual(k.grade, "A")

    def test_empty_trade_field_is_not_brackets(self):
        t = store.text_to_trade(
            "---\nid: x\naccount: bybit\npair: EURUSD\ndirection: long\n"
            "style: swing\nentry tf: \nrisk %: 1\nentry: 2026-08-30\n---\n")
        self.assertEqual(t.entry_tf, "")


class Layout(unittest.TestCase):
    def test_journal_dirs_appear_at_once(self):
        with tempfile.TemporaryDirectory() as root:
            created = store.make_layout(root)
            self.assertIn(store.CARDS, created)
            for name in store.JOURNAL_DIRS:
                path = os.path.join(root, store.JOURNAL, name)
                self.assertTrue(os.path.isdir(path), name)
                # git does not keep an empty folder — the layout must survive a clone
                self.assertTrue(os.path.isfile(os.path.join(path, ".gitkeep")))
            self.assertEqual(store.make_layout(root), [])   # a second call is quiet


if __name__ == "__main__":
    unittest.main()
