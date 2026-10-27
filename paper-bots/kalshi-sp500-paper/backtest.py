"""
backtest.py - replays Strategy Version 1 (and the HOURLY variant) on real,
already-settled Kalshi KXINXU markets using only Kalshi's public API.

Two phases (both cached, so re-running is cheap):
  python3 backtest.py fetch daily     # download quotes at 12:30 PM CT for each 3 PM CT event
  python3 backtest.py fetch hourly    # download quotes 30 min before every hourly settle
  python3 backtest.py report          # compute stats -> Backtest_Report.md

HOW THE ENTRY PRICE IS DERIVED (important, read this)
----------------------------------------------------
Kalshi's candlestick endpoint (period_interval=1 -> 1-minute bars) gives, for each
minute in which anything changed, the CLOSING best yes-bid and yes-ask of that
minute. The quote standing at the entry time T (e.g. 12:30:00 CT) is the close
of the LAST 1-minute bar whose end time is <= T (data_feed.quote_at). We look
back up to 3 hours; minutes with no bar mean "quote unchanged".
  * YES ask = that bar's yes_ask close;  NO ask = 1 - that bar's yes_bid close.
  * Nothing after T is used for the decision -> no lookahead in the signal.
  * The settled result comes from Kalshi's official 'result' field.

DOWNLOAD SHORT-CUT (and why it does not leak the future into the decision)
-------------------------------------------------------------------------
Each event has 30-400 contracts; downloading every one for ~3,000 events is too
slow, so we first download the contracts whose strike is near the settled
index value, then KEEP WIDENING until the edges prove nothing further out can be
in the 80-90c band: the lowest fetched strike must have YES ask > 90c and the
highest fetched strike must have YES bid < 10c (=> NO ask > 90c). Because
"S&P >= strike" prices fall as the strike rises, every contract beyond those
edges is outside the band. The settled value only decides the download ORDER;
the trade decision only uses quotes at time T. (Residual risk: if quotes were
not monotonic across strikes a far contract could be missed; we log any edge
that fails the test instead of guessing.)

ASSUMPTIONS / LIMITS
  * Fill = full size at the displayed ask (we cannot see historic depth; our size
    is <= 31 contracts, and Market_Notes found ~100k at the best quote, but
    depth at old timestamps is UNVERIFIED).
  * Slippage sensitivity: +1c on every fill (ask+0.01, fee recomputed).
  * Fees: 0.07*C*P*(1-P) rounded up to the cent (taker), per Strategy.md.
"""
import sys, os, json, math, datetime as dt, concurrent.futures as cf, threading, statistics
from zoneinfo import ZoneInfo
import data_feed as feed
import signal_engine, risk_manager, paper_sim

CT = ZoneInfo("America/Chicago")
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "raw", "bt_cache")
os.makedirs(CACHE, exist_ok=True)
CUTOFF = dt.datetime(2026, 8, 27, tzinfo=dt.timezone.utc)  # /historical/cutoff market_settled_ts (checked Oct 26 2026)
CFG = risk_manager.CFG
LOG_LOCK = threading.Lock()


def log(msg):
    with LOG_LOCK:
        print(msg, flush=True)


# ------------------------------------------------------------------ download
def candles(ticker, close_iso, t0, t1):
    """1-minute candles for one market from the right endpoint (live vs historical)."""
    close = dt.datetime.fromisoformat(close_iso.replace("Z", "+00:00"))
    if close < CUTOFF:
        d = feed.get_json(f"/historical/markets/{ticker}/candlesticks?start_ts={t0}&end_ts={t1}&period_interval=1")
    else:
        d = feed.get_json(f"/series/KXINXU/markets/{ticker}/candlesticks?start_ts={t0}&end_ts={t1}&period_interval=1")
    return [feed._norm_candle(c) for c in d.get("candlesticks", [])]


def strike_of(m):
    return m.get("floor_strike") if m.get("floor_strike") is not None else m.get("cap_strike")


def fetch_event(event_ticker, entry_ts, mode):
    """Download (or load from cache) the quotes at entry_ts for one event."""
    path = os.path.join(CACHE, f"{event_ticker}_{entry_ts}.json")
    if os.path.exists(path):
        return json.load(open(path))
    ms = feed.get_event_markets(event_ticker)
    rec = {"event": event_ticker, "entry_ts": entry_ts, "n_markets": len(ms), "quotes": {}, "edge_ok": None, "note": ""}
    ms = [m for m in ms if strike_of(m) is not None and m.get("strike_type") in ("greater", "greater_or_equal")]
    if not ms:
        rec["note"] = "no usable markets returned by API"
        json.dump(rec, open(path, "w")); return rec
    ms.sort(key=strike_of)
    meta = {m["ticker"]: {"strike": strike_of(m), "result": m.get("result"), "close_time": m["close_time"],
                          "type": m["strike_type"]} for m in ms}
    rec["meta"] = meta
    try:
        settle_val = float(ms[0].get("expiration_value") or "nan")
    except ValueError:
        settle_val = float("nan")
    strikes = [strike_of(m) for m in ms]
    t0 = entry_ts - 3 * 3600
    # --- choose the initial download set
    if math.isnan(settle_val):
        lo, hi = 0, len(ms) - 1
    else:
        width = 100 if mode == "daily" else 40
        idx = [i for i, s in enumerate(strikes) if abs(s - settle_val) <= width]
        if not idx:
            near = min(range(len(ms)), key=lambda i: abs(strikes[i] - settle_val))
            idx = [near]
        lo, hi = min(idx), max(idx)

    def get_range(a, b):
        need = [ms[i] for i in range(a, b + 1) if ms[i]["ticker"] not in rec["quotes"]]
        live = [m for m in need if dt.datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")) >= CUTOFF]
        hist = [m for m in need if m not in live]
        if live:
            got = feed.get_candles_batch([m["ticker"] for m in live], t0, entry_ts, 1)
            for m in live:
                yb, ya, ts = feed.quote_at(got.get(m["ticker"], []), entry_ts)
                rec["quotes"][m["ticker"]] = {"yes_bid": yb, "yes_ask": ya, "ts": ts}
        for m in hist:
            yb, ya, ts = feed.quote_at(candles(m["ticker"], m["close_time"], t0, entry_ts), entry_ts)
            rec["quotes"][m["ticker"]] = {"yes_bid": yb, "yes_ask": ya, "ts": ts}

    get_range(lo, hi)
    # --- widen until the edges prove completeness (or we run out of strikes)
    for _ in range(60):
        q_lo = rec["quotes"][ms[lo]["ticker"]]; q_hi = rec["quotes"][ms[hi]["ticker"]]
        lo_ok = lo == 0 or (q_lo["yes_ask"] is not None and q_lo["yes_ask"] > 0.90)
        hi_ok = hi == len(ms) - 1 or (q_hi["yes_bid"] is not None and q_hi["yes_bid"] < 0.10)
        if lo_ok and hi_ok:
            break
        if not lo_ok:
            nlo = max(0, lo - 8); get_range(nlo, lo - 1); lo = nlo
        if not hi_ok:
            nhi = min(len(ms) - 1, hi + 8); get_range(hi + 1, nhi); hi = nhi
    q_lo = rec["quotes"][ms[lo]["ticker"]]; q_hi = rec["quotes"][ms[hi]["ticker"]]
    rec["edge_ok"] = bool((lo == 0 or (q_lo["yes_ask"] or 0) > 0.90) and (hi == len(ms) - 1 or (q_hi["yes_bid"] if q_hi["yes_bid"] is not None else 1) < 0.10))
    rec["fetched"] = hi - lo + 1
    json.dump(rec, open(path, "w"))
    return rec


def build_jobs(mode):
    """List (event_ticker, settle_dt_ct, entry_dt_ct) for every settled KXINXU event we will test."""
    events = feed.list_events("KXINXU")
    jobs = []
    now = dt.datetime.now(CT)
    for e in events:
        if not e["event_ticker"].startswith("KXINXU-") or not e.get("strike_date"):
            continue
        if e["event_ticker"].endswith("B"):
            continue  # Nov 20 2025 duplicate listing; the normal ticker is used
        s = feed.event_settle_time_ct(e)
        if s > now - dt.timedelta(hours=1):
            continue  # not settled yet
        if mode == "daily":
            if (s.hour, s.minute) != (15, 0):
                continue
            entry = s.replace(hour=12, minute=30)
        else:
            if s.minute != 0 or not (9 <= s.hour <= 15):
                continue
            entry = s - dt.timedelta(minutes=30)
        jobs.append((e["event_ticker"], s, entry))
    jobs.sort(key=lambda j: j[1])
    return jobs


def fetch(mode, workers=12):
    jobs = build_jobs(mode)
    log(f"{mode}: {len(jobs)} events from {jobs[0][1].date()} to {jobs[-1][1].date()}")
    done = [0]

    def work(j):
        r = fetch_event(j[0], int(j[2].timestamp()), mode)
        done[0] += 1
        if done[0] % 100 == 0:
            log(f"  {mode}: {done[0]}/{len(jobs)} done ({dt.datetime.now(CT):%H:%M:%S})")
        return r
    with cf.ThreadPoolExecutor(workers) as ex:
        list(ex.map(work, jobs))
    log(f"{mode}: fetch complete")


# ------------------------------------------------------------------ simulate
def decide(rec, slip=0.0):
    """Apply signal_engine to the cached quotes. Returns trade dict or None."""
    quotes = [{"ticker": t, "strike": rec["meta"][t]["strike"], **q} for t, q in rec["quotes"].items()]
    pick = signal_engine.pick_trade(quotes, CFG["band_min_ask"], CFG["band_max_ask"])
    if not pick:
        return None
    result = rec["meta"][pick["ticker"]]["result"]
    if result not in ("yes", "no"):
        return {"void": True, **pick}
    fill = round(pick["ask"] + slip, 4)
    n = risk_manager.stake_contracts(fill)
    fee = paper_sim.taker_fee(n, fill)
    won = (result == pick["side"])
    pnl = paper_sim.trade_pnl(pick["side"], won, n, fill, fee)
    return {**pick, "fill": fill, "contracts": n, "fee": fee, "won": won, "pnl": pnl, "result": result}


def simulate(mode, slip=0.0):
    """Walk every event in time order, apply skip days + risk rules, collect trades."""
    rows = []
    for ev, s, entry in build_jobs(mode):
        path = os.path.join(CACHE, f"{ev}_{int(entry.timestamp())}.json")
        if not os.path.exists(path):
            rows.append({"event": ev, "settle": s, "status": "missing_data"}); continue
        rec = json.load(open(path))
        day = s.date()
        skip = risk_manager.news_skip_reason(day)
        if skip:
            rows.append({"event": ev, "settle": s, "status": "skip_news", "why": skip}); continue
        if not rec.get("quotes"):
            rows.append({"event": ev, "settle": s, "status": "missing_data", "why": rec.get("note")}); continue
        t = decide(rec, slip)
        if t is None:
            rows.append({"event": ev, "settle": s, "status": "skip_no_band"}); continue
        if t.get("void"):
            rows.append({"event": ev, "settle": s, "status": "void_result"}); continue
        rows.append({"event": ev, "settle": s, "status": "trade", "edge_ok": rec.get("edge_ok"), **t})
    # risk overlay: $50 daily loss limit (matters only for the hourly variant: 1 trade/day can lose <= $25.x)
    by_day_pnl = {}
    for r in rows:
        if r["status"] != "trade":
            continue
        d = r["settle"].date()
        if by_day_pnl.get(d, 0) <= -CFG["daily_loss_limit"]:
            r["status"] = "skip_daily_loss_limit"; continue
        by_day_pnl[d] = by_day_pnl.get(d, 0) + r["pnl"]
    return rows


def stats(rows, start_bank=500.0):
    tr = [r for r in rows if r["status"] == "trade"]
    out = {"events": len(rows), "trades": len(tr)}
    for k in ("skip_news", "skip_no_band", "missing_data", "void_result", "skip_daily_loss_limit"):
        out[k] = sum(1 for r in rows if r["status"] == k)
    if not tr:
        return out
    wins = [r["pnl"] for r in tr if r["won"]]; losses = [r["pnl"] for r in tr if not r["won"]]
    eq, peak, mdd, bank_min = start_bank, start_bank, 0.0, start_bank
    streak = worst = 0; kill_hit = None
    for r in tr:
        eq += r["pnl"]; peak = max(peak, eq); mdd = max(mdd, peak - eq); bank_min = min(bank_min, eq)
        if kill_hit is None and eq <= CFG["kill_switch_bankroll"]:
            kill_hit = str(r["settle"].date())
        streak = streak + 1 if not r["won"] else 0; worst = max(worst, streak)
    aw = statistics.mean(wins) if wins else 0.0; al = statistics.mean(losses) if losses else 0.0
    out.update({
        "win_rate": len(wins) / len(tr), "avg_win": aw, "avg_loss": al,
        "total_pnl": sum(r["pnl"] for r in tr), "expectancy": sum(r["pnl"] for r in tr) / len(tr),
        "max_drawdown": mdd, "risk_reward": (aw / abs(al)) if al else float("inf"),
        "breakeven_win_rate": (abs(al) / (aw + abs(al))) if al else 0.0,
        "worst_losing_streak": worst, "avg_entry": statistics.mean(r["fill"] for r in tr),
        "total_fees": sum(r["fee"] for r in tr), "end_bankroll": eq, "min_bankroll": bank_min,
        "kill_switch_date": kill_hit, "edge_check_failed": sum(1 for r in tr if r.get("edge_ok") is False),
        "first": str(tr[0]["settle"].date()), "last": str(tr[-1]["settle"].date()),
    })
    return out


def split(rows, frac=0.70):
    """Chronological split by trading DAY (so an hourly day is never cut in half)."""
    days = sorted({r["settle"].date() for r in rows})
    cut = days[int(len(days) * frac)]
    return [r for r in rows if r["settle"].date() < cut], [r for r in rows if r["settle"].date() >= cut], cut


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "fetch":
        fetch(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 12)
    elif len(sys.argv) >= 2 and sys.argv[1] == "report":
        import backtest_report
        backtest_report.main()
    else:
        print(__doc__)
