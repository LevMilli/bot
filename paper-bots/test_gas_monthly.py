"""Gas monthly tower (KXAAAGASM). Offline."""
import datetime as dt
import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _bot():
    spec = importlib.util.spec_from_file_location("gas_monthly_bot", os.path.join(HERE, "gas-monthly-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


READING = {"as_of": "2026-11-13", "current": 3.8724, "yesterday": 3.9081, "week_ago": 4.0688}


def _markets(event):
    base = {"event_ticker": event, "strike_type": "greater", "yes_ask_dollars": "0.40",
            "no_ask_dollars": "0.62", "yes_bid_dollars": "0.38", "no_bid_dollars": "0.60"}
    return [dict(base, ticker=f"{event}-3.70", floor_strike=3.70),
            dict(base, ticker=f"{event}-3.60", floor_strike=3.60),
            dict(base, ticker=f"{event}-x", strike_type="between", floor_strike=3.5)]


def test_far_and_unfitted_are_log_only():
    bot = _bot()
    unfitted = bot.gm.fit({})
    far = bot.quotes_for(_markets("KXAAAGASM-26NOV30"), READING, unfitted)
    assert len(far) == 4 and all(q["log_only"] for q in far)
    assert "buys only within 14d" in far[0]["log_reason"]
    mid = bot.quotes_for(_markets("KXAAAGASM-26NOV20"), READING, unfitted)
    assert all(q["log_only"] and "learning momentum" in q["log_reason"] for q in mid)
    near = bot.quotes_for(_markets("KXAAAGASM-26NOV15"), READING, unfitted)
    assert near and not any(q.get("log_only") for q in near)
    fitted = dict(unfitted, fitted=True)
    ok = bot.quotes_for(_markets("KXAAAGASM-26NOV20"), READING, fitted)
    assert ok and not any(q.get("log_only") for q in ok)
    yes = next(q for q in ok if q["side"] == "yes" and q["ticker"].endswith("3.60"))
    no = next(q for q in ok if q["side"] == "no" and q["ticker"].endswith("3.60"))
    assert abs(yes["fair"] + no["fair"] - 1.0) < 1e-9 and "month end" in yes["label"]


def test_history_merges_weekly_read_only(tmp_path, monkeypatch):
    bot = _bot()
    weekly = tmp_path / "gas-weekly-paper"
    own = tmp_path / "gas-monthly-paper"
    weekly.mkdir()
    own.mkdir()
    (weekly / "aaa_history.json").write_text(json.dumps({"2026-11-01": 4.0, "2026-11-02": 4.01, "bad": 1}))
    (own / "aaa_history.json").write_text(json.dumps({"2026-11-02": 4.02, "2026-11-03": 4.03}))
    before = (weekly / "aaa_history.json").read_text()
    monkeypatch.setattr(bot, "WEEKLY_DIR", str(weekly))
    monkeypatch.setattr(bot, "HERE", str(own))
    merged = bot.merged_history()
    assert merged == {"2026-11-01": 4.0, "2026-11-02": 4.02, "2026-11-03": 4.03}
    assert (weekly / "aaa_history.json").read_text() == before


def test_model_reads_cache_and_notes_dormant(tmp_path, monkeypatch):
    bot = _bot()
    monkeypatch.setattr(bot, "HERE", str(tmp_path))
    monkeypatch.setattr(bot, "WEEKLY_DIR", str(tmp_path / "none"))
    now = dt.datetime(2026, 11, 13, 18, tzinfo=dt.timezone.utc)
    (tmp_path / "aaa_latest.json").write_text(json.dumps({"fetched": now.isoformat(), "reading": READING}))
    monkeypatch.setattr(bot.engine, "kalshi_open_markets", lambda series: [])
    assert bot.model({}, now) == ([], "no open markets: KXAAAGASM")
    monkeypatch.setattr(bot.engine, "kalshi_open_markets", lambda series: _markets("KXAAAGASM-26NOV30"))
    quotes, note = bot.model({}, now)
    assert len(quotes) == 4 and note == ""
    assert bot.SPEC["floor"] == 0.05 and bot.SERIES == "KXAAAGASM"
