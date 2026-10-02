#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The server faults of the 1.7 audit, each on a journal of its own: a number
put back into a form, the pictures of an update, a record that does not read,
a word that closes a script, a tick at the close."""
import hashlib
import importlib
import json
import os
import re
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import reports, store
from plainbook.model import (Account, Card, IdeaBlock, Note, Plan, Playbook, Rule,
                             Setup, Trade, Week)

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6360000002000100ffff0300000600"
    "05572bd6a20000000049454e44ae426082")


class FixesCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        store.save_account(cls.root, Account(id="broker", name="Broker",
                                             start_balance=10000))
        store.save_account(cls.root, Account(id="odd", name="Odd", kind="prop",
                                             start_balance=104327.55))
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

    # --- helpers ---
    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path):
        with urllib.request.urlopen(self.url(path)) as r:
            return r.status, r.read().decode("utf-8")

    def post(self, path, fields):
        data = urllib.parse.urlencode(fields, doseq=True).encode("utf-8")
        with urllib.request.urlopen(urllib.request.Request(self.url(path), data=data)) as r:
            return r.status, r.geturl()

    def answer(self, path, fields=None):
        """The code and the page, a refusal included."""
        data = (None if fields is None else
                urllib.parse.urlencode(fields, doseq=True).encode("utf-8"))
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url(path), data=data)) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read().decode("utf-8")

    def token(self, html):
        return re.search(r'name="token" value="([0-9a-f]{16})"', html).group(1)

    def value(self, html, name):
        return re.search(rf'name="{name}"[^>]*?value="([^"]*)"', html, re.S).group(1)

    def trade(self, trade_id, **over):
        fields = dict(id=trade_id, account="broker", pair="EURUSD", direction="long",
                      style="swing", entry_tf="H4", risk=1.0,
                      opened=datetime.strptime(trade_id[:10] + " 10:00", "%Y-%m-%d %H:%M"),
                      opened_time=True,
                      idea=[IdeaBlock(tf="H4", text="an idea")])
        fields.update(over)
        t = Trade(**fields)
        store.save_trade(self.root, t)
        self.S.drop_cache()
        return t

    def broken(self, path, line, replace):
        """Spoils one line of a record file; gives back what it held."""
        with open(path) as f:
            was = f.read()
        with open(path, "w") as f:
            f.write(re.sub(line, replace, was, count=1, flags=re.M))
        self.S.drop_cache()
        return was

    def put_back(self, path, text):
        with open(path, "w") as f:
            f.write(text)
        self.S.drop_cache()

    # --- 1: the rules form keeps every digit ---
    def test_rules_round_trip_to_the_digit(self):
        self.post("/account/odd/rules", {"kind": "prop", "firm": "X", "daily": "5%",
                                         "max": "10%", "target": "8%", "mode": "static"})
        self.assertEqual(store.all_accounts(self.root)["odd"].max_loss, 10432.75)
        _, html = self.get("/account/odd/rules")
        self.assertEqual(self.value(html, "max"), "10432.75")
        form = {"kind": "prop", "firm": "Y", "mode": "static"}
        for name in ("daily", "max", "target"):
            form[name] = self.value(html, name)
        self.post("/account/odd/rules", form)
        a = store.all_accounts(self.root)["odd"]
        self.assertEqual((a.daily_loss_limit, a.max_loss, a.profit_target),
                         (5216.38, 10432.75, 8346.2))
        self.post("/account/odd/rules", {"kind": "prop", "max": "1234567.89",
                                         "mode": "static"})
        self.assertEqual(self.value(self.get("/account/odd/rules")[1], "max"),
                         "1234567.89")

    # --- 13, 28: a PnL keeps its cents in the forms and the CSV ---
    def test_pnl_is_put_back_as_the_file_holds_it(self):
        self.trade("2026-08-25-01-gbpusd", pair="GBPUSD", result="Win",
                   pnl=12345.67, closed=datetime(2026, 8, 26, 12, 0), risk=0.0959)
        _, html = self.get("/edit/2026-08-25-01-gbpusd")
        self.assertEqual(self.value(html, "pnl"), "12345.67")
        self.assertEqual(self.value(html, "risk"), "0.0959")
        with urllib.request.urlopen(self.url("/export.csv?pair=GBPUSD")) as r:
            line = [x for x in r.read().decode("utf-8").splitlines()
                    if x.startswith("2026-08-25-01-gbpusd")][0]
        self.assertIn(",12345.67,", line)
        store.save_card(self.root, Card(day=date(2026, 8, 20), pnl=123456.78))
        self.assertEqual(self.value(self.get("/card/2026-08-20")[1], "pnl"), "123456.78")
        store.save_week(self.root, Week(week="2026-W33", pnl=1234567.5))
        self.assertEqual(self.value(self.get("/week/2026-W33")[1], "pnl"), "1234567.5")

    # --- 2: the daily limit is set where the rules are ---
    def test_the_old_limit_route_is_gone(self):
        self.assertEqual(self.answer("/account/limit", {"id": "broker", "limit": "50"})[0],
                         404)
        self.post("/account/new", {"id": "with-limit", "start": "1000", "limit": "50"})
        self.assertIsNone(store.all_accounts(self.root)["with-limit"].daily_loss_limit)

    # --- 12: an update picture removed takes only its own link ---
    def test_removing_the_first_update_picture_keeps_the_second_in_place(self):
        t = self.trade("2026-08-27-01-usdjpy", pair="USDJPY",
                       updates="**01.09** moved stop\n![](shots/update-01.png)\n\n"
                               "**02.09** partial\n![](shots/update-02.png)")
        shots = os.path.join(store.trade_dir(self.root, t.id), store.SHOTS)
        os.makedirs(shots)
        for n in (1, 2):
            with open(os.path.join(shots, f"update-0{n}.png"), "wb") as f:
                f.write(PNG + bytes([n]))
        second = hashlib.md5(PNG + bytes([2])).hexdigest()
        _, html = self.get(f"/edit/{t.id}")
        self.post(f"/edit/{t.id}", {
            "token": self.token(html), "blocks": "1", "account": "broker",
            "pair": "USDJPY", "direction": "long", "style": "swing", "entry_tf": "H4",
            "risk": "1", "entry": "2026-08-27T10:00", "idea_tf_1": "H4",
            "idea_text_1": "an idea", "updates": t.updates,
            "have_update": "shots/update-02.png"})
        after = store.load_trade(self.root, t.id).updates
        self.assertEqual(after, "**01.09** moved stop\n\n\n**02.09** partial\n"
                                "![](shots/update-01.png)")
        with open(os.path.join(shots, "update-01.png"), "rb") as f:
            self.assertEqual(hashlib.md5(f.read()).hexdigest(), second)
        self.assertFalse(os.path.exists(os.path.join(shots, "update-02.png")))

    def test_the_plan_form_matches_its_update_pictures_by_name(self):
        k = Plan(id="2026-08-24-eurusd", title="names", pair="EURUSD",
                 narrative="bullish", day=datetime(2026, 8, 24),
                 updates="**25.08** first\n![](shots/update-01.png)\n\n"
                         "**26.08** second\n![](shots/update-02.png)")
        store.save_plan(self.root, k)
        shots = os.path.join(store.plan_dir(self.root, k.id), store.SHOTS)
        os.makedirs(shots)
        for n in (1, 2):
            with open(os.path.join(shots, f"update-0{n}.png"), "wb") as f:
                f.write(PNG + bytes([n]))
        _, html = self.get(f"/plan/{k.id}/edit")
        self.post(f"/plan/{k.id}/edit", {
            "token": self.token(html), "title": "names", "pair": "EURUSD",
            "narrative": "bullish", "from": "2026-08-24", "blocks": "0",
            "updates": k.updates, "have_update": "shots/update-02.png"})
        after = store.load_plan(self.root, k.id).updates
        self.assertTrue(after.endswith("**26.08** second\n![](shots/update-01.png)"), after)
        self.assertNotIn("first\n![]", after)

    # --- 17: a save waiting for a picture keeps the form guarded ---
    def test_a_waiting_save_marks_the_form_unsaved(self):
        _, html = self.get("/new")
        waiting = html[html.index("if (!uploading) return;"):]
        waiting = waiting[:waiting.index("});")]
        self.assertIn("window.form_changed(e.target)", waiting)

    # --- 18: a refused save says how to go back and what is lost ---
    def test_a_refused_save_offers_the_way_back(self):
        _, html = self.get("/new")
        code, page = self.answer("/new", {
            "token": self.token(html), "blocks": "1", "account": "broker",
            "pair": "EURUSD", "direction": "long", "style": "swing", "entry_tf": "H4",
            "risk": "abc", "entry": "2026-08-29T14:30", "idea_tf_1": "H4",
            "idea_text_1": "typed", "file_idea-1": "0123456789abcdef.png"})
        self.assertEqual(code, 400)
        self.assertIn('onclick="history.back(); return false"', page)
        self.assertIn('<a href="/">Back to journal</a>', page)
        self.assertIn("paste them again", page)
        code, page = self.answer("/plan/new", {"token": "x", "from": "2026-13-45"})
        self.assertEqual(code, 400)
        self.assertNotIn("paste them again", page)

    # --- 19: the list of a shared document scrolls inside its card ---
    def test_the_shared_list_scrolls_inside_its_card(self):
        self.trade("2026-08-28-01-audusd", pair="AUDUSD")
        _, html = self.get("/share/journal")
        self.assertIn('<div class="wide"><table class="list">', html)
        phone = html[html.index("@media (max-width:760px)"):]
        self.assertIn(".wide{overflow-x:auto}", phone[:phone.index("\n}")])

    # --- 21, 22: a plan that does not read stops nothing ---
    def test_a_broken_plan_leaves_the_forms_and_its_share_standing(self):
        k = Plan(id="2026-08-10-gbpusd", title="broken", pair="GBPUSD",
                 day=datetime(2026, 8, 10))
        store.save_plan(self.root, k)
        t = self.trade("2026-08-11-01-nzdusd", pair="NZDUSD")
        path = os.path.join(store.plan_dir(self.root, k.id), "plan.md")
        was = self.broken(path, r"^from: .*$", "from: 2026-13-45")
        try:
            self.assertEqual(self.get("/new")[0], 200)
            self.assertEqual(self.get(f"/edit/{t.id}")[0], 200)
            code, html = self.get(f"/share/plan/{k.id}")
            self.assertEqual(code, 200)
            self.assertIn("This record could not be read", html)
        finally:
            self.put_back(path, was)

    # --- 24: a word of the owner's cannot close a script ---
    def test_a_style_word_does_not_close_the_note_script(self):
        word = "</script><b id=pwnS>"
        t = self.trade("2026-08-12-01-eurgbp", pair="EURGBP", style=word)
        store.save_note(self.root, Note(id="2026-08-12-note", title="note",
                                        day=datetime(2026, 8, 12), trades=[t.id]))
        _, html = self.get("/note/2026-08-12-note/edit")
        self.assertNotIn("</script><b id=pwnS>", html)
        self.assertIn("\\u003c/script>\\u003cb id=pwnS>", html)
        self.assertEqual(json.loads(self.S.js(word)), word)

    # --- 26: a report is shared while a card does not read ---
    def test_a_report_is_shared_with_a_broken_card(self):
        self.trade("2026-07-06-01-eurusd", result="Win", pnl=50, closed=datetime(2026, 7, 7, 9, 0))
        reports.build(self.root, self.S.journal(True), "2026-07", problems=[])
        store.save_card(self.root, Card(day=date(2026, 7, 8), pnl=10))
        path = store.card_path(self.root, date(2026, 7, 8))
        was = self.broken(path, r"^date: .*$", "date: 2026-07-32")
        try:
            self.assertEqual(self.get("/report/2026-07")[0], 200)
            self.assertEqual(self.get("/share/report/2026-07")[0], 200)
        finally:
            self.put_back(path, was)

    # --- 27: management ticked only at the close names the version ---
    def test_a_tick_at_the_close_holds_the_version(self):
        store.save_playbook(self.root, Playbook(
            id="mgmt", name="Mgmt", styles=["swing"], version="1.0",
            setups=[Setup(rules=[Rule(1, "Trend")])],
            management=[Rule(2, "Stop never moved"), Rule(3, "Held to target")]))
        t = self.trade("2026-08-13-01-gbpjpy", pair="GBPJPY", playbook="mgmt")
        self.assertEqual(self.S.trades_under(self.S.journal(True), "mgmt", "1.0"), [])
        _, html = self.get(f"/close/{t.id}")
        self.post(f"/close/{t.id}", {"token": self.token(html), "result": "Win",
                                     "pnl": "100", "exit": "2026-08-14T10:00",
                                     "conclusions": "", "held_mgmt": "2"})
        after = store.load_trade(self.root, t.id)
        self.assertEqual((after.exit_deviations, after.playbook_version), ([3], "1.0"))
        self.assertIsNone(after.deviations)
        under = self.S.trades_under(self.S.journal(True), "mgmt", "1.0")
        self.assertEqual([x.id for x in under], [t.id])


if __name__ == "__main__":
    unittest.main()
