#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
The README as pypi.org shows it: every link and picture that points into the
repository made absolute, on the tag of the release.

    python3 tools/pypi_readme.py v1.9.0     # rewrites README.md in place

The README is the description of the package on PyPI, and there a link like
docs/journal.png leads nowhere. The publish workflow runs this on its own
checkout just before it builds the package; the README of the repository is
never rewritten. Pictures go to raw.githubusercontent.com, documents and
anchors to the page of the file on GitHub. The code blocks are left alone,
since a link inside one is an example of a file, not a link.
"""
import os
import re
import sys

REPO = "stop-loss-enjoyer/plainbook"
PICTURE = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")
# ](target) of a markdown link or picture, src="target" of an <img>
LINK = re.compile(r'(\]\(|src=")([^)"\s]+)')


def absolute(target, tag):
    """Where a target of the README points from outside GitHub."""
    if re.match(r"[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("/"):
        return target
    if target.startswith("#"):
        return f"https://github.com/{REPO}/blob/{tag}/README.md{target}"
    if target.split("#")[0].lower().endswith(PICTURE):
        return f"https://raw.githubusercontent.com/{REPO}/{tag}/{target}"
    return f"https://github.com/{REPO}/blob/{tag}/{target}"


def rewrite(text, tag):
    out = []
    fenced = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced:
            line = LINK.sub(lambda m: m.group(1) + absolute(m.group(2), tag), line)
        out.append(line)
    return "\n".join(out)


def main(argv):
    if len(argv) != 1:
        sys.exit("usage: pypi_readme.py TAG")
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "README.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(rewrite(text, argv[0]))


if __name__ == "__main__":
    main(sys.argv[1:])
