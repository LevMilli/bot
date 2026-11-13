"""Vault cash is the desk book only. Shadow towers stay on their own line."""
import unittest

import pimp_desk


def _bot(bot_id, cash, realized, today, shadow=False):
    return {
        "id": bot_id,
        "cash": cash,
        "realized": realized,
        "today": today,
        "open_risk": 3,
        "open_count": 1,
        "shadow_only": shadow,
        "history": [],
        "positions": [],
    }


class VaultBankrollTests(unittest.TestCase):
    def test_shadow_profit_does_not_enter_the_vault(self):
        bots = [
            _bot("btc15m", 97.19, -2.81, -2.81),
            _bot("commodity-15m", 45.54, -54.46, -54.46),
            _bot("memecoin", 58.08, -136.83, -10.0),
            _bot("more-15m", 1449.87, 974.87, 974.87, shadow=True),
            _bot("nasdaq", 500.0, 0.0, 0.0, shadow=True),
        ]
        roll = pimp_desk.bankroll_roll(bots)
        self.assertEqual(roll["towers"], ["btc15m", "commodity-15m", "memecoin"])
        self.assertEqual(roll["cash"], 200.81)
        self.assertEqual(roll["realized"], -194.10)
        self.assertEqual(roll["today"], -67.27)
        self.assertEqual(roll["shadow_towers"], ["more-15m", "nasdaq"])
        self.assertEqual(roll["shadow_cash"], 1949.87)
        self.assertEqual(roll["shadow_today"], 974.87)
        self.assertEqual(roll["missing"], [])

    def test_a_desk_tower_with_no_book_is_named_missing(self):
        bots = [
            _bot("sports-gap", None, None, 0),
            _bot("coinbase-spot", 500.0, 12.0, 12.0, shadow=True),
        ]
        roll = pimp_desk.bankroll_roll(bots)
        self.assertIsNone(roll["cash"])
        self.assertEqual(roll["missing"], ["sports-gap"])
        self.assertEqual(roll["shadow_cash"], 500.0)
        self.assertNotIn("coinbase-spot", roll["towers"])

    def test_desk_row_uses_the_same_towers(self):
        bots = [
            _bot("btc15m", 97.19, -2.81, -2.81),
            _bot("more-15m", 1449.87, 974.87, 974.87, shadow=True),
        ]
        row = pimp_desk._desk_row(
            bots, [999], [999], "", "", dict(pimp_desk.DEFAULTS), "/tmp",
        )
        self.assertEqual(row["cash"], 97.19)
        self.assertEqual(row["realized"], -2.81)
        self.assertEqual(row["today"], -2.81)
        self.assertEqual(row["open_count"], 1)
