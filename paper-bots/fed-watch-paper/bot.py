#!/usr/bin/env python3
"""Fed Watch — shadow paper tower.

Compares the Polymarket "Fed Decision in <month>?" mid (fed_feed.py) to the
Kalshi KXFEDDECISION YES/NO ask on the same meeting and outcome. Buys only when lag edge after Kalshi fee clears
the locked economics floor 0.05.

Paper only. Shadow only. Spends no desk cash. Never LIVE.
KXFED / rates series stay idea-bank for main AUTO — this sleeve researches only.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
LOCKED_FLOOR = 0.05
STAKE_USD = 25.0
STARTER_CASH = 500.0


def locked_cfg(raw: dict | None = None) -> dict:
    cfg = dict(raw or {})
    floor = float(cfg.get("venue_min_edge") or LOCKED_FLOOR)
    cfg["venue_min_edge"] = max(LOCKED_FLOOR, floor)
    cfg["paper_only"] = True
    cfg["live_orders"] = False
    cfg["shadow_only"] = True
    cfg["stake_usd"] = float(cfg.get("stake_usd") or STAKE_USD)
    cfg["starter_cash"] = float(cfg.get("starter_cash") or STARTER_CASH)
    cfg["max_open"] = int(cfg.get("max_open") or 1)
    return cfg


def kalshi_fee_per_contract(ask: float) -> float:
    """Same ceil(0.07·p·(1-p)) dollars per $1 contract as desk_roi_plan."""
    p = float(ask)
    if not (0.0 < p < 1.0) or not math.isfinite(p):
        return 0.0
    raw = 0.07 * p * (1.0 - p)
    return math.ceil(round(raw * 100, 6)) / 100.0


def fed_decision(quote: dict, cfg: dict | None = None) -> dict:
    """Fee-aware FedWatch→Kalshi relative-value decision for one outcome row."""
    cfg = locked_cfg(cfg)
    fair = _num(
        quote.get("fedwatch_fair")
        if quote.get("fedwatch_fair") is not None
        else quote.get("fair")
    )
    ask = _num(quote.get("ask"))
    label = str(quote.get("outcome") or quote.get("ticker") or quote.get("game") or "fed")
    src = str(quote.get("source") or "fedwatch")
    row = {
        "outcome": label,
        "ticker": str(quote.get("ticker") or ""),
        "side": str(quote.get("side") or "yes"),
        "meeting": str(quote.get("meeting") or ""),
        "source": src,
        "fair": fair,
        "action": "skip",
        "reason": "",
        "fedwatch_fair": fair,
        "ask": ask,
        "fee": None,
        "edge": None,
        "floor": cfg["venue_min_edge"],
        "paper_only": True,
        "shadow_only": True,
        "idea_bank_only": True,
    }
    if fair is None or ask is None:
        row["reason"] = "need fair + ask"
        return row
    if not (0.0 < ask < 1.0) or not (0.0 < fair < 1.0):
        row["reason"] = "fair/ask out of range"
        return row
    fee = kalshi_fee_per_contract(ask)
    edge = fair - ask - fee
    row["fee"] = round(fee, 4)
    row["edge"] = round(edge, 4)
    if edge + 1e-12 < float(cfg["venue_min_edge"]):
        row["reason"] = (
            f"fed edge {edge:.4f} < floor {cfg['venue_min_edge']:g} "
            f"(fair {fair:.3f} ask {ask:.3f} fee {fee:.4f})"
        )
        return row
    row["action"] = "buy"
    row["reason"] = (
        f"{src} clears floor: fair {fair:.3f} ask {ask:.3f} "
        f"fee {fee:.4f} edge {edge:.4f}"
    )
    return row


def load_quotes(tower: str) -> list[dict]:
    """Optional fixture file. Empty → waiting on FedWatch (no invent)."""
    path = os.path.join(tower, "fedwatch_quotes.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        data = data.get("quotes") or data.get("rows") or []
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def quotes_from_bins(bins: list[dict]) -> list[dict]:
    """Build quote rows from FedWatch fair + Kalshi ask bins. Skip incomplete."""
    out = []
    for row in bins or []:
        if not isinstance(row, dict):
            continue
        fair = _num(
            row.get("fedwatch_fair") if row.get("fedwatch_fair") is not None else row.get("fair")
        )
        ask = _num(row.get("ask") if row.get("ask") is not None else row.get("kalshi_ask"))
        if fair is None or ask is None:
            continue
        if not (0.0 < ask < 1.0) or not (0.0 < fair < 1.0):
            continue
        out.append({
            "outcome": str(row.get("outcome") or row.get("label") or row.get("ticker") or "fed"),
            "fedwatch_fair": round(float(fair), 4),
            "ask": round(float(ask), 4),
            "ticker": str(row.get("ticker") or ""),
            "meeting": str(row.get("meeting") or row.get("fomc") or ""),
            "source": str(row.get("source") or "fedwatch"),
        })
    return out


def write_fedwatch_quotes(tower: str, quotes: list[dict], *, note: str = "") -> str:
    path = os.path.join(tower, "fedwatch_quotes.json")
    payload = {
        "paper_only": True,
        "shadow_only": True,
        "fee_floors_locked": True,
        "idea_bank_only": True,
        "floor": LOCKED_FLOOR,
        "note": note or "CME FedWatch fair vs Kalshi ask — never invent",
        "quotes": list(quotes or []),
    }
    _write_json(path, payload)
    return path


def harvest_from_bins(
    desk_root: str | None,
    bins: list[dict],
    *,
    note: str = "",
) -> dict:
    """Write fedwatch_quotes.json from fair/ask bins. No network. No invent."""
    desk_root = desk_root or DESK_ROOT
    tower = os.path.join(desk_root, "fed-watch-paper")
    os.makedirs(tower, exist_ok=True)
    quotes = quotes_from_bins(bins)
    path = write_fedwatch_quotes(
        tower,
        quotes,
        note=note or "harvested FedWatch/Kalshi bins",
    )
    return {
        "ok": True,
        "paper_only": True,
        "shadow_only": True,
        "fee_floors_locked": True,
        "idea_bank_only": True,
        "path": path,
        "n": len(quotes),
        "bin_n": len(bins or []),
        "quotes": quotes,
        "note": "Incomplete fair/ask bins skipped — no invent",
    }


def empty_state(cfg: dict) -> dict:
    return {
        "cash": float(cfg["starter_cash"]),
        "open": [],
        "closed": [],
        "paper_only": True,
        "shadow_only": True,
        "live_orders": False,
        "idea_bank_only": True,
        "checks": 0,
    }


def run_once(
    desk_root: str | None = None,
    cfg: dict | None = None,
    quotes: list | None = None,
    now: dt.datetime | None = None,
) -> int:
    desk_root = desk_root or DESK_ROOT
    tower = os.path.join(desk_root, "fed-watch-paper")
    os.makedirs(tower, exist_ok=True)
    cfg = locked_cfg(cfg or _read_json(os.path.join(tower, "config.json")) or {})
    now = now or dt.datetime.now(dt.timezone.utc)
    state = _read_json(os.path.join(tower, "paper_account.json")) or empty_state(cfg)
    state.setdefault("open", [])
    state.setdefault("closed", [])
    state["paper_only"] = True
    state["shadow_only"] = True
    state["live_orders"] = False
    state["idea_bank_only"] = True
    feed = None
    if quotes is not None:
        rows = list(quotes)
    else:
        rows, feed = _live_or_file(tower)
    settled = settle_open(state, now)
    held = {(str(p.get("kalshi_ticker") or ""), str(p.get("side") or "")) for p in state.get("open") or []}
    decisions = [fed_decision(row, cfg) for row in rows]
    for decision in decisions:
        if decision.get("action") == "buy" and (decision.get("ticker"), decision.get("side")) in held:
            decision["action"] = "skip"
            decision["reason"] = "already holding this side"
    bought = None
    blocked = os.environ.get("DESK_BLOCK_ENTRIES") == "1"
    if blocked:
        for decision in decisions:
            if decision.get("action") == "buy":
                decision["action"] = "skip"
                decision["reason"] = "desk entry gate"
    open_n = len(state.get("open") or [])
    if open_n >= int(cfg["max_open"]):
        for decision in decisions:
            if decision.get("action") == "buy":
                decision["action"] = "skip"
                decision["reason"] = "max open"
    else:
        ranked = sorted(decisions, key=lambda d: -(d.get("edge") or -1))
        for decision in ranked:
            if decision.get("action") != "buy":
                continue
            cash = float(state.get("cash") or 0)
            stake = float(cfg["stake_usd"])
            if cash + 1e-9 < stake:
                decision["action"] = "skip"
                decision["reason"] = "shadow cash below ticket"
                continue
            per = float(decision.get("ask") or 0) + float(decision.get("fee") or 0)
            contracts = int(stake // per) if per > 0 else 0
            if contracts < 1:
                decision["action"] = "skip"
                decision["reason"] = "ticket buys no contract"
                continue
            cost = round(contracts * per, 2)
            state["cash"] = round(cash - cost, 4)
            state["open"].append({
                "ticker": decision.get("outcome"),
                "kalshi_ticker": decision.get("ticker"),
                "side": decision.get("side") or "yes",
                "meeting": decision.get("meeting"),
                "source": decision.get("source"),
                "contracts": contracts,
                "fee": decision.get("fee"),
                "cost": cost,
                "ask": decision.get("ask"),
                "fair": decision.get("fair"),
                "edge": decision.get("edge"),
                "opened": now.isoformat(timespec="seconds"),
                "paper_only": True,
                "shadow_only": True,
                "idea_bank_only": True,
                "exit_plan": {
                    "kind": "model-flip+settle",
                    "fee_floors_locked": True,
                    "note": "shadow fed-watch; staff settle backstop; idea-bank",
                },
            })
            bought = decision.get("outcome")
            break
    state["checks"] = int(state.get("checks") or 0) + 1
    state["last_check"] = now.isoformat(timespec="seconds")
    _write_json(os.path.join(tower, "paper_account.json"), state)
    _append_research(tower, now, decisions)
    for row in settled:
        print(f"SETTLE: {row.get('ticker')} {row.get('result')} pnl {row.get('pnl'):+.2f}")
    if bought:
        print(f"SIGNAL: BUY {bought}")
        print(f"CARD: paper buy {bought} fed watch (Polymarket vs Kalshi)")
    elif not decisions:
        note = (feed or {}).get("note") or "waiting on Fed quotes (Polymarket vs Kalshi)"
        print(f"SIGNAL: SKIP {note}")
        print(f"CARD: {note} (no invent)")
        print("no trade")
    else:
        first = max(decisions, key=lambda d: d.get("edge") if d.get("edge") is not None else -9)
        print(f"SIGNAL: SKIP {first.get('outcome')} {first.get('reason')}")
        print("CARD: " + str(first.get("reason") or "no fee-clear fedwatch"))
        print("no trade")
    return 0


def _live_or_file(tower: str):
    """Live Polymarket vs Kalshi Fed decision quotes; the file only if the read fails."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    try:
        import fed_feed
        quotes, status = fed_feed.live_quotes()
    except Exception as exc:  # noqa: BLE001
        rows = load_quotes(tower)
        return rows, {"note": f"Polymarket/Kalshi read failed ({type(exc).__name__}); waiting"}
    try:
        write_fedwatch_quotes(tower, quotes, note="live Polymarket mid vs Kalshi KXFEDDECISION ask")
    except OSError:
        pass
    if not quotes:
        status["note"] = "no Fed meeting priced on both Polymarket and Kalshi"
    return quotes, status


def _kalshi_market(ticker: str) -> dict:
    if DESK_ROOT not in sys.path:
        sys.path.insert(0, DESK_ROOT)
    import public_http
    url = f"https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}"
    data = json.loads(public_http.read(url, timeout=10).decode("utf-8"))
    return data.get("market") or {}


def settle_open(state: dict, now: dt.datetime, fetch=None) -> list:
    """Close rows whose Kalshi market has a result. $1 per contract when it matches our side."""
    fetch = fetch or _kalshi_market
    closed, keep = [], []
    for pos in state.get("open") or []:
        ticker = str(pos.get("kalshi_ticker") or "")
        if not ticker:
            keep.append(pos)
            continue
        try:
            market = fetch(ticker)
        except Exception:  # noqa: BLE001
            keep.append(pos)
            continue
        result = str(market.get("result") or "").lower()
        if result not in ("yes", "no"):
            keep.append(pos)
            continue
        side = str(pos.get("side") or "yes").lower()
        contracts = int(pos.get("contracts") or 0)
        payout = float(contracts) if result == side else 0.0
        cost = float(pos.get("cost") or 0)
        row = dict(pos)
        row.update({
            "result": result,
            "payout": round(payout, 2),
            "pnl": round(payout - cost, 2),
            "closed": now.isoformat(timespec="seconds"),
            "exit": "settled",
        })
        state["cash"] = round(float(state.get("cash") or 0) + payout, 4)
        state.setdefault("closed", []).append(row)
        closed.append(row)
    state["open"] = keep
    return closed


def _num(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(n):
        return None
    return n


def _read_json(path: str):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def _append_research(tower: str, now: dt.datetime, decisions: list[dict]) -> None:
    path = os.path.join(tower, "research.jsonl")
    row = {
        "at": now.isoformat(timespec="seconds"),
        "paper_only": True,
        "shadow_only": True,
        "idea_bank_only": True,
        "decisions": decisions,
    }
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def harvest_live(desk_root: str | None = None) -> dict:
    """Opt-in harvest from local fedwatch_bins.json only. No network invent.

    Live CME FedWatch scrape is not wired yet — staff drops matched fair/ask
    bins into fed-watch-paper/fedwatch_bins.json, then this writes quotes.
    Incomplete bins are skipped.
    """
    desk_root = desk_root or DESK_ROOT
    tower = os.path.join(desk_root, "fed-watch-paper")
    path = os.path.join(tower, "fedwatch_bins.json")
    if not os.path.isfile(path):
        return {
            "ok": True,
            "paper_only": True,
            "shadow_only": True,
            "idea_bank_only": True,
            "fee_floors_locked": True,
            "n": 0,
            "quotes": [],
            "reason": "waiting on fedwatch_bins.json (no invent; CME scrape not wired)",
        }
    raw = _read_json(path) or {}
    bins = raw.get("bins") or raw.get("quotes") or raw.get("rows") or []
    if not isinstance(bins, list):
        bins = []
    out = harvest_from_bins(
        desk_root,
        bins,
        note="harvested from fedwatch_bins.json — incomplete skipped",
    )
    out["source"] = path
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--reset" in argv:
        tower = os.path.join(DESK_ROOT, "fed-watch-paper")
        cfg = locked_cfg(_read_json(os.path.join(tower, "config.json")) or {})
        _write_json(os.path.join(tower, "paper_account.json"), empty_state(cfg))
        print("reset paper account")
        return 0
    if "--harvest" in argv:
        out = harvest_live(DESK_ROOT)
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if out.get("ok") else 2
    return run_once()


if __name__ == "__main__":
    raise SystemExit(main())
