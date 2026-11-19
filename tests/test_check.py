"""The check that fails when a view on disk no longer matches the source."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sample():
    """A small valid org used as a starting point."""
    return {
        "org": "Fixture Co",
        "people": ["Nia", "Omar"],
        "teams": [
            {"name": "Make", "head": "Nia", "measured_by": "ships that land", "owns": ["the widget"]},
            {"name": "Trade", "head": "Omar", "measured_by": "deals that were signed", "owns": ["the price card"]},
        ],
        "outputs": [
            {"view": "roster", "file": "ROSTER.md"},
            {"view": "owners", "file": "OWNERS.md"},
            {"view": "roster", "file": "PAGE.md", "block": "roster"},
        ],
    }


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="org-chart-check-")
        self.addCleanup(shutil.rmtree, self.tmp)
        page = os.path.join(self.tmp, "PAGE.md")
        with open(page, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("KEEP\n<!-- org:roster:begin -->\n<!-- org:roster:end -->\nTAIL\n")

    def write_org(self, data):
        with open(os.path.join(self.tmp, "org.json"), "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle)
            handle.write("\n")

    def render(self, *args):
        env = os.environ.copy()
        env["HOME"] = self.tmp
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.pop("PYTHONPATH", None)
        return subprocess.run(
            [sys.executable, os.path.join(PROJECT, "render.py"), *args, "--root", self.tmp],
            cwd=self.tmp,
            env=env,
            capture_output=True,
            text=True,
        )

    def test_matching_views_exit_clean(self):
        """source: a check of views that match the source exits clean and writes nothing"""
        self.write_org(sample())
        self.assertEqual(self.render().returncode, 0)
        proc = self.render("--check")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("views match org.json (3 outputs)", proc.stdout)

    def test_a_changed_line_is_shown(self):
        """source: the check names the first line that differs, both on disk and expected"""
        self.write_org(sample())
        self.render()
        path = os.path.join(self.tmp, "ROSTER.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read().replace("Nia", "NiaX", 1)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        proc = self.render("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("DRIFT: ROSTER.md line", proc.stdout)
        self.assertIn(" differs", proc.stdout)
        self.assertIn("\n  on disk:  ", proc.stdout)
        self.assertIn("\n  expected: ", proc.stdout)
        self.assertIn("NiaX", proc.stdout)
        self.assertIn("1 of 3 outputs out of date. Change org.json, then run: python3 render.py", proc.stdout)

    def test_a_long_line_is_cut(self):
        """source: a differing line is cut so the report stays short"""
        data = sample()
        data["teams"][0]["measured_by"] = "m" * 120
        self.write_org(data)
        self.render()
        path = os.path.join(self.tmp, "ROSTER.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read().replace("m" * 120, "n" * 120)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        proc = self.render("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        disk = [line for line in proc.stdout.splitlines() if line.startswith("  on disk:  ")]
        self.assertTrue(disk, proc.stdout)
        self.assertEqual(len(disk[0].split("  on disk:  ", 1)[1]), 100)

    def test_a_missing_view_is_named(self):
        """source: a missing whole-file view is reported as missing"""
        self.write_org(sample())
        self.render()
        os.remove(os.path.join(self.tmp, "OWNERS.md"))
        proc = self.render("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("DRIFT: OWNERS.md is missing", proc.stdout)

    def test_a_missing_block_is_named(self):
        """source: a page with no marker block is reported as having no block"""
        self.write_org(sample())
        self.render()
        with open(os.path.join(self.tmp, "PAGE.md"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write("no markers here\n")
        proc = self.render("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("DRIFT: PAGE.md has no org:roster block", proc.stdout)

    def test_bytes_outside_a_block_are_free_to_edit(self):
        """source: editing bytes outside a block does not count as drift"""
        self.write_org(sample())
        self.render()
        with open(os.path.join(self.tmp, "PAGE.md"), "a", encoding="utf-8") as handle:
            handle.write("A sentence outside the block.\n")
        proc = self.render("--check")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("views match org.json", proc.stdout)

    def test_dropped_final_newline_is_drift(self):
        """source: the check compares bytes, so a dropped final newline is drift"""
        self.write_org(sample())
        self.render()
        path = os.path.join(self.tmp, "ROSTER.md")
        with open(path, "rb") as handle:
            raw = handle.read()
        self.assertTrue(raw.endswith(b"\n"))
        with open(path, "wb") as handle:
            handle.write(raw[:-1])
        proc = self.render("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("DRIFT: ROSTER.md line", proc.stdout)

    def test_missing_source_cannot_pass(self):
        """source: a check with no readable source file fails and never passes"""
        self.write_org(sample())
        os.remove(os.path.join(self.tmp, "org.json"))
        proc = self.render("--check")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertTrue(proc.stdout.startswith("could not check: org.json is missing"))

    def test_source_must_be_a_json_object(self):
        """source: a source file that is not a JSON object cannot be checked or rendered"""
        with open(os.path.join(self.tmp, "org.json"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[]\n")
        proc = self.render("--check")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("could not check: org.json is not a JSON object", proc.stdout)
        with open(os.path.join(self.tmp, "org.json"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write("{")
        proc = self.render()
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("could not render: org.json is not valid JSON", proc.stdout)

    def test_usage_goes_to_stderr(self):
        """source: a usage error is one line on stderr and a failing status"""
        env = os.environ.copy()
        env["HOME"] = self.tmp
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [sys.executable, os.path.join(PROJECT, "render.py"), "--nope"],
            cwd=self.tmp,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertTrue(proc.stderr.startswith("usage:"))
        self.assertEqual(proc.stdout, "")

    def test_a_hand_edit_in_a_block_names_the_file_line(self):
        """source: a hand edit inside a block is reported on the line of the file"""
        self.write_org(sample())
        made = self.render()
        self.assertEqual(made.returncode, 0, made.stdout + made.stderr)
        self.assertEqual(made.stderr, "")
        path = os.path.join(self.tmp, "PAGE.md")
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        self.assertTrue(lines[5].startswith("| Make |"), "\n".join(lines))
        lines[5] = lines[5].replace("Make", "Mike", 1)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(lines))
        proc = self.render("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("DRIFT: PAGE.md line 6 differs", proc.stdout)
        self.assertEqual(proc.stderr, "")

    def test_a_later_block_names_the_file_line_after_an_earlier_block_was_shortened(self):
        """source: drift in a later block is reported on the file line when an earlier block was shortened"""
        page = os.path.join(self.tmp, "PAGE.md")
        with open(page, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "KEEP\n"
                "<!-- org:owners:begin -->\n"
                "<!-- org:owners:end -->\n"
                "MID\n"
                "<!-- org:roster:begin -->\n"
                "<!-- org:roster:end -->\n"
                "TAIL\n"
            )
        data = sample()
        data["outputs"] = [
            {"view": "owners", "file": "PAGE.md", "block": "owners"},
            {"view": "roster", "file": "PAGE.md", "block": "roster"},
        ]
        self.write_org(data)
        made = self.render()
        self.assertEqual(made.returncode, 0, made.stdout + made.stderr)
        self.assertEqual(made.stderr, "")
        with open(page, encoding="utf-8") as handle:
            text = handle.read()
        begin = "<!-- org:owners:begin -->\n"
        start = text.index(begin) + len(begin)
        stop = text.index("<!-- org:owners:end -->")
        text = text[:start] + text[stop:]
        lines = text.split("\n")
        self.assertTrue(lines[8].startswith("| Make |"), "\n".join(lines))
        lines[8] = lines[8].replace("Make", "Mike", 1)
        with open(page, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(lines))
        proc = self.render("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertEqual(proc.stderr, "")
        self.assertIn("DRIFT: PAGE.md line 3 differs", proc.stdout)
        self.assertIn("DRIFT: PAGE.md line 9 differs", proc.stdout)
        self.assertLess(
            proc.stdout.index("DRIFT: PAGE.md line 3 differs"),
            proc.stdout.index("DRIFT: PAGE.md line 9 differs"),
        )


if __name__ == "__main__":
    unittest.main()
