"""Registry and desk wiring for the seven shadow towers added together. Offline."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

ROWS = {
    "ncaab-gap": ("kalshi_sports", 0.06, 500.0),
    "sports-gap-poly": ("kalshi_sports", 0.06, 500.0),
    "fight-golf-esports-lean": ("kalshi_sports", 0.06, 500.0),
    "sp500-model": ("kalshi_inx", 0.02, 500.0),
    "fed-curve": ("kalshi_econ", 0.05, 500.0),
    "coinbase-maker": ("coinbase_spot", 0.05, 500.0),
    "meme-price-check": ("solana_dex", 0.02, 0.0),
}


def test_registry_and_desk_wiring():
    import desk_profit
    import new_towers
    import pimp_desk

    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower

    for bot_id, (venue, floor, cash) in ROWS.items():
        row = new_towers.BY_ID[bot_id]
        assert row["floor"] == floor and row["venue"] == venue
        assert desk_profit.BOT_VENUE[bot_id] == venue
        assert desk_profit.DEFAULT_VENUE_MIN_EDGE[venue] == floor
        spec = next(b for b in pimp_desk.BOTS if b["id"] == bot_id)
        assert spec["shadow_only"]
        assert pimp_desk._account_body(bot_id)["cash"] == cash
        assert new_tower.check_tower(bot_id)["ok"], bot_id
    assert "meme-price-check" in new_towers.RESEARCH
    assert new_towers.BY_ID["meme-price-check"]["max_open"] == 0


def test_configs_are_paper_only():
    import json
    import new_towers

    for bot_id in ROWS:
        folder = new_towers.BY_ID[bot_id]["folder"]
        path = os.path.join(HERE, folder, "config.json")
        if not os.path.exists(path):
            continue
        cfg = json.load(open(path, encoding="utf-8"))
        assert cfg["paper_only"] is True and cfg["live_orders"] is False and cfg["shadow_only"] is True
