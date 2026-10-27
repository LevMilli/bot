"""
signal_engine.py - decides WHICH contract (if any) to buy. Pure logic, no network.

Strategy Version 1 rule (from Strategy.md)
------------------------------------------
At the entry time, look at every contract in the event and BOTH of its sides:
  * the YES side costs its yes_ask
  * the NO  side costs its no_ask = 1 - yes_bid
Keep only sides whose ask is between 80c and 90c (inclusive).
Buy the HIGHEST-priced one of those (closest to 90c = market thinks it's the
most likely to win while still being inside the band).
If nothing is in the band, there is no trade today.

Tie-break (two sides at the same price): prefer the tighter bid/ask spread, then
YES before NO, then the ticker name, so the choice is always repeatable.
"""


def candidate_sides(quotes, band_min=0.80, band_max=0.90):
    """quotes: list of dicts {ticker, strike, yes_bid, yes_ask}.
    Returns every buyable side whose ask is inside [band_min, band_max]."""
    out = []
    eps = 1e-9  # protects against float rounding like 0.8999999
    for q in quotes:
        yb, ya = q.get("yes_bid"), q.get("yes_ask")
        # YES side: you pay the yes ask. A 0 or 1 ask means no real offer.
        if ya is not None and 0 < ya < 1 and band_min - eps <= ya <= band_max + eps:
            spread = (ya - yb) if yb is not None else 1.0
            out.append({"ticker": q["ticker"], "strike": q.get("strike"), "side": "yes",
                        "ask": round(ya, 4), "spread": round(spread, 4)})
        # NO side: you pay 1 - yes bid. A yes bid of 0 means nobody to sell to you.
        if yb is not None and 0 < yb < 1:
            no_ask = round(1 - yb, 4)
            if band_min - eps <= no_ask <= band_max + eps:
                spread = (ya - yb) if ya is not None else 1.0
                out.append({"ticker": q["ticker"], "strike": q.get("strike"), "side": "no",
                            "ask": no_ask, "spread": round(spread, 4)})
    return out


def pick_trade(quotes, band_min=0.80, band_max=0.90):
    """Return the single side to buy, or None if nothing is in the band."""
    c = candidate_sides(quotes, band_min, band_max)
    if not c:
        return None
    c.sort(key=lambda s: (-s["ask"], s["spread"], s["side"] != "yes", s["ticker"]))
    return c[0]


if __name__ == "__main__":
    # Self-test with made-up quotes (not market data) to prove the rule works.
    demo = [
        {"ticker": "A", "strike": 100, "yes_bid": 0.93, "yes_ask": 0.95},  # yes 95 (too high), no 7 (too low)
        {"ticker": "B", "strike": 105, "yes_bid": 0.86, "yes_ask": 0.88},  # yes 88 in band
        {"ticker": "C", "strike": 110, "yes_bid": 0.50, "yes_ask": 0.53},  # nothing
        {"ticker": "D", "strike": 115, "yes_bid": 0.11, "yes_ask": 0.14},  # no side = 89 in band  <- highest
        {"ticker": "E", "strike": 120, "yes_bid": 0.00, "yes_ask": 0.03},  # yes_bid 0 -> no NO offer
    ]
    p = pick_trade(demo)
    assert p["ticker"] == "D" and p["side"] == "no" and abs(p["ask"] - 0.89) < 1e-9, p
    assert pick_trade([{"ticker": "X", "yes_bid": 0.4, "yes_ask": 0.45}]) is None
    assert len(candidate_sides(demo)) == 2
    print("signal_engine self-test OK ->", p)
