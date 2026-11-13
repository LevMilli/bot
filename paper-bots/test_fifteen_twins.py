"""Practice twins of the 15-minute towers (ideas B1-B5). Offline."""
import datetime as dt
import importlib.util
import json
import os
import shutil

import fifteen_twins as twins
import kalshi_shadow_tower as engine
import new_towers

HERE = os.path.dirname(os.path.abspath(__file__))
UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 13, 20, 36, tzinfo=UTC)


def _more_spec():
    spec = importlib.util.spec_from_file_location("more15_for_twins", os.path.join(HERE, "more-15m-paper", "bot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SPEC


def _busy(ticker, now):
    return [{"yes_price_dollars": "0.10", "count_fp": "5000"}, {"yes_price_dollars": "0.90", "count_fp": "5000"}]


def _acct(tower):
    with open(os.path.join(tower, "paper_account.json"), encoding="utf-8") as handle:
        return json.load(handle)


def _row(minutes=12.0, fair=0.92, ask=0.80, bid=0.78, side="yes", reasons=(), lane="accurate", group=None):
    close = NOW + dt.timedelta(minutes=minutes)
    row = {"ticker": "KXBTC15M-W", "event": "KXBTC15M-W", "close": close.isoformat(), "side": side,
           "fair": fair, "ask": ask, "bid": bid, "other_ask": round(1 - bid, 2), "other_bid": round(1 - ask, 2),
           "lane": lane, "reasons": list(reasons), "why": "test", "label": "BTC 15m up by 20:48 UTC"}
    if group:
        row["group"] = group
    return row


def _run(twin_id, tower, rows, root, **kw):
    model = twins.make_model(twin_id, root=root, reader=lambda: (rows, ""))
    # Each run is a fresh read: clear the shared cache so tests see their own rows.
    shutil.rmtree(os.path.join(root, "fifteen-twins-cache"), ignore_errors=True)
    return engine.run_tower(twins.twin_spec(twin_id), tower, model, now=NOW,
                            fetch=kw.get("fetch", lambda t: {}), tape=kw.get("tape", _busy))


# ------------------------------------------------------------------ registry + guard rails
def test_every_twin_has_a_row_folder_and_locked_shadow_rules():
    rows = {row["id"]: row for row in new_towers.TOWERS if row.get("twin_of")}
    assert set(rows) == set(twins.TWINS)
    locked = {"kalshi_btc15m": 0.05, "kalshi_commodity15m": 0.05}
    for tid, row in rows.items():
        assert row["floor"] == locked[row["venue"]]
        assert os.path.isfile(os.path.join(HERE, row["folder"], "bot.py"))
        cfg = json.load(open(os.path.join(HERE, row["folder"], "config.json")))
        assert cfg["paper_only"] is True and cfg["live_orders"] is False and cfg["shadow_only"] is True
        assert cfg["stake_usd"] == 25 and cfg["starter_cash"] == 500 and cfg["venue_min_edge"] == 0.05
        spec = twins.twin_spec(tid)
        assert spec["floor"] == 0.05 and spec["id"] == tid
        locked_cfg = engine.locked_cfg(spec, {"venue_min_edge": 0.01, "stake_usd": 25})
        assert locked_cfg["venue_min_edge"] == 0.05 and locked_cfg["shadow_only"] and not locked_cfg["live_orders"]
        assert row["max_open"] == spec["max_open"] > 0
    assert len({row["id"] for row in new_towers.TOWERS}) == len(new_towers.TOWERS)
    assert "favorite-harvest" not in twins.TWINS


def test_twins_are_installed_as_shadow_towers_with_25_dollar_tickets():
    import pimp_desk
    ids = {bot["id"]: bot for bot in pimp_desk.BOTS}
    for tid in twins.TWINS:
        assert ids[tid]["shadow_only"] is True and ids[tid]["kind"] == "shadow"
        assert pimp_desk.BOT_PLANS[tid]["stake"] == "fixed-25"
        assert pimp_desk.TOWER_STARTER_CASH[tid] == 500.0
    # The originals keep their own rows.
    for orig in ("more-15m", "btc15m", "commodity-15m"):
        assert orig in ids and ids[orig].get("folder") != ids.get(f"{orig}-mirror", {}).get("folder")


def test_more_15m_original_spec_is_unchanged():
    assert _more_spec() == {"id": "more-15m", "name": "More 15m", "floor": 0.05, "max_open": 4, "max_edge": 0.20,
                            "group_cap": 2, "tape_check": True, "fee_per_order": True}


def test_each_twin_changes_one_rule_against_its_control():
    more = dict(_more_spec())
    more.pop("id"), more.pop("name"), more.pop("floor")
    t = twins.TWINS

    def bare(tid):
        spec = dict(t[tid]["spec"])
        spec.pop("name")
        return spec

    # B1: same spec as More 15m; the change is the long-shot bar on quotes.
    assert bare("more-15m-longshot") == more and t["more-15m-longshot"]["cheap_extra_edge"] == 0.05
    # B5 More: same spec plus take-profit.
    assert bare("more-15m-tp15") == dict(more, take_profit=0.15)
    mirror = bare("btc15m-mirror")
    assert bare("btc15m-5min") == mirror and t["btc15m-5min"]["min_minutes"] == 5.0
    assert t["btc15m-mirror"]["min_minutes"] == 10.0
    assert bare("btc15m-tape") == dict(mirror, tape_check=True, fee_per_order=True)
    assert bare("btc15m-tp10") == dict(mirror, take_profit=0.10) and mirror["take_profit"] == 0.15
    cmirror = bare("commodity-15m-mirror")
    assert bare("commodity-15m-cap85") == cmirror and t["commodity-15m-cap85"]["ask_cap"] == 0.85
    assert "ask_cap" not in t["commodity-15m-mirror"]
    assert bare("commodity-15m-tape") == dict(cmirror, tape_check=True, fee_per_order=True)
    assert not mirror.get("tape_check") and not cmirror.get("tape_check")


# ------------------------------------------------------------------ engine: off by default
def test_engine_decide_is_unchanged_without_extra_edge():
    cfg = engine.locked_cfg({"floor": 0.05})
    quote = {"ticker": "T", "event": "E", "side": "yes", "fair": 0.30, "ask": 0.15, "bid": 0.12}
    row = engine.decide(quote, cfg)
    assert row["action"] == "buy" and "extra_edge" not in row
    row = engine.decide(dict(quote, extra_edge=0.05), cfg)
    assert row["action"] == "buy" and row["extra_edge"] == 0.05  # edge 0.14 clears 0.10
    row = engine.decide(dict(quote, fair=0.25, extra_edge=0.05, extra_reason="ask under 20c"), cfg)
    assert row["action"] == "skip" and "raised bar 0.1" in row["reason"] and "ask under 20c" in row["reason"]
    # A negative extra never lowers the floor.
    row = engine.decide(dict(quote, fair=0.19, extra_edge=-0.05), cfg)
    assert row["action"] == "skip" and "< floor 0.05" in row["reason"]


def test_engine_without_take_profit_keeps_more_15m_exits(tmp_path):
    spec = _more_spec()
    tower = str(tmp_path / "m")
    buy = [{"ticker": "W", "event": "E", "side": "yes", "fair": 0.70, "ask": 0.60, "bid": 0.55}]
    engine.run_tower(spec, tower, None, now=NOW, fetch=lambda t: {}, quotes=buy, tape=_busy)
    assert len(_acct(tower)["open"]) == 1
    assert _acct(tower)["open"][0]["exit_plan"] == {"kind": "model-flip+settle", "flip_margin": 0.02}
    # Bid up 20c but fair higher still: More 15m holds (no take-profit), as before.
    engine.run_tower(spec, tower, None, now=NOW, fetch=lambda t: {},
                     quotes=[dict(buy[0], fair=0.95, bid=0.80, ask=0.82)], tape=_busy)
    acct = _acct(tower)
    assert len(acct["open"]) == 1 and acct["closed"] == []


# ------------------------------------------------------------------ B1
def test_b1_long_shot_bar_skips_cheap_asks_the_original_buys(tmp_path):
    rows = [{"ticker": "KXDOGE15M-W", "event": "KXDOGE15M-E", "side": "yes", "fair": 0.25, "ask": 0.15,
             "bid": 0.13, "label": "DOGE", "why": ""}]
    original = str(tmp_path / "orig")
    engine.run_tower(_more_spec(), original, None, now=NOW, fetch=lambda t: {}, quotes=rows, tape=_busy)
    assert len(_acct(original)["open"]) == 1  # edge 0.09 clears 0.05
    twin = str(tmp_path / "twin")
    _run("more-15m-longshot", twin, rows, str(tmp_path))
    assert _acct(twin)["open"] == []  # needs 0.10 under 20c
    rich = [dict(rows[0], fair=0.27, ask=0.15)]  # edge 0.11
    _run("more-15m-longshot", twin, rich, str(tmp_path))
    assert len(_acct(twin)["open"]) == 1
    # 20c and up: same bar as More 15m.
    twin2 = str(tmp_path / "twin2")
    _run("more-15m-longshot", twin2, [dict(rows[0], fair=0.33, ask=0.25)], str(tmp_path))
    assert len(_acct(twin2)["open"]) == 1


# ------------------------------------------------------------------ B3
def test_b3_five_minute_twin_buys_where_the_mirror_waits(tmp_path):
    rows = [_row(minutes=7.0)]
    mirror, short = str(tmp_path / "mirror"), str(tmp_path / "short")
    _run("btc15m-mirror", mirror, rows, str(tmp_path))
    _run("btc15m-5min", short, rows, str(tmp_path))
    assert _acct(mirror)["open"] == []
    assert len(_acct(short)["open"]) == 1
    late = str(tmp_path / "late")
    _run("btc15m-5min", late, [_row(minutes=4.0)], str(tmp_path))
    assert _acct(late)["open"] == []


def test_btc_gates_from_the_original_block_buys(tmp_path):
    tower = str(tmp_path / "t")
    _run("btc15m-mirror", tower, [_row(reasons=["z 0.40 < 0.6"])], str(tmp_path))
    assert _acct(tower)["open"] == []
    # Speed lane needs 0.02 more edge, as in BTC 15m.
    _run("btc15m-mirror", tower, [_row(fair=0.86, ask=0.79, lane="speed")], str(tmp_path))
    assert _acct(tower)["open"] == []  # edge 0.86-0.79-0.02 = 0.05 < 0.07
    _run("btc15m-mirror", tower, [_row(fair=0.89, ask=0.79, lane="speed")], str(tmp_path))
    assert len(_acct(tower)["open"]) == 1


# ------------------------------------------------------------------ B2
def test_b2_cap_twin_refuses_asks_over_85c(tmp_path):
    rows = [_row(fair=0.99, ask=0.88, bid=0.86, group="metal")]
    mirror, cap = str(tmp_path / "mirror"), str(tmp_path / "cap")
    _run("commodity-15m-mirror", mirror, rows, str(tmp_path))
    _run("commodity-15m-cap85", cap, rows, str(tmp_path))
    assert len(_acct(mirror)["open"]) == 1
    assert _acct(cap)["open"] == []
    _run("commodity-15m-cap85", cap, [_row(fair=0.95, ask=0.84, bid=0.82, group="metal")], str(tmp_path))
    assert len(_acct(cap)["open"]) == 1


def test_commodity_twins_hold_one_metal_and_one_energy(tmp_path):
    tower = str(tmp_path / "t")
    _run("commodity-15m-mirror", tower, [_row(fair=0.95, ask=0.80, group="metal")], str(tmp_path))
    second = dict(_row(fair=0.95, ask=0.80, group="metal"), ticker="KXSILVER15M-W", event="KXSILVER15M-W")
    _run("commodity-15m-mirror", tower, [second], str(tmp_path))
    assert len(_acct(tower)["open"]) == 1
    energy = dict(second, ticker="KXWTI15M-W", event="KXWTI15M-W", group="energy")
    _run("commodity-15m-mirror", tower, [energy], str(tmp_path))
    assert len(_acct(tower)["open"]) == 2


# ------------------------------------------------------------------ B4
def test_b4_tape_twin_needs_real_trading_and_pays_fee_once(tmp_path):
    rows = [_row(fair=0.95, ask=0.80)]
    quiet = lambda t, n: [{"yes_price_dollars": "0.85", "count_fp": "900"}]  # noqa: E731 - all above our ask
    mirror, tape = str(tmp_path / "mirror"), str(tmp_path / "tape")
    _run("btc15m-mirror", mirror, rows, str(tmp_path), tape=quiet)
    _run("btc15m-tape", tape, rows, str(tmp_path), tape=quiet)
    assert len(_acct(mirror)["open"]) == 1  # mirror never reads the tape
    assert _acct(tape)["open"] == []
    _run("btc15m-tape", tape, rows, str(tmp_path), tape=_busy)
    pos = _acct(tape)["open"][0]
    assert "order_fee" in pos and pos["order_fee"] == engine.order_fee(pos["contracts"], 0.80)
    assert "order_fee" not in _acct(mirror)["open"][0]
    ctape = str(tmp_path / "ctape")
    _run("commodity-15m-tape", ctape, [_row(fair=0.95, ask=0.80, group="metal")], str(tmp_path), tape=quiet)
    assert _acct(ctape)["open"] == []


# ------------------------------------------------------------------ B5 and exits
def test_b5_take_profit_levels(tmp_path):
    rows = [_row(fair=0.95, ask=0.80, bid=0.78)]
    t15, t10 = str(tmp_path / "t15"), str(tmp_path / "t10")
    _run("btc15m-mirror", t15, rows, str(tmp_path))
    _run("btc15m-tp10", t10, rows, str(tmp_path))
    up = [_row(fair=0.97, ask=0.92, bid=0.90)]  # +10c, not +15c
    _run("btc15m-mirror", t15, up, str(tmp_path))
    _run("btc15m-tp10", t10, up, str(tmp_path))
    assert len(_acct(t15)["open"]) == 1
    closed = _acct(t10)["closed"]
    assert len(closed) == 1 and closed[0]["exit"] == "take-profit" and closed[0]["exit_target"] == 0.90
    assert closed[0]["pnl"] == round(closed[0]["payout"] - closed[0]["cost"], 2)
    _run("btc15m-mirror", t15, [_row(fair=0.99, ask=0.97, bid=0.95)], str(tmp_path))
    assert _acct(t15)["closed"][0]["exit"] == "take-profit" and _acct(t15)["closed"][0]["exit_target"] == 0.95


def test_more_take_profit_twin_sells_at_plus_15(tmp_path):
    tower = str(tmp_path / "m")
    _run("more-15m-tp15", tower, [{"ticker": "W", "event": "E", "side": "yes", "fair": 0.70, "ask": 0.60,
                                   "bid": 0.55, "label": "SOL", "why": ""}], str(tmp_path))
    _run("more-15m-tp15", tower, [{"ticker": "W", "event": "E", "side": "yes", "fair": 0.95, "ask": 0.77,
                                   "bid": 0.75, "label": "SOL", "why": ""}], str(tmp_path))
    closed = _acct(tower)["closed"]
    assert len(closed) == 1 and closed[0]["exit"] == "take-profit"
    assert closed[0]["payout"] == round(closed[0]["contracts"] * 0.75 - engine.order_fee(closed[0]["contracts"], 0.75), 2)


def test_side_flip_sells_the_held_side_and_counts_the_loss(tmp_path):
    tower = str(tmp_path / "t")
    _run("btc15m-mirror", tower, [_row(fair=0.95, ask=0.80, bid=0.78)], str(tmp_path))
    # BTC crossed the target: model now on NO. Held YES bid is 0.40.
    flipped = _row(side="no", fair=0.70, ask=0.58, bid=0.56)
    flipped["other_bid"], flipped["other_ask"] = 0.40, 0.44
    _run("btc15m-mirror", tower, [flipped], str(tmp_path))
    acct = _acct(tower)
    assert acct["open"] == [] or acct["open"][0]["side"] == "no"
    row = acct["closed"][0]
    assert row["exit"] == "side-flip" and row["exit_bid"] == 0.40 and row["pnl"] < 0


def test_settle_counts_losses(tmp_path):
    tower = str(tmp_path / "t")
    _run("btc15m-mirror", tower, [_row(fair=0.95, ask=0.80)], str(tmp_path))
    _run("btc15m-mirror", tower, [], str(tmp_path), fetch=lambda t: {"result": "no"})
    row = _acct(tower)["closed"][0]
    assert row["exit"] == "settled" and row["payout"] == 0 and row["pnl"] == -row["cost"]


# ------------------------------------------------------------------ shared data, own ledgers
def test_twins_of_a_family_share_one_read(tmp_path):
    calls = []

    def reader():
        calls.append(1)
        return [_row()], ""

    root = str(tmp_path)
    rows1, _ = twins.shared_rows("btc", reader, root, now_ts=1000.0)
    rows2, _ = twins.shared_rows("btc", reader, root, now_ts=1000.0 + twins.CACHE_SEC - 1)
    assert rows1 == rows2 and len(calls) == 1
    twins.shared_rows("btc", reader, root, now_ts=1000.0 + twins.CACHE_SEC + 1)
    assert len(calls) == 2


def test_each_twin_keeps_its_own_ledger(tmp_path):
    root = str(tmp_path)
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    _run("btc15m-mirror", a, [_row(minutes=7.0)], root)
    _run("btc15m-5min", b, [_row(minutes=7.0)], root)
    assert _acct(a)["open"] == [] and len(_acct(b)["open"]) == 1
    assert _acct(a)["cash"] == 500.0 and _acct(b)["cash"] < 500.0


def test_load_base_never_writes_the_original_folder(tmp_path):
    root = tmp_path
    for family, (folder, script) in twins.BASES.items():
        os.makedirs(root / folder)
        shutil.copy(os.path.join(HERE, folder, script), root / folder / script)
    orig_basis = {"KXGOLD15M": {"frac": 0.001, "last": "OLD", "n": 4}}
    (root / "commodity-15m-paper" / "index_basis.json").write_text(json.dumps(orig_basis))
    before = {p: open(p, "rb").read() for p in map(str, root.rglob("*")) if os.path.isfile(p)}
    base = twins.load_base("commodity", str(root))
    m = {"ticker": "KXGOLD15M-NEW", "target": 2000.0,
         "close_time": dt.datetime.now(UTC) + dt.timedelta(minutes=14)}
    base.anchored_spot("KXGOLD15M", 1999.0, m)
    for path, body in before.items():
        assert open(path, "rb").read() == body, path
    mine = json.loads((root / "fifteen-twins-cache" / "commodity" / "index_basis.json").read_text())
    assert mine["KXGOLD15M"]["last"] == "KXGOLD15M-NEW" and mine["KXGOLD15M"]["n"] == 5
    btc = twins.load_base("btc", str(root))
    assert btc._CACHE.startswith(str(root / "fifteen-twins-cache"))
    assert btc.ACCOUNT.startswith(str(root / "fifteen-twins-cache"))
    more = twins.load_base("more", str(root))
    assert more.HERE == str(root / "fifteen-twins-cache" / "more")
    # The real originals' module constants are untouched.
    real = importlib.util.spec_from_file_location("c_real", os.path.join(HERE, "commodity-15m-paper", "bot.py"))
    mod = importlib.util.module_from_spec(real)
    real.loader.exec_module(mod)
    assert mod.MIN_MINUTES_LEFT == 8 and mod.ASK_MAX == 0.92


def test_failed_read_is_a_skip_not_a_guess(tmp_path):
    tower = str(tmp_path / "t")

    def broken():
        raise OSError("down")

    model = twins.make_model("btc15m-mirror", root=str(tmp_path), reader=broken)
    engine.run_tower(twins.twin_spec("btc15m-mirror"), tower, model, now=NOW, fetch=lambda t: {}, tape=_busy)
    assert _acct(tower)["open"] == [] and _acct(tower)["cash"] == 500.0
