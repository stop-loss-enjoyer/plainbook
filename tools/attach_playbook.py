#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tie the trades a playbook was already being traded by to the playbook.

A playbook is usually written down for a way of trading that has been going
on for a while, and its `since` date says which trades it counts. This tool
gives those trades the playbook: every trade of one of the playbook's styles
opened on or after that date, which does not carry a playbook yet. No
version, no setup and no deviations are written: nobody ticked the rules for
these trades, and the statistics cannot pretend otherwise. A trade takes the
version of the playbook on the day its rules are ticked. Open each such trade
and fill them in if you remember.

    python3 tools/attach_playbook.py <journal root> <playbook id>          # what would change
    python3 tools/attach_playbook.py <journal root> <playbook id> --apply  # write it

Prints counts only, never the trades. Running it twice changes nothing the
second time.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import store


def candidates(root, p):
    styles = set(p.styles)
    for t in store.all_trades(root):
        if t.playbook or t.style not in styles:
            continue
        if p.since is not None and t.opened.date() < p.since.date():
            continue
        yield t


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    root, playbook_id, apply = argv[1], argv[2], "--apply" in argv
    p = store.load_playbook(root, playbook_id).check()
    if not p.styles:
        print(f"{p.id}: the playbook names no styles, so no trade can be told to be its")
        return 1
    found = list(candidates(root, p))
    by_account, by_style = {}, {}
    for t in found:
        by_account[t.account] = by_account.get(t.account, 0) + 1
        by_style[t.style] = by_style.get(t.style, 0) + 1
    since = f"{p.since:%Y-%m-%d}" if p.since else "the beginning"
    print(f"{p.id} {p.version or ''}: styles {', '.join(p.styles)}, since {since}")
    print(f"trades to tie: {len(found)}")
    for name, count in sorted(by_account.items()):
        print(f"  {name}: {count}")
    for name, count in sorted(by_style.items()):
        print(f"  {name}: {count}")
    if not apply:
        print("nothing written; add --apply to write")
        return 0
    for t in found:
        # the playbook only: a version is held by a trade that was ticked
        # against it (invariant 13), and the first tick writes it
        t.playbook = p.id
        store.save_trade(root, t)
    print(f"written: {len(found)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
