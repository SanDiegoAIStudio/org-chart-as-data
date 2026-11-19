"""Git hooks that run the check on the working copy and on the commit being pushed."""

import os
import shutil
import subprocess
import tempfile
import unittest

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GIT = shutil.which("git")
ZERO = "0" * 40


@unittest.skipUnless(GIT, "git is not installed")
class HookTests(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="org-chart-hooks-")
        self.addCleanup(shutil.rmtree, self.repo)
        project = os.path.realpath(PROJECT)
        repo = os.path.realpath(self.repo)
        if repo == project or repo.startswith(project + os.sep):
            self.fail("temp folder is inside the project")
        self.env = os.environ.copy()
        for key in list(self.env):
            if key.startswith("GIT_"):
                del self.env[key]
        self.env["GIT_CONFIG_GLOBAL"] = "/dev/null"
        self.env["GIT_CONFIG_SYSTEM"] = "/dev/null"
        self.env["HOME"] = self.repo
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"
        for name in ("render.py", "org.json", "ROSTER.md", "OWNERS.md", "README.md"):
            shutil.copy(os.path.join(PROJECT, name), os.path.join(self.repo, name))
        self.git("init")
        top = self.git("rev-parse", "--show-toplevel")
        if os.path.realpath(top.stdout.strip()) != repo:
            self.fail("git toplevel is not the temp folder")
        self.git("add", "render.py", "org.json", "ROSTER.md", "OWNERS.md", "README.md")
        self.commit("initial")

    def git(self, *args):
        proc = subprocess.run(
            [GIT, *args],
            cwd=self.repo,
            env=self.env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            self.fail("%s\n%s" % (" ".join(args), proc.stderr))
        return proc

    def commit(self, message, verify=True):
        cmd = [
            GIT, "-c", "user.name=test", "-c", "user.email=test@example.com",
            "-c", "commit.gpgsign=false", "commit", "-m", message,
        ]
        if not verify:
            cmd.append("--no-verify")
        proc = subprocess.run(cmd, cwd=self.repo, env=self.env, capture_output=True, text=True)
        if proc.returncode != 0:
            self.fail(proc.stderr or proc.stdout)
        return proc

    def hook(self, name, stdin=""):
        script = os.path.join(PROJECT, "examples", name)
        return subprocess.run(
            ["/bin/sh", script],
            cwd=self.repo,
            env=self.env,
            input=stdin,
            capture_output=True,
            text=True,
        )

    def head(self):
        return self.git("rev-parse", "HEAD").stdout.strip()

    def branch(self):
        return self.git("symbolic-ref", "--short", "HEAD").stdout.strip()

    def push_line(self, sha):
        name = self.branch()
        return "refs/heads/%s %s refs/heads/%s %s\n" % (name, sha, name, ZERO)

    def test_pre_commit_passes_a_clean_copy(self):
        """source: the pre-commit hook passes when the working copy matches the source"""
        proc = self.hook("pre-commit")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_pre_commit_fails_after_a_hand_edit(self):
        """source: the pre-commit hook fails after a generated file is edited by hand"""
        path = os.path.join(self.repo, "ROSTER.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read().replace("Ada", "Ava", 1)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        proc = self.hook("pre-commit")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("DRIFT:", proc.stdout)

    def test_pre_push_refuses_a_bad_commit_after_the_working_copy_is_fixed(self):
        """source: the pre-push hook checks the commit being pushed, so a fixed working copy cannot hide it"""
        good = self.head()
        path = os.path.join(self.repo, "ROSTER.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read().replace("Ada", "Ava", 1)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        self.git("add", "ROSTER.md")
        self.commit("bad roster", verify=False)
        bad = self.head()
        shown = self.git("show", "%s:ROSTER.md" % good)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(shown.stdout)
        proc = self.hook("pre-push", self.push_line(bad))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("refusing refs/heads/%s" % self.branch(), proc.stdout + proc.stderr)

    def test_pre_push_allows_a_clean_commit_with_a_dirty_working_copy(self):
        """source: an unfinished edit in the working copy does not block a commit that is fine"""
        good = self.head()
        path = os.path.join(self.repo, "ROSTER.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read().replace("Ada", "Ava", 1)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        proc = self.hook("pre-push", self.push_line(good))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_pre_push_skips_a_deleted_branch(self):
        """source: deleting a branch is not checked"""
        name = self.branch()
        line = "refs/heads/%s %s refs/heads/%s %s\n" % (name, ZERO, name, self.head())
        proc = self.hook("pre-push", line)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_pre_push_skips_a_tag(self):
        """source: a tag is not a branch, so the hook leaves it alone"""
        path = os.path.join(self.repo, "org.json")
        os.remove(path)
        self.git("add", "-u")
        self.commit("drop source", verify=False)
        bad = self.head()
        line = "refs/tags/sample %s refs/tags/sample %s\n" % (bad, ZERO)
        proc = self.hook("pre-push", line)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_pre_push_refuses_a_commit_with_no_source_file(self):
        """source: a commit that has the views and no source file is refused"""
        os.remove(os.path.join(self.repo, "org.json"))
        self.git("add", "-u")
        self.commit("drop source", verify=False)
        proc = self.hook("pre-push", self.push_line(self.head()))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("refusing refs/heads/%s" % self.branch(), proc.stdout + proc.stderr)

    def test_pre_push_removes_each_temp_folder_before_the_next_commit(self):
        """source: a temp path that holds a space is removed before the next commit is checked, and a nearby folder stays"""
        base = tempfile.mkdtemp(prefix="org-chart-mktemp-")
        self.addCleanup(shutil.rmtree, base)
        os.makedirs(os.path.join(base, "t"))
        keep = os.path.join(base, "t", "keep.txt")
        with open(keep, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("keep\n")
        space = os.path.join(base, "t mp")
        os.makedirs(space)
        bin_dir = os.path.join(base, "bin")
        os.makedirs(bin_dir)
        record = os.path.join(base, "record")

        def quote(value):
            return "'" + value.replace("'", "'\\''") + "'"

        script = """#!/bin/sh
base=__BASE__
record=__RECORD__
n=0
for entry in "$base"/*; do
  if [ -e "$entry" ]; then
    n=$((n + 1))
  fi
done
dir="$base/tmp.$n"
mkdir "$dir"
printf '%s\\n' "$n" >> "$record"
printf '%s\\n' "$dir"
"""
        script = script.replace("__BASE__", quote(space)).replace("__RECORD__", quote(record))
        stand_in = os.path.join(bin_dir, "mktemp")
        with open(stand_in, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(script)
        os.chmod(stand_in, 0o755)
        self.env["PATH"] = bin_dir + os.pathsep + self.env.get("PATH", "")
        proc = self.hook("pre-push", self.push_line(self.head()) * 2)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(proc.stderr, "")
        self.assertTrue(os.path.isfile(keep))
        self.assertEqual(sorted(os.listdir(space)), [])
        with open(record, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "0\n0\n")


if __name__ == "__main__":
    unittest.main()
