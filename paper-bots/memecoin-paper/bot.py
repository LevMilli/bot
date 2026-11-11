"""Paper-only Solana meme coin desk. One run = manage open paper positions, then scan for entries.

NO wallets, NO keys, NO real trades. Every price/liquidity/score comes from a live API response:
  - DexScreener public API (prices, liquidity, pair age, volume, txns)
  - RugCheck public API (risk score, LP locked %, holders, creator balance, insiders)
If a fact can't be fetched, the check FAILS CLOSED (SKIP). If a held position can't be priced,
we HOLD and log it -- we never invent a price.
"""
import csv, json, os, sys, time, uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
import config as C

CT = ZoneInfo("America/Chicago")

BASE = os.path.dirname(os.path.abspath(__file__))
P_LOG, P_POS, P_TRADES = (os.path.join(BASE, f) for f in (C.LOG, C.POSITIONS, C.TRADES))
DS = "https://api.dexscreener.com"
RC = "https://api.rugcheck.xyz/v1"
S = requests.Session()
S.headers["User-Agent"] = "memecoin-desk-paper/1.0"
RUN_ID = uuid.uuid4().hex[:8]
NOW = time.time()
STATUS = {}  # data source -> "ok" / error text


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def today_local():
    """Chicago calendar day for trades_today / daily halt (living upgrade P0)."""
    return datetime.now(CT).date().isoformat()


# ------------------------------------------------------------------ HTTP
def get_json(url, source, pause):
    last = None
    for attempt in range(C.HTTP["retries"] + 1):
        try:
            r = S.get(url, timeout=C.HTTP["timeout_sec"])
            time.sleep(pause)
            if r.status_code == 429:
                last = "429 rate limited"
                time.sleep(pause * 5 * (attempt + 1))
                continue
            if r.status_code != 200:
                last = f"HTTP {r.status_code}"
                if r.status_code in (401, 403, 404):
                    break
                continue
            STATUS.setdefault(source, "ok")
            return r.json()
        except Exception as exc:  # network / JSON errors; keep the URL out of the log
            last = type(exc).__name__
    STATUS[source + " (last error)"] = last
    return None


def ds(path):
    return get_json(DS + path, "dexscreener", C.HTTP["dexscreener_pause_sec"])


def rc_report(mint):
    return get_json(f"{RC}/tokens/{mint}/report", "rugcheck", C.HTTP["rugcheck_pause_sec"])


# ------------------------------------------------------------------ state
def load_state():
    if os.path.exists(P_POS):
        with open(P_POS) as f:
            return json.load(f)
    return {"cash_usd": C.START_BANKROLL_USD, "open": [], "cooldown": {}, "realized_pnl_usd": 0.0}


def save_state(st):
    path = P_POS
    if os.path.islink(path):
        path = os.path.realpath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, indent=2)
    os.replace(tmp, path)


TRADE_COLS = ["ts", "run_id", "side", "mint", "symbol", "pair", "reason", "market_price_usd",
              "fill_price_usd", "tokens", "usd", "fee_usd", "impact_pct", "pnl_usd", "liquidity_usd"]
CHECK_COLS = ["ts", "run_id", "mint", "symbol", "pair", "source",
              "age_min", "age_ok", "liquidity_usd", "liquidity_ok", "ticket_share", "ticket_share_ok",
              "risk_score", "risk_ok", "lp_locked_pct", "lp_locked_ok", "top10_pct", "top10_ok",
              "dev_pct", "dev_ok", "insiders", "insiders_ok", "facts_pass",
              "confidence", "score_detail", "risk_gates_ok", "decision", "reason"]


def append_csv(path, cols, row):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in cols})


def trades_today():
    """(entries today, realized pnl today) from trades.csv, local calendar day."""
    n, pnl, day = 0, 0.0, today_local()
    if os.path.exists(P_TRADES):
        with open(P_TRADES) as f:
            for r in csv.DictReader(f):
                if r["ts"][:10] != day:
                    continue
                if r["side"] == "BUY":
                    n += 1
                elif r["pnl_usd"]:
                    pnl += float(r["pnl_usd"])
    return n, pnl


# ------------------------------------------------------------------ fills (estimate only)
def impact(usd, liq_usd):
    q = liq_usd / 2.0  # one side of the pool
    return usd / (q + usd) if q > 0 else 1.0


def paper_buy(price, liq, usd):
    fee = usd * C.PAPER_FILL["swap_fee_pct"] / 100
    imp = impact(usd - fee, liq)
    tokens = (usd - fee) / price * (1 - imp)
    return tokens, fee, imp, usd / tokens


def paper_sell(price, liq, tokens):
    gross = tokens * price
    imp = impact(gross, liq)
    after_imp = gross * (1 - imp)
    fee = after_imp * C.PAPER_FILL["swap_fee_pct"] / 100
    return after_imp - fee, fee, imp


# ------------------------------------------------------------------ manage open positions
def pair_now(pair_addr):
    d = ds(f"/latest/dex/pairs/solana/{pair_addr}")
    pairs = (d or {}).get("pairs") or []
    if not pairs:
        return None, None
    p = pairs[0]
    try:
        return float(p["priceUsd"]), float((p.get("liquidity") or {}).get("usd"))
    except (KeyError, TypeError, ValueError):
        return None, None


def sell(st, pos, frac_of_original, reason, price, liq, full=False):
    qty = pos["tokens_left"] if full else min(pos["tokens_left"], pos["tokens"] * frac_of_original)
    proceeds, fee, imp = paper_sell(price, liq, qty)
    cost = pos["cost_usd"] * qty / pos["tokens"]
    pnl = proceeds - cost
    pos["tokens_left"] -= qty
    st["cash_usd"] += proceeds
    st["realized_pnl_usd"] += pnl
    pos.setdefault("realized_usd", 0.0)
    pos["realized_usd"] += pnl
    append_csv(P_TRADES, TRADE_COLS, dict(ts=now_iso(), run_id=RUN_ID, side="SELL", mint=pos["mint"],
               symbol=pos["symbol"], pair=pos["pair"], reason=reason, market_price_usd=price,
               fill_price_usd=round(proceeds / qty, 12), tokens=round(qty, 4), usd=round(proceeds, 4),
               fee_usd=round(fee, 4), impact_pct=round(imp * 100, 3), pnl_usd=round(pnl, 4),
               liquidity_usd=liq))
    print(f"  PAPER SELL {pos['symbol']}: {reason} -> ${proceeds:.2f} (pnl ${pnl:+.2f})")
    try:
        desk_root = os.path.dirname(BASE)
        if desk_root not in sys.path:
            sys.path.insert(0, desk_root)
        import desk_roi_plan
        import desk_living
        import teller_memory
        desk_roi_plan.record_fee_ledger(
            desk_root,
            bot="memecoin",
            ticker=str(pos.get("mint") or pos.get("symbol") or ""),
            side="SELL",
            price=price,
            contracts=1.0,
            fee=fee,
            pnl=pnl,
            fill_id=f"{pos.get('mint')}|{pos.get('entry_iso')}",
            kind="sell" if full else "partial_sell",
            note=str(reason or "")[:120],
        )
        if full:
            desk_living.record_completion(
                desk_root,
                bot="memecoin",
                ticker=str(pos.get("mint") or pos.get("symbol") or ""),
                side="SELL",
                pnl=pnl,
                contracts=1.0,
                fill_id=f"{pos.get('mint')}|{pos.get('entry_iso')}",
                kind="sell",
                eligible=False,
                note=str(reason or "")[:120],
            )
            # Near-miss would_pnl densify when mint matches a soft skip.
            try:
                nm_result = "yes" if float(pnl) > 0 else "no"
                desk_roi_plan.label_near_miss_from_result(
                    desk_root,
                    ticker=str(pos.get("mint") or pos.get("symbol") or ""),
                    result=nm_result,
                    bot="memecoin",
                    note="memecoin sell label",
                )
            except Exception:
                pass
            teller_memory.remember(
                desk_root,
                kind="wins" if float(pnl) > 0 else "mistakes",
                text=f"memecoin {pos.get('symbol')} {reason} pnl {float(pnl):+.2f}"[:200],
                bot_id="memecoin",
            )
    except Exception:
        pass
    if full:
        try:
            desk = _desk()
            desk.record_learning(os.path.dirname(BASE), {
                "result": "hit" if pnl > 0 else "miss",
                "market": pos.get("mint") or pos.get("symbol") or "",
                "prob": pos.get("confidence"),
                "stake": pos.get("cost_usd"),
                "fill_id": f"{pos.get('mint')}|{pos.get('entry_iso')}",
                "side": pos.get("lane") or pos.get("side") or "long",
            })
        except Exception:
            pass


def manage(st):
    E = C.EXIT
    still = []
    for pos in st["open"]:
        price, liq = pair_now(pos["pair"])
        if price is None or liq is None:
            print(f"  {pos['symbol']}: no live price/liquidity this run -> HOLD (never invent a price)")
            still.append(pos)
            continue
        pos["last_price"], pos["last_liq"], pos["last_checked"] = price, liq, now_iso()
        pos["peak_price"] = max(pos.get("peak_price", price), price)
        pct = (price / pos["entry_market_price"] - 1) * 100
        held_h = (NOW - pos["entry_ts"]) / 3600
        liq_drop = (1 - liq / pos["entry_liq"]) * 100 if pos["entry_liq"] else 0
        from_peak = (1 - price / pos["peak_price"]) * 100
        print(f"  {pos['symbol']}: {pct:+.1f}% from entry, {from_peak:.1f}% off peak, liq {liq_drop:+.1f}% drop, held {held_h:.2f}h")
        exit_reason = None
        # Model-flip before hard stop: adverse move / momentum collapse.
        floor_m = float(E.get("model_flip_momentum_h1_floor") or -8)
        if pct <= floor_m and pct > float(E["stop_pct"]):
            exit_reason = f"model-flip momentum {pct:.1f}% <= {floor_m:.1f}%"
        if exit_reason is None and liq_drop >= E["liq_drop_pct"]:
            exit_reason = f"liq_drop {liq_drop:.1f}% >= {E['liq_drop_pct']}%"
        elif exit_reason is None and pct <= E["stop_pct"]:
            exit_reason = f"stop {pct:.1f}% <= {E['stop_pct']}%"
        if not exit_reason:
            for i, (lvl, frac) in enumerate(E["ladder"]):
                if pct >= lvl and i not in pos.setdefault("ladder_done", []):
                    sell(st, pos, frac, f"ladder +{lvl}% sells {frac:.0%}", price, liq)
                    pos["ladder_done"].append(i)
            # trailing stop applies to "the rest" = after the first ladder rung has filled
            if pos["ladder_done"] and from_peak >= E["trail_pct"]:
                exit_reason = f"trail {from_peak:.1f}% off peak >= {E['trail_pct']}%"
            elif held_h >= E["time_stop_hours"] and pct < E["time_stop_min_pct"]:
                exit_reason = f"time_stop {held_h:.1f}h and only {pct:+.1f}% < {E['time_stop_min_pct']}%"
        if exit_reason and pos["tokens_left"] > 0:
            sell(st, pos, 1, exit_reason, price, liq, full=True)
        if pos["tokens_left"] <= 1e-12:
            st["cooldown"][pos["mint"]] = NOW
            print(f"  {pos['symbol']}: CLOSED, cooldown {C.COOLDOWN_HOURS}h")
        else:
            still.append(pos)
    st["open"] = still


# ------------------------------------------------------------------ facts
def top_pair(pairs):
    sol = [p for p in pairs if p.get("chainId") == "solana" and (p.get("liquidity") or {}).get("usd")]
    return max(sol, key=lambda p: p["liquidity"]["usd"]) if sol else None


def rug_facts(rep, pair_addr):
    """Return dict of rugcheck facts; None for anything the report doesn't provide (fail closed)."""
    f = {"risk_score": None, "lp_locked_pct": None, "top10_pct": None, "dev_pct": None, "insiders": None}
    if not rep:
        return f
    f["risk_score"] = rep.get("score_normalised")
    markets = rep.get("markets") or []
    m = next((x for x in markets if x.get("pubkey") == pair_addr), None)
    if m is None and markets:  # fall back to biggest market by liquidity
        m = max(markets, key=lambda x: ((x.get("lp") or {}).get("quoteUSD") or 0) + ((x.get("lp") or {}).get("baseUSD") or 0))
    if m and (m.get("lp") or {}).get("lpLockedPct") is not None:
        f["lp_locked_pct"] = m["lp"]["lpLockedPct"]
    # exclude pools, AMMs, lockers from the top-10 count
    known = rep.get("knownAccounts") or {}
    excl = {a for a, v in known.items() if (v or {}).get("type") in ("AMM", "LOCKER")}
    for x in markets:
        for k in ("pubkey", "liquidityA", "liquidityB", "liquidityAAccount", "liquidityBAccount"):
            v = x.get(k)
            if isinstance(v, dict):
                v = v.get("owner") or v.get("pubkey") or v.get("address")
            if isinstance(v, str):
                excl.add(v)
    excl.update((rep.get("lockers") or {}).keys())
    excl.update((rep.get("lockerOwners") or {}).keys())
    holders = rep.get("topHolders")
    if holders is not None:
        clean = [h for h in holders if h.get("owner") not in excl and h.get("address") not in excl]
        f["top10_pct"] = round(sum(h.get("pct") or 0 for h in clean[:10]), 3)
    tok = rep.get("token") or {}
    supply, cb = tok.get("supply"), rep.get("creatorBalance")
    if supply and cb is not None:
        dev = cb / supply * 100
        cr = rep.get("creator")
        for h in holders or []:
            if cr and h.get("owner") == cr:
                dev = max(dev, h.get("pct") or 0)
        f["dev_pct"] = round(dev, 4)
    gi = rep.get("graphInsidersDetected")
    if holders is not None and gi is not None:
        f["insiders"] = int(gi) + sum(1 for h in holders if h.get("insider"))
    return f


# ------------------------------------------------------------------ scorer (free, rule-based)
def lin(x, bad, good):
    if x is None:
        return 0.0
    return max(0.0, min(1.0, (x - bad) / (good - bad)))


def score(pair):
    K = C.SCORER
    pc = pair.get("priceChange") or {}
    h1, m5 = pc.get("h1"), pc.get("m5")
    mom = lin(h1, K["momentum_h1_bad"], K["momentum_h1_good"])
    if (m5 is not None and m5 < K["momentum_m5_floor"]) or (h1 is not None and h1 > K["momentum_h1_too_hot"]):
        mom /= 2
    liq = (pair.get("liquidity") or {}).get("usd") or 0
    v1 = (pair.get("volume") or {}).get("h1")
    vol = lin(v1 / liq if (v1 is not None and liq) else None, K["vol_turnover_bad"], K["vol_turnover_good"])
    lq = lin(liq, K["liq_bad"], K["liq_good"])
    t = (pair.get("txns") or {}).get("h1") or {}
    b, s = t.get("buys"), t.get("sells")
    if b is None or s is None or (b + s) < K["min_txns_h1"]:
        bp = 0.0
    else:
        bp = lin(b / (b + s), K["buy_ratio_bad"], K["buy_ratio_good"])
    parts = {"momentum": mom, "volume": vol, "liquidity": lq, "buy_pressure": bp}
    conf = sum(K["weights"][k] * v for k, v in parts.items())
    return round(conf, 3), {k: round(v, 2) for k, v in parts.items()}


# ===================== OPTIONAL GROK HOOK (DISABLED BY DEFAULT) =====================
# Grok's API is paid (console.x.ai). Off unless config.GROK_ENABLED = True AND the env var
# XAI_API_KEY is set. It can only veto (BUY -> SKIP). Untested here because it costs money.
def grok_veto(pair, facts, conf):
    if not C.GROK_ENABLED:
        return None
    key = os.environ.get("XAI_API_KEY")
    if not key:
        return "grok enabled but XAI_API_KEY not set -> SKIP (fail closed)"
    prompt = ("Answer with JSON {\"decision\":\"BUY\"|\"SKIP\",\"confidence\":0-1}. Solana meme token facts: "
              + json.dumps({"pair": {k: pair.get(k) for k in ("priceChange", "volume", "txns", "liquidity")},
                            "facts": facts, "rule_confidence": conf}))
    try:
        r = requests.post("https://api.x.ai/v1/chat/completions", timeout=C.GROK_TIMEOUT_SEC,
                          headers={"Authorization": f"Bearer {key}"},
                          json={"model": C.MODEL, "messages": [{"role": "user", "content": prompt}]})
        out = json.loads(r.json()["choices"][0]["message"]["content"])
        if out.get("decision") != "BUY" or float(out.get("confidence", 0)) < C.MIN_CONFIDENCE:
            return f"grok veto: {out}"
        return None
    except Exception as e:
        return f"grok error -> SKIP (fail closed): {e}"
# ====================================================================================


# ------------------------------------------------------------------ scan
def candidates():
    found = {}
    for path, tag in (("/token-profiles/latest/v1", "profiles"), ("/token-boosts/latest/v1", "boosts_latest"),
                      ("/token-boosts/top/v1", "boosts_top")):
        d = ds(path)
        if d is None:
            print(f"  source {tag}: FAILED")
            continue
        n = 0
        for t in d if isinstance(d, list) else []:
            if t.get("chainId") == "solana" and t.get("tokenAddress"):
                found.setdefault(t["tokenAddress"], tag)
                n += 1
        print(f"  source {tag}: {n} solana tokens")
    return found


def scan(st, stats):
    F = C.FACTS
    cands = candidates()
    mints = list(cands)
    pairs_by_mint = {}
    for i in range(0, len(mints), 30):  # DexScreener allows up to 30 addresses per call
        d = ds("/tokens/v1/solana/" + ",".join(mints[i:i + 30])) or []
        for p in d:
            m = (p.get("baseToken") or {}).get("address")
            pairs_by_mint.setdefault(m, []).append(p)
    entries_today, pnl_today = trades_today()
    open_mints = {p["mint"] for p in st["open"]}
    stats["candidates"] = len(mints)
    red_lock = float(getattr(C, "RED_DAY_ENTRY_LOCK_USD", 20) or 20)
    max_open_eff = int(C.MAX_OPEN)
    if pnl_today < 0:
        max_open_eff = min(max_open_eff, int(getattr(C, "MAX_OPEN_RED", 2) or 2))
    if pnl_today <= -red_lock:
        print(
            f"  RED-DAY LOCK: today ${pnl_today:.2f} <= −${red_lock:.0f} — "
            "new entries off (exits already ran)"
        )
        stats["red_day_lock"] = 1
        return

    for mint in mints:
        row = {"ts": now_iso(), "run_id": RUN_ID, "mint": mint, "source": cands[mint]}
        stats["checked"] += 1
        pairs = pairs_by_mint.get(mint, [])
        p = top_pair(pairs)
        fails = []

        def record(decision, reason):
            row["decision"], row["reason"] = decision, reason
            append_csv(P_LOG, CHECK_COLS, row)

        if p is None:
            stats["fail:no_dex_pair"] += 1
            record("SKIP", "no Solana pair with reported liquidity on DexScreener (e.g. still on pump.fun bonding curve) -> fail closed")
            continue
        row["symbol"], row["pair"] = (p.get("baseToken") or {}).get("symbol"), p.get("pairAddress")
        created = [x.get("pairCreatedAt") for x in pairs if x.get("pairCreatedAt")]
        age = (NOW * 1000 - min(created)) / 60000 if created else None
        liq = p["liquidity"]["usd"]
        share = C.TICKET_USD / liq if liq else None
        row.update(age_min=None if age is None else round(age, 1), liquidity_usd=liq,
                   ticket_share=None if share is None else round(share, 6))

        def gate(name, value, ok_fn):
            ok = value is not None and ok_fn(value)
            row[name + "_ok"] = "PASS" if ok else ("FAIL" if value is not None else "FAIL(missing)")
            stats[f"{name}:checked"] += 1
            stats[f"{name}:pass"] += ok
            if not ok:
                fails.append(name if value is not None else name + "(missing)")
            return ok

        gate("age", age, lambda a: F["min_age_min"] <= a <= F["max_age_hours"] * 60)
        gate("liquidity", liq, lambda v: v >= F["min_liquidity_usd"])
        gate("ticket_share", share, lambda v: v <= F["max_ticket_share"])
        if fails:  # save RugCheck calls for tokens already out
            for k in ("risk", "lp_locked", "top10", "dev", "insiders"):
                row[k + "_ok"] = "not_checked"
            row["facts_pass"] = "FAIL"
            record("SKIP", "failed: " + ", ".join(fails))
            continue

        rf = rug_facts(rc_report(mint), p.get("pairAddress"))
        stats["rugcheck_calls"] += 1
        row.update(rf)
        gate("risk", rf["risk_score"], lambda v: v <= F["max_risk_score"])
        gate("lp_locked", rf["lp_locked_pct"], lambda v: v >= F["min_lp_locked_pct"])
        gate("top10", rf["top10_pct"], lambda v: v <= F["max_top10_pct"])
        gate("dev", rf["dev_pct"], lambda v: v <= F["max_dev_pct"])
        gate("insiders", rf["insiders"], lambda v: v <= F["max_insiders"])
        row["facts_pass"] = "PASS" if not fails else "FAIL"
        conf, detail = score(p)
        row["confidence"], row["score_detail"] = conf, json.dumps(detail)
        if fails:
            record("SKIP", "failed: " + ", ".join(fails))
            continue
        stats["facts_pass"] += 1
        if conf + 1e-12 >= C.MIN_CONFIDENCE_ACCURATE:
            lane = "accurate"
        elif conf + 1e-12 >= C.MIN_CONFIDENCE_SPEED:
            lane = "speed"
        else:
            skip_reason = f"confidence {conf} < speed floor {C.MIN_CONFIDENCE_SPEED}"
            record("SKIP", skip_reason)
            # Soft-p densify when conf sits in near-miss p band (rare under speed floor).
            try:
                desk_root = os.path.dirname(BASE)
                if desk_root not in sys.path:
                    sys.path.insert(0, desk_root)
                import desk_more as _nm_meme
                nm = _nm_meme.is_near_miss(
                    reasons=[skip_reason],
                    z=None,
                    p=conf,
                    edge=conf_minus_half_residual(conf),
                    min_edge=0.05,
                )
                if nm.get("near_miss"):
                    _nm_meme.record_near_miss(desk_root, {
                        "bot": "memecoin",
                        "ticker": mint or row.get("symbol") or "",
                        "side": "long",
                        "soft": nm.get("soft"),
                        "p": conf,
                        "note": f"meme {nm.get('note')}",
                    })
            except Exception:
                pass
            continue
        if (
            lane == "speed"
            and (
                getattr(C, "SPEED_ONLY_IF_TODAY_NONNEG", True)
                or getattr(C, "ACCURATE_ONLY_WHEN_TODAY_NEG", True)
            )
            and pnl_today < 0
        ):
            record("SKIP", f"speed lane blocked on red day (today ${pnl_today:.2f})")
            continue
        if lane == "speed" and getattr(C, "SPEED_REQUIRE_M5_NONNEG", True):
            try:
                m5_raw = (p.get("priceChange") or {}).get("m5")
                m5_v = float(m5_raw) if m5_raw is not None else None
            except (TypeError, ValueError):
                m5_v = None
            if m5_v is None or m5_v < 0:
                record("SKIP", f"speed lane needs m5 ≥ 0 (have {m5_v})")
                continue
        speed_liq = float(getattr(C, "SPEED_MIN_LIQUIDITY_USD", 50000) or 50000)
        if lane == "speed" and float(liq or 0) + 1e-9 < speed_liq:
            record("SKIP", f"speed lane needs liq >= ${speed_liq:.0f} (have ${float(liq or 0):.0f})")
            continue
        stats["confidence_pass"] += 1
        veto = grok_veto(p, rf, conf)
        if veto:
            record("SKIP", veto)
            continue
        # risk gates
        cd = st["cooldown"].get(mint)
        gate_reason = None
        if mint in open_mints:
            gate_reason = "already open"
        elif cd and NOW - cd < C.COOLDOWN_HOURS * 3600:
            gate_reason = f"cooldown ({(NOW - cd) / 3600:.1f}h < {C.COOLDOWN_HOURS}h)"
        elif len(st["open"]) >= max_open_eff:
            gate_reason = f"MAX_OPEN {max_open_eff} reached"
        elif entries_today >= C.MAX_ENTRIES_PER_DAY:
            gate_reason = f"MAX_ENTRIES_PER_DAY {C.MAX_ENTRIES_PER_DAY} reached"
        elif pnl_today <= -C.DAILY_LOSS_HALT_USD:
            gate_reason = f"daily loss halt (realized today ${pnl_today:.2f})"
        else:
            ticket = ticket_for(st, conf, lane)
            if ticket < C.MIN_TICKET_USD:
                gate_reason = f"paper cash ${st['cash_usd']:.2f} < min ticket ${C.MIN_TICKET_USD}"
            else:
                # Shared learning book can only add a skip. It cannot buy and
                # it cannot lower the DEX floor. Market key is the mint.
                learn_skip = ""
                try:
                    desk = _desk()
                    learn_skip = desk.learning_skip(
                        desk.load_learning(os.path.dirname(BASE)),
                        mint or row.get("symbol") or "",
                        desk.prob_bucket(conf),
                        side=str(lane or "long"),
                        hour_ct=datetime.now(CT).hour,
                    ) or ""
                except Exception:
                    learn_skip = ""
                if learn_skip:
                    gate_reason = learn_skip
                else:
                    # conf−0.5 residual is not fee-aware EV (rt swap ~2%). Refuse like INX
                    # residual-as-edge — stay starved. Fail closed if desk settings missing.
                    try:
                        desk = _desk()
                        venue = float(desk.venue_min_edge("solana_dex", desk.load_settings(os.path.dirname(BASE))))
                        need_venue = venue + (0.02 if lane == "speed" else 0.0)
                    except Exception:
                        need_venue = 0.02 + (0.02 if lane == "speed" else 0.0)
                    gate_reason = refuse_conf_residual_as_edge(
                        conf, lane=str(lane or ""), venue_need=need_venue,
                    )
        row["risk_gates_ok"] = "PASS" if not gate_reason else "FAIL"
        if gate_reason:
            record("SKIP", gate_reason)
            try:
                desk_root = os.path.dirname(BASE)
                if desk_root not in sys.path:
                    sys.path.insert(0, desk_root)
                import desk_more as _nm_meme
                residual = conf_minus_half_residual(conf)
                nm = _nm_meme.is_near_miss(
                    reasons=[gate_reason],
                    z=None,
                    p=conf,
                    edge=residual,
                    min_edge=0.05,
                )
                if nm.get("near_miss"):
                    _nm_meme.record_near_miss(desk_root, {
                        "bot": "memecoin",
                        "ticker": mint or row.get("symbol") or "",
                        "side": str(lane or "long"),
                        "soft": nm.get("soft"),
                        "p": conf,
                        "edge": residual,
                        "note": f"meme {nm.get('note')} · {gate_reason}"[:160],
                    })
            except Exception:
                pass
            try:
                desk_root = os.path.dirname(BASE)
                if desk_root not in sys.path:
                    sys.path.insert(0, desk_root)
                import desk_living
                residual = conf_minus_half_residual(conf)
                desk_living.record_eval_features(
                    desk_root,
                    bot="memecoin",
                    action="skip",
                    series="solana_dex",
                    ev={
                        "ticker": mint or row.get("symbol"),
                        "confidence": conf,
                        "edge": residual,
                        "lane": lane,
                        "depth": liq,
                    },
                    reasons=[gate_reason],
                    note=str(gate_reason)[:160],
                )
            except Exception:
                pass
            continue
        ticket = apply_entry_cuts(ticket_for(st, conf, lane), st, lane, pnl_today)
        if ticket < C.MIN_TICKET_USD:
            if pnl_today < 0:
                red_cap = float(getattr(C, "RED_DAY_TICKET_USD", C.MIN_TICKET_USD) or C.MIN_TICKET_USD)
                record("SKIP", f"red-day ticket ${ticket:.2f} below min after cap ${red_cap:.0f}")
            elif lane == "speed":
                record("SKIP", f"speed-lane ticket below ${C.MIN_TICKET_USD:.0f}")
            else:
                record("SKIP", f"ticket ${ticket:.2f} below min")
            continue
        price = float(p["priceUsd"])
        tokens, fee, imp, fill = paper_buy(price, liq, ticket)
        st["cash_usd"] = round(float(st["cash_usd"]) - ticket, 4)
        pos = dict(mint=mint, symbol=row["symbol"], pair=p["pairAddress"], entry_ts=NOW, entry_iso=now_iso(),
                   entry_market_price=price, entry_fill_price=fill, entry_liq=liq, tokens=tokens,
                   tokens_left=tokens, cost_usd=ticket, risk=ticket,
                   why=f"Paper buy ({lane} lane). Confidence {conf}. Ticket ${ticket:.2f}.",
                   peak_price=price, ladder_done=[],
                   confidence=conf, lane=lane, url=p.get("url"))
        try:
            desk_root = os.path.dirname(BASE)
            if desk_root not in sys.path:
                sys.path.insert(0, desk_root)
            import desk_roi_plan as _xp
            pos["exit_plan"] = _xp.default_exit_plan("memecoin")
        except Exception:
            pos["exit_plan"] = {
                "kind": "stop+model_flip+ladder+settle",
                "stop_pct": -0.12,
                "model_flip_mom": -0.06,
                "ladder_take_profits": True,
                "settle_backstop": True,
                "fee_floors_locked": True,
            }
        st["open"].append(pos)
        open_mints.add(mint)
        entries_today += 1
        stats["entries"] += 1
        append_csv(P_TRADES, TRADE_COLS, dict(ts=now_iso(), run_id=RUN_ID, side="BUY", mint=mint,
                   symbol=row["symbol"], pair=p["pairAddress"], reason=f"conf {conf}", market_price_usd=price,
                   fill_price_usd=fill, tokens=round(tokens, 4), usd=ticket, fee_usd=round(fee, 4),
                   impact_pct=round(imp * 100, 3), liquidity_usd=liq))
        record("BUY", f"PAPER BUY ${ticket:.2f} @ market {price} (fill est {fill:.10g})")
        try:
            desk_root = os.path.dirname(BASE)
            if desk_root not in sys.path:
                sys.path.insert(0, desk_root)
            import desk_living
            residual = conf_minus_half_residual(conf)
            desk_living.record_eval_features(
                desk_root,
                bot="memecoin",
                action="buy",
                series="solana_dex",
                ev={
                    "ticker": mint or row.get("symbol"),
                    "ask": fill,
                    "fee": fee,
                    "confidence": conf,
                    "edge": residual,
                    "lane": lane,
                    "depth": liq,
                },
                note=f"paper buy {lane}",
            )
        except Exception:
            pass
        print(f"  PAPER BUY {row['symbol']} ${ticket:.2f} @ {price} conf {conf}")


def _desk():
    root = os.path.dirname(BASE)
    if root not in sys.path:
        sys.path.insert(0, root)
    import pimp_desk
    return pimp_desk


def round_trip_swap_fee_frac() -> float:
    """Buy + sell paper swap fee as a fraction of notional (never invents a fill)."""
    one = float((C.PAPER_FILL or {}).get("swap_fee_pct") or 0.0) / 100.0
    return max(0.0, 2.0 * one)


def conf_minus_half_residual(conf) -> float:
    """Scorer residual above coin-flip — NOT fee-aware EV."""
    try:
        return max(0.0, float(conf) - 0.5)
    except (TypeError, ValueError):
        return 0.0


def refuse_conf_residual_as_edge(conf, *, lane: str = "", venue_need: float = 0.0) -> str:
    """Stop-bleed honesty: conf−0.5 is not fee-aware edge (1% buy + 1% sell).

    Tower-local sibling of INX residual refuse. Keeps expand_volume false and
    does not soften red lock / −12% stop.
    """
    raw = conf_minus_half_residual(conf)
    rt = round_trip_swap_fee_frac()
    after = max(0.0, raw - rt)
    lane_s = f"; {lane}" if lane else ""
    need_s = f"; need={float(venue_need):.3f}" if venue_need else ""
    return (
        f"refuse conf−0.5 residual {raw:.3f} as fee-aware edge "
        f"(rt_fee={rt:.3f}; after_fee={after:.3f}{need_s}{lane_s}) — starve honesty"
    )


def confidence_buy_in(conf, lane: str = "") -> float:
    """Target dollars before red-day and cash cuts.

    $10 at 80% and on the speed lane, $17.50 at 85%, $25 at 90% and above.
    Linear between 80% and 90%. Speed never outgrows the 80% ticket.
    """
    lo = float(C.MIN_TICKET_USD)
    hi = float(C.TICKET_USD)
    if str(lane or "").lower() == "speed":
        return round(lo, 2)
    try:
        chance = float(conf)
    except (TypeError, ValueError):
        return round(lo, 2)
    p_lo = float(getattr(C, "CONF_P_LO", 0.80) or 0.80)
    p_hi = float(getattr(C, "CONF_P_HI", 0.90) or 0.90)
    if p_hi <= p_lo or chance <= p_lo:
        return round(lo, 2)
    if chance >= p_hi:
        return round(hi, 2)
    t = (chance - p_lo) / (p_hi - p_lo)
    return round(lo + t * (hi - lo), 2)


def ticket_for(st, conf, lane: str = "") -> float:
    """Confidence buy-in, then cash. Red-day ceiling is apply_entry_cuts."""
    cash = float(st.get("cash_usd") or 0)
    if cash + 1e-9 < float(C.MIN_TICKET_USD):
        return 0.0
    dollars = min(confidence_buy_in(conf, lane), cash)
    if dollars + 1e-9 < float(C.MIN_TICKET_USD):
        return 0.0
    return round(dollars, 2)


def apply_entry_cuts(ticket: float, st, lane: str, pnl_today: float) -> float:
    """Red day stays at $10. Speed stays at the $10 / 80% ticket. Cash caps both."""
    cash = float(st.get("cash_usd") or 0)
    try:
        out = float(ticket)
    except (TypeError, ValueError):
        return 0.0
    out = min(out, cash)
    if float(pnl_today) < 0:
        out = min(out, float(getattr(C, "RED_DAY_TICKET_USD", C.MIN_TICKET_USD) or C.MIN_TICKET_USD))
    if str(lane or "").lower() == "speed":
        out = min(out, float(C.MIN_TICKET_USD))
    if out + 1e-9 < float(C.MIN_TICKET_USD):
        return 0.0
    return round(out, 2)


def maybe_reload_broke_cash(st) -> bool:
    """Paper-desk reload when cash cannot fund a minimum ticket and nothing is open.

    Does not invent trades or erase realized PnL — only restores buy capacity.
    """
    if st.get("open"):
        return False
    cash = float(st.get("cash_usd") or 0)
    if cash + 1e-9 >= C.MIN_TICKET_USD:
        return False
    before = cash
    st["cash_usd"] = float(C.START_BANKROLL_USD)
    st["paper_only"] = True
    st["reloaded_at"] = now_iso()
    st["reloaded_from"] = round(before, 2)
    print(f"  PAPER RELOAD cash ${before:.2f} -> ${st['cash_usd']:.2f} (no open positions; min ticket ${C.MIN_TICKET_USD})")
    return True


def main():
    if not C.PAPER:
        sys.exit("PAPER is False. This desk is paper-only and has no wallet. Refusing to run.")
    desk_root = os.path.dirname(BASE)
    try:
        if desk_root not in sys.path:
            sys.path.insert(0, desk_root)
        import desk_living
        blocked = desk_living.honor_desk_entry_gate(desk_root)
        if blocked:
            print(f"Desk entry_gate (CLI honor): {blocked[:160]}")
    except Exception:
        pass
    from collections import Counter
    stats = Counter()
    st = load_state()
    if not os.path.exists(P_POS):
        save_state(st)
    if maybe_reload_broke_cash(st):
        save_state(st)
    print(f"run {RUN_ID} @ {now_iso()}  cash ${st['cash_usd']:.2f}  open {len(st['open'])}")
    print("1) managing open paper positions")
    manage(st)
    save_state(st)
    if os.environ.get("DESK_BLOCK_ENTRIES") == "1":
        # Prefer-1: surface DESK_BLOCK_REASON — do not invent bland entry_gate (#531 twin).
        gate_why = "Desk entry_gate blocked new paper buys (exits above still ran)"
        try:
            import desk_living
            gate_why = desk_living.desk_block_entries_reason(gate_why) or gate_why
        except Exception:
            pass
        print(f"2) scanning skipped — {gate_why}")
        print(
            f"CARD: Managed open paper positions. {gate_why} "
            f"({len(st['open'])} still open)."
        )
        print(f"  cash ${st['cash_usd']:.2f}, open {len(st['open'])}, realized pnl ${st['realized_pnl_usd']:+.2f}")
        return
    print("2) scanning for candidates")
    scan(st, stats)
    save_state(st)
    print("\nsummary:")
    print(f"  tokens checked: {stats['checked']} (no dex pair: {stats['fail:no_dex_pair']}), rugcheck calls: {stats['rugcheck_calls']}")
    for g in ("age", "liquidity", "ticket_share", "risk", "lp_locked", "top10", "dev", "insiders"):
        print(f"  {g:13s} passed {stats[g + ':pass']}/{stats[g + ':checked']}")
    print(f"  all FACTS passed: {stats['facts_pass']}, confidence>= {C.MIN_CONFIDENCE}: {stats['confidence_pass']}, paper entries: {stats['entries']}")
    print(f"  cash ${st['cash_usd']:.2f}, open {len(st['open'])}, realized pnl ${st['realized_pnl_usd']:+.2f}")
    print(f"  data sources: {STATUS}")
    checked = int(stats.get("checked") or 0)
    entries = int(stats.get("entries") or 0)
    word = "token" if checked == 1 else "tokens"
    if entries <= 0:
        print(f"CARD: Checked {checked} Solana {word}. No paper buy.")
    elif entries == 1:
        print(f"CARD: Checked {checked} Solana {word}. Paper buy.")
    else:
        print(f"CARD: Checked {checked} Solana {word}. {entries} paper buys.")


if __name__ == "__main__":
    main()
