"""Post-E3E7 living CLI surfaces — observe only; floors locked; no tip invent."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / "tools" / "staff_living_status.py"


class PostE3E7Cli(unittest.TestCase):
    def _run(self, action: str, root: str) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT)
        return subprocess.run(
            [sys.executable, str(TOOLS), action, "--root", root],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_post_e3e7_actions_exit_ok(self):
        actions = (
            "latency-stage",
            "tip-decision-ms",
            "exit-risk-ms",
            "fill-capacity",
            "firm-tower-m1",
            "m5-idle-budget",
            "distance-stance",
        )
        with tempfile.TemporaryDirectory() as tmp:
            for action in actions:
                proc = self._run(action, tmp)
                self.assertIn(
                    proc.returncode,
                    (0, 2),
                    msg=f"{action} rc={proc.returncode} stderr={proc.stderr!r}",
                )
                self.assertTrue(
                    proc.stdout.strip().startswith("{"),
                    msg=f"{action} stdout={proc.stdout[:200]!r}",
                )

    def test_makefile_targets_listed(self):
        mk = (ROOT / "Makefile").read_text(encoding="utf-8")
        for target in (
            "living-latency-stage",
            "living-tip-decision-ms",
            "living-exit-risk-ms",
            "living-fill-capacity",
            "living-firm-tower-m1",
            "living-m5-idle-budget",
            "living-distance-stance",
        ):
            self.assertIn(target, mk)


if __name__ == "__main__":
    unittest.main()
