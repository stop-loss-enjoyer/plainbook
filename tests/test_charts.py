#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The pictures: what the smoothing is allowed to do, and how R is split."""
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


class RSplitCase(unittest.TestCase):
    def setUp(self):
        self.accounts = {"bybit": Account(id="bybit", start_balance=10000)}

    def trade(self, tid, result, pnl):
        return Trade(id=tid, account="bybit", pair="EURUSD", direction="long",
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

    def test_a_break_even_stays_out_of_both_rings(self):
        j = Journal(self.accounts, [self.trade("t1", "BE", 0)], [])
        losses, wins, be = stats.r_split(j, j.trades)
        self.assertEqual((sum(n for _, n, _ in losses),
                          sum(n for _, n, _ in wins), be), (0, 0, 1))


class DrawdownAndSlicesCase(unittest.TestCase):
    """Figures the reports lean on: the deepest fall, and a field held twice."""

    def journal(self, results):
        accounts = {"bybit": Account(id="bybit", start_balance=10000)}
        trades = []
        for i, (pnl, execution) in enumerate(results, 1):
            trades.append(Trade(
                id=f"t{i}", account="bybit", pair="EURUSD", direction="long",
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


if __name__ == "__main__":
    unittest.main()
