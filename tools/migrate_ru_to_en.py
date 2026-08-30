#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-shot migration: a journal written with Russian keys and folder names into
the English format of v1.1.

    python3 tools/migrate_ru_to_en.py [journal root]     # dry run, shows the plan
    python3 tools/migrate_ru_to_en.py [journal root] --apply

Only names are translated — keys, folders, file names, the values of the closed
vocabularies (style, adjustment kind) and the section headings. Everything the
owner wrote by hand — idea texts, conclusions, notes, card sections — is left
exactly as it is.

The script is idempotent: run on an already migrated journal it finds nothing
to do.
"""
import os
import re
import shutil
import sys

DIRS = {
    "сделки": "trades",
    "счета": "accounts",
    "корректировки": "adjustments",
    "карточки": "cards",
    "отчёты": "reports",
}
FILES = {"сделка.md": "trade.md", "пары.md": "pairs.md"}
SHOTS_DIR = ("скрины", "shots")
ROOT_DIRS = {".черновики": ".drafts", ".корзина": ".trash"}

# header keys, per record kind
KEYS = {
    "счёт": "account", "пара": "pair", "направление": "direction",
    "стиль": "style", "вход": "entry", "результат": "result", "выход": "exit",
    "пометка": "note", "риск %": "risk %",
    "название": "name", "стартовый баланс": "start balance",
    "валюта": "currency", "архив": "archived",
    "тип": "kind", "сумма": "amount", "дата": "date",
    "оценка процесса": "process grade",
    "качество возможностей": "opportunity quality",
    "пары": "pairs", "период": "period", "обновлён": "updated",
}

# closed vocabularies: only these values are translated
VALUES = {
    "style": {"свинг": "swing", "емт": "EMT", "емт-проп": "EMT prop",
              "интрадей": "intraday"},
    "pair": {"пара не указана": "pair not set"},
    "archived": {"да": "yes", "нет": "no"},
    "kind": {"депозит": "deposit", "вывод": "withdrawal", "комиссия": "fee",
             "сверка": "reconciliation", "месяц": "month", "квартал": "quarter"},
}

SECTIONS = {
    "## Идея": "## Idea",
    "## Момент выхода": "## Exit",
    "## Выводы": "## Conclusions",
    "## Фокус": "## Focus",
    "## Процесс": "## Process",
    "## Что получилось": "## Learned",
    "## Ошибки": "## Errors",
    "## Лучшая сделка": "## Best trade",
    "## Обзор дня": "## Overview",
}

SHOT_PREFIX = {"идея": "idea", "выход": "exit", "выводы": "conclusions"}
# a trade id is built from the pair, so trades without one carry the placeholder
ID_PART = ("пара-не-указана", "pair-not-set")


def new_shot_name(name):
    m = re.match(r"^(идея|выход|выводы)(-.*)$", name)
    return SHOT_PREFIX[m.group(1)] + m.group(2) if m else name


def convert_text(text):
    """Rewrites the header keys, the vocabulary values, the section headings
    and the image paths inside one markdown file."""
    out, in_head, seen_sep = [], False, 0
    for line in text.split("\n"):
        if line.strip() == "---" and seen_sep < 2:
            seen_sep += 1
            in_head = seen_sep == 1
            out.append(line)
            continue
        if in_head and ":" in line and not line.lstrip().startswith("- "):
            key, _, value = line.partition(":")
            plain, value = key.strip(), value.strip()
            key_en = KEYS.get(plain, plain)
            value = VALUES.get(key_en, {}).get(value, value)
            if key_en == "id":
                value = value.replace(*ID_PART)
            out.append(f"{key_en}: {value}" if value else f"{key_en}:")
            continue
        stripped = line.strip()
        if stripped in SECTIONS:
            out.append(SECTIONS[stripped])
            continue
        # image links: скрины/идея-01-01.png -> shots/idea-01-01.png
        line = re.sub(r"\((скрины)/([^)]+)\)",
                      lambda m: f"(shots/{new_shot_name(m.group(2))})", line)
        out.append(line)
    return "\n".join(out)


def walk(root, apply):
    """Renames first, then rewrites every markdown file found afterwards.

    In a dry run nothing is touched: the moves are only listed and the files are
    converted in memory to count the ones that would change."""
    journal = os.path.join(root, "journal")
    steps = []

    def move(src, dst):
        if not os.path.exists(src) or os.path.exists(dst):
            return
        steps.append(("move", os.path.relpath(src, root), os.path.relpath(dst, root)))
        if apply:
            os.rename(src, dst)

    # 1. folders and file names
    for old, new_name in DIRS.items():
        move(os.path.join(journal, old), os.path.join(journal, new_name))
    move(os.path.join(journal, "пары.md"), os.path.join(journal, FILES["пары.md"]))
    for old, new_name in ROOT_DIRS.items():
        move(os.path.join(root, old), os.path.join(root, new_name))

    trades = os.path.join(journal, DIRS["сделки"] if apply else "сделки")
    if not os.path.isdir(trades):
        trades = os.path.join(journal, "trades")
    for name in sorted(os.listdir(trades)) if os.path.isdir(trades) else []:
        folder = os.path.join(trades, name)
        if not os.path.isdir(folder):
            continue
        # the id of a trade without a pair carries the Russian placeholder
        if ID_PART[0] in name:
            renamed = os.path.join(trades, name.replace(*ID_PART))
            move(folder, renamed)
            if apply:
                folder = renamed
        move(os.path.join(folder, "сделка.md"), os.path.join(folder, FILES["сделка.md"]))
        move(os.path.join(folder, SHOTS_DIR[0]), os.path.join(folder, SHOTS_DIR[1]))
        shots = os.path.join(folder, SHOTS_DIR[1] if apply else SHOTS_DIR[0])
        if not os.path.isdir(shots):
            shots = os.path.join(folder, SHOTS_DIR[1])
        for shot in sorted(os.listdir(shots)) if os.path.isdir(shots) else []:
            fresh = new_shot_name(shot)
            if fresh != shot:
                move(os.path.join(shots, shot), os.path.join(shots, fresh))

    # 2. the contents of every markdown file under journal/
    for base, dirs, files in os.walk(journal):
        for name in sorted(files):
            if not name.endswith(".md"):
                continue
            path = os.path.join(base, name)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            fresh = convert_text(text)
            if fresh == text:
                continue
            steps.append(("rewrite", os.path.relpath(path, root), ""))
            if apply:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(fresh)
    return steps


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    root = os.path.abspath(args[0] if args else ".")
    steps = walk(root, apply)
    for kind, a, b in steps:
        print(f"{kind:8} {a}" + (f"  ->  {b}" if b else ""))
    print(f"\n{len(steps)} steps, root {root}")
    if not apply:
        print("dry run — add --apply to actually do it")


if __name__ == "__main__":
    main()
