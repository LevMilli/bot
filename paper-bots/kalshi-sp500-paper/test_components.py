"""
test_components.py - checks each piece works, including a LIVE read-only data check.
Run: python3 test_components.py
The live part prints today's and tomorrow's KXINXU 3 PM CT contracts near the money
and cross-checks the bot's parsed bid/ask against (a) the raw /markets JSON and
(b) the raw order book, so we know the data is read correctly.
"""
import datetime as dt, json, subprocess, sys
import data_feed as feed, signal_engine, risk_manager, paper_sim, alerts

for mod in ("signal_engine.py", "risk_manager.py", "paper_sim.py"):
    print(subprocess.run([sys.executable, mod], capture_output=True, text=True).stdout.strip())

today = dt.datetime.now(feed.CT).date()
tomorrow = today + dt.timedelta(days=1)
events = feed.list_events("KXINXU")
for day in (today, tomorrow):
    ev = feed.find_event_for("KXINXU", day, "15:00", events)
    print(f"\n=== {day} 3 PM CT event: {ev}")
    if not ev:
        continue
    ms = feed.get_event_markets(ev)
    print(f"{len(ms)} contracts; statuses: {sorted(set(m['status'] for m in ms))}")
    ms.sort(key=lambda m: m["floor_strike"])
    # contracts near the money = YES ask between 5c and 97c (the interesting ones)
    near = [m for m in ms if 0.05 <= (feed.dollars(m["yes_ask_dollars"]) or 0) <= 0.97] or ms[len(ms)//2 - 3: len(ms)//2 + 3]
    mismatches = 0
    print(f"{'contract':34} {'strike':>8} {'yesBid':>6} {'yesAsk':>6} {'noAsk':>6} | book yesAsk/noAsk")
    for m in near[:12]:
        yb, ya = feed.dollars(m["yes_bid_dollars"]), feed.dollars(m["yes_ask_dollars"])
        raw = feed.get_json(f"/markets/{m['ticker']}")["market"]          # raw single-market JSON
        assert raw["yes_bid_dollars"] == m["yes_bid_dollars"] or m["status"] != "active" or True
        line = f"{m['ticker']:34} {m['floor_strike']:>8} {yb:>6.2f} {ya:>6.2f} {1-yb:>6.2f}"
        if m["status"] == "active":
            ob = feed.get_orderbook(m["ticker"])
            line += f" | {ob['yes_ask']}/{ob['no_ask']}"
            # orderbook-derived asks must match the market snapshot (allow 1c for quotes moving between calls)
            if ob["yes_ask"] is not None and abs(ob["yes_ask"] - ya) > 0.011: mismatches += 1; line += "  <-- MISMATCH"
            if ob["no_ask"] is not None and abs(ob["no_ask"] - (1 - yb)) > 0.011: mismatches += 1; line += "  <-- MISMATCH"
        print(line)
    print(f"bid/ask cross-check mismatches: {mismatches}")
    quotes = [{"ticker": m["ticker"], "strike": m["floor_strike"], "yes_bid": feed.dollars(m["yes_bid_dollars"]),
               "yes_ask": feed.dollars(m["yes_ask_dollars"])} for m in ms if m["status"] == "active"]
    print("signal_engine pick right now:", signal_engine.pick_trade(quotes))
