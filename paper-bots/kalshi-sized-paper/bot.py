"""
Sized Kalshi paper bot — KXINXU with desk Kelly-lite sizing (Tower 5).

  python3 bot.py brief  [--dry-run] [--date YYYY-MM-DD]
  python3 bot.py scan   [--dry-run] [--date YYYY-MM-DD] [--any-time]
  python3 bot.py settle [--dry-run]

PAPER ONLY. Shares public Kalshi reads with kalshi-sp500-paper; own bankroll + ledger.
Stake comes from the desk (Kelly-lite + starve), not a flat $25 ticket.
"""
import argparse
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
SIBLING = os.path.join(DESK_ROOT, "kalshi-sp500-paper")
if SIBLING not in sys.path:
    sys.path.insert(0, SIBLING)

import data_feed as feed  # noqa: E402
import signal_engine  # noqa: E402

import risk_manager  # noqa: E402  (local)
import paper_sim  # noqa: E402
import logger  # noqa: E402
import alerts  # noqa: E402

CFG = json.load(open(os.path.join(HERE, "config.json")))
CT = ZoneInfo(CFG["timezone"])
WINDOW_START = dt.time(12, 5)
WINDOW_END = dt.time(14, 55)


def scan_window(day, entry_time=None):
    """12:05–14:55 CT. A start before 12:05 is put back. The end stays 14:55."""
    start_t = WINDOW_START
    raw = CFG.get("entry_time_ct") if entry_time is None else entry_time
    try:
        configured = dt.time.fromisoformat(str(raw))
    except (TypeError, ValueError):
        configured = WINDOW_START
    if configured > WINDOW_START:
        start_t = configured
    return (
        dt.datetime.combine(day, start_t, CT),
        dt.datetime.combine(day, WINDOW_END, CT),
    )


def outside_scan_window(now, day, entry_time=None) -> str:
    """A clock outside the tower window. It does not open a buy."""
    start, end = scan_window(day, entry_time)
    if start <= now <= end:
        return ""
    return f"outside {start:%H:%M}–{end:%H:%M} CT"


def learning_is_header_only(text) -> bool:
    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    if not lines:
        return True
    return not any(ln for ln in lines if not ln.startswith("#"))


def header_only_fact(text):
    """A header-only learning file is a fact. It does not force a sample fill."""
    if not learning_is_header_only(text):
        return None
    return {
        "fact": "header-only learning file",
        "fill": False,
        "paper_only": True,
    }


def remember_refused_edge(best, ask, edge):
    """Keep the best refused edge only when the ask is a real quote."""
    try:
        ask_n = float(ask)
        edge_n = float(edge)
    except (TypeError, ValueError):
        return best
    if ask_n != ask_n or edge_n != edge_n or ask_n <= 0 or ask_n >= 1:
        return best
    if best is None or edge_n > float(best):
        return edge_n
    return best


def _desk():
    if DESK_ROOT not in sys.path:
        sys.path.insert(0, DESK_ROOT)
    import pimp_desk
    return pimp_desk


def _ask_band():
    """Staff-promoted research band overrides config; else config.json."""
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_roi_plan
        band = desk_roi_plan.effective_inx_ask_band(DESK_ROOT, CFG)
        return float(band["lo"]), float(band["hi"])
    except Exception:
        return float(CFG["band_min_ask"]), float(CFG["band_max_ask"])


def _densify_scan_skip(
    reason: str,
    *,
    ticker: str = "",
    side: str = "",
    edge=None,
    confidence=None,
    features: bool = True,
) -> None:
    """Feed desk_brain / skip_board (+ features) for sized INX scan skips."""
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_inx
        desk_inx.densify_skip(
            DESK_ROOT,
            bot="kalshi-sized",
            reason=reason,
            ticker=ticker,
            side=side,
            edge=edge,
            confidence=confidence,
            series=str(CFG.get("series") or "KXINXU"),
            note="kalshi-sized scan skip densify",
            features=features,
        )
    except Exception:
        pass


def live_quotes(event_ticker):
    out = []
    for m in feed.get_event_markets(event_ticker):
        if m.get("status") != "active":
            continue
        out.append({
            "ticker": m["ticker"],
            "strike": m.get("floor_strike"),
            "yes_bid": feed.dollars(m.get("yes_bid_dollars")),
            "yes_ask": feed.dollars(m.get("yes_ask_dollars")),
        })
    return out


def confirm_with_orderbook(pick):
    ob = feed.get_orderbook(pick["ticker"])
    ask = ob["yes_ask"] if pick["side"] == "yes" else ob["no_ask"]
    lo, hi = _ask_band()
    if ask is None or not (lo - 1e-9 <= ask <= hi + 1e-9):
        return None, ob
    return {**pick, "ask": round(ask, 4)}, ob


def upcoming_skips(day, days=14):
    out = []
    for i in range(days + 1):
        d = day + dt.timedelta(days=i)
        r = risk_manager.SKIP_DAYS.get(str(d))
        if r:
            out.append((str(d), "+".join(r)))
    return out


def _desk_open_risk(desk) -> float:
    try:
        snap = desk.snapshot(DESK_ROOT)
        return float(sum(float(b.get("open_risk") or 0) for b in snap.get("bots") or [] if not b.get("shadow_only")))
    except Exception:
        return 0.0


def step_brief(args, state, day):
    skip = risk_manager.news_skip_reason(day)
    ok, msg = risk_manager.check_can_trade(
        day, state["bankroll"], paper_sim.trades_on(state, day),
        paper_sim.realised_pnl_on(state, day), ignore_calendar=True,
    )
    ev = feed.find_event_for(CFG["series"], day, CFG["settle_time_ct"])
    cands = []
    if ev:
        lo, hi = _ask_band()
        cands = signal_engine.candidate_sides(live_quotes(ev), lo, hi)
        cands.sort(key=lambda c: -c["ask"])
    text = alerts.format_brief(day, skip, ok, msg, state, ev, cands, upcoming_skips(day), logger.now_ct())
    print(text)
    return text


def _sync_kalshi_tape():
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import kalshi_tape
        tape = kalshi_tape.sync_tape_family(DESK_ROOT, "inx")
        print(f"Kalshi tape: +{tape.get('last_added') or 0} new prints (kept {len(tape.get('trades') or [])})")
    except Exception as exc:
        print(f"Kalshi tape sync skipped: {type(exc).__name__}")


def step_scan(args, state, day):
    _sync_kalshi_tape()
    now = dt.datetime.now(CT)
    # #515 pre-noon INX book warm @11:50 CT — observe into quote_cache; still 1/day.
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_more
        warm = desk_more.warm_inx_books_pre_noon(
            DESK_ROOT, now_ct=now, bots=("kalshi-sized",),
            series=(CFG.get("series") or "KXINXU",),
        )
        if warm.get("warmed"):
            print(
                f"Pre-noon INX warm @11:50 CT: {warm.get('warmed_n') or 0} series "
                f"(1/day buy limit unchanged)"
            )
    except Exception as exc:
        print(f"Pre-noon INX warm skipped: {type(exc).__name__}")
    if not (getattr(args, "any_time", False) and getattr(args, "dry_run", False)):
        outside = outside_scan_window(now, day, CFG.get("entry_time_ct"))
        if outside:
            print(
                f"Not scan time: now {now:%Y-%m-%d %H:%M} CT, {outside}. "
                "The window is not loosened."
            )
            return
    try:
        with open(logger.LEARNING, encoding="utf-8") as handle:
            learning_text = handle.read()
    except OSError:
        learning_text = ""
    fact = header_only_fact(learning_text)
    if fact:
        print(f"Learning file: {fact['fact']}. Not a sample fill.")
    if state.get("halted"):
        print("HALTED by kill switch earlier. Review paper_state.json before trading resumes.")
        return
    ok, why = risk_manager.check_can_trade(
        day, state["bankroll"], paper_sim.trades_on(state, day),
        paper_sim.realised_pnl_on(state, day),
    )
    if not ok:
        print(alerts.format_skip_note(day, why))
        if not args.dry_run:
            logger.learn(f"{day}: no trade - {why}", "skip")
            _densify_scan_skip(why)
        return
    ev = feed.find_event_for(CFG["series"], day, CFG["settle_time_ct"])
    if not ev:
        reason = "no KXINXU 3 PM CT event listed (holiday/half day?)"
        print(alerts.format_skip_note(day, reason))
        if not args.dry_run:
            logger.learn(f"{day}: no trade - {reason}", "skip")
            _densify_scan_skip(reason, features=False)
        return
    # Positive-ROI: post-print / pre-FOMC calm gates (fee floors unchanged).
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_inx
        macro = desk_inx.inx_entry_blocks(
            now=now, day=day, skip_days=risk_manager.SKIP_DAYS,
        )
        if macro:
            print(alerts.format_skip_note(day, macro))
            if not args.dry_run:
                logger.learn(f"{day}: no trade - {macro}", "skip")
                _densify_scan_skip(macro)
            return
    except Exception:
        pass
    quotes = live_quotes(ev)
    print(f"Sized Kalshi event {ev}: {len(quotes)} active contracts at {logger.now_ct()}")
    lo, hi = _ask_band()
    cands = signal_engine.candidate_sides(quotes, lo, hi)
    if not cands:
        reason = "no contract with ask in the 84-92c band"
        print(alerts.format_skip_note(day, reason))
        if not args.dry_run:
            logger.learn(f"{day}: no trade - nothing in 84-92c band at scan time", "skip")
            _densify_scan_skip(reason)
        return
    venue_edge = 0.02
    try:
        desk = _desk()
        venue_edge = float(desk.venue_min_edge("kalshi_inx", desk.load_settings(DESK_ROOT)))
    except Exception:
        pass
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_inx
        chosen = desk_inx.rank_by_fair(
            cands,
            venue_edge=venue_edge,
            now=now,
            settle_time_ct=str(CFG.get("settle_time_ct") or "15:00"),
        )
    except Exception as exc:
        chosen = {"ok": False, "reason": f"inx fair pick unavailable ({type(exc).__name__})"}
    if not chosen.get("ok") or not (chosen.get("picks") or chosen.get("pick")):
        reason = str(chosen.get("reason") or "no candidate cleared inx fair venue edge")
        print(alerts.format_skip_note(day, reason))
        if not args.dry_run:
            logger.learn(f"{day}: no trade - {reason}", "skip")
            _densify_scan_skip(reason)
        return
    ranked = list(chosen.get("picks") or [])
    if not ranked and chosen.get("pick"):
        ranked = [{"pick": chosen["pick"], "fair": chosen.get("fair")}]
    pick = None
    ob = None
    fair = None
    edge_proxy = 0.0
    fair_p = None
    fee_one = 0.0
    n = 0
    last_ob_miss = False
    last_reason = ""
    # Twin / anti-double / fair vetoes must densify with the blocked ticker+edge
    # (skip honesty). edge_proxy stays 0 until a buy clears — do not lose veto edge.
    last_skip_ticker = ""
    last_skip_side = ""
    last_skip_edge = None
    best_refused = None
    spot_px = chosen.get("spot")
    hour_ct = dt.datetime.now(CT).hour
    sp_state = {}
    sp_path = os.path.join(SIBLING, "paper_state.json")
    try:
        if os.path.isfile(sp_path):
            with open(sp_path, encoding="utf-8") as handle:
                sp_state = json.load(handle) or {}
    except Exception:
        sp_state = {}
    try:
        desk = _desk()
        cfg = desk.load_settings(DESK_ROOT)
        venue_edge = float(desk.venue_min_edge("kalshi_inx", cfg))
    except Exception:
        desk = None
        cfg = {}
    if DESK_ROOT not in sys.path:
        sys.path.insert(0, DESK_ROOT)
    import desk_inx

    def _remember_veto(reason: str, confirmed: dict, edge=None) -> None:
        nonlocal last_reason, last_skip_ticker, last_skip_side, last_skip_edge
        last_reason = str(reason or "")
        last_skip_ticker = str(confirmed.get("ticker") or "")
        last_skip_side = str(confirmed.get("side") or "")
        last_skip_edge = edge

    for row in ranked:
        cand = row.get("pick") if isinstance(row, dict) else None
        if not isinstance(cand, dict):
            continue
        confirmed, ob_try = confirm_with_orderbook(cand)
        if not confirmed:
            last_ob_miss = True
            continue
        blocked_dbl = desk_inx.anti_double_blocks(
            ticker=str(confirmed.get("ticker") or ""), sp_state=sp_state,
        )
        if blocked_dbl:
            _remember_veto(blocked_dbl, confirmed)
            continue
        fee_try = paper_sim.taker_fee(1, confirmed["ask"])
        try:
            fair_try = desk_inx.fair_evaluate(
                confirmed,
                venue_edge=venue_edge,
                spot=spot_px,
                now=now,
                settle_time_ct=str(CFG.get("settle_time_ct") or "15:00"),
            )
        except Exception as exc:
            _remember_veto(f"inx fair unavailable ({type(exc).__name__})", confirmed)
            continue
        if not fair_try.get("ok"):
            _remember_veto(
                str(fair_try.get("reason") or desk_inx.refuse_residual_as_edge()),
                confirmed,
            )
            continue
        edge_try = float(fair_try.get("edge") or 0.0)
        best_refused = remember_refused_edge(best_refused, confirmed.get("ask"), edge_try)
        twin_block = desk_inx.twin_edge_blocks(
            sized_edge=edge_try, venue_edge=venue_edge, extra=0.01,
        )
        if twin_block:
            _remember_veto(twin_block, confirmed, edge=edge_try)
            continue
        # Learn/corr are side×bucket keyed — continue to next fair sibling.
        policy = desk_inx.inx_learn_corr_reason(
            desk, DESK_ROOT,
            market="S&P-sized", bot_id="kalshi-sized",
            pick=confirmed, edge=edge_try, hour_ct=hour_ct,
        )
        if policy:
            _remember_veto(policy, confirmed, edge=edge_try)
            continue
        pick = confirmed
        ob = ob_try
        fair = fair_try
        edge_proxy = edge_try
        fair_p = fair_try.get("p")
        fee_one = float(fair_try.get("fee") if fair_try.get("fee") is not None else fee_try)
        break
    if not pick or not fair:
        reason = last_reason or (
            "chosen contract moved out of the band on the order-book re-check"
            if last_ob_miss
            else "no candidate cleared inx fair venue edge"
        )
        print(alerts.format_skip_note(day, reason))
        if not args.dry_run:
            logger.learn(f"{day}: no trade - {reason}", "skip")
            densify_edge = best_refused if best_refused is not None else last_skip_edge
            if densify_edge is None and edge_proxy:
                densify_edge = edge_proxy
            _densify_scan_skip(
                reason,
                ticker=last_skip_ticker,
                side=last_skip_side,
                edge=densify_edge,
            )
        return
    try:
        desk = _desk()
        cfg = desk.load_settings(DESK_ROOT)
        # Desk-wide entry_gate — sibling retry cannot clear it.
        gate = desk.entry_gate(DESK_ROOT)
        if gate:
            print(alerts.format_skip_note(day, str(gate)))
            if not args.dry_run:
                logger.learn(f"{day}: no trade - {gate}", "skip")
                _densify_scan_skip(
                    str(gate),
                    ticker=str(pick.get("ticker") or ""),
                    side=str(pick.get("side") or ""),
                    edge=edge_proxy,
                    confidence=fair_p,
                )
            return
        open_risk = _desk_open_risk(desk)
        dollars = desk.stake_dollars_for(
            "kalshi-sized",
            pick["ask"],
            edge=edge_proxy,
            cfg=cfg,
            open_risk_used=open_risk,
            ask=pick["ask"],
            root=DESK_ROOT,
        )
        n = desk.contracts_for_stake(pick["ask"], dollars)
        while n >= 1 and n * pick["ask"] + paper_sim.taker_fee(n, pick["ask"]) > float(state["bankroll"]) + 1e-9:
            n -= 1
    except Exception as exc:
        print(f"Desk sizing / fair unavailable ({exc}); falling back to local max stake.")
        n = risk_manager.stake_contracts(pick["ask"], bankroll=state["bankroll"])
    if n < 1:
        reason = "not enough paper bankroll / stake for 1 contract after fee"
        print(alerts.format_skip_note(day, reason))
        if not args.dry_run:
            logger.learn(f"{day}: no trade - bankroll/stake too small after fee", "skip")
            _densify_scan_skip(reason)
        return
    fee = paper_sim.taker_fee(n, pick["ask"])
    preview = {
        "ticker": pick["ticker"],
        "side": pick["side"],
        "ask": pick["ask"],
        "contracts": n,
        "cost": round(n * pick["ask"], 2),
        "fee": fee,
    }
    if args.dry_run:
        print(alerts.format_trade_note(preview, state["bankroll"] - preview["cost"] - fee, dry_run=True))
        return
    pos = paper_sim.open_position(state, day, ev, pick, n, now.isoformat(timespec="seconds"))
    pos["why"] = (
        f"Sized paper buy (Φ fair). Ask in band; desk Kelly-lite sized {n} contracts."
    )
    try:
        import desk_profit
        pos["risk_factor"] = desk_profit.risk_factor_for("kalshi-sized", pick["side"])
        pos["gap_at_entry"] = round(float(edge_proxy), 4)
        pos["fair_at_entry"] = round(float(fair_p if fair_p is not None else pick["ask"]), 4)
    except Exception:
        pass
    try:
        import desk_living
        desk_living.record_eval_features(
            DESK_ROOT, bot="kalshi-sized", action="buy",
            series=CFG.get("series") or "KXINXU",
            ticker=str(pick.get("ticker") or ""),
            ev={"side": pick.get("side"), "ask": pick.get("ask"), "fee": fee_one,
                "edge": edge_proxy, "confidence": fair_p or pick.get("ask")},
            note="paper buy kalshi-sized (Φ fair)",
        )
    except Exception:
        pass
    paper_sim.save_state(state)
    logger.ledger_open(pos, state["bankroll"])
    print(alerts.format_trade_note(pos, state["bankroll"]))


def step_settle(args, state, day):
    if not state["open"]:
        print("No open paper positions.")
        return
    for pos in list(state["open"]):
        m = feed.get_market(pos["ticker"])
        if not m:
            print(f"Could not read {pos['ticker']} yet.")
            continue
        if m.get("result") not in ("yes", "no"):
            bid = feed.dollars(m.get("yes_bid_dollars")) if pos["side"] == "yes" else feed.dollars(m.get("no_bid_dollars"))
            print(f"{pos['ticker']} not settled yet (status {m.get('status')}); our side bid now {bid}")
            flip_on = True
            try:
                desk = _desk()
                cfg = desk.load_settings(DESK_ROOT)
                flip_on = bool(cfg.get("model_flip_exits", True))
            except Exception:
                pass
            if flip_on and bid is not None and bid < CFG["invalidation_log_below"] and not args.dry_run:
                contracts = float(pos.get("contracts") or 0)
                sell_fee = float(paper_sim.taker_fee(contracts, bid))
                proceeds = round(contracts * float(bid) - sell_fee, 4)
                pnl = round(proceeds - float(pos.get("cost") or 0) - float(pos.get("fee") or 0), 4)
                state["bankroll"] = round(float(state["bankroll"]) + proceeds, 4)
                pos.update({
                    "status": "sold",
                    "exit": "model-flip bid under 50c",
                    "exit_price": bid,
                    "exit_fee": sell_fee,
                    "payout": proceeds,
                    "pnl": pnl,
                    "settled_at": dt.datetime.now().isoformat(timespec="seconds"),
                })
                state["open"] = [p for p in state["open"] if p is not pos]
                state["closed"].append(pos)
                paper_sim.save_state(state)
                try:
                    desk = _desk()
                    desk.record_learning(DESK_ROOT, {
                        "result": "hit" if pnl > 0 else "miss",
                        "market": "S&P-sized",
                        "prob": pos.get("ask"),
                        "stake": pos.get("risk") if pos.get("risk") is not None else pos.get("cost"),
                        "fill_id": pos.get("fill_id") or "",
                        "side": pos.get("side") or "",
                    })
                except Exception:
                    pass
                try:
                    if DESK_ROOT not in sys.path:
                        sys.path.insert(0, DESK_ROOT)
                    import desk_roi_plan
                    import desk_living
                    desk_roi_plan.record_fee_ledger(
                        DESK_ROOT,
                        bot="kalshi-sized",
                        ticker=str(pos.get("ticker") or ""),
                        side=str(pos.get("side") or ""),
                        price=bid,
                        contracts=pos.get("contracts"),
                        fee=sell_fee,
                        pnl=pnl,
                        fill_id=str(pos.get("fill_id") or ""),
                        kind="model_flip",
                        note="model-flip bid under 50c",
                    )
                    desk_living.record_completion(
                        DESK_ROOT,
                        bot="kalshi-sized",
                        ticker=str(pos.get("ticker") or ""),
                        side=str(pos.get("side") or ""),
                        pnl=pnl,
                        contracts=pos.get("contracts"),
                        fill_id=str(pos.get("fill_id") or ""),
                        kind="model_flip",
                        eligible=False,
                        note="model-flip bid under 50c",
                    )
                except Exception:
                    pass
                logger.learn(
                    f"MODEL-FLIP SELL: {pos['ticker']} {pos['side']} bid {bid:.2f} pnl {pnl:+.2f}",
                    "model-flip",
                )
                print(f"MODEL-FLIP SELL {pos['ticker']} @ {bid:.2f} pnl {pnl:+.2f}")
                continue
            if bid is not None and bid < CFG["invalidation_log_below"] and not args.dry_run:
                logger.learn(
                    f"INVALIDATION (log only): {pos['ticker']} {pos['side']} bid {bid:.2f} < 0.50",
                    "invalidation",
                )
            continue
        if args.dry_run:
            won = m["result"] == pos["side"]
            print(
                f"(dry run) {pos['ticker']} result {m['result']} -> would be "
                f"{'WON' if won else 'LOST'} "
                f"{paper_sim.trade_pnl(pos['side'], won, pos['contracts'], pos['ask'], pos['fee']):+.2f}"
            )
            continue
        paper_sim.settle_position(state, pos, m["result"])
        paper_sim.save_state(state)
        try:
            desk = _desk()
            desk.record_learning(DESK_ROOT, {
                "result": "hit" if (pos.get("pnl") or 0) > 0 else "miss",
                "market": "S&P-sized",
                "prob": pos.get("ask"),
                "stake": pos.get("risk") if pos.get("risk") is not None else pos.get("cost"),
                "fill_id": pos.get("fill_id") or "",
                "side": pos.get("side") or "",
            })
        except Exception:
            pass
        try:
            if DESK_ROOT not in sys.path:
                sys.path.insert(0, DESK_ROOT)
            import desk_roi_plan
            import desk_living
            pnl = pos.get("pnl")
            desk_roi_plan.record_fee_ledger(
                DESK_ROOT,
                bot="kalshi-sized",
                ticker=str(pos.get("ticker") or ""),
                side=str(pos.get("side") or ""),
                price=pos.get("ask"),
                contracts=pos.get("contracts"),
                fee=pos.get("fee") or 0.0,
                pnl=pnl,
                fill_id=str(pos.get("fill_id") or ""),
                kind="settle",
                note="INX sized settle",
            )
            desk_living.record_completion(
                DESK_ROOT,
                bot="kalshi-sized",
                ticker=str(pos.get("ticker") or ""),
                side=str(pos.get("side") or ""),
                pnl=pnl,
                contracts=pos.get("contracts"),
                fill_id=str(pos.get("fill_id") or ""),
                kind="settle",
                eligible=False,
                note="INX sized settle",
            )
        except Exception:
            pass
        logger.ledger_settle(pos, state["bankroll"])
        logger.learn(
            f"Settled {pos['ticker']} {pos['side']} @ {pos['ask']:.2f}: {pos['status']} {pos['pnl']:+.2f}",
            "settle",
        )
        print(alerts.format_settle_note(pos, state["bankroll"]))
        if state.get("halted"):
            msg = (
                f"KILL SWITCH: bankroll {state['bankroll']:.2f} <= "
                f"{CFG['kill_switch_bankroll']}. Bot halted for review."
            )
            print(msg)
            logger.learn(msg, "kill-switch")


def main():
    if CFG.get("paper_mode") is not True:
        sys.exit("Refusing to run: config.json paper_mode is not true. This bot is paper-only.")
    ap = argparse.ArgumentParser(description="Sized Kalshi KXINXU paper bot (Kelly-lite stake)")
    ap.add_argument("step", choices=["brief", "scan", "settle"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date", help="target day YYYY-MM-DD (default: today in CT)")
    ap.add_argument("--any-time", action="store_true")
    args = ap.parse_args()
    day = dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(CT).date()
    if not args.dry_run:
        logger.ensure_files()
    existed = os.path.exists(paper_sim.STATE_PATH)
    state = paper_sim.load_state()
    if not existed and not args.dry_run:
        paper_sim.save_state(state)
    {"brief": step_brief, "scan": step_scan, "settle": step_settle}[args.step](args, state, day)


if __name__ == "__main__":
    main()
