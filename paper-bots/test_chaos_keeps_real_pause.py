"""The chaos drill pack runs inside pimp_desk.snapshot() on the live server.

It must never swap out a live desk function, even with several snapshots
running at once, or a staff pause can silently stop working.
"""
import os
import threading
import unittest

import desk_roi_e9_chaos
import pimp_desk

HERE = os.path.dirname(os.path.abspath(__file__))


class ChaosKeepsRealPause(unittest.TestCase):
    def test_parallel_ruin_drills_leave_set_pause_alone(self):
        real = pimp_desk.set_pause
        real_pause_file = pimp_desk.pause_path(HERE)
        before = os.path.exists(real_pause_file)
        errors = []

        def run():
            try:
                row = desk_roi_e9_chaos.drill_ruin_nuclear()
                if not row.get("ok"):
                    errors.append(row)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=run) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual(errors, [])
        self.assertIs(pimp_desk.set_pause, real)
        # The drill pauses its own temp folder, never this desk.
        self.assertEqual(os.path.exists(real_pause_file), before)

    def test_no_runtime_module_patches_the_desk(self):
        for name in sorted(os.listdir(HERE)):
            if not name.endswith(".py") or name.startswith("test_") or name == "conftest.py":
                continue
            with open(os.path.join(HERE, name), encoding="utf-8") as handle:
                src = handle.read()
            self.assertNotIn("mock.patch", src.replace("# No mock.patch here", ""), name)


if __name__ == "__main__":
    unittest.main()
