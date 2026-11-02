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
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json")))
STATE_PATH = os.path.join(HERE, CFG["state_file"])


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
           "fill_id": f"{pick.get('ticker')}|{entry_time_iso}"}
    state["bankroll"] = round(state["bankroll"] - cost - fee, 4)
    state["open"].append(pos)
    return pos


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
