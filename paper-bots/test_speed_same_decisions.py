"""Speed work must never change what a tower decides. Offline.

The proof: run More 15m's real model and the shared engine twice on the same
recorded inputs, once with no speed measurement and once with every speed
change in this branch switched on (desk check timer, gateway wait counter, a
window-history read of the same market just before). The paper account, the
research log and the printed decision must match exactly.
"""
import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import shutil
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_speed  # noqa: E402
import kalshi_gateway  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 13, 18, 7, tzinfo=UTC)
CLOSE = NOW + dt.timedelta(minutes=8)
TICKER = "KXSOL15M-26NOV131315-15"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Resp(io.BytesIO):
    status = 200

    def __init__(self, body):
        super().__init__(body)
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _router(seen):
    market = {"ticker": TICKER, "event_ticker": TICKER.rsplit("-", 1)[0], "close_time": CLOSE.isoformat(),
              "floor_strike": 100.0, "yes_ask_dollars": "0.6000", "yes_bid_dollars": "0.5800",
              "no_ask_dollars": "0.4200", "no_bid_dollars": "0.4000"}
    closes = [{"c": str(100.0 + (0.05 if i % 2 else 0.0))} for i in range(66)]

    def urlopen(req, timeout=None, **_kw):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        seen.append(url)
        if "hyperliquid" in url:
            body = json.loads(req.data.decode())
            if body["type"] == "metaAndAssetCtxs":
                return _Resp(json.dumps([{"universe": []}, []]).encode())
            return _Resp(json.dumps(closes).encode())
        if "coinbase" in url:
            sym = url.split("/products/")[1].split("-")[0]
            px = {"SOL": (100.09, 100.11)}.get(sym)
            if not px:
                raise OSError("no coin")
            return _Resp(json.dumps({"bid": str(px[0]), "ask": str(px[1])}).encode())
        if "kraken" in url:
            raise OSError("no kraken")
        if "/markets/trades" in url:
            return _Resp(json.dumps({"trades": [{"yes_price_dollars": "0.5900", "count_fp": "100"}]}).encode())
        if "/orderbook" in url:
            return _Resp(json.dumps({"orderbook_fp": {"yes_dollars": [["0.58", "50"]],
                                                       "no_dollars": [["0.40", "50"]]}}).encode())
        if "series_ticker=KXSOL15M" in url:
            return _Resp(json.dumps({"markets": [market]}).encode())
        if "series_ticker=" in url:
            return _Resp(json.dumps({"markets": []}).encode())
        raise AssertionError(url)

    return urlopen


def _one_run(tmp_path, monkeypatch, label, speed_on):
    tower = tmp_path / label / "more-15m-paper"
    tower.mkdir(parents=True)
    shutil.copy(os.path.join(HERE, "more-15m-paper", "config.json"), tower / "config.json")
    monkeypatch.setenv("KALSHI_GATEWAY_DIR", str(tmp_path / label / "gw"))
    monkeypatch.setenv("KALSHI_READS_PER_SEC", "0")
    monkeypatch.setenv("PUBLIC_HTTP_GAP_SECONDS", "0")
    monkeypatch.delenv("DESK_BLOCK_ENTRIES", raising=False)
    seen = []
    monkeypatch.setattr(urllib.request, "urlopen", _router(seen))
    bot = _load(f"more15m_{label}", os.path.join("more-15m-paper", "bot.py"))
    monkeypatch.setattr(bot.time, "sleep", lambda s: None)
    if not speed_on:
        monkeypatch.setattr(kalshi_gateway, "_note_wait", lambda data, wait: None)
    else:
        # The window history reads the same market's book a moment before the tower does.
        rec = _load(f"rec_{label}", os.path.join("window-history-paper", "recorder.py"))
        rec.gateway_get(rec.book_url(TICKER))
        rec.gateway_get(rec.list_url("KXSOL15M"))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        if speed_on:
            with desk_speed.Timer() as timer:
                engine.run_tower(bot.SPEC, str(tower), bot.model, now=NOW)
            desk_speed.record(str(tmp_path / label), "more-15m", "run", timer.seconds, True, NOW.isoformat())
        else:
            engine.run_tower(bot.SPEC, str(tower), bot.model, now=NOW)
    account = json.loads((tower / "paper_account.json").read_text())
    # Wall-clock read times (added Nov 13) differ run to run; everything else must match.
    for row in account.get("open", []) + account.get("closed", []):
        for key in ("quote_read_from", "quote_read_to", "exit_quote_read_to", "exit_quote_at"):
            row.pop(key, None)
    research = [json.loads(line) for line in (tower / "research.jsonl").read_text().splitlines()]
    return account, research, out.getvalue(), seen


def test_speed_changes_do_not_change_more_15m_decisions(tmp_path, monkeypatch):
    plain = _one_run(tmp_path, monkeypatch, "plain", speed_on=False)
    fast = _one_run(tmp_path, monkeypatch, "fast", speed_on=True)
    assert plain[0] == fast[0]          # same paper account: cash, open position, everything
    assert plain[1] == fast[1]          # same research log: every fair, edge, action and reason
    assert plain[2] == fast[2]          # same printed decision
    assert "SIGNAL: BUY" in plain[2] and plain[0]["open"][0]["ticker"] == TICKER
    # The tower's own reads were real reads, not served from the window history's copy.
    tower_reads = [u for u in fast[3] if "kalshi" in u and "depth=" not in u and "limit=4" not in u]
    assert tower_reads == [u for u in plain[3] if "kalshi" in u]
    # And the speed pieces did measure something.
    assert desk_speed.summary(str(tmp_path / "fast"))["rows"][0]["bot"] == "more-15m"


def test_engine_decide_is_untouched_by_timing():
    cfg = engine.locked_cfg({"floor": 0.05, "max_edge": 0.20})
    quotes = [{"ticker": f"T{i}", "side": s, "fair": f, "ask": a}
              for i, (s, f, a) in enumerate([("yes", 0.7, 0.6), ("no", 0.4, 0.45), ("yes", 0.95, 0.5),
                                             ("yes", 0.5, 0.97), ("no", None, 0.5)])]
    plain = [engine.decide(q, cfg) for q in quotes]
    with desk_speed.Timer():
        timed = [engine.decide(q, cfg) for q in quotes]
    assert plain == timed
    assert [d["action"] for d in plain] == ["buy", "skip", "skip", "skip", "skip"]
