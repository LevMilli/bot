"""Window history (15-minute recordings). Offline."""
import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REC_DIR = os.path.join(HERE, "window-history-paper")
sys.path.insert(0, REC_DIR)

import desk_data  # noqa: E402
import recorder as rec  # noqa: E402

UTC = dt.timezone.utc
CLOSE = dt.datetime(2026, 11, 13, 18, 15, tzinfo=UTC)
TICKER = "KXSOL15M-26NOV131315-15"


def _market(ticker=TICKER, close=CLOSE):
    return {"ticker": ticker, "event_ticker": ticker.rsplit("-", 1)[0], "close_time": close.isoformat(),
            "floor_strike": 142.5, "yes_bid_dollars": "0.40", "yes_ask_dollars": "0.44"}


BOOK = {"orderbook_fp": {
    "yes_dollars": [["0.3500", "10"], ["0.4000", "25"], ["0.3800", "5"], ["0.3000", "1"], ["0.2000", "9"],
                    ["0.1000", "4"]],
    "no_dollars": [["0.5600", "12"], ["0.5000", "3"]],
}}


class FakeKalshi:
    def __init__(self, result="", series=("KXSOL15M",)):
        self.urls = []
        self.result = result
        self.series = series

    def __call__(self, url):
        self.urls.append(url)
        if "/orderbook" in url:
            return BOOK
        if "series_ticker=" in url:
            s = url.split("series_ticker=")[1].split("&")[0]
            return {"markets": [_market(TICKER.replace("KXSOL15M", s))] if s in self.series else []}
        if "/markets/" in url:
            return {"market": {"ticker": url.rsplit("/", 1)[1], "result": self.result, "expiration_value": "142.91",
                               "floor_strike": 142.5}}
        raise AssertionError(url)


def test_levels_top_five_best_first():
    book = BOOK["orderbook_fp"]
    assert rec.levels(book, "yes") == [[0.4, 25.0], [0.38, 5.0], [0.35, 10.0], [0.3, 1.0], [0.2, 9.0]]
    assert rec.levels({"yes": [[45, 3]]}, "yes") == [[0.45, 3.0]]  # old cents payload


def test_book_row_bid_and_ask():
    now = CLOSE - dt.timedelta(minutes=5)
    row = rec.book_row(BOOK, at=now, series="KXSOL15M", ticker=TICKER, minutes=5.0)
    assert row["yes_bid"] == 0.4 and row["yes_ask"] == 0.44 and row["no_bid"] == 0.56 and row["no_ask"] == 0.6
    assert len(row["yes_bids"]) == 5 and row["depth"] == 50.0 + 15.0


def test_records_only_last_14_minutes_then_result():
    state, fake = {}, FakeKalshi(series=("KXSOL15M",))
    early = CLOSE - dt.timedelta(minutes=14, seconds=30)
    rows, _ = rec.record(state, early, fake, series=("KXSOL15M",))
    assert [r["kind"] for r in rows] == ["window"]             # 14.5 min left: window noted, no book yet
    assert rows[0]["open_price"] == 142.5
    rows, _ = rec.record(state, CLOSE - dt.timedelta(minutes=10), fake, series=("KXSOL15M",))
    assert [r["kind"] for r in rows] == ["book"]               # window remembered: no second list read
    assert sum("series_ticker" in u for u in fake.urls) == 1
    rows, _ = rec.record(state, CLOSE + dt.timedelta(seconds=30), fake, series=("KXSOL15M",))
    assert state["pending"] and not any(r["kind"] == "result" for r in rows)
    fake.result = "yes"
    rows, _ = rec.record(state, CLOSE + dt.timedelta(minutes=2), fake, series=("KXSOL15M",))
    res = [r for r in rows if r["kind"] == "result"]
    assert res and res[0]["result"] == "yes" and res[0]["settle_value"] == 142.91 and not state["pending"]


def test_read_budget_and_time_budget():
    state, fake = {}, FakeKalshi(series=rec.SERIES)
    rows, notes = rec.record(state, CLOSE - dt.timedelta(minutes=5), fake, budget=4)
    assert len(fake.urls) == 4 and any("budget" in n for n in notes)
    ticks = iter([0.0] + [100.0] * 100)
    fake2 = FakeKalshi(series=rec.SERIES)
    rec.record({}, CLOSE - dt.timedelta(minutes=5), fake2, clock=lambda: next(ticks))
    assert fake2.urls == []


def test_one_series_failing_does_not_stop_the_rest():
    def get(url):
        if "KXBTC15M" in url:
            raise TimeoutError
        return FakeKalshi(series=rec.SERIES)(url)

    rows, notes = rec.record({}, CLOSE - dt.timedelta(minutes=5), get, series=("KXBTC15M", "KXSOL15M"))
    assert any("KXBTC15M list read failed" in n for n in notes)
    assert any(r["kind"] == "book" and r["series"] == "KXSOL15M" for r in rows)


def test_recorder_urls_never_share_the_tower_cache():
    """A recorder read must never hand a tower an older book: own URLs, cache off."""
    import kalshi_gateway

    seen = {}

    def fake_read(url, headers=None, timeout=15, ttl=None, sleep=None):
        seen[url] = (ttl, timeout)
        return json.dumps(BOOK).encode()

    orig = kalshi_gateway.read
    kalshi_gateway.read = fake_read
    try:
        rec.gateway_get(rec.book_url(TICKER))
    finally:
        kalshi_gateway.read = orig
    (url, (ttl, timeout)), = seen.items()
    assert ttl == 0 and timeout <= 6
    assert url.endswith("?depth=5")              # towers read /orderbook with no depth
    assert rec.list_url("KXSOL15M").endswith("limit=4")  # More 15m lists with limit=3


def test_recordings_hold_nothing_private(tmp_path):
    state, fake = {}, FakeKalshi(series=rec.SERIES)
    rows, _ = rec.record(state, CLOSE - dt.timedelta(minutes=5), fake)
    rows.append({"kind": "book", "ticker": TICKER, "api_key": "x", "note": "mail me at a@b.com"})
    rec.save(str(tmp_path), [desk_data.strip_private(r) for r in rows], CLOSE)
    saved = desk_data.load_day(str(tmp_path), CLOSE.date())
    assert saved and desk_data.find_private(saved) == []


def test_rebuild_window_and_chart(tmp_path):
    state, fake = {}, FakeKalshi(series=("KXSOL15M",))
    for minutes in (14.6, 13, 12, 10, 9):   # 11 left is missing on purpose
        now = CLOSE - dt.timedelta(minutes=minutes)
        rows, _ = rec.record(state, now, fake, series=("KXSOL15M",))
        rec.save(str(tmp_path), rows, now)
    fake.result = "no"
    rows, _ = rec.record(state, CLOSE + dt.timedelta(minutes=3), fake, series=("KXSOL15M",))
    rec.save(str(tmp_path), rows, CLOSE)
    win = rec.rebuild_window(str(tmp_path), TICKER)
    assert win["open_price"] == 142.5 and win["result"] == "no" and len(win["books"]) == 4
    assert win["quality"]["missing"] == 1
    svg = rec.window_chart_svg(win, fairs=[{"at": (CLOSE - dt.timedelta(minutes=9)).isoformat(), "fair": 0.3,
                                            "side": "no"}],
                               trades=[{"opened": (CLOSE - dt.timedelta(minutes=9)).isoformat(), "ask": 0.6,
                                        "side": "no"}])
    assert svg.startswith("<svg") and "polyline" in svg and "<circle" in svg and "result NO" in svg
    q = rec.quality_report(desk_data.load_day(str(tmp_path), CLOSE.date()))
    assert q["windows"] == 1 and q["missing_minutes"] == 1 and not q["ok"]
    cal = rec.market_calibration(desk_data.load_day(str(tmp_path), CLOSE.date()))
    assert cal["family"] == "15m" and cal["all"]["n"] == 4 and cal["all"]["wins"] == 0


def test_prune_keeps_today_and_180_days(tmp_path):
    today = dt.date(2026, 11, 13)
    for day in (today - dt.timedelta(days=200), today - dt.timedelta(days=10), today):
        desk_data.write_rows(str(tmp_path), day, [{"kind": "book", "at": day.isoformat()}])
    gone = rec.prune(str(tmp_path), today)
    assert gone == [(today - dt.timedelta(days=200)).isoformat() + ".jsonl.gz"]
    assert rec.prune(str(tmp_path), today, max_bytes=0)[-1].startswith("2026-11-03")
    assert desk_data.day_files(str(tmp_path)) == ["2026-11-13.jsonl.gz"]


def _load_bot():
    spec = importlib.util.spec_from_file_location("window_rec_bot", os.path.join(REC_DIR, "bot.py"))
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    return bot


def test_bot_main_and_nightly_report(tmp_path):
    bot = _load_bot()
    folder = tmp_path / "rec" / "recordings"
    fake = FakeKalshi(series=("KXSOL15M",))
    research = tmp_path / "research.jsonl"
    research.write_text(json.dumps({"at": (CLOSE - dt.timedelta(minutes=6)).isoformat(), "decisions": [
        {"ticker": TICKER, "side": "yes", "fair": 0.7, "ask": 0.44, "edge": 0.2, "action": "skip",
         "reason": "edge 0.200 over trust cap 0.2"}]}) + "\n")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        for minutes in (14.6, 6):
            assert bot.main([], here=str(tmp_path), get=fake, now=CLOSE - dt.timedelta(minutes=minutes),
                            folder=str(folder), research={}) == 0
        fake.result = "yes"
        assert bot.main([], here=str(tmp_path), get=fake, now=CLOSE + dt.timedelta(minutes=2),
                        folder=str(folder), research={}) == 0
    assert "no trade" in out.getvalue() and "Window history:" in out.getvalue()
    state = json.loads((tmp_path / "paper_account.json").read_text())
    assert state["cash"] == 0.0 and state["open"] == [] and state["live_orders"] is False
    report = bot.nightly(str(folder), CLOSE.date(), {"more-15m": str(research)})
    assert report["results"] == 1 and report["decisions"]["skips"] == 1
    cal = report["tower_calibration"]["more-15m"]
    assert cal["15m"]["n"] == 1 and "15m 6-9 min left" in cal
    assert (tmp_path / "rec" / "reports" / "2026-11-13.json").exists()
    # The next day's first run writes yesterday's report once.
    with contextlib.redirect_stdout(io.StringIO()) as again:
        bot.main([], here=str(tmp_path), get=FakeKalshi(series=()), now=CLOSE + dt.timedelta(days=1),
                 folder=str(folder), research={})
    assert "Yesterday:" in again.getvalue()


def test_tools_print_and_chart(tmp_path):
    bot = _load_bot()
    folder = tmp_path / "recordings"
    desk_data.write_rows(str(folder), CLOSE.date(), [{"kind": "book", "series": "KXSOL15M", "ticker": TICKER,
                                                     "at": CLOSE.isoformat(), "min_left": 1, "yes_bid": 0.5,
                                                     "yes_ask": 0.52}])
    with contextlib.redirect_stdout(io.StringIO()) as out:
        assert bot.main(["--day", "2026-11-13", "KXSOL15M"], here=str(tmp_path), folder=str(folder)) == 0
    assert json.loads(out.getvalue())["rows"] == 1
    svg = tmp_path / "w.svg"
    with contextlib.redirect_stdout(io.StringIO()):
        assert bot.main(["--chart", TICKER, str(svg)], here=str(tmp_path), folder=str(folder)) == 0
    assert svg.read_text().startswith("<svg")


def test_registry_and_desk_wiring():
    import new_towers
    import pimp_desk

    row = new_towers.BY_ID["window-history"]
    assert "window-history" in new_towers.RESEARCH and row["max_open"] == 0
    assert row["floor"] == 0.05 and row["venue"] == "kalshi_btc15m"
    assert pimp_desk._account_body("window-history")["cash"] == 0.0
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("window-history")["ok"]
    cfg = json.load(open(os.path.join(REC_DIR, "config.json")))
    assert cfg["paper_only"] is True and cfg["live_orders"] is False
