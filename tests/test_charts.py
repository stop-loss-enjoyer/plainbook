#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The pictures: what the smoothing is allowed to do, and how R is split."""
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import html as H
from plainbook import stats
from plainbook.balances import Journal
from plainbook.html import smooth_path, spread_days
from plainbook.model import Account, Trade


def cubics(d):
    """The path back as numbers: [(kind, [x, y, ...])]."""
    out = []
    for chunk in d.replace(",", " ").split("M")[1].split("C"):
        out.append([float(v) for v in chunk.replace("L", " ").split()])
    return out


def sample(p0, c1, c2, p1, n=40):
    """Points along a cubic, to see where the curve actually goes."""
    ys = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        ys.append(u**3 * p0[1] + 3 * u**2 * t * c1[1]
                  + 3 * u * t**2 * c2[1] + t**3 * p1[1])
    return ys


class SmoothingCase(unittest.TestCase):
    def test_the_curve_never_leaves_the_data_behind(self):
        """A soft line may not invent a high or a low.

        This is the whole reason the smoothing is monotone: an equity curve
        that bulges past a real peak would be a picture of a profit that never
        happened."""
        points = [(0, 100), (10, 40), (20, 44), (30, 42), (40, 90), (50, 20)]
        d = smooth_path(points)
        pieces = cubics(d)
        cursor = points[0]
        for i, piece in enumerate(pieces[1:], 0):
            c1, c2, p1 = (piece[0], piece[1]), (piece[2], piece[3]), (piece[4], piece[5])
            low, high = min(cursor[1], p1[1]), max(cursor[1], p1[1])
            for y in sample(cursor, c1, c2, p1):
                self.assertGreaterEqual(y, low - 1e-6, f"segment {i} dips below")
                self.assertLessEqual(y, high + 1e-6, f"segment {i} rises above")
            cursor = p1

    def test_two_points_on_one_day_keep_their_step(self):
        """Nothing to interpolate across an x of zero width."""
        self.assertIn("L", smooth_path([(0, 10), (10, 20), (10, 5), (20, 6)]))

    def test_a_single_point_draws_nothing(self):
        self.assertEqual(smooth_path([(1, 1)]), "")


class SpreadCase(unittest.TestCase):
    def test_closes_of_one_day_get_their_own_place_in_it(self):
        """Otherwise they share an x and the line between them is a wall."""
        day = datetime(2026, 7, 14)
        out = spread_days([(datetime(2026, 7, 1), 10), (day, 11), (day, 12),
                           (day, 9), (datetime(2026, 7, 20), 13)])
        xs = [d for d, _ in out]
        self.assertEqual([v for _, v in out], [10, 11, 12, 9, 13])   # order kept
        self.assertEqual(len(set(xs)), 5)                            # all apart
        for d, _ in out:
            self.assertEqual(d.date(), d.date())
        self.assertTrue(all(d.date() == day.date() for d in xs[1:4]))
        self.assertTrue(xs[0] < xs[1] < xs[2] < xs[3] < xs[4])

    def test_a_lone_close_keeps_midnight(self):
        """Nothing is nudged when there is nothing to untangle."""
        pts = [(datetime(2026, 7, 1), 10), (datetime(2026, 7, 2), 11)]
        self.assertEqual(spread_days(pts), pts)


class PeriodCase(unittest.TestCase):
    def test_a_report_counts_the_trades_that_closed_in_its_period(self):
        """By the exit, as a broker states a month: a trade entered in August
        and closed in September is September's, and an open one is nobody's."""
        from plainbook import reports
        accounts = {"broker": Account(id="broker", start_balance=10000)}
        ran_over = Trade(id="t1", account="broker", pair="EURUSD", direction="long",
                         style="swing", risk=1.0, opened=datetime(2026, 8, 28),
                         result="Win", pnl=200, closed=datetime(2026, 9, 2))
        still_open = Trade(id="t2", account="broker", pair="GBPUSD", direction="long",
                           style="swing", risk=1.0, opened=datetime(2026, 9, 1))
        j = Journal(accounts, [ran_over, still_open], [])
        self.assertEqual([t.id for t in reports.trades_of_period(j, "2026-09")], ["t1"])
        self.assertEqual(reports.trades_of_period(j, "2026-08"), [])
        self.assertEqual(stats.closing_months(j.trades), ["2026-09"])
        self.assertEqual(stats.months(j.trades), ["2026-08", "2026-09"])


class EquityTipCase(unittest.TestCase):
    def test_the_tip_names_the_currency_of_the_account(self):
        from plainbook.html import equity_svg
        pts = [(datetime(2026, 7, 1), 100.0), (datetime(2026, 7, 2), 110.0)]
        svg = equity_svg([("acc", "#fff", pts)], sign="€")
        self.assertIn('"sign": "€"', svg)


class EquityAxesCase(unittest.TestCase):
    def test_the_ticks_are_round(self):
        from plainbook.html import count_step, date_ticks, nice_step
        self.assertEqual(nice_step(1877), 500)
        self.assertEqual(nice_step(90), 20)
        self.assertEqual(count_step(16), 5)
        self.assertEqual(count_step(160), 50)
        # a few weeks tick on Mondays, a year ticks on the first of the month
        ticks = date_ticks(datetime(2026, 8, 5), datetime(2026, 9, 4))
        self.assertEqual([d.weekday() for d, _ in ticks], [0, 0, 0, 0])
        self.assertEqual(ticks[0][1], "10.08")
        ticks = date_ticks(datetime(2025, 10, 3), datetime(2026, 9, 4))
        self.assertTrue(all(d.day == 1 for d, _ in ticks))
        self.assertLessEqual(len(ticks), 8)
        self.assertEqual(ticks[0][1], "11.2025")

    def test_by_trade_an_adjustment_takes_no_step(self):
        from plainbook.html import equity_svg
        from plainbook.model import Adjustment
        deposit = Adjustment(id="a", account="acc", kind="deposit", amount=50,
                             day=datetime(2026, 7, 2))
        pts = [(datetime(2026, 7, 1), 100.0, "start"),
               (datetime(2026, 7, 1), 110.0, None),
               (datetime(2026, 7, 2), 160.0, deposit),
               (datetime(2026, 7, 3), 150.0, None)]
        svg = equity_svg([("acc", "#fff", pts)], base=100.0, axis="trade")
        # the deposit shares the x of the trade before it and is marked
        self.assertIn('"trade 1 ', svg)
        self.assertIn("deposit +50", svg)
        self.assertIn('r="3.5"', svg)
        # the end label: 150, and the deposit is not a result, so +0 from 150
        self.assertIn("+0</text>", svg)
        self.assertIn('stroke-dasharray="3 4"', svg)
        # the tip: 110 is +10 from the start, 160 is +10 from the raised base
        self.assertIn("110, '', 10]".replace("'", '"'), svg)
        self.assertIn('160, "deposit +50", 10]', svg)


class RSplitCase(unittest.TestCase):
    def setUp(self):
        self.accounts = {"broker": Account(id="broker", start_balance=10000)}

    def trade(self, tid, result, pnl):
        return Trade(id=tid, account="broker", pair="EURUSD", direction="long",
                     style="swing", risk=1.0, opened=datetime(2026, 8, 1),
                     result=result, pnl=pnl, closed=datetime(2026, 8, 2))

    def test_the_piles_follow_the_result_and_the_buckets_follow_r(self):
        j = Journal(self.accounts, [
            self.trade("t1", "Lose", -100),      # -1.00 R
            self.trade("t2", "Lose", -30),       # -0.30 R
            self.trade("t3", "Win", 40),         # +0.40 R
            self.trade("t4", "Win", 350),        # +3.50 R
            self.trade("t5", "BE", 0),
        ], [])
        losses, wins, be = stats.r_split(j, j.trades)
        self.assertEqual(be, 1)
        self.assertEqual([(label, n) for label, n, _ in losses],
                         [("0…-0.5", 1), ("-0.5…-1", 0), ("-1…-1.2", 1),
                          ("-1.2R and worse", 0)])
        self.assertEqual([(label, n) for label, n, _ in wins],
                         [("0…+0.5", 1), ("+0.5…+1", 0), ("+1…+2", 0),
                          ("+2…+3", 0), ("+3R and more", 1)])
        # the counts are the ones the winrate is built from
        s = stats.summary(j, j.trades)
        self.assertEqual(sum(n for _, n, _ in losses), s.losses)
        self.assertEqual(sum(n for _, n, _ in wins), s.wins)
        self.assertEqual(be, s.be)

    def test_the_stop_is_told_apart_from_too_much_size(self):
        """A stop costs a little more than -1R; past -1.2R it was not the stop.

        Commission and swap are paid on top of the stop, so the bucket that
        means "taken to the stop" runs to -1.2R. Anything worse says the
        position was too big, which is the whole reason to keep it apart."""
        j = Journal(self.accounts, [
            self.trade("t1", "Lose", -100),      # -1.00 R exactly: the stop
            self.trade("t2", "Lose", -115),      # -1.15 R: the stop and its fees
            self.trade("t3", "Lose", -120),      # -1.20 R: over the tolerance
            self.trade("t4", "Lose", -250),      # -2.50 R: too much size
            self.trade("t5", "Lose", -99),       # -0.99 R: never reached it
        ], [])
        losses, _, _ = stats.r_split(j, j.trades)
        self.assertEqual([(label, n) for label, n, _ in losses],
                         [("0…-0.5", 0), ("-0.5…-1", 1), ("-1…-1.2", 2),
                          ("-1.2R and worse", 2)])

    def test_the_ev_counts_every_closed_trade(self):
        """Σ R over the closed trades, break-evens included: a trade closed at
        zero still paid its commission, and leaving it out would flatter the
        figure. The winrate beside it keeps them out, as always."""
        j = Journal(self.accounts, [
            self.trade("t1", "Win", 200),        # +2.00 R
            self.trade("t2", "Win", 100),        # +1.00 R
            self.trade("t3", "Lose", -100),      # -1.00 R
            self.trade("t4", "BE", -10),         # -0.10 R: the commission
        ], [])
        s = stats.summary(j, j.trades)
        self.assertAlmostEqual(s.average_r, 1.9 / 4)
        self.assertAlmostEqual(s.wr, 200 / 3)
        # the three sums are the whole of Σ R, and the break-evens are in it
        self.assertAlmostEqual(s.sum_r_win + s.sum_r_lose + s.sum_r_be, s.sum_r)
        self.assertAlmostEqual(s.sum_r_be, -0.1)
        self.assertEqual(stats.Summary().average_r, 0.0)

    def test_a_break_even_stays_out_of_both_rings(self):
        j = Journal(self.accounts, [self.trade("t1", "BE", 0)], [])
        losses, wins, be = stats.r_split(j, j.trades)
        self.assertEqual((sum(n for _, n, _ in losses),
                          sum(n for _, n, _ in wins), be), (0, 0, 1))


class DrawdownAndSlicesCase(unittest.TestCase):
    """Figures the reports lean on: the deepest fall, and a field held twice."""

    def journal(self, results):
        accounts = {"broker": Account(id="broker", start_balance=10000)}
        trades = []
        for i, (pnl, execution) in enumerate(results, 1):
            trades.append(Trade(
                id=f"t{i}", account="broker", pair="EURUSD", direction="long",
                style="swing", risk=1.0, execution=execution,
                opened=datetime(2026, 8, i), closed=datetime(2026, 8, i),
                result="Win" if pnl > 0 else "Lose" if pnl < 0 else "BE",
                pnl=pnl))
        return Journal(accounts, trades, [])

    def test_the_drawdown_is_measured_from_the_high_of_the_period(self):
        # +2R, then two losses, then +1R: the fall from the high is about -2R,
        # even though the period ends higher than it started. Not exactly -2R,
        # because the two losses are measured against a balance the first win
        # had already raised
        j = self.journal([(200, []), (-100, []), (-100, []), (100, [])])
        self.assertAlmostEqual(stats.drawdown_r(j, j.trades), -1.97, places=2)
        # a period that only goes up never fell
        j = self.journal([(100, []), (100, [])])
        self.assertEqual(stats.drawdown_r(j, j.trades), 0.0)

    def test_a_trade_counts_in_every_execution_format_it_carries(self):
        j = self.journal([(100, ["IDM", "SNR"]), (-100, ["SNR"])])
        rows = dict(stats.by_values(j, j.trades, lambda t: t.execution or ["not set"]))
        self.assertEqual(rows["SNR"].trades, 2)
        self.assertEqual(rows["IDM"].trades, 1)
        self.assertEqual(rows["IDM"].wins, 1)
        # a trade without the field is not silently dropped
        j = self.journal([(100, [])])
        rows = dict(stats.by_values(j, j.trades, lambda t: t.execution or ["not set"]))
        self.assertEqual(rows["not set"].trades, 1)


class ReportCase(unittest.TestCase):
    """What a report calls a mistake, and the shelf it lays the periods on."""

    def trade(self, i, pnl, **kw):
        return Trade(id=f"t{i}", account="broker", pair="EURUSD", direction="long",
                     style="swing", risk=1.0, opened=datetime(2026, 8, i, 10),
                     closed=datetime(2026, 8, i, 12),
                     result="Win" if pnl > 0 else "Lose" if pnl < 0 else "BE",
                     pnl=pnl, **kw)

    def test_a_mistake_is_a_rule_not_met_or_a_loss_past_the_stop(self):
        import tempfile
        from plainbook import reports
        accounts = {"broker": Account(id="broker", start_balance=10000)}
        trades = [self.trade(1, 200, playbook="p", deviations=[2]),       # broke a rule and won
                  self.trade(2, -150, playbook="p", deviations=[],
                             exit_deviations=[7]),                         # broke at the close, past the stop
                  self.trade(3, -100, playbook="p", deviations=[]),       # clean, the stop itself
                  self.trade(4, -130),                                     # no playbook, past the stop
                  self.trade(5, 100, playbook="p")]                        # tied later, never ticked
        j = Journal(accounts, trades, [])
        with tempfile.TemporaryDirectory() as root:
            r = reports.compose(root, j, "2026-08")
        self.assertEqual((r.ticked, r.unticked), (3, 1))
        self.assertEqual((r.entry_broken, r.close_broken), (1, 1))
        self.assertEqual([t.id for t in r.past_stop], ["t2", "t4"])      # the deeper first
        # t2 broke a rule and went past the stop, and is counted once
        self.assertEqual(sorted(t.id for t in r.mistakes), ["t1", "t2", "t4"])
        self.assertEqual(r.mistakes_sum.trades, 3)
        self.assertEqual(r.kept.trades, 1)
        self.assertEqual([t.id for t in r.order], ["t1", "t2", "t3", "t4", "t5"])
        self.assertEqual(r.days_traded, 5)
        self.assertEqual(r.earlier_name, "July 2026")

    def test_a_rule_not_held_at_the_close_counts_without_an_entry_checklist(self):
        """A trade tied to its playbook later, ticked at the close only, with a
        management rule not held: a mistake on the tile, a break in the
        playbook's held column, the two agree."""
        import tempfile
        from plainbook import reports, stats
        accounts = {"broker": Account(id="broker", start_balance=10000)}
        trades = [self.trade(1, 100, playbook="p", exit_deviations=[13]),   # entry never ticked
                  self.trade(2, 100, playbook="p", exit_deviations=[]),     # close ticked clean
                  self.trade(3, 100, playbook="p")]                          # never ticked at all
        j = Journal(accounts, trades, [])
        with tempfile.TemporaryDirectory() as root:
            r = reports.compose(root, j, "2026-08")
        self.assertEqual((r.ticked, r.unticked), (2, 1))
        self.assertEqual((r.entry_broken, r.close_broken), (0, 1))
        self.assertEqual([t.id for t in r.mistakes], ["t1"])
        self.assertEqual(r.kept.trades, 1)
        self.assertTrue(stats.ticked(trades[0]) and stats.broke(trades[0]))
        self.assertFalse(stats.ticked(trades[2]))

    def test_the_file_writes_a_dash_where_the_page_shows_one(self):
        import tempfile
        from plainbook import reports
        accounts = {"broker": Account(id="broker", start_balance=10000)}
        j = Journal(accounts, [self.trade(4, 0)], [])
        with tempfile.TemporaryDirectory() as root:
            r = reports.compose(root, j, "2026-08")
            md = reports.to_markdown(r, j, "")
        self.assertIn("| winrate (BE not counted) | - |", md)
        self.assertIn("1 day had trades", md)

    def test_the_shelf_runs_from_the_first_closed_trade_to_now(self):
        from plainbook import reports
        accounts = {"broker": Account(id="broker", start_balance=10000)}
        j = Journal(accounts, [self.trade(3, 100)], [])
        now = datetime(2026, 10, 5)
        self.assertEqual(reports.periods(j, "month", now), ["2026-08", "2026-09", "2026-10"])
        self.assertEqual(reports.periods(j, "quarter", now), ["2026-Q3", "2026-Q4"])
        self.assertEqual(reports.periods(Journal(accounts, [], []), "month", now), [])
        self.assertEqual(reports.next_period("2026-12"), "2027-01")
        self.assertEqual(reports.next_period("2026-Q4"), "2027-Q1")
        self.assertEqual(reports.previous_period("2027-Q1"), "2026-Q4")

    def test_open_positions_stand_only_beside_the_running_period(self):
        from plainbook import reports
        accounts = {"broker": Account(id="broker", start_balance=10000)}
        # a swing carried over the end of May and closed in June, and one
        # position open now, entered in August
        carried = Trade(id="c", account="broker", pair="EURUSD", direction="long",
                        style="swing", risk=1.0, opened=datetime(2026, 5, 20, 9),
                        closed=datetime(2026, 6, 2, 12), result="Win", pnl=100)
        live = Trade(id="o", account="broker", pair="EURUSD", direction="long",
                     style="swing", risk=1.0, opened=datetime(2026, 8, 28, 9))
        j = Journal(accounts, [self.trade(3, 100), carried, live], [])
        now = datetime(2026, 9, 6)
        # a finished period shows nothing in blue, whatever ran across its end
        self.assertEqual(reports.still_open(j, "2026-05", now), [])
        self.assertEqual(reports.still_open(j, "2026-08", now), [])
        self.assertEqual(reports.still_open(j, "2026-Q2", now), [])
        # the running month and quarter carry the position open now
        self.assertEqual([t.id for t in reports.still_open(j, "2026-09", now)], ["o"])
        self.assertEqual([t.id for t in reports.still_open(j, "2026-Q3", now)], ["o"])

    def test_the_tape_draws_one_bar_per_trade(self):
        self.assertIn("No closed trades", H.tape_svg([], []))
        bars = [(2.1, "Win", "/trade/a", "a"), (-1.0, "Lose", "/trade/b", "b"),
                (-0.05, "BE", "/trade/c", "c"), (-1.6, "Lose", "/trade/d", "d")]
        svg = H.tape_svg(bars, [(0, "W32"), (2, "W33")])
        self.assertEqual(svg.count("<a href="), 4)
        self.assertIn(">stop<", svg)
        self.assertIn(">W32<", svg)
        self.assertIn(f'fill="{H.WARN}"', svg)                  # the break-even tick
        # the scale reaches past the deepest loss and never stops short of -1.5
        self.assertIn(">-2<", svg)


if __name__ == "__main__":
    unittest.main()
