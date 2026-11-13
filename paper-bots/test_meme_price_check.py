"""Meme price check research building. Offline."""
import datetime as dt
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "meme-price-check-paper"))

import price_check as pc  # noqa: E402


def _bot():
    spec = importlib.util.spec_from_file_location("meme_price_check_bot",
                                                  os.path.join(HERE, "meme-price-check-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _meme(tmp_path):
    meme = tmp_path / "meme"
    meme.mkdir()
    (meme / "positions.json").write_text(json.dumps({"open": [{"mint": "AAA", "symbol": "A"}]}))
    (meme / "checks.csv").write_text("ts,mint,symbol\n1,BBB,B\n2,CCC,C\n3,AAA,A\n")
    return meme


def test_watch_list_open_first_then_newest(tmp_path):
    meme = _meme(tmp_path)
    got = pc.watch_list(json.loads((meme / "positions.json").read_text()), str(meme / "checks.csv"))
    assert [(w["mint"], w["why"]) for w in got] == [("AAA", "open"), ("CCC", "checked"), ("BBB", "checked")]
    assert pc.watch_list(None, None) == []


def test_deepest_pair_and_compare_fails_closed():
    dex = pc.dex_prices([{"baseToken": {"address": "AAA"}, "priceUsd": "1.00", "liquidity": {"usd": 10}},
                         {"baseToken": {"address": "AAA"}, "priceUsd": "1.10", "liquidity": {"usd": 900}},
                         {"baseToken": {"address": "BBB"}, "priceUsd": "2.0", "liquidity": {"usd": 50}}])
    assert dex["AAA"] == (1.10, 900)
    jup = pc.jup_prices({"AAA": {"usdPrice": 1.09}, "BBB": {"usdPrice": 2.2}, "CCC": None})
    rows = pc.compare([{"mint": m, "why": "checked"} for m in ("AAA", "BBB", "CCC")], dex, jup)
    by = {r["mint"]: r for r in rows}
    assert not by["AAA"]["block"]
    assert by["BBB"]["block"] and "differ" in by["BBB"]["reason"]
    assert by["CCC"]["block"] and "missing" in by["CCC"]["reason"]


def test_bot_tallies_and_holds_no_cash(tmp_path):
    bot = _bot()
    meme = _meme(tmp_path)
    here = tmp_path / "h"
    dex = [{"baseToken": {"address": "AAA"}, "priceUsd": "1.00", "liquidity": {"usd": 1}},
           {"baseToken": {"address": "BBB"}, "priceUsd": "1.00", "liquidity": {"usd": 1}}]
    jup = {"AAA": {"usdPrice": 1.05}, "BBB": {"usdPrice": 1.0}}
    now = dt.datetime(2026, 11, 13, tzinfo=dt.timezone.utc)
    bot.main(here=str(here), meme=str(meme), dex_get=lambda u, **k: dex, jup_get=lambda u, **k: jup, now=now)

    def boom(url, **k):
        raise OSError("down")

    bot.main(here=str(here), meme=str(meme), dex_get=boom, jup_get=lambda u, **k: jup, now=now)
    out = json.loads((here / "price_check.json").read_text())
    t = out["tally"]
    assert t["checks"] == 2 and t["mints"] == 6
    assert t["agree"] == 1 and t["gap_over_2pct"] == 1 and t["missing"] == 4 and t["open_blocked"] == 2
    acct = json.loads((here / "paper_account.json").read_text())
    assert acct["cash"] == 0.0 and acct["research"] and acct["open"] == []
