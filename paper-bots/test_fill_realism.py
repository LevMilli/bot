"""Fill realism: shared settings, helpers, flags (off by default) and the lab. Offline."""
import ast
import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "fill-realism-lab-paper"))

import fill_realism as fr  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402
import lab_model as lm  # noqa: E402
import strict_fill  # noqa: E402

NOW = dt.datetime(2026, 11, 13, 18, tzinfo=dt.timezone.utc)
T0 = NOW.timestamp()


def _trade(ts, yes, count):
    return {"created_time": dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(),
            "yes_price_dollars": f"{yes:.4f}", "count_fp": f"{count:.2f}"}


@pytest.fixture(autouse=True)
def _flags_off(monkeypatch):
    for var in fr.FLAGS.values():
        monkeypatch.delenv(var, raising=False)


# ------------------------------------------------------------------ settings and flags
def test_settings_match_the_live_defaults():
    src = open(os.path.join(HERE, "strict_fill.py"), encoding="utf-8").read()
    for env, key in (("PAPER_REQUOTE_SECONDS", "requote_seconds"), ("PAPER_DEPTH_SHARE", "depth_share"),
                     ("PAPER_MAX_SLIP", "max_slip"), ("PAPER_SPOT_MAX_SLIP", "spot_max_slip"),
                     ("PAPER_SPOT_FALLBACK_SLIP", "spot_fallback_slip")):
        m = re.search(rf'"{env}", ([0-9.]+)\)', src)
        assert m and float(m.group(1)) == fr.SETTINGS[key], env
    assert strict_fill.FALLBACK_SLIP == fr.SETTINGS["fallback_slip"]
    assert engine.TAPE_LOOKBACK_SEC == fr.SETTINGS["tape_lookback_sec"]
    assert engine.TAPE_MAX_READS == fr.SETTINGS["tape_max_reads"]
    assert len(fr.GENEROUS_WAYS) >= 10


def test_every_flag_is_off_by_default(monkeypatch):
    assert not any(fr.flags_state().values())
    monkeypatch.setenv("FILL_BTC15M_TAPE", "true")       # only exactly "1" turns a flag on
    assert not fr.flag("btc15m_tape")
    monkeypatch.setenv("FILL_BTC15M_TAPE", "1")
    assert fr.flag("btc15m_tape")


def test_no_config_turns_a_flag_on():
    for name in os.listdir(HERE):
        if name.endswith(".json") or name in ("Makefile",):
            text = open(os.path.join(HERE, name), encoding="utf-8", errors="ignore").read()
            for var in fr.FLAGS.values():
                assert var not in text, f"{name} mentions {var}"


# ------------------------------------------------------------------ tape check (207-209)
def test_tape_counts_only_trades_inside_the_window():
    trades = [_trade(T0 - 400, 0.60, 50), _trade(T0 - 100, 0.60, 4), _trade(T0 + 30, 0.60, 50)]
    out = fr.tape_cover(trades, "yes", 0.60, 5, window_start=T0 - 300, decided_at=T0)
    assert out["volume"] == 4 and not out["covered"] and out["outside_window"] == 2


def test_tape_counts_only_trades_at_or_better_than_our_price():
    trades = [_trade(T0 - 60, 0.62, 100), _trade(T0 - 50, 0.60, 3), _trade(T0 - 40, 0.55, 2)]
    out = fr.tape_cover(trades, "yes", 0.60, 5, window_start=T0 - 300, decided_at=T0)
    assert out["volume"] == 5 and out["covered"] and out["worse_price"] == 1
    # NO side: a YES print at 0.45 is a NO price of 0.55
    no = fr.tape_cover([_trade(T0 - 10, 0.45, 9)], "no", 0.55, 9, window_start=T0 - 300, decided_at=T0)
    assert no["covered"]


def test_tape_volume_must_cover_the_full_count():
    trades = [_trade(T0 - 10, 0.60, 4.99)]
    assert not fr.tape_cover(trades, "yes", 0.6, 5, window_start=T0 - 300, decided_at=T0)["covered"]
    assert fr.tape_cover(trades + [_trade(T0 - 5, 0.6, 0.01)], "yes", 0.6, 5,
                         window_start=T0 - 300, decided_at=T0)["covered"]


def test_tape_gate_reasons():
    ok = lambda t, n: [_trade(T0 - 10, 0.60, 10)]  # noqa: E731
    thin = lambda t, n: [_trade(T0 - 10, 0.60, 1)]  # noqa: E731

    def boom(t, n):
        raise TimeoutError

    assert fr.tape_gate("KX-1", "YES", 0.60, 5, now=NOW, fetch=ok) == ""
    assert "need 5" in fr.tape_gate("KX-1", "YES", 0.60, 5, now=NOW, fetch=thin)
    assert "read failed" in fr.tape_gate("KX-1", "YES", 0.60, 5, now=NOW, fetch=boom)


# ------------------------------------------------------------------ books (213-218)
def test_multi_level_fill_walks_the_book():
    out = fr.walk_book([(0.62, 10), (0.60, 6), (0.61, 4)], 8)
    assert out["levels"] == [{"price": 0.6, "contracts": 3}, {"price": 0.61, "contracts": 2},
                             {"price": 0.62, "contracts": 3}]
    assert out["full"] and out["avg_price"] == round((3 * 0.6 + 2 * 0.61 + 3 * 0.62) / 8, 4)
    capped = fr.walk_book([(0.60, 6), (0.65, 100)], 8, limit=0.63)
    assert capped["contracts"] == 3 and capped["short"] == 5 and not capped["full"]


def test_early_sale_never_sells_more_than_the_bid_size_shown():
    for bids, want in (([(0.70, 3)], 10), ([(0.70, 4), (0.69, 2)], 10), ([(0.7, 100)], 10)):
        out = fr.sell_cap(bids, want, share=1.0)
        assert out["contracts"] <= min(want, out["bid_size_shown"])
    half = fr.sell_cap([(0.70, 10)], 10)
    assert half["contracts"] == 5 and not half["full"]


# ------------------------------------------------------------------ no-fills (248-252)
def test_market_closed_before_fill():
    assert fr.no_fill(0.6, close_time=T0, fill_at=T0 + 1) == "market closed before the fill"
    assert fr.no_fill(0.6, status="finalized") == "market closed before the fill"
    assert fr.no_fill(0.6, quoted=0.61, close_time=T0 + 60, fill_at=T0) == ""


def test_price_jumped_past_limit():
    assert fr.no_fill(0.60, quoted=0.64) == "price jumped past our limit"
    assert fr.no_fill(0.60, quoted=0.63) == ""
    assert fr.no_fill(0.60, quoted=0.62, limit=0.61) == "price jumped past our limit"


def test_skip_text_maps_to_plain_reasons():
    assert fr.classify_skip("price ran away before the fill (0.60 → 0.65)") == "jumped"
    assert fr.classify_skip("book too thin at the re-checked price") == "thin"
    assert fr.classify_skip("Kalshi tape: 0 contracts traded at 0.60 or better") == "no_tape"
    assert fr.classify_skip("edge below floor") == ""


# ------------------------------------------------------------------ maker (227-233)
def test_maker_fee_math():
    assert fr.maker_fee(0.5, 100) == 0.0                     # M is 0 on most series
    assert fr.maker_fee(0.5, 100, multiplier=1) == 0.44
    assert fr.kalshi_fee(0.5, 100) == 1.75
    assert fr.kalshi_fee(0.5, 1) == engine.fee(0.5)


def test_maker_fill_needs_the_tape_to_trade_through():
    touch = [_trade(T0 + 10, 0.60, 50)]
    assert fr.maker_fill("yes", 0.60, 5, touch, queue_ahead=float("inf"), placed_at=T0)["filled"] == 0
    through = [_trade(T0 + 10, 0.59, 3), _trade(T0 + 20, 0.58, 10)]
    out = fr.maker_fill("yes", 0.60, 5, through, queue_ahead=float("inf"), placed_at=T0)
    assert out["filled"] == 5 and out["status"] == "filled"
    before = [_trade(T0 - 10, 0.50, 50)]
    assert fr.maker_fill("yes", 0.60, 5, before, placed_at=T0)["filled"] == 0


def test_maker_queue_position_we_are_last_in_line():
    at_price = [_trade(T0 + 5, 0.60, 8), _trade(T0 + 9, 0.60, 4)]
    out = fr.maker_fill("yes", 0.60, 5, at_price, queue_ahead=10, placed_at=T0)
    assert out["filled"] == 2 and out["status"] == "partial" and out["queue_left"] == 0


def test_maker_cancel_when_price_moves_away():
    path = [(T0 + 30, 0.61), (T0 + 60, 0.64)]
    trades = [_trade(T0 + 40, 0.59, 2), _trade(T0 + 90, 0.55, 50)]
    out = fr.maker_fill("yes", 0.60, 5, trades, queue_ahead=0, placed_at=T0, best_ask_path=path)
    assert out["filled"] == 2 and out["status"] == "partial-cancelled" and out["cancelled_at"] == T0 + 60
    assert fr.adverse_move("yes", 0.60, 0.55) == -0.05


# ------------------------------------------------------------------ tape gap and score (219-242)
def test_tape_gap_quality_and_flag():
    trades = [_trade(T0 + 10, 0.62, 10), _trade(T0 - 20, 0.60, 10), _trade(T0 + 500, 0.10, 99)]
    gap = fr.tape_gap("yes", 0.60, trades, T0)
    assert gap["tape_price"] == 0.61 and gap["gap"] == -0.01 and gap["tape_volume"] == 20
    assert fr.fill_quality([0.01, 0.02], [True, True]) == 100
    assert fr.fill_quality([-0.01] * 5, [True] * 4 + [False]) == 82
    assert fr.beats_tape([-0.01] * 5) and not fr.beats_tape([-0.01] * 4) and not fr.beats_tape([0.0] * 9)


def test_daily_sample_is_stable_and_ten():
    rows = [{"bot": "b", "ticker": f"KX-{i}", "opened": str(i), "side": "yes"} for i in range(30)]
    a, b = fr.daily_sample(rows, "2026-11-13"), fr.daily_sample(list(reversed(rows)), "2026-11-13")
    assert a == b and len(a) == 10 and fr.daily_sample(rows, "2026-11-14") != a


# ------------------------------------------------------------------ fees (222-226)
def _consts(path, *names):
    tree = ast.parse(open(os.path.join(HERE, path), encoding="utf-8").read())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return {n: out.get(n) for n in names}


def test_no_tower_charges_less_than_the_fee_reference():
    ref = fr.FEE_REFERENCE
    cb = json.load(open(os.path.join(HERE, "coinbase-spot-paper", "config.json")))
    lock = _consts("coinbase-spot-paper/bot.py", "LOCKED_TAKER_MIN", "LOCKED_SLIP_MIN")
    assert min(cb["taker_fee"], lock["LOCKED_TAKER_MIN"]) >= ref["coinbase-spot"]["taker"]
    assert min(cb["slippage"], lock["LOCKED_SLIP_MIN"]) >= ref["coinbase-spot"]["slippage"]
    carry = _consts("btc-carry-paper/bot.py", "SPOT_TAKER", "PERP_TAKER")
    assert carry["SPOT_TAKER"] >= ref["btc-carry"]["spot_taker"]
    assert carry["PERP_TAKER"] >= ref["btc-carry"]["perp_taker"]
    meme = _consts("memecoin-paper/config.py", "PAPER_FILL")["PAPER_FILL"]
    assert meme["swap_fee_pct"] >= ref["memecoin"]["swap_fee_pct"]
    qqq = _consts("qqq-momentum-paper/qqq_model.py", "COMMISSION", "SLIPPAGE")
    assert qqq["COMMISSION"] >= ref["qqq-momentum"]["commission"]
    assert qqq["SLIPPAGE"] >= ref["qqq-momentum"]["slippage"]
    assert strict_fill.kalshi_fee(0.5) == fr.kalshi_fee(0.5)


def test_fee_review_is_monthly():
    assert not fr.fee_review_due(dt.date(2026, 11, 20))
    assert fr.fee_review_due(dt.date(2026, 12, 20))


# ------------------------------------------------------------------ shadow engine flags
SPEC = {"id": "t", "name": "T", "floor": 0.05, "max_open": 2}


def _quote(**kw):
    q = {"ticker": "KXT-1", "event": "KXT", "side": "yes", "fair": 0.80, "ask": 0.60, "bid": 0.58,
         "label": "T", "why": "test"}
    q.update(kw)
    return q


def _run(tmp_path, quotes, monkeypatch=None):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        engine.run_tower(SPEC, str(tmp_path), lambda c, n: (quotes, ""), now=NOW, fetch=lambda t: {})
    return json.loads((tmp_path / "paper_account.json").read_text()), out.getvalue()


def test_shadow_strict_flag_off_leaves_buys_alone(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(strict_fill, "recheck", lambda *a, **k: called.append(1))
    state, _ = _run(tmp_path, [_quote()])
    assert not called and state["open"][0]["ask"] == 0.60 and "fill_check" not in state["open"][0]


def test_shadow_strict_flag_on_rechecks(tmp_path, monkeypatch):
    monkeypatch.setenv("FILL_SHADOW_STRICT", "1")
    book = {"orderbook_fp": {"no_dollars": [["0.38", "6"]], "yes_dollars": []}}  # YES ask 0.62, 6 deep
    real = strict_fill.recheck
    monkeypatch.setattr(strict_fill, "recheck",
                        lambda *a, **k: real(*a, **dict(k, fetch=lambda t: book, wait=0)))
    state, _ = _run(tmp_path, [_quote()])
    pos = state["open"][0]
    assert pos["ask"] == 0.62 and pos["contracts"] == 3 and pos["fill_check"]["capped"]
    assert pos["cost"] == round(3 * (0.62 + engine.fee(0.62)), 2)


def test_shadow_strict_flag_on_skips_a_runaway_price(tmp_path, monkeypatch):
    monkeypatch.setenv("FILL_SHADOW_STRICT", "1")
    book = {"orderbook_fp": {"no_dollars": [["0.30", "100"]]}}  # YES ask 0.70
    real = strict_fill.recheck
    monkeypatch.setattr(strict_fill, "recheck",
                        lambda *a, **k: real(*a, **dict(k, fetch=lambda t: book, wait=0)))
    state, out = _run(tmp_path, [_quote()])
    assert state["open"] == [] and "ran away" in out


def test_shadow_sell_depth_flag(tmp_path, monkeypatch):
    pos = {"ticker": "KXT-1", "event": "KXT", "side": "yes", "contracts": 10, "cost": 5.0, "label": "T"}
    flip = [_quote(fair=0.40, bid=0.70, bid_size=8)]
    state = {"cash": 0.0, "open": [dict(pos)], "closed": []}
    assert len(engine.model_flips(state, flip, NOW, 0.02)) == 1          # flag off: sells all 10
    monkeypatch.setenv("FILL_SHADOW_SELL_DEPTH", "1")
    state = {"cash": 0.0, "open": [dict(pos)], "closed": []}
    assert engine.model_flips(state, flip, NOW, 0.02) == [] and "too thin" in state["open"][0]["sell_held"]
    state = {"cash": 0.0, "open": [dict(pos)], "closed": []}
    assert len(engine.model_flips(state, [_quote(fair=0.4, bid=0.7, bid_size=40)], NOW, 0.02)) == 1


def test_btc_and_commodity_tape_flags_are_wired_off():
    for path, name in (("btc15m-signal/btc15m_signal.py", "btc15m_tape"),
                       ("commodity-15m-paper/bot.py", "commodity_tape")):
        src = open(os.path.join(HERE, path), encoding="utf-8").read()
        assert f'fill_realism.flag("{name}")' in src
    more = open(os.path.join(HERE, "more-15m-paper", "bot.py"), encoding="utf-8").read()
    assert "fill_realism" not in more                                     # More 15m is frozen


# ------------------------------------------------------------------ the lab
def _states():
    return {
        "btc15m": {"open": [], "closed": [
            {"ticker": "KXBTC15M-A", "side": "YES", "ask": 0.80, "contracts": 10,
             "opened": "2026-11-13 17:00:00 UTC", "result": "yes", "pnl": 1.5, "closed": "2026-11-13T17:15:00+00:00"},
            {"ticker": "KXBTC15M-B", "side": "yes", "ask": 0.70, "contracts": 10,
             "opened": "2026-11-13T16:00:00+00:00", "result": "no", "pnl": -7.2},
        ]},
        "coinbase-spot": {"open": [{"ticker": "ETH-USD", "side": "buy", "entry_price": 3000.0,
                                    "opened": "2026-11-13T15:00:00+00:00"}], "closed": []},
    }


def _tape(ticker, lo, hi):
    base = dt.datetime(2026, 11, 13, 17, tzinfo=dt.timezone.utc).timestamp()
    if ticker.endswith("A"):
        return [_trade(base - 30, 0.79, 20), _trade(base + 20, 0.81, 10), _trade(base + 60, 0.78, 50)]
    return []


def test_lab_grades_each_buy_once_and_keeps_losses(tmp_path):
    reads = []

    def tape(t, lo, hi):
        reads.append(t)
        return _tape(t, lo, hi)

    body = lm.run(_states(), {}, tape, NOW, candle_fetch=lambda b, t, o: 3030.0)
    t = body["towers"]["btc15m"]
    assert t["buys"] == 2 and t["tape_covered"] == 1 and t["tape_blocked"] == 1
    assert t["tape_blocked_today"] == 1
    assert t["maker_book"]["tries"] == 2 and t["maker_book"]["filled"] == 1
    assert t["maker_book"]["taker_win_rate"] == 0.5                      # the loss still counts
    assert body["towers"]["coinbase-spot"]["spot_vs_next_open_pct"] == round((3000 / 3030 - 1) * 100, 4)
    again = lm.run(_states(), body, tape, NOW, candle_fetch=lambda b, t, o: 1 / 0)
    assert len(reads) == 2 and again["towers"] == body["towers"]
    assert all(not v for v in body["flags"].values())
    lines = lm.report_lines(body)
    assert any("btc15m: 2 buys" in line for line in lines)
    assert "2 Kalshi buys checked" in lm.card(body)


def test_lab_read_limit_and_failures():
    def boom(t, lo, hi):
        raise TimeoutError

    body = lm.run(_states(), {}, boom, NOW, max_reads=1)
    assert body["pending"] == 1 and body["graded"] == {} and "read failed" in body["notes"][0]


def test_lab_counts_no_fills_from_research_logs(tmp_path):
    folder = tmp_path / "x-paper"
    folder.mkdir()
    rows = [{"at": NOW.isoformat(), "decisions": [{"reason": "Kalshi tape: 0 contracts traded"},
                                                  {"reason": "edge below floor"}]},
            {"at": "2026-11-01T00:00:00+00:00", "decisions": [{"reason": "Kalshi tape: old"}]}]
    (folder / "research.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    got = lm.no_fills(str(tmp_path), [{"id": "x", "folder": "x-paper"}], T0 - 86400)
    assert got == {"x": {"no real Kalshi trading at our price": 1}}


def test_lab_bot_main_and_registry(tmp_path):
    import new_towers
    import pimp_desk

    assert "fill-realism-lab" in new_towers.RESEARCH
    assert new_towers.BY_ID["fill-realism-lab"]["max_open"] == 0
    assert pimp_desk._account_body("fill-realism-lab")["cash"] == 0.0
    assert "fill-realism-lab-paper/fill_realism.json" in pimp_desk.SETTLEMENT_FILES
    spec = importlib.util.spec_from_file_location("fr_bot", os.path.join(HERE, "fill-realism-lab-paper", "bot.py"))
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    folder = tmp_path / "btc15m-signal"
    folder.mkdir()
    (folder / "paper_account.json").write_text(json.dumps(_states()["btc15m"]))
    specs = [{"id": "btc15m", "folder": "btc15m-signal", "state": "paper_account.json"}]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert bot.main([], root=str(tmp_path), trades_fetch=_tape, candle_fetch=lambda *a: None,
                        now=NOW, specs=specs) == 0
    assert "no trade" in out.getvalue()
    acct = json.loads((tmp_path / "fill-realism-lab-paper" / "paper_account.json").read_text())
    assert acct["cash"] == 0.0 and acct["open"] == [] and not acct["live_orders"]
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("fill-realism-lab")["ok"]


def test_time_formats_the_towers_write():
    base = dt.datetime(2026, 11, 13, 18, 0, tzinfo=dt.timezone.utc).timestamp()
    assert fr._epoch("2026-11-13T18:00:00Z") == base
    assert fr._epoch("2026-11-13 18:00:00 UTC") == base
    assert fr._epoch("2026-11-13 12:00:00 CT") == base
    assert fr._epoch("2026-11-13 13:00:00 ET") == base
    assert fr._epoch(base * 1000) == base
    assert fr._epoch("not a time") is None
