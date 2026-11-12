#!/usr/bin/env python3
"""
PAPER-ONLY live sports "mispricing" bot for Kalshi game-winner markets.

One run = fetch live games (ESPN, free) + Kalshi prices (public API, no auth),
compute gaps, open/close/settle PAPER positions, log everything.

NO real orders are ever placed. There is no API key, no wallet, no login.
Only public GET requests are made.

Usage:  python3 gap_bot.py            # one check
        python3 gap_bot.py --reset    # wipe paper state (back to $100)
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
START_BANKROLL = 100.00
OLD_BANKROLL = 14.00
# The desk file is the source of these limits. Old defaults: 8 points of edge, 3 open positions.
# New defaults: 4 points of edge, 12 open positions. A paper buy needs that edge after the fee.
# The hourly count does not waive it. The desk daily loss stop still ends a bad paper day.
MAX_OPEN = 12
MIN_GAP = 0.06            # fee-aware edge floor AFTER the taker fee (desk venue can raise)
MIN_GAP_MODEL = 0.08      # NHL model stays 2 points stricter
# Dual lanes on one tower: accurate (high fair) + speed (lower fair, extra edge).
MIN_FAIR_ACCURATE = 0.80
MIN_FAIR_SPEED = 0.72
MIN_GAP_SPEED_EXTRA = 0.02   # speed lane needs +2¢ edge after fee vs desk venue
MIN_FAIR_PROB = MIN_FAIR_ACCURATE  # legacy name used in logs
# Extra paper size only after this tower's own settles are actually accurate.
# Desk play-big starts at 80%. Sports waits for 85%, n≥30, Wilson lower ≥70%,
# and a non-negative average. A short hot streak does not get the extra dollars.
SPORTS_ACCURACY_HIT = 0.85
SPORTS_ACCURACY_MIN_N = 30
SPORTS_ACCURACY_CI = 0.70
SPORTS_ACCURACY_MULT = 1.50
DESK_PLAY_BIG_MULT = 1.75
DESK_ROOT = os.path.dirname(HERE)
CLOSE_GAME_BAND = (0.40, 0.60)  # skip if fair prob for home team is in this band
MAX_SPREAD = 0.05         # skip illiquid markets (ask - bid wider than 5c)
PRICE_BOUNDS = (0.05, 0.92)     # avoid near-worthless / near-locked contracts
PREGAME_WINDOW_MIN = 180  # tip-soon window (3h) so Monday/weekday books fill earlier
TIP_ALARM_WINDOWS_MIN = (15, 5)  # force-priority refresh bands before tip
MAX_BUYS_PER_CHECK = 4    # more than one paper fill per timer tick when risk allows
# E1 #112 — mid-game scale-out when fair moves +8¢ in our favor (fee still on sell).
SCALE_OUT_FAIR_MOVE = 0.08
SCALE_OUT_FRAC = 0.50


def fair_lane_floors(league: str = "", root: str | None = None) -> dict:
    """Accurate/speed fair floors with staff soft-p relax applied (never edge/fee)."""
    fair_floor = float(MIN_FAIR_PROB)
    speed_floor = float(MIN_FAIR_SPEED)
    try:
        root_s = root if root is not None else DESK_ROOT
        if root_s not in sys.path:
            sys.path.insert(0, root_s)
        import desk_top25
        fair_floor = float(desk_top25.league_fair_floor(league))
        speed_floor = float(desk_top25.league_speed_floor(league))
    except Exception:
        fair_floor = float(MIN_FAIR_PROB)
        speed_floor = float(MIN_FAIR_SPEED)
    p_relax = 0.0
    try:
        root_s = root if root is not None else DESK_ROOT
        if root_s not in sys.path:
            sys.path.insert(0, root_s)
        import desk_roi_plan as _nm_relax
        relax = _nm_relax.effective_near_miss_relax(root_s)
        p_relax = float(relax.get("p_relax") or 0.0)
    except Exception:
        p_relax = 0.0
    accurate = max(0.50, max(float(MIN_FAIR_ACCURATE), fair_floor) - p_relax)
    speed = max(0.50, max(float(speed_floor), float(MIN_FAIR_SPEED)) - p_relax)
    return {
        "accurate_floor": accurate,
        "speed_floor": speed,
        "p_relax": p_relax,
        "fair_floor": fair_floor,
        "paper_only": True,
        "fee_floors_locked": True,
    }


def sports_accuracy_ready(perf: dict | None) -> bool:
    """True when this tower's settles earned the extra size.

    Point hit ≥ 85%, at least 30 closes, Wilson lower bound ≥ 70%, and
    expectancy ≥ 0. Fee floors are not involved.
    """
    perf = perf or {}
    try:
        n = int(perf.get("n") or 0)
        hit = float(perf.get("hit_rate"))
        ci = float(perf.get("hit_ci_low"))
        ev = float(perf.get("expectancy"))
    except (TypeError, ValueError):
        return False
    return (
        n >= int(SPORTS_ACCURACY_MIN_N)
        and hit + 1e-12 >= float(SPORTS_ACCURACY_HIT)
        and ci + 1e-12 >= float(SPORTS_ACCURACY_CI)
        and ev + 1e-12 >= 0.0
    )


def apply_sports_accuracy_size(stake, plan: dict | None) -> float:
    """Strip the desk's 80% size-up. Add 1.50× only after the 85% gate."""
    try:
        dollars = float(stake)
    except (TypeError, ValueError):
        return 0.0
    plan = plan or {}
    if plan.get("play_big"):
        dollars = dollars / float(DESK_PLAY_BIG_MULT)
    if sports_accuracy_ready(plan.get("perf")) and not plan.get("play_safe"):
        dollars = dollars * float(SPORTS_ACCURACY_MULT)
    dollars = round(max(0.0, dollars), 2)
    if 0 < dollars < 1.0:
        return 0.0
    return dollars


def stake_for_model(fair, desk=None, cfg=None, edge=None, open_risk_used=0.0, ask=None, spread=None, ticker=None):
    """Paper dollars for one sports fill — Kelly-lite + shared vol/learn adapt."""
    if desk is not None:
        try:
            quoted = desk.stake_dollars_for(
                "sports-gap",
                fair,
                edge=edge,
                cfg=cfg,
                open_risk_used=open_risk_used,
                ask=ask,
                root=DESK_ROOT,
                vol_kwargs={
                    "ask": ask,
                    "spread": spread,
                    "ticker": ticker or "sports",
                    # Thin edges near the money ⇒ higher vol / safer size.
                    "cushion": abs(float(fair) - 0.5) if fair is not None else None,
                    "sigma": 0.25,
                },
                return_plan=True,
            )
            if isinstance(quoted, tuple):
                stake, plan = quoted
            else:
                stake, plan = quoted, {}
            return apply_sports_accuracy_size(stake, plan)
        except Exception:
            try:
                return float(desk.paper_stake_dollars(fair, cfg))
            except Exception:
                pass
    try:
        chance = float(fair)
    except (TypeError, ValueError):
        chance = 0.0
    if chance + 1e-12 < 0.8:
        return 20.0
    span = 0.2
    t = (chance - 0.8) / span
    if t < 0:
        t = 0.0
    elif t > 1:
        t = 1.0
    return round(20.0 + t * 80.0, 2)

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


def _kalshi_urlopen(req, timeout):
    """Kalshi GETs share one pace / back-off / cache across towers (kalshi_gateway)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        import kalshi_gateway
    except ImportError:
        return urllib.request.urlopen(req, timeout=timeout)
    return kalshi_gateway.urlopen(req, timeout=timeout)


def _gateway_busy(exc) -> bool:
    return type(exc).__name__ == "GatewayBusy"


def get(url, tries=3):
    """Public GET with a one-minute cache and a retry. A failure stays a failure."""
    hit = _cache_get(url)
    if hit is not None:
        return hit
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (paper)"})
            with _kalshi_urlopen(req, timeout=20) as response:
                body = json.load(response)
            _cache_put(url, body)
            return body
        except Exception as exc:
            if i == tries - 1 or _gateway_busy(exc):
                raise RuntimeError("public GET failed")
            time.sleep(1.5)

def now_ct():
    return datetime.now(CT).strftime("%Y-%m-%d %H:%M:%S CT")

# ---------------- state + log ----------------
def _lift_old_starter(state):
    """Raise the empty $14 paper starter to $100. Any other cash stays put."""
    if not isinstance(state, dict):
        return False
    if state.get("open") or state.get("closed"):
        return False
    try:
        cash = float(state.get("cash"))
    except (TypeError, ValueError):
        return False
    if abs(cash - OLD_BANKROLL) > 0.001:
        return False
    state["cash"] = START_BANKROLL
    state["paper_only"] = True
    return True


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as f:
            state = json.load(f)
        try:
            lifted = _desk().lift_sports_starter(state)
        except Exception:
            lifted = _lift_old_starter(state)
        if lifted:
            save_state(state)
        return state
    return {"cash": START_BANKROLL, "open": [], "closed": [], "runs": 0, "paper_only": True}

def save_state(s):
    path = STATE
    if os.path.islink(path):
        path = os.path.realpath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(s, handle, indent=2)
        handle.flush()
    os.replace(tmp, path)


BUY_INTENT = os.path.join(HERE, "buy_intent.json")
BUY_EXIT_RULE = "sports-gap live exit"


def replacement_block(game_key, open_by_game, exited_this_check) -> str:
    """A game already held, or closed this check, is not bought again."""
    if game_key in (open_by_game or {}):
        return "already holding this game"
    if game_key in (exited_this_check or ()):
        return "no replacement after an exit this check"
    return ""


def record_close(position, *, cash, exit_name, bid=None, stake=None, exit_fee=None, root=None):
    """Stamp cash and the exit on the closed row, then journal that reason.

    A missing bid is not stored. The same fill id and exit name are not written twice.
    P/L stays the number already on the row.
    """
    if not isinstance(position, dict):
        return None
    try:
        position["cash_after"] = round(float(cash), 2)
    except (TypeError, ValueError):
        pass
    if exit_fee is not None:
        try:
            fee_n = float(exit_fee)
        except (TypeError, ValueError):
            fee_n = None
        if fee_n is not None and fee_n == fee_n and fee_n >= 0:
            position["exit_fee"] = round(fee_n, 4)
    journal_root = DESK_ROOT if root is None else root
    fee_for_journal = position.get("exit_fee")
    if fee_for_journal is None:
        fee_for_journal = position.get("fee")
    try:
        if journal_root not in sys.path:
            sys.path.insert(0, journal_root)
        import desk_brain
        return desk_brain.record_decision(
            journal_root,
            bot="sports-gap",
            action="settle" if str(exit_name or "") == "settled" else "sell",
            ticker=str(position.get("ticker") or ""),
            side=str(position.get("side") or ""),
            reasons=[str(exit_name or "")],
            note=str(exit_name or "")[:240],
            fill_id=str(position.get("fill_id") or ""),
            bid=bid,
            stake=stake if stake is not None else position.get("cost"),
            exit_name=str(exit_name or ""),
            fee=fee_for_journal,
            cash=position.get("cash_after"),
        )
    except Exception:
        return None


def _atomic_json(path, payload):
    dest = path
    if os.path.islink(dest):
        dest = os.path.realpath(dest)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
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
        "tower": "sports-gap",
        "fill_id": str(fill_id),
        "ticker": str(ticker or ""),
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
    opens = [p for p in (state or {}).get("open") or [] if isinstance(p, dict)]
    closed = [p for p in (state or {}).get("closed") or [] if isinstance(p, dict)]
    if fid and any(str(p.get("fill_id") or "") == fid for p in opens):
        status = "open"
    elif fid and any(str(p.get("fill_id") or "") == fid for p in closed):
        status = "closed"
    else:
        status = "abandoned"
    if intent.get("status") != status or intent.get("paper_only") is not True:
        intent["status"] = status
        intent["paper_only"] = True
        _atomic_json(BUY_INTENT, intent)
    return status

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
    """Skip re-fetch only when cache has neither live nor tip-soon games.

    Prefer-1: live-only idle was a tip-soon false-friend. Pre-tip warm (and any
    prior tick) caches scoreboards with ``pre`` games; treating "no ``in``" as
    idle then skipped tip-soon evaluate and CARD-invented
    "No live or tip-soon games" while tip-soon sat in cache (#433 sibling).
    """
    body = _cache_get(league_url(path))
    if not isinstance(body, dict):
        return False
    for event in body.get("events") or []:
        try:
            state = event["status"]["type"]["state"]
            if state == "in":
                return False
            if state == "pre" and tip_within_minutes({"date": event.get("date")}):
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


def espn_pregame_fair_home(summary):
    """De-vigged home win prob from ESPN pickcenter moneylines (pregame)."""
    pc = (summary.get("pickcenter") or [])
    if not pc:
        return None
    try:
        ph = ml_to_prob(pc[0]["homeTeamOdds"]["moneyLine"])
        pa = ml_to_prob(pc[0]["awayTeamOdds"]["moneyLine"])
        if ph + pa <= 0:
            return None
        return ph / (ph + pa)
    except Exception:
        return None


def tip_eta_minutes(game) -> float | None:
    """Minutes until tip (negative if already tipped). None if date missing/bad."""
    raw = game.get("date")
    if not raw:
        return None
    try:
        when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    now = datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (when - now).total_seconds() / 60.0


def tip_within_minutes(game, minutes=PREGAME_WINDOW_MIN) -> bool:
    """True when tip/start is within ±minutes of now (CT-aware via UTC date string)."""
    eta = tip_eta_minutes(game)
    if eta is None:
        return False
    return abs(float(eta)) <= float(minutes)


def tip_alarm_band(game) -> int | None:
    """
    Masters tip alarms: return 15 or 5 when tip is inside that forward window
    (0 < eta <= band). Used to prioritize fee-aware buys near tip — does not
    waive venue min_edge.
    """
    eta = tip_eta_minutes(game)
    if eta is None or eta <= 0:
        return None
    for band in sorted(TIP_ALARM_WINDOWS_MIN):
        if eta <= float(band):
            return int(band)
    return None


def espn_fair_home(summary, game):
    """Live WP when available; otherwise tip-soon pickcenter fair."""
    live = espn_home_wp(summary)
    if live is not None:
        return live
    if game.get("state") == "pre" and tip_within_minutes(game):
        return espn_pregame_fair_home(summary)
    return None


def _line_clv_fair_home(fair):
    """Line CLV fair for green_boost — refuse exact 0/1 wipe as binary.

    Hold-to-settle must densify a non-wipe close fair. Exact 0.0/1.0 is Kalshi
    settle autopsy only and is excluded from green_boost n.
    """
    if fair is None:
        return None
    try:
        f = float(fair)
    except (TypeError, ValueError):
        return None
    if not (0.0 < f < 1.0):
        return None
    return f


def _espn_settle_line_wp(summary):
    """Last non-wipe home WP for hold-to-settle line CLV.

    ESPN finals append exact 0.0/1.0 as the trailing winprobability row.
    Mid-open ``espn_home_wp`` correctly uses that last tick for buy fair;
    settle densify must walk back past trailing wipe so #442 line CLV fires.
    """
    wp = summary.get("winprobability") or []
    for row in reversed(wp):
        if not isinstance(row, dict):
            continue
        v = row.get("homeWinPercentage")
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if 0.0 < f < 1.0:
            return f
    return None


_NHL_PERIOD_SEC = 20 * 60


def _nhl_play_period(play):
    """ESPN NHL play period may be int or ``{'number': N}``."""
    if not isinstance(play, dict):
        return None
    period = play.get("period")
    if isinstance(period, dict):
        period = period.get("number")
    try:
        return int(period)
    except (TypeError, ValueError):
        return None


def _nhl_play_elapsed_sec(play):
    """ESPN NHL play clocks count UP (elapsed in period), not remaining."""
    if not isinstance(play, dict):
        return None
    clock = play.get("clock")
    if isinstance(clock, (int, float)):
        return float(clock)
    if not isinstance(clock, dict):
        return None
    display = clock.get("displayValue")
    if isinstance(display, str) and ":" in display:
        try:
            mm, ss = display.split(":", 1)
            return int(mm) * 60 + int(float(ss))
        except (TypeError, ValueError):
            return None
    for key in ("value", "seconds"):
        if clock.get(key) is not None:
            try:
                return float(clock[key])
            except (TypeError, ValueError):
                continue
    return None


def _nhl_settle_line_fair(summary, game):
    """Last non-wipe nhl_model fair from plays (ESPN WP walkback sibling).

    Scoreboard finals ship ``period=3 clock=0`` → ``nhl_model`` exact 0/1 →
    ``_line_clv_fair_home`` refuses → hold-to-settle still Kalshi binary.
    NHL has no winprobability series; walk plays past rem=0 / OT wipe and
    re-run the model at the last regulation state with rem>0.
    Play clocks are elapsed — convert to remaining for ``nhl_model``.
    """
    plays = summary.get("plays") or []
    base_home = dict((game or {}).get("home") or {})
    base_away = dict((game or {}).get("away") or {})
    for play in reversed(plays):
        if not isinstance(play, dict):
            continue
        period = _nhl_play_period(play)
        if period is None or period > 3:
            continue
        elapsed = _nhl_play_elapsed_sec(play)
        if elapsed is None:
            continue
        rem_sec = max(0.0, float(_NHL_PERIOD_SEC) - float(elapsed))
        if rem_sec <= 0:
            continue
        hs = play.get("homeScore")
        as_ = play.get("awayScore")
        if hs is None or as_ is None:
            continue
        snap = {
            "id": (game or {}).get("id"),
            "home": dict(base_home),
            "away": dict(base_away),
            "state": "in",
            "status": {"period": period, "clock": rem_sec},
        }
        snap["home"]["score"] = hs
        snap["away"]["score"] = as_
        try:
            fair = nhl_model(summary, snap)
        except Exception:
            continue
        line = _line_clv_fair_home(fair)
        if line is not None:
            return line
    return None


def _post_settle_fair_home(path, game, src, summary=None):
    """Densify ESPN/model fair_home for a finalized open hold (green CLV)."""
    try:
        summ = summary if summary is not None else espn_summary(path, game["id"])
        if src != "espn":
            # Prefer-3: scoreboard rem=0 finals wipe nhl_model to exact 0/1.
            # Walk plays past rem=0 (no WP series); fall through to live model
            # only when plays yield no line (tip summary invent / mid-data).
            fair = _nhl_settle_line_fair(summ, game)
            if fair is None:
                fair = nhl_model(summ, game)
        else:
            # Prefer-3: walk back past trailing wipe 0/1; do not use mid-open
            # espn_home_wp (would no-op via _line_clv_fair_home on true finals).
            fair = _espn_settle_line_wp(summ)
            if fair is None:
                fair = espn_fair_home(summ, game)
        return _line_clv_fair_home(fair)
    except Exception:
        return None

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
    if not isinstance(clock, (int, float)):
        # Prefer shared ESPN clock densify (#416/#shortDetail) — empty displayClock
        # must not invent a full 20:00 period (same lie as t-final DROP).
        clock = None
        try:
            if DESK_ROOT not in sys.path:
                sys.path.insert(0, DESK_ROOT)
            import desk_roi_plan as _clk
            clock = _clk._sports_clock_seconds(st if isinstance(st, dict) else {})
        except Exception:
            clock = None
        if clock is None:
            clock = 20 * 60  # truly missing clock → period-start guess for fair only
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


def market_yes_bid(m):
    """Yes bid in dollars from a Kalshi market dict (dollars or cents)."""
    if not isinstance(m, dict):
        return None
    bid = px(m, "yes_bid_dollars")
    if bid is not None:
        return bid
    raw = m.get("yes_bid")
    if raw in (None, ""):
        return None
    try:
        bid = float(raw)
    except (TypeError, ValueError):
        return None
    if bid > 1.5:
        bid = bid / 100.0
    return bid


def fetch_kalshi_market(ticker: str):
    """Best-effort public market fetch for settle-retro / mid-open bid densify."""
    tick = str(ticker or "").strip()
    if not tick:
        return None
    try:
        payload = get(f"{KALSHI}/markets/{tick}")
    except Exception:
        return None
    market = payload.get("market") if isinstance(payload, dict) else None
    if not isinstance(market, dict):
        market = payload if isinstance(payload, dict) else None
    return market if isinstance(market, dict) else None


# ---------------- main ----------------
def _desk():
    if DESK_ROOT not in sys.path:
        sys.path.insert(0, DESK_ROOT)
    import pimp_desk
    return pimp_desk


def _paper_limits():
    """Desk limits for this check. Paper only. A missing desk keeps the saved edge."""
    try:
        desk = _desk()
        cfg = desk.load_settings(DESK_ROOT)
        return desk, cfg
    except Exception:
        return None, {
            "min_edge": MIN_GAP,
            "max_open_positions": MAX_OPEN,
            "daily_loss_stop": 150.0,
        }


def _card_line(summary_out):
    trades = summary_out.get("trades") or []
    skips = summary_out.get("skips") or []
    if skips:
        return "CARD: " + str(skips[0])
    # Prefer-1: feed failures must not false-friend as empty/no-edge (#432 leftover).
    data_errors = summary_out.get("data_errors") or []
    if data_errors:
        err0 = data_errors[0] if isinstance(data_errors[0], dict) else {}
        src = str(err0.get("source") or "feed")
        league = str(err0.get("league") or "")
        reason = f"data error: {src} down"
        if league:
            reason = f"{reason} ({league})"
        return "CARD: " + reason
    if trades:
        word = "trade" if len(trades) == 1 else "trades"
        return f"CARD: Paper buy. {len(trades)} paper {word} this check."
    if summary_out.get("live_games") == 0 and not summary_out.get("matched"):
        return "CARD: No live or tip-soon games, so this check bought nothing."
    return "CARD: No paper buy (lanes clear, no fee-aware edge)."


def _densify_early_eval_skip(
    *,
    reason: str,
    ticker: str = "",
    side: str = "",
    series: str = "",
    league: str = "",
    fair=None,
    gap=None,
    ask=None,
    bid=None,
    lane: str = "",
) -> None:
    """Mirror buy-path skip densify for early evaluate rejects (#396 leftover).

    CARD already gets `summary_out["skips"]`; this feeds desk_brain / skip_board
    / feature-store consumers. Observe only — never LIVE / force-arm.
    """
    if not reason:
        return
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_brain
        desk_brain.record_decision(
            DESK_ROOT,
            bot="sports-gap",
            action="skip",
            ticker=str(ticker or ""),
            side=str(side or ""),
            edge=gap,
            confidence=fair,
            reasons=[reason],
            note="early evaluate densify",
        )
    except Exception:
        pass
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_living
        fee_n = None
        try:
            fee_n = fee(ask) if ask is not None else None
        except Exception:
            fee_n = None
        desk_living.record_eval_features(
            DESK_ROOT,
            bot="sports-gap",
            action="skip",
            ticker=str(ticker or ""),
            series=str(series or league or ""),
            ev={
                "side": side,
                "ask": ask,
                "bid": bid,
                "fee": fee_n,
                "confidence": fair,
                "edge": gap,
                "lane": lane,
                "ticker": ticker,
            },
            reasons=[reason],
            note=str(reason)[:160],
        )
    except Exception:
        pass


def run():
    t0 = time.perf_counter()
    existed = os.path.exists(STATE)
    s = load_state()
    if not existed:
        save_state(s)
    try:
        reconcile_buy_intent(s)
    except Exception:
        pass
    # Living upgrade: CLI/standalone honors desk entry_gate (exits still run).
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_living
        blocked = desk_living.honor_desk_entry_gate(DESK_ROOT)
        if blocked:
            print(f"Desk entry_gate (CLI honor): {blocked[:160]}")
    except Exception:
        pass
    # Sync public Kalshi trade tape for sports + desk series (read-only).
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import kalshi_tape
        # Sports family budget — never expand KXINXU/NCAAF hundreds of opens here
        # (that blew the 75s desk timeout → "Stopped after 75s.").
        tape = kalshi_tape.sync_tape_family(DESK_ROOT, "sports")
        print(
            f"Kalshi tape: +{tape.get('last_added') or 0} new prints "
            f"(kept {len(tape.get('trades') or [])})"
        )
    except Exception as exc:
        print(f"Kalshi tape sync skipped: {type(exc).__name__}")
    desk, cfg = _paper_limits()
    try:
        need_edge = float(desk.venue_min_edge("kalshi_sports", cfg)) if desk is not None else float(
            cfg.get("min_edge") if cfg.get("min_edge") is not None else MIN_GAP
        )
    except Exception:
        need_edge = float(cfg.get("min_edge") if cfg.get("min_edge") is not None else MIN_GAP)
    flip_delta = float(cfg.get("model_flip_delta") if cfg.get("model_flip_delta") is not None else 0.08)
    flip_on = bool(cfg.get("model_flip_exits", True))
    max_open = int(cfg.get("max_open_positions") or MAX_OPEN)
    day = datetime.now(CT).strftime("%Y-%m-%d")
    today_pnl = 0.0
    for pos in s.get("closed") or []:
        if str(pos.get("closed") or "").startswith(day):
            try:
                today_pnl += float(pos.get("pnl") or 0)
            except (TypeError, ValueError):
                pass
    # Sticky book PnL — red rescue must not forget overnight realized losses.
    realized_book = 0.0
    for pos in s.get("closed") or []:
        try:
            realized_book += float(pos.get("pnl") or 0)
        except (TypeError, ValueError):
            pass
    red_pnl = min(float(today_pnl), float(realized_book))
    entries_off = ""
    stop = float(cfg.get("daily_loss_stop") or 150)
    if today_pnl <= -stop:
        entries_off = f"Daily loss stop is hit (${abs(today_pnl):.2f} against ${stop:.2f})."
    if os.environ.get("DESK_BLOCK_ENTRIES") == "1":
        # Prefer-1: honor stored DESK_BLOCK_REASON — do not invent bland entry_gate.
        gate_why = ""
        try:
            if DESK_ROOT not in sys.path:
                sys.path.insert(0, DESK_ROOT)
            import desk_living
            gate_why = desk_living.desk_block_entries_reason(
                "Desk entry_gate blocked new paper buys. Exits and settles still run."
            )
        except Exception:
            gate_why = ""
        entries_off = entries_off or gate_why or (
            "Desk entry_gate blocked new paper buys. Exits and settles still run."
        )
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
    # ROI loop: gather candidates first, sell/settle next, then paper-buy inside open-risk.
    buy_candidates = []
    max_open_risk = float(cfg.get("max_open_risk") if cfg.get("max_open_risk") is not None else 100)

    # Pre-tip book warm T−15 / T−5 into quote_cache (never places orders / waives floors).
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_more
        tip_games = []
        for league, (path, series, _src) in SPORTS.items():
            try:
                games = espn_games(path)
            except Exception:
                continue
            for g in games:
                if g.get("state") != "pre":
                    continue
                eta = tip_eta_minutes(g)
                if eta is None or eta <= 0 or eta > 15:
                    continue
                tip_games.append({
                    "league": league,
                    "series": series,
                    "tip_in_min": float(eta),
                    "ticker": str(g.get("id") or ""),
                })
        if tip_games:
            warm15 = desk_more.warm_tip_books(
                DESK_ROOT, 15, games=tip_games, fetch=get,
            )
            print(
                f"Pre-tip warm T−15: {warm15.get('warmed_n') or 0} series "
                f"({warm15.get('games_n') or 0} tip-soon)"
            )
            tip5 = [g for g in tip_games if float(g.get("tip_in_min") or 99) <= 5]
            if tip5:
                warm5 = desk_more.warm_tip_books(
                    DESK_ROOT, 5, games=tip5, fetch=get,
                )
                print(
                    f"Pre-tip warm T−5: {warm5.get('warmed_n') or 0} series "
                    f"({warm5.get('games_n') or 0} tip-soon)"
                )
    except Exception as exc:
        print(f"Pre-tip warm skipped: {type(exc).__name__}")

    espn_secs = 0.0
    kalshi_secs = 0.0
    for league, (path, series, src) in SPORTS.items():
        # Prefer-3: idle scoreboard must not skip a league we still hold open —
        # post settles need to reach fair_home densify for green line CLV.
        league_has_open = any(
            str(k).startswith(f"{league}:") for k in open_by_game
        )
        if league_cached_idle(path) and not league_has_open:
            summary_out["leagues"][league] = "no live games"
            continue
        try:
            t_espn = time.perf_counter()
            games = espn_games(path)
            espn_secs += time.perf_counter() - t_espn
        except Exception:
            miss = f"data error: ESPN down ({league})"
            lines.append(f"| {ts} | {league} | - | {miss} | | | | | data error |")
            summary_out.setdefault("data_errors", []).append(
                {"league": league, "source": "ESPN", "error": "failed"}
            )
            # Prefer-1/2: densify feed fail into CARD skips + brain (match-miss sibling).
            # Without this, all-league ESPN down false-friends as "No live or tip-soon".
            summary_out["skips"].append(miss)
            _densify_early_eval_skip(
                reason=miss,
                ticker="",
                series=series,
                league=league,
            )
            continue
        relevant = []
        for g in games:
            key = f"{league}:{g['id']}"
            if key in open_by_game:
                relevant.append(g)
            elif g["state"] == "in":
                relevant.append(g)
            elif g["state"] == "pre" and tip_within_minutes(g):
                relevant.append(g)
        if not relevant:
            summary_out["leagues"][league] = "no live/tip-soon games"; continue
        try:
            t_kalshi = time.perf_counter()
            markets = kalshi_markets(series)
            kalshi_secs += time.perf_counter() - t_kalshi
        except Exception:
            miss = f"data error: Kalshi down ({league})"
            lines.append(f"| {ts} | {league} | - | {miss} | | | | | data error |")
            summary_out.setdefault("data_errors", []).append(
                {"league": league, "source": "Kalshi", "error": "failed"}
            )
            # Prefer-1/2: densify feed fail into CARD skips + brain (match-miss sibling).
            summary_out["skips"].append(miss)
            _densify_early_eval_skip(
                reason=miss,
                ticker="",
                series=series,
                league=league,
            )
            continue
        summary_out["leagues"][league] = f"{sum(g['state']=='in' for g in relevant)} live, series {series} ({len(markets)} open mkts)"
        for g in relevant:
            key = f"{league}:{g['id']}"
            name = f"{g['away']['team']['abbreviation']} @ {g['home']['team']['abbreviation']}"
            score = f"{g['away'].get('score','?')}-{g['home'].get('score','?')} ({g['detail']})"
            if g["state"] == "in":
                summary_out["live_games"] += 1
            if g["state"] == "post":
                # Prefer-3: bare post was starving green line CLV (binary wipe).
                # When we hold this game open, densify fair_home (+ pair) before settle.
                entry = {
                    "final": True, "game": g, "name": name, "score": score,
                }
                if key in open_by_game:
                    fair_home = _post_settle_fair_home(path, g, src)
                    if fair_home is not None:
                        entry["fair_home"] = fair_home
                    try:
                        pair_post = match_event(g, markets)
                        if pair_post:
                            entry["pair"] = pair_post
                    except Exception:
                        pass
                live_info[key] = entry
                continue
            pair = match_event(g, markets)
            try:
                summ = espn_summary(path, g["id"])
                if src != "espn":
                    fair_home = nhl_model(summ, g)
                    # Prefer-3: rem=0 End-of-period (still state=in) wipes exact
                    # 0/1 — reuse settle plays walkback so open-hold last_fair /
                    # exit CLV stay line (#445 mid-open sibling).
                    if _line_clv_fair_home(fair_home) is None:
                        walked = _nhl_settle_line_fair(summ, g)
                        if walked is not None:
                            fair_home = walked
                else:
                    fair_home = espn_fair_home(summ, g)
            except Exception as e:
                fair_home = None
            if not pair:
                # Seed live_info anyway so open-hold densify (hard-stop / t-final /
                # last_fair) can ticker-fetch bids. Buy path stays skipped.
                live_info[key] = {
                    "final": False, "game": g, "pair": None, "fair_home": fair_home,
                    "name": name, "score": score,
                }
                miss = "no Kalshi match - skip"
                lines.append(
                    f"| {ts} | {league} | {name} | {score} | | | | | {miss} |"
                )
                # Densify match-miss into CARD skips (buy path stays off).
                summary_out["skips"].append(miss)
                # Honest DATA densify: no ticker (unmatched). Feeds skip_board
                # MATCH/DATA codes without inventing a market id (#401 leftover).
                _densify_early_eval_skip(
                    reason=miss,
                    ticker="",
                    series=series,
                    league=league,
                )
                continue
            summary_out["matched"] += 1
            hb, ha = px(pair["home"], "yes_bid_dollars"), px(pair["home"], "yes_ask_dollars")
            ab, aa = px(pair["away"], "yes_bid_dollars"), px(pair["away"], "yes_ask_dollars")
            src_tag = "model" if src != "espn" else ("ESPN" if g.get("state") == "in" else "pregame")
            row = f"| {ts} | {league} | {name} | {score} | " + \
                  (f"{fair_home:.1%} ({src_tag})" if fair_home is not None else "n/a") + \
                  f" | {hb}/{ha} | {ab}/{aa} | "
            live_info[key] = {"final": False, "game": g, "pair": pair, "fair_home": fair_home, "name": name, "score": score}
            if fair_home is None:
                reason = "no fair prob - skip"
                lines.append(row + f" | {reason} |")
                summary_out["skips"].append(reason)
                tick0 = str((pair.get("home") or {}).get("ticker") or "")
                _densify_early_eval_skip(
                    reason=reason, ticker=tick0, series=series, league=league,
                )
                continue
            # best side
            cands = []
            for side, m, fair, bid, ask in (("home", pair["home"], fair_home, hb, ha), ("away", pair["away"], 1 - fair_home, ab, aa)):
                if ask is None or bid is None: continue
                cands.append((fair - ask - fee(ask), side, m, fair, bid, ask))
            if not cands:
                reason = "no prices - skip"
                lines.append(row + f" | {reason} |")
                summary_out["skips"].append(reason)
                tick0 = str((pair.get("home") or {}).get("ticker") or "")
                _densify_early_eval_skip(
                    reason=reason,
                    ticker=tick0,
                    series=series,
                    league=league,
                    fair=fair_home,
                )
                continue
            gap, side, m, fair, bid, ask = max(cands, key=lambda c: c[0])
            gtxt = f"{gap*100:+.1f} pts on {m.get('yes_sub_title')} (fair {fair:.1%} vs ask {ask:.2f})"
            base_need = need_edge if src == "espn" else round(need_edge + 0.02, 4)
            reason = None
            lane = "accurate"
            need = base_need
            # Top25 #15 / E1 #113 — sport-split fair floors + staff soft-p relax.
            floors = fair_lane_floors(league, DESK_ROOT)
            accurate_floor = float(floors["accurate_floor"])
            speed_floor = float(floors["speed_floor"])
            if entries_off:
                reason = entries_off
            elif key in open_by_game:
                reason = "already holding this game"
            elif CLOSE_GAME_BAND[0] <= fair_home <= CLOSE_GAME_BAND[1]:
                reason = "close game - skip"
            elif fair + 1e-12 >= accurate_floor:
                lane = "accurate"
                need = base_need
            elif fair + 1e-12 >= speed_floor:
                # Speed lane: take the fill only with extra fee-aware edge.
                lane = "speed"
                need = round(base_need + MIN_GAP_SPEED_EXTRA, 4)
            else:
                reason = f"fair {fair:.0%} < speed floor {speed_floor:.0%} - skip"
            if reason is None and gap < need:
                reason = f"gap < {need*100:.0f} ({lane}) - no trade"
            elif reason is None and ask - bid > MAX_SPREAD:
                reason = "spread too wide - skip"
            elif reason is None and not (PRICE_BOUNDS[0] <= ask <= PRICE_BOUNDS[1]):
                reason = "price too extreme - skip"
            elif reason is None and desk is not None:
                skip = desk.learning_skip(
                    desk.load_learning(DESK_ROOT),
                    league,
                    desk.prob_bucket(fair),
                    side=side,
                    hour_ct=datetime.now(CT).hour,
                )
                if skip:
                    reason = skip
            alarm = tip_alarm_band(g) if g.get("state") == "pre" else None
            tip_window = alarm is not None or (
                g.get("state") == "pre" and tip_within_minutes(g)
            )
            if tip_window:
                try:
                    if DESK_ROOT not in sys.path:
                        sys.path.insert(0, DESK_ROOT)
                    import desk_roi_plan as _tip_funnel
                    _tip_funnel.record_tip_funnel(DESK_ROOT, league, "games_seen")
                    if reason is None:
                        _tip_funnel.record_tip_funnel(DESK_ROOT, league, "fee_clear")
                    elif reason and (
                        "gap <" in str(reason)
                        or "fair" in str(reason).lower()
                        or "edge" in str(reason).lower()
                        or "spread" in str(reason).lower()
                        or "price too" in str(reason).lower()
                    ):
                        _tip_funnel.record_tip_funnel(DESK_ROOT, league, "block_edge")
                except Exception:
                    pass
            # Soft z/p near-miss densify (mirror btc15m) — shadow only, no buy.
            if reason and (
                "gap <" in str(reason)
                or "fair" in str(reason).lower()
                or "speed floor" in str(reason).lower()
            ):
                try:
                    if DESK_ROOT not in sys.path:
                        sys.path.insert(0, DESK_ROOT)
                    import desk_more as _nm_more
                    # Soft-p via fair; soft-edge via gap vs need (no sports z — p/edge only).
                    nm = _nm_more.is_near_miss(
                        reasons=[reason],
                        z=None,
                        p=fair,
                        edge=gap,
                        min_edge=float(need) if need is not None else 0.06,
                    )
                    if nm.get("near_miss"):
                        _nm_more.record_near_miss(DESK_ROOT, {
                            "bot": "sports-gap",
                            "ticker": m.get("ticker"),
                            "side": "YES",  # Kalshi yes contract on this team market
                            "soft": nm.get("soft"),
                            "p": fair,
                            "edge": gap,
                            "ask": ask,
                            "note": f"sports {nm.get('note')} · {side}",
                            "league": league,
                        })
                        summary_out.setdefault("near_miss", []).append(
                            f"NEAR-MISS {m.get('ticker')} ({nm.get('note')})"
                        )
                except Exception:
                    pass
            if reason:
                lines.append(row + gtxt + f" | {reason} |")
                # Densify evaluate rejects into CARD skips (was learning_skip-only).
                summary_out["skips"].append(reason)
                # Also densify brain / feature-store / skip_board (#396 leftover).
                _densify_early_eval_skip(
                    reason=reason,
                    ticker=str(m.get("ticker") or ""),
                    side=str(side or ""),
                    series=series,
                    league=league,
                    fair=fair,
                    gap=gap,
                    ask=ask,
                    bid=bid,
                    lane=lane,
                )
                continue
            if alarm is not None:
                print(f"  TIP-ALARM T−{alarm}: {league} {name} (fee-aware priority, edge still required)")
            buy_candidates.append({
                "key": key, "league": league, "name": name, "m": m, "side": side, "fair": fair,
                "bid": bid, "ask": ask, "gap": gap, "score": score, "path": path, "g": g,
                "series": series, "row": row, "gtxt": gtxt, "lane": lane, "need": need,
                "tip_alarm": alarm,
                "tip_window": tip_window,
            })

    # ---- exits / settlement (before new paper buys) ----
    still = []
    exited_this_check = set()
    for p in s["open"]:
        info = live_info.get(p["game_key"])
        if info is None:
            # game not on scoreboard any more (next day) -> check summary directly
            try:
                summ = espn_summary(p["espn_path"], p["espn_id"])
                comp = summ["header"]["competitions"][0]
                if comp["status"]["type"]["state"] == "post":
                    home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
                    away = next(c for c in comp["competitors"] if c["homeAway"] == "away")
                    game_blob = {
                        "id": p.get("espn_id"),
                        "home": home,
                        "away": away,
                        "state": "post",
                        "status": comp.get("status") or {},
                    }
                    # Prefer-3: densify line fair_home so green CLV is not binary wipe.
                    league = str(p.get("league") or "")
                    src = (SPORTS.get(league) or (None, None, "espn"))[2]
                    fair_home = _post_settle_fair_home(
                        p["espn_path"], game_blob, src, summary=summ,
                    )
                    info = {
                        "final": True,
                        "game": {"home": home, "away": away},
                        "name": p["game"],
                        "score": comp["status"]["type"].get("shortDetail", "Final"),
                    }
                    if fair_home is not None:
                        info["fair_home"] = fair_home
            except Exception:
                pass
        if info and info["final"]:
            g = info["game"]
            hs, as_ = int(g["home"].get("score") or 0), int(g["away"].get("score") or 0)
            if hs == as_:
                still.append(p); continue   # tie/unclear -> wait for Kalshi settlement
            winner = "home" if hs > as_ else "away"
            won = winner == p["side"]
            payout = p["contracts"] * 1.0 if won else 0.0
            pnl = round(payout - p["cost"], 2)
            s["cash"] = round(s["cash"] + payout, 2)
            # Honest binary settle mark — HS/tf catchup reads exit_price|exit_bid|mark_bid
            # only (never entry companion). Losers with exit_price=0 densify when
            # settle-retro market bid is missing; winners with 1.0 stay non-invent
            # (wipe guard / organic-exit rules). Commodity #462 sibling.
            p.update({
                "closed": ts,
                "exit": "settled",
                "exit_price": 1.0 if won else 0.0,
                "payout": payout,
                "pnl": pnl,
                "final_score": f"{as_}-{hs}",
            })
            record_close(
                p,
                cash=s["cash"],
                exit_name="settled",
                stake=p.get("risk") if p.get("risk") is not None else p.get("cost"),
            )
            s["closed"].append(p)
            if p.get("game_key"):
                exited_this_check.add(p.get("game_key"))
            if desk is not None:
                desk.record_learning(DESK_ROOT, {
                    "result": "hit" if won else "miss",
                    "reason": "settled",
                    "market": p.get("league") or "",
                    "bucket": desk.prob_bucket(p.get("fair_at_entry")),
                    "stake": p.get("risk") if p.get("risk") is not None else p.get("cost"),
                    "fill_id": p.get("fill_id") or "",
                    "side": p.get("side") or "",
                    "at": ts,
                })
            # Closing-line value: entry fair vs last model/market fair — never binary 0/1.
            # Binary settle proxies invert beat-close (wins always "lose" CLV) and starve green_boost.
            # Prefer stashed last_fair / last_mark from mid-open ticks; refuse Kalshi wipe 0/1 as line.
            try:
                if DESK_ROOT not in sys.path:
                    sys.path.insert(0, DESK_ROOT)
                import desk_more
                close_fair = None
                clv_kind = "line"
                if info.get("fair_home") is not None:
                    close_fair = (
                        float(info["fair_home"]) if p["side"] == "home"
                        else 1.0 - float(info["fair_home"])
                    )
                if close_fair is None:
                    for key in ("last_fair", "fair_at_exit", "last_mark"):
                        if p.get(key) is not None:
                            try:
                                close_fair = float(p.get(key))
                            except (TypeError, ValueError):
                                close_fair = None
                            if close_fair is not None:
                                # last_mark is a market bid — only accept non-wipe line.
                                if key == "last_mark" and not (0.0 < float(close_fair) < 1.0):
                                    close_fair = None
                                    continue
                                break
                if close_fair is None:
                    pair_clv = info.get("pair") if isinstance(info, dict) else None
                    m_clv = None
                    if isinstance(pair_clv, dict):
                        m_clv = pair_clv.get(p["side"])
                    bid_clv = market_yes_bid(m_clv) if m_clv else None
                    if bid_clv is None:
                        m_clv = fetch_kalshi_market(p.get("ticker"))
                        bid_clv = market_yes_bid(m_clv) if m_clv else None
                    if bid_clv is not None:
                        # Finalized wipe 0/1 is binary — autopsy only, not green_boost line.
                        if abs(float(bid_clv) - 0.0) < 1e-12 or abs(float(bid_clv) - 1.0) < 1e-12:
                            close_fair = float(bid_clv)
                            clv_kind = "binary"
                        else:
                            close_fair = float(bid_clv)
                if close_fair is not None:
                    desk_more.record_sports_clv(
                        DESK_ROOT,
                        ticker=str(p.get("ticker") or ""),
                        side=str(p.get("side") or ""),
                        fair_entry=p.get("fair_at_entry"),
                        close_fair=close_fair,
                        pnl=pnl,
                        league=str(p.get("league") or ""),
                        exit_reason="settled",
                        clv_kind=clv_kind,
                    )
            except Exception:
                pass
            try:
                if DESK_ROOT not in sys.path:
                    sys.path.insert(0, DESK_ROOT)
                import desk_roi_plan
                desk_roi_plan.record_fee_ledger(
                    DESK_ROOT,
                    bot="sports-gap",
                    ticker=str(p.get("ticker") or ""),
                    side=str(p.get("side") or ""),
                    price=p.get("entry_price"),
                    contracts=p.get("contracts"),
                    fee=float(p.get("fee") or p.get("entry_fee") or 0.0),
                    pnl=pnl,
                    fill_id=str(p.get("fill_id") or ""),
                    kind="settle",
                    note="settled",
                )
            except Exception:
                pass
            # Near-miss would_pnl densify — label shadow skips for this ticker (observe).
            # Kalshi yes-contract: our side won → result=yes, else no. No live sell.
            try:
                if DESK_ROOT not in sys.path:
                    sys.path.insert(0, DESK_ROOT)
                import desk_roi_plan
                nm_result = "yes" if winner == p.get("side") else "no"
                desk_roi_plan.label_near_miss_from_result(
                    DESK_ROOT,
                    ticker=str(p.get("ticker") or ""),
                    result=nm_result,
                    bot="sports-gap",
                    note="sports-gap settle label",
                )
            except Exception:
                pass
            # Settle retrospective shadow densify — bid from pair if present;
            # next-day finals rebuild has no pair → Kalshi market bid fallback.
            # Still NO live sell.
            try:
                if DESK_ROOT not in sys.path:
                    sys.path.insert(0, DESK_ROOT)
                import desk_roi_plan
                pair = info.get("pair") if isinstance(info, dict) else None
                m_settle = None
                if isinstance(pair, dict):
                    m_settle = pair.get(p["side"])
                bid_settle = market_yes_bid(m_settle) if m_settle else None
                if bid_settle is None:
                    m_settle = fetch_kalshi_market(p.get("ticker"))
                    bid_settle = market_yes_bid(m_settle) if m_settle else None
                fair_settle = None
                if info.get("fair_home") is not None:
                    fair_settle = (
                        info["fair_home"] if p["side"] == "home"
                        else 1 - info["fair_home"]
                    )
                # Hard-stop settle-retro: never invent threshold stops from
                # finalized bid=0 on winners (same poison catch-up repair strips).
                if bid_settle is not None and not p.get("hard_stop_shadowed"):
                    wipe_quote = float(bid_settle) <= 0
                    if wipe_quote and float(pnl) + 1e-12 >= 0.0:
                        pass
                    else:
                        hs = desk_roi_plan.sports_hard_stop_hit(
                            p.get("entry_price"), bid_settle,
                        )
                        if hs.get("hit"):
                            desk_roi_plan.record_sports_hard_stop_shadow(
                                DESK_ROOT,
                                ticker=str(p.get("ticker") or ""),
                                side=str(p.get("side") or ""),
                                league=str(p.get("league") or ""),
                                entry_price=p.get("entry_price"),
                                bid=bid_settle,
                                fair=fair_settle,
                                contracts=p.get("contracts"),
                                cost=p.get("cost"),
                                note="settle-retro shadow hard-stop — no live sell",
                            )
                            p["hard_stop_shadowed"] = True
                            summary_out.setdefault("hard_stop_shadow", []).append(
                                f"SETTLE-RETRO STOP {p.get('ticker')} bid {bid_settle}"
                            )
                # Time-final settle-retro disabled: forcing rem=0 on finals invents
                # false near-final trims. Mid-open clock densify only.
            except Exception:
                pass
            lines.append(f"| {ts} | {p['league']} | {p['game']} | FINAL {as_}-{hs} | | | | | **PAPER SETTLE** {p['team']}: {'WON' if payout else 'LOST'} payout ${payout:.2f}, P&L ${pnl:+.2f} |")
            summary_out["closes"].append(f"SETTLE {p['ticker']} pnl {pnl:+.2f}")
            continue
        # Mid-open exits: hard-stop + time-final densify when pair/bid exist
        # (fair_home optional). Gap-decay / flip / scale-out still need fair.
        # When pair missing but ticker known, fetch Kalshi bid so shadow densifies.
        # Prefer-1: orphan opens (info is None — off scoreboard / next-day not-yet
        # final) must still ticker-fetch + HS densify. Gating fetch on `info`
        # starved shadow n while losers rode to settle. No rem invent; no live sell
        # on the orphan path (staff-armed live HS still needs live_info below).
        pair_info = info.get("pair") if info and isinstance(info, dict) else None
        m = None
        if isinstance(pair_info, dict):
            m = pair_info.get(p["side"])
        bid = market_yes_bid(m) if m is not None else None
        if bid is None:
            fetched = fetch_kalshi_market(p.get("ticker"))
            bid = market_yes_bid(fetched) if fetched else None
            # Prefer pair market for ask/fair exits; use fetch only when pair absent.
            if m is None and fetched is not None:
                m = fetched
        # Orphan densify: bid-only HS shadow when live_info missing (no clock → no t-final).
        if info is None and bid is not None:
            try:
                bid_f = float(bid)
            except (TypeError, ValueError):
                bid_f = None
            if bid_f is not None and 0.0 < bid_f < 1.0:
                p["last_mark"] = round(bid_f, 4)
            if not p.get("hard_stop_shadowed"):
                try:
                    if DESK_ROOT not in sys.path:
                        sys.path.insert(0, DESK_ROOT)
                    import desk_roi_plan
                    hs = desk_roi_plan.sports_hard_stop_hit(
                        p.get("entry_price"), bid,
                    )
                    if hs.get("hit"):
                        desk_roi_plan.record_sports_hard_stop_shadow(
                            DESK_ROOT,
                            ticker=str(p.get("ticker") or ""),
                            side=str(p.get("side") or ""),
                            league=str(p.get("league") or ""),
                            entry_price=p.get("entry_price"),
                            bid=bid,
                            fair=None,
                            contracts=p.get("contracts"),
                            cost=p.get("cost"),
                            note="orphan shadow hard-stop — no live sell",
                        )
                        p["hard_stop_shadowed"] = True
                        summary_out.setdefault("hard_stop_shadow", []).append(
                            f"ORPHAN STOP {p.get('ticker')} bid {bid}"
                        )
                except Exception:
                    pass
        if info and m is not None:
            fair_home = info.get("fair_home")
            fair = None
            if fair_home is not None:
                fair = fair_home if p["side"] == "home" else 1 - fair_home
            # Stash rolling model fair for hold-to-settle line CLV densify.
            # Refuse exact 0/1 wipe (mirror last_mark) — End-of-period NHL rem=0
            # must not poison green line CLV / settle fallback.
            if fair is not None:
                try:
                    fair_f = float(fair)
                except (TypeError, ValueError):
                    fair_f = None
                if fair_f is not None and 0.0 < fair_f < 1.0:
                    p["last_fair"] = round(fair_f, 4)
            # When model fair is absent, stash mid-open Kalshi mark (non-wipe) so
            # settle CLV can stay line — HS/t-final already densify from bid alone.
            if bid is not None:
                try:
                    bid_f = float(bid)
                except (TypeError, ValueError):
                    bid_f = None
                if bid_f is not None and 0.0 < bid_f < 1.0:
                    p["last_mark"] = round(bid_f, 4)
            exit_reason = None
            # Hard-stop / time-final shadow need a bid; live sell stays off until promote.
            if bid is not None:
                try:
                    if DESK_ROOT not in sys.path:
                        sys.path.insert(0, DESK_ROOT)
                    import desk_roi_plan
                    hs = desk_roi_plan.sports_hard_stop_hit(
                        p.get("entry_price"), bid,
                    )
                    if hs.get("hit") and not p.get("hard_stop_shadowed"):
                        desk_roi_plan.record_sports_hard_stop_shadow(
                            DESK_ROOT,
                            ticker=str(p.get("ticker") or ""),
                            side=str(p.get("side") or ""),
                            league=str(p.get("league") or ""),
                            entry_price=p.get("entry_price"),
                            bid=bid,
                            fair=fair,
                            contracts=p.get("contracts"),
                            cost=p.get("cost"),
                            note="shadow hard-stop — no live sell",
                        )
                        p["hard_stop_shadowed"] = True
                        summary_out.setdefault("hard_stop_shadow", []).append(
                            f"SHADOW STOP {p.get('ticker')} bid {bid}"
                        )
                        # Live hard-stop only after staff promote file (code default False).
                        if desk_roi_plan.sports_hard_stop_is_live(DESK_ROOT):
                            exit_reason = (
                                f"hard-stop bid {float(bid):.2f} ≤ "
                                f"{hs.get('threshold')}"
                            )
                    # Time-to-final trim shadow: ≤N min left + underwater mark.
                    if exit_reason is None and not p.get("time_final_shadowed"):
                        game = info.get("game") if isinstance(info, dict) else None
                        status = (game or {}).get("status") if isinstance(game, dict) else None
                        # espn_games densifies shortDetail onto game["detail"] —
                        # pass through so rem does not invent full period_min.
                        rem = desk_roi_plan.sports_minutes_remaining(
                            status,
                            league=str(p.get("league") or ""),
                            detail=(game or {}).get("detail") if isinstance(game, dict) else None,
                        )
                        tf = desk_roi_plan.sports_time_final_hit(
                            rem, bid,
                            entry_price=p.get("entry_price"),
                            cost=p.get("cost"),
                            contracts=p.get("contracts"),
                        )
                        if tf.get("hit"):
                            desk_roi_plan.record_sports_time_final_shadow(
                                DESK_ROOT,
                                ticker=str(p.get("ticker") or ""),
                                side=str(p.get("side") or ""),
                                league=str(p.get("league") or ""),
                                minutes_left=rem,
                                entry_price=p.get("entry_price"),
                                bid=bid,
                                contracts=p.get("contracts"),
                                cost=p.get("cost"),
                                note="shadow time-final — no live sell",
                            )
                            p["time_final_shadowed"] = True
                            summary_out.setdefault("time_final_shadow", []).append(
                                f"SHADOW TFINAL {p.get('ticker')} rem={rem}"
                            )
                            if desk_roi_plan.sports_time_final_is_live(DESK_ROOT):
                                exit_reason = (
                                    f"time-final ≤{tf.get('min_left_bar')}m "
                                    f"underwater mark {tf.get('mark_pnl')}"
                                )
                except Exception:
                    pass
            # Fair-dependent exits (gap-decay / flip / scale-out) need fair_home.
            if fair is not None:
                # Phase 2: gap-decay — tip edge that died mid-game frees risk.
                try:
                    if DESK_ROOT not in sys.path:
                        sys.path.insert(0, DESK_ROOT)
                    import desk_phase2
                    live_ask = px(m, "yes_ask_dollars")
                    if live_ask is not None:
                        gap_now = float(fair) - float(live_ask) - fee(live_ask)
                    else:
                        gap_now = float(fair) - float(p.get("entry_price") or 0)
                    mins = None
                    try:
                        # Use module-level datetime — a local import here shadows it for
                        # the whole run() and crashed every check after tape sync
                        # (UnboundLocalError on datetime.now(CT) for the day stamp).
                        opened = str(p.get("opened") or "")
                        if opened.endswith("Z"):
                            opened = opened[:-1] + "+00:00"
                        mins = (datetime.now(timezone.utc) - datetime.fromisoformat(opened)).total_seconds() / 60.0
                    except Exception:
                        mins = None
                    decay = desk_phase2.sports_gap_decay_exit(
                        gap_at_entry=p.get("gap_at_entry"),
                        gap_now=gap_now,
                        minutes_since_open=mins,
                        live=True,
                    )
                    if decay.get("exit"):
                        exit_reason = decay.get("reason") or "gap-decay"
                        desk_phase2.remember_gap_decay(DESK_ROOT, {
                            "ticker": p.get("ticker"), "league": p.get("league"), **decay,
                        })
                except Exception:
                    pass
                if exit_reason is None and flip_on and desk is not None:
                    try:
                        import desk_profit
                        if desk_profit.model_flip_adverse(
                            p["side"], p.get("fair_at_entry"), fair, flip_delta
                        ):
                            exit_reason = f"model-flip fair Δ≥{flip_delta:g}"
                    except Exception:
                        pass
                if exit_reason is None and bid is not None and bid > 0 and bid - fee(bid) >= fair:
                    exit_reason = "gap closed - sold at bid"
            # Scale-out 50% when fair moved +8¢ since entry (keep runner; free risk).
            if (
                fair is not None
                and exit_reason is None
                and bid is not None
                and bid > 0
                and not p.get("scaled_out")
                and p.get("fair_at_entry") is not None
                and float(fair) + 1e-12 >= float(p["fair_at_entry"]) + SCALE_OUT_FAIR_MOVE
            ):
                contracts = int(p.get("contracts") or 0)
                if contracts >= 2:
                    clip = max(1, int(round(contracts * SCALE_OUT_FRAC)))
                    clip = min(clip, contracts - 1)
                    px_net = bid - fee(bid)
                    proceeds = round(clip * px_net, 2)
                    cost_full = float(p.get("cost") or 0)
                    cost_clip = round(cost_full * clip / contracts, 2)
                    pnl = round(proceeds - cost_clip, 2)
                    s["cash"] = round(s["cash"] + proceeds, 2)
                    p["contracts"] = contracts - clip
                    p["cost"] = round(cost_full - cost_clip, 2)
                    if p.get("risk") is not None:
                        try:
                            p["risk"] = round(float(p["risk"]) * (contracts - clip) / contracts, 2)
                        except (TypeError, ValueError):
                            pass
                    p["scaled_out"] = True
                    p["scale_out_at"] = ts
                    p["scale_out_fair"] = round(float(fair), 4)
                    reason = f"scale-out +{SCALE_OUT_FAIR_MOVE*100:.0f}¢ fair (50%)"
                    # Densify clip into closed[] so boards/CLV/phase2 see partial exits
                    # (cash already moved; runner stays open). Never invent tip.
                    clip_row = dict(p)
                    clip_row.update({
                        "closed": ts,
                        "exit": reason,
                        "exit_price": round(float(bid), 4),
                        "payout": proceeds,
                        "pnl": pnl,
                        "contracts": clip,
                        "cost": cost_clip,
                        "fair_at_exit": round(float(fair), 4),
                        "scale_out_clip": True,
                        "runner_left": int(p.get("contracts") or 0),
                    })
                    record_close(
                        clip_row,
                        cash=s["cash"],
                        exit_name=reason,
                        bid=bid,
                        stake=cost_clip,
                        exit_fee=fee(bid),
                    )
                    s.setdefault("closed", []).append(clip_row)
                    try:
                        if DESK_ROOT not in sys.path:
                            sys.path.insert(0, DESK_ROOT)
                        import desk_roi_plan
                        import desk_living
                        import desk_phase2
                        desk_roi_plan.record_fee_ledger(
                            DESK_ROOT,
                            bot="sports-gap",
                            ticker=str(p.get("ticker") or ""),
                            side=str(p.get("side") or ""),
                            price=bid,
                            contracts=clip,
                            fee=fee(bid) if bid else 0.0,
                            pnl=pnl,
                            fill_id=str(p.get("fill_id") or ""),
                            kind="scale_out",
                            note=reason[:120],
                        )
                        desk_living.record_completion(
                            DESK_ROOT,
                            bot="sports-gap",
                            ticker=str(p.get("ticker") or ""),
                            side=str(p.get("side") or ""),
                            pnl=pnl,
                            contracts=clip,
                            fill_id=str(p.get("fill_id") or ""),
                            kind="scale_out",
                            eligible=True,
                            note=reason[:120],
                        )
                        desk_phase2.remember_scale_out(
                            DESK_ROOT,
                            bot="sports-gap",
                            ticker=str(p.get("ticker") or ""),
                            plan={
                                "league": p.get("league"),
                                "side": p.get("side"),
                                "clip": clip,
                                "runner": int(p.get("contracts") or 0),
                                "bid": round(float(bid), 4),
                                "pnl": pnl,
                                "fair": round(float(fair), 4),
                                "fair_at_entry": p.get("fair_at_entry"),
                                "reason": reason[:120],
                            },
                        )
                    except Exception:
                        pass
                    lines.append(
                        f"| {ts} | {p['league']} | {p['game']} | {info['score']} | {fair:.1%} ({p['team']}) | | | | "
                        f"**PAPER SELL** {clip} @ bid {bid:.2f} ({reason}), P&L ${pnl:+.2f}; "
                        f"{p['contracts']} runner left |"
                    )
                    summary_out["closes"].append(f"SCALE {p.get('ticker')} pnl {pnl:+.2f}")
                    still.append(p)
                    continue
                exit_reason = f"scale-out +{SCALE_OUT_FAIR_MOVE*100:.0f}¢ fair (full)"
            if exit_reason and bid is not None and bid > 0:
                proceeds = round(p["contracts"] * (bid - fee(bid)), 2)
                pnl = round(proceeds - p["cost"], 2)
                s["cash"] = round(s["cash"] + proceeds, 2)
                fair_exit = round(fair, 4) if fair is not None else None
                p.update({"closed": ts, "exit": exit_reason, "exit_price": bid, "payout": proceeds,
                          "pnl": pnl, "fair_at_exit": fair_exit})
                record_close(
                    p,
                    cash=s["cash"],
                    exit_name=exit_reason,
                    bid=bid,
                    stake=p.get("risk") if p.get("risk") is not None else p.get("cost"),
                    exit_fee=fee(bid),
                )
                s["closed"].append(p)
                if p.get("game_key"):
                    exited_this_check.add(p.get("game_key"))
                # Adverse cool-off when mark dropped hard vs entry ask.
                try:
                    if DESK_ROOT not in sys.path:
                        sys.path.insert(0, DESK_ROOT)
                    import desk_roi_plan
                    desk_roi_plan.record_adverse_fill(
                        DESK_ROOT,
                        bot="sports-gap",
                        ticker=str(p.get("ticker") or ""),
                        entry_price=p.get("entry_price"),
                        mark_price=bid,
                        note=str(exit_reason or "")[:120],
                    )
                    why = str(exit_reason or "").lower()
                    if any(k in why for k in ("hard-stop", "model-flip", "stop", "gap-decay")):
                        desk_roi_plan.record_anti_revenge(
                            DESK_ROOT,
                            bot="sports-gap",
                            ticker=str(p.get("ticker") or ""),
                            reason=str(exit_reason or "stop")[:80],
                            note=str(exit_reason or "")[:120],
                        )
                    desk_roi_plan.record_fee_ledger(
                        DESK_ROOT,
                        bot="sports-gap",
                        ticker=str(p.get("ticker") or ""),
                        side=str(p.get("side") or ""),
                        price=bid,
                        contracts=p.get("contracts"),
                        fee=fee(bid) if bid else 0.0,
                        pnl=pnl,
                        fill_id=str(p.get("fill_id") or ""),
                        kind="sell",
                        note=str(exit_reason or "")[:120],
                    )
                    try:
                        import desk_living
                        import teller_memory
                        desk_living.record_completion(
                            DESK_ROOT,
                            bot="sports-gap",
                            ticker=str(p.get("ticker") or ""),
                            side=str(p.get("side") or ""),
                            pnl=pnl,
                            contracts=p.get("contracts"),
                            fill_id=str(p.get("fill_id") or ""),
                            kind="sell",
                            eligible=True,
                            note=str(exit_reason or "")[:120],
                        )
                        teller_memory.remember(
                            DESK_ROOT,
                            kind="wins" if float(pnl) > 0 else "mistakes",
                            text=(
                                f"sports-gap {p.get('ticker')} {exit_reason} "
                                f"pnl {float(pnl):+.2f}"
                            )[:200],
                            bot_id="sports-gap",
                        )
                    except Exception:
                        pass
                except Exception:
                    pass
                if desk is not None:
                    desk.record_learning(DESK_ROOT, {
                        "reason": str(exit_reason or "")[:120],
                        "market": p.get("league") or "",
                        "bucket": desk.prob_bucket(p.get("fair_at_entry")),
                        "stake": p.get("risk") if p.get("risk") is not None else p.get("cost"),
                        "fill_id": p.get("fill_id") or "",
                        "side": p.get("side") or "",
                        "at": ts,
                    })
                try:
                    if DESK_ROOT not in sys.path:
                        sys.path.insert(0, DESK_ROOT)
                    import desk_more
                    # Prefer-1: mid-open wipe fair must not invent line CLV
                    # (settle path already densifies; #446 walkback may miss).
                    close_fair = None
                    clv_kind = "line"
                    if fair is not None:
                        try:
                            ff = float(fair)
                        except (TypeError, ValueError):
                            ff = None
                        if ff is not None and 0.0 < ff < 1.0:
                            close_fair = ff
                    if close_fair is None:
                        for key in ("last_fair", "last_mark"):
                            if p.get(key) is None:
                                continue
                            try:
                                mf = float(p.get(key))
                            except (TypeError, ValueError):
                                continue
                            if 0.0 < mf < 1.0:
                                close_fair = mf
                                break
                    if close_fair is None and fair is not None:
                        try:
                            close_fair = float(fair)
                            clv_kind = "binary"
                        except (TypeError, ValueError):
                            close_fair = None
                    if close_fair is not None:
                        desk_more.record_sports_clv(
                            DESK_ROOT,
                            ticker=str(p.get("ticker") or ""),
                            side=str(p.get("side") or ""),
                            fair_entry=p.get("fair_at_entry"),
                            fair_exit=close_fair,
                            close_fair=close_fair,
                            pnl=pnl,
                            league=str(p.get("league") or ""),
                            exit_reason=str(exit_reason or "sell"),
                            clv_kind=clv_kind,
                        )
                except Exception:
                    pass
                fair_txt = f"{fair:.1%}" if fair is not None else "n/a"
                lines.append(f"| {ts} | {p['league']} | {p['game']} | {info['score']} | {fair_txt} ({p['team']}) | | | | **PAPER SELL** {p['contracts']} @ bid {bid:.2f} ({exit_reason}), P&L ${pnl:+.2f} |")
                summary_out["closes"].append(f"SELL {p['ticker']} pnl {pnl:+.2f}")
                continue
        still.append(p)
    s["open"] = still
    open_by_game = {p["game_key"]: p for p in s["open"]}
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_roi_plan
        # #502 stage densify: espn / kalshi fetch walls (plus existing evaluate/exit).
        if espn_secs > 0:
            desk_roi_plan.record_latency(
                DESK_ROOT, bot="sports-gap",
                seconds=espn_secs, note="sports-gap espn fetch", stage="espn",
            )
        if kalshi_secs > 0:
            desk_roi_plan.record_latency(
                DESK_ROOT, bot="sports-gap",
                seconds=kalshi_secs, note="sports-gap kalshi fetch", stage="kalshi",
            )
        desk_roi_plan.record_latency(
            DESK_ROOT, bot="sports-gap",
            seconds=time.perf_counter() - t0,
            note="sports-gap exits", stage="exit",
        )
        desk_roi_plan.record_latency(
            DESK_ROOT, bot="sports-gap",
            seconds=time.perf_counter() - t0,
            note=f"sports-gap evaluate n={len(buy_candidates)}", stage="evaluate",
        )
    except Exception:
        pass

    # ---- paper buys after exits, capped by desk open risk ----
    # Rank-then-buy: spend open-risk on highest fee-aware gaps first.
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_brain
        for c in buy_candidates:
            c["edge"] = c.get("gap")
            c["confidence"] = c.get("fair")
            c["depth"] = None
            # Top25 #2 — CLV-aware sports score when we have avg CLV history.
            try:
                if DESK_ROOT not in sys.path:
                    sys.path.insert(0, DESK_ROOT)
                import desk_more
                import desk_top25
                clv_avg = (desk_more.clv_summary(DESK_ROOT) or {}).get("avg_clv")
                base = float(desk_top25.sports_rank_score(
                    c.get("gap"), c.get("fair"), clv=clv_avg, depth=None,
                ) or 0)
                # Tip-alarm boost: T−5 > T−15 > none (still must clear fee gap).
                alarm = c.get("tip_alarm")
                boost = 0.15 if alarm == 5 else (0.08 if alarm == 15 else 0.0)
                c["_brain_score"] = base + boost
            except Exception:
                pass
        buy_candidates = desk_brain.rank_candidates(buy_candidates)
        # Prefer precomputed CLV-adjusted scores when present.
        if any(c.get("_brain_score") is not None for c in buy_candidates):
            buy_candidates = sorted(
                buy_candidates, key=lambda c: -float(c.get("_brain_score") or 0),
            )
    except Exception:
        desk_brain = None
        buy_candidates = sorted(buy_candidates, key=lambda c: -float(c.get("gap") or 0))

    # Cross-tower firm queue: offer sports fits, then defer if desk risk
    # is reserved for a higher btc/commodity score.
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_roi_plan
        firm_offers = []
        for c in buy_candidates:
            m0 = c.get("m") or {}
            firm_offers.append({
                "bot": "sports-gap",
                "ticker": str(m0.get("ticker") or c.get("key") or ""),
                "side": c.get("side"),
                "edge": c.get("gap") if c.get("gap") is not None else c.get("edge"),
                "confidence": c.get("fair") if c.get("fair") is not None else c.get("confidence"),
                "depth": c.get("depth"),
                "stake_est": 25.0,
            })
        desk_roi_plan.offer_firm_candidates(
            DESK_ROOT, firm_offers, bot="sports-gap",
        )
        local_open = sum(
            float(p.get("risk") if p.get("risk") is not None else p.get("cost") or 0)
            for p in s["open"]
        )
        # E1 #116 — firm queue remaining uses desk-wide headroom, not sports-local only.
        head = desk_roi_plan.desk_open_risk_headroom(
            DESK_ROOT,
            local_bot="sports-gap",
            local_open_risk=local_open,
            max_open_risk=max_open_risk,
        )
        desk_roi_plan.rebuild_firm_queue(
            DESK_ROOT,
            remaining_risk=float(head.get("remaining") or 0.0),
            note="sports-gap firm offer (desk-wide risk)",
        )
    except Exception:
        pass

    buys_this_check = 0
    # Selective volume when green; ROI rescue caps when red — fee floors unchanged.
    # green_boost stays 0 until sports_green_boost_status ready (2w M1≥0 + CLV bar).
    # E4: kill selective +1 if taxed EV worsens over 5 green Chicago days.
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_more
        import desk_roi_plan
        boost = int(desk_roi_plan.sports_green_boost(DESK_ROOT))
        if red_pnl is not None and float(red_pnl) >= 0:
            top = buy_candidates[0] if buy_candidates else {}
            desk_roi_plan.record_selective_attempt(
                DESK_ROOT,
                "sports-gap",
                edge=(top or {}).get("gap"),
                z=None,
                depth=None,
                league=(top or {}).get("league"),
                today=red_pnl,
                boosted=bool(boost),
                note="selective +1 path considered",
            )
        if desk_roi_plan.selective_kill_active(DESK_ROOT, "sports-gap"):
            max_buys_eff = int(MAX_BUYS_PER_CHECK)
            print("Selective +1 KILLED (5 green-day EV worsen) — base max_buys only")
        else:
            max_buys_eff = int(
                desk_more.selective_max_buys(
                    "sports-gap", base=MAX_BUYS_PER_CHECK, today=red_pnl, green_boost=boost,
                )
            )
        if boost and max_buys_eff > MAX_BUYS_PER_CHECK:
            print(f"Sports green_boost={boost} (CLV+M1 gate ready; fee floors locked)")
    except Exception:
        max_buys_eff = int(MAX_BUYS_PER_CHECK)
    if red_pnl < 0:
        max_buys_eff = min(max_buys_eff, 2)
    if red_pnl <= -10:
        max_buys_eff = min(max_buys_eff, 1)
    # Adverse cool-off after fast mark-downs (ROI plan Phase 4).
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_roi_plan
        def _densify_gate_skip(reason: str, *, note: str) -> None:
            """CARD prepend + brain densify for buy-loop gate locks (#519 sibling)."""
            skips = summary_out.setdefault("skips", [])
            skips.insert(0, reason)
            if desk_brain is not None:
                try:
                    desk_brain.record_decision(
                        DESK_ROOT, bot="sports-gap", action="skip",
                        reasons=[reason], note=note,
                    )
                except Exception:
                    pass

        cool = desk_roi_plan.adverse_cool_blocks(DESK_ROOT, "sports-gap")
        if cool:
            lines.append(f"| {ts} | | | | | | | | {cool} |")
            # Prepend so CARD densifies cool ahead of evaluate noise (#519 leftover).
            _densify_gate_skip(cool, note="sports adverse-cool densify")
            max_buys_eff = 0
        stale = desk_roi_plan.stale_world_blocks(DESK_ROOT, "sports-gap")
        if stale:
            lines.append(f"| {ts} | | | | | | | | {stale} |")
            # Prepend so CARD densifies stale ahead of evaluate noise (#519 leftover).
            _densify_gate_skip(stale, note="sports stale-world densify")
            max_buys_eff = 0
        # Prefer-1: densify real entry_gate / daily-loss reason (BTC/CMD #531 twin).
        if entries_off:
            lines.append(f"| {ts} | | | | | | | | {entries_off} |")
            _densify_gate_skip(entries_off, note="sports entry-gate densify")
            max_buys_eff = 0
        r_block = desk_roi_plan.daily_r_blocks("sports-gap", red_pnl)
        if r_block:
            lines.append(f"| {ts} | | | | | | | | {r_block} |")
            # Prepend so CARD/why densify settle-only ahead of evaluate/cool noise (#482 twin).
            # Settle-only insert last so it stays skips[0] over cool/stale/entry.
            _densify_gate_skip(r_block, note="sports daily-r densify")
            max_buys_eff = 0
    except Exception:
        pass
    for c in buy_candidates:
        key, m, fair, ask, bid, gap = c["key"], c["m"], c["fair"], c["ask"], c["bid"], c["gap"]
        row, gtxt = c["row"], c["gtxt"]
        reason = None
        if buys_this_check >= max_buys_eff:
            # Prefer-1: gate (settle-only / cool / stale / entry / ruin) zeroed the cap —
            # do not invent capacity skip into brain while CARD names the gate.
            gate_keys = (
                "settle-only", "adverse cool", "stale-world", "clock-skew",
                "entry_gate", "ruin drill", "daily loss",
                "max open risk", "max open positions",
            )
            gate_hits = [
                str(s)
                for s in (summary_out.get("skips") or [])
                if any(k in str(s).lower() for k in gate_keys)
            ]
            gate_lock = max_buys_eff == 0 and bool(gate_hits)
            if gate_lock:
                gate_why = next(
                    (s for s in gate_hits if "settle-only" in s.lower()),
                    gate_hits[0],
                )
                lines.append(row + gtxt + f" | {gate_why} |")
                continue
            reason = f"max buys this check ({max_buys_eff})"
        elif red_pnl < 0 and str(c.get("lane") or "") == "speed":
            reason = f"speed lane off on red sports book (red ${red_pnl:.2f})"
        elif replacement_block(key, open_by_game, exited_this_check):
            reason = replacement_block(key, open_by_game, exited_this_check)
        elif len(s["open"]) >= max_open:
            reason = "max open positions"
        local_open_risk = sum(
            float(p.get("risk") if p.get("risk") is not None else p.get("cost") or 0)
            for p in s["open"]
        )
        # E1 #116 — desk-wide open risk (BTC+commodity+…) + sports local.
        open_risk = local_open_risk
        try:
            if DESK_ROOT not in sys.path:
                sys.path.insert(0, DESK_ROOT)
            import desk_roi_plan as _drp_risk
            _head = _drp_risk.desk_open_risk_headroom(
                DESK_ROOT,
                local_bot="sports-gap",
                local_open_risk=local_open_risk,
                max_open_risk=max_open_risk,
            )
            open_risk = float(_head.get("used") or local_open_risk)
        except Exception:
            open_risk = local_open_risk
        if reason is None and desk is not None:
            try:
                blocked = desk.correlation_blocks(DESK_ROOT, "sports-gap", c["side"], gap)
                if blocked:
                    reason = blocked
            except Exception:
                pass
        if reason is None:
            try:
                if DESK_ROOT not in sys.path:
                    sys.path.insert(0, DESK_ROOT)
                import desk_roi_plan
                revenge = desk_roi_plan.anti_revenge_blocks(
                    DESK_ROOT, "sports-gap", str(m.get("ticker") or ""),
                )
                if revenge:
                    reason = revenge
                if reason is None:
                    firm_block = desk_roi_plan.firm_queue_blocks(
                        DESK_ROOT, "sports-gap", str(m.get("ticker") or ""),
                    )
                    if firm_block:
                        reason = firm_block
            except Exception:
                pass
        # E1 #136/#137 — red-day sticky opens get exit priority before new buys.
        if reason is None:
            try:
                if DESK_ROOT not in sys.path:
                    sys.path.insert(0, DESK_ROOT)
                import desk_more
                sticky_bots = [{
                    "id": "sports-gap",
                    "positions": list(s.get("open") or []),
                }]
                sticky_block = desk_more.sticky_entry_blocks(
                    "sports-gap",
                    today=red_pnl,
                    bots=sticky_bots,
                )
                if sticky_block:
                    reason = sticky_block
            except Exception:
                pass
        spread = None
        try:
            if bid is not None and ask is not None:
                spread = abs(float(ask) - float(bid))
        except (TypeError, ValueError):
            spread = None
        stake = stake_for_model(
            fair, desk, cfg, edge=gap, open_risk_used=open_risk, ask=ask,
            spread=spread, ticker=str(m.get("ticker") or ""),
        )
        per = ask + fee(ask)
        if desk is not None:
            try:
                n = desk.contracts_for_stake(per, stake)
            except Exception:
                n = int(stake // per) if per > 0 else 0
        else:
            n = int(stake // per) if per > 0 else 0
        cost = round(n * per, 2) if n >= 1 else 0.0
        if reason is None and n >= 1 and (c.get("tip_window") or c.get("tip_alarm") is not None):
            try:
                if DESK_ROOT not in sys.path:
                    sys.path.insert(0, DESK_ROOT)
                import desk_roi_plan as _tip_sized
                _tip_sized.record_tip_funnel(DESK_ROOT, str(c.get("league") or ""), "sized")
            except Exception:
                pass
        if reason is None and (n < 1 or cost > s["cash"] + 1e-9):
            reason = "not enough paper cash"
        if reason is None:
            try:
                if DESK_ROOT not in sys.path:
                    sys.path.insert(0, DESK_ROOT)
                import desk_roi_plan
                desk_block = desk_roi_plan.desk_open_risk_blocks(
                    DESK_ROOT,
                    local_bot="sports-gap",
                    local_open_risk=local_open_risk,
                    add_cost=cost,
                    max_open_risk=max_open_risk,
                )
                if desk_block:
                    reason = desk_block
            except Exception:
                if open_risk + cost > max_open_risk + 1e-9:
                    reason = (
                        f"max open risk (${open_risk:.2f} + ${cost:.2f} > "
                        f"${max_open_risk:.2f})"
                    )
        fill_check = None
        if reason is None:
            try:
                if DESK_ROOT not in sys.path:
                    sys.path.insert(0, DESK_ROOT)
                import strict_fill
                fill_check = strict_fill.recheck(
                    m.get("ticker"), c.get("side") or "YES", ask, n, fee_per=fee,
                    edge=gap, min_edge=float(c.get("need") or need_edge or 0.0),
                )
            except ImportError:
                fill_check = None
            if fill_check is not None:
                if not fill_check["ok"]:
                    reason = fill_check["reason"]
                else:
                    gap = round(float(gap) - (fill_check["ask"] - ask) - (fee(fill_check["ask"]) - fee(ask)), 4)
                    ask = fill_check["ask"]
                    n = int(fill_check["contracts"])
                    cost = round(n * (ask + fee(ask)), 2)
                    if cost > s["cash"] + 1e-9:
                        reason = "not enough paper cash"
        if reason is None:
            fill_id = f"{m['ticker']}|{ts}"
            if any(str(p.get("fill_id") or "") == fill_id for p in s.get("open") or []):
                reason = "already holding this fill"
            else:
                try:
                    write_buy_intent(
                        fill_id=fill_id,
                        ticker=m.get("ticker"),
                        side=c.get("side"),
                        contracts=n,
                        stake=cost,
                        ask=ask,
                    )
                except Exception as exc:
                    reason = f"buy intent not written ({type(exc).__name__})"
        if reason:
            lines.append(row + gtxt + f" | {reason} |")
            summary_out["skips"].append(reason)
            # Soft near-miss on late buy-path skips (mirror early eval path).
            try:
                if DESK_ROOT not in sys.path:
                    sys.path.insert(0, DESK_ROOT)
                import desk_more as _nm_buy
                why = str(reason or "").lower()
                if any(k in why for k in ("gap", "edge", "fair", "speed floor")):
                    nm = _nm_buy.is_near_miss(
                        reasons=[reason],
                        z=None,
                        p=fair,
                        edge=gap,
                        min_edge=float(c.get("need") or need_edge or 0.06),
                    )
                    if nm.get("near_miss"):
                        _nm_buy.record_near_miss(DESK_ROOT, {
                            "bot": "sports-gap",
                            "ticker": m.get("ticker"),
                            "side": "YES",
                            "soft": nm.get("soft"),
                            "p": fair,
                            "edge": gap,
                            "ask": ask,
                            "note": f"sports buy-skip {nm.get('note')}",
                            "league": c.get("league"),
                        })
            except Exception:
                pass
            if desk_brain is not None:
                try:
                    desk_brain.record_decision(
                        DESK_ROOT, bot="sports-gap", action="skip",
                        ticker=str(m.get("ticker") or ""), side=str(c.get("side") or ""),
                        edge=gap, confidence=fair, reasons=[reason],
                        score=c.get("_brain_score"),
                    )
                except Exception:
                    pass
            try:
                if DESK_ROOT not in sys.path:
                    sys.path.insert(0, DESK_ROOT)
                import desk_roi_plan
                import desk_living
                desk_roi_plan.record_fit(
                    DESK_ROOT, bot="sports-gap", outcome="block",
                    ticker=str(m.get("ticker") or ""), side=str(c.get("side") or ""),
                    edge=gap, note=str(reason)[:160],
                )
                desk_living.record_eval_features(
                    DESK_ROOT,
                    bot="sports-gap",
                    action="skip",
                    ticker=str(m.get("ticker") or ""),
                    series=str(c.get("series") or ""),
                    ev={
                        "side": c.get("side"),
                        "ask": ask,
                        "bid": bid,
                        "fee": fee(ask) if ask else None,
                        "confidence": fair,
                        "edge": gap,
                        "lane": c.get("lane"),
                        "ticker": m.get("ticker"),
                    },
                    reasons=[reason],
                    note=str(reason)[:160],
                )
                why = str(reason or "").lower()
                if any(k in why for k in ("max buys", "max open risk", "budget", "open risk")):
                    desk_roi_plan.note_pending_high_edge(
                        DESK_ROOT,
                        bot="sports-gap",
                        ticker=str(m.get("ticker") or ""),
                        edge=gap,
                        reason=str(reason)[:120],
                    )
                if c.get("tip_window") or c.get("tip_alarm") is not None:
                    if any(k in why for k in ("max buys", "max open risk", "budget", "open risk", "cash")):
                        desk_roi_plan.record_tip_funnel(
                            DESK_ROOT, str(c.get("league") or ""), "block_budget",
                        )
                    elif any(k in why for k in ("gap", "edge", "fair", "spread", "price")):
                        desk_roi_plan.record_tip_funnel(
                            DESK_ROOT, str(c.get("league") or ""), "block_edge",
                        )
            except Exception:
                pass
            continue
        s["cash"] = round(s["cash"] - cost, 2)
        max_payout = round(n * 1.0, 2)
        reward = round(max_payout - cost, 2)
        ratio = round(reward / cost, 4) if cost else None
        lane = str(c.get("lane") or "accurate")
        why = (
            f"Paper buy ({lane} lane). The fair price beat the ask by "
            f"{gap * 100:.1f} points after the fee."
        )
        try:
            import desk_profit
            risk_factor = desk_profit.risk_factor_for("sports-gap", c["side"])
        except Exception:
            risk_factor = ""
        try:
            if DESK_ROOT not in sys.path:
                sys.path.insert(0, DESK_ROOT)
            import desk_roi_plan as _exit_plan_mod
            exit_plan = _exit_plan_mod.default_exit_plan("sports-gap")
        except Exception:
            exit_plan = {
                "kind": "gap_decay+scale_out+hard_stop_shadow+time_final_shadow+settle",
                "hard_stop_shadow": True,
                "time_final_shadow": True,
                "settle_backstop": True,
                "fee_floors_locked": True,
            }
        pos = {"game_key": key, "league": c["league"], "game": c["name"], "ticker": m["ticker"], "team": m.get("yes_sub_title"),
               "side": c["side"], "contracts": n, "entry_price": ask, "bid": bid, "ask": ask, "entry_fee": fee(ask),
               "fee": fee(ask), "cost": cost, "risk": cost, "reward": reward, "risk_reward": ratio,
               "max_payout": max_payout, "why": why, "lane": lane,
               "fair_at_entry": round(fair, 4), "gap_at_entry": round(gap, 4),
               "risk_factor": risk_factor,
               "opened": ts, "score_at_entry": c["score"], "espn_id": c["g"]["id"], "espn_path": c["path"],
               "price_source": f"{KALSHI}/markets?series_ticker={c['series']}",
               "price_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "fill_id": fill_id,
               "exit_plan": exit_plan}
        if fill_check is not None:
            strict_fill.stamp(pos, fill_check)
        s["open"].append(pos)
        open_by_game[key] = pos
        buys_this_check += 1
        lines.append(
            row + gtxt
            + f" | **PAPER BUY** [{lane}] {n} YES {m.get('yes_sub_title')} @ {ask:.2f} "
            + f"(+fee {fee(ask):.2f}) = ${cost:.2f} |"
        )
        summary_out["trades"].append(f"BUY [{lane}] {n}x {m['ticker']} @ {ask:.2f} gap {gap*100:.1f}")
        if desk_brain is not None:
            try:
                note = desk_brain.explain_buy(
                    "sports-gap", c["side"], m["ticker"], gap, fair, None,
                )
                desk_brain.record_decision(
                    DESK_ROOT, bot="sports-gap", action="buy",
                    ticker=str(m.get("ticker") or ""), side=str(c.get("side") or ""),
                    edge=gap, confidence=fair, score=c.get("_brain_score"), note=note,
                )
            except Exception:
                pass
        try:
            if DESK_ROOT not in sys.path:
                sys.path.insert(0, DESK_ROOT)
            import desk_roi_plan
            import desk_living
            desk_roi_plan.record_fit(
                DESK_ROOT, bot="sports-gap", outcome="buy",
                ticker=str(m.get("ticker") or ""), side=str(c.get("side") or ""),
                edge=gap,
            )
            desk_living.record_eval_features(
                DESK_ROOT,
                bot="sports-gap",
                action="buy",
                ticker=str(m.get("ticker") or ""),
                series=str(c.get("series") or ""),
                ev={
                    "side": c.get("side"),
                    "ask": ask,
                    "bid": bid,
                    "fee": fee(ask) if ask else None,
                    "confidence": fair,
                    "edge": gap,
                    "lane": lane,
                    "ticker": m.get("ticker"),
                    "fill_id": pos.get("fill_id"),
                },
                note=why[:160],
            )
            desk_roi_plan.flush_opp_cost_on_buy(
                DESK_ROOT,
                bot="sports-gap",
                ticker=str(m.get("ticker") or ""),
                edge=gap,
            )
            if c.get("tip_window") or c.get("tip_alarm") is not None:
                desk_roi_plan.record_tip_funnel(
                    DESK_ROOT, str(c.get("league") or ""), "bought",
                )
        except Exception:
            pass

    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_roi_plan
        desk_roi_plan.record_latency(
            DESK_ROOT, bot="sports-gap",
            seconds=time.perf_counter() - t0,
            note=f"sports-gap buys={buys_this_check}", stage="buy",
        )
    except Exception:
        pass

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
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_roi_plan
        desk_roi_plan.record_latency(
            DESK_ROOT, bot="sports-gap", seconds=time.perf_counter() - t0,
            note="sports-gap check", stage="loop",
        )
    except Exception:
        pass
    print(_card_line(summary_out))
    # Always densify evaluate rows into paper_trades — book-unchanged ticks used
    # to return before log(), leaving matched>0 with skips=[] and a stale md log.
    log(lines)
    if before_book != after_book:
        save_state(s)
    print(json.dumps(summary_out, indent=2))

if __name__ == "__main__":
    if "--reset" in sys.argv:
        for f in (STATE, LOG):
            if os.path.islink(f):
                target = os.path.realpath(f)
                os.remove(f)
                if os.path.isfile(target):
                    os.remove(target)
            elif os.path.exists(f):
                os.remove(f)
        print("Paper state reset to $%.2f" % START_BANKROLL); sys.exit()
    try:
        run()
    except Exception as exc:
        # Never leave the desk card as a raw Traceback — exits still matter next tick.
        import traceback
        traceback.print_exc()
        print(f"CARD: Sports check error ({type(exc).__name__}). Buys skipped this tick.")
        sys.exit(1)
