"""Settlement auditor. Offline."""
import datetime as dt
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "settlement-auditor-paper"))

import audit_model as am  # noqa: E402

NOW = dt.datetime(2026, 11, 12, 18, tzinfo=dt.timezone.utc)


def _row(ticker, side, result, contracts=10, payout=None, **kw):
    if payout is None:
        payout = float(contracts) if side == result else 0.0
    return dict(ticker=ticker, side=side, result=result, contracts=contracts, payout=payout,
                closed="2026-11-11T20:00:00+00:00", pnl=1.0, **kw)


def test_settled_rows_skip_sold_and_non_kalshi():
    state = {"closed": [
        _row("KXA-1", "yes", "yes"),
        dict(ticker="KXA-2", side="yes", exit="model-flip", payout=5.0),       # sold: no result
        dict(_row("KXA-3", "no", "no"), status="sold"),
        _row("ETH-USD", "yes", "yes"),
        "junk",
    ]}
    assert [r["ticker"] for r in am.settled_rows("x", state)] == ["KXA-1"]


def test_check_result_and_payout():
    assert am.check(_row("KXA", "yes", "yes"), "yes") == ""
    assert am.check(_row("KXA", "yes", "yes"), "no") == "recorded yes, Kalshi says no"
    assert am.check(_row("KXA", "yes", "yes", payout=0.0), "yes") == "paid $0.00, should be $10.00"
    assert am.check(_row("KXA", "no", "yes", payout=10.0), "yes") == "paid $10.00, should be $0.00"


def test_run_checks_once_keeps_mismatch_and_caps_reads():
    states = {"tower-a": {"closed": [_row("KXA-1", "yes", "yes"), _row("KXA-2", "no", "yes")]},
              "tower-b": {"closed": [_row("KXB-1", "yes", "no", payout=10.0)]}}
    official = {"KXA-1": "yes", "KXA-2": "no", "KXB-1": "no"}
    calls = []

    def fetch(ticker):
        calls.append(ticker)
        return {"result": official[ticker]}

    body = am.run(states, {}, fetch, NOW)
    assert len(body["checked"]) == 3 and body["reads"] == 3
    bad = {m["ticker"]: m["problem"] for m in body["mismatches"]}
    assert bad == {"KXA-2": "recorded yes, Kalshi says no", "KXB-1": "paid $10.00, should be $0.00"}
    calls.clear()
    again = am.run(states, json.loads(json.dumps(body)), fetch, NOW)
    assert sorted(calls) == ["KXA-2", "KXB-1"]            # good trade not re-read; mismatches are
    assert len(again["mismatches"]) == 2
    capped = am.run(states, {}, fetch, NOW, max_reads=1)
    assert capped["reads"] == 1 and capped["pending"] == 2
    assert "2 mismatches" in am.card(body)
    assert am.card(am.run({"t": {"closed": [_row("KXA-1", "yes", "yes")]}}, {}, fetch, NOW)).endswith("all match")


def test_unsettled_and_failed_reads_wait():
    states = {"t": {"closed": [_row("KXA-1", "yes", "yes"), _row("KXA-9", "yes", "yes")]}}

    def fetch(ticker):
        if ticker == "KXA-9":
            raise TimeoutError
        return {"result": ""}

    body = am.run(states, {}, fetch, NOW)
    assert body["checked"] == {} and body["pending"] == 2 and body["notes"]


def test_reset_drops_old_checks():
    states = {"t": {"closed": [_row("KXA-1", "yes", "yes")]}}
    body = am.run(states, {}, lambda t: {"result": "yes"}, NOW)
    assert am.run({"t": {"closed": []}}, body, lambda t: {"result": "yes"}, NOW)["checked"] == {}


def test_bot_main_writes_audit(tmp_path):
    spec = importlib.util.spec_from_file_location("audit_bot", os.path.join(HERE, "settlement-auditor-paper", "bot.py"))
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    folder = tmp_path / "nasdaq-paper"
    folder.mkdir()
    (folder / "paper_account.json").write_text(json.dumps({"closed": [_row("KXNASDAQ100-X", "no", "no")]}))
    assert bot.main([], root=str(tmp_path), fetch=lambda t: {"result": "no"}, now=NOW) == 0
    audit = json.loads((tmp_path / "settlement-auditor-paper" / "audit.json").read_text())
    assert len(audit["checked"]) == 1 and audit["mismatches"] == []
    acct = json.loads((tmp_path / "settlement-auditor-paper" / "paper_account.json").read_text())
    assert acct["cash"] == 0.0 and acct["research"] is True


def test_registry_and_desk_wiring():
    import new_towers
    import pimp_desk

    assert "settlement-auditor" in new_towers.RESEARCH
    assert pimp_desk._account_body("settlement-auditor")["cash"] == 0.0
    assert "settlement-auditor-paper/audit.json" in pimp_desk.SETTLEMENT_FILES
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import new_tower
    assert new_tower.check_tower("settlement-auditor")["ok"]
