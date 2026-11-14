"""Registry and desk wiring for the B6/B7/B8/B9/B16/B18 shadow towers. Offline."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

NEW = {
    "crypto-hourly": ("kalshi_btc15m", 0.05, "crypto-hourly-paper"),
    "weather-low": ("kalshi_econ", 0.05, "weather-low-paper"),
    "weather-cities": ("kalshi_econ", 0.05, "weather-cities-paper"),
    "monthly-precip": ("kalshi_econ", 0.05, "monthly-precip-paper"),
    "gas-monthly": ("kalshi_econ", 0.05, "gas-monthly-paper"),
    "spy-momentum": ("equity_qqq", 0.02, "spy-momentum-paper"),
    "iwm-momentum": ("equity_qqq", 0.02, "iwm-momentum-paper"),
    "treasury-tenors": ("kalshi_econ", 0.05, "treasury-tenors-paper"),
}


def test_rows_reuse_locked_floors_and_are_shadow():
    import desk_profit
    import new_towers
    import pimp_desk

    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower

    # Our 8 colors must be unique and not shared with any other tower.
    mine = [new_towers.BY_ID[b]["color"] for b in NEW]
    others = [r["color"] for r in new_towers.TOWERS if r["id"] not in NEW]
    assert len(mine) == len(set(mine))
    assert not set(mine) & set(others)
    budgets = pimp_desk.DEFAULTS.get("tower_risk_budgets") or {}
    for bot_id, (venue, floor, folder) in NEW.items():
        row = new_towers.BY_ID[bot_id]
        assert row["venue"] == venue and row["floor"] == floor and row["folder"] == folder
        assert desk_profit.BOT_VENUE[bot_id] == venue
        assert desk_profit.DEFAULT_VENUE_MIN_EDGE[venue] == floor
        spec = next(b for b in pimp_desk.BOTS if b["id"] == bot_id)
        assert spec["shadow_only"] and bot_id not in budgets
        assert pimp_desk._account_body(bot_id)["cash"] == 500.0
        assert f"{folder}/research.jsonl" in pimp_desk.SETTLEMENT_FILES
        assert any(s["id"] == bot_id and s["every_sec"] == row["every_sec"] for s in pimp_desk.AUTO)
        assert new_tower.check_tower(bot_id)["ok"], bot_id
        assert os.path.exists(os.path.join(HERE, folder, "README.md"))


def test_locked_floors_unchanged():
    import desk_profit

    locked = {"kalshi_sports": 0.06, "kalshi_btc15m": 0.05, "kalshi_commodity15m": 0.05, "kalshi_inx": 0.02,
              "solana_dex": 0.02, "coinbase_spot": 0.05, "binance_btc_carry": 0.02, "coinbase_btc_carry": 0.02, "kalshi_econ": 0.05,
              "equity_qqq": 0.02}
    for venue, floor in locked.items():
        assert desk_profit.DEFAULT_VENUE_MIN_EDGE[venue] == floor
        assert desk_profit.venue_min_edge(venue, {"venue_min_edge": {venue: 0.0}}) == floor


def test_configs_are_paper_shadow():
    for _, _, folder in NEW.values():
        with open(os.path.join(HERE, folder, "config.json"), encoding="utf-8") as fh:
            cfg = json.load(fh)
        assert cfg["paper_only"] is True and cfg["live_orders"] is False and cfg["shadow_only"] is True
        assert cfg["stake_usd"] == 25
