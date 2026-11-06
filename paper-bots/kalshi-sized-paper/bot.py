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
    if not args.any_time:
        start = dt.datetime.combine(day, dt.time.fromisoformat(CFG["entry_time_ct"]), CT)
        end = dt.datetime.combine(day, dt.time(14, 55), CT)
        if not (start <= now <= end):
            print(
                f"Not scan time: now {now:%Y-%m-%d %H:%M} CT, "
                f"window {start:%H:%M}-{end:%H:%M} CT on {day}. Use --any-time to test."
            )
            return
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
        return
    ev = feed.find_event_for(CFG["series"], day, CFG["settle_time_ct"])
    if not ev:
        print(alerts.format_skip_note(day, "no KXINXU 3 PM CT event listed (holiday/half day?)"))
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
            return
    except Exception:
        pass
    quotes = live_quotes(ev)
    print(f"Sized Kalshi event {ev}: {len(quotes)} active contracts at {logger.now_ct()}")
    lo, hi = _ask_band()
    pick = signal_engine.pick_trade(quotes, lo, hi)
    if not pick:
        print(alerts.format_skip_note(day, "no contract with ask in the 84-92c band"))
        if not args.dry_run:
            logger.learn(f"{day}: no trade - nothing in 84-92c band at scan time", "skip")
        return
    pick, ob = confirm_with_orderbook(pick)
    if not pick:
        print(alerts.format_skip_note(day, "chosen contract moved out of the band on the order-book re-check"))
        return
    # Anti-double: refuse same ticker already open on kalshi-sp twin.
    try:
        if DESK_ROOT not in sys.path:
            sys.path.insert(0, DESK_ROOT)
        import desk_inx
        sp_path = os.path.join(SIBLING, "paper_state.json")
        sp_state = {}
        if os.path.isfile(sp_path):
            with open(sp_path, encoding="utf-8") as handle:
                sp_state = json.load(handle) or {}
        blocked_dbl = desk_inx.anti_double_blocks(
            ticker=str(pick.get("ticker") or ""), sp_state=sp_state,
        )
        if blocked_dbl:
            print(alerts.format_skip_note(day, blocked_dbl))
            if not args.dry_run:
                logger.learn(f"{day}: no trade - {blocked_dbl}", "skip")
            return
    except Exception:
        pass
    try:
        desk = _desk()
        skip = desk.learning_skip(desk.load_learning(DESK_ROOT), "S&P-sized", desk.prob_bucket(pick["ask"]))
    except Exception:
        skip = ""
    if skip:
        print(skip)
        try:
            import desk_living
            desk_living.record_eval_features(
                DESK_ROOT, bot="kalshi-sized", action="skip",
                series=CFG.get("series") or "KXINXU",
                ticker=str(pick.get("ticker") or ""),
                ev={"side": pick.get("side"), "ask": pick.get("ask"), "confidence": pick.get("ask")},
                reasons=[skip], note=str(skip)[:160],
            )
        except Exception:
            pass
        return
    edge_proxy = 0.0
    try:
        desk = _desk()
        cfg = desk.load_settings(DESK_ROOT)
        venue_edge = float(desk.venue_min_edge("kalshi_inx", cfg))
        fee_one = paper_sim.taker_fee(1, pick["ask"])
        edge_proxy = max(0.0, (1.0 - float(pick["ask"]) - float(fee_one)))
        if venue_edge > 0 and edge_proxy + 1e-12 < venue_edge:
            reason = f"venue kalshi_inx edge {edge_proxy:.3f} < {venue_edge:.3f}"
            print(alerts.format_skip_note(day, reason))
            try:
                import desk_living
                desk_living.record_eval_features(
                    DESK_ROOT, bot="kalshi-sized", action="skip",
                    series=CFG.get("series") or "KXINXU",
                    ticker=str(pick.get("ticker") or ""),
                    ev={"side": pick.get("side"), "ask": pick.get("ask"), "edge": edge_proxy,
                        "fee": fee_one, "confidence": pick.get("ask")},
                    reasons=[reason], note=reason[:160],
                )
            except Exception:
                pass
            return
        # Twin +1¢: sized must clear venue floor + 0.01 vs residual edge.
        try:
            import desk_inx
            twin_block = desk_inx.twin_edge_blocks(
                sized_edge=edge_proxy, venue_edge=venue_edge, extra=0.01,
            )
            if twin_block:
                print(alerts.format_skip_note(day, twin_block))
                if not args.dry_run:
                    logger.learn(f"{day}: no trade - {twin_block}", "skip")
                try:
                    import desk_living
                    desk_living.record_eval_features(
                        DESK_ROOT, bot="kalshi-sized", action="skip",
                        series=CFG.get("series") or "KXINXU",
                        ticker=str(pick.get("ticker") or ""),
                        ev={"side": pick.get("side"), "ask": pick.get("ask"), "edge": edge_proxy},
                        reasons=[twin_block], note=str(twin_block)[:160],
                    )
                except Exception:
                    pass
                return
        except Exception:
            pass
        blocked = desk.correlation_blocks(DESK_ROOT, "kalshi-sized", pick["side"], edge_proxy)
        if blocked:
            print(blocked)
            try:
                import desk_living
                desk_living.record_eval_features(
                    DESK_ROOT, bot="kalshi-sized", action="skip",
                    series=CFG.get("series") or "KXINXU",
                    ticker=str(pick.get("ticker") or ""),
                    ev={"side": pick.get("side"), "ask": pick.get("ask"), "edge": edge_proxy},
                    reasons=[blocked], note=str(blocked)[:160],
                )
            except Exception:
                pass
            return
        gate = desk.entry_gate(DESK_ROOT)
        if gate:
            print(gate)
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
        print(f"Desk sizing unavailable ({exc}); falling back to local max stake.")
        n = risk_manager.stake_contracts(pick["ask"], bankroll=state["bankroll"])
    if n < 1:
        print(alerts.format_skip_note(day, "not enough paper bankroll / stake for 1 contract after fee"))
        if not args.dry_run:
            logger.learn(f"{day}: no trade - bankroll/stake too small after fee", "skip")
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
        f"Sized paper buy. Ask in {CFG['band_min_ask']*100:.0f}-"
        f"{CFG['band_max_ask']*100:.0f}c band; desk Kelly-lite sized {n} contracts."
    )
    try:
        import desk_profit
        pos["risk_factor"] = desk_profit.risk_factor_for("kalshi-sized", pick["side"])
        pos["gap_at_entry"] = round(edge_proxy, 4)
        pos["fair_at_entry"] = round(float(pick["ask"]), 4)
    except Exception:
        pass
    try:
        import desk_living
        fee_one = paper_sim.taker_fee(1, pick["ask"])
        desk_living.record_eval_features(
            DESK_ROOT, bot="kalshi-sized", action="buy",
            series=CFG.get("series") or "KXINXU",
            ticker=str(pick.get("ticker") or ""),
            ev={"side": pick.get("side"), "ask": pick.get("ask"), "fee": fee_one,
                "edge": edge_proxy, "confidence": pick.get("ask")},
            note="paper buy kalshi-sized",
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
                proceeds = round(contracts * float(bid), 4)
                pnl = round(proceeds - float(pos.get("cost") or 0) - float(pos.get("fee") or 0), 4)
                state["bankroll"] = round(float(state["bankroll"]) + proceeds, 4)
                pos.update({
                    "status": "sold",
                    "exit": "model-flip bid under 50c",
                    "exit_price": bid,
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
                        fee=pos.get("fee") or 0.0,
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
