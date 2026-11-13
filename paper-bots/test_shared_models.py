"""Shared models and the model lab. Offline."""
import contextlib
import datetime as dt
import importlib.util
import io
import json
import math
import os
import statistics
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "model-lab-paper"))

import shared_models as sm  # noqa: E402
import model_lab as ml  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 13, 18, 3, tzinfo=UTC)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------ the shared fair helper matches today (420)
def test_matches_more_15m(tmp_path, monkeypatch):
    bot = _load("more15_for_shared", "more-15m-paper/bot.py")
    monkeypatch.setattr(bot, "HERE", str(tmp_path))
    close = NOW + dt.timedelta(minutes=9)
    for spot, sigma in ((100.3, 0.001), (99.6, 0.0007), (100.0, 0.002)):
        mk = {"ticker": "KXSOL15M-T", "event_ticker": "E", "floor_strike": 100.0,
              "close_time": close.isoformat().replace("+00:00", "Z"), "yes_ask_dollars": "0.5",
              "no_ask_dollars": "0.5", "yes_bid_dollars": "0.4", "no_bid_dollars": "0.4"}
        old = next(q for q in bot.window_quotes("KXSOL15M", [mk], spot, sigma, NOW) if q["side"] == "yes")
        new = sm.fair_up(spot, 100.0, sigma, max(0.25, 9 - 0.67), clip=(0.01, 0.99))
        assert abs(old["fair"] - new) < 1e-12


def test_matches_btc_15m():
    btc = _load("btc_for_shared", "btc15m-signal/btc15m_signal.py")
    closes = [70000 * (1 + 0.0004 * math.sin(i)) for i in range(70)]
    for dvol in (None, 45.0):
        sigma, _, _ = btc._sigma_for(70100.0, 7.5, closes, dvol)
        for cushion in (35.0, 120.0, -60.0):
            assert abs(btc.phi(cushion / sigma) - sm.fair_up(70000 + cushion, 70000, sigma, mode="dollar")) < 1e-12
    assert btc.phi(0.7) == sm.phi(0.7)


def test_matches_commodity_15m():
    com = _load("com_for_shared", "commodity-15m-paper/bot.py")
    src = open(os.path.join(HERE, "commodity-15m-paper", "bot.py"), encoding="utf-8").read()
    assert "sigma = spot * 0.0015 * math.sqrt(max(minutes_left, 1.0) / 15.0)" in src
    for spot, target, minutes in ((2400.0, 2396.0, 8.0), (31.2, 31.25, 0.5), (75.0, 74.0, 13.0)):
        sigma = spot * 0.0015 * math.sqrt(max(minutes, 1.0) / 15.0)
        old = com.phi(abs(spot - target) / sigma)
        side_up = spot > target
        new = sm.side_fair(sm.fair_up(spot, target, sigma, mode="dollar"), "yes" if side_up else "no")
        assert abs(old - new) < 1e-12


def test_more_15m_sigma_is_the_shared_realized_sigma():
    closes = [100 * (1 + 0.001 * math.cos(i * 1.3)) for i in range(66)]
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:])]
    assert abs(sm.realized_sigma(closes, 65) - statistics.pstdev(rets)) < 1e-15


# ------------------------------------------------------------------ tails and swings (421-426)
def test_student_tails_are_fatter_but_same_middle():
    assert abs(sm.student_cdf(0.0) - 0.5) < 1e-12
    assert sm.student_cdf(4.0) < sm.phi(4.0)            # more chance of a big move against us
    assert abs(sm.student_cdf(1.0) + sm.student_cdf(-1.0) - 1.0) < 1e-9
    assert abs(sm.student_cdf(1.5, df=200) - sm.phi(1.5)) < 2e-3
    with pytest.raises(ValueError):
        sm.student_cdf(1.0, df=2)


def test_blended_sigma_and_short_history():
    calm = [100.0 * (1 + 0.0001 * ((-1) ** i)) for i in range(250)]
    wild = calm[:-15] + [100.0 * (1 + 0.003 * ((-1) ** i)) for i in range(15)]
    assert sm.blended_sigma(wild) > sm.blended_sigma(calm)
    assert sm.blended_sigma([100, 101]) is None
    short = [100.0 * (1 + 0.001 * ((-1) ** i)) for i in range(40)]  # 240-minute window drops out
    assert sm.blended_sigma(short) is not None


def test_time_of_day_news_and_jump_guard():
    assert sm.time_of_day_mult(dt.datetime(2026, 11, 13, 14, 0, tzinfo=UTC)) == 1.25
    assert sm.time_of_day_mult(dt.datetime(2026, 11, 13, 1, 0, tzinfo=UTC)) == 1.10
    assert sm.time_of_day_mult(dt.datetime(2026, 11, 13, 20, 0, tzinfo=UTC)) == 1.0
    assert sm.news_mult(NOW, [NOW + dt.timedelta(minutes=10)]) == 1.5
    assert sm.news_mult(NOW, [NOW + dt.timedelta(hours=2)]) == 1.0
    base = [100 * (1 + 0.0005 * ((-1) ** i)) for i in range(60)]
    assert sm.jump_guard(base + [base[-1] * 1.01])["jump"]
    assert not sm.jump_guard(base + [base[-1] * 1.0005])["jump"]


def test_multiplier_refresh_is_capped_and_waits_for_50():
    assert sm.measured_multiplier([1.3, -1.3, 1.3, -1.3]) == pytest.approx(1.3)
    assert sm.next_multiplier(1.0, 1.31, 49) == 1.0
    assert sm.next_multiplier(1.0, 1.31, 50) == 1.15
    assert sm.next_multiplier(1.3, 1.25, 80) == 1.25
    assert sm.next_multiplier(1.0, 9.0, 80, max_step=5) == 2.0
    assert sm.apply_basis(100.0, 0.5, 0.3) == 100.15


def test_error_by_minutes_and_trust_cap():
    rows = [{"minutes": 2, "fair": 0.9, "won": True}] * 60 + [{"minutes": 10, "fair": 0.7, "won": False}] * 10
    buckets = sm.error_by_minutes(rows)
    assert buckets[0]["n"] == 60 and buckets[0]["brier"] == 0.01
    assert buckets[3]["n"] == 10 and buckets[3]["bias"] == 0.7
    assert sm.trust_cap(buckets[3]) is None                 # under 50 rows: keep today's cap
    cap = sm.trust_cap(buckets[0])
    assert 0.08 <= cap <= 0.20


def test_confidence_and_stake_stay_inside_25():
    assert sm.confidence(None, None) == 0.0
    assert sm.confidence(3.0, 0.2) == 1.0
    assert sm.confidence(1.5, 0.1, n_history=10, hit_low=0.0) == 0.5   # track record needs 50
    for c in (-1, 0, 0.5, 1, 5):
        assert 0 < sm.confidence_stake(c) <= 25.0
    assert sm.confidence_stake(1) == 25.0 and sm.confidence_stake(0) == 10.0


def test_log_only_features():
    assert sm.book_imbalance([(0.5, 30)], [(0.52, 10)]) == 0.5
    assert sm.book_imbalance([], []) is None
    t0 = NOW.timestamp()
    trades = [{"ts": t0 - 50, "count_fp": "10", "taker_side": "yes", "yes_price_dollars": "0.50"},
              {"ts": t0 - 10, "count_fp": "4", "taker_side": "no", "yes_price_dollars": "0.53"},
              {"ts": t0 - 120, "count_fp": "99", "taker_side": "no", "yes_price_dollars": "0.40"}]
    assert sm.tape_momentum(trades, t0) == {"trades": 2, "net_yes": 6.0, "drift": 0.03}
    assert sm.cross_market(0.001, {"a": 0.002, "b": -0.001, "c": 0.0005, "d": 0.003})["same_way"] == 0.75
    assert sm.cross_market(None, {"a": 1})["same_way"] is None
    assert sm.crowding_penalty([], "yes") == 0.0
    assert sm.crowding_penalty(["yes"], "yes") == 0.01
    assert sm.crowding_penalty(["yes", "yes", "no"], "yes", free=2) == 0.01


# ------------------------------------------------------------------ exits (442-447)
def test_shared_exit_rules():
    assert sm.exit_decision(fair=0.6, bid=None)["why"] == "no bid"
    assert sm.exit_decision(fair=0.6, bid=0.9, rules={"take_profit": 0.9})["rule"] == "take-profit"
    assert sm.exit_decision(fair=0.6, bid=0.66, fee=0.02)["rule"] == "model-flip"
    assert not sm.exit_decision(fair=0.6, bid=0.63, fee=0.02)["sell"]                   # default: flip only
    assert sm.exit_decision(fair=0.6, bid=0.60, fee=0.0, rules={"little_left": 0.02})["rule"] == "little-left"
    decay = {"decay_min": 4, "decay_cushion": 0.6}
    assert sm.exit_decision(fair=0.55, bid=0.40, minutes_left=3, rules=decay)["rule"] == "time-decay"
    assert not sm.exit_decision(fair=0.65, bid=0.40, minutes_left=3, rules=decay)["sell"]
    assert sm.exit_decision(fair=0.9, bid=0.5, minutes_left=1, rules={"time_stop_min": 2})["rule"] == "time-stop"


# ------------------------------------------------------------------ cautious statistics (450-454)
def test_wilson_and_cautious_rules():
    lo, hi = sm.wilson(7, 10)
    assert 0.39 < lo < 0.40 and 0.89 < hi < 0.90
    assert sm.wilson(0, 0) == (0.0, 1.0)
    assert sm.enough_data(50) and not sm.enough_data(49) and not sm.enough_data(None)
    assert not sm.cautious_skip(3, 10, 0.55)               # raw 30% but the high end is 60%
    assert sm.cautious_skip(10, 60, 0.55)
    assert not sm.cautious_skip(0, 5, 0.55)                 # too few to judge
    assert sm.recovered(16, 20, 0.55) and not sm.recovered(12, 20, 0.55)
    assert sm.cautious_expectancy([1.0, -1.0, 1.0, -1.0]) < 0
    assert sm.cautious_expectancy([1.0]) is None


def test_compare_needs_50_rows():
    rows = [{"a": 0.6, "b": 0.8, "won": True}] * 49
    assert sm.compare(rows, "a", "b")["verdict"] == "need 50 rows"
    assert sm.compare(rows + rows[:1], "a", "b")["verdict"] == "b better"


def test_nothing_imports_shared_models_yet():
    for root, _, files in os.walk(HERE):
        if "model-lab-paper" in root or "__pycache__" in root:
            continue
        for name in files:
            if name.endswith(".py") and not name.startswith("test_") and name != "shared_models.py":
                text = open(os.path.join(root, name), encoding="utf-8", errors="ignore").read()
                assert "import shared_models" not in text, f"{name} imports shared_models"


def test_model_cards_cover_every_15m_tower():
    text = open(os.path.join(HERE, "MODEL_CARDS.md"), encoding="utf-8").read()
    for name in ("BTC 15m", "More 15m", "Commodity 15m", "Model change rules", "Known weak spots"):
        assert name in text


# ------------------------------------------------------------------ model lab
def _candles(product):
    base = NOW.timestamp() // 60 * 60
    out = []
    for i in range(300):
        t = base - 60 * (300 - i)
        c = 100.0 * (1 + 0.0006 * math.sin(i / 3.0))
        out.append([t, c, c, c, c, 1])
    return list(reversed(out))   # Coinbase sends newest first


def _markets(series, close_min=8, strike=99.9):
    close = (NOW + dt.timedelta(minutes=close_min)).isoformat().replace("+00:00", "Z")
    return [{"ticker": f"{series}-W1", "close_time": close, "floor_strike": strike,
             "yes_ask_dollars": "0.40", "no_ask_dollars": "0.62", "yes_bid_dollars": "0.38",
             "no_bid_dollars": "0.58", "yes_bid_size_fp": "30", "yes_ask_size_fp": "10"}]


def test_model_lab_logs_then_scores():
    body = ml.run({}, NOW, candles=_candles, open_markets=_markets, market=lambda t: {})
    assert len(body["pending"]) == len(ml.SERIES) and body["scored"] == []
    row = body["pending"][0]
    for key in ml.METHODS:
        assert 0.01 <= row[key] <= 0.99
    assert row["imbalance"] == 0.5
    btc = next(r for r in body["pending"] if r["series"] == "KXBTC15M")
    assert btc["btc_pull"] is not None
    again = ml.run(body, NOW, candles=_candles, open_markets=_markets, market=lambda t: {})
    assert len(again["pending"]) == len(ml.SERIES)          # same minute is not logged twice
    later = NOW + dt.timedelta(minutes=12)
    done = ml.run(again, later, candles=_candles, open_markets=lambda s: [],
                  market=lambda t: {"result": "yes" if "BTC" in t else "no"})
    assert len(done["scored"]) == len(ml.SERIES) and done["pending"] == []
    assert sum(1 for r in done["scored"] if r["won"]) == 1                 # losses are kept
    assert done["methods"]["fair_blend"]["verdict"] == "need 50 rows"
    assert set(done["exits"]) == set(ml.EXIT_RULES) | {"hold"}
    assert "settled 15-minute windows scored" in ml.card(done)


def test_model_lab_one_failure_does_not_stop_the_rest():
    def bad(product):
        if product == "ETH-USD":
            raise TimeoutError
        return _candles(product)

    body = ml.run({}, NOW, candles=bad, open_markets=_markets, market=lambda t: {})
    assert "ETH-USD candles failed (TimeoutError)" in body["notes"]
    assert len(body["pending"]) == len(ml.SERIES) - 1


def test_model_lab_exit_replay():
    rows = [
        {"ticker": "W", "at": "2026-11-13T18:00:00", "fair_now": 0.80, "minutes": 10, "won": True,
         "yes_ask": 0.60, "no_ask": 0.42, "yes_bid": 0.58, "no_bid": 0.40},
        {"ticker": "W", "at": "2026-11-13T18:05:00", "fair_now": 0.70, "minutes": 5, "won": True,
         "yes_ask": 0.80, "no_ask": 0.22, "yes_bid": 0.78, "no_bid": 0.20},
    ]
    out = ml.replay_exits(rows)
    assert out["hold"]["n"] == 1 and out["hold"]["pnl"] == round(1 - 0.60 - ml.kalshi_fee(0.60), 4)
    assert out["flip-only"]["sold"] == 1                    # bid 0.78 - fee beats fair 0.70 + 0.02
    assert out["flip-only"]["pnl"] == round(0.78 - ml.kalshi_fee(0.78) - 0.60 - ml.kalshi_fee(0.60), 4)


def test_model_lab_bot_main_and_registry(tmp_path):
    import new_towers
    import pimp_desk

    assert "model-lab" in new_towers.RESEARCH and new_towers.BY_ID["model-lab"]["max_open"] == 0
    assert pimp_desk._account_body("model-lab")["cash"] == 0.0
    assert "model-lab-paper/model_lab.json" in pimp_desk.SETTLEMENT_FILES
    bot = _load("model_lab_bot", "model-lab-paper/bot.py")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert bot.main([], root=str(tmp_path), candles_fetch=_candles, markets_fetch=_markets,
                        market_fetch=lambda t: {}, now=NOW) == 0
    assert "no trade" in out.getvalue()
    acct = json.loads((tmp_path / "model-lab-paper" / "paper_account.json").read_text())
    assert acct["cash"] == 0.0 and acct["open"] == [] and not acct["live_orders"]
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("model-lab")["ok"]
