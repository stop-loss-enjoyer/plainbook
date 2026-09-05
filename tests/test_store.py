#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round trip: object -> file -> object -> file."""
import os
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import mdfile, store
from plainbook.model import (Trade, Account, Adjustment, IdeaBlock, Card, Week,
                      Graded, Plan, Playbook, Setup, Rule, RecordError,
                      PAIR_NOT_SET)


def sample_trade(**kw):
    t = Trade(
        id="2025-06-25-01-eurusd",
        account="broker",
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
        head = {"account": "broker", "risk %": "1", "execution": ["M15", "M5"]}
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
            mdfile.parse("---\naccount: broker\nbody")


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
        c = Adjustment(id="2026-08-29-reconciliation-broker", account="broker",
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
            store.save_account(root, Account(id="broker", name="Broker",
                                             start_balance=10000))
            t = store.save_trade(root, sample_trade())
            again = store.load_trade(root, t.id)
            self.assertEqual(store.trade_to_text(again), store.trade_to_text(t))
            self.assertEqual([x.id for x in store.all_trades(root)], [t.id])
            self.assertEqual(list(store.all_accounts(root)), ["broker"])

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

    def test_a_daily_card_carries_a_trades_assessment(self):
        """The same table the weekly card has, on the same shared code."""
        with tempfile.TemporaryDirectory() as root:
            k = Card(day=datetime(2026, 8, 30), grade="A", focus="pennies",
                     assessment=[Graded("EURUSD long", "A", "Win +1.20 R"),
                                 Graded("XAU short", "")])
            store.save_card(root, k)
            again = store.load_card(root, datetime(2026, 8, 30))
            self.assertEqual(again, k)

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
            "---\nid: x\naccount: broker\npair: EURUSD\ndirection: long\n"
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

    def test_the_two_cards_share_a_folder_and_do_not_mix(self):
        """A day and a week are both cards and live in journal/cards, told
        apart by the name of the file."""
        with tempfile.TemporaryDirectory() as root:
            store.save_card(root, Card(day=datetime(2026, 8, 31), focus="a day"))
            store.save_week(root, self.sample(focus="a week"))
            self.assertEqual(os.path.dirname(store.week_path(root, "2026-W36")),
                             os.path.dirname(store.card_path(
                                 root, datetime(2026, 8, 31))))
            problems = []
            days = store.all_cards(root, problems)
            weeks = store.all_weeks(root, problems)
            self.assertEqual([k.focus for k in days], ["a day"])
            self.assertEqual([k.focus for k in weeks], ["a week"])
            self.assertEqual(problems, [])

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

    def test_the_result_is_the_third_cell_and_an_old_line_still_reads(self):
        """A line written before the result column has two cells, or one; it
        reads as a row with an empty result, and is written back unchanged."""
        k = store.text_to_week(
            "---\nweek: 2026-W36\n---\n\n## Trades\n\n"
            "1. EURUSD long, 31.08 | B | Win +1.20 R\n2. XAU short | C\n3. GBPUSD\n")
        self.assertEqual([(r.trade, r.grade, r.result) for r in k.assessment],
                         [("EURUSD long, 31.08", "B", "Win +1.20 R"),
                          ("XAU short", "C", ""), ("GBPUSD", "", "")])
        text = store.week_to_text(k)
        self.assertIn("1. EURUSD long, 31.08 | B | Win +1.20 R\n", text)
        self.assertIn("2. XAU short | C\n", text)
        self.assertNotIn("3. GBPUSD |", text)


class Layout(unittest.TestCase):
    def test_journal_dirs_appear_at_once(self):
        with tempfile.TemporaryDirectory() as root:
            created = store.make_layout(root)
            self.assertIn(store.CARDS, created)
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
            t = Trade(id="2026-08-29-01-eurusd", account="broker", pair="EURUSD",
                      direction="long", style="swing", opened=datetime(2026, 8, 29))
            store.save_trade(root, t)
            store.save_account(root, Account(id="broker", start_balance=1))
            store.delete_trade(root, t.id)
            store.delete_account(root, "broker")
            kinds = {kind: record_id for _, kind, record_id, _ in store.trash_list(root)}
            self.assertEqual(kinds, {"trade": t.id, "account": "broker"})
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

    def test_one_second_holds_two_deletions_in_one_order(self):
        class Frozen(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 9, 3, 18, 47, 3)

        with tempfile.TemporaryDirectory() as root, \
                mock.patch.object(store, "datetime", Frozen):
            for account in ("test-acc", "spare"):
                store.save_account(root, Account(id=account, start_balance=1))
                store.delete_account(root, account)
            # the same stamp on both: the order is by name, whichever way the
            # file system lists the folder
            names = [x[0] for x in store.trash_list(root)]
            self.assertEqual([x[2] for x in store.trash_list(root)],
                             ["spare", "test-acc"])
            with mock.patch.object(store.os, "listdir", return_value=names[::-1]):
                self.assertEqual([x[0] for x in store.trash_list(root)], names)
            # the same id deleted again within the second does not write over
            # its earlier copy: it takes the next second
            store.save_account(root, Account(id="spare", start_balance=2))
            store.delete_account(root, "spare")
            listed = store.trash_list(root)
            self.assertEqual([x[2] for x in listed], ["spare", "spare", "test-acc"])
            self.assertEqual(listed[0][3], datetime(2026, 9, 3, 18, 47, 4))

    def test_the_id_follows_the_day_and_the_pair(self):
        with tempfile.TemporaryDirectory() as root:
            t = Trade(id="2026-08-29-01-eurusd", account="broker", pair="EURUSD",
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
            good = Trade(id="2026-08-29-01-eurusd", account="broker", pair="EURUSD",
                         direction="long", style="swing", opened=datetime(2026, 8, 29))
            store.save_trade(root, good)
            bad = store.trade_dir(root, "2026-08-30-01-eurusd")
            os.makedirs(bad)
            with open(os.path.join(bad, "trade.md"), "w") as f:
                f.write("---\nid: 2026-08-30-01-eurusd\naccount: broker\n"
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


PLAYBOOK_TEXT = """---
id: pullback
name: Pullback
styles:
  - swing
status: experiment
version: 1.0
since: 2026-08-15
block: 40
---

The one way I enter with the trend. Written 14.08.2026.

## Markets

Majors only.

## Setups

### A: reaction at a higher level
The level was hit, the first reaction is in.
- [ ] **Level on W or D** The level is a fractal on the weekly or the daily chart
- [ ] The reaction is seen on H4 or H1
- [x] The target is at least 1R away

### B: continuation
- [ ] The trend is visible on D1
- [ ] Entry from the touch, stop behind the fractal

## Filters

- [ ] More than an hour to the next high-impact release
- [ ] No other position of this playbook is open

## Management

- [ ] **Stop never moved against** The stop stays where the idea dies
- [ ] **Closed by Friday** No position over the weekend

## Limits

- risk: 1 %
- max per week: 5
"""


class PlaybookCase(unittest.TestCase):
    def test_the_review_is_its_own_part(self):
        text = PLAYBOOK_TEXT + "\n## Review\n\n**01.09.2026**: block one held.\n![](shots/review-01.png)\n"
        p = store.text_to_playbook(text)
        self.assertEqual(p.sections, [("Markets", "Majors only.")])
        self.assertIn("block one held", p.review)
        again = store.text_to_playbook(store.playbook_to_text(p))
        self.assertEqual(again.review, p.review)

    def test_a_playbook_reads_rules_numbered_through(self):
        p = store.text_to_playbook(PLAYBOOK_TEXT).check()
        self.assertEqual((p.id, p.name, p.styles, p.status, p.version, p.block),
                         ("pullback", "Pullback", ["swing"], "experiment", "1.0", 40))
        self.assertEqual(p.since, datetime(2026, 8, 15))
        self.assertTrue(p.intro.startswith("The one way"))
        self.assertEqual([s.name for s in p.setups], ["A: reaction at a higher level",
                                                      "B: continuation"])
        self.assertEqual(p.setups[0].text, "The level was hit, the first reaction is in.")
        self.assertEqual([r.number for r in p.rules], [1, 2, 3, 4, 5, 6, 7, 8, 9])
        self.assertEqual([r.number for r in p.management], [8, 9])
        self.assertEqual(p.management[1].text, "Closed by Friday")
        self.assertIn("## Management", store.playbook_to_text(p))
        self.assertEqual((p.rules[0].text, p.rules[0].detail),
                         ("Level on W or D",
                          "The level is a fractal on the weekly or the daily chart"))
        self.assertEqual((p.rules[1].text, p.rules[1].detail),
                         ("The reaction is seen on H4 or H1", ""))
        self.assertIn("- [ ] **Level on W or D** The level", store.playbook_to_text(p))
        self.assertEqual(p.filters[1].text, "No other position of this playbook is open")
        self.assertEqual(p.limits, [("risk", "1 %"), ("max per week", "5")])
        self.assertEqual(p.sections, [("Markets", "Majors only.")])

    def test_a_playbook_round_trips(self):
        p = store.text_to_playbook(PLAYBOOK_TEXT)
        text = store.playbook_to_text(p)
        again = store.text_to_playbook(text)
        self.assertEqual(store.playbook_to_text(again), text)
        self.assertEqual([r.text for r in again.rules], [r.text for r in p.rules])
        self.assertEqual([r.number for r in again.management], [8, 9])
        self.assertEqual(again.limits, p.limits)
        self.assertEqual(again.sections, p.sections)

    def test_prose_above_the_first_setup_goes_to_the_introduction(self):
        p = store.text_to_playbook("---\nid: one\nname: One\n---\n\nWhy.\n\n## Setups\n\n"
                                   "A word on the setups.\n\n### A\n\n- [ ] first\n")
        self.assertEqual([x.name for x in p.setups], ["A"])
        self.assertEqual(p.intro, "Why.\n\nA word on the setups.")
        p.check()

    def test_conditions_without_setups_are_one_nameless_setup(self):
        p = store.text_to_playbook("---\nid: one\nname: One\n---\n\n## Conditions\n\n"
                                   "- [ ] first\n- [ ] second\n\n## Filters\n\n- [ ] third\n")
        self.assertEqual(len(p.setups), 1)
        self.assertEqual(p.setups[0].name, "")
        self.assertEqual([r.number for r in p.rules], [1, 2, 3])
        text = store.playbook_to_text(p)
        self.assertIn("## Conditions", text)
        self.assertNotIn("###", text)

    def test_a_playbook_is_saved_and_listed(self):
        with tempfile.TemporaryDirectory() as root:
            store.save_playbook(root, Playbook(id="old", name="Old", status="retired"))
            store.save_playbook(root, Playbook(
                id="pull", name="Pullback",
                setups=[Setup(name="A", rules=[Rule(1, "one")])],
                filters=[Rule(2, "two")]))
            books = store.all_playbooks(root)
            self.assertEqual([p.id for p in books], ["pull", "old"])
            self.assertEqual([r.text for r in books[0].rules], ["one", "two"])
            with self.assertRaises(RecordError):
                store.save_playbook(root, Playbook(id="bad", name="Bad", status="maybe"))
            with self.assertRaises(RecordError):
                store.save_playbook(root, Playbook(id="nameless", name="  "))

    def test_a_playbook_id_comes_from_the_name(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(store.new_playbook_id(root, "EMT prop"), "emt-prop")
            self.assertEqual(store.new_playbook_id(root, "  "), "playbook")
            store.save_playbook(root, Playbook(id="emt-prop", name="EMT prop"))
            self.assertEqual(store.new_playbook_id(root, "EMT prop"), "emt-prop-2")
            self.assertEqual(store.freeze_playbook(root, "emt-prop"), "unversioned")
            self.assertEqual(store.freeze_playbook(root, "emt-prop"), "unversioned-2")
            self.assertEqual(store.playbook_versions(root, "emt-prop"),
                             ["unversioned", "unversioned-2"])

    def test_a_trade_keeps_its_playbook_and_deviations(self):
        t = sample_trade(playbook="pull", playbook_version="1.0", setup="A", deviations=[2, 5])
        again = store.text_to_trade(store.trade_to_text(t))
        self.assertEqual((again.playbook, again.playbook_version, again.setup, again.deviations),
                         ("pull", "1.0", "A", [2, 5]))
        clean = store.text_to_trade(store.trade_to_text(sample_trade(playbook="pull", deviations=[])))
        self.assertEqual(clean.deviations, [])       # ticked, every rule met
        untouched = store.text_to_trade(store.trade_to_text(sample_trade(playbook="pull")))
        self.assertIsNone(untouched.deviations)      # tied later, never ticked
        self.assertNotIn("deviations", store.trade_to_text(sample_trade(playbook="pull")))
        held = store.text_to_trade(store.trade_to_text(
            sample_trade(playbook="pull", deviations=[], exit_deviations=[9])))
        self.assertEqual((held.deviations, held.exit_deviations), ([], [9]))
        why = store.text_to_trade(store.trade_to_text(sample_trade(
            playbook="pull", deviations=[2], exit_deviations=[9],
            reasons={9: "closed at the news: fear", 2: "no reaction, entered anyway"})))
        self.assertEqual(why.reasons, {2: "no reaction, entered anyway",
                                       9: "closed at the news: fear"})
        self.assertIn("  - 9: closed at the news: fear", store.trade_to_text(why))
        self.assertIsNone(store.text_to_trade(store.trade_to_text(
            sample_trade(playbook="pull", deviations=[]))).exit_deviations)
        self.assertNotIn("playbook", store.trade_to_text(sample_trade()))
