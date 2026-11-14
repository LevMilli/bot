"""Kalshi fee once per order on BTC 15m, Commodity 15m, Kalshi S&P and Sized Kalshi (Nov 13). Offline."""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mods():
    return [_load("btc15m-signal/btc15m_signal.py", "fee_btc"), _load("commodity-15m-paper/bot.py", "fee_com")]


def test_order_fee_matches_kalshi_formula():
    for mod in _mods():
        assert mod.order_fee(10, 0.90) == 0.07      # 0.063 rounded up once
        assert mod.order_fee(29, 0.85) == 0.26
        assert mod.order_fee(31, 0.80) == 0.35
        assert mod.order_fee(1, 0.50) == 0.02
        assert mod.order_fee(0, 0.50) == 0.0 and mod.order_fee(5, 1.0) == 0.0 and mod.order_fee(5, None) == 0.0


def test_once_per_order_is_never_more_than_per_contract():
    for mod in _mods():
        per = getattr(mod, "fee_per_contract", None) or mod.kalshi_fee
        for c in (1, 3, 10, 25, 60):
            for p in (0.05, 0.3, 0.5, 0.81, 0.97):
                assert mod.order_fee(c, p) <= round(c * per(p), 2) + 1e-9


def test_sell_books_bid_less_one_order_fee():
    for mod in _mods():
        mod.record_close = lambda *a, **k: None
        mod.IS_SHADOW = True
        state = {"cash": 100.0, "open": [], "closed": []}
        pos = {"ticker": "T", "side": "YES", "contracts": 10, "cost": 7.2, "fill_id": "T|1", "series": "KXBTC15M"}
        pnl = mod.paper_sell(state, pos, 0.90, 0.01, "take-profit")
        row = state["closed"][-1]
        assert row["payout"] == 8.93 and row["exit_fee_order"] == 0.07
        assert abs(pnl - (8.93 - 7.2)) < 1e-9 and abs(state["cash"] - 108.93) < 1e-9


def test_zero_fee_from_caller_still_means_no_fee():
    for mod in _mods():
        mod.record_close = lambda *a, **k: None
        mod.IS_SHADOW = True
        state = {"cash": 0.0, "open": [], "closed": []}
        mod.paper_sell(state, {"ticker": "T", "side": "YES", "contracts": 4, "cost": 2.0}, 0.0, 0, "no bid")
        assert state["closed"][-1]["payout"] == 0.0


def test_sp_and_sized_already_charge_once_per_order():
    for rel in ("kalshi-sp500-paper/paper_sim.py", "kalshi-sized-paper/paper_sim.py"):
        sim = _load(rel, "fee_" + rel.split("/")[0].replace("-", "_"))
        assert sim.taker_fee(10, 0.90) == 0.07
        assert sim.taker_fee(29, 0.85) == 0.26
