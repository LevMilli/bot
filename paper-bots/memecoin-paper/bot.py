"""Paper-only Solana meme coin desk. One run = manage open paper positions, then scan for entries.

NO wallets, NO keys, NO real trades. Every price/liquidity/score comes from a live API response:
  - DexScreener public API (prices, liquidity, pair age, volume, txns)
  - RugCheck public API (risk score, LP locked %, holders, creator balance, insiders)
If a fact can't be fetched, the check FAILS CLOSED (SKIP). If a held position can't be priced,
we HOLD and log it -- we never invent a price.
"""
import csv, json, os, sys, time, uuid
from datetime import datetime, timezone

import requests
import config as C

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
    return datetime.now().astimezone().date().isoformat()


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
    if full:
        try:
            desk = _desk()
            desk.record_learning(os.path.dirname(BASE), {
                "result": "hit" if pnl > 0 else "miss",
                "market": pos.get("mint") or pos.get("symbol") or "",
                "prob": pos.get("confidence"),
                "stake": pos.get("cost_usd"),
                "fill_id": f"{pos.get('mint')}|{pos.get('entry_iso')}",
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
        # Model-flip before hard stop: adverse move / momentum collapse (still above −35%).
        floor_m = float(E.get("model_flip_momentum_h1_floor") or -12)
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
        if conf < C.MIN_CONFIDENCE:
            record("SKIP", f"confidence {conf} < {C.MIN_CONFIDENCE}")
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
        elif len(st["open"]) >= C.MAX_OPEN:
            gate_reason = f"MAX_OPEN {C.MAX_OPEN} reached"
        elif entries_today >= C.MAX_ENTRIES_PER_DAY:
            gate_reason = f"MAX_ENTRIES_PER_DAY {C.MAX_ENTRIES_PER_DAY} reached"
        elif pnl_today <= -C.DAILY_LOSS_HALT_USD:
            gate_reason = f"daily loss halt (realized today ${pnl_today:.2f})"
        else:
            ticket = ticket_for(st, conf)
            if ticket < C.MIN_TICKET_USD:
                gate_reason = f"paper cash ${st['cash_usd']:.2f} < min ticket ${C.MIN_TICKET_USD}"
            else:
                try:
                    desk = _desk()
                    venue = float(desk.venue_min_edge("solana_dex", desk.load_settings(os.path.dirname(BASE))))
                    # Confidence above 0.5 as a crude residual edge vs coin-flip.
                    if max(0.0, float(conf) - 0.5) + 1e-12 < venue:
                        gate_reason = f"venue solana_dex edge {max(0.0, float(conf) - 0.5):.3f} < {venue:.3f}"
                    else:
                        gate_reason = desk.learning_skip(
                            desk.load_learning(os.path.dirname(BASE)),
                            mint or row.get("symbol") or "",
                            desk.prob_bucket(conf),
                        ) or None
                except Exception:
                    gate_reason = None
        row["risk_gates_ok"] = "PASS" if not gate_reason else "FAIL"
        if gate_reason:
            record("SKIP", gate_reason)
            continue
        ticket = ticket_for(st, conf)
        if ticket < C.MIN_TICKET_USD:
            record("SKIP", f"ticket ${ticket:.2f} below min")
            continue
        price = float(p["priceUsd"])
        tokens, fee, imp, fill = paper_buy(price, liq, ticket)
        st["cash_usd"] = round(float(st["cash_usd"]) - ticket, 4)
        pos = dict(mint=mint, symbol=row["symbol"], pair=p["pairAddress"], entry_ts=NOW, entry_iso=now_iso(),
                   entry_market_price=price, entry_fill_price=fill, entry_liq=liq, tokens=tokens,
                   tokens_left=tokens, cost_usd=ticket, risk=ticket,
                   why=f"Paper buy. Confidence {conf}. Ticket ${ticket:.2f}.",
                   peak_price=price, ladder_done=[],
                   confidence=conf, url=p.get("url"))
        st["open"].append(pos)
        open_mints.add(mint)
        entries_today += 1
        stats["entries"] += 1
        append_csv(P_TRADES, TRADE_COLS, dict(ts=now_iso(), run_id=RUN_ID, side="BUY", mint=mint,
                   symbol=row["symbol"], pair=p["pairAddress"], reason=f"conf {conf}", market_price_usd=price,
                   fill_price_usd=fill, tokens=round(tokens, 4), usd=ticket, fee_usd=round(fee, 4),
                   impact_pct=round(imp * 100, 3), liquidity_usd=liq))
        record("BUY", f"PAPER BUY ${ticket:.2f} @ market {price} (fill est {fill:.10g})")
        print(f"  PAPER BUY {row['symbol']} ${ticket:.2f} @ {price} conf {conf}")


def _desk():
    root = os.path.dirname(BASE)
    if root not in sys.path:
        sys.path.insert(0, root)
    import pimp_desk
    return pimp_desk


def ticket_for(st, conf) -> float:
    """Fee-aware ticket: desk Kelly-lite when available, never above cash or TICKET_USD."""
    cash = float(st.get("cash_usd") or 0)
    if cash + 1e-9 < C.MIN_TICKET_USD:
        return 0.0
    dollars = float(C.TICKET_USD)
    try:
        desk = _desk()
        cfg = desk.load_settings(os.path.dirname(BASE))
        edge = max(0.0, float(conf) - 0.5)  # residual confidence above coin-flip
        open_risk = sum(float(p.get("cost_usd") or 0) for p in (st.get("open") or []))
        dollars = float(desk.stake_dollars_for(
            "memecoin", conf, edge=edge, cfg=cfg, open_risk_used=open_risk,
            ask=None, root=os.path.dirname(BASE),
        ))
    except Exception:
        pass
    dollars = max(float(C.MIN_TICKET_USD), min(float(C.TICKET_USD), dollars, cash))
    return round(dollars, 2)


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
        print("2) scanning skipped — desk entry_gate blocked new paper buys (exits above still ran)")
        print(f"CARD: Managed open paper positions. Desk gate blocked new buys ({len(st['open'])} still open).")
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
