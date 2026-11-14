"""Plan sections 'Safety and honest numbers' (1-98) and 'Rules, graduation and safety locks' (941-980).

Guards only. Nothing here changes how a tower trades.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import io
import json
import logging
import math
import os
import re
import subprocess
import sys
import tempfile
from fractions import Fraction

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_profit  # noqa: E402
import desk_safety  # noqa: E402
import kalshi_shadow_tower as engine  # noqa: E402
import new_towers  # noqa: E402
import pimp_desk  # noqa: E402

VAULT = ("sports-gap", "btc15m", "commodity-15m", "kalshi-sp", "kalshi-sized", "memecoin")


def _py_files():
    for base, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules")]
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(base, name)


def _tower_configs():
    for spec in pimp_desk.BOTS:
        path = os.path.join(HERE, spec["folder"], "config.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                yield spec, json.load(fh)


# ------------------------------------------------------------ steps 1, 966: no live orders
def test_no_tower_config_turns_live_orders_on():
    seen = 0
    for spec, cfg in _tower_configs():
        seen += 1
        assert cfg.get("live_orders") is not True, spec["id"]
        assert cfg.get("paper_only") is not False, spec["id"]
    assert seen >= 20


def test_no_json_file_anywhere_sets_live_orders_true():
    pat = re.compile(r'"live_orders(_enabled)?"\s*:\s*true', re.I)
    bad = []
    for base, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for name in files:
            if name.endswith(".json"):
                path = os.path.join(base, name)
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    if pat.search(fh.read()):
                        bad.append(os.path.relpath(path, HERE))
    assert bad == []


def test_desk_defaults_paper_only_and_no_live_switch():
    assert pimp_desk.DEFAULTS["paper_only"] is True
    assert pimp_desk.LIVE_SWITCH_BUILT is False
    with open(os.path.join(HERE, "pimp-trading.json"), encoding="utf-8") as fh:
        saved = json.load(fh)
    assert saved.get("paper_only") is True
    assert saved.get("live_orders") is not True


def test_child_env_never_passes_exchange_keys():
    keys = {"KALSHI_API_KEY": "x", "COINBASE_API_SECRET": "x", "WALLET_SECRET": "x",
            "BINANCE_API_KEY": "x", "DESK_SERVICE_KEY": "x"}
    old = {k: os.environ.get(k) for k in keys}
    os.environ.update(keys)
    try:
        env = pimp_desk._child_env()
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    for k in keys:
        assert k not in env
    assert env["PAPER_ONLY"] == "1"


# ------------------------------------------------------------ steps 2, 966: no order code
_SDK = re.compile(
    r"^\s*(?:import|from)\s+(ccxt|kalshi_python|kalshi_client|kalshi|binance|coinbase|"
    r"coinbase_advanced_py|cbpro|solders|solana|web3|alpaca|alpaca_trade_api|py_clob_client|"
    r"hyperliquid|pybit|krakenex)\b",
    re.M,
)
_ORDER = re.compile(
    r"(/portfolio/orders|/portfolio/batched|KALSHI-ACCESS-SIGNATURE|KALSHI-ACCESS-KEY|CB-ACCESS-SIGN|"
    r"X-MBX-APIKEY|/api/v3/order|/api/v3/brokerage/orders|sendTransaction|signTransaction|"
    r"\bplace_order\s*\(|\bcreate_order\s*\(|\bsubmit_order\s*\()"
)


def test_no_file_imports_an_exchange_trading_library_or_order_endpoint():
    me = os.path.abspath(__file__)
    sdk, order = [], []
    for path in _py_files():
        if os.path.abspath(path) == me:
            continue
        with open(path, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
        if _SDK.search(text):
            sdk.append(os.path.relpath(path, HERE))
        if _ORDER.search(text):
            order.append(os.path.relpath(path, HERE))
    assert sdk == [], sdk
    assert order == [], order


def test_order_scan_catches_a_planted_order_call():
    assert _SDK.search("import ccxt\n")
    assert _SDK.search("from kalshi_python import ApiClient\n")
    assert not _SDK.search("import kalshi_shadow_tower as engine\n")
    assert not _SDK.search("import kalshi_tape\n")
    assert _ORDER.search('requests.post(BASE + "/portfolio/orders", json=o)')


# ------------------------------------------------------------ steps 3, 4, 5, 942, 943, 97: floors
def test_locked_floor_table_matches_desk_profit_and_brief():
    assert desk_safety.LOCKED_FLOORS == {
        "kalshi_sports": 0.06, "kalshi_btc15m": 0.05, "kalshi_commodity15m": 0.05,
        "kalshi_inx": 0.02, "solana_dex": 0.02, "coinbase_spot": 0.05,
        "binance_btc_carry": 0.02, "coinbase_btc_carry": 0.02, "kalshi_econ": 0.05, "equity_qqq": 0.02,
    }
    for key, lock in desk_safety.LOCKED_FLOORS.items():
        assert float(desk_profit.DEFAULT_VENUE_MIN_EDGE[key]) + 1e-12 >= lock, key
        assert float(pimp_desk.DEFAULTS["venue_min_edge"][key]) + 1e-12 >= lock, key
    assert desk_safety.floor_problems() == []


def test_saved_desk_settings_floors_not_below_lock():
    with open(os.path.join(HERE, "pimp-trading.json"), encoding="utf-8") as fh:
        saved = json.load(fh)
    for key, value in (saved.get("venue_min_edge") or {}).items():
        assert key in desk_safety.LOCKED_FLOORS, key
        assert float(value) + 1e-12 >= desk_safety.LOCKED_FLOORS[key], key


def test_each_tower_config_edge_not_below_its_venue_floor():
    checked = 0
    for spec, cfg in _tower_configs():
        raw = cfg.get("venue_min_edge")
        venue = desk_profit.BOT_VENUE.get(spec["id"])
        if raw is None or venue is None:
            continue
        values = raw.values() if isinstance(raw, dict) else [raw]
        for value in values:
            assert float(value) + 1e-12 >= desk_safety.LOCKED_FLOORS[venue], spec["id"]
            checked += 1
    assert checked >= 15


def test_runtime_edge_never_below_lock_even_if_config_asks_lower():
    low = {"venue_min_edge": {k: 0.0 for k in desk_profit.VENUE_KEYS}, "min_edge": 0.0}
    for key, lock in desk_safety.LOCKED_FLOORS.items():
        assert desk_profit.venue_min_edge(key, low) + 1e-12 >= lock
    for bot_id in VAULT:
        venue = desk_profit.BOT_VENUE[bot_id]
        assert desk_profit.bot_venue_edge(bot_id, low) + 1e-12 >= desk_safety.LOCKED_FLOORS[venue]
    _, err = desk_profit.parse_venue_min_edge({"kalshi_sports": 0.05})
    assert err and "locked floor" in err


@pytest.mark.parametrize("key", sorted(desk_safety.LOCKED_FLOORS))
def test_startup_refuses_when_a_floor_is_missing_or_lowered(key):
    good = dict(desk_profit.DEFAULT_VENUE_MIN_EDGE)
    missing = {k: v for k, v in good.items() if k != key}
    with pytest.raises(desk_safety.SafetyError):
        desk_safety.startup_check(defaults=missing, environ={})
    lowered = dict(good, **{key: desk_safety.LOCKED_FLOORS[key] - 0.01})
    with pytest.raises(desk_safety.SafetyError):
        desk_safety.startup_check(defaults=lowered, environ={})
    raised = dict(good, **{key: desk_safety.LOCKED_FLOORS[key] + 0.01})
    desk_safety.startup_check(defaults=raised, environ={})


def test_every_venue_has_a_locked_floor_and_every_bot_has_a_venue():
    for key in desk_profit.VENUE_KEYS:
        assert key in desk_safety.LOCKED_FLOORS, key
    for spec in pimp_desk.BOTS:
        if spec["id"] == "wall-street":   # display floor, never trades
            continue
        venue = desk_profit.BOT_VENUE.get(spec["id"])
        assert venue, spec["id"]
        assert venue in desk_safety.LOCKED_FLOORS, (spec["id"], venue)


# ------------------------------------------------------------ step 6: startup line
def test_startup_logs_one_line_with_every_floor():
    stream = io.StringIO()
    logger = logging.getLogger("test_plan_safety_startup")
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        line = desk_safety.startup_check(logger, environ={})
    finally:
        logger.removeHandler(handler)
    out = stream.getvalue().strip().splitlines()
    assert out == [line]
    for key, lock in desk_safety.LOCKED_FLOORS.items():
        assert f"{key} {lock:.2f}" in line
    assert "real money off" in line


def test_desk_service_main_runs_the_startup_check():
    with open(os.path.join(HERE, "desk_service.py"), encoding="utf-8") as fh:
        text = fh.read()
    main = text.split('if __name__ == "__main__":', 1)[1]
    assert "desk_safety.startup_check(" in main
    assert main.index("startup_check") < main.index("run_forever()")


# ------------------------------------------------------------ steps 11, 963: key names, never values
def test_exchange_key_names_reports_names_only():
    env = {"KALSHI_API_KEY": "abc123secret", "COINBASE_API_SECRET": "zzz", "WALLET_SEED": "w",
           "ODDS_API_KEY": "fine", "PORT": "8080", "BINANCE_SECRET": "", "PAPER_TIMER": "external"}
    names = desk_safety.exchange_key_names(env)
    assert names == ["COINBASE_API_SECRET", "KALSHI_API_KEY", "WALLET_SEED"]
    stream = io.StringIO()
    logger = logging.getLogger("test_plan_safety_keys")
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        desk_safety.startup_check(logger, environ=env)
    finally:
        logger.removeHandler(handler)
    text = stream.getvalue()
    assert "KALSHI_API_KEY" in text
    assert "abc123secret" not in text and "zzz" not in text


# ------------------------------------------------------------ steps 9, 963: secret scan
def test_secret_patterns_catch_planted_secrets_and_hide_the_text():
    fake = "ghp_" + "a" * 36
    hits = desk_safety.secret_hits(f"token = '{fake}'")
    assert hits == ["github token"]
    assert fake not in " ".join(hits)
    assert desk_safety.secret_hits("-----BEGIN RSA " + "PRIVATE KEY-----") == ["private key block"]
    assert desk_safety.secret_hits("KALSHI_API_KEY = os.environ.get('KALSHI_API_KEY')") == []


def test_repo_has_no_tracked_secrets():
    try:
        out = subprocess.run(["git", "-C", REPO, "ls-files", "-z"], capture_output=True, timeout=30, check=True)
        files = [f for f in out.stdout.decode("utf-8", "ignore").split("\0") if f]
    except (OSError, subprocess.SubprocessError):
        files = [os.path.relpath(p, REPO) for p in _py_files()]
    found = []
    for rel in files:
        path = os.path.join(REPO, rel)
        if not os.path.isfile(path) or os.path.getsize(path) > 5_000_000:
            continue
        with open(path, "rb") as fh:
            raw = fh.read()
        if b"\0" in raw[:4096]:
            continue
        hits = desk_safety.secret_hits(raw.decode("utf-8", "ignore"))
        if hits:
            found.append((rel, hits))   # file and kind only, never the text
    assert found == []


# ------------------------------------------------------------ steps 951-956, 21-23: desk limits
def test_desk_limits_stay_locked():
    d = pimp_desk.DEFAULTS
    for key, value in desk_safety.RISK_LOCKS.items():
        assert d[key] == value, key
    assert float(d["kelly_fraction"]) <= 0.25
    assert float(d["stake_lo_max"]) <= 20.0
    assert pimp_desk.QUIET_START == "22:00" and pimp_desk.QUIET_END == "07:00"


def _gate(rows):
    with tempfile.TemporaryDirectory() as root:
        return pimp_desk.entry_gate(root, bots=rows)


def _row(bot_id, today=0.0, open_risk=0.0, open_count=0, shadow=False):
    return {"id": bot_id, "today": today, "open_risk": open_risk, "open_count": open_count,
            "shadow_only": shadow}


def test_daily_loss_stop_blocks_vault_buys_at_150():
    assert "Daily loss stop" in _gate([_row("btc15m", today=-150.0)])
    assert "Daily loss stop" in _gate([_row("btc15m", today=-100.0), _row("sports-gap", today=-60.0)])
    assert _gate([_row("btc15m", today=-149.99)]) == ""


def test_open_risk_100_blocks_vault_buys():
    assert "Max open risk" in _gate([_row("btc15m", open_risk=100.0, open_count=3)])
    assert _gate([_row("btc15m", open_risk=99.0, open_count=3)]) == ""


def test_twelve_open_blocks_vault_buys():
    assert "Max open positions" in _gate([_row("btc15m", open_count=7, open_risk=10),
                                          _row("sports-gap", open_count=5, open_risk=10)])
    assert _gate([_row("btc15m", open_count=11, open_risk=10)]) == ""


def test_practice_books_never_count_toward_the_vault_gate():
    rows = [_row("more-15m", today=-900.0, open_risk=900.0, open_count=40, shadow=True)]
    assert _gate(rows) == ""


def test_gate_message_says_settles_still_run():
    msg = _gate([_row("btc15m", today=-200.0)])
    assert "Settle" in msg


# ------------------------------------------------------------ step 24: exits never gated
def test_settle_and_brief_actions_are_not_entry_gated():
    for bot_id, acts in pimp_desk.ACTIONS.items():
        for name, act in acts.items():
            if name in ("settle", "brief"):
                assert act["entry"] is False, (bot_id, name)


# ------------------------------------------------------------ steps 19, 20, 4: practice towers
def test_practice_towers_take_no_risk_share_and_no_vault_cash():
    shares = pimp_desk.DEFAULTS["tower_risk_budgets"]
    assert set(shares) <= set(VAULT)
    assert abs(sum(shares.values()) - 1.0) < 1e-9
    for spec in pimp_desk.BOTS:
        if spec["id"] not in VAULT:
            assert spec.get("shadow_only") is True, spec["id"]
            assert spec["id"] not in shares, spec["id"]


def test_shadow_rows_keep_the_shadow_rules():
    assert engine.STAKE_USD == desk_safety.SHADOW_TICKET
    assert engine.STARTER_CASH == desk_safety.SHADOW_SLEEVE
    for row in new_towers.TOWERS:
        venue = row["venue"]
        assert venue in desk_safety.LOCKED_FLOORS, row["id"]
        assert float(row["floor"]) + 1e-12 >= desk_safety.LOCKED_FLOORS[venue], row["id"]
        if row.get("research"):
            assert int(row["max_open"]) == 0, row["id"]
            assert pimp_desk.TOWER_STARTER_CASH.get(row["id"]) == 0.0
        elif row["id"] in new_towers.BY_ID and row["id"] not in new_towers.PAUSED:
            assert pimp_desk.TOWER_STARTER_CASH.get(row["id"]) == desk_safety.SHADOW_SLEEVE


# ------------------------------------------------------------ steps 32, 33, 34: fills and fees
def test_kalshi_fee_is_ceil_of_seven_percent_p_times_one_minus_p():
    for cents in range(1, 100):
        p = cents / 100
        exact = Fraction(7 * cents * (100 - cents), 10000)   # in cents
        want = math.ceil(exact) / 100
        assert pimp_desk.kalshi_fee(p) == pytest.approx(want), cents
        assert engine.fee(p) == pytest.approx(want), cents


def test_order_fee_is_charged_once_per_order_not_per_contract():
    for cents in (5, 33, 50, 71, 92):
        p = cents / 100
        for contracts in (1, 3, 10, 27):
            exact = Fraction(7 * contracts * cents * (100 - cents), 10000)
            assert engine.order_fee(contracts, p) == pytest.approx(math.ceil(exact) / 100)
            assert engine.order_fee(contracts, p) <= contracts * engine.fee(p) + 1e-9


def test_paper_fill_is_never_better_than_the_ask():
    for cents in range(1, 100):
        ask = cents / 100
        fill = pimp_desk.paper_fill(ask - 0.02, ask)
        assert fill >= ask - 1e-9 or fill == 0.99
        assert pimp_desk.paper_fill(ask - 0.02, ask, adverse=-0.05) >= ask - 1e-9
    assert pimp_desk.paper_fill(0.40, None) is None


def test_edge_after_fee_never_invents_a_price():
    assert pimp_desk.edge_after_fee(0.9, None) is None
    assert pimp_desk.edge_after_fee(None, 0.8) is None


# ------------------------------------------------------------ steps 59, 60: learning and starve
def test_learning_skip_and_starve_numbers():
    assert pimp_desk.LEARN_MIN_SETTLES == 8
    assert pimp_desk.LEARN_HIT_RATE == 0.40
    assert pimp_desk.DEFAULTS["starve_min_n"] == 4
    assert pimp_desk.DEFAULTS["starve_factor"] == 0.15


# ------------------------------------------------------------ steps 75, 76, 945, 946: 50 results
def test_practice_tower_cannot_be_ready_under_50():
    assert desk_safety.practice_status(49)["ready"] is False
    assert "49 of 50" in desk_safety.practice_status(49)["line"]
    assert desk_safety.practice_status(50)["ready"] is True
    with pytest.raises(desk_safety.SafetyError):
        desk_safety.mark_ready(49)
    assert desk_safety.mark_ready(50)["ready"] is True


def test_promotion_needs_50_and_levis_ok():
    assert desk_safety.can_promote(49, True)[0] is False
    assert desk_safety.can_promote(80, False)[0] is False
    assert desk_safety.can_promote(80, None)[0] is False
    assert desk_safety.can_promote(50, True)[0] is True


# ------------------------------------------------------------ step 77, 944: favorite harvest waits
def _harvest_model():
    path = os.path.join(HERE, "favorite-harvest-paper", "harvest_model.py")
    spec = importlib.util.spec_from_file_location("harvest_model_safety", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_favorite_harvest_waits_for_50_results():
    hm = _harvest_model()
    assert hm.MIN_N == 50
    side = {"side": "yes", "ask": 0.90, "bid": 0.88}
    for n, log_only in ((0, True), (49, True), (50, False)):
        cell = {"n": n, "wins": n, "wilson_lo": 0.97, "win_rate": 1.0, "avg_price": 0.90}
        out = hm.price_side(side, "weather", 3, {}, lambda *a, _c=cell: _c if _c["n"] else None)
        assert bool(out.get("log_only")) is log_only, n
    cfg = json.load(open(os.path.join(HERE, "favorite-harvest-paper", "config.json"), encoding="utf-8"))
    assert cfg["shadow_only"] is True and cfg["live_orders"] is False


# ------------------------------------------------------------ steps 947, 948, 6: honest card
def test_promotion_card_counts_every_loss():
    results = [{"pnl": 2.0, "fee": 0.1}] * 30 + [{"pnl": -5.0, "fee": 0.1}] * 20 + [{"pnl": 0.0}]
    card = desk_safety.promotion_card("more-15m", results)
    assert card["results"] == 51
    assert card["wins"] == 30 and card["losses"] == 20
    assert card["total_pnl"] == pytest.approx(60.0 - 100.0)
    assert card["avg_loss"] == pytest.approx(-5.0)
    assert card["avg_win"] == pytest.approx(2.0)
    assert card["fees"] == pytest.approx(5.0)
    assert card["cautious_win_rate"] < card["win_rate"]
    assert card["promote"] is False and card["needs_levi_ok"] is True
    small = desk_safety.promotion_card("x", [{"pnl": 1}] * 10)
    assert small["ready"] is False and "50" in small["line"]


def test_wilson_low_bound():
    assert desk_safety.wilson_low(0, 0) == 0.0
    assert desk_safety.wilson_low(50, 50) < 1.0
    assert desk_safety.wilson_low(30, 50) == pytest.approx(0.4627, abs=1e-3)


# ------------------------------------------------------------ steps 81, 82, 949, 950
def test_demotion_flag_after_30_results_under_bound():
    bad = [1.0] * 10 + [-1.0] * 20
    flag = desk_safety.demotion_check(bad, bound=0.5)
    assert flag["flag"] is True and flag["keeps_losses"] is True
    assert desk_safety.demotion_check([1.0] * 20 + [-1.0] * 10, bound=0.5)["flag"] is False
    assert desk_safety.demotion_check(bad[:29], bound=0.5)["flag"] is False


def test_retire_flag_after_six_months_under_50():
    start = dt.date(2026, 1, 1)
    assert desk_safety.retire_check(start, 20, dt.date(2026, 7, 10))["flag"] is True
    assert desk_safety.retire_check(start, 60, dt.date(2026, 7, 10))["flag"] is False
    assert desk_safety.retire_check(start, 20, dt.date(2026, 3, 1))["flag"] is False


# ------------------------------------------------------------ steps 83, 84, 85: Central day
def test_ct_day_starts_at_midnight_central():
    # 05:59 UTC on 13 Nov is 23:59 CST on 12 Nov; 06:00 UTC is midnight CST.
    assert pimp_desk._ct_date("2026-11-13T05:59:00+00:00") == dt.date(2026, 11, 12)
    assert pimp_desk._ct_date("2026-11-13T06:00:00+00:00") == dt.date(2026, 11, 13)
    assert pimp_desk._ct_date("2026-11-13 06:00:00 UTC") == dt.date(2026, 11, 13)


def test_ct_day_across_daylight_saving():
    # Summer (CDT, UTC-5): midnight is 05:00 UTC.
    assert pimp_desk._ct_date("2026-07-01T04:59:00Z") == dt.date(2026, 6, 30)
    assert pimp_desk._ct_date("2026-07-01T05:00:00Z") == dt.date(2026, 7, 1)
    # Spring forward 8 Mar 2026 and fall back 1 Nov 2026 keep one day each.
    assert pimp_desk._ct_date("2026-03-08T05:59:00Z") == dt.date(2026, 3, 7)
    assert pimp_desk._ct_date("2026-03-09T04:59:00Z") == dt.date(2026, 3, 8)
    assert pimp_desk._ct_date("2026-11-01T04:59:00Z") == dt.date(2026, 10, 31)
    assert pimp_desk._ct_date("2026-11-02T05:59:00Z") == dt.date(2026, 11, 1)


# ------------------------------------------------------------ steps 95, 53, 969: READMEs
def test_every_tower_has_a_readme_that_says_paper():
    for spec in pimp_desk.BOTS:
        path = os.path.join(HERE, spec["folder"], "README.md")
        assert os.path.exists(path), spec["id"]
        with open(path, encoding="utf-8") as fh:
            text = fh.read().lower()
        assert any(w in text for w in ("paper", "shadow", "never buys", "buys nothing")), spec["id"]


# ------------------------------------------------------------ steps 12, 79, 961, 967, 973: docs
@pytest.mark.parametrize("name", ["REAL_MONEY_OFF.md", "PROMOTION_CHECKLIST.md",
                                  "REAL_MONEY_READINESS.md", "RULE_CHANGES.md"])
def test_safety_docs_exist_and_list_the_floors_plainly(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        text = fh.read()
    assert "!" not in text.replace("!=", "")
    low = text.lower()
    for word in ("scrape", "crawl"):
        assert word not in low
    if name in ("REAL_MONEY_OFF.md", "RULE_CHANGES.md"):
        for key, lock in desk_safety.LOCKED_FLOORS.items():
            assert re.search(rf"{key}\D+{lock:.2f}", text), (name, key)
    if name == "PROMOTION_CHECKLIST.md":
        assert "50" in text and "Levi" in text


def test_real_money_off_doc_lists_the_variables_and_no_key_hides():
    with open(os.path.join(HERE, "REAL_MONEY_OFF.md"), encoding="utf-8") as fh:
        doc = fh.read()
    pat = re.compile(r"(?:os\.environ\.get|os\.getenv|os\.environ\[|environ\.get)\(?\s*[\"']([A-Z0-9_]+)[\"']")
    names = set()
    for path in _py_files():
        if os.path.basename(path).startswith("test_") or path.endswith("conftest.py"):
            continue
        with open(path, encoding="utf-8", errors="ignore") as fh:
            names |= set(pat.findall(fh.read()))
    # A new plain setting may land before the doc catches up; a key-style name may not.
    missing = sorted(n for n in names if f"`{n}`" not in doc and desk_safety.exchange_key_names({n: "x"}))
    assert missing == [], missing
    assert len([n for n in names if f"`{n}`" in doc]) >= 20
