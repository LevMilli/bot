"""Result splits, risk room and freshness inspector. Offline. They never buy."""
import datetime as dt
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for sub in ("result-splits-paper", "risk-room-paper", "freshness-inspector-paper"):
    sys.path.insert(0, os.path.join(HERE, sub))

import fresh_model as fm  # noqa: E402
import risk_model as rm  # noqa: E402
import split_model as sm  # noqa: E402

NOW = dt.datetime(2026, 11, 13, 20, tzinfo=dt.timezone.utc)
NEW = ("result-splits", "risk-room", "freshness-inspector")


def _bot(folder, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, folder, "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------ result splits
def test_market_exit_hour_side_keys():
    row = {"ticker": "KXBTC15M-26NOV131215-15", "side": "YES", "exit_reason": "take profit 0.91",
           "priced_at": "2026-11-13T18:05:00+00:00"}
    assert sm.market_of(row) == "KXBTC15M"
    assert sm.market_of({"ticker": "KXNBAGAME-26NOV13LALBOS-BOS"}) == "NBA"
    assert sm.market_of({"team": "BONK"}) == "BONK"
    assert sm.market_of({}) == "unknown"
    assert sm.exit_of(row) == "take profit"
    assert sm.exit_of({"exit_reason": "settled yes"}) == "held to result"
    assert sm.exit_of({"exit_reason": "model-flip sold at bid"}) == "model flip sold at bid"
    assert sm.exit_of({"exit_reason": "unknown"}) == "not stored"
    assert sm.hour_of(row) == "12:00 CT"
    assert sm.hour_of({"priced_at": "12:05"}) == "buy time not stored"
    assert sm.side_of(row) == "yes" and sm.side_of({}) == "not stored"


def test_losses_always_count_and_flags():
    rows = [{"ticker": "KXGOLD-A", "pnl": 0.5, "side": "yes"}] * 8 + [{"ticker": "KXGOLD-B", "pnl": -6.0, "side": "yes"}] * 2
    body = sm.split(rows)
    gold = body["market"]["KXGOLD"]
    assert gold["n"] == 10 and gold["losses"] == 2 and gold["total"] == -8.0
    assert gold["win_rate"] == 0.8 and gold["avg_win"] == 0.5 and gold["avg_loss"] == -6.0
    assert "wins often, loses money" in gold["flags"]
    losing = sm.stats([-1.0, -1.2] * 30)
    assert "clearly losing" in losing["flags"]
    assert "clearly losing" not in sm.stats([-1.0, -1.2] * 10)["flags"]   # under 50: no grade


def test_missing_results_are_counted_not_dropped():
    body = sm.run({"a": ("A", [{"ticker": "KXINX-1", "pnl": None}, {"ticker": "KXINX-2", "pnl": 1.0}])}, NOW)
    assert body["towers"]["a"]["no_result"] == 1 and body["towers"]["a"]["n"] == 1
    assert "1 closed trades had no stored result" in sm.card(body)
    assert body["suggest_only"] is True


def test_result_splits_bot_reads_desk_books(tmp_path):
    bot = _bot("result-splits-paper", "splits_bot")
    folder = tmp_path / "nasdaq-paper"
    folder.mkdir()
    (folder / "bot.py").write_text("")
    closed = [dict(ticker=f"KXNASDAQ100-{i}", side="no", contracts=10, cost=5.0, payout=10.0 if i % 4 else 0.0,
                   pnl=4.8 if i % 4 else -5.2, status="settled", settled_at="2026-11-01T20:00:00+00:00")
              for i in range(12)]
    (folder / "paper_account.json").write_text(json.dumps({"cash": 100.0, "open": [], "closed": closed}))
    assert bot.main([], root=str(tmp_path), now=NOW) == 0
    body = json.loads((tmp_path / "result-splits-paper" / "splits.json").read_text())
    nd = body["towers"]["nasdaq"]["cuts"]["market"]["KXNASDAQ100"]
    assert nd["n"] == 12 and nd["losses"] == 3
    assert abs(nd["total"] - (9 * 4.8 - 3 * 5.2 - 12 * 10 * 0.01)) < 1e-6      # fill tax, losses kept
    acct = json.loads((tmp_path / "result-splits-paper" / "paper_account.json").read_text())
    assert acct["cash"] == 0.0 and acct["open"] == [] and acct["research"] is True


# ------------------------------------------------------------ risk room
def test_classify_underlyings():
    assert rm.classify("btc15m", {"ticker": "KXBTC15M-26NOV13-15", "side": "yes"})[:1] == ("Bitcoin",)
    assert rm.classify("more-15m", {"ticker": "KXSOL15M-X", "side": "no"}) == ("Solana", "", "no")
    assert rm.classify("kalshi-sp", {"ticker": "KXINX-26NOV13H1600-B6000"})[0] == "S&P 500"
    assert rm.classify("nasdaq", {"ticker": "KXNASDAQ100U-26NOV13H1600"})[0] == "Nasdaq 100"
    assert rm.classify("weather-high", {"ticker": "KXHIGHNY-26NOV13-B55"})[0] == "Weather NY"
    assert rm.classify("coinbase-spot", {"ticker": "BTC-USD"}) == ("Bitcoin", "", "up")
    assert rm.classify("qqq-momentum", {"symbol": "QQQ"})[0] == "Nasdaq 100"
    assert rm.classify("memecoin", {"team": "BONK"})[0] == "Memecoin BONK"
    game = rm.classify("sports-gap", {"ticker": "KXNBAGAME-26NOV13LALBOS-BOS", "team": "BOS"})
    assert game == ("Game KXNBAGAME-26NOV13LALBOS", "KXNBAGAME-26NOV13LALBOS", "BOS")
    assert rm.classify("x", {"ticker": "KXNEWTHING-1"})[0] == "KXNEWTHING"


def test_room_flags_stacking_same_side_and_heavy():
    rows = {
        "btc15m": ("BTC 15m", "btc", [{"ticker": "KXBTC15M-A", "side": "yes", "cost": 20.0}]),
        "crypto-ladder": ("Crypto ladder", "crypto", [{"ticker": "KXBTCD-B", "side": "yes", "cost": 25.0}]),
        "sports-gap": ("Sports gap", "sports", [{"ticker": "KXNFLGAME-26NOV15KCBUF-KC", "team": "KC", "cost": 5.0}]),
        "poly-sports-lean": ("Poly lean", "sports", [{"ticker": "KXNFLGAME-26NOV15KCBUF-KC", "team": "KC",
                                                     "cost": 5.0}]),
    }
    body = rm.room(rows, NOW)
    assert body["open_cost"] == 55.0 and body["positions"] == 4 and body["towers"] == 4
    btc = body["underlyings"][0]
    assert btc["underlying"] == "Bitcoin" and btc["share"] == round(45 / 55, 3)
    assert set(btc["flags"]) == {"stacked", "heavy"}
    game = next(g for g in body["underlyings"] if g["underlying"].startswith("Game"))
    assert "same side, same game" in game["flags"] and game["same_side"] == ["KC"]
    card = rm.card(body)
    assert card.startswith("Open paper risk $55.00 in 4 positions across 4 towers. Biggest: Bitcoin $45.00 (82%)")
    assert rm.card(rm.room({}, NOW)) == "No open paper positions in the city right now."


def test_risk_room_bot(tmp_path):
    bot = _bot("risk-room-paper", "risk_bot")
    folder = tmp_path / "weather-high-paper"
    folder.mkdir()
    (folder / "bot.py").write_text("")
    open_rows = [{"ticker": "KXHIGHCHI-26NOV13-B50", "event": "KXHIGHCHI-26NOV13", "side": "yes",
                  "contracts": 40, "ask": 0.6, "cost": 24.6, "opened": "2026-11-13T21:00:00+00:00"}]
    (folder / "paper_account.json").write_text(json.dumps({"cash": 475.4, "open": open_rows, "closed": []}))
    assert bot.main([], root=str(tmp_path), now=NOW) == 0
    body = json.loads((tmp_path / "risk-room-paper" / "risk_room.json").read_text())
    assert body["display_only"] and body["underlyings"][0]["underlying"] == "Weather CHI"
    assert body["underlyings"][0]["cost"] == 24.6


# ------------------------------------------------------------ freshness inspector
def test_building_status():
    run = {"at": "2026-11-13 19:50:00 UTC", "ok": True}
    assert fm.building("a", "A", run, 300, False, False, NOW)["status"] == "on time"
    old = {"at": "2026-11-13 18:00:00 UTC", "ok": True}
    late = fm.building("a", "A", old, 300, False, False, NOW)
    assert late["status"] == "late" and late["age_min"] == 120.0 and late["late_after_min"] == 35.0
    assert fm.building("a", "A", {"at": "2026-11-13 19:59:00 UTC", "ok": False}, 300, False, False, NOW)["status"] \
        == "last run failed"
    assert fm.building("a", "A", None, 300, False, False, NOW)["status"] == "never ran"
    assert fm.building("a", "A", old, 300, False, True, NOW)["status"] == "paused"
    weekend = {"at": "2026-11-11T20:00:00+00:00", "ok": True}
    assert fm.building("kalshi-sp", "S&P", weekend, None, True, False, NOW)["status"] == "on time"
    assert fm.building("wall-street", "WS", None, None, False, False, NOW)["status"] == "no timer"


def test_quote_ages():
    rows = [{"price_at": "2026-11-13T19:00:00+00:00", "opened": "2026-11-13T19:00:30+00:00"},
            {"price_at": "2026-11-13T19:00:00+00:00", "opened": "2026-11-13T19:02:00+00:00"},
            {"opened": "2026-11-13T19:00:00+00:00"}]
    got = fm.quote_ages(rows)
    assert got == {"checked": 2, "not_stored": 1, "stale": 1, "max_sec": 120.0, "avg_sec": 75.0}


def test_freshness_bot_lists_every_building(tmp_path):
    import pimp_desk

    bot = _bot("freshness-inspector-paper", "fresh_bot")
    (tmp_path / "pimp-runs.json").write_text(json.dumps({"btc15m": {"at": "2026-11-13 19:59:30 UTC", "ok": True}}))
    assert bot.main([], root=str(tmp_path), now=NOW) == 0
    body = json.loads((tmp_path / "freshness-inspector-paper" / "freshness.json").read_text())
    ids = [b["id"] for b in body["buildings"]]
    assert ids == [b["id"] for b in pimp_desk.BOTS]
    by = {b["id"]: b for b in body["buildings"]}
    assert by["btc15m"]["status"] == "on time" and by["freshness-inspector"]["status"] == "on time"
    assert by["sports-gap"]["status"] == "never ran"
    assert "buildings ran on time" in fm.card(body)


# ------------------------------------------------------------ registry rails
def test_new_buildings_are_research_and_never_buy():
    import new_towers
    import pimp_desk

    for tid in NEW:
        row = new_towers.BY_ID[tid]
        assert row["research"] and row["max_open"] == 0 and row["kind"] == "research"
        assert tid in new_towers.RESEARCH
        assert pimp_desk._account_body(tid)["cash"] == 0.0
        assert pimp_desk.TOWER_STARTER_CASH[tid] == 0.0
        cfg = json.load(open(os.path.join(HERE, row["folder"], "config.json")))
        assert cfg["paper_only"] and not cfg["live_orders"] and cfg["stake_usd"] == 0
        assert row["floor"] >= 0.05 and row["venue"] == "kalshi_econ"
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    for tid in NEW:
        assert new_tower.check_tower(tid)["ok"]


def test_scorekeeper_skips_new_research_buildings(tmp_path):
    bot = _bot("scorekeeper-paper", "score_bot_plan")
    got = bot.histories(str(tmp_path), NOW)
    assert not set(NEW) & set(got)
