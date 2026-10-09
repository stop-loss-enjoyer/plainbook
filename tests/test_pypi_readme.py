#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The README as pypi.org shows it."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import pypi_readme

RAW = "https://raw.githubusercontent.com/stop-loss-enjoyer/plainbook/v9.9.9/"
BLOB = "https://github.com/stop-loss-enjoyer/plainbook/blob/v9.9.9/"


class PypiReadmeCase(unittest.TestCase):
    def rewrite(self, text):
        return pypi_readme.rewrite(text, "v9.9.9")

    def test_pictures_documents_and_anchors_point_at_the_tag(self):
        self.assertEqual(self.rewrite("![a](docs/journal.png)"),
                         f"![a]({RAW}docs/journal.png)")
        self.assertEqual(self.rewrite('<img src="docs/card.png" width="49%">'),
                         f'<img src="{RAW}docs/card.png" width="49%">')
        self.assertEqual(self.rewrite("[guide](GUIDE.md) and [l](LICENSE)"),
                         f"[guide]({BLOB}GUIDE.md) and [l]({BLOB}LICENSE)")
        self.assertEqual(self.rewrite("[x](#checking-a-downloaded-file)"),
                         f"[x]({BLOB}README.md#checking-a-downloaded-file)")

    def test_absolute_links_and_code_blocks_are_left_alone(self):
        text = ("[t](https://github.com/x/y) [m](mailto:a@b.c)\n"
                "```\n![](shots/exit-01.png)\n```\n")
        self.assertEqual(self.rewrite(text), text)

    def test_the_readme_has_no_relative_link_left(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            done = self.rewrite(f.read())
        fenced = False
        for line in done.split("\n"):
            if line.lstrip().startswith("```"):
                fenced = not fenced
                continue
            if fenced:
                continue
            for _, target in pypi_readme.LINK.findall(line):
                self.assertRegex(target, r"^(https?|mailto):", line)


if __name__ == "__main__":
    unittest.main()
