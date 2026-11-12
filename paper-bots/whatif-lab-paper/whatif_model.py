"""What-if lab: what the towers' logged-but-not-bought rows would have made.

Two reports, both from the towers' own ``research.jsonl`` logs.

1. Missed trades. Each tower logs every priced contract on every check. A row
   whose edge after fee cleared the tower's floor but was not bought is a
   "missed" row. It is grouped by why:

   - ``log_only``: priced only for calibration (e.g. weather before its window,
     GDP more than 45 days out)
   - ``trust_cap``: edge over the tower's trust cap
   - ``rule_buy``: rows the buy rule passed (for comparison; capacity limits
     like max open are ignored, so this is the rule's own record)

   The first qualifying sighting of a contract is taken as the would-be entry:
   one contract at that ask, plus fee. Once Kalshi settles it, P&L per
   contract is ``(1 if won else 0) − ask − fee``. A bucket with 50+ settled
   rows whose 95% low end is above $0 is flagged "worth a look".

2. Cross-venue gaps (the Polymarket towers). A gap "episode" is a run of
   consecutive checks where a contract's edge stayed at or above the floor.
   It reports how many episodes, how long they lasted, and the typical peak
   edge. Short-lived gaps are hard to catch in real life.

3. Maker check. Instead of paying the ask, what if the tower had rested a bid
   1 cent above the best bid for 30 minutes? Our bid would be the new best
   bid, so any public trade in that window where a seller hit a bid at or
   below our price would have filled us first. Fills are graded at
   settlement with a maker fee of 0.0175 × p × (1 − p) a contract (Kalshi's
   maker rate; many series charge none). It is compared with taking the ask
   on the same contracts. Queue size is ignored, so fill rates run high.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import statistics

MIN_N = 50
Z95 = 1.96
MAX_READS = 40
RECHECK_HOURS = 12          # an unsettled contract is read again after this
GAP_TOWERS = ("poly-sports-lean", "soccer-tennis-lean")
GAP_DAYS = 7
KEEP_RESULTS = 20000
MAKER_WINDOW_MIN = 30
MAKER_RATE = 0.0175
MAKER_READS = 20


def _when(text) -> dt.datetime | None:
    try:
        when = dt.datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=dt.timezone.utc)


def _num(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def read_log(folder: str) -> list[dict]:
    rows = []
    for name in ("research.jsonl.1", "research.jsonl"):
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and _when(row.get("at")):
                    rows.append(row)
    rows.sort(key=lambda r: r["at"])
    return rows


def bucket_of(d: dict, floor: float) -> str | None:
    edge, ask = _num(d.get("edge")), _num(d.get("ask"))
    if edge is None or ask is None or not d.get("ticker") or d.get("side") not in ("yes", "no"):
        return None
    if not 0.0 < ask < 1.0 or edge + 1e-12 < floor:
        return None
    if d.get("action") == "buy":
        return "rule_buy"
    reason = str(d.get("reason") or "")
    if "trust cap" in reason:
        return "trust_cap"
    if reason.startswith("edge ") or reason.startswith("ask ") or reason.startswith("need ") or "out of range" in reason:
        return None
    return "log_only"


def first_sightings(log: list[dict], floor: float) -> dict:
    """{(bucket, ticker, side): entry} — first qualifying sighting per contract and bucket."""
    out: dict = {}
    for row in log:
        for d in row.get("decisions") or []:
            bucket = bucket_of(d, floor)
            if bucket is None:
                continue
            key = (bucket, d["ticker"], d["side"])
            if key not in out:
                out[key] = {"at": row["at"], "ask": _num(d["ask"]), "fee": _num(d.get("fee")) or 0.0,
                            "edge": _num(d["edge"]), "bid": _num(d.get("bid"))}
    return out


def stats(pnls: list[float]) -> dict:
    n = len(pnls)
    out = {"n": n, "avg": None, "low": None, "high": None, "hit_rate": None, "worth_a_look": False}
    if not n:
        return out
    avg = sum(pnls) / n
    out.update(avg=round(avg, 4), hit_rate=round(sum(1 for p in pnls if p > 0) / n, 3))
    if n > 1:
        half = Z95 * statistics.stdev(pnls) / math.sqrt(n)
        out.update(low=round(avg - half, 4), high=round(avg + half, 4))
        out["worth_a_look"] = bool(n >= MIN_N and avg - half > 0)
    return out


def missed(towers: list[tuple[str, float, list[dict]]], results: dict, waiting: dict, fetch,
           now: dt.datetime, max_reads: int = MAX_READS):
    """towers: [(id, floor, log)]. results/waiting are updated in place.

    Returns (report, reads, pending). Oldest sightings are read first; a contract
    that was still open is read again only after RECHECK_HOURS.
    """
    reads = pending = 0
    sightings = {t: first_sightings(log, floor) for t, floor, log in towers}
    todo = sorted({(e["at"], k[1]) for s in sightings.values() for k, e in s.items() if k[1] not in results})
    for _, ticker in todo:
        last = _when(waiting.get(ticker))
        if last and now - last < dt.timedelta(hours=RECHECK_HOURS):
            continue
        if ticker in results:
            continue
        if reads >= max_reads:
            break
        reads += 1
        try:
            result = str((fetch(ticker) or {}).get("result") or "").lower()
        except Exception:  # noqa: BLE001 - a failed read waits for the next run
            result = ""
        if result in ("yes", "no"):
            results[ticker] = result
            waiting.pop(ticker, None)
        else:
            waiting[ticker] = now.isoformat(timespec="seconds")
    report = {}
    for tower_id, _, _ in towers:
        pnls: dict = {}
        for (bucket, ticker, side), entry in sightings[tower_id].items():
            result = results.get(ticker)
            if result not in ("yes", "no"):
                pending += 1
                continue
            won = 1.0 if result == side else 0.0
            pnls.setdefault(bucket, []).append(won - entry["ask"] - entry["fee"])
        report[tower_id] = {b: stats(p) for b, p in sorted(pnls.items())}
    return report, reads, pending


def maker_price(entry: dict) -> float | None:
    bid, ask = entry.get("bid"), entry.get("ask")
    if bid is None or ask is None:
        return None
    price = round(bid + 0.01, 2)
    return price if 0.02 <= price < ask - 1e-9 else None


def maker_filled(trades: list[dict], side: str, price: float) -> bool:
    """A seller hit a bid at or below our price on our side (we would have been first)."""
    for t in trades or []:
        taker = str(t.get("taker_side") or t.get("taker_outcome_side") or "").lower()
        if side == "yes" and taker == "no":
            px = _num(t.get("yes_price_dollars"))
        elif side == "no" and taker == "yes":
            px = _num(t.get("no_price_dollars"))
        else:
            continue
        if px is not None and px <= price + 1e-9:
            return True
    return False


def maker(towers: list[tuple[str, float, list[dict]]], results: dict, quotes: dict, trades_fetch,
          now: dt.datetime, max_reads: int = MAKER_READS):
    """quotes {key: {"price", "filled"}} is updated in place. Returns (report, reads)."""
    reads = 0
    report = {}
    for tower_id, floor, log in towers:
        rows = []
        for (bucket, ticker, side), entry in sorted(first_sightings(log, floor).items(), key=lambda kv: kv[1]["at"]):
            price = maker_price(entry)
            if price is None:
                continue
            key = f"{ticker}|{side}"
            got = quotes.get(key)
            start = _when(entry["at"])
            end = start + dt.timedelta(minutes=MAKER_WINDOW_MIN)
            if got is None:
                if end > now or reads >= max_reads:
                    continue
                reads += 1
                try:
                    trades = trades_fetch(ticker, int(start.timestamp()), int(end.timestamp()))
                except Exception:  # noqa: BLE001 - a failed read waits for the next run
                    continue
                got = quotes[key] = {"price": price, "filled": maker_filled(trades, side, price)}
            result = results.get(ticker)
            if result not in ("yes", "no"):
                continue
            won = 1.0 if result == side else 0.0
            taker = won - entry["ask"] - entry["fee"]
            made = (won - got["price"] - MAKER_RATE * got["price"] * (1 - got["price"])) if got["filled"] else None
            rows.append((taker, made))
        if not rows:
            report[tower_id] = {"n": 0}
            continue
        fills = [m for _, m in rows if m is not None]
        report[tower_id] = {
            "n": len(rows),
            "fill_rate": round(len(fills) / len(rows), 3),
            "maker_avg": round(sum(fills) / len(fills), 4) if fills else None,
            "taker_avg_same": round(sum(t for t, m in rows if m is not None) / len(fills), 4) if fills else None,
            "taker_avg_all": round(sum(t for t, _ in rows) / len(rows), 4),
        }
    return report, reads


def gaps(log: list[dict], floor: float, every_sec: int, now: dt.datetime, days: int = GAP_DAYS) -> dict:
    """Episodes of edge ≥ floor over consecutive checks, per contract, in the last ``days``."""
    cutoff = now - dt.timedelta(days=days)
    checks = [r for r in log if _when(r["at"]) >= cutoff]
    live: dict = {}
    done = []
    for i, row in enumerate(checks):
        seen = set()
        for d in row.get("decisions") or []:
            edge = _num(d.get("edge"))
            if edge is None or edge + 1e-12 < floor or not d.get("ticker"):
                continue
            key = (d["ticker"], d.get("side"))
            seen.add(key)
            ep = live.setdefault(key, {"start": row["at"], "last": row["at"], "checks": 0, "peak": edge})
            ep["last"], ep["checks"], ep["peak"] = row["at"], ep["checks"] + 1, max(ep["peak"], edge)
        for key in [k for k in live if k not in seen]:
            done.append(live.pop(key))
    done.extend(live.values())
    priced = sum(1 for r in checks for d in r.get("decisions") or [] if _num(d.get("edge")) is not None)
    hits = sum(1 for r in checks for d in r.get("decisions") or [] if (_num(d.get("edge")) or -9) + 1e-12 >= floor)
    if not done:
        return {"checks": len(checks), "episodes": 0, "share_over_floor": round(hits / priced, 4) if priced else None}
    mins = [(_when(e["last"]) - _when(e["start"])).total_seconds() / 60 + every_sec / 60 for e in done]
    one = sum(1 for e in done if e["checks"] == 1)
    return {
        "checks": len(checks),
        "episodes": len(done),
        "share_over_floor": round(hits / priced, 4) if priced else None,
        "median_minutes": round(statistics.median(mins), 1),
        "longest_minutes": round(max(mins), 1),
        "one_check_share": round(one / len(done), 3),
        "median_peak_edge": round(statistics.median(e["peak"] for e in done), 4),
    }


def run(towers: list[dict], root: str, prior: dict, fetch, now: dt.datetime, max_reads: int = MAX_READS,
        trades_fetch=None) -> dict:
    """towers: tower specs (id, folder, floor, every_sec)."""
    results = dict(prior.get("results") or {})
    waiting = dict(prior.get("waiting") or {})
    logs = {s["id"]: read_log(os.path.join(root, s["folder"])) for s in towers}
    report, reads, pending = missed([(s["id"], float(s["floor"]), logs[s["id"]]) for s in towers],
                                    results, waiting, fetch, now, max_reads)
    quotes = dict(prior.get("maker_quotes") or {})
    tower_logs = [(s["id"], float(s["floor"]), logs[s["id"]]) for s in towers]
    maker_report, maker_reads = maker(tower_logs, results, quotes, trades_fetch, now) if trades_fetch else ({}, 0)
    gap = {s["id"]: gaps(logs[s["id"]], float(s["floor"]), int(s.get("every_sec") or 300), now)
           for s in towers if s["id"] in GAP_TOWERS}
    return {"updated": now.isoformat(timespec="seconds"), "paper_only": True, "min_n": MIN_N,
            "missed": report, "gaps": gap, "maker": maker_report, "reads": reads + maker_reads,
            "pending": pending, "maker_quotes": dict(list(quotes.items())[-KEEP_RESULTS:]),
            "results": dict(list(results.items())[-KEEP_RESULTS:]),
            "waiting": dict(list(waiting.items())[-KEEP_RESULTS:])}


NAMES = {"log_only": "log-only", "trust_cap": "over trust cap", "rule_buy": "rule said buy"}


def card(body: dict) -> str:
    settled = sum(s["n"] for t in body["missed"].values() for s in t.values())
    line = f"What-if lab: {settled} settled would-be trades across {len(body['missed'])} towers"
    flags = [f"{t} {NAMES[b]} (n {s['n']}, avg {s['avg']:+.3f})"
             for t, by in body["missed"].items() for b, s in by.items() if s["worth_a_look"] and b != "rule_buy"]
    line += ("; worth a look: " + ", ".join(flags)) if flags else "; nothing worth a look yet"
    if body["pending"]:
        line += f"; {body['pending']} not settled yet"
    gaps = [f"{t} {g['episodes']} gaps, median {g['median_minutes']:.0f} min"
            for t, g in body["gaps"].items() if g.get("episodes")]
    if gaps:
        line += ". Gaps (7d): " + "; ".join(gaps)
    makers = [f"{t} fills {m['fill_rate']:.0%}, maker {m['maker_avg']:+.3f} vs taker {m['taker_avg_same']:+.3f}"
              for t, m in (body.get("maker") or {}).items() if m.get("n") and m.get("maker_avg") is not None]
    if makers:
        line += ". Maker check: " + "; ".join(makers)
    return line + "."
