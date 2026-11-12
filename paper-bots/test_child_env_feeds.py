"""Tower child processes get their feed keys but never the desk secrets."""
import os
import unittest
from unittest import mock

import pimp_desk


class ChildEnvTests(unittest.TestCase):
    def test_feed_keys_pass_and_secrets_do_not(self):
        env = {
            "ODDS_API_KEY": "odds-key", "FED_PM_MAX_SPREAD": "0.03", "PAPER_MAX_SLIP": "0.02",
            "DESK_SERVICE_KEY": "x" * 40, "PAPER_RECAP_WEBHOOK": "https://hook", "DISCORD_TOKEN": "t",
        }
        with mock.patch.dict(os.environ, env):
            child = pimp_desk._child_env()
        self.assertEqual(child["ODDS_API_KEY"], "odds-key")
        self.assertEqual(child["FED_PM_MAX_SPREAD"], "0.03")
        self.assertEqual(child["PAPER_MAX_SLIP"], "0.02")
        for secret in ("DESK_SERVICE_KEY", "PAPER_RECAP_WEBHOOK", "DISCORD_TOKEN"):
            self.assertNotIn(secret, child)


if __name__ == "__main__":
    unittest.main()
