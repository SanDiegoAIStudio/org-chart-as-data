"""The demo walks the render and check cycle on a throwaway copy."""

import hashlib
import os
import subprocess
import unittest

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class DemoTests(unittest.TestCase):
    def test_demo_prints_the_seven_parts(self):
        """source: the demo shows a clean render, a hand edit, a restored view and a missing source file"""
        watched = ["render.py", "org.json", "ROSTER.md", "OWNERS.md", "README.md"]
        before = {name: digest(os.path.join(PROJECT, name)) for name in watched}
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            ["/bin/sh", os.path.join(PROJECT, "examples", "demo.sh")],
            cwd=PROJECT,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for label in (
            "(1) render",
            "(2) check",
            "(3) hand edit",
            "(4) render after the hand edit",
            "(5) block edits",
            "(6) shared head",
            "(7) missing org.json",
        ):
            self.assertIn(label, proc.stdout)
        self.assertIn("unchanged ROSTER.md", proc.stdout)
        self.assertIn("views match org.json", proc.stdout)
        self.assertIn("DRIFT:", proc.stdout)
        self.assertIn("wrote ROSTER.md", proc.stdout)
        self.assertIn("RULE:", proc.stdout)
        self.assertIn("could not check:", proc.stdout)
        after = {name: digest(os.path.join(PROJECT, name)) for name in watched}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
