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
from plainbook.model import (Trade, Account, Adjustment, IdeaBlock, Card, Week,
                      Graded, Plan, RecordError, PAIR_NOT_SET)


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
        conclusions="Held to target. Did not move the stop, right call.",
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

    def test_the_exit_keeps_its_hour(self):
        """The hour of the close is what orders two trades of the same day."""
        t = sample_trade(closed=datetime(2025, 6, 27, 12, 40), closed_time=True)
        again = self.round_trip(t)
        self.assertEqual(again.closed, datetime(2025, 6, 27, 12, 40))
        self.assertTrue(again.closed_time)
        self.assertIn("exit: 2025-06-27 12:40", store.trade_to_text(t))

    def test_closed_trade(self):
        t = sample_trade()
        again = self.round_trip(t)
        for name in ("id", "account", "pair", "direction", "style", "entry_tf",
                     "execution", "risk", "opened", "opened_time", "result",
                     "pnl", "closed", "closed_time", "exit_images",
                     "conclusions"):
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
            sample_trade(style="").check()
        # a style is the owner's word, not a fixed list: one taken out of the
        # trade form must still load in the trades that carry it
        sample_trade(style="scalp").check()
        with self.assertRaises(RecordError):
            sample_trade(pnl=None).check()          # closed without PnL
        with self.assertRaises(RecordError):
            sample_trade(result=None).check()       # open with PnL
        sample_trade().check()


class PlanRoundTrip(unittest.TestCase):
    def plan(self, **kw):
        fields = dict(id="2026-09-01-eurusd", title="weekly", pair="EURUSD",
                      narrative="bullish", day=datetime(2026, 9, 1),
                      until=datetime(2026, 9, 5),
                      analysis=[IdeaBlock(tf="D1", text="range formed",
                                          images=["shots/idea-01-01.png"])],
                      plan="long from the nearest SNR, no shorts",
                      updates="**01.09.2026**: gap up",
                      review="went as written")
        fields.update(kw)
        return Plan(**fields)

    def test_a_plan_survives_the_round_trip(self):
        k = self.plan()
        again = store.text_to_plan(store.plan_to_text(k))
        self.assertEqual((again.id, again.title, again.pair, again.narrative),
                         (k.id, k.title, k.pair, k.narrative))
        self.assertEqual((again.day, again.until), (k.day, k.until))
        self.assertEqual(again.analysis[0].tf, "D1")
        self.assertEqual(again.analysis[0].images, ["shots/idea-01-01.png"])
        self.assertEqual((again.plan, again.updates, again.review),
                         (k.plan, k.updates, k.review))

    def test_a_plan_of_one_day_has_no_until(self):
        k = self.plan(until=None)
        text = store.plan_to_text(k)
        self.assertNotIn("until:", text)                  # an empty key is a list
        self.assertIsNone(store.text_to_plan(text).until)

    def test_a_plan_is_checked(self):
        with self.assertRaises(RecordError):
            self.plan(day=None).check()
        with self.assertRaises(RecordError):
            self.plan(narrative="sideways").check()
        with self.assertRaises(RecordError):
            self.plan(until=datetime(2026, 8, 1)).check()
        self.plan().check()

    def test_a_plan_knows_the_days_it_covers(self):
        k = self.plan()
        self.assertTrue(k.covers(datetime(2026, 9, 3, 14, 30)))
        self.assertTrue(k.covers(datetime(2026, 9, 5, 23, 0)))
        self.assertFalse(k.covers(datetime(2026, 9, 6)))
        self.assertTrue(self.plan(until=None).covers(datetime(2026, 9, 1, 8)))


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
            with open(store.card_path(root, k.day), encoding="utf-8") as f:
                text = f.read()
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


class Weeks(unittest.TestCase):
    def sample(self, **kw):
        k = Week(week="2026-W36", grade="B", pnl=480.0, trades=4, quality="A",
                 progress=3, focus="one setup a day", lesson="write it first",
                 assessment=[Graded("EURUSD long", "A"), Graded("XAU short", "")])
        for name, value in kw.items():
            setattr(k, name, value)
        return k

    def test_a_week_survives_the_round_trip(self):
        k = self.sample()
        again = store.text_to_week(store.week_to_text(k))
        self.assertEqual(again, k)

    def test_the_dates_come_from_the_key(self):
        k = self.sample()
        self.assertEqual(k.monday, datetime(2026, 8, 31))
        self.assertEqual(k.number, 36)

    def test_a_week_that_never_happened_is_refused(self):
        for bad in ("", "2026-36", "2026-W00", "2025-W53"):
            with self.assertRaises(RecordError):
                Week(week=bad).check()

    def test_empty_week_fields_survive_a_write(self):
        with tempfile.TemporaryDirectory() as root:
            k = Week(week="2026-W36", grade="A", focus="pennies")
            store.save_week(root, k)
            with open(store.week_path(root, k.week), encoding="utf-8") as f:
                text = f.read()
            self.assertNotIn("pnl $:", text)          # no empty key in the file
            self.assertNotIn("## Trades", text)       # nothing was assessed
            again = store.load_week(root, "2026-W36")
            self.assertIsNone(again.pnl)
            self.assertIsNone(again.trades)
            self.assertEqual(again.quality, "")       # not "[]"
            self.assertEqual(again.assessment, [])

    def test_an_assessment_row_without_a_grade_reads_back(self):
        k = store.text_to_week(
            "---\nweek: 2026-W36\n---\n\n## Trades\n\n"
            "1. EURUSD long | B\n2. XAU short\n3.\n")
        self.assertEqual([(r.trade, r.grade) for r in k.assessment],
                         [("EURUSD long", "B"), ("XAU short", "")])


class Layout(unittest.TestCase):
    def test_journal_dirs_appear_at_once(self):
        with tempfile.TemporaryDirectory() as root:
            created = store.make_layout(root)
            self.assertIn(store.CARDS, created)
            self.assertIn(store.WEEKS, created)
            for name in store.JOURNAL_DIRS:
                path = os.path.join(root, store.JOURNAL, name)
                self.assertTrue(os.path.isdir(path), name)
                # git does not keep an empty folder, so the layout must survive a clone
                self.assertTrue(os.path.isfile(os.path.join(path, ".gitkeep")))
            self.assertEqual(store.make_layout(root), [])   # a second call is quiet


if __name__ == "__main__":
    unittest.main()


class Trash(unittest.TestCase):
    def test_a_record_is_listed_and_restored(self):
        with tempfile.TemporaryDirectory() as root:
            t = Trade(id="2026-08-29-01-eurusd", account="bybit", pair="EURUSD",
                      direction="long", style="swing", opened=datetime(2026, 8, 29))
            store.save_trade(root, t)
            store.save_account(root, Account(id="bybit", start_balance=1))
            store.delete_trade(root, t.id)
            store.delete_account(root, "bybit")
            kinds = {kind: record_id for _, kind, record_id, _ in store.trash_list(root)}
            self.assertEqual(kinds, {"trade": t.id, "account": "bybit"})
            name = next(x[0] for x in store.trash_list(root) if x[1] == "trade")
            self.assertEqual(store.restore(root, name), ("trade", t.id))
            self.assertEqual(store.load_trade(root, t.id).pair, "EURUSD")
            # deleted again, it is a second entry with its own stamp, and it
            # will not come back over the one that is in the journal now
            store.delete_trade(root, t.id)
            store.save_trade(root, t)
            name = next(x[0] for x in store.trash_list(root) if x[1] == "trade")
            with self.assertRaises(FileExistsError):
                store.restore(root, name)

    def test_the_id_follows_the_day_and_the_pair(self):
        with tempfile.TemporaryDirectory() as root:
            t = Trade(id="2026-08-29-01-eurusd", account="bybit", pair="EURUSD",
                      direction="long", style="swing", opened=datetime(2026, 8, 29))
            store.save_trade(root, t)
            self.assertTrue(store.id_fits(t))
            t.pair = "GBPUSD"
            self.assertFalse(store.id_fits(t))
            # the pair changed on the same day: the number is kept
            self.assertEqual(store.new_id(root, t.opened, t.pair, keep=t.id),
                             "2026-08-29-01-gbpusd")
            store.rename_trade(root, t, "2026-08-29-01-gbpusd")
            store.save_trade(root, t)
            self.assertEqual(store.load_trade(root, "2026-08-29-01-gbpusd").pair, "GBPUSD")
            self.assertFalse(os.path.isdir(store.trade_dir(root, "2026-08-29-01-eurusd")))
            # an id of another shape is never judged
            t.id = "notion-import-7"
            self.assertTrue(store.id_fits(t))

    def test_a_broken_file_is_reported_and_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            good = Trade(id="2026-08-29-01-eurusd", account="bybit", pair="EURUSD",
                         direction="long", style="swing", opened=datetime(2026, 8, 29))
            store.save_trade(root, good)
            bad = store.trade_dir(root, "2026-08-30-01-eurusd")
            os.makedirs(bad)
            with open(os.path.join(bad, "trade.md"), "w") as f:
                f.write("---\nid: 2026-08-30-01-eurusd\naccount: bybit\n"
                        "direction: long\nstyle: swing\nrisk %: one\n"
                        "entry: 2026-08-30\n---\n")
            with self.assertRaises(ValueError):
                store.all_trades(root)
            problems = []
            trades = store.all_trades(root, problems)
            self.assertEqual([t.id for t in trades], [good.id])
            self.assertEqual(len(problems), 1)
            self.assertIn("2026-08-30-01-eurusd/trade.md", problems[0][0])
            self.assertIn("one", problems[0][1])
