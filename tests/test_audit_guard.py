"""
The guard of tools/check_public.py on throwaway repositories: what a push
would publish, commit and tag messages, record folders at any depth, files
that do not read as text, the remote the pre-push hook measures against, and
a git that cannot be asked.
"""
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(HERE, "tools", "check_public.py")
HOOK = os.path.join(HERE, ".githooks", "pre-push")
GITIGNORE = os.path.join(HERE, ".gitignore")
GIT = shutil.which("git")
ZERO = "0" * 40
# pieced together so that the guard does not fire on this file
WORD = "".join(map(chr, (0x0441, 0x0434, 0x0435, 0x043B, 0x043A, 0x0430)))
DASH = chr(0x2014)
LINUX_HOME = "/ho" + "me/somebody/x"
MAC_HOME = "/Us" + "ers/somebody/x"
WINDOWS_HOME = "C:" + "\\Us" + "ers\\somebody\\x"
PNG = b"\x89PNG\r\n\x1a\n" + bytes(24)


@unittest.skipIf(GIT is None, "git is not installed")
class GuardRepo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pb-audit-guard-")
        self.repo = self.new_repo("repo")

    def tearDown(self):
        # git keeps its objects read-only, which Windows will not delete
        for top, _, files in os.walk(self.tmp):
            for f in files:
                os.chmod(os.path.join(top, f), stat.S_IWRITE | stat.S_IREAD)
        shutil.rmtree(self.tmp)

    def new_repo(self, name):
        repo = os.path.join(self.tmp, name)
        os.makedirs(repo)
        self.git(repo, "init", "-q")
        for key, value in (("user.name", "t"), ("user.email", "t@example.com"),
                           ("commit.gpgsign", "false"), ("tag.gpgsign", "false"),
                           ("core.autocrlf", "false")):
            self.git(repo, "config", key, value)
        self.write(repo, "journal/trades/.gitkeep", "")
        self.write(repo, "README.md", "plain words\n")
        self.commit(repo, "layout")
        return repo

    def git(self, repo, *args):
        done = subprocess.run(["git", *args], cwd=repo, capture_output=True,
                              stdin=subprocess.DEVNULL, check=True)
        return done.stdout.decode("utf-8").strip()

    def write(self, repo, path, content):
        full = os.path.join(repo, *path.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(content.encode("utf-8") if isinstance(content, str) else content)

    def commit(self, repo, message):
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "--allow-empty", "-m", message)
        return self.git(repo, "rev-parse", "HEAD")

    def guard(self, *args, cwd=None, env=None):
        run_env = dict(os.environ if env is None else env, PYTHONIOENCODING="utf-8")
        done = subprocess.run([sys.executable, TOOL, *args], cwd=cwd or self.repo,
                              capture_output=True, env=run_env, stdin=subprocess.DEVNULL)
        return done.returncode, done.stdout.decode("utf-8", "replace")


class RangeContent(GuardRepo):
    """Item 17: the content of the commits, not the files on the disk."""

    def test_text_committed_and_cleaned_by_a_later_commit_is_found(self):
        self.write(self.repo, "notes.md", f"a word in {WORD}\n")
        leak = self.commit(self.repo, "notes")
        self.write(self.repo, "notes.md", "a word in English\n")
        self.commit(self.repo, "cleaned")
        self.assertEqual(self.guard()[0], 0)
        code, out = self.guard("--range", "HEAD")
        self.assertEqual(code, 1, out)
        self.assertIn(f"notes.md in {leak[:9]}:1: cyrillic", out)
        code, out = self.guard("--range", "HEAD~1..HEAD")
        self.assertEqual(code, 0, out)                  # the cleaning commit alone

    def test_text_cleaned_on_the_disk_only_is_found_in_the_tree_of_the_tip(self):
        self.write(self.repo, "paths.md", f"kept in {LINUX_HOME}\n")
        self.commit(self.repo, "paths")
        self.write(self.repo, "other.md", "unrelated\n")
        tip = self.commit(self.repo, "other")
        self.write(self.repo, "paths.md", "kept nowhere\n")    # never committed
        self.assertEqual(self.guard()[0], 0)
        code, out = self.guard("--range", "HEAD~1..HEAD")
        self.assertEqual(code, 1, out)
        self.assertIn(f"paths.md in {tip[:9]}:1: home path", out)

    def test_text_added_and_removed_inside_the_range_is_found(self):
        self.write(self.repo, "draft.md", f"one {DASH} two\n")
        self.commit(self.repo, "draft")
        self.git(self.repo, "rm", "-q", "draft.md")
        self.commit(self.repo, "gone")
        self.assertEqual(self.guard()[0], 0)
        code, out = self.guard("--range", "HEAD~2..HEAD")
        self.assertEqual(code, 1, out)
        self.assertIn("draft.md in ", out)
        self.assertIn("long dash", out)

    def test_a_shallow_checkout_is_refused_only_where_it_is_cut(self):
        for n in range(3):
            self.write(self.repo, "count.md", f"{n}\n")
            self.commit(self.repo, f"count {n}")
        shallow = os.path.join(self.tmp, "shallow")
        subprocess.run(["git", "clone", "-q", "--depth", "2", pathlib.Path(self.repo).as_uri(),
                        shallow], capture_output=True, check=True, stdin=subprocess.DEVNULL)
        self.assertEqual(self.guard(cwd=shallow)[0], 0)     # the tree alone, as CI runs it
        code, out = self.guard("--range", "HEAD~1..HEAD", cwd=shallow)
        self.assertEqual(code, 0, out)
        code, out = self.guard("--range", "HEAD", cwd=shallow)
        self.assertEqual(code, 1, out)
        self.assertIn("shallow", out)


class Messages(GuardRepo):
    """Item 18: commit messages, and the message of an annotated tag."""

    def test_cyrillic_and_a_long_dash_in_a_message_are_found(self):
        self.commit(self.repo, f"fixed {WORD}")
        code, out = self.guard("--range", "HEAD")
        self.assertEqual(code, 1, out)
        self.assertIn("cyrillic in the message", out)
        self.commit(self.repo, f"one {DASH} two")
        code, out = self.guard("--range", "HEAD~1..HEAD")
        self.assertEqual(code, 1, out)
        self.assertIn("long dash in the message", out)
        self.assertNotIn("cyrillic", out)
        self.commit(self.repo, "plain words")
        self.assertEqual(self.guard("--range", "HEAD~1..HEAD")[0], 0)

    def raw_commit(self, header, message):
        # git commit would mend the bytes; a commit made elsewhere may not be
        tree = self.git(self.repo, "write-tree")
        raw = os.path.join(self.tmp, "commit")
        with open(raw, "wb") as f:
            f.write(f"tree {tree}\nauthor t <t@example.com> 1 +0000\n"
                    f"committer t <t@example.com> 1 +0000\n{header}\n".encode("ascii") + message)
        return self.git(self.repo, "hash-object", "-w", "-t", "commit", raw)

    def test_a_message_in_another_encoding_is_found(self):
        bare = self.raw_commit("", WORD.encode("cp1251") + b"\n")
        code, out = self.guard("--range", bare)
        self.assertEqual(code, 1, out)
        self.assertIn("the message is not UTF-8", out)
        declared = self.raw_commit("encoding windows-1251\n", WORD.encode("cp1251") + b"\n")
        code, out = self.guard("--range", declared)
        self.assertEqual(code, 1, out)
        self.assertIn("cyrillic in the message", out)

    def test_the_message_of_an_annotated_tag_is_found(self):
        self.git(self.repo, "tag", "-a", "v1", "-m", f"release {WORD}")
        code, out = self.guard("--range", "v1")
        self.assertEqual(code, 1, out)
        self.assertIn("tag v1: cyrillic in the message", out)
        self.git(self.repo, "tag", "-a", "v2", "-m", "release")
        self.assertEqual(self.guard("--range", "v2")[0], 0)


class FoldersAtAnyDepth(GuardRepo):
    """Item 19: journal, .trash, .drafts and .restore below the top."""

    NESTED = ["sub/journal/trades/x/trade.md", "docs/.trash/t.md",
              "a/.drafts/d.md", "b/.restore/r/journal/accounts/a.md"]

    def test_a_nested_record_is_found_tracked_and_in_history(self):
        for path in self.NESTED:
            self.write(self.repo, path, "pair: EURUSD\n")
        self.commit(self.repo, "nested")
        code, out = self.guard()
        self.assertEqual(code, 1, out)
        for path in self.NESTED:
            self.assertIn(f"a record is tracked: {path}", out)
        self.assertNotIn("journal/trades/.gitkeep", out)
        for path in self.NESTED:
            self.git(self.repo, "rm", "-q", path)
        self.commit(self.repo, "removed")
        self.assertEqual(self.guard()[0], 0)
        code, out = self.guard("--range", "HEAD")
        self.assertEqual(code, 1, out)
        for path in self.NESTED:
            self.assertIn(f"a record is in history: {path}", out)

    def test_only_the_top_journal_is_passed_over_on_the_disk(self):
        self.write(self.repo, "journal/trades/y/trade.md", f"idea: {WORD}\n")
        self.write(self.repo, ".trash/z/trade.md", f"idea: {WORD}\n")
        self.assertEqual(self.guard()[0], 0)            # the journal of a source checkout
        self.write(self.repo, "copy/journal/trades/y/trade.md", f"idea: {WORD}\n")
        code, out = self.guard()
        self.assertEqual(code, 1, out)
        self.assertIn("copy/journal/trades/y/trade.md:1: cyrillic", out)

    def test_gitignore_keeps_records_out_at_any_depth_and_the_layout_in(self):
        shutil.copy(GITIGNORE, os.path.join(self.repo, ".gitignore"))
        ignored = ["journal/trades/x/trade.md", "journal/settings.md",
                   "sub/journal/trades/x/trade.md", "sub/journal/notes.csv",
                   "sub/.trash/t.md", "sub/.restore/r/f.md", "old.plainbook",
                   "sub/backup.plainbook"]
        kept = ["journal/trades/.gitkeep", "journal/accounts/.gitkeep",
                "desktop/trader.plainbook/Journal.qml", "notes.md"]
        for path in ignored + kept:
            self.write(self.repo, path, "x\n")
        for path in ignored:
            done = subprocess.run(["git", "check-ignore", "-q", path], cwd=self.repo,
                                  stdin=subprocess.DEVNULL)
            self.assertEqual(done.returncode, 0, path)
        for path in kept:
            done = subprocess.run(["git", "check-ignore", "-q", path], cwd=self.repo,
                                  stdin=subprocess.DEVNULL)
            self.assertEqual(done.returncode, 1, path)


class UnreadFiles(GuardRepo):
    """Item 20: a tracked file that is not text, and a backup of a journal."""

    def test_a_tracked_file_that_does_not_read_is_found(self):
        self.write(self.repo, "trades.csv", WORD.encode("cp1251") + b"\n")
        self.write(self.repo, "notes.pdf", b"%PDF-1.4\n\xe2\xe3\xcf\xd3\n")
        self.write(self.repo, "shot.png", b"PK\x03\x04" + bytes(24))
        self.write(self.repo, "chart.png", PNG)
        self.write(self.repo, "old.plainbook", b"PK\x03\x04" + bytes(24))
        self.commit(self.repo, "binaries")
        code, out = self.guard()
        self.assertEqual(code, 1, out)
        self.assertIn("trades.csv: not UTF-8 text", out)
        self.assertIn("notes.pdf: not UTF-8 text", out)
        self.assertIn("shot.png: not the picture its name says", out)
        self.assertIn("a record is tracked: old.plainbook", out)
        self.assertNotIn("chart.png", out)

    def test_an_untracked_binary_is_left_alone(self):
        self.write(self.repo, "scratch.bin", b"\xff\xfe\x00\x01")
        self.write(self.repo, "a.plainbook", b"PK\x03\x04")
        self.assertEqual(self.guard()[0], 0)

    def test_a_binary_in_the_range_is_found(self):
        self.write(self.repo, "export.csv", WORD.encode("cp1251"))
        self.commit(self.repo, "export")
        self.git(self.repo, "rm", "-q", "export.csv")
        self.commit(self.repo, "gone")
        code, out = self.guard("--range", "HEAD")
        self.assertEqual(code, 1, out)
        self.assertIn("export.csv in ", out)
        self.assertIn("not UTF-8 text", out)


class Markers(GuardRepo):
    """Item 47: git that fails, more home paths and dashes, any start folder."""

    def test_a_repository_git_cannot_read_is_a_finding(self):
        with open(os.path.join(self.repo, ".git", "HEAD"), "w") as f:
            f.write("garbage\n")
        code, out = self.guard()
        self.assertEqual(code, 1, out)
        self.assertIn("git could not read this repository", out)
        self.assertNotIn("clean", out)

    def test_a_missing_git_is_a_finding_in_a_repository(self):
        empty = os.path.join(self.tmp, "nothing-here")
        os.makedirs(empty)
        code, out = self.guard(env=dict(os.environ, PATH=empty))
        self.assertEqual(code, 1, out)
        self.assertIn("git could not read this repository", out)

    def test_a_folder_no_repository_holds_is_scanned_and_said_so(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        self.write(plain, "a.md", "plain words\n")
        code, out = self.guard(cwd=plain)
        self.assertEqual(code, 0, out)
        self.assertIn("clean: not a git repository", out)
        self.write(plain, "b.md", f"{WORD}\n")
        self.assertEqual(self.guard(cwd=plain)[0], 1)

    def test_home_paths_of_macos_and_windows_and_the_placeholder(self):
        self.write(self.repo, "mac.md", f"in {MAC_HOME}\n")
        self.write(self.repo, "win.md", f"in {WINDOWS_HOME}\n")
        self.write(self.repo, "win.py", "p = " + repr(WINDOWS_HOME) + "\n")
        self.write(self.repo, "samples.md",
                   "/Users/NAME/plainbook, C:\\Users\\NAME\\plainbook, "
                   "C:\\Users\\<you>\\Plainbook, /Users/<you>/Plainbook, /Users/Shared/x\n")
        code, out = self.guard()
        self.assertEqual(code, 1, out)
        for name in ("mac.md:1: home path", "win.md:1: home path", "win.py:1: home path"):
            self.assertIn(name, out)
        self.assertNotIn("samples.md", out)

    def test_every_long_dash_is_found(self):
        for n, code_point in enumerate((0x2012, 0x2013, 0x2014, 0x2015, 0x2E3A, 0x2E3B)):
            self.write(self.repo, f"dash{n}.md", f"one {chr(code_point)} two\n")
        code, out = self.guard()
        self.assertEqual(code, 1, out)
        for n in range(6):
            self.assertIn(f"dash{n}.md:1: long dash", out)
        self.write(self.repo, "minus.md", "a hyphen - and a minus " + chr(0x2212) + "\n")
        for n in range(6):
            os.remove(os.path.join(self.repo, f"dash{n}.md"))
        self.assertEqual(self.guard()[0], 0)

    def test_the_verdict_does_not_depend_on_the_start_folder(self):
        self.write(self.repo, "journal/trades/x/trade.md", "pair: EURUSD\n")
        self.git(self.repo, "add", "-f", "journal/trades/x/trade.md")
        self.write(self.repo, "top.md", f"one {DASH} two\n")
        self.write(self.repo, "tools/x.py", "x = 1\n")
        code, out = self.guard(cwd=os.path.join(self.repo, "tools"))
        self.assertEqual(code, 1, out)
        self.assertIn("a record is tracked: journal/trades/x/trade.md", out)
        self.assertIn("top.md:1: long dash", out)

    def test_a_cyrillic_file_name_is_found(self):
        self.write(self.repo, f"{WORD}.md", "plain words\n")
        self.commit(self.repo, "named")
        code, out = self.guard("--range", "HEAD~1..HEAD")
        self.assertEqual(code, 1, out)
        self.assertIn("cyrillic in the file name", out)


@unittest.skipIf(os.name == "nt" or shutil.which("bash") is None,
                 "the hook is a bash script; Windows may find another bash first")
class Hook(GuardRepo):
    """Item 21: the hook measures the push against the remote it goes to."""

    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.repo, "tools"))
        shutil.copy(TOOL, os.path.join(self.repo, "tools", "check_public.py"))
        self.base = self.git(self.repo, "rev-parse", "HEAD")
        self.write(self.repo, "notes.md", f"{WORD}\n")
        self.leak = self.commit(self.repo, "notes")
        self.write(self.repo, "notes.md", "plain\n")
        self.tip = self.commit(self.repo, "cleaned")
        self.git(self.repo, "update-ref", "refs/remotes/origin/main", self.base)
        self.git(self.repo, "update-ref", "refs/remotes/backup/main", self.tip)

    def hook(self, remote, *lines):
        env = dict(os.environ, PATH=os.path.dirname(sys.executable) + os.pathsep + os.environ["PATH"])
        done = subprocess.run(["bash", HOOK, remote, "https://example.com/x.git"], cwd=self.repo,
                              input="".join(line + "\n" for line in lines).encode(),
                              capture_output=True, env=env)
        return done.returncode, done.stdout.decode("utf-8", "replace")

    def test_a_commit_only_another_remote_holds_is_still_looked_through(self):
        line = f"refs/heads/main {self.tip} refs/heads/main {ZERO}"
        code, out = self.hook("origin", line)
        self.assertEqual(code, 1, out)
        self.assertIn("push refused", out)
        self.assertIn("cyrillic", out)
        self.assertEqual(self.hook("backup", line)[0], 0)

    def test_every_line_is_read_a_delete_passes_and_the_leak_comes_last(self):
        lines = [f"(delete) {ZERO} refs/heads/old {self.base}",
                 f"refs/heads/clean {self.base} refs/heads/clean {ZERO}",
                 f"refs/heads/main {self.tip} refs/heads/main {self.base}"]
        code, out = self.hook("origin", *lines)
        self.assertEqual(code, 1, out)
        self.assertIn("cyrillic", out)
        self.assertEqual(self.hook("origin", *lines[:2])[0], 0)

    def test_a_tag_and_a_known_remote_tip(self):
        self.git(self.repo, "tag", "-a", "v1", "-m", "release", self.tip)
        tag = self.git(self.repo, "rev-parse", "v1")
        line = f"refs/tags/v1 {tag} refs/tags/v1 {ZERO}"
        self.assertEqual(self.hook("origin", line)[0], 1)
        self.assertEqual(self.hook("backup", line)[0], 0)
        after_leak = f"refs/heads/main {self.tip} refs/heads/main {self.leak}"
        self.assertEqual(self.hook("origin", after_leak)[0], 0)

    def test_a_push_to_a_bare_url_looks_through_the_whole_history(self):
        line = f"refs/heads/main {self.tip} refs/heads/main {ZERO}"
        self.assertEqual(self.hook("https://example.com/x.git", line)[0], 1)


if __name__ == "__main__":
    unittest.main()
