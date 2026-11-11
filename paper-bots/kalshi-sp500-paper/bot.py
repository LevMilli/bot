"""
bot.py - the Kalshi PAPER bot. One run = one step.

  python3 bot.py brief  [--dry-run] [--date YYYY-MM-DD]   morning summary (text only)
  python3 bot.py scan   [--dry-run] [--date YYYY-MM-DD] [--any-time]
                                                         12:30 PM CT: pick & paper-buy
  python3 bot.py settle [--dry-run]                      after 3 PM CT: settle open paper trades

Safety
  * PAPER ONLY. config.json must say "paper_mode": true or the bot refuses to run.
  * Only public read-only API calls (data_feed.py has no order functions).
  * --dry-run: does everything except write paper_state.json, Trade_Ledger.md, Learning.md.
  * --date lets you point the scan at another day's 3 PM CT contract (e.g. tomorrow's,
    which is already listed) for testing. Combined with --dry-run it is harmless.
  * --any-time: skip the "is it 12:30-2:55 PM CT?" clock check (testing only).
"""
import argparse
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import data_feed as feed
import signal_engine
import risk_manager
import paper_sim
import logger
import alerts

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_ROOT = os.path.dirname(HERE)
CFG = json.load(open(os.path.join(HERE, "config.json")))
CT = ZoneInfo(CFG["timezone"])


def _desk():
    if DESK_ROOT not in sys.path:
        sys.path.insert(0, DESK_ROOT)
    import pimp_desk
    return pimp_desk


def _ask_band():
    """Staff-promoted research band overrides config; else config.json 80–92¢."""
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
    """Feed desk_brain / skip_board (+ features) for INX scan skips."""
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_inx
        desk_inx.densify_skip(
            DESK_ROOT,
            bot="kalshi-sp",
            reason=reason,
            ticker=ticker,
            side=side,
            edge=edge,
            confidence=confidence,
            series=str(CFG.get("series") or "KXINXU"),
            note="kalshi-sp scan skip densify",
            features=features,
        )
    except Exception:
        pass


def live_quotes(event_ticker):
    """Current top-of-book for every contract in the event (from the public markets list).
    Only contracts that are still 'active' (tradable) are returned."""
    out = []
    for m in feed.get_event_markets(event_ticker):
        if m.get("status") != "active":
            continue
        out.append({"ticker": m["ticker"], "strike": m.get("floor_strike"),
                    "yes_bid": feed.dollars(m.get("yes_bid_dollars")),
                    "yes_ask": feed.dollars(m.get("yes_ask_dollars"))})
    return out


def confirm_with_orderbook(pick):
    """Re-read the chosen contract's order book right before 'buying' so the paper
    fill uses the freshest real ask. Returns the updated pick or None if it left the band."""
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


def step_brief(args, state, day):
    skip = risk_manager.news_skip_reason(day)
    ok, msg = risk_manager.check_can_trade(day, state["bankroll"], paper_sim.trades_on(state, day),
                                           paper_sim.realised_pnl_on(state, day), ignore_calendar=True)
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
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root not in sys.path:
            sys.path.insert(0, root)
        import kalshi_tape
        tape = kalshi_tape.sync_tape_family(root, "inx")
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
            DESK_ROOT, now_ct=now, bots=("kalshi-sp",),
            series=(CFG.get("series") or "KXINXU",),
        )
        if warm.get("warmed"):
            print(
                f"Pre-noon INX warm @11:50 CT: {warm.get('warmed_n') or 0} series "
                f"(1/day buy limit unchanged)"
            )
    except Exception as exc:
        print(f"Pre-noon INX warm skipped: {type(exc).__name__}")
    # 1) clock check: only between 12:30 and 2:55 PM CT on the target day
    if not args.any_time:
        start = dt.datetime.combine(day, dt.time.fromisoformat(CFG["entry_time_ct"]), CT)
        end = dt.datetime.combine(day, dt.time(14, 55), CT)
        if not (start <= now <= end):
            print(f"Not scan time: now {now:%Y-%m-%d %H:%M} CT, window {start:%H:%M}-{end:%H:%M} CT on {day}. Use --any-time to test.")
            return
    # 2) risk rules (skip days, 1/day, loss limit, kill switch)
    if state.get("halted"):
        print("HALTED by kill switch earlier. A human must review paper_state.json before trading resumes.")
        return
    ok, why = risk_manager.check_can_trade(day, state["bankroll"], paper_sim.trades_on(state, day),
                                           paper_sim.realised_pnl_on(state, day))
    if not ok:
        print(alerts.format_skip_note(day, why))
        if not args.dry_run:
            logger.learn(f"{day}: no trade - {why}", "skip")
            _densify_scan_skip(why)
        return
    # Positive-ROI: post-print / pre-FOMC calm (in addition to full-day calendar skips).
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
    # 3) find the 3 PM CT contract family and read live prices
    ev = feed.find_event_for(CFG["series"], day, CFG["settle_time_ct"])
    if not ev:
        reason = "no KXINXU 3 PM CT event listed (holiday/half day?)"
        print(alerts.format_skip_note(day, reason))
        if not args.dry_run:
            _densify_scan_skip(reason, features=False)
        return
    quotes = live_quotes(ev)
    print(f"Event {ev}: {len(quotes)} active contracts read at {logger.now_ct()}")
    lo, hi = _ask_band()
    cands = signal_engine.candidate_sides(quotes, lo, hi)
    if not cands:
        reason = f"no contract with ask in the {lo * 100:.0f}–{hi * 100:.0f}¢ band"
        print(alerts.format_skip_note(day, reason))
        if not args.dry_run:
            logger.learn(f"{day}: no trade - nothing in the ask band at scan time", "skip")
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
    # Walk fair-ranked siblings: OB move / post-OB fair fail must not day-skip
    # while another fee-clear band contract still clears.
    ranked = list(chosen.get("picks") or [])
    if not ranked and chosen.get("pick"):
        ranked = [{"pick": chosen["pick"], "fair": chosen.get("fair")}]
    pick = None
    ob = None
    fair = None
    fee_one = 0.0
    edge_proxy = 0.0
    fair_p = None
    last_ob_miss = False
    last_fair_reason = ""
    spot_px = chosen.get("spot")
    hour_ct = dt.datetime.now(CT).hour
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
    for row in ranked:
        cand = row.get("pick") if isinstance(row, dict) else None
        if not isinstance(cand, dict):
            continue
        confirmed, ob_try = confirm_with_orderbook(cand)
        if not confirmed:
            last_ob_miss = True
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
            last_fair_reason = f"inx fair unavailable ({type(exc).__name__})"
            continue
        if not fair_try.get("ok"):
            last_fair_reason = str(
                fair_try.get("reason") or desk_inx.refuse_residual_as_edge()
            )
            continue
        edge_try = float(fair_try.get("edge") or 0.0)
        # Learn/corr are side×bucket keyed — continue to next fair sibling.
        policy = desk_inx.inx_learn_corr_reason(
            desk, DESK_ROOT,
            market="S&P", bot_id="kalshi-sp",
            pick=confirmed, edge=edge_try, hour_ct=hour_ct,
        )
        if policy:
            last_fair_reason = policy
            continue
        pick = confirmed
        ob = ob_try
        fair = fair_try
        fee_one = float(fair_try.get("fee") if fair_try.get("fee") is not None else fee_try)
        edge_proxy = edge_try
        fair_p = fair_try.get("p")
        break
    if not pick or not fair:
        reason = last_fair_reason or (
            "chosen contract moved out of the band on the order-book re-check"
            if last_ob_miss
            else "no candidate cleared inx fair venue edge"
        )
        print(alerts.format_skip_note(day, reason))
        if not args.dry_run:
            logger.learn(f"{day}: no trade - {reason}", "skip")
            # densify_skip also records features (replaces prior local-only block).
            _densify_scan_skip(reason)
        return
    n = risk_manager.stake_contracts(pick["ask"], bankroll=state["bankroll"])
    if n < 1:
        reason = "not enough paper bankroll for 1 contract after fee"
        print(alerts.format_skip_note(day, reason))
        if not args.dry_run:
            logger.learn(f"{day}: no trade - bankroll too small after fee", "skip")
            _densify_scan_skip(reason)
        return
    fee = paper_sim.taker_fee(n, pick["ask"])
    preview = {"ticker": pick["ticker"], "side": pick["side"], "ask": pick["ask"], "contracts": n,
               "cost": round(n * pick["ask"], 2), "fee": fee}
    if args.dry_run:
        print(alerts.format_trade_note(preview, state["bankroll"] - preview["cost"] - fee, dry_run=True))
        return
    pos = paper_sim.open_position(state, day, ev, pick, n, now.isoformat(timespec="seconds"))
    try:
        import desk_profit
        pos["risk_factor"] = desk_profit.risk_factor_for("kalshi-sp", pick["side"])
        pos["gap_at_entry"] = round(float(edge_proxy), 4)
        pos["fair_at_entry"] = round(float(fair_p if fair_p is not None else pick["ask"]), 4)
    except Exception:
        pass
    try:
        import desk_living
        desk_living.record_eval_features(
            DESK_ROOT, bot="kalshi-sp", action="buy", series=CFG.get("series") or "KXINXU",
            ticker=str(pick.get("ticker") or ""),
            ev={"side": pick.get("side"), "ask": pick.get("ask"), "fee": fee_one,
                "edge": edge_proxy, "confidence": fair_p or pick.get("ask")},
            note="paper buy kalshi-sp (Φ fair)",
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
            print(f"Could not read {pos['ticker']} yet."); continue
        if m.get("result") not in ("yes", "no"):
            # still open: model-flip sell when desk enables it and side bid collapses under 50¢
            bid = feed.dollars(m.get("yes_bid_dollars")) if pos["side"] == "yes" else feed.dollars(m.get("no_bid_dollars"))
            note = f"{pos['ticker']} not settled yet (status {m.get('status')}); our side bid now {bid}"
            print(note)
            flip_on = True
            try:
                desk = _desk()
                cfg = desk.load_settings(DESK_ROOT)
                flip_on = bool(cfg.get("model_flip_exits", True))
            except Exception:
                pass
            if (
                flip_on
                and bid is not None
                and bid < CFG["invalidation_log_below"]
                and not args.dry_run
            ):
                # Paper sell at bid minus taker fee (honest EV; matches sports sell path).
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
                        "market": "S&P",
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
                    import teller_memory
                    desk_roi_plan.record_fee_ledger(
                        DESK_ROOT,
                        bot="kalshi-sp",
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
                        bot="kalshi-sp",
                        ticker=str(pos.get("ticker") or ""),
                        side=str(pos.get("side") or ""),
                        pnl=pnl,
                        contracts=pos.get("contracts"),
                        fill_id=str(pos.get("fill_id") or ""),
                        kind="model_flip",
                        eligible=False,
                        note="model-flip bid under 50c",
                    )
                    teller_memory.remember(
                        DESK_ROOT,
                        kind="wins" if float(pnl) > 0 else "mistakes",
                        text=f"kalshi-sp flip {pos.get('ticker')} pnl {float(pnl):+.2f}"[:200],
                        bot_id="kalshi-sp",
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
                logger.learn(f"INVALIDATION (log only): {pos['ticker']} {pos['side']} bid {bid:.2f} < 0.50", "invalidation")
            continue
        if args.dry_run:
            won = m["result"] == pos["side"]
            print(f"(dry run) {pos['ticker']} result {m['result']} -> would be {'WON' if won else 'LOST'} "
                  f"{paper_sim.trade_pnl(pos['side'], won, pos['contracts'], pos['ask'], pos['fee']):+.2f}")
            continue
        paper_sim.settle_position(state, pos, m["result"])
        paper_sim.save_state(state)
        try:
            desk = _desk()
            desk.record_learning(DESK_ROOT, {
                "result": "hit" if (pos.get("pnl") or 0) > 0 else "miss",
                "market": "S&P",
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
            import teller_memory
            pnl = pos.get("pnl")
            desk_roi_plan.record_fee_ledger(
                DESK_ROOT,
                bot="kalshi-sp",
                ticker=str(pos.get("ticker") or ""),
                side=str(pos.get("side") or ""),
                price=pos.get("ask"),
                contracts=pos.get("contracts"),
                fee=pos.get("fee") or 0.0,
                pnl=pnl,
                fill_id=str(pos.get("fill_id") or ""),
                kind="settle",
                note="INX settle",
            )
            desk_living.record_completion(
                DESK_ROOT,
                bot="kalshi-sp",
                ticker=str(pos.get("ticker") or ""),
                side=str(pos.get("side") or ""),
                pnl=pnl,
                contracts=pos.get("contracts"),
                fill_id=str(pos.get("fill_id") or ""),
                kind="settle",
                eligible=False,
                note="INX settle",
            )
            teller_memory.remember(
                DESK_ROOT,
                kind="wins" if float(pnl or 0) > 0 else "mistakes",
                text=f"kalshi-sp settle {pos.get('ticker')} pnl {float(pnl or 0):+.2f}"[:200],
                bot_id="kalshi-sp",
            )
        except Exception:
            pass
        logger.ledger_settle(pos, state["bankroll"])
        logger.learn(f"Settled {pos['ticker']} {pos['side']} @ {pos['ask']:.2f}: {pos['status']} {pos['pnl']:+.2f}", "settle")
        print(alerts.format_settle_note(pos, state["bankroll"]))
        if state.get("halted"):
            msg = f"KILL SWITCH: bankroll {state['bankroll']:.2f} <= {CFG['kill_switch_bankroll']}. Bot halted for review."
            print(msg); logger.learn(msg, "kill-switch")


def main():
    if CFG.get("paper_mode") is not True:
        sys.exit("Refusing to run: config.json paper_mode is not true. This bot is paper-only.")
    ap = argparse.ArgumentParser(description="Kalshi KXINXU paper bot (one step per run)")
    ap.add_argument("step", choices=["brief", "scan", "settle"])
    ap.add_argument("--dry-run", action="store_true", help="read and decide, but write nothing")
    ap.add_argument("--date", help="target day YYYY-MM-DD (default: today in CT)")
    ap.add_argument("--any-time", action="store_true", help="ignore the 12:30-2:55 PM CT scan window (testing)")
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
