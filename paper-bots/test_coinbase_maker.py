"""Coinbase maker tower. Offline."""
import datetime as dt
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "coinbase-maker-paper"))

import maker_model as mm  # noqa: E402

UTC = dt.timezone.utc
T0 = 1_800_000_000 - (1_800_000_000 % 900)


def _bot():
    spec = importlib.util.spec_from_file_location("coinbase_maker_bot", os.path.join(HERE, "coinbase-maker-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_fee_math_is_honest():
    assert mm.maker_trip() == 0.01
    assert abs(mm.take_profit_move() - 0.06) < 1e-12
    assert abs(mm.bar_needed() - 0.24) < 1e-12
    assert mm.bar_needed(0.01) == mm.bar_needed()   # floor cannot go under 0.05
    pnl, fees = mm.pnl(25.0, 100.0, 106.0, True)
    assert fees == round(25 * 0.005 + 25 * 1.06 * 0.005, 4) and pnl == round(1.5 - fees, 4)
    loss, _ = mm.pnl(25.0, 100.0, 98.5, False)
    assert loss < -0.375


def test_parse_drops_open_bar():
    rows = [[T0, 1, 2, 1.5, 1.6, 9], [T0 + 900, 1, 2, 1.5, 1.7, 9], [T0 - 900, 1, 2, 1.5, 1.4, 9]]
    bars = mm.parse_candles(rows, T0 + 900 + 100)
    assert [b["t"] for b in bars] == [T0 - 900, T0]


def test_fill_and_exit_rules():
    assert mm.entry_fills(100.0, {"low": 99.9}) and not mm.entry_fills(100.0, {"low": 100.0})
    pos = {"entry": 100.0, "take_profit": 106.0}
    assert mm.exit_on_bar(pos, {"low": 98.0, "high": 107, "open": 99, "close": 100}, 0, 1)[0] == "stop"
    assert mm.exit_on_bar(pos, {"low": 99, "high": 106.5, "open": 100, "close": 101}, 0, 1) == ("take-profit", 106.0, True)
    assert mm.exit_on_bar(pos, {"low": 99, "high": 101, "open": 100, "close": 100}, -2.5, 1)[0] == "model-flip"
    assert mm.exit_on_bar(pos, {"low": 99, "high": 101, "open": 100, "close": 100}, 0, 24)[0] == "time"
    assert mm.exit_on_bar(pos, {"low": 99, "high": 101, "open": 100, "close": 100}, 0, 1) is None


def _candles(closes, start=T0, lows=None, highs=None):
    rows = []
    for i, c in enumerate(closes):
        lo = (lows or {}).get(i, c * 0.999)
        hi = (highs or {}).get(i, c * 1.001)
        rows.append([start + i * 900, lo, hi, c, c, 1])
    return rows


def test_book_orders_fills_and_takes_profit(tmp_path):
    bot = _bot()
    base = [100 + 0.1 * (i % 2) for i in range(20)]
    jump = base + [130.0]                       # +30% bar, z far above 2
    now = dt.datetime.fromtimestamp(T0 + len(jump) * 900 + 60, UTC)
    data = {"ETH-USD": _candles(jump), "SOL-USD": _candles(base)}
    assert bot.main([], here=str(tmp_path), candles=data, now=now) == 0
    state = json.loads((tmp_path / "paper_account.json").read_text())
    assert state["orders"][0]["product"] == "ETH-USD" and state["orders"][0]["limit"] == 130.0
    assert state["open"] == [] and state["cash"] == 500.0
    # Next bar trades below the limit: fill. The bar after trades above take-profit: maker exit.
    more = jump + [131.0, 140.0]
    rows = _candles(more, lows={21: 129.0}, highs={22: 139.0})
    now2 = dt.datetime.fromtimestamp(T0 + len(more) * 900 + 60, UTC)
    bot.main([], here=str(tmp_path), candles={"ETH-USD": rows, "SOL-USD": _candles(base)}, now=now2)
    state = json.loads((tmp_path / "paper_account.json").read_text())
    assert state["open"] == [] and len(state["closed"]) == 1
    done = state["closed"][0]
    assert done["exit"] == "take-profit" and done["maker_exit"] and done["entry"] == 130.0
    assert done["pnl"] > 0 and abs(state["cash"] - (500 + done["pnl"])) < 1e-6


def test_unfilled_order_expires_and_old_signal_is_not_ordered(tmp_path):
    bot = _bot()
    base = [100 + 0.1 * (i % 2) for i in range(20)]
    jump = base + [130.0]
    old = dt.datetime.fromtimestamp(T0 + len(jump) * 900 + 3600, UTC)
    bot.main([], here=str(tmp_path / "a"), candles={"ETH-USD": _candles(jump), "SOL-USD": []}, now=old)
    assert json.loads((tmp_path / "a" / "paper_account.json").read_text())["orders"] == []
    now = dt.datetime.fromtimestamp(T0 + len(jump) * 900 + 60, UTC)
    bot.main([], here=str(tmp_path / "b"), candles={"ETH-USD": _candles(jump), "SOL-USD": []}, now=now)
    more = jump + [131.0, 132.0]
    rows = _candles(more, lows={21: 130.5, 22: 131.5})
    now2 = dt.datetime.fromtimestamp(T0 + len(more) * 900 + 60, UTC)
    bot.main([], here=str(tmp_path / "b"), candles={"ETH-USD": rows, "SOL-USD": []}, now=now2)
    state = json.loads((tmp_path / "b" / "paper_account.json").read_text())
    assert state["orders"] == [] and state["open"] == [] and state["expired"] == 1


def test_entry_gate_blocks_new_orders(tmp_path, monkeypatch):
    bot = _bot()
    monkeypatch.setenv("DESK_BLOCK_ENTRIES", "1")
    base = [100 + 0.1 * (i % 2) for i in range(20)]
    jump = base + [130.0]
    now = dt.datetime.fromtimestamp(T0 + len(jump) * 900 + 60, UTC)
    bot.main([], here=str(tmp_path), candles={"ETH-USD": _candles(jump), "SOL-USD": []}, now=now)
    assert json.loads((tmp_path / "paper_account.json").read_text())["orders"] == []
