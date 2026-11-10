#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fixes after the audit of 09.11.2026 in the store, the backup, the reports,
the page shell and the shared file: a card or a week read under its file
name, an account file that does not read counting as taken, labels, prices
and typed picture lines surviving a save, a backup that survives a file
failing halfway, a report that is not UTF-8, a period at the edge of the
calendar, and the figures a shared file and a chart print."""
import io
import os
import re
import shutil
import sys
import tempfile
import unittest
import unicodedata
import zipfile
from datetime import datetime
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import backup, reports, share, store
from plainbook import html as H
from plainbook.model import Account, Card, Trade, Week
from plainbook.stats import Summary


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def read_file(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class Scratch(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pb-audit-store-")
        store.make_layout(self.root)
        self.addCleanup(shutil.rmtree, self.root, True)

    def cards_dir(self):
        return os.path.join(self.root, store.JOURNAL, store.CARDS)


class AccountTakenTest(Scratch):
    def test_a_file_that_does_not_parse_still_counts_as_taken(self):
        write(os.path.join(self.root, store.JOURNAL, store.ACCOUNTS, "prop.md"),
              "---\nstart balance: not a number\n---\n")
        self.assertEqual(store.all_accounts(self.root, []), {})
        self.assertTrue(store.account_taken(self.root, "prop"))

    def test_a_free_id_is_not_taken(self):
        self.assertFalse(store.account_taken(self.root, "prop"))
        store.save_account(self.root, Account(id="broker", name="Broker"))
        self.assertTrue(store.account_taken(self.root, "broker"))
        self.assertFalse(store.account_taken(self.root, "brokers"))

    def test_capitals_make_the_same_name_and_an_id_is_never_a_path(self):
        store.save_account(self.root, Account(id="broker", name="Broker"))
        self.assertTrue(store.account_taken(self.root, "BROKER"))
        self.assertFalse(store.account_taken(self.root, "../../broker"))

    def test_no_accounts_folder_at_all(self):
        shutil.rmtree(os.path.join(self.root, store.JOURNAL, store.ACCOUNTS))
        self.assertFalse(store.account_taken(self.root, "x"))


class CardFileNameIsTheTruthTest(Scratch):
    """Item 12: a card copied by hand keeps the date of its original."""

    def copy_of_a_card(self):
        store.save_card(self.root, Card(day=datetime(2026, 3, 4), focus="the original"))
        store.save_card(self.root, Card(day=datetime(2026, 3, 5), focus="the copy"))
        # the owner copied the file of the 4th over the name of the 5th
        # and typed his own words into the copy
        copied = read_file(os.path.join(self.cards_dir(), "2026-03-04.md"))
        write(os.path.join(self.cards_dir(), "2026-03-05.md"),
              copied.replace("the original", "the owner wrote this on the 5th"))

    def test_the_copy_is_read_under_the_day_of_its_file_and_named(self):
        self.copy_of_a_card()
        problems = []
        cards = {k.id: k for k in store.all_cards(self.root, problems)}
        self.assertEqual(sorted(cards), ["2026-03-04", "2026-03-05"])
        self.assertEqual(cards["2026-03-05"].focus, "the owner wrote this on the 5th")
        self.assertEqual(cards["2026-03-04"].focus, "the original")
        self.assertEqual([p[0] for p in problems],
                         ["journal/cards/2026-03-05.md"])

    def test_a_save_of_the_copy_leaves_the_original_alone(self):
        self.copy_of_a_card()
        before = read_file(os.path.join(self.cards_dir(), "2026-03-04.md"))
        k = store.load_card(self.root, datetime(2026, 3, 5), [])
        k.focus = "edited"
        store.save_card(self.root, k)
        self.assertEqual(read_file(os.path.join(self.cards_dir(), "2026-03-04.md")), before)
        back = store.load_card(self.root, datetime(2026, 3, 5), [])
        self.assertEqual(back.focus, "edited")
        # saved, the header agrees with the file again
        problems = []
        store.all_cards(self.root, problems)
        self.assertEqual(problems, [])

    def test_retargeting_a_trade_does_not_write_over_another_day(self):
        self.copy_of_a_card()
        row = __import__("plainbook.model", fromlist=["Graded"]).Graded(
            trade="EURUSD", grade="A", result="win", id="old-id")
        k = store.load_card(self.root, datetime(2026, 3, 5), [])
        k.assessment = [row]
        store.save_card(self.root, k)
        before = read_file(os.path.join(self.cards_dir(), "2026-03-04.md"))
        store.retarget_trade(self.root, "old-id", "new-id")
        self.assertEqual(read_file(os.path.join(self.cards_dir(), "2026-03-04.md")), before)
        self.assertEqual(store.load_card(self.root, datetime(2026, 3, 5), []).assessment[0].id,
                         "new-id")

    def test_without_a_list_the_card_still_reads_under_its_file(self):
        self.copy_of_a_card()
        self.assertEqual(store.load_card(self.root, datetime(2026, 3, 5)).id, "2026-03-05")

    def test_a_file_not_named_for_a_day_is_named_and_not_read(self):
        store.save_card(self.root, Card(day=datetime(2026, 3, 4), focus="mine"))
        copied = read_file(os.path.join(self.cards_dir(), "2026-03-04.md"))
        write(os.path.join(self.cards_dir(), "2026-03-04 - Copy.md"), copied)
        problems = []
        cards = store.all_cards(self.root, problems)
        self.assertEqual([k.id for k in cards], ["2026-03-04"])
        self.assertEqual([p[0] for p in problems], ["journal/cards/2026-03-04 - Copy.md"])
        with self.assertRaises(ValueError):
            store._card_of_file(None, self.root,
                                os.path.join(self.cards_dir(), "2026-03-04 - Copy.md"))

    def test_a_header_day_with_a_time_in_the_same_day_is_no_mismatch(self):
        write(os.path.join(self.cards_dir(), "2026-03-04.md"),
              "---\ndate: 2026-03-04 10:30\n---\n\n## Focus\n\nf\n")
        problems = []
        self.assertEqual(len(store.all_cards(self.root, problems)), 1)
        self.assertEqual(problems, [])


class WeekFileNameIsTheTruthTest(Scratch):
    def copy_of_a_week(self):
        store.save_week(self.root, Week(week="2026-W10", focus="the original"))
        copied = read_file(os.path.join(self.cards_dir(), "2026-W10.md"))
        write(os.path.join(self.cards_dir(), "2026-W11.md"),
              copied.replace("the original", "typed in week 11"))

    def test_the_copy_is_read_under_the_week_of_its_file_and_named(self):
        self.copy_of_a_week()
        problems = []
        weeks = {w.id: w for w in store.all_weeks(self.root, problems)}
        self.assertEqual(sorted(weeks), ["2026-W10", "2026-W11"])
        self.assertEqual(weeks["2026-W11"].focus, "typed in week 11")
        self.assertEqual([p[0] for p in problems], ["journal/cards/2026-W11.md"])

    def test_a_save_of_the_copy_leaves_the_original_alone(self):
        self.copy_of_a_week()
        before = read_file(os.path.join(self.cards_dir(), "2026-W10.md"))
        w = store.load_week(self.root, "2026-W11", [])
        w.focus = "edited"
        store.save_week(self.root, w)
        self.assertEqual(read_file(os.path.join(self.cards_dir(), "2026-W10.md")), before)
        self.assertEqual(store.load_week(self.root, "2026-W11", []).focus, "edited")

    def test_a_file_named_for_no_week_is_named_and_left_alone(self):
        store.save_week(self.root, Week(week="2026-W10", focus="x"))
        copied = read_file(os.path.join(self.cards_dir(), "2026-W10.md"))
        write(os.path.join(self.cards_dir(), "2026-W99.md"), copied)
        problems = []
        self.assertEqual([w.id for w in store.all_weeks(self.root, problems)], ["2026-W10"])
        self.assertEqual([p[0] for p in problems], ["journal/cards/2026-W99.md"])


class LabelsTest(unittest.TestCase):
    def test_a_superscript_digit_in_a_version_label_does_not_crash(self):
        root = tempfile.mkdtemp(prefix="pb-audit-store-")
        self.addCleanup(shutil.rmtree, root, True)
        store.make_layout(root)
        base = os.path.join(root, store.JOURNAL, store.PLAYBOOKS, "pb", store.VERSIONS)
        for name in ("\u00b2.md", "2.md", "10.md", "9.md"):
            write(os.path.join(base, name), "x")
        self.assertEqual(store.playbook_versions(root, "pb"),
                         ["2", "9", "10", "\u00b2"])

    def test_a_superscript_digit_in_a_reason_line_does_not_crash(self):
        self.assertEqual(store._reasons(["\u00b2: odd", "6: closed at the news"]),
                         {6: "closed at the news"})


class TypedImageLineTest(unittest.TestCase):
    def test_a_line_that_is_not_a_picture_of_the_record_stays_in_the_text(self):
        t = Trade(id="t", account="a", direction="long", style="s",
                  opened=datetime(2026, 1, 1), exit_text="before\n![](http://x.test/a.png)\nafter",
                  exit_images=["shots/exit-01.png"],
                  conclusions="c")
        text = store.trade_to_text(t)
        back = store.text_to_trade(text)
        self.assertEqual(back.exit_images, ["shots/exit-01.png"])
        self.assertIn("![](http://x.test/a.png)", back.exit_text)
        # and a second save and read changes nothing
        again = store.text_to_trade(store.trade_to_text(back))
        self.assertEqual(again.exit_text, back.exit_text)

    def test_an_idea_text_keeps_a_typed_link_and_its_pictures_apart(self):
        text, images = store._text_and_images(
            "a\n![alt](https://x.test/p.png)\n![](shots\\idea-01.png)\n![](shots/idea-02.png)")
        self.assertEqual(images, ["shots/idea-01.png", "shots/idea-02.png"])
        self.assertEqual(text, "a\n![alt](https://x.test/p.png)")


class PriceTextTest(unittest.TestCase):
    def test_more_than_ten_significant_digits_are_kept(self):
        self.assertEqual(store._price_to_text(1234.56789012), "1234.56789012")
        self.assertEqual(store._price_to_text(0.123456789012), "0.123456789012")

    def test_prices_typed_with_few_digits_print_as_typed(self):
        self.assertEqual(store._price_to_text(0.00001234), "0.00001234")
        self.assertEqual(store._price_to_text(1.08452), "1.08452")
        self.assertEqual(store._price_to_text(1.1), "1.1")
        self.assertEqual(store._price_to_text(2000), "2000")
        self.assertEqual(store._price_to_text(1e-7), "0.0000001")

    def test_a_long_price_survives_a_round_trip_of_the_trade(self):
        t = Trade(id="t", account="a", direction="long", style="s", pair="BTCUSD",
                  opened=datetime(2026, 1, 1), entry_price=64321.123456789)
        back = store.text_to_trade(store.trade_to_text(t))
        self.assertEqual(back.entry_price, 64321.123456789)


class BackupFailingFileTest(Scratch):
    def journal(self):
        store.save_account(self.root, Account(id="broker", name="Broker", start_balance=1000))
        write(os.path.join(self.root, store.JOURNAL, "a-notes.txt"), "x" * 5000)
        write(os.path.join(self.root, store.JOURNAL, "b-fails.txt"), "y" * (3 << 20))
        write(os.path.join(self.root, store.JOURNAL, "c-after.txt"), "z" * 100)

    def test_a_file_failing_halfway_is_skipped_and_the_rest_restores(self):
        self.journal()
        real_open = open
        bad = os.path.join(self.root, store.JOURNAL, "b-fails.txt")

        class Failing:
            def __init__(self, f):
                self.f, self.reads = f, 0

            def read(self, n=-1):
                self.reads += 1
                if self.reads > 1:
                    raise OSError(5, "Input/output error")
                return self.f.read(n)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                self.f.close()

        def opener(path, *args, **kw):
            f = real_open(path, *args, **kw)
            return Failing(f) if path == bad else f

        out = io.BytesIO()
        with mock.patch.object(backup, "open", opener, create=True):
            manifest = backup.make(self.root, out)
        self.assertIn("journal/b-fails.txt", manifest["skipped"])
        self.assertNotIn("journal/b-fails.txt", manifest["files"])
        with zipfile.ZipFile(io.BytesIO(out.getvalue())) as z:
            self.assertNotIn("journal/b-fails.txt", z.namelist())
        # a backup with a skipped file is still a backup that can be taken
        source = os.path.join(self.root, "failed.plainbook")
        with open(source, "wb") as f:
            f.write(out.getvalue())
        token, _ = backup.new_stage(self.root)
        kept = backup.unpack(self.root, token, source)
        self.assertEqual(kept["skipped"], ["journal/b-fails.txt"])
        self.assertTrue(os.path.isfile(os.path.join(
            self.root, backup.STAGE, token, "journal", "c-after.txt")))


class BackupNormalisedNamesTest(Scratch):
    def test_two_names_differing_only_in_the_form_of_an_accent_are_refused(self):
        nfc = unicodedata.normalize("NFC", "journal/notes/café.md")
        nfd = unicodedata.normalize("NFD", nfc)
        self.assertNotEqual(nfc, nfd)
        source = os.path.join(self.root, "twins.plainbook")
        import hashlib
        import json
        files = {}
        with zipfile.ZipFile(source, "w") as z:
            for n in (nfc, nfd):
                z.writestr(n, b"x")
                files[n] = {"sha256": hashlib.sha256(b"x").hexdigest(), "size": 1}
            z.writestr(backup.MANIFEST, json.dumps(
                {"app": "plainbook", "format": backup.FORMAT, "files": files}))
        token, _ = backup.new_stage(self.root)
        with self.assertRaises(backup.BackupError) as e:
            backup.unpack(self.root, token, source)
        self.assertIn("differ only", str(e.exception))


class ReportNotUtf8Test(Scratch):
    def report(self, period="2026-03"):
        path = reports.path(self.root, period)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"---\nperiod: " + period.encode() + b"\n---\n\n## Conclusions\n\n"
                    b"caf\xe9 was the lesson\n")
        return path

    def test_read_does_not_raise_and_names_the_file(self):
        self.report()
        problems = []
        head, body = reports.read(self.root, "2026-03", problems)
        self.assertIn("lesson", body)
        self.assertEqual([p[0] for p in problems], ["journal/reports/2026-03.md"])

    def test_read_without_a_list_still_opens_the_page_text(self):
        self.report()
        head, body = reports.read(self.root, "2026-03")
        self.assertIn("lesson", body)

    def test_a_rebuild_keeps_the_original_bytes_beside_the_file(self):
        path = self.report()
        with open(path, "rb") as f:
            original = f.read()
        reports._keep_undecodable(path)
        with open(path + ".bak", "rb") as f:
            self.assertEqual(f.read(), original)
        # a second call does not replace the first copy
        write(path, "now valid\n")
        reports._keep_undecodable(path)
        with open(path + ".bak", "rb") as f:
            self.assertEqual(f.read(), original)

    def test_a_readable_file_is_not_copied(self):
        path = reports.path(self.root, "2026-03")
        write(path, "---\nperiod: 2026-03\n---\n\nfine\n")
        reports._keep_undecodable(path)
        self.assertFalse(os.path.exists(path + ".bak"))


class ReportAtTheEdgeOfTheCalendarTest(Scratch):
    def test_the_first_month_a_date_holds_is_not_a_period(self):
        self.assertFalse(reports.is_period("0001-01"))
        self.assertFalse(reports.is_period("0001-Q1"))
        self.assertTrue(reports.is_period("0001-02"))
        with self.assertRaises(ValueError):
            reports.previous_period("0001-01")

    def test_a_report_file_for_year_one_is_passed_over(self):
        for name in ("0001-01.md", "2026-03.md"):
            write(os.path.join(self.root, store.JOURNAL, store.REPORTS, name), "x")
        self.assertEqual(reports.existing(self.root), ["2026-03"])


class MoneyTest(unittest.TestCase):
    def test_a_value_that_is_not_finite_is_a_hyphen(self):
        for x in (float("inf"), float("-inf"), float("nan")):
            self.assertEqual(H.money(x), "-")
            self.assertEqual(H.money(x, signed=True), "-")
        self.assertEqual(H.money(1234.4), "1 234")
        self.assertEqual(H.money(-0.4), "0")


class ChartFontTest(unittest.TestCase):
    """The font list holds double quotes: unescaped they end the attribute,
    the browser drops the rest of it and the labels fall back to the sans
    font of the page."""

    def attributes(self, svg):
        return re.findall(r'font-family="(.*?)"', svg)

    def test_the_labels_of_the_equity_curve_keep_the_monospace_list(self):
        pts = [(datetime(2026, 7, 1), 100.0), (datetime(2026, 7, 2), 110.0)]
        svg = H.equity_svg([("acc", "#fff", pts)])
        found = self.attributes(svg)
        self.assertTrue(found)
        self.assertEqual(set(found), {H.esc(H.MONO)})

    def test_the_labels_of_the_tape_keep_the_monospace_list(self):
        bars = [(1.5, "Win", "", "a"), (-1.0, "Lose", "", "b")]
        svg = H.tape_svg(bars, [(0, "W32")], labels=("mon", "tue"))
        found = self.attributes(svg)
        self.assertTrue(found)
        self.assertEqual(set(found), {H.esc(H.MONO)})


class SharedFileFiguresTest(unittest.TestCase):
    def test_r_that_rounds_to_zero_has_no_sign(self):
        self.assertEqual(share.r_or_dash(-0.004), "0.00")
        self.assertEqual(share.r_or_dash(0.004), "0.00")
        self.assertEqual(share.r_or_dash(0), "0.00")
        self.assertEqual(share.r_or_dash(-0.006), "-0.01")
        self.assertEqual(share.r_or_dash(1.234), "+1.23")
        self.assertEqual(share.r_or_dash(None), "-")

    def test_ev_is_captioned_by_the_trades_it_was_measured_on(self):
        s = Summary(trades=5, wins=2, losses=2, be=1, sum_r=3.0,
                    measured=3, measured_wins=1, measured_losses=1, measured_be=1)
        tiles = share.summary_tiles(s)
        self.assertIn("over 3 trades with a measured R", tiles)
        self.assertNotIn("per closed trade", tiles)
        one = Summary(trades=1, wins=1, sum_r=1.0, measured=1, measured_wins=1)
        self.assertIn("over 1 trade with a measured R", share.summary_tiles(one))

    def test_a_breakdown_with_unmeasured_trades_says_what_ev_is_over(self):
        row = Summary(trades=4, wins=2, losses=2, sum_r=1.0, measured=2,
                      measured_wins=1, measured_losses=1)
        whole = Summary(trades=2, wins=1, losses=1, sum_r=1.0, measured=2,
                        measured_wins=1, measured_losses=1)
        self.assertIn('class="muted"', share.doc_slice_card(None, "By style", [("a", row)]))
        self.assertNotIn('class="muted"', share.doc_slice_card(None, "By style", [("a", whole)]))


class ResultSvgFlatTest(unittest.TestCase):
    def test_a_result_that_prints_zero_is_neither_green_nor_red(self):
        for r in (-0.004, 0.004, 0.0):
            svg = H.result_svg(r, [], 2.0)
            self.assertIn("0.00 R", svg)
            self.assertNotIn("-0.00 R", svg)
            self.assertNotIn("+0.00 R", svg)
            self.assertNotIn(H.GOOD, re.findall(r'<rect[^>]*y="31"[^>]*/>', svg)[0])
            self.assertNotIn(H.BAD, re.findall(r'<rect[^>]*y="31"[^>]*/>', svg)[0])

    def test_a_real_loss_is_still_red(self):
        svg = H.result_svg(-0.4, [], 2.0)
        self.assertIn(H.BAD, re.findall(r'<rect[^>]*y="31"[^>]*/>', svg)[0])


if __name__ == "__main__":
    unittest.main()
