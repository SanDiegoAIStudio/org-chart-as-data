"""The files in this folder stay in step with the source."""

import os
import subprocess
import sys
import tempfile
import unittest

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class RepoTests(unittest.TestCase):
    def test_check_passes_here(self):
        """source: the views in this folder match the source, so the check passes"""
        home = tempfile.mkdtemp(prefix="org-chart-repo-")
        self.addCleanup(lambda: __import__("shutil").rmtree(home))
        env = os.environ.copy()
        env["HOME"] = home
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [sys.executable, os.path.join(PROJECT, "render.py"), "--check"],
            cwd=PROJECT,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("views match org.json", proc.stdout)

    def test_readme_holds_the_roster_block(self):
        """source: the readme holds the roster between its two marker lines"""
        path = os.path.join(PROJECT, "README.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        begin = text.index("<!-- org:roster:begin -->")
        end = text.index("<!-- org:roster:end -->")
        block = text[begin:end]
        self.assertLess(begin, end)
        self.assertIn("Edits between these two markers are overwritten.", block)
        self.assertIn("| Team |", block)
        self.assertIn("| Head |", block)

    def test_tool_stays_short(self):
        """source: the generator stays short enough to read in one sitting"""
        path = os.path.join(PROJECT, "render.py")
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        self.assertLess(len(lines), 420)


if __name__ == "__main__":
    unittest.main()
