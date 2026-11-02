"""Regression: sports gap_bot must not shadow module datetime inside run()."""

import ast
import os
import unittest


ROOT = os.path.dirname(os.path.abspath(__file__))
GAP = os.path.join(ROOT, "sports-gap-paper", "gap_bot.py")


class SportsGapDatetimeTests(unittest.TestCase):
    def test_run_does_not_reimport_datetime(self):
        with open(GAP, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=GAP)
        run_fn = None
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "run":
                run_fn = node
                break
        self.assertIsNotNone(run_fn, "run() missing")
        shadowed = []
        for node in ast.walk(run_fn):
            if isinstance(node, ast.ImportFrom) and node.module == "datetime":
                names = [a.name for a in (node.names or [])]
                if "datetime" in names:
                    shadowed.append(node.lineno)
        self.assertEqual(
            shadowed,
            [],
            f"local datetime import inside run() shadows module datetime at lines {shadowed}",
        )


if __name__ == "__main__":
    unittest.main()
