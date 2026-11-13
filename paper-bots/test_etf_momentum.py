"""SPY and IWM momentum twins (etf_momentum_book.py). Offline."""
import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import etf_momentum_book as book  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


QQQ_TESTS = _load("qqq_tests_for_etf", os.path.join(HERE, "test_qqq_momentum.py"))
QQQ_BOT = os.path.join(HERE, "qqq-momentum-paper", "bot.py")


def _bot(symbol):
    low = symbol.lower()
    return _load(f"{low}_momentum_bot", os.path.join(HERE, f"{low}-momentum-paper", "bot.py"))


def _replay(main, here, chart, last):
    for k in range(1, 80):
        now = (dt.datetime.combine(last, dt.time(9, 30), book.qm.NY)
               + dt.timedelta(minutes=5 * k + 1)).astimezone(dt.timezone.utc)
        with contextlib.redirect_stdout(io.StringIO()):
            main([], here=str(here), chart=chart, now=now)
    return json.loads((here / "paper_account.json").read_text())


def test_twins_trade_exactly_like_qqq_on_the_same_bars(tmp_path):
    chart, last = QQQ_TESTS._sessions(16, QQQ_TESTS._rally)
    qqq = _replay(_load("qqq_bot_for_etf", QQQ_BOT).main, tmp_path / "qqq", chart, last)
    assert qqq["closed"]
    for symbol in ("SPY", "IWM"):
        state = _replay(_bot(symbol).main, tmp_path / symbol, chart, last)
        assert state["open"] == [] and state["shadow_only"] is True
        assert len(state["closed"]) == len(qqq["closed"])
        for mine, ref in zip(state["closed"], qqq["closed"]):
            assert mine["ticker"] == symbol and mine["label"].startswith(symbol)
            assert mine["side"] == ref["side"] and abs(mine["pnl"] - ref["pnl"]) < 1e-9
        assert abs(state["cash"] - qqq["cash"]) < 1e-9


def test_closed_day_gate_and_symbol_guard(tmp_path, monkeypatch):
    chart, last = QQQ_TESTS._sessions(16, QQQ_TESTS._rally)
    spy = _bot("SPY")
    sunday = dt.datetime(2026, 11, 15, 15, tzinfo=dt.timezone.utc)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert spy.main(here=str(tmp_path / "a"), chart=chart, now=sunday) == 0
    assert "no SPY session today" in out.getvalue() and "no trade" in out.getvalue()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert spy.main(here=str(tmp_path / "b"), chart={}, now=sunday) == 0
    assert "no trade" in out.getvalue()
    monkeypatch.setenv("DESK_BLOCK_ENTRIES", "1")
    state = _replay(_bot("IWM").main, tmp_path / "gated", chart, last)
    assert state["open"] == [] and state["closed"] == [] and state["cash"] == 500
    try:
        book.main("QQQ", "x", "x", str(tmp_path / "c"), chart=chart, now=sunday)
    except ValueError:
        pass
    else:
        raise AssertionError("book must not run QQQ itself")
    assert "SPY" in book.bars_url("SPY") and "IWM" in book.bars_url("IWM")
    assert book.FLOOR == 0.02
