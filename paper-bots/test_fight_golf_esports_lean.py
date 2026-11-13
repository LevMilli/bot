"""UFC, golf & esports lean tower. Offline."""
import datetime as dt
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "fight-golf-esports-lean-paper"))
sys.path.insert(0, os.path.join(HERE, "soccer-tennis-lean-paper"))

import fge_model as fm  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 13, 18, tzinfo=UTC)


def _bot():
    spec = importlib.util.spec_from_file_location("fge_bot", os.path.join(HERE, "fight-golf-esports-lean-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _k(ev, code, sub, ya=0.40, yb=0.38, title=""):
    return {"ticker": f"{ev}-{code}", "event_ticker": ev, "yes_sub_title": sub, "title": title,
            "yes_ask_dollars": ya, "yes_bid_dollars": yb,
            "no_ask_dollars": round(1 - yb, 2), "no_bid_dollars": round(1 - ya, 2)}


def _fight(spread=0.02, liq=20_000, start=NOW + dt.timedelta(hours=10)):
    return {"slug": "ufc-jon-jones-vs-tom-aspinall", "startTime": start.isoformat().replace("+00:00", "Z"),
            "markets": [{"sportsMarketType": "moneyline", "outcomes": json.dumps(["Jon Jones", "Tom Aspinall"]),
                         "bestBid": 0.55 - spread / 2, "bestAsk": 0.55 + spread / 2, "liquidityNum": liq}]}


def test_two_way_fight_pairs_by_surname():
    ev = "KXUFCFIGHT-26NOV13JONASP"
    kalshi = [_k(ev, "JON", "Jon Jones"), _k(ev, "ASP", "Tom Aspinall")]
    pairs, unmatched = fm.pair_two_way("UFC", [_fight()], kalshi, NOW)
    assert unmatched == 0 and len(pairs) == 2
    fair = {m["ticker"]: p for m, p, _ in pairs}
    assert fair[f"{ev}-JON"] == 0.55 and fair[f"{ev}-ASP"] == 0.45


def test_wide_thin_or_too_soon_is_skipped():
    ev = "KXUFCFIGHT-26NOV13JONASP"
    kalshi = [_k(ev, "JON", "Jon Jones"), _k(ev, "ASP", "Tom Aspinall")]
    assert fm.pair_two_way("UFC", [_fight(spread=0.05)], kalshi, NOW)[0] == []
    assert fm.pair_two_way("UFC", [_fight(liq=1000)], kalshi, NOW)[0] == []
    assert fm.pair_two_way("UFC", [_fight(start=NOW + dt.timedelta(minutes=5))], kalshi, NOW)[0] == []
    assert fm.pair_two_way("UFC", [_fight(start=NOW + dt.timedelta(hours=60))], kalshi, NOW)[0] == []


def test_golf_winner_matches_tournament_and_player():
    ev = "KXPGATOUR-26RSMC"
    kalshi = [_k(ev, "SSCH", "Scottie Scheffler", title="RSM Classic: Will Scottie Scheffler win?"),
              _k(ev, "XNOB", "Nobody Here", title="RSM Classic: Will Nobody Here win?")]
    events = [{"slug": "pga-tour-rsm-classic-winner", "title": "PGA Tour: RSM Classic Winner",
               "markets": [{"groupItemTitle": "Scottie Scheffler", "bestBid": 0.20, "bestAsk": 0.22,
                            "liquidityNum": 30_000}]}]
    pairs, unmatched = fm.pair_golf(events, kalshi, NOW)
    assert [(m["ticker"], p) for m, p, _ in pairs] == [(f"{ev}-SSCH", 0.21)]
    assert unmatched == 1


def test_bot_quotes_and_spec():
    bot = _bot()
    assert bot.SPEC["floor"] == 0.06 and bot.SPEC["max_edge"] == 0.15
    ev = "KXUFCFIGHT-26NOV13JONASP"
    quotes, _ = bot.quotes_for("UFC", [_fight()], [_k(ev, "JON", "Jon Jones"), _k(ev, "ASP", "Tom Aspinall")], NOW)
    assert len(quotes) == 4
    no = next(q for q in quotes if q["ticker"].endswith("JON") and q["side"] == "no")
    assert abs(no["fair"] - 0.45) < 1e-9
    assert "end_date_max" in bot.gamma_url(38, "fight", NOW)
