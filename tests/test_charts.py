#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The pictures: what the smoothing is allowed to do, and how R is split."""
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import html as H
from plainbook import stats
from plainbook.balances import Journal
from plainbook.html import smooth_path, spread_days
from plainbook.model import Account, Adjustment, Trade


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

    def test_exits_with_an_hour_keep_it_and_never_run_backwards(self):
        """Two exits of one afternoon used to be pushed past midnight, behind
        the next morning's exit, and the curve ran backwards between them."""
        pts = [(datetime(2026, 9, 18, 14, 30), 1), (datetime(2026, 9, 18, 16, 0), 2),
               (datetime(2026, 9, 19, 7, 0), 3)]
        self.assertEqual(spread_days(pts), pts)
        # the same moment twice is told apart by a minute, in order
        same = [(datetime(2026, 9, 18, 14, 30), 1), (datetime(2026, 9, 18, 14, 30), 2),
                (datetime(2026, 9, 18, 16, 0), 3)]
        out = spread_days(same)
        xs = [d for d, _ in out]
        self.assertEqual(len(set(xs)), 3)
        self.assertTrue(xs[0] < xs[1] < xs[2])
        self.assertTrue(all(d.date() == datetime(2026, 9, 18).date() for d in xs))

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

    def test_the_dots_on_the_line_are_the_trades_the_legend_counts(self):
        """Every dot stands in the bucket the tables count it in, so the line
        and the two legends under it can never disagree about a trade."""
        j = Journal(self.accounts, [
            self.trade("t1", "Lose", -100), self.trade("t2", "Lose", -30),
            self.trade("t3", "Win", 40), self.trade("t4", "Win", 350),
            self.trade("t5", "BE", -2),
        ], [])
        line = stats.r_line(j, j.trades)
        self.assertEqual([t.id for t, *_ in line], ["t1", "t2", "t5", "t3", "t4"])   # by R
        losses, wins, be = stats.r_split(j, j.trades)
        for pile, counted in (("Lose", losses), ("Win", wins)):
            for i, (_, n, sum_r) in enumerate(counted):
                mine = [r for _, r, p, b in line if p == pile and b == i]
                self.assertEqual(len(mine), n)
                self.assertAlmostEqual(sum(mine), sum_r)
        self.assertEqual(sum(1 for *_, p, _ in line if p == "BE"), be)
        svg = H.r_line_svg([(r, p, b, "/trade/" + t.id, t.id) for t, r, p, b in line],
                           [top for _, top in stats.loss_buckets(1.2)],
                           [top for _, top in stats.WIN_BUCKETS])
        self.assertEqual(svg.count("<circle"), 5)
        self.assertIn('<a href="/trade/t4">', svg)
        self.assertIn('data-tip="t5"', svg)

    def test_the_days_are_the_exits_and_the_weekdays_the_entries(self):
        """A day of the calendar is the exit's, a weekday the entry's."""
        timed = Trade(id="a", account="broker", pair="EURUSD", direction="long",
                      style="swing", risk=1.0, opened=datetime(2026, 8, 3, 14, 30),
                      opened_time=True, result="Win", pnl=200,
                      closed=datetime(2026, 8, 5, 9, 0), closed_time=True)
        dated = self.trade("b", "Lose", -100)
        j = Journal(self.accounts, [timed, dated], [])
        days = stats.by_exit_day(j, j.trades)
        self.assertEqual(sorted(days), [datetime(2026, 8, 2).date(), datetime(2026, 8, 5).date()])
        self.assertAlmostEqual(days[datetime(2026, 8, 5).date()].sum_r, j.r("a"))
        week = stats.by_entry_weekday(j, j.trades)
        self.assertEqual(sorted(week), [0, 5])           # a Monday and a Saturday
        self.assertEqual(stats.cumulative_r(j, j.trades), [0.0, -1.0, -1.0 + j.r("a")])

    def test_the_profit_factor_and_the_fall_in_money(self):
        """Money made against money lost; the fall of the balance from its
        high, a withdrawal not counted as one."""
        trades = [Trade(id=f"t{i}", account="broker", pair="EURUSD", direction="long",
                        style="swing", risk=1.0, opened=datetime(2026, 8, i),
                        result="Win" if p > 0 else "Lose", pnl=p,
                        closed=datetime(2026, 8, i))
                  for i, p in ((1, 500), (2, -300), (3, -200), (4, 400))]
        out = Adjustment(id="w", account="broker", kind="withdrawal", amount=-1000,
                         day=datetime(2026, 8, 5))
        j = Journal(self.accounts, trades, [out])
        s = stats.summary(j, j.trades)
        self.assertAlmostEqual(s.profit_factor, 900 / 500)
        f = stats.money_fall(j, "broker")
        self.assertEqual(f.worst, -500)                  # 10 500 down to 10 000
        self.assertAlmostEqual(f.share, -500 / 10500 * 100)
        self.assertEqual(f.trough_at, datetime(2026, 8, 3))

    def test_the_prices_read_in_r(self):
        """The stop is 1 R by price, whatever the pair and the side."""
        t = Trade(id="p", account="broker", pair="USDJPY", direction="short",
                  style="swing", risk=1.0, opened=datetime(2026, 8, 1),
                  result="Win", pnl=200, closed=datetime(2026, 8, 2),
                  entry_price=150.0, stop_price=150.5, target_price=148.5,
                  exit_price=149.0, best_price=148.25, worst_price=150.25)
        p = stats.prices(t)
        self.assertAlmostEqual(p.planned, 3.0)
        self.assertAlmostEqual(p.taken, 2.0)
        self.assertAlmostEqual(p.best, 3.5)
        self.assertAlmostEqual(p.worst, -0.5)
        self.assertAlmostEqual(p.left, 1.5)
        self.assertTrue(p.reached)
        ps = stats.price_summary([t, self.trade("q", "Lose", -100)])
        self.assertEqual((ps.trades, ps.reached), (1, 1))
        self.assertAlmostEqual(ps.mean(ps.left), 1.5)
        self.assertIsNone(stats.prices(self.trade("q", "Lose", -100)))

    def test_a_month_names_every_day_under_the_pointer(self):
        day = datetime(2026, 8, 5).date()
        svg = H.month_days_svg(2026, 8, {day: (2.0, "Wed 05.08.2026\n+2.00 R")}, 2.0)
        self.assertIn('data-tip="Wed 05.08.2026\n+2.00 R"', svg)
        self.assertIn("no trade closed", svg)                # an empty day says so
        self.assertEqual(svg.count("data-tip="), 31)

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

    def test_the_stop_edge_moves_the_cut_of_the_losses(self):
        """The owner sets where a stop ends: the same five losses fall into
        other buckets at another edge, and at an edge of exactly 1 the stop
        bucket is gone, since nothing could stand in it."""
        trades = [
            self.trade("t1", "Lose", -100),      # -1.00 R
            self.trade("t2", "Lose", -115),      # -1.15 R
            self.trade("t3", "Lose", -120),      # -1.20 R
            self.trade("t4", "Lose", -250),      # -2.50 R
            self.trade("t5", "Lose", -99),       # -0.99 R
        ]
        j = Journal(self.accounts, trades, [], stop_edge=1.1)
        losses, _, _ = stats.r_split(j, j.trades)
        self.assertEqual([(label, n) for label, n, _ in losses],
                         [("0…-0.5", 0), ("-0.5…-1", 1), ("-1…-1.1", 1),
                          ("-1.1R and worse", 3)])
        self.assertEqual([t.id for t in stats.past_stop(j, j.trades)], ["t4", "t3", "t2"])
        self.assertAlmostEqual(stats.past_stop_over(j, trades[1]), -0.05, 4)
        j = Journal(self.accounts, trades, [], stop_edge=1.0)
        losses, _, _ = stats.r_split(j, j.trades)
        self.assertEqual([(label, n) for label, n, _ in losses],
                         [("0…-0.5", 0), ("-0.5…-1", 1), ("-1R and worse", 4)])
        self.assertEqual(len(stats.past_stop(j, j.trades)), 4)
        self.assertAlmostEqual(stats.past_stop_over(j, trades[0]), 0.0, 4)

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

    def test_the_stops_moved_to_the_entry_stand_against_the_rest(self):
        """Four trades moved, two not. The moved ones are summed on their
        own, and the move is timed only where the entry carries an hour."""
        import tempfile
        from plainbook import reports
        accounts = {"broker": Account(id="broker", start_balance=10000)}
        at = lambda i, h: datetime(2026, 8, i, h)
        timed = dict(opened_time=True, closed_time=True)
        trades = [self.trade(1, 200, breakeven=at(1, 11), **timed),  # won, moved at half the hold
                  self.trade(2, 0, breakeven=at(2, 11), **timed),
                  self.trade(3, 0, breakeven=at(3, 11), **timed),    # stopped at the entry
                  self.trade(4, -120, breakeven=at(4, 11), **timed), # lost after the move
                  self.trade(5, 150, **timed),                       # the stop stayed
                  self.trade(6, -100, **timed)]
        trades[1].pnl = -5                                     # a BE a few dollars under
        b = stats.breakeven_split(Journal(accounts, trades, []), trades)
        self.assertEqual((b.moved.trades, b.moved.wins, b.moved.be, b.moved.losses),
                         (4, 1, 2, 1))
        self.assertEqual(b.stayed.trades, 2)
        self.assertEqual(b.median_hours, 1.0)
        self.assertAlmostEqual(b.median_share, 0.5)
        # an entry without an hour is not timed, and an open trade is not counted
        trades[0].opened_time = False
        live = Trade(id="o", account="broker", pair="EURUSD", direction="long",
                     style="swing", risk=1.0, opened=datetime(2026, 8, 7, 9),
                     breakeven=datetime(2026, 8, 7, 12))
        b = stats.breakeven_split(Journal(accounts, trades + [live], []), trades + [live])
        self.assertEqual(len(b.hours), 3)
        self.assertEqual(b.moved.trades, 4)
        # the report carries the split, and its file says it in one sentence
        with tempfile.TemporaryDirectory() as root:
            r = reports.compose(root, Journal(accounts, trades, []), "2026-08")
            text = reports.to_markdown(r, Journal(accounts, trades, []), "")
        self.assertEqual(r.breakeven.moved.trades, 4)
        self.assertIn("Stop moved to breakeven on 4 of 6 trades: 1 won, "
                      "2 stopped at the entry, 1 lost after it", text)
        self.assertIn("the stop stayed on 2", text)
        # a period with no moved trade says nothing about them
        with tempfile.TemporaryDirectory() as root:
            r = reports.compose(root, Journal(accounts, trades[4:], []), "2026-08")
            text = reports.to_markdown(r, Journal(accounts, trades[4:], []), "")
        self.assertNotIn("breakeven", text)

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

    def test_a_day_is_counted_by_the_entry_not_by_what_closed_on_it(self):
        """The card is written on the day the trades were taken. A position
        that closed by itself the next morning does not make that morning a
        day worked, and one entered on the last day of a month stays in that
        month even though it paid in the next."""
        import tempfile
        from plainbook import reports

        def trade(i, opened, closed):
            return Trade(id=i, account="broker", pair="EURUSD", direction="long",
                         style="swing", risk=1.0, opened=opened, closed=closed,
                         result=None if closed is None else "Win",
                         pnl=None if closed is None else 100)

        accounts = {"broker": Account(id="broker", start_balance=10000)}
        j = Journal(accounts, [trade("a", datetime(2026, 8, 3, 10), datetime(2026, 8, 4, 9)),
                               trade("b", datetime(2026, 8, 3, 15), datetime(2026, 9, 1, 9)),
                               trade("c", datetime(2026, 8, 31, 11), datetime(2026, 9, 2, 9)),
                               trade("d", datetime(2026, 8, 5, 12), None)], [])
        with tempfile.TemporaryDirectory() as root:
            august = reports.compose(root, j, "2026-08")
            september = reports.compose(root, j, "2026-09")
        # entries on the 3rd, twice, the 5th and the 31st: three days worked
        self.assertEqual(august.days_traded, 3)
        # September closed two of them and was never traded in
        self.assertEqual(september.days_traded, 0)

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
        self.assertIn("1 day had entries", md)

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


class SelectionCase(unittest.TestCase):
    """The figures the Statistics tab leans on: what a win is worth against a
    loss, how long a position is carried, and how a run of periods reads."""

    def setUp(self):
        self.accounts = {"broker": Account(id="broker", start_balance=10000)}

    def trade(self, tid, result, pnl, opened, closed, **over):
        return Trade(id=tid, account="broker", pair="EURUSD", direction="long",
                     style="swing", risk=1.0, opened=opened, closed=closed,
                     result=result, pnl=pnl, **over)

    def journal(self, trades):
        return Journal(self.accounts, trades, [])

    def month(self, results, month=8):
        return self.journal([
            self.trade(f"t{i}", "Win" if pnl > 0 else "Lose" if pnl < 0 else "BE",
                       pnl, datetime(2026, month, i), datetime(2026, month, i))
            for i, pnl in enumerate(results, 1)])

    def test_the_payoff_weighs_a_win_against_a_loss(self):
        j = self.month([200, -100, 100, -100])
        s = stats.summary(j, j.trades)
        self.assertAlmostEqual(s.average_win, s.sum_r_win / 2)
        self.assertAlmostEqual(s.average_loss, s.sum_r_lose / 2)
        self.assertAlmostEqual(s.payoff, s.average_win / -s.average_loss)
        self.assertGreater(s.payoff, 1.4)                # two R won against one lost
        # nothing to weigh with only one side of the market answered
        wins = self.journal([self.trade("w", "Win", 100, datetime(2026, 8, 1),
                                        datetime(2026, 8, 1))])
        self.assertIsNone(stats.summary(wins, wins.trades).payoff)
        self.assertIsNone(stats.summary(wins, wins.trades).needed_wr)

    def test_the_winrate_needed_charges_the_break_evens_in(self):
        """The figure has to agree with the sign of the EV, or two tiles of one
        strip say opposite things about the same trades."""
        results = [100] * 10 + [-100] * 10 + [-10] * 10
        j = self.journal([
            self.trade(f"t{i}", "Win" if pnl > 0 else "Lose" if pnl < -50 else "BE",
                       pnl, datetime(2026, 8, 1 + i // 3), datetime(2026, 8, 1 + i // 3))
            for i, pnl in enumerate(results)])
        s = stats.summary(j, j.trades)
        self.assertEqual(s.wr, 50.0)
        self.assertLess(s.average_r, 0)             # the break-evens paid for it
        self.assertGreater(s.needed_wr, 50.0)       # so the winrate is not enough
        # the textbook figure, worked out without them, says the winrate is
        # enough while the EV says it is not
        self.assertLess(100 / (1 + s.payoff), s.wr)
        self.assertLess(100 / (1 + s.payoff), s.needed_wr)

    def test_a_winrate_off_a_handful_of_trades_is_thin(self):
        j = self.month([100, -100, 100, -100])
        self.assertTrue(stats.summary(j, j.trades).thin)
        j = self.month([100, -100, 100, -100, 100])
        self.assertFalse(stats.summary(j, j.trades).thin)

    def test_the_fall_says_when_it_happened_and_whether_it_came_back(self):
        j = self.month([200, -100, -100, 100, 200])
        f = stats.drawdown(j, j.trades)
        self.assertAlmostEqual(f.worst, stats.drawdown_r(j, j.trades))
        self.assertLess(f.worst, -1.9)
        self.assertEqual(f.peak_at, datetime(2026, 8, 1))    # the high it fell from
        self.assertEqual(f.trough_at, datetime(2026, 8, 3))
        self.assertEqual(f.back_at, datetime(2026, 8, 5))
        self.assertAlmostEqual(f.now, 0.0)                   # ends on its high
        # a hole that is still open has no day it was made back on
        j = self.month([200, -100, -100])
        f = stats.drawdown(j, j.trades)
        self.assertIsNone(f.back_at)
        self.assertLess(f.now, 0)
        # a run that only goes up never fell
        f = stats.drawdown(*(lambda k: (k, k.trades))(self.month([100, 100])))
        self.assertEqual((f.worst, f.peak_at, f.back_at), (0.0, None, None))

    def test_a_period_that_closed_nothing_keeps_its_place(self):
        j = self.journal([
            self.trade("a", "Win", 100, datetime(2026, 7, 20), datetime(2026, 7, 21)),
            self.trade("b", "Lose", -100, datetime(2026, 9, 1), datetime(2026, 9, 2))])
        rows = stats.by_period(j, j.trades, "month")
        self.assertEqual([key for key, _ in rows], ["2026-07", "2026-08", "2026-09"])
        self.assertEqual([s.trades for _, s in rows], [1, 0, 1])
        # a quarter holds them both, a week keeps the gap between them
        self.assertEqual([key for key, _ in stats.by_period(j, j.trades, "quarter")],
                         ["2026-Q3"])
        weeks = stats.by_period(j, j.trades, "week")
        self.assertEqual(weeks[0][0], "2026-W30")
        self.assertEqual(weeks[-1][0], "2026-W36")
        self.assertEqual(sum(s.trades for _, s in weeks), 2)
        self.assertEqual(stats.by_period(j, [], "month"), [])

    def test_a_period_key_names_its_grain_and_cuts_by_the_exit(self):
        j = self.journal([
            self.trade("in", "Win", 100, datetime(2026, 7, 30), datetime(2026, 8, 3)),
            self.trade("out", "Lose", -100, datetime(2026, 8, 1), datetime(2026, 9, 1))])
        self.assertEqual(stats.grain_of("2026-W36"), "week")
        self.assertEqual(stats.grain_of("2026-08"), "month")
        self.assertEqual(stats.grain_of("2026-Q3"), "quarter")
        self.assertIsNone(stats.grain_of("august"))
        # by the exit: the trade entered in July belongs to August
        self.assertEqual([t.id for t in stats.closed_in(j.trades, "2026-08")], ["in"])
        self.assertEqual([t.id for t in stats.closed_in(j.trades, "2026-09")], ["out"])
        self.assertEqual(len(stats.closed_in(j.trades, "2026-Q3")), 2)
        # a key that is not a period leaves the selection alone
        self.assertEqual(len(stats.closed_in(j.trades, "august")), 2)
        self.assertEqual(len(stats.closed_in(j.trades, "")), 2)
        # the shape of a key is not enough: a thirteenth month and a week
        # the year does not have name no period either
        for key in ("2026-13", "2026-00", "2025-W53", "2026-W00", "2026-Q5"):
            self.assertIsNone(stats.grain_of(key), key)
            self.assertIsNone(stats.period_bounds(key), key)
        self.assertEqual(stats.period_bounds("2026-W01"),
                         (datetime(2025, 12, 29), datetime(2026, 1, 5)))
        self.assertEqual(stats.period_bounds("2026-08"),
                         (datetime(2026, 8, 1), datetime(2026, 9, 1)))
        self.assertEqual(stats.period_bounds("2026-Q4"),
                         (datetime(2026, 10, 1), datetime(2027, 1, 1)))

    def test_a_week_that_straddles_the_new_year_keeps_its_iso_year(self):
        j = self.journal([
            self.trade("a", "Win", 100, datetime(2025, 12, 22), datetime(2025, 12, 28)),
            self.trade("b", "Lose", -100, datetime(2026, 1, 5), datetime(2026, 1, 6))])
        rows = stats.by_period(j, j.trades, "week")
        self.assertEqual([key for key, _ in rows], ["2025-W52", "2026-W01", "2026-W02"])
        self.assertEqual([s.trades for _, s in rows], [1, 0, 1])
        # a bar of the picture finds exactly the trades it was drawn from
        for key, s in rows:
            self.assertEqual(len(stats.closed_in(j.trades, key)), s.trades, key)
        self.assertEqual([key for key, _ in stats.by_period(j, j.trades, "quarter")],
                         ["2025-Q4", "2026-Q1"])

    def test_the_fall_is_dated_from_the_last_time_the_curve_stood_on_its_high(self):
        # +2, -1, +1 puts the curve back on its high on the third day: the
        # fall that follows began there, not on the first
        j = self.month([200, -100, 100, -300, 300])
        f = stats.drawdown(j, j.trades)
        self.assertEqual(f.peak_at, datetime(2026, 8, 3))
        self.assertEqual(f.trough_at, datetime(2026, 8, 4))
        self.assertEqual(f.back_at, datetime(2026, 8, 5))
        # two losses first: the high it fell from is the start, not a trade
        j = self.month([-100, -100, 250])
        f = stats.drawdown(j, j.trades)
        self.assertIsNone(f.peak_at)
        self.assertEqual(f.trough_at, datetime(2026, 8, 2))
        self.assertEqual(f.back_at, datetime(2026, 8, 3))

    def test_a_curve_cut_to_a_period_ends_with_it(self):
        j = Journal(self.accounts, [
            self.trade("a", "Win", 100, datetime(2026, 8, 1), datetime(2026, 8, 2))],
            [Adjustment(id="dep", day=datetime(2026, 9, 3), account="broker", kind="deposit",
                        amount=500, comment="")])
        walk = stats.equity_events(j, "broker", j.trades, datetime(2026, 8, 1),
                                   datetime(2026, 9, 1))
        self.assertEqual([what for _, _, what in walk], ["since", None])
        self.assertEqual(walk[-1][1], 10100)
        # without an end the deposit of September steps the line
        walk = stats.equity_events(j, "broker", j.trades, datetime(2026, 8, 1))
        self.assertEqual(walk[-1][1], 10600)
        # the end holds for the trades too, selection or none: the walk of a
        # whole account must not step on a trade closed after the period
        j = Journal(self.accounts, [
            self.trade("in", "Win", 100, datetime(2026, 8, 1), datetime(2026, 8, 2)),
            self.trade("out", "Win", 700, datetime(2026, 8, 30), datetime(2026, 9, 1))], [])
        walk = stats.equity_events(j, "broker", None, datetime(2026, 8, 1),
                                   datetime(2026, 9, 1))
        self.assertEqual(walk[-1][1], 10100)

    def test_a_period_counts_the_trade_that_closed_in_it(self):
        """A trade carried across the edge belongs to the month it closed in,
        the way a report counts it."""
        j = self.journal([self.trade("a", "Win", 100, datetime(2026, 7, 30),
                                     datetime(2026, 8, 3))])
        self.assertEqual([key for key, _ in stats.by_period(j, j.trades, "month")],
                         ["2026-08"])

    def test_how_long_a_position_was_carried(self):
        days = [(0, "same day"), (1, "1 to 2 days"), (2, "1 to 2 days"),
                (3, "3 to 5 days"), (5, "3 to 5 days"), (6, "6 days or more")]
        trades = [self.trade(f"t{n}", "Win", 100, datetime(2026, 8, 1, 9),
                             datetime(2026, 8, 1) + timedelta(days=n))
                  for n, _ in days]
        j = self.journal(trades)
        for t, (n, label) in zip(trades, days):
            self.assertEqual(stats.held_days(t), n)
            self.assertEqual(stats.by_hold(j, [t])[0][0], label)
        # the buckets come out in the order of their length, not of their size
        self.assertEqual([label for label, _ in stats.by_hold(j, j.trades)],
                         ["same day", "1 to 2 days", "3 to 5 days", "6 days or more"])
        # an open trade has no length yet
        live = Trade(id="o", account="broker", pair="EURUSD", direction="long",
                     style="swing", risk=1.0, opened=datetime(2026, 8, 28))
        self.assertIsNone(stats.held_days(live))

    def test_the_checklist_counts_only_what_was_ticked(self):
        clean = self.trade("clean", "Win", 100, datetime(2026, 8, 1),
                           datetime(2026, 8, 1), playbook="pull", deviations=[])
        broke = self.trade("broke", "Lose", -100, datetime(2026, 8, 2),
                           datetime(2026, 8, 2), playbook="pull", deviations=[2])
        loose = self.trade("loose", "Win", 100, datetime(2026, 8, 3),
                           datetime(2026, 8, 3), playbook="pull")
        live = Trade(id="o", account="broker", pair="EURUSD", direction="long",
                     style="swing", risk=1.0, opened=datetime(2026, 8, 28),
                     playbook="pull", deviations=[])
        j = self.journal([clean, broke, loose, live])
        c = stats.checklist(j, j.trades)
        self.assertEqual((c.ticked, c.unticked), (2, 1))     # the open one is out
        self.assertEqual((c.kept.trades, c.broke.trades), (1, 1))
        self.assertGreater(c.kept.average_r, c.broke.average_r)

    def test_a_loss_past_the_stop_is_the_one_the_rings_cut_out(self):
        # the balance is 10 000 and the risk 1%, so a loss of 120 is -1.2 R
        # exactly: it is past the stop, and 119 stands one hundredth short
        j = self.journal([
            self.trade("stop", "Lose", -119, datetime(2026, 8, 1), datetime(2026, 8, 1))])
        self.assertEqual(stats.past_stop(j, j.trades), [])
        j = self.journal([
            self.trade("edge", "Lose", -120, datetime(2026, 8, 1), datetime(2026, 8, 1))])
        self.assertEqual([t.id for t in stats.past_stop(j, j.trades)], ["edge"])
        # the deepest first, and an open position is not a loss yet
        live = Trade(id="o", account="broker", pair="EURUSD", direction="long",
                     style="swing", risk=1.0, opened=datetime(2026, 8, 2))
        j = self.journal([
            self.trade("edge", "Lose", -120, datetime(2026, 8, 1), datetime(2026, 8, 1)),
            self.trade("deep", "Lose", -300, datetime(2026, 8, 2), datetime(2026, 8, 2)),
            live])
        self.assertEqual([t.id for t in stats.past_stop(j, j.trades)], ["deep", "edge"])


    def test_an_overrun_costs_only_what_it_ran_past_the_stop(self):
        """The stop is the attempt and the attempt was allowed: -1 R is the
        plan working, and commission carries it to -1.2 R. Only what lies
        past that edge was lost to the risk being overrun."""
        # one trade a journal, so that the balance is 10 000 and the risk 1%
        # when it opens and the R of it is exact
        def only(pnl, result="Lose"):
            j = self.journal([self.trade("t", result, pnl,
                                         datetime(2026, 8, 1), datetime(2026, 8, 1))])
            return j, j.trades[0]
        # at the edge the loss reached the stop and did not pass it
        self.assertAlmostEqual(stats.past_stop_over(*only(-120)), 0.0, 4)
        self.assertAlmostEqual(stats.past_stop_over(*only(-135)), -0.15, 4)
        self.assertAlmostEqual(stats.past_stop_over(*only(-100)), 0.0, 4)
        # a win never overran anything, whatever it brought
        self.assertAlmostEqual(stats.past_stop_over(*only(200, "Win")), 0.0, 4)
        j = self.journal([
            self.trade("deep", "Lose", -135, datetime(2026, 8, 1), datetime(2026, 8, 1)),
            self.trade("also", "Lose", -140, datetime(2026, 8, 2), datetime(2026, 8, 2)),
            self.trade("won", "Win", 200, datetime(2026, 8, 3), datetime(2026, 8, 3))])
        past = stats.past_stop(j, j.trades)
        cost = stats.past_stop_cost(j, past)
        self.assertEqual(len(past), 2)
        self.assertAlmostEqual(cost, sum(stats.past_stop_over(j, t) for t in past), 9)
        # the price of the overruns and what those trades brought are two
        # different figures, and the overrun is the smaller of them by far
        self.assertGreater(cost, stats.summary(j, past).sum_r + 2.0)


class TapeCase(unittest.TestCase):
    """The tape draws trades and periods with the same code."""

    def test_a_period_that_closed_nothing_keeps_its_slot(self):
        bars = [(2.0, "Win", "/report/2026-07", "July"), (None, "", "", "August"),
                (-1.0, "Lose", "/report/2026-09", "September")]
        svg = H.tape_svg(bars, [(0, "2026")], stop=None)
        self.assertEqual(svg.count("<a href="), 2)      # the empty period draws none
        self.assertNotIn(">stop<", svg)                 # no stop under a sum of trades
        self.assertNotIn("stroke-dasharray", svg)

    def test_a_single_flat_bar_still_has_a_scale(self):
        svg = H.tape_svg([(0.0, "BE", "/x", "x")], [], stop=None)
        self.assertIn("<svg", svg)
        self.assertIn("No closed trades", H.tape_svg([(None, "", "", "")], [], stop=None))

    def test_a_bar_carries_its_name_while_there_is_room_for_one(self):
        names = [f"M{i}" for i in range(15)]
        bars = [(1.0, "Win", f"/p/{i}", n) for i, n in enumerate(names)]
        svg = H.tape_svg(bars, [(0, "2026")], width=810, stop=None, labels=names)
        for n in names:
            self.assertIn(f">{n}</text>", svg)
        # sixty bars in the same width leave no room, so only the marks stay
        many = [f"W{i}" for i in range(60)]
        svg = H.tape_svg([(1.0, "Win", "/p", n) for n in many], [(0, "Jul")],
                         width=810, stop=None, labels=many)
        self.assertNotIn(">W7</text>", svg)
        self.assertIn(">Jul</text>", svg)
        # a bar with no address is drawn and is not a link
        svg = H.tape_svg([(1.0, "Win", "", "edge"), (2.0, "Win", "/p", "in")], [],
                         stop=None)
        self.assertEqual(svg.count("<a href="), 1)
        self.assertEqual(svg.count("<rect"), 3)         # the ground and two bars


if __name__ == "__main__":
    unittest.main()
