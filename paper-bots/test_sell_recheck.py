"""Early-sale bid re-read (More 15m, Nov 13). Offline."""
import datetime as dt
import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 12, 20, 36, tzinfo=UTC)


def _bot():
    spec = importlib.util.spec_from_file_location("more15_bot_rc", os.path.join(HERE, "more-15m-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tape(ticker, now):
    return [{"yes_price_dollars": "0.30", "count_fp": "500"}, {"yes_price_dollars": "0.70", "count_fp": "500"}]


def _q(fair=0.70, ask=0.60, bid=0.55):
    return {"ticker": "KXSOL15M-W", "event": "KXSOL15M-W-E", "side": "yes", "fair": fair, "ask": ask, "bid": bid}


def _acct(tower):
    return json.load(open(os.path.join(tower, "paper_account.json")))


def _run(tower, quotes, market, waits):
    import kalshi_shadow_tower as engine
    engine.run_tower(_bot().SPEC, tower, None, now=NOW, fetch=lambda t: {}, quotes=quotes, tape=_tape,
                     market=market, sleep=waits.append)


def _sell_with_recheck_bid(tmp_path, bid2):
    tower, waits = str(tmp_path / "t"), []
    _run(tower, [_q()], lambda t: {}, waits)
    cash_before = _acct(tower)["cash"]
    market = (lambda t: {"ticker": t, "yes_bid_dollars": str(bid2), "no_bid_dollars": "0.1"}) if bid2 is not None \
        else (lambda t: (_ for _ in ()).throw(TimeoutError()))
    _run(tower, [_q(fair=0.40, bid=0.80)], market, waits)   # model flip: sale decided at 0.80
    acct = _acct(tower)
    return acct, cash_before, waits


def test_more_15m_has_three_second_recheck():
    assert _bot().SPEC["sell_recheck_sec"] == 3


def test_lower_bid_on_recheck_books_the_lower_bid(tmp_path):
    import kalshi_shadow_tower as engine
    acct, cash_before, waits = _sell_with_recheck_bid(tmp_path, 0.70)
    row = acct["closed"][0]
    assert waits == [3.0]
    assert row["exit"] == "model-flip"            # decision unchanged
    assert row["exit_bid_decided"] == 0.80 and row["exit_bid"] == 0.70
    c = int(row["contracts"])
    assert row["payout"] == round(c * 0.70 - engine.order_fee(c, 0.70), 2)
    assert row["pnl"] == round(row["payout"] - row["cost"], 2)
    assert abs(acct["cash"] - (cash_before + row["payout"])) < 0.01
    assert "booked the lower bid" in row["exit_recheck"] and row.get("exit_quote_at")


def test_higher_bid_on_recheck_keeps_the_decided_bid(tmp_path):
    acct, _, _ = _sell_with_recheck_bid(tmp_path, 0.90)
    row = acct["closed"][0]
    assert row["exit_bid"] == 0.80 and row["exit_bid_recheck"] == 0.90 and "held" in row["exit_recheck"]


def test_failed_recheck_keeps_decided_bid(tmp_path):
    acct, _, _ = _sell_with_recheck_bid(tmp_path, None)
    row = acct["closed"][0]
    assert row["exit_bid"] == 0.80 and "failed" in row["exit_recheck"]


def test_buys_carry_quote_read_times(tmp_path):
    tower = str(tmp_path / "t")
    _run(tower, [_q()], lambda t: {}, [])
    pos = _acct(tower)["open"][0]
    assert pos["quote_read_from"] and pos["quote_read_to"] >= pos["quote_read_from"]


def test_towers_without_the_option_never_wait(tmp_path):
    import kalshi_shadow_tower as engine
    spec = dict(_bot().SPEC)
    spec.pop("sell_recheck_sec")
    tower, waits = str(tmp_path / "t"), []
    for q in ([_q()], [_q(fair=0.40, bid=0.80)]):
        engine.run_tower(spec, tower, None, now=NOW, fetch=lambda t: {}, quotes=q, tape=_tape,
                         market=lambda t: {"yes_bid_dollars": "0.1"}, sleep=waits.append)
    row = _acct(tower)["closed"][0]
    assert waits == [] and row["exit_bid"] == 0.80 and "exit_recheck" not in row
