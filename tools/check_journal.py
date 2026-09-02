#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Does every record in the journal read? Run before a commit of the records, or
whenever the interface says a file could not be read:

    python3 tools/check_journal.py            # the journal in ./journal
    python3 tools/check_journal.py ~/plainbook-data

Every trade, plan, card, account and adjustment is loaded the way the server
loads it, and each one that fails is named with the reason. Nothing is written
and nothing from the records is printed but the path of the file and the error.
Exits non-zero when a record does not read.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import store


def check(root):
    problems = []
    counts = {}
    for name, reader in (("trades", store.all_trades), ("plans", store.all_plans),
                         ("cards", store.all_cards), ("accounts", store.all_accounts),
                         ("adjustments", store.all_adjustments)):
        counts[name] = len(reader(root, problems))
    return counts, problems


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                           os.environ.get("PLAINBOOK_ROOT") or ".")
    if not os.path.isdir(os.path.join(root, store.JOURNAL)):
        print(f"no journal folder under {root}")
        return 2
    counts, problems = check(root)
    for path, why in problems:
        print(f"CANNOT READ {path}: {why}")
    read = ", ".join(f"{n} {name}" for name, n in counts.items())
    if problems:
        n = len(problems)
        print(f"\n{read}; {n} record{'' if n == 1 else 's'} left out")
        return 1
    print(f"clean: {read}, every file reads")
    return 0


if __name__ == "__main__":
    sys.exit(main())
