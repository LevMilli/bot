"""Past-slip history for the dashboard picks list.

Every figure comes from a number that was stored. A missing stake, payout,
return, time, or line stays "unknown". Nothing here fills a gap with zero
or with the clock right now.
"""

from __future__ import annotations

import html
import math
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Chicago")
UNKNOWN = "unknown"
SLIP_PAGE = 20
FILTERS = ("all", "hits", "misses", "open")

_PICK_RESULT = {
    "win": "hit",
    "loss": "miss",
    "push": "push",
    "void": "void",
    "open": "open",
}
_RESULT_LABEL = {
    "hit": "Hit",
    "miss": "Miss",
    "push": "Push",
    "void": "Void",
    "open": "Open",
}
_LEG_GRADE = {"hit": "hit", "miss": "miss", "push": "push", "open": "open", "void": "void"}
_LINE = re.compile(r"\b(?:over|under|more|less)\s+(-?\d+(?:\.\d+)?)\b", re.I)
_EMPTY = {
    "all": "No slips in this list.",
    "hits": "No hits in this list.",
    "misses": "No misses in this list.",
    "open": "No open slips in this list.",
}


def _get(row, key, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def _num(value):
    """A stored finite number, or None when the field was empty."""
    if value is None or isinstance(value, bool) or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _shown(value) -> str:
    text = _text(value)
    return text if text else UNKNOWN


def parse_when(raw):
    """A stored timestamp as America/Chicago. None when it was not stored or will not parse."""
    if isinstance(raw, datetime):
        when = raw
    else:
        text = _text(raw)
        if not text:
            return None
        try:
            when = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(TZ)


def clock_text(raw) -> str:
    when = parse_when(raw)
    if when is None:
        return UNKNOWN
    hour = str(int(when.strftime("%I")))
    return f"{when.strftime('%b')} {when.day}, {when.year}, {hour}:{when.strftime('%M %p')} CT"


def duration_text(start, end) -> str:
    """Logged time to settled time. Unknown when either timestamp was not stored."""
    opened = parse_when(start)
    settled = parse_when(end)
    if opened is None or settled is None:
        return UNKNOWN
    seconds = int((settled - opened).total_seconds())
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return sign + " ".join(parts)


def plain_money(value) -> str:
    number = _num(value)
    if number is None:
        return UNKNOWN
    number = round(number, 2) + 0.0
    if number < 0:
        return f"-${abs(number):,.2f}"
    return f"${number:,.2f}"


def signed_money(value) -> str:
    number = _num(value)
    if number is None:
        return UNKNOWN
    number = round(number, 2) + 0.0
    if number == 0:
        number = 0.0
    sign = "+" if number >= 0 else "-"
    return f"{sign}${abs(number):,.2f}"


def _signed_points(number: float) -> str:
    number = round(number, 2) + 0.0
    if number == 0:
        number = 0.0
    sign = "+" if number >= 0 else "-"
    text = f"{abs(number):.2f}".rstrip("0").rstrip(".")
    return f"{sign}{text or '0'}"


def pick_result(status) -> str:
    return _PICK_RESULT.get(_text(status).lower(), UNKNOWN)


def leg_grade(status) -> str:
    return _LEG_GRADE.get(_text(status).lower(), UNKNOWN)


def _logged_line(pick, legs) -> float | None:
    direct = _num(_get(pick, "line"))
    if direct is not None:
        return direct
    found: list[float] = []
    for leg in legs:
        number = _num(_get(leg, "line"))
        if number is None:
            match = _LINE.search(_text(_get(leg, "text")))
            if match:
                number = float(match.group(1))
        if number is None or number in found:
            continue
        found.append(number)
    if len(found) == 1:
        return found[0]
    return None


def _settled_price(pick):
    for key in ("settled_price", "settle_price"):
        number = _num(_get(pick, key))
        if number is not None:
            return number
    return None


def slippage_text(pick, legs) -> str:
    """Returned versus the logged payout, and a settled price versus the logged line.

    Each comparison is shown only when both of its numbers were stored.
    A dollar return is not compared with a points line.
    """
    parts = []
    returned = _num(_get(pick, "returned"))
    payout = _num(_get(pick, "payout"))
    if returned is not None and payout is not None:
        parts.append(signed_money(returned - payout) + " vs payout")
    settled = _settled_price(pick)
    line = _logged_line(pick, legs)
    if settled is not None and line is not None:
        parts.append(_signed_points(settled - line) + " vs line")
    return " · ".join(parts) if parts else UNKNOWN


def _stored_legs(pick, legs):
    """Leg rows that were stored. A text blob with no grades is not marked hit, miss, or open."""
    if legs:
        return list(legs)
    raw = _get(pick, "legs")
    if isinstance(raw, (list, tuple)) and raw:
        return list(raw)
    text = _get(pick, "leg_text")
    if not isinstance(text, str):
        text = raw if isinstance(raw, str) else ""
    return [{"text": line.strip(), "status": None} for line in str(text).splitlines() if line.strip()]


def _sort_stamp(pick) -> float:
    for key in ("settled_at", "settled", "created_at", "opened"):
        when = parse_when(_get(pick, key))
        if when is not None:
            return when.timestamp()
    return 0.0


def build_slip(pick, legs=None) -> dict:
    """One slip, with display text already decided. Missing numbers stay unknown."""
    stored = _stored_legs(pick, legs)
    graded = []
    for index, leg in enumerate(stored, start=1):
        raw_n = _get(leg, "idx", _get(leg, "n"))
        try:
            number = int(raw_n)
        except (TypeError, ValueError):
            number = index
        graded.append({
            "n": number,
            "text": _shown(_get(leg, "text")),
            "grade": leg_grade(_get(leg, "status")),
        })
    graded.sort(key=lambda leg: leg["n"])
    stake = _num(_get(pick, "cost"))
    if stake is None:
        stake = _num(_get(pick, "stake"))
    returned = _num(_get(pick, "returned"))
    payout = _num(_get(pick, "payout"))
    net = None if stake is None or returned is None else returned - stake
    result = pick_result(_get(pick, "status"))
    opened = _get(pick, "created_at")
    if not _text(opened):
        opened = _get(pick, "opened")
    settled = _get(pick, "settled_at")
    if not _text(settled):
        settled = _get(pick, "settled")
    counts: dict[str, int] = {}
    for leg in graded:
        counts[leg["grade"]] = counts.get(leg["grade"], 0) + 1
    order = ("hit", "miss", "push", "open", "void", UNKNOWN)
    summary = ", ".join(f"{counts[word]} {word}" for word in order if counts.get(word)) or UNKNOWN
    raw_id = _get(pick, "id")
    try:
        slip_id = int(raw_id) if raw_id is not None and str(raw_id).strip() != "" else None
    except (TypeError, ValueError):
        slip_id = None
    return {
        "id": slip_id,
        "result": result,
        "result_label": _RESULT_LABEL.get(result, UNKNOWN),
        "who": _shown(_get(pick, "bettor_name") or _get(pick, "who")),
        "platform": _shown(_get(pick, "platform")),
        "description": _shown(_get(pick, "description")),
        "legs": graded,
        "legs_summary": summary,
        "stake": plain_money(stake),
        "payout": plain_money(payout),
        "returned": plain_money(returned),
        "net": signed_money(net),
        "opened": clock_text(opened),
        "settled": clock_text(settled),
        "duration": duration_text(opened, settled),
        "slippage": slippage_text(pick, stored),
        "_sort": _sort_stamp(pick),
    }


def normalize_filter(value) -> str:
    text = _text(value).lower()
    return text if text in FILTERS else "all"


def history_page(picks, filt="all", page=1, page_size=SLIP_PAGE) -> dict:
    """Filter and page slips that were already loaded. Does not read the database."""
    filt = normalize_filter(filt)
    try:
        size = max(1, int(page_size))
    except (TypeError, ValueError):
        size = SLIP_PAGE
    built = [build_slip(pick) for pick in (picks or [])]
    if filt == "hits":
        built = [row for row in built if row["result"] == "hit"]
    elif filt == "misses":
        built = [row for row in built if row["result"] == "miss"]
    elif filt == "open":
        built = [row for row in built if row["result"] == "open"]
    built.sort(key=lambda row: (row["_sort"], row["id"] or 0), reverse=True)
    pages = max(1, (len(built) + size - 1) // size)
    try:
        current = int(page)
    except (TypeError, ValueError):
        current = 1
    if current < 1:
        current = 1
    if current > pages:
        current = pages
    start = (current - 1) * size
    return {
        "filter": filt,
        "page": current,
        "pages": pages,
        "total": len(built),
        "rows": built[start:start + size],
        "all_rows": built,
        "empty": _EMPTY[filt],
    }


def _esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _href(filt: str, page: int, slip_id=None) -> str:
    query = f"filter={filt}&page={page}"
    if slip_id is not None:
        query += f"&slip={int(slip_id)}"
    return "?" + _esc(query)


def _cell(value: str, kind: str = "") -> str:
    classes = []
    if value == UNKNOWN:
        classes.append("unk")
    if kind:
        classes.append(kind)
    attr = f' class="{" ".join(classes)}"' if classes else ""
    return f"<td{attr}>{_esc(value)}</td>"


def _detail(row: dict) -> str:
    if row["legs"]:
        items = "".join(
            f"<li><span class=\"grade\">{_esc(leg['grade'])}</span> {_esc(leg['text'])}</li>"
            for leg in row["legs"]
        )
        legs = f"<ol class=\"legs\">{items}</ol>"
    else:
        legs = f"<p class=\"unk\">{_esc('No legs were stored.')}</p>"
    fields = (
        ("Result", row["result_label"]),
        ("Platform", row["platform"]),
        ("Description", row["description"]),
        ("Who", row["who"]),
        ("Stake", row["stake"]),
        ("Payout", row["payout"]),
        ("Returned", row["returned"]),
        ("Net", row["net"]),
        ("Opened", row["opened"]),
        ("Settled", row["settled"]),
        ("Duration", row["duration"]),
        ("Slippage", row["slippage"]),
    )
    body = "".join(
        f"<div><dt>{_esc(label)}</dt><dd class=\"{'unk' if value == UNKNOWN else ''}\">{_esc(value)}</dd></div>"
        for label, value in fields
    )
    title = f"Slip {row['id']}" if row["id"] is not None else "Slip"
    return (
        f"<section class=\"detail\" id=\"slip\">"
        f"<h2>{_esc(title)}</h2>"
        f"<dl>{body}</dl>"
        f"<h3>Legs</h3>{legs}"
        f"</section>"
    )


def render_slip_history_page(picks, *, filt="all", page=1, slip_id=None, page_size=SLIP_PAGE) -> str:
    """The history table and, when a slip is selected, its detail."""
    view = history_page(picks, filt, page, page_size)
    filt = view["filter"]
    current = view["page"]
    filters = "".join(
        f"<a class=\"{'on' if key == filt else ''}\" href=\"{_href(key, 1)}\">{_esc(label)}</a>"
        for key, label in (("all", "All"), ("hits", "Hits"), ("misses", "Misses"), ("open", "Open"))
    )
    if view["page"] <= 1:
        prev = "<span class=\"off\">Previous</span>"
    else:
        prev = f"<a href=\"{_href(filt, current - 1, slip_id)}\">Previous</a>"
    if view["page"] >= view["pages"]:
        nxt = "<span class=\"off\">Next</span>"
    else:
        nxt = f"<a href=\"{_href(filt, current + 1, slip_id)}\">Next</a>"
    header = (
        "<tr><th scope=\"col\">#</th><th scope=\"col\">Result</th><th scope=\"col\">Who</th>"
        "<th scope=\"col\">Platform</th><th scope=\"col\">Description</th><th scope=\"col\">Legs</th>"
        "<th scope=\"col\">Stake</th><th scope=\"col\">Payout</th><th scope=\"col\">Returned</th>"
        "<th scope=\"col\">Net</th><th scope=\"col\">Opened</th><th scope=\"col\">Settled</th>"
        "<th scope=\"col\">Duration</th><th scope=\"col\">Slippage</th></tr>"
    )
    if view["rows"]:
        body_rows = []
        for row in view["rows"]:
            selected = slip_id is not None and row["id"] == slip_id
            link = _href(filt, current, row["id"]) if row["id"] is not None else ""
            ident = _esc(row["id"]) if row["id"] is not None else _esc(UNKNOWN)
            if link:
                ident = f"<a href=\"{link}\">{ident}</a>"
            body_rows.append(
                f"<tr class=\"{'selected' if selected else ''}\" data-slip=\"{_esc(row['id'] if row['id'] is not None else '')}\">"
                f"<td>{ident}</td>"
                f"<td class=\"result { _esc(row['result']) }\">{_esc(row['result_label'])}</td>"
                + _cell(row["who"])
                + _cell(row["platform"])
                + _cell(row["description"])
                + _cell(row["legs_summary"])
                + _cell(row["stake"])
                + _cell(row["payout"])
                + _cell(row["returned"])
                + _cell(row["net"])
                + _cell(row["opened"])
                + _cell(row["settled"])
                + _cell(row["duration"])
                + _cell(row["slippage"])
                + "</tr>"
            )
        body = "".join(body_rows)
        empty = ""
    else:
        body = ""
        empty = f"<p class=\"empty\" role=\"status\">{_esc(view['empty'])}</p>"
    chosen = None
    if slip_id is not None:
        for row in view["all_rows"]:
            if row["id"] == slip_id:
                chosen = row
                break
        if chosen is None:
            detail = (
                "<section class=\"detail\" id=\"slip\"><h2>Slip</h2>"
                f"<p class=\"empty\">{_esc('That slip is not in this list.')}</p></section>"
            )
        else:
            detail = _detail(chosen)
    elif view["rows"]:
        detail = (
            "<section class=\"detail\" id=\"slip\"><h2>Slip</h2>"
            "<p class=\"muted\">Select a slip for the platform, the legs, and the full record.</p></section>"
        )
    else:
        detail = ""
    count = f"{view['total']} slip" if view["total"] == 1 else f"{view['total']} slips"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Past slips</title>
<style>
:root {{color-scheme:dark; --bg:#0d0a14; --card:#17121f; --line:#2a2238; --text:#f4f1fb; --muted:#a59cbc; --brand:#a27bff; --up:#34d399; --down:#fb7185; --open:#f0b429}}
* {{box-sizing:border-box}}
body {{margin:0; background:var(--bg); color:var(--text); font:15px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
header, main {{max-width:1180px; margin:auto; padding:20px}}
header {{display:flex; justify-content:space-between; align-items:baseline; gap:12px; flex-wrap:wrap}}
h1 {{margin:0; font-size:26px}} h2 {{margin:0 0 12px; font-size:18px}} h3 {{margin:16px 0 8px; font-size:13px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted)}}
a {{color:var(--brand); font-weight:650; text-decoration:none}} a:hover {{text-decoration:underline}}
.back {{min-height:44px; display:inline-flex; align-items:center}}
.filters, .pager {{display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin:0 0 14px}}
.filters a, .pager a, .pager .off {{min-height:44px; display:inline-flex; align-items:center; padding:0 14px; border-radius:999px; border:1px solid var(--line); background:#1f1829; color:var(--text)}}
.filters a.on {{background:#7B3FE4; border-color:#7B3FE4; color:#fff}}
.pager .off {{color:var(--muted)}}
.note, .muted {{color:var(--muted)}}
.wrap {{overflow-x:auto; border:1px solid var(--line); border-radius:16px; background:var(--card)}}
table {{width:100%; border-collapse:collapse; min-width:980px}}
th, td {{padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top}}
th {{color:var(--muted); font-weight:650; font-size:12px; letter-spacing:.04em; text-transform:uppercase; position:sticky; top:0; background:#1c1626}}
tr.selected td {{background:#2a2040}}
td.num, td {{font-variant-numeric:tabular-nums}}
.unk {{color:var(--muted); font-style:italic; font-weight:500}}
.result.hit {{color:var(--up); font-weight:750}} .result.miss {{color:var(--down); font-weight:750}} .result.open {{color:var(--open); font-weight:750}}
.empty {{padding:28px 8px; text-align:center; color:var(--text); font-size:16px}}
.detail {{margin-top:18px; background:var(--card); border:1px solid var(--line); border-radius:16px; padding:16px 18px}}
dl {{display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px 16px; margin:0}}
dt {{color:var(--muted); font-size:12px; letter-spacing:.06em; text-transform:uppercase}}
dd {{margin:2px 0 0; overflow-wrap:anywhere}}
.legs {{margin:0; padding-left:1.2em}} .legs li {{margin:6px 0}}
.grade {{display:inline-block; min-width:3.2em; font-weight:750; text-transform:lowercase}}
</style>
</head>
<body>
<header>
  <div>
    <h1>Past slips</h1>
    <p class="note">Times are America/Chicago, from the logged time to the settled time. A number that was not stored is unknown.</p>
  </div>
  <a class="back" href="/">Dashboard</a>
</header>
<main>
  <nav class="filters" aria-label="Filter slips">{filters}</nav>
  <p class="muted">{_esc(count)} · page {current} of {view['pages']}</p>
  {empty}
  <div class="wrap">
    <table>
      <caption class="muted">Past slips</caption>
      <thead>{header}</thead>
      <tbody>{body}</tbody>
    </table>
  </div>
  <nav class="pager" aria-label="Pages">{prev}<span>Page {current} of {view['pages']}</span>{nxt}</nav>
  {detail}
</main>
</body>
</html>
"""
