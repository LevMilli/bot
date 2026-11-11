"""
paper_sim.py - a pretend brokerage account. NOTHING here touches real money.

How a paper trade works
-----------------------
1. FILL: we "buy" at the real ask price seen on Kalshi's public order book
   (pay-the-ask, no hoping for a better price) and pay Kalshi's taker fee.
2. HOLD: nothing happens until the market settles.
3. SETTLE: we read Kalshi's official result ('yes' or 'no') for that contract.
   If our side won, each contract pays $1.00. If it lost, it pays $0.
   P&L = payout - cost - fee.

Fee formula (Kalshi fee schedule, taker): fee = 0.07 x C x P x (1 - P),
rounded UP to the next whole cent. C = contracts, P = price in dollars.
Example: 29 contracts at $0.85 -> 0.07*29*0.85*0.15 = $0.2588 -> $0.26.

State (bankroll, open positions, history) is saved in paper_state.json so the
bot can be run once per step (scan at 12:30, settle after 3 PM) and remember.
"""
import json
import math
import os
import sys
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json")))
STATE_PATH = os.path.join(HERE, CFG["state_file"])
BUY_EXIT_RULE = "model-flip bid under 50c"
BUY_INTENT = os.path.join(HERE, "buy_intent.json")


def _atomic_json(dest, payload):
    tmp = dest + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        handle.flush()
    os.replace(tmp, dest)


def load_buy_intent():
    if not os.path.exists(BUY_INTENT):
        return None
    try:
        with open(BUY_INTENT, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_buy_intent(*, fill_id, ticker, side, contracts, stake, ask):
    """Write the crash intent before cash moves. The ask has to be a real quote."""
    try:
        ask_n = float(ask)
        stake_n = float(stake)
    except (TypeError, ValueError):
        raise ValueError("buy intent needs the real ask and the stake") from None
    if ask_n != ask_n or ask_n <= 0 or stake_n != stake_n or stake_n <= 0:
        raise ValueError("buy intent needs the real ask and the stake")
    payload = {
        "tower": "kalshi-sized",
        "fill_id": str(fill_id or "").strip(),
        "ticker": str(ticker or "").strip(),
        "side": str(side or ""),
        "contracts": int(contracts),
        "stake": round(stake_n, 2),
        "ask": ask_n,
        "exit_rule": BUY_EXIT_RULE,
        "paper_only": True,
        "status": "intent",
    }
    if not payload["fill_id"] or not payload["ticker"]:
        raise ValueError("buy intent needs a fill id and a ticker")
    _atomic_json(BUY_INTENT, payload)
    return payload


def reconcile_buy_intent(state):
    """Match an intent to the saved book. Never create a position or a price."""
    intent = load_buy_intent()
    if not isinstance(intent, dict):
        return "none"
    fid = str(intent.get("fill_id") or "")
    book = state if isinstance(state, dict) else {}
    opens = [p for p in book.get("open") or [] if isinstance(p, dict)]
    closed = [p for p in book.get("closed") or [] if isinstance(p, dict)]
    if fid and any(str(p.get("fill_id") or "") == fid for p in opens):
        status = "open"
    elif fid and any(str(p.get("fill_id") or "") == fid for p in closed):
        status = "closed"
    else:
        status = "abandoned"
    if intent.get("status") != status or intent.get("paper_only") is not True:
        intent["status"] = status
        intent["paper_only"] = True
        intent["exit_rule"] = BUY_EXIT_RULE
        _atomic_json(BUY_INTENT, intent)
    return status


def already_open(state, fill_id="") -> str:
    """A restart that finds the open row does not buy again."""
    opens = [p for p in (state or {}).get("open") or [] if isinstance(p, dict)]
    if not opens:
        return ""
    return "open row already on the book"


def real_side_bid(bid):
    """A bid inside (0, 1). Missing, zero, and a wipe are not a mark."""
    try:
        number = float(bid)
    except (TypeError, ValueError):
        return None
    if number != number or not (0.0 < number < 1.0):
        return None
    return number


def bid_under_exit(bid, floor=0.50) -> bool:
    """Under 50¢ is the exit signal. A missing bid is not under 50¢."""
    mark = real_side_bid(bid)
    if mark is None:
        return False
    try:
        bar = float(floor)
    except (TypeError, ValueError):
        bar = 0.50
    return mark < bar


def _sized_row(pos) -> bool:
    """This tower's open row. An S&P row is not watched here."""
    if not isinstance(pos, dict):
        return False
    owner = str(pos.get("tower") or pos.get("bot") or "kalshi-sized")
    if owner in ("kalshi-sp", "sp", "S&P"):
        return False
    return owner in ("kalshi-sized", "sized", "S&P-sized")


def watch_open(pos, quotes):
    """Mark the held contract at its own side bid. This does not sell.

    A quote for another ticker, including S&P's, is not this mark.
    A missing bid does not replace a prior mark.
    """
    if not _sized_row(pos) or not isinstance(quotes, dict):
        return {"marked": False, "sold": False}
    ticker = str(pos.get("ticker") or "")
    book = quotes.get(ticker)
    if not ticker or not isinstance(book, dict):
        return {"marked": False, "sold": False}
    named = str(book.get("ticker") or ticker)
    if named != ticker:
        return {"marked": False, "sold": False}
    side = str(pos.get("side") or "").lower()
    if side == "yes":
        raw = book.get("yes_bid")
    elif side == "no":
        raw = book.get("no_bid")
    else:
        return {"marked": False, "sold": False}
    mark = real_side_bid(raw)
    if mark is None:
        return {"marked": False, "sold": False}
    pos["last_mark"] = mark
    pos["tower"] = "kalshi-sized"
    return {
        "marked": True,
        "sold": False,
        "last_mark": mark,
        "exit_signal": bid_under_exit(mark, 0.50),
    }


def watch_opens(state, quotes):
    notes = []
    for pos in list((state or {}).get("open") or []):
        if not isinstance(pos, dict):
            continue
        result = watch_open(pos, quotes)
        if result.get("marked"):
            notes.append(f"{pos.get('ticker')} last_mark={result['last_mark']} sold=False")
    return notes


def failsafe_sale(pos, bid, *, floor=0.50, quote_ticker=None):
    """Sell this tower's contract at its own bid minus the taker.

    An S&P contract is not sold. A missing bid is not a sale.
    The sale does not open another ticket.
    """
    if not _sized_row(pos):
        return None
    if quote_ticker is not None and str(quote_ticker) != str(pos.get("ticker") or ""):
        return None
    mark = real_side_bid(bid)
    if not bid_under_exit(bid, floor):
        return None
    try:
        contracts = float(pos.get("contracts") or 0)
        cost = float(pos.get("cost") or 0)
        entry_fee = float(pos.get("fee") or 0)
    except (TypeError, ValueError):
        return None
    if contracts <= 0 or mark is None:
        return None
    fee = taker_fee(contracts, mark)
    proceeds = round(contracts * mark - fee, 4)
    pnl = round(proceeds - cost - entry_fee, 4)
    return {
        "exit": BUY_EXIT_RULE,
        "exit_price": mark,
        "exit_fee": fee,
        "payout": proceeds,
        "pnl": pnl,
        "opens_new_ticket": False,
        "unlocks_fill": False,
    }


def apply_failsafe(state, pos, bid, *, floor=0.50, quote_ticker=None):
    """Close this tower's open row. The day's fill stays counted."""
    if not isinstance(state, dict) or not isinstance(pos, dict):
        return None
    if pos not in (state.get("open") or []):
        return None
    sale = failsafe_sale(pos, bid, floor=floor, quote_ticker=quote_ticker)
    if not isinstance(sale, dict) or sale.get("opens_new_ticket") or sale.get("unlocks_fill"):
        return None
    state["bankroll"] = round(float(state.get("bankroll") or 0) + float(sale["payout"]), 4)
    pos.update({
        "status": "sold",
        "exit": sale["exit"],
        "exit_price": sale["exit_price"],
        "exit_fee": sale["exit_fee"],
        "payout": sale["payout"],
        "pnl": sale["pnl"],
        "settled_at": dt.datetime.now().isoformat(timespec="seconds"),
        "paper_only": True,
    })
    state["open"] = [p for p in state["open"] if p is not pos]
    state.setdefault("closed", []).append(pos)
    return sale


def header_only_note(text) -> bool:
    """A title with no closed row. It is not a sample fill."""
    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    if not lines:
        return True
    return all(ln.startswith("#") for ln in lines)


def record_close(pos, *, bankroll, reason, bid=None, root=None):
    """Closed row with the bid and the reason already on the book.

    A header-only note is not turned into a sample fill. A bid is stored only
    when it is a real quote. A settle does not invent one. P/L is not retyped.
    The same fill and reason are not written twice.
    """
    raw = str(reason or "").strip()
    if header_only_note(raw):
        return {"fill": False, "fact": "header-only learning file", "paper_only": True}
    if not _sized_row(pos):
        return None
    label = raw or str(pos.get("exit") or "").strip()
    if not label:
        return {"fill": False, "fact": "header-only learning file", "paper_only": True}
    pnl_before = pos.get("pnl")
    try:
        pos["bankroll_after"] = round(float(bankroll), 4)
    except (TypeError, ValueError):
        pass
    if not pos.get("exit"):
        pos["exit"] = label
    if pnl_before is not None:
        pos["pnl"] = pnl_before
    stored = real_side_bid(bid)
    if stored is not None and pos.get("exit_price") is None:
        pos["exit_price"] = stored
    fee_for_journal = pos.get("exit_fee")
    if fee_for_journal is None:
        fee_for_journal = pos.get("fee")
    journal_root = root if root is not None else os.path.dirname(HERE)
    try:
        if journal_root not in sys.path:
            sys.path.insert(0, journal_root)
        import desk_brain
        return desk_brain.record_decision(
            journal_root,
            bot="kalshi-sized",
            action="settle" if label == "settled" else "sell",
            ticker=str(pos.get("ticker") or ""),
            side=str(pos.get("side") or ""),
            reasons=[label],
            note=label[:240],
            fill_id=str(pos.get("fill_id") or ""),
            bid=stored,
            stake=pos.get("risk") if pos.get("risk") is not None else pos.get("cost"),
            exit_name=label,
            fee=fee_for_journal,
            cash=pos.get("bankroll_after"),
        )
    except Exception:
        return None


def taker_fee(contracts, price, rate=None):
    """Kalshi taker fee, rounded up to the cent. Tiny epsilon avoids 0.26000000001 -> 0.27."""
    rate = CFG["taker_fee_rate"] if rate is None else rate
    raw = rate * contracts * price * (1 - price)
    return math.ceil(raw * 100 - 1e-9) / 100.0


def trade_pnl(side, won, contracts, ask, fee):
    """Profit/loss in dollars of one held-to-settlement trade."""
    cost = contracts * ask
    payout = contracts * 1.0 if won else 0.0
    return round(payout - cost - fee, 4)


# ------------------------------------------------------------- persistent account
def new_state():
    return {"bankroll": CFG["starting_bankroll"], "open": [], "closed": [], "halted": False,
            "created": dt.datetime.now().isoformat(timespec="seconds")}


def load_state(path=STATE_PATH):
    if os.path.exists(path):
        return json.load(open(path))
    return new_state()


def save_state(state, path=STATE_PATH):
    if os.path.islink(path):
        path = os.path.realpath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    json.dump(state, open(tmp, "w"), indent=1)
    os.replace(tmp, path)      # atomic write so a crash can't corrupt the file


def open_position(state, day, event_ticker, pick, contracts, entry_time_iso):
    """Record a simulated buy. Cash is reserved (cost + fee) immediately."""
    fee = taker_fee(contracts, pick["ask"])
    cost = round(contracts * pick["ask"], 4)
    stake = round(cost + fee, 4)
    max_payout = float(contracts)
    reward = round(max_payout - stake, 4)
    pos = {"day": str(day), "event": event_ticker, "ticker": pick["ticker"], "side": pick["side"],
           "strike": pick.get("strike"), "bid": pick.get("bid"), "ask": pick["ask"], "contracts": contracts,
           "cost": cost, "fee": fee, "risk": stake, "reward": reward,
           "risk_reward": round(reward / stake, 4) if stake else None,
           "max_payout": max_payout,
           "why": "Sized paper buy. The ask was in the 84 to 92 cent band; desk Kelly-lite sized.",
           "entry_time": entry_time_iso, "status": "open",
           "price_source": "https://api.elections.kalshi.com/trade-api/v2",
           "price_at": entry_time_iso,
           "fill_id": f"{pick.get('ticker')}|{entry_time_iso}",
           "exit_rule": BUY_EXIT_RULE, "tower": "kalshi-sized", "paper_only": True}
    try:
        desk_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if desk_root not in sys.path:
            sys.path.insert(0, desk_root)
        import desk_roi_plan as _xp
        pos["exit_plan"] = _xp.default_exit_plan("kalshi-sized")
    except Exception:
        pos["exit_plan"] = {
            "kind": "model_flip+settle",
            "model_flip": True,
            "settle_backstop": True,
            "fee_floors_locked": True,
        }
    state["bankroll"] = round(state["bankroll"] - cost - fee, 4)
    state["open"].append(pos)
    return pos


def place_paper_buy(state, day, event_ticker, pick, contracts, entry_time):
    """One paper buy. The intent is on disk before cash moves.

    An open row already on the book is not bought again.
    """
    held = already_open(state)
    if held:
        return held
    try:
        ask = float(pick["ask"])
        count = int(contracts)
    except (TypeError, ValueError, KeyError):
        return "buy intent needs a real ask"
    if ask <= 0 or count < 1:
        return "buy intent needs a real ask"
    fee = taker_fee(count, ask)
    stake = round(count * ask + fee, 2)
    fill_id = f"{pick.get('ticker')}|{entry_time}"
    try:
        write_buy_intent(
            fill_id=fill_id,
            ticker=pick.get("ticker"),
            side=pick.get("side"),
            contracts=count,
            stake=stake,
            ask=ask,
        )
    except (TypeError, ValueError):
        return "buy intent needs a real ask"
    return open_position(state, day, event_ticker, pick, count, entry_time)


def settle_position(state, pos, market_result):
    """market_result: Kalshi 'result' field ('yes'/'no'). Returns the closed position or None if not final."""
    if market_result not in ("yes", "no"):
        return None                                   # not settled yet
    won = (market_result == pos["side"])
    payout = pos["contracts"] * 1.0 if won else 0.0
    pnl = trade_pnl(pos["side"], won, pos["contracts"], pos["ask"], pos["fee"])
    state["bankroll"] = round(state["bankroll"] + payout, 4)
    pos.update({"status": "won" if won else "lost", "result": market_result, "payout": payout, "pnl": pnl,
                "settled_at": dt.datetime.now().isoformat(timespec="seconds")})
    state["open"] = [p for p in state["open"] if p is not pos]
    state["closed"].append(pos)
    if state["bankroll"] <= CFG["kill_switch_bankroll"]:
        state["halted"] = True
    return pos


def realised_pnl_on(state, day):
    return round(sum(p["pnl"] for p in state["closed"] if p["day"] == str(day)), 4)


def trades_on(state, day):
    return sum(1 for p in state["open"] + state["closed"] if p["day"] == str(day))


if __name__ == "__main__":
    assert taker_fee(29, 0.85) == 0.26, taker_fee(29, 0.85)
    assert taker_fee(31, 0.80) == 0.35, taker_fee(31, 0.80)    # 0.07*31*.8*.2 = 0.3472 -> 0.35
    assert taker_fee(27, 0.90) == 0.18, taker_fee(27, 0.90)    # 0.1701 -> 0.18
    assert trade_pnl("yes", True, 29, 0.85, 0.26) == round(29 - 24.65 - 0.26, 4)
    assert trade_pnl("no", False, 29, 0.85, 0.26) == -24.91
    s = new_state(); p = open_position(s, dt.date(2026, 1, 2), "EV", {"ticker": "T", "side": "no", "ask": 0.85}, 29, "x")
    assert abs(s["bankroll"] - (500 - 24.65 - 0.26)) < 1e-9
    settle_position(s, p, "no"); assert abs(s["bankroll"] - (500 + 29 - 24.65 - 0.26)) < 1e-9 and p["pnl"] == 4.09
    print("paper_sim self-test OK: win +$4.09, loss -$24.91 on 29 @ 85c")
