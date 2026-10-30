#!/usr/bin/env python3
"""
PAPER-ONLY live sports "mispricing" bot for Kalshi game-winner markets.

One run = fetch live games (ESPN, free) + Kalshi prices (public API, no auth),
compute gaps, open/close/settle PAPER positions, log everything.

NO real orders are ever placed. There is no API key, no wallet, no login.
Only public GET requests are made.

Usage:  python3 gap_bot.py            # one check
        python3 gap_bot.py --reset    # wipe paper state (back to $14)
"""
import json, math, os, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")
LOG = os.path.join(HERE, "paper_trades.md")
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
ESPN = "https://site.api.espn.com/apis/site/v2/sports"
CT = ZoneInfo("America/Chicago")
ET = ZoneInfo("America/New_York")

# ---------------- settings (edit freely) ----------------
START_BANKROLL = 14.00
# The desk file is the source of these limits. Old defaults: 8 points of edge, 3 open positions.
# New defaults: 4 points of edge, 12 open positions. Under 12 trades this hour, the timer
# may paper-buy without that edge. The desk daily loss stop still ends a bad paper day.
MAX_OPEN = 12
MIN_GAP = 0.04            # saved edge bar AFTER the taker fee (old bar was 0.08)
MIN_GAP_MODEL = 0.06      # NHL model stays 2 points stricter (old bar was 0.10)
DESK_ROOT = os.path.dirname(HERE)
CLOSE_GAME_BAND = (0.40, 0.60)  # skip if fair prob for home team is in this band
MAX_SPREAD = 0.05         # skip illiquid markets (ask - bid wider than 5c)
PRICE_BOUNDS = (0.05, 0.95)     # don't buy near-certain / near-worthless contracts

def stake_for_gap(gap):
    """$1 default, $2 for big gaps, $3 for huge gaps."""
    if gap >= 0.16: return 3.0
    if gap >= 0.12: return 2.0
    return 1.0

# sport key -> (espn path, kalshi series, fair-value source)
SPORTS = {
    "NFL":   ("football/nfl",              "KXNFLGAME",   "espn"),
    "NCAAF": ("football/college-football", "KXNCAAFGAME", "espn"),
    "NBA":   ("basketball/nba",            "KXNBAGAME",   "espn"),
    "WNBA":  ("basketball/wnba",           "KXWNBAGAME",  "espn"),
    "MLB":   ("baseball/mlb",              "KXMLBGAME",   "espn"),
    "NHL":   ("hockey/nhl",                "KXNHLGAME",   "nhl_model"),
}
# ESPN abbreviation -> Kalshi ticker code, where they differ
ALIAS = {"WSH": "WAS", "GS": "GSW", "UTAH": "UTA", "SA": "SAS", "NO": "NOP", "NY": "NYK"}

def fee(p):
    """Kalshi taker fee per contract: ceil(0.07*P*(1-P)*100)/100."""
    return math.ceil(round(0.07 * p * (1 - p) * 100, 6)) / 100

CACHE = os.path.join(HERE, "quote_cache.json")
CACHE_TTL = 60


def _cache_load():
    try:
        with open(CACHE, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _cache_get(url):
    row = _cache_load().get(url)
    if not isinstance(row, dict):
        return None
    try:
        age = time.time() - float(row.get("at") or 0)
    except (TypeError, ValueError):
        return None
    if age > CACHE_TTL:
        return None
    return row.get("body")


def _cache_put(url, body):
    data = _cache_load()
    data[url] = {"at": time.time(), "body": body}
    if len(data) > 40:
        newest = sorted(data.items(), key=lambda item: float((item[1] or {}).get("at") or 0))[-40:]
        data = dict(newest)
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    os.replace(tmp, CACHE)


def get(url, tries=3):
    """Public GET with a one-minute cache and a retry. A failure stays a failure."""
    hit = _cache_get(url)
    if hit is not None:
        return hit
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (paper)"})
            with urllib.request.urlopen(req, timeout=20) as response:
                body = json.load(response)
            _cache_put(url, body)
            return body
        except Exception:
            if i == tries - 1:
                raise RuntimeError("public GET failed")
            time.sleep(1.5)

def now_ct():
    return datetime.now(CT).strftime("%Y-%m-%d %H:%M:%S CT")

# ---------------- state + log ----------------
def load_state():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {"cash": START_BANKROLL, "open": [], "closed": [], "runs": 0}

def save_state(s):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(s, handle, indent=2)
        handle.flush()
    os.replace(tmp, STATE)

def log(lines):
    if os.path.exists(LOG) and os.path.getsize(LOG) > 256 * 1024:
        with open(LOG, "rb") as handle:
            handle.seek(-128 * 1024, os.SEEK_END)
            tail = handle.read().decode("utf-8", "replace").split("\n", 1)[-1]
        with open(LOG, "w", encoding="utf-8") as handle:
            handle.write("# Paper log capped.\n" + tail)
    new = not os.path.exists(LOG)
    with open(LOG, "a", encoding="utf-8") as handle:
        if new:
            handle.write("# Paper trades & checks (PAPER ONLY - no real money)\n\n")
        for line in lines:
            handle.write(line + "\n")

# ---------------- ESPN ----------------
def league_url(path):
    url = f"{ESPN}/{path}/scoreboard"
    if "college-football" in path:
        url += "?groups=80&limit=300"   # all FBS games, not just top 25
    return url


def league_cached_idle(path):
    """A league with no live games stays cached for a minute, so we do not fetch it again."""
    body = _cache_get(league_url(path))
    if not isinstance(body, dict):
        return False
    for event in body.get("events") or []:
        try:
            if event["status"]["type"]["state"] == "in":
                return False
        except Exception:
            continue
    return True


def espn_games(path):
    d = get(league_url(path))
    out = []
    for e in d.get("events", []):
        c = e["competitions"][0]
        teams = {t["homeAway"]: t for t in c["competitors"]}
        out.append({"id": e["id"], "date": e["date"], "state": e["status"]["type"]["state"],
                    "detail": e["status"]["type"]["shortDetail"], "status": c.get("status", e["status"]),
                    "home": teams["home"], "away": teams["away"]})
    return out

def espn_summary(path, eid):
    return get(f"{ESPN}/{path}/summary?event={eid}")

def espn_home_wp(summary):
    wp = summary.get("winprobability") or []
    if not wp:
        return None
    v = wp[-1].get("homeWinPercentage")
    return float(v) if v is not None else None

def ml_to_prob(ml):
    ml = float(ml)
    return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)

def poisson_pmf(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k) if lam > 0 else (1.0 if k == 0 else 0.0)

def p_home_from_rates(lh, la, lead):
    """P(home wins) given home currently leads by `lead`, remaining goals ~ Poisson(lh), Poisson(la).
    Ties go to OT/shootout, counted as 50/50."""
    ph = [poisson_pmf(k, lh) for k in range(20)]
    pa = [poisson_pmf(k, la) for k in range(20)]
    win = tie = 0.0
    for i in range(20):
        for j in range(20):
            final = lead + i - j
            if final > 0: win += ph[i] * pa[j]
            elif final == 0: tie += ph[i] * pa[j]
    return win + 0.5 * tie

def nhl_model(summary, game):
    """Simple hockey model: goals are Poisson. Team strength is taken from the
    pregame moneyline (ESPN pickcenter) if available, else teams are treated equal."""
    total = 6.0
    share = 0.5
    pc = (summary.get("pickcenter") or [])
    if pc:
        p0 = pc[0]
        try:
            total = float(p0.get("overUnder") or 6.0)
            ph = ml_to_prob(p0["homeTeamOdds"]["moneyLine"]); pa = ml_to_prob(p0["awayTeamOdds"]["moneyLine"])
            target = ph / (ph + pa)   # remove the bookmaker margin
            lo, hi = 0.2, 0.8
            for _ in range(40):
                mid = (lo + hi) / 2
                if p_home_from_rates(total * mid, total * (1 - mid), 0) < target: lo = mid
                else: hi = mid
            share = (lo + hi) / 2
        except Exception:
            pass
    st = game["status"]
    period = int(st.get("period") or 1)
    clock = st.get("clock")
    if clock is None:
        mm, ss = (st.get("displayClock") or "20:00").split(":")
        clock = int(mm) * 60 + float(ss)
    if period <= 3:
        rem_min = (3 - period) * 20 + float(clock) / 60
    else:
        rem_min = 0.0   # OT/shootout: treat as tie-breaker coin flip
    lead = int(game["home"].get("score") or 0) - int(game["away"].get("score") or 0)
    lh = total * share * rem_min / 60
    la = total * (1 - share) * rem_min / 60
    return p_home_from_rates(lh, la, lead)

# ---------------- Kalshi ----------------
def kalshi_markets(series):
    out, cursor = [], None
    while True:
        url = f"{KALSHI}/markets?series_ticker={series}&status=open&limit=1000"
        if cursor: url += f"&cursor={cursor}"
        d = get(url)
        out += d.get("markets", [])
        cursor = d.get("cursor")
        if not cursor or not d.get("markets"):
            return out

def norm(s):
    s = (s or "").lower().replace(".", "").replace("&", "and").strip()
    s = s.replace(" st", " state") if s.endswith(" st") else s
    return " ".join(s.split())

def team_matches(market, team):
    t = team["team"]
    code = market["ticker"].rsplit("-", 1)[-1]
    abbr = t.get("abbreviation", "")
    if code == abbr or code == ALIAS.get(abbr):
        return True
    sub = norm(market.get("yes_sub_title"))
    names = {norm(t.get("location")), norm(t.get("displayName")), norm(t.get("shortDisplayName")),
             norm(f'{t.get("location","")} {t.get("name","")[:1]}')}
    return sub in names

def match_event(game, markets):
    """Return {'home': market, 'away': market} for this ESPN game, or None."""
    d = datetime.fromisoformat(game["date"].replace("Z", "+00:00")).astimezone(ET)
    dates = {d.strftime("%y%b%d").upper()}
    by_event = {}
    for m in markets:
        part = m["event_ticker"].split("-", 1)[1] if "-" in m["event_ticker"] else ""
        if part[:7] in dates:
            by_event.setdefault(m["event_ticker"], []).append(m)
    hits = []
    for ev, ms in by_event.items():
        if len(ms) != 2: continue
        h = [m for m in ms if team_matches(m, game["home"])]
        a = [m for m in ms if team_matches(m, game["away"])]
        if len(h) == 1 and len(a) == 1 and h[0] is not a[0]:
            hits.append({"home": h[0], "away": a[0]})
    return hits[0] if len(hits) == 1 else None

def px(m, k):
    v = m.get(k)
    return float(v) if v not in (None, "") else None

# ---------------- main ----------------
def _desk():
    if DESK_ROOT not in sys.path:
        sys.path.insert(0, DESK_ROOT)
    import pimp_desk
    return pimp_desk


def _paper_limits():
    """Desk limits for this check. Paper only. A missing desk falls back to the new defaults."""
    try:
        desk = _desk()
        cfg = desk.load_settings(DESK_ROOT)
        pace = desk.hour_pace(DESK_ROOT, cfg=cfg)
        return desk, cfg, pace
    except Exception:
        return None, {
            "min_edge": MIN_GAP,
            "max_open_positions": MAX_OPEN,
            "daily_loss_stop": 150.0,
            "pace_target": 12,
            "pace_min": 6,
        }, {"edge": 0.0, "loosened": True, "count": 0, "target": 12}


def _card_line(summary_out):
    trades = summary_out.get("trades") or []
    skips = summary_out.get("skips") or []
    if skips:
        return "CARD: " + str(skips[0])
    if trades:
        word = "trade" if len(trades) == 1 else "trades"
        return f"CARD: Paper buy. {len(trades)} paper {word} this check."
    if summary_out.get("live_games") == 0:
        return "CARD: No live games, so this check bought nothing."
    return "CARD: No paper buy."


def run():
    existed = os.path.exists(STATE)
    s = load_state()
    if not existed:
        save_state(s)
    desk, cfg, pace = _paper_limits()
    force = bool(pace.get("loosened"))
    need_edge = float(pace.get("edge") if pace.get("edge") is not None else cfg.get("min_edge") or MIN_GAP)
    max_open = int(cfg.get("max_open_positions") or MAX_OPEN)
    room = max(0, int(pace.get("target") or 12) - int(pace.get("count") or 0))
    opened_now = 0
    day = datetime.now(CT).strftime("%Y-%m-%d")
    today_pnl = 0.0
    for pos in s.get("closed") or []:
        if str(pos.get("closed") or "").startswith(day):
            try:
                today_pnl += float(pos.get("pnl") or 0)
            except (TypeError, ValueError):
                pass
    entries_off = ""
    stop = float(cfg.get("daily_loss_stop") or 150)
    if today_pnl <= -stop:
        entries_off = f"Daily loss stop is hit (${abs(today_pnl):.2f} against ${stop:.2f})."
    before_book = json.dumps(
        {"cash": s.get("cash"), "open": s.get("open"), "closed": s.get("closed")},
        sort_keys=True, default=str)
    s["runs"] += 1
    ts = now_ct()
    lines = [f"\n## Check {ts} (run #{s['runs']})", "",
             "| time | league | game | score/status | fair (home) | Kalshi home bid/ask | Kalshi away bid/ask | best gap after fee | action |",
             "|---|---|---|---|---|---|---|---|---|"]
    summary_out = {"time": ts, "live_games": 0, "matched": 0, "leagues": {}, "trades": [], "closes": [], "skips": []}
    open_by_game = {p["game_key"]: p for p in s["open"]}
    live_info = {}  # game_key -> dict for exits

    for league, (path, series, src) in SPORTS.items():
        if league_cached_idle(path):
            summary_out["leagues"][league] = "no live games"
            continue
        try:
            games = espn_games(path)
        except Exception:
            lines.append(f"| {ts} | {league} | - | data error: ESPN down | | | | | data error |")
            summary_out.setdefault("data_errors", []).append({"league": league, "source": "ESPN", "error": "failed"})
            continue
        relevant = [g for g in games if g["state"] == "in" or f"{league}:{g['id']}" in open_by_game]
        if not relevant:
            summary_out["leagues"][league] = "no live games"; continue
        try:
            markets = kalshi_markets(series)
        except Exception:
            lines.append(f"| {ts} | {league} | - | data error: Kalshi down | | | | | data error |")
            summary_out.setdefault("data_errors", []).append({"league": league, "source": "Kalshi", "error": "failed"})
            continue
        summary_out["leagues"][league] = f"{sum(g['state']=='in' for g in relevant)} live, series {series} ({len(markets)} open mkts)"
        for g in relevant:
            key = f"{league}:{g['id']}"
            name = f"{g['away']['team']['abbreviation']} @ {g['home']['team']['abbreviation']}"
            score = f"{g['away'].get('score','?')}-{g['home'].get('score','?')} ({g['detail']})"
            if g["state"] == "in":
                summary_out["live_games"] += 1
            if g["state"] == "post":
                live_info[key] = {"final": True, "game": g, "name": name, "score": score}
                continue
            pair = match_event(g, markets)
            if not pair:
                lines.append(f"| {ts} | {league} | {name} | {score} | | | | | no Kalshi match - skip |"); continue
            summary_out["matched"] += 1
            try:
                summ = espn_summary(path, g["id"])
                fair_home = espn_home_wp(summ) if src == "espn" else nhl_model(summ, g)
            except Exception as e:
                fair_home = None
            hb, ha = px(pair["home"], "yes_bid_dollars"), px(pair["home"], "yes_ask_dollars")
            ab, aa = px(pair["away"], "yes_bid_dollars"), px(pair["away"], "yes_ask_dollars")
            row = f"| {ts} | {league} | {name} | {score} | " + \
                  (f"{fair_home:.1%}" + (" (model)" if src != "espn" else " (ESPN)") if fair_home is not None else "n/a") + \
                  f" | {hb}/{ha} | {ab}/{aa} | "
            live_info[key] = {"final": False, "game": g, "pair": pair, "fair_home": fair_home, "name": name, "score": score}
            if fair_home is None:
                lines.append(row + " | no fair prob - skip |"); continue
            # best side
            cands = []
            for side, m, fair, bid, ask in (("home", pair["home"], fair_home, hb, ha), ("away", pair["away"], 1 - fair_home, ab, aa)):
                if ask is None or bid is None: continue
                cands.append((fair - ask - fee(ask), side, m, fair, bid, ask))
            if not cands:
                lines.append(row + " | no prices - skip |"); continue
            gap, side, m, fair, bid, ask = max(cands, key=lambda c: c[0])
            gtxt = f"{gap*100:+.1f} pts on {m.get('yes_sub_title')} (fair {fair:.1%} vs ask {ask:.2f})"
            need = need_edge if src == "espn" else round(need_edge + 0.02, 4)
            reason = None
            if entries_off:
                reason = entries_off
            elif key in open_by_game:
                reason = "already holding this game"
            elif (not force) and CLOSE_GAME_BAND[0] <= fair_home <= CLOSE_GAME_BAND[1]:
                reason = "close game - skip"
            elif (not force) and gap < need:
                reason = f"gap < {need*100:.0f} - no trade"
            elif ask - bid > MAX_SPREAD:
                reason = "spread too wide - skip"
            elif not (PRICE_BOUNDS[0] <= ask <= PRICE_BOUNDS[1]):
                reason = "price too extreme - skip"
            elif len(s["open"]) >= max_open:
                reason = "max open positions"
            elif force and opened_now >= room:
                reason = "This hour already has 12 paper trades, so the timer is not adding another."
            elif desk is not None:
                skip = desk.learning_skip(desk.load_learning(DESK_ROOT), league, desk.prob_bucket(fair))
                if skip:
                    reason = skip
                    summary_out["skips"].append(skip)
            if reason:
                lines.append(row + gtxt + f" | {reason} |"); continue
            stake = stake_for_gap(gap)
            per = ask + fee(ask)
            n = int(stake // per)
            if n < 1 or n * per > s["cash"] + 1e-9:
                lines.append(row + gtxt + " | not enough paper cash |"); continue
            cost = round(n * per, 2)
            s["cash"] = round(s["cash"] - cost, 2)
            max_payout = round(n * 1.0, 2)
            reward = round(max_payout - cost, 2)
            ratio = round(reward / cost, 4) if cost else None
            if force and gap < float(cfg.get("min_edge") or MIN_GAP):
                why = (
                    f"Paper buy. This hour had {int(pace.get('count') or 0)} paper trades, "
                    f"under {int(pace.get('target') or 12)}, so the timer took this side "
                    f"without waiting for the strict edge. Fair versus ask was {gap * 100:.1f} points after the fee."
                )
            else:
                why = f"Paper buy. The fair price beat the ask by {gap * 100:.1f} points after the fee."
            pos = {"game_key": key, "league": league, "game": name, "ticker": m["ticker"], "team": m.get("yes_sub_title"),
                   "side": side, "contracts": n, "entry_price": ask, "bid": bid, "ask": ask, "entry_fee": fee(ask),
                   "fee": fee(ask), "cost": cost, "risk": cost, "reward": reward, "risk_reward": ratio,
                   "max_payout": max_payout, "why": why,
                   "fair_at_entry": round(fair, 4), "gap_at_entry": round(gap, 4),
                   "opened": ts, "score_at_entry": score, "espn_id": g["id"], "espn_path": path,
                   "price_source": f"{KALSHI}/markets?series_ticker={series}",
                   "price_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "fill_id": f"{m['ticker']}|{ts}"}
            opened_now += 1
            s["open"].append(pos); open_by_game[key] = pos
            lines.append(row + gtxt + f" | **PAPER BUY** {n} YES {m.get('yes_sub_title')} @ {ask:.2f} (+fee {fee(ask):.2f}) = ${cost:.2f} |")
            summary_out["trades"].append(f"BUY {n}x {m['ticker']} @ {ask:.2f} gap {gap*100:.1f}")

    # ---- exits / settlement ----
    still = []
    for p in s["open"]:
        info = live_info.get(p["game_key"])
        if info is None:
            # game not on scoreboard any more (next day) -> check summary directly
            try:
                summ = espn_summary(p["espn_path"], p["espn_id"])
                comp = summ["header"]["competitions"][0]
                if comp["status"]["type"]["state"] == "post":
                    info = {"final": True, "game": {"home": next(c for c in comp["competitors"] if c["homeAway"] == "home"),
                                                    "away": next(c for c in comp["competitors"] if c["homeAway"] == "away")},
                            "name": p["game"], "score": comp["status"]["type"].get("shortDetail", "Final")}
            except Exception:
                pass
        if info and info["final"]:
            g = info["game"]
            hs, as_ = int(g["home"].get("score") or 0), int(g["away"].get("score") or 0)
            if hs == as_:
                still.append(p); continue   # tie/unclear -> wait for Kalshi settlement
            winner = "home" if hs > as_ else "away"
            payout = p["contracts"] * 1.0 if winner == p["side"] else 0.0
            pnl = round(payout - p["cost"], 2)
            s["cash"] = round(s["cash"] + payout, 2)
            p.update({"closed": ts, "exit": "settled", "payout": payout, "pnl": pnl, "final_score": f"{as_}-{hs}"})
            s["closed"].append(p)
            if desk is not None:
                desk.record_learning(DESK_ROOT, {
                    "result": "hit" if pnl > 0 else "miss",
                    "market": p.get("league") or "",
                    "bucket": desk.prob_bucket(p.get("fair_at_entry")),
                    "stake": p.get("risk") if p.get("risk") is not None else p.get("cost"),
                    "fill_id": p.get("fill_id") or "",
                    "at": ts,
                })
            lines.append(f"| {ts} | {p['league']} | {p['game']} | FINAL {as_}-{hs} | | | | | **PAPER SETTLE** {p['team']}: {'WON' if payout else 'LOST'} payout ${payout:.2f}, P&L ${pnl:+.2f} |")
            summary_out["closes"].append(f"SETTLE {p['ticker']} pnl {pnl:+.2f}")
            continue
        if info and info.get("fair_home") is not None:
            m = info["pair"][p["side"]]
            fair = info["fair_home"] if p["side"] == "home" else 1 - info["fair_home"]
            bid = px(m, "yes_bid_dollars")
            if bid is not None and bid > 0 and bid - fee(bid) >= fair:
                proceeds = round(p["contracts"] * (bid - fee(bid)), 2)
                pnl = round(proceeds - p["cost"], 2)
                s["cash"] = round(s["cash"] + proceeds, 2)
                p.update({"closed": ts, "exit": "gap closed - sold at bid", "exit_price": bid, "payout": proceeds,
                          "pnl": pnl, "fair_at_exit": round(fair, 4)})
                s["closed"].append(p)
                if desk is not None:
                    desk.record_learning(DESK_ROOT, {
                        "result": "hit" if pnl > 0 else "miss",
                        "market": p.get("league") or "",
                        "bucket": desk.prob_bucket(p.get("fair_at_entry")),
                        "stake": p.get("risk") if p.get("risk") is not None else p.get("cost"),
                        "fill_id": p.get("fill_id") or "",
                        "at": ts,
                    })
                lines.append(f"| {ts} | {p['league']} | {p['game']} | {info['score']} | {fair:.1%} ({p['team']}) | | | | **PAPER SELL** {p['contracts']} @ bid {bid:.2f} (gap closed), P&L ${pnl:+.2f} |")
                summary_out["closes"].append(f"SELL {p['ticker']} pnl {pnl:+.2f}")
                continue
        still.append(p)
    s["open"] = still

    equity_open = sum(p["cost"] for p in s["open"])
    realized = round(sum(p["pnl"] for p in s["closed"]), 2)
    lines.append("")
    lines.append(f"Paper cash ${s['cash']:.2f} | open positions {len(s['open'])} (cost ${equity_open:.2f}) | realized P&L ${realized:+.2f}")
    if summary_out["live_games"] == 0:
        lines.append("No live games found this check (see rows above for any data errors).")
    after_book = json.dumps(
        {"cash": s.get("cash"), "open": s.get("open"), "closed": s.get("closed")},
        sort_keys=True, default=str)
    summary_out.update({"cash": s["cash"], "open": [f"{p['contracts']}x {p['ticker']} @ {p['entry_price']}" for p in s["open"]], "realized_pnl": realized})
    print(_card_line(summary_out))
    if before_book == after_book:
        print(json.dumps(summary_out, indent=2))
        return
    log(lines)
    save_state(s)
    print(json.dumps(summary_out, indent=2))

if __name__ == "__main__":
    if "--reset" in sys.argv:
        for f in (STATE, LOG):
            if os.path.exists(f): os.remove(f)
        print("Paper state reset to $%.2f" % START_BANKROLL); sys.exit()
    run()
