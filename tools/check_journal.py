#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Does every record in the journal read? Run before a commit of the records, or
whenever the interface says a file could not be read:

    python3 tools/check_journal.py            # the journal in PLAINBOOK_ROOT, or ./journal
    python3 tools/check_journal.py ~/plainbook-data

Every trade, plan, playbook, every frozen version of a playbook, note, card,
week, account and adjustment is loaded the way the server loads it, and so are
the settings, the vocabulary and the pairs; each one that fails is named with
the reason. A trade whose account is not among the accounts is named too: it
reads, but its money is counted against an account that is not there. Nothing is
written and nothing from the records is printed but the path of the file and the
error. Exits non-zero when a record does not read.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plainbook import balances, store


def playbook_versions(root, problems):
    """The versions a playbook was frozen as, which no page loads until a trade
    held to one is opened: a broken one is found here or on that day."""
    base = os.path.join(root, store.JOURNAL, store.PLAYBOOKS)
    found = []
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        for label in store.playbook_versions(root, name):
            version = store.load_playbook_version(root, name, label, problems)
            if version is not None:
                found.append(version)
    return found


def check(root):
    # the settings and the owner's lists first: the server reads them on
    # every page, and one that does not parse is named there too
    problems = store.unread_lists(root, [])
    counts = {}
    read = {}
    for name, reader in (("trades", store.all_trades), ("plans", store.all_plans),
                         ("playbooks", store.all_playbooks), ("notes", store.all_notes),
                         ("cards", store.all_cards), ("weeks", store.all_weeks),
                         ("accounts", store.all_accounts),
                         ("adjustments", store.all_adjustments)):
        read[name] = reader(root, problems)
        counts[name] = len(read[name])
        if name == "playbooks":
            counts["playbook versions"] = len(playbook_versions(root, problems))
    # what the replay finds wrong with the money: an entry on a balance of
    # nothing has no R, and the server names it on every page the same way.
    # These records are read and counted, so they are kept apart from the
    # unreadable ones
    if all(k in read for k in ("trades", "accounts", "adjustments")):
        j = balances.Journal(read["accounts"], read["trades"],
                             read["adjustments"], [])
        replay = list(j.problems)
    else:
        replay = []
    # the account of a trade that is not among the accounts: the replay starts
    # it from a balance of nothing and no page names it
    accounts = set(read.get("accounts", {}))
    orphans = [(t.id, f"the account {t.account!r} is not among the accounts")
               for t in read.get("trades", []) if t.account not in accounts]
    return counts, problems, replay, orphans


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                           os.environ.get("PLAINBOOK_ROOT") or ".")
    if not os.path.isdir(os.path.join(root, store.JOURNAL)):
        print(f"no journal folder under {root}")
        return 2
    counts, problems, replay, orphans = check(root)
    for path, why in problems:
        print(f"CANNOT READ {path}: {why}")
    for path, why in replay:
        print(f"NO R {path}: {why}")
    for path, why in orphans:
        print(f"NO ACCOUNT {path}: {why}")
    read = ", ".join(f"{n} {name}" for name, n in counts.items())
    if problems:
        n = len(problems)
        print(f"\n{read}; {n} record{'' if n == 1 else 's'} left out")
        return 1
    if replay or orphans:
        print(f"\n{read}; every file reads, {len(replay)} with no R, "
              f"{len(orphans)} with no account")
        return 1
    print(f"clean: {read}, every file reads")
    return 0


if __name__ == "__main__":
    sys.exit(main())
