"""Rules the source file must keep before any view is written."""

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
            {
                "name": "Make",
                "head": "Nia",
                "measured_by": "ships that land",
                "owns": ["the alder log"],
            },
            {
                "name": "Trade",
                "head": "Omar",
                "measured_by": "deals that were signed",
                "owns": ["the cedar log"],
            },
        ],
        "outputs": [{"view": "roster", "file": "ROSTER.md"}],
    }


class RuleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="org-chart-rules-")
        self.addCleanup(shutil.rmtree, self.tmp)

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

    def test_empty_team_list_is_rejected(self):
        """source: an emptied source file must fail its own check because it has no team"""
        self.write_org({"org": "Fixture Co", "people": [], "teams": [], "outputs": []})
        proc = self.render("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("RULE: there is no team", proc.stdout)
        self.assertIn("nothing was checked", proc.stdout)

    def test_empty_name_head_and_measure_are_all_reported(self):
        """source: a team needs a name, a head and a measure, and each gap is reported"""
        data = sample()
        data["teams"] = [{"name": "", "head": "", "measured_by": ""}]
        self.write_org(data)
        proc = self.render()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("a team has an empty name", proc.stdout)
        self.assertIn("empty head", proc.stdout)
        self.assertIn("empty measured_by", proc.stdout)
        self.assertIn("nothing was written", proc.stdout)

    def test_team_names_must_differ(self):
        """source: two teams must not share one name"""
        data = sample()
        data["teams"][1]["name"] = "Make"
        self.write_org(data)
        proc = self.render()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("the team name Make is used more than once", proc.stdout)

    def test_people_names_must_differ(self):
        """source: the same person must not be listed twice"""
        data = sample()
        data["people"] = ["Nia", "Nia"]
        data["teams"] = [data["teams"][0]]
        self.write_org(data)
        proc = self.render()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("Nia is listed more than once in people", proc.stdout)

    def test_head_must_be_a_person(self):
        """source: a head who is not in the people list is rejected"""
        data = sample()
        data["teams"][0]["head"] = "Zoe"
        self.write_org(data)
        proc = self.render()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("has head Zoe, who is not in people", proc.stdout)

    def test_member_must_be_a_person(self):
        """source: a member who is not in the people list is rejected"""
        data = sample()
        data["teams"][0]["members"] = ["Zoe"]
        self.write_org(data)
        proc = self.render()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("has member Zoe, who is not in people", proc.stdout)

    def test_one_person_does_not_head_two_teams(self):
        """source: one person heads two teams only when the source allows it"""
        data = sample()
        data["teams"][1]["head"] = "Nia"
        data["teams"][0]["members"] = ["Omar"]
        self.write_org(data)
        proc = self.render()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("RULE: Nia heads both Make and Trade", proc.stdout)
        data["allow_shared_heads"] = True
        self.write_org(data)
        proc = self.render("--check")
        self.assertNotIn("RULE:", proc.stdout)

    def test_every_person_is_on_a_team(self):
        """source: a person who heads nothing and belongs to nothing is rejected"""
        data = sample()
        data["people"].append("Pip")
        self.write_org(data)
        proc = self.render()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("Pip heads no team and is a member of none", proc.stdout)

    def test_one_owner_for_each_thing(self):
        """source: the same owned thing under two teams is rejected even when the case differs"""
        data = sample()
        data["teams"][1]["owns"] = ["The Alder Log"]
        self.write_org(data)
        proc = self.render()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("is owned by both", proc.stdout)

    def test_values_cannot_hold_a_line_break(self):
        """source: a value with a line break is rejected"""
        data = sample()
        data["teams"][0]["measured_by"] = "one\ntwo"
        self.write_org(data)
        proc = self.render()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("holds a line break", proc.stdout)

    def test_unknown_field_is_named(self):
        """source: a misspelt field is named, together with the place it was found"""
        data = sample()
        data["teams"][0]["mesured_by"] = "slipped"
        self.write_org(data)
        proc = self.render()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("team Make has an unknown field mesured_by", proc.stdout)

    def test_output_view_must_be_known(self):
        """source: an output that names an unknown view is rejected"""
        data = sample()
        data["outputs"] = [{"view": "chart", "file": "CHART.md"}]
        self.write_org(data)
        proc = self.render()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("names an unknown view chart", proc.stdout)

    def test_output_path_stays_inside_the_root(self):
        """source: an output path that leaves the root is rejected and nothing is written"""
        nested = os.path.join(self.tmp, "nested")
        os.makedirs(nested)
        data = sample()
        data["outputs"] = [{"view": "roster", "file": "../escape.md"}]
        with open(os.path.join(nested, "org.json"), "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle)
            handle.write("\n")
        env = os.environ.copy()
        env["HOME"] = self.tmp
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [sys.executable, os.path.join(PROJECT, "render.py"), "--root", nested],
            cwd=self.tmp,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("outside the root", proc.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "escape.md")))

    def test_output_is_not_listed_twice(self):
        """source: the same output must not be listed twice"""
        data = sample()
        data["outputs"] = [
            {"view": "roster", "file": "ROSTER.md"},
            {"view": "owners", "file": "ROSTER.md"},
        ]
        self.write_org(data)
        proc = self.render()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("output ROSTER.md is listed twice", proc.stdout)

    def test_whole_file_is_not_also_a_block(self):
        """source: a file written whole is not also given a block"""
        data = sample()
        data["outputs"] = [
            {"view": "roster", "file": "PAGE.md"},
            {"view": "roster", "file": "PAGE.md", "block": "roster"},
        ]
        self.write_org(data)
        proc = self.render()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("written whole and also as a block", proc.stdout)

    def test_every_broken_rule_is_reported(self):
        """source: every broken rule is reported, not only the first"""
        self.write_org({
            "org": "Fixture Co",
            "colour": "blue",
            "people": ["Nia"],
            "teams": [],
            "outputs": [],
        })
        proc = self.render()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("unknown field colour", proc.stdout)
        self.assertIn("there is no team", proc.stdout)
        self.assertIn("Nia heads no team and is a member of none", proc.stdout)
        self.assertIn("nothing was written", proc.stdout)

    def test_a_broken_rule_writes_nothing(self):
        """source: when a rule is broken, an existing view is left untouched"""
        path = os.path.join(self.tmp, "ROSTER.md")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("ORIGINAL\n")
        data = sample()
        data["teams"][0]["head"] = "Zoe"
        self.write_org(data)
        proc = self.render()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "ORIGINAL\n")

    def test_a_view_that_is_not_text_is_rejected(self):
        """source: a view that is not text is reported as an unknown view"""
        data = sample()
        data["outputs"] = [{"view": ["roster"], "file": "X.md"}]
        self.write_org(data)
        checked = self.render("--check")
        self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
        self.assertIn("RULE: output X.md names an unknown view ['roster']", checked.stdout)
        self.assertIn("1 rules broken in org.json; nothing was checked", checked.stdout)
        self.assertEqual(checked.stderr, "")
        written = self.render()
        self.assertEqual(written.returncode, 1, written.stdout + written.stderr)
        self.assertIn("RULE: output X.md names an unknown view ['roster']", written.stdout)
        self.assertIn("1 rules broken in org.json; nothing was written", written.stdout)
        self.assertEqual(written.stderr, "")

    def test_an_output_cannot_replace_the_source_or_the_tool(self):
        """source: an output that names the source or the tool is rejected in any letter case"""
        cases = (
            ("org.json", "org.json"),
            ("ORG.JSON", "org.json"),
            ("./org.json", "org.json"),
            ("render.py", "render.py"),
            ("Render.PY", "render.py"),
        )
        for filename, kind in cases:
            data = sample()
            data["outputs"] = [{"view": "roster", "file": filename}]
            self.write_org(data)
            path = os.path.join(self.tmp, "org.json")
            with open(path, "rb") as handle:
                before = handle.read()
            proc = self.render()
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn(
                "RULE: output %s would overwrite %s" % (filename, kind),
                proc.stdout,
            )
            self.assertEqual(proc.stderr, "")
            with open(path, "rb") as handle:
                self.assertEqual(handle.read(), before, filename)


if __name__ == "__main__":
    unittest.main()
