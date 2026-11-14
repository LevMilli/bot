"""Every research building must ship a paper-only config, or the desk refuses to start it."""
import json
import os

import new_towers
import pimp_desk

HERE = os.path.dirname(os.path.abspath(__file__))


def test_every_research_row_has_paper_only_config():
    missing = []
    for bot_id in new_towers.RESEARCH:
        path = os.path.join(HERE, new_towers.BY_ID[bot_id]["folder"], "config.json")
        cfg = json.load(open(path)) if os.path.exists(path) else {}
        if cfg.get("paper_only") is not True or cfg.get("live_orders") is True:
            missing.append(bot_id)
    assert missing == []


def test_desk_will_start_meme_price_check():
    assert pimp_desk._paper_ok(HERE, "meme-price-check") == ""
