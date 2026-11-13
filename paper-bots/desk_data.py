"""Shared data tools for recordings and decision rows. Paper only, read-only.

Nothing here buys, sells or changes a tower. It reads files the towers and the
window history already write, and turns them into plain tables.

* **Decision rows** (plan steps 266-270): one shared shape for every check of
  every tower: inputs, fair, price, edge, action and reason. ``decision_row``
  builds one, ``check_row`` lists what is wrong with one, and
  ``from_research`` turns a line of a shadow tower's ``research.jsonl`` into
  decision rows without touching the tower.
* **Privacy** (262): ``find_private`` and ``strip_private`` keep keys, tokens,
  cookies, emails and account ids out of anything saved.
* **Keeping** (271): ``prune_days`` deletes day files older than 180 days.
* **Summaries** (272): checks, buys and skips by reason for one day.
* **Calibration** (273, 275, 277-279): when we said 70%, how often did it win,
  split by family (15-minute kept apart from daily), minutes left and volume.
  A tower is flagged when it is off by more than 5 points with 50+ results.
* **Data quality** (299-302): missing minutes, duplicate rows, out-of-order
  times; small gaps may be filled from public history and are marked
  ``filled``. Our own trade records are never filled.
* **Exports** (303-304): a month of trades as CSV (losses included) and a
  month of decision rows as gzip.
* **Queries and index** (306-308): "every BNB trade this week", "every skip
  for price outside range", rows by tower, market and hour.
* **Rule versions** (314-316): which rule version was live when a trade
  opened, and results split by version. Losses always count.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import gzip
import io
import json
import math
import os
import re

FORMAT_VERSION = 1
KEEP_DAYS = 180
CALIB_MIN_N = 50
CALIB_FLAG_POINTS = 5.0
ACTIONS = ("buy", "skip", "sell", "hold")
REQUIRED = ("v", "tower", "at", "market", "side", "inputs", "fair", "price", "edge", "action", "reason")
DAY_FILE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.jsonl(\.gz)?$")

# Key names that must never be saved in a recording or a decision row.
PRIVATE_KEY = re.compile(
    r"(api[_-]?key|secret|token|password|passwd|auth|cookie|session|signature|private|"
    r"email|account[_-]?id|user[_-]?id|wallet|credential|bearer|service[_-]?key)",
    re.IGNORECASE,
)
PRIVATE_VALUE = re.compile(r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|\bBearer\s+[A-Za-z0-9._-]{12,}|"
                           r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")


# ------------------------------------------------------------------ small helpers
def num(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def parse_at(value) -> dt.datetime | None:
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)
    try:
        out = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return out if out.tzinfo else out.replace(tzinfo=dt.timezone.utc)


def series_of(ticker: str) -> str:
    return str(ticker or "").split("-", 1)[0].upper()


def family_of(ticker: str) -> str:
    """'15m' for the 15-minute series, 'daily' for everything else (kept apart, step 277)."""
    return "15m" if series_of(ticker).endswith("15M") else "daily"


def minutes_bucket(minutes) -> str | None:
    """Minutes left before a 15-minute close, in 3-minute buckets (step 278)."""
    m = num(minutes)
    if m is None or m < 0:
        return None
    lo = min(12, int(m // 3) * 3)
    return f"{lo}-{lo + 3}"


def volume_bucket(volume) -> str | None:
    """Thin vs busy market by contracts traded (step 279)."""
    v = num(volume)
    if v is None:
        return None
    if v < 100:
        return "thin"
    if v < 1000:
        return "normal"
    return "busy"


# ------------------------------------------------------------------ privacy (262)
def find_private(obj, path: str = "") -> list[str]:
    """Paths of anything that looks private: a private key name or a private-looking value."""
    found = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            here = f"{path}.{key}" if path else str(key)
            if PRIVATE_KEY.search(str(key)):
                found.append(here)
                continue
            found.extend(find_private(value, here))
    elif isinstance(obj, (list, tuple)):
        for i, value in enumerate(obj):
            found.extend(find_private(value, f"{path}[{i}]"))
    elif isinstance(obj, str) and PRIVATE_VALUE.search(obj):
        found.append(path or "<value>")
    return found


def strip_private(obj):
    """A copy with private-looking keys dropped and private-looking strings blanked."""
    if isinstance(obj, dict):
        return {k: strip_private(v) for k, v in obj.items() if not PRIVATE_KEY.search(str(k))}
    if isinstance(obj, list):
        return [strip_private(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(strip_private(v) for v in obj)
    if isinstance(obj, str) and PRIVATE_VALUE.search(obj):
        return "[removed]"
    return obj


# ------------------------------------------------------------------ decision rows (266-270)
def decision_row(tower: str, at, market: str, side: str, *, fair=None, price=None, edge=None,
                 action: str = "skip", reason: str = "", inputs: dict | None = None,
                 minutes_left=None, volume=None, event: str = "") -> dict:
    """One check of one side of one market, in the shared format."""
    when = parse_at(at)
    row = {
        "v": FORMAT_VERSION,
        "tower": str(tower or ""),
        "at": when.isoformat(timespec="seconds") if when else str(at or ""),
        "market": str(market or ""),
        "event": str(event or ""),
        "side": str(side or "yes").lower(),
        "inputs": strip_private(dict(inputs or {})),
        "fair": None if num(fair) is None else round(num(fair), 4),
        "price": None if num(price) is None else round(num(price), 4),
        "edge": None if num(edge) is None else round(num(edge), 4),
        "action": str(action or "skip").lower(),
        "reason": str(reason or ""),
        "family": family_of(market),
    }
    if num(minutes_left) is not None:
        row["minutes_left"] = round(num(minutes_left), 2)
    if num(volume) is not None:
        row["volume"] = round(num(volume), 2)
    return row


def check_row(row) -> list[str]:
    """Plain list of problems with one decision row. Empty means it is good (step 270)."""
    if not isinstance(row, dict):
        return ["not a dict"]
    bad = [f"missing {key}" for key in REQUIRED if key not in row]
    if bad:
        return bad
    if row["v"] != FORMAT_VERSION:
        bad.append(f"format version {row['v']} is not {FORMAT_VERSION}")
    if not row["tower"]:
        bad.append("tower is empty")
    if parse_at(row["at"]) is None:
        bad.append("at is not a time")
    if not row["market"]:
        bad.append("market is empty")
    if row["side"] not in ("yes", "no"):
        bad.append("side is not yes or no")
    if row["action"] not in ACTIONS:
        bad.append(f"action {row['action']!r} is not one of {', '.join(ACTIONS)}")
    if not isinstance(row["inputs"], dict):
        bad.append("inputs is not a dict")
    for key in ("fair", "price", "edge"):
        value = row[key]
        if value is not None and num(value) is None:
            bad.append(f"{key} is not a number")
    for key in ("fair", "price"):
        value = num(row[key])
        if value is not None and not (0.0 <= value <= 1.0):
            bad.append(f"{key} {value} is outside 0-1")
    if row["action"] == "buy" and (row["fair"] is None or row["price"] is None or row["edge"] is None):
        bad.append("a buy needs fair, price and edge")
    if row["action"] == "skip" and not row["reason"]:
        bad.append("a skip needs a reason")
    if find_private(row):
        bad.append("holds something private")
    return bad


def from_research(tower: str, line: dict) -> list[dict]:
    """Shared rows from one line of a shadow tower's research.jsonl (fair, skip reason, edge)."""
    out = []
    at = (line or {}).get("at")
    for d in (line or {}).get("decisions") or []:
        if not isinstance(d, dict) or not d.get("ticker"):
            continue
        out.append(decision_row(
            tower, at, d.get("ticker"), d.get("side") or "yes", fair=d.get("fair"), price=d.get("ask"),
            edge=d.get("edge"), action=d.get("action") or "skip",
            reason=d.get("reason") or ("bought" if d.get("action") == "buy" else "no reason logged"),
            inputs={k: d[k] for k in ("bid", "fee", "floor", "why", "group", "tape_volume") if k in d},
            event=d.get("event") or "",
        ))
    return out


def read_research(path: str, tower: str) -> list[dict]:
    rows = []
    for candidate in (path + ".1", path):
        try:
            with open(candidate, encoding="utf-8") as handle:
                for text in handle:
                    try:
                        rows.extend(from_research(tower, json.loads(text)))
                    except ValueError:
                        continue
        except OSError:
            continue
    return rows


# ------------------------------------------------------------------ day files (261, 263, 271)
def write_rows(folder: str, day: dt.date, rows: list[dict]) -> str:
    """Append rows to ``folder/YYYY-MM-DD.jsonl.gz`` (one gzip member per call)."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, day.isoformat() + ".jsonl.gz")
    body = "".join(json.dumps(strip_private(r), separators=(",", ":")) + "\n" for r in rows)
    with gzip.open(path, "ab") as handle:
        handle.write(body.encode("utf-8"))
    return path


def read_rows(path: str) -> list[dict]:
    out = []
    opener = gzip.open if path.endswith(".gz") else open
    try:
        with opener(path, "rt", encoding="utf-8") as handle:
            for text in handle:
                try:
                    row = json.loads(text)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except (OSError, EOFError):
        return out
    return out


def day_files(folder: str) -> list[str]:
    if not os.path.isdir(folder):
        return []
    return sorted(f for f in os.listdir(folder) if DAY_FILE.match(f))


def load_day(folder: str, day, series: str | None = None) -> list[dict]:
    """One day of recordings, optionally for one series only (step 263)."""
    stamp = day.isoformat() if hasattr(day, "isoformat") else str(day)
    rows = []
    for name in (stamp + ".jsonl.gz", stamp + ".jsonl"):
        rows.extend(read_rows(os.path.join(folder, name)))
    if series:
        want = series.upper()
        rows = [r for r in rows if str(r.get("series") or series_of(r.get("ticker") or r.get("market"))) == want]
    return rows


def prune_days(folder: str, today: dt.date, keep_days: int = KEEP_DAYS) -> list[str]:
    """Delete day files older than ``keep_days`` (step 271). Today's file always stays."""
    cutoff = today - dt.timedelta(days=int(keep_days))
    gone = []
    for name in day_files(folder):
        try:
            day = dt.date.fromisoformat(DAY_FILE.match(name).group(1))
        except ValueError:
            continue
        if day < cutoff and day != today:
            try:
                os.remove(os.path.join(folder, name))
                gone.append(name)
            except OSError:
                pass
    return gone


# ------------------------------------------------------------------ summaries (272)
def reason_kind(reason: str) -> str:
    """Group skip reasons by their words, not their numbers."""
    text = re.sub(r"[-+]?\d+(\.\d+)?", "#", str(reason or "").lower())
    text = re.sub(r"\(.*?\)", "", text)
    return re.sub(r"\s+", " ", text).strip(" .;:") or "no reason"


def daily_summary(rows: list[dict]) -> dict:
    checks = {(r.get("tower"), r.get("at")) for r in rows}
    buys = [r for r in rows if r.get("action") == "buy"]
    skips = [r for r in rows if r.get("action") == "skip"]
    by_tower = collections.defaultdict(lambda: {"checks": set(), "buys": 0, "skips": 0})
    for r in rows:
        t = by_tower[r.get("tower") or "?"]
        t["checks"].add(r.get("at"))
        t["buys" if r.get("action") == "buy" else "skips"] += r.get("action") in ("buy", "skip")
    reasons = collections.Counter(reason_kind(r.get("reason")) for r in skips)
    return {
        "rows": len(rows),
        "checks": len(checks),
        "buys": len(buys),
        "skips": len(skips),
        "skip_reasons": reasons.most_common(),
        "towers": {k: {"checks": len(v["checks"]), "buys": v["buys"], "skips": v["skips"]}
                   for k, v in sorted(by_tower.items())},
    }


# ------------------------------------------------------------------ calibration (273, 275, 277-279)
def calibration(pairs, band: float = 0.10) -> dict:
    """``pairs`` = iterable of (said, won). Returns buckets and a flag (step 275).

    ``off_points`` is the gap between the average said and the real win rate, in
    points. The flag needs at least 50 results and a gap above 5 points.
    """
    buckets = collections.defaultdict(lambda: [0, 0, 0.0])
    n = wins = 0
    said_sum = 0.0
    for said, won in pairs:
        p = num(said)
        if p is None or not (0.0 <= p <= 1.0):
            continue
        lo = min(1.0 - band, math.floor(round(p / band, 6)) * band)
        key = f"{lo:.2f}-{lo + band:.2f}"
        b = buckets[key]
        b[0] += 1
        b[1] += 1 if won else 0
        b[2] += p
        n += 1
        wins += 1 if won else 0
        said_sum += p
    rows = []
    for key in sorted(buckets):
        count, w, s = buckets[key]
        rows.append({"band": key, "n": count, "wins": w, "said": round(s / count, 4),
                     "won": round(w / count, 4), "gap_points": round(100 * (w / count - s / count), 1)})
    off = round(100 * (wins / n - said_sum / n), 1) if n else None
    return {"n": n, "wins": wins, "said": round(said_sum / n, 4) if n else None,
            "won": round(wins / n, 4) if n else None, "off_points": off,
            "flag": bool(n >= CALIB_MIN_N and off is not None and abs(off) > CALIB_FLAG_POINTS),
            "counts": n >= CALIB_MIN_N, "bands": rows}


def tower_calibration(rows: list[dict], results: dict) -> dict:
    """Per tower, per family (15m apart from daily), from decision rows and settled results.

    ``results`` maps ticker -> "yes" / "no". For each tower and side, the last
    fair logged before settlement is the one scored (one result per market side).
    """
    last = {}
    for r in sorted(rows, key=lambda r: str(r.get("at") or "")):
        if r.get("fair") is None or r.get("market") not in results:
            continue
        last[(r.get("tower"), r.get("market"), r.get("side"))] = r
    groups = collections.defaultdict(list)
    for (tower, market, side), r in last.items():
        won = results[market] == side
        groups[(tower, r.get("family") or family_of(market))].append((r["fair"], won))
        mb = minutes_bucket(r.get("minutes_left"))
        if mb:
            groups[(tower, f"{r.get('family') or family_of(market)} {mb} min left")].append((r["fair"], won))
        vb = volume_bucket(r.get("volume"))
        if vb:
            groups[(tower, f"{r.get('family') or family_of(market)} {vb}")].append((r["fair"], won))
    out = collections.defaultdict(dict)
    for (tower, split), pairs in groups.items():
        out[tower][split] = calibration(pairs)
    return {tower: dict(splits) for tower, splits in sorted(out.items())}


def flagged_towers(table: dict) -> list[str]:
    """Plain lines for every tower/family off by more than 5 points with 50+ results."""
    lines = []
    for tower, splits in table.items():
        for split, cal in splits.items():
            if " " in split:  # only the whole-family rows raise a flag
                continue
            if cal.get("flag"):
                lines.append(f"{tower} {split}: said {100 * cal['said']:.0f}%, won {100 * cal['won']:.0f}% "
                             f"over {cal['n']} results ({cal['off_points']:+.1f} points)")
    return lines


# ------------------------------------------------------------------ data quality (299-302)
def quality_check(times, step_sec: int = 60, keys=None) -> dict:
    """Missing steps, duplicate rows and out-of-order times in one stream (step 299).

    ``times`` are the row times in file order; ``keys`` (same length, optional)
    are row identities for the duplicate count (defaults to the times).
    """
    stamps = [parse_at(t) for t in times]
    stamps_ok = [t for t in stamps if t is not None]
    keys = list(keys) if keys is not None else [t.isoformat() if t else None for t in stamps]
    dupes = sum(c - 1 for c in collections.Counter(keys).values() if c > 1)
    out_of_order = sum(1 for a, b in zip(stamps_ok, stamps_ok[1:]) if b < a)
    gaps, missing = [], 0
    ordered = sorted(set(stamps_ok))
    for a, b in zip(ordered, ordered[1:]):
        lost = int(round((b - a).total_seconds() / step_sec)) - 1
        if lost > 0:
            missing += lost
            gaps.append({"after": a.isoformat(timespec="seconds"), "before": b.isoformat(timespec="seconds"),
                         "missing": lost})
    return {"rows": len(stamps), "bad_times": len(stamps) - len(stamps_ok), "duplicates": dupes,
            "out_of_order": out_of_order, "missing": missing, "gaps": gaps,
            "ok": not (dupes or out_of_order or missing or len(stamps) != len(stamps_ok))}


OWN_RECORDS = frozenset({"trades", "closed", "open", "paper_account", "ledger", "lifetime", "book"})


def fill_small_gaps(points: list[dict], lookup, *, kind: str, step_sec: int = 60, max_gap: int = 5) -> list[dict]:
    """Fill gaps of up to ``max_gap`` steps from public history (step 301).

    ``lookup(at) -> dict | None`` reads the public history. Every filled row
    carries ``filled: True`` so it can always be told apart. Our own trade
    records are never filled (step 302): ``kind`` in OWN_RECORDS raises.
    """
    if str(kind).lower() in OWN_RECORDS:
        raise ValueError("our own trade records are never filled")
    rows = sorted((p for p in points if parse_at(p.get("at"))), key=lambda p: parse_at(p["at"]))
    out = []
    for a, b in zip(rows, rows[1:] + [None]):
        out.append(a)
        if b is None:
            break
        ta, tb = parse_at(a["at"]), parse_at(b["at"])
        lost = int(round((tb - ta).total_seconds() / step_sec)) - 1
        if not (0 < lost <= max_gap):
            continue
        for i in range(1, lost + 1):
            at = ta + dt.timedelta(seconds=step_sec * i)
            got = lookup(at)
            if got:
                out.append(dict(strip_private(got), at=at.isoformat(timespec="seconds"), filled=True))
    return out


# ------------------------------------------------------------------ exports (303-305)
TRADE_COLUMNS = ("tower", "ticker", "side", "label", "opened", "closed", "contracts", "ask", "cost",
                 "payout", "pnl", "exit", "result", "rule_version")


def month_of(value) -> str:
    when = parse_at(value)
    return when.strftime("%Y-%m") if when else ""


def trades_csv(closed_by_tower: dict, month: str) -> str:
    """Every closed trade of one month as CSV text. Losses included, nothing filtered."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TRADE_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for tower in sorted(closed_by_tower):
        for row in closed_by_tower[tower] or []:
            if month_of(row.get("closed") or row.get("opened")) != month:
                continue
            writer.writerow({**{k: row.get(k, "") for k in TRADE_COLUMNS}, "tower": tower})
    return buf.getvalue()


def decisions_gz(rows: list[dict], month: str) -> bytes:
    """One month of decision rows as gzip JSON lines."""
    body = "".join(json.dumps(strip_private(r), separators=(",", ":")) + "\n"
                   for r in rows if month_of(r.get("at")) == month)
    return gzip.compress(body.encode("utf-8"))


# ------------------------------------------------------------------ queries and index (306-308)
def query(rows, *, tower: str | None = None, market: str | None = None, action: str | None = None,
          reason: str | None = None, since=None, until=None) -> list[dict]:
    """Simple filters. ``market`` and ``reason`` match a part of the text, any case."""
    lo, hi = parse_at(since) if since else None, parse_at(until) if until else None
    out = []
    for r in rows:
        if tower and r.get("tower") != tower:
            continue
        name = str(r.get("market") or r.get("ticker") or "") + " " + str(r.get("label") or "")
        if market and market.lower() not in name.lower():
            continue
        if action and r.get("action", "buy" if r.get("contracts") else None) != action:
            continue
        if reason and reason.lower() not in str(r.get("reason") or "").lower():
            continue
        when = parse_at(r.get("at") or r.get("opened"))
        if (lo or hi) and when is None:
            continue
        if lo and when < lo:
            continue
        if hi and when >= hi:
            continue
        out.append(r)
    return out


def week_start(now: dt.datetime) -> dt.datetime:
    day = now.astimezone(dt.timezone.utc)
    return (day - dt.timedelta(days=day.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def trades_this_week(trades, coin: str, now: dt.datetime) -> list[dict]:
    """'Show every BNB trade this week.'"""
    return query(trades, market=coin, since=week_start(now))


def skips_outside_range(rows) -> list[dict]:
    """'Show every skip for price outside range.'"""
    return [r for r in query(rows, action="skip") if "outside" in str(r.get("reason") or "").lower()]


class DecisionIndex:
    """Rows indexed by tower, market and hour (step 308)."""

    def __init__(self, rows):
        self.rows = list(rows)
        self.by_tower = collections.defaultdict(list)
        self.by_market = collections.defaultdict(list)
        self.by_hour = collections.defaultdict(list)
        for i, r in enumerate(self.rows):
            self.by_tower[r.get("tower")].append(i)
            self.by_market[r.get("market")].append(i)
            when = parse_at(r.get("at"))
            if when:
                self.by_hour[when.strftime("%Y-%m-%dT%H")].append(i)

    def find(self, tower=None, market=None, hour=None) -> list[dict]:
        sets = []
        if tower is not None:
            sets.append(set(self.by_tower.get(tower, ())))
        if market is not None:
            sets.append(set(self.by_market.get(market, ())))
        if hour is not None:
            sets.append(set(self.by_hour.get(hour, ())))
        if not sets:
            return list(self.rows)
        keep = set.intersection(*sets)
        return [self.rows[i] for i in sorted(keep)]


# ------------------------------------------------------------------ rule versions (314-316)
RULE_VERSIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rule_versions.json")


def load_rule_versions(path: str = RULE_VERSIONS_FILE) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    rows = data.get("versions") if isinstance(data, dict) else data
    return [r for r in rows or [] if isinstance(r, dict) and r.get("tower") and parse_at(r.get("start"))]


def version_at(versions: list[dict], tower: str, at) -> str:
    """The rule version live for ``tower`` at time ``at`` ('v0' before the first record)."""
    when = parse_at(at)
    best, best_start = "v0", None
    for v in versions:
        if v.get("tower") != tower:
            continue
        start = parse_at(v.get("start"))
        if when is not None and start <= when and (best_start is None or start >= best_start):
            best, best_start = str(v.get("version")), start
    return best


def tag_trades(trades: list[dict], versions: list[dict], tower: str) -> list[dict]:
    """Copies of the trades with ``rule_version`` set from the time each one opened (step 315)."""
    return [dict(t, rule_version=t.get("rule_version") or version_at(versions, tower, t.get("opened")))
            for t in trades]


def results_by_version(trades: list[dict], versions: list[dict], tower: str) -> list[dict]:
    """Closed results split by rule version (step 316). Losses always count."""
    groups = collections.OrderedDict()
    for t in tag_trades(trades, versions, tower):
        pnl = num(t.get("pnl"))
        if pnl is None:
            continue
        g = groups.setdefault(t["rule_version"], {"version": t["rule_version"], "n": 0, "wins": 0,
                                                   "losses": 0, "pnl": 0.0})
        g["n"] += 1
        g["wins" if pnl > 0 else "losses"] += 1 if pnl != 0 else 0
        g["pnl"] = round(g["pnl"] + pnl, 2)
    return list(groups.values())
