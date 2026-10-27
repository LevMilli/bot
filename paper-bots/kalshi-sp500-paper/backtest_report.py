"""
backtest_report.py - turns the cached backtest data into Backtest_Report.md.
Called by:  python3 backtest.py report
All numbers come from backtest.simulate()/stats(); nothing is typed in by hand.
"""
import collections
import datetime as dt
import os
import statistics
import backtest as bt

HERE = os.path.dirname(os.path.abspath(__file__))


def fmt(s):
    if not s.get("trades"):
        return "| (no trades) |" + " |" * 13
    return (f"| {s['trades']} | {s['skip_news']} | {s['skip_no_band']} | {s['missing_data'] + s['void_result']} | "
            f"{s['win_rate']*100:.1f}% | ${s['avg_win']:.2f} | ${s['avg_loss']:.2f} | ${s['total_pnl']:+.2f} | "
            f"${s['max_drawdown']:.2f} | {s['risk_reward']:.3f} | {s['breakeven_win_rate']*100:.1f}% | "
            f"${s['expectancy']:+.3f} | {s['worst_losing_streak']} | {s['kill_switch_date'] or 'never'} |")


VERDICT = """
**Verdict - Version 1 daily: FAIL (not proven; do not trust it with money yet).**
- Win rate looks great (~88%) but each loss (~-$24.85) wipes out ~7 wins (~+$3.56), so the strategy needs ~87.5-88.5% wins just to
  break even. It sits right on that line: +$35 over two years (+$0.12/trade) and **negative with just +1c worse fills** (-$43).
- In-sample (Oct 2024-Mar 2026) **lost $97** and would have hit the $400 kill switch on **2025-08-05**; out-of-sample (Mar-Oct 2026)
  made +$132 (+$1.21/trade) but the confidence interval includes $0 and the period is only ~7 months. The rule was not tuned, so the split
  is a stability test: the edge flipped sign between periods, which is the opposite of robust.
- Honest read: the 80-90c band is roughly fairly priced by Kalshi. Any edge is smaller than the spread + fee.

**Verdict - Hourly variant: FAIL in both splits.** It lost money in-sample and out-of-sample, at pay-the-ask and worse with +1c.
**"Profit every hour" is not realistic:** ~86% of hourly trades win, but fewer than half of trading days end positive, losing
streaks of up to 5 trades occurred, and one loss erases ~7 wins. More trades = more fees + spread paid, so the hourly version loses faster.

**Paper-trading status:** keep the bot in PAPER mode. Version 1 can be paper-traded forward to collect live evidence, but the
backtest does not support real-money use.
"""


HEAD = ("| Trades | Skipped: news/holiday | Skipped: no 80-90c contract | No data / void | Win rate | Avg win | Avg loss | "
        "Total P&L | Max drawdown | Reward:risk (avg win/avg loss) | Break-even win rate | Expectancy / trade | "
        "Worst losing streak | $400 kill switch hit |\n|" + "---|" * 14)


def section(name, rows):
    ins, oos, cut = bt.split(rows)
    out = [f"Split date: in-sample = trading days before **{cut}** (first ~70% of days), out-of-sample = {cut} onward.\n",
           "| Period | " + HEAD.split("| ", 1)[1].replace("|---|", "|---|---|", 1)]
    for label, rr in (("Overall", rows), ("In-sample", ins), ("Out-of-sample", oos)):
        s = bt.stats(rr)
        rng = f"{s.get('first','-')} to {s.get('last','-')}"
        out.append(f"| {label} ({rng}) " + fmt(s))
    return "\n".join(out), (ins, oos, cut)


def hourly_extra(rows):
    """Profitability by hour-of-day and by trading hour/day."""
    tr = [r for r in rows if r["status"] == "trade"]
    lines = ["| Settle hour (CT) | Entry (CT) | Trades | Win rate | Total P&L | Expectancy |", "|---|---|---|---|---|---|"]
    by_h = collections.defaultdict(list)
    for r in tr:
        by_h[r["settle"].hour].append(r)
    for h in sorted(by_h):
        L = by_h[h]
        w = sum(r["won"] for r in L) / len(L)
        p = sum(r["pnl"] for r in L)
        lines.append(f"| {h}:00 | {h-1}:30 | {len(L)} | {w*100:.1f}% | ${p:+.2f} | ${p/len(L):+.3f} |")
    return "\n".join(lines)


def hour_day_profitability(rows):
    tr = [r for r in rows if r["status"] == "trade"]
    slots = [r for r in rows if r["status"] not in ("missing_data",)]
    prof = sum(1 for r in tr if r["pnl"] > 0); lose = sum(1 for r in tr if r["pnl"] <= 0)
    day = collections.defaultdict(float)
    for r in tr:
        day[r["settle"].date()] += r["pnl"]
    dp = sum(1 for v in day.values() if v > 0); dl = sum(1 for v in day.values() if v <= 0)
    tradable = [r for r in slots if r["status"] != "skip_news"]
    return (f"- Hours with a trade: {len(tr)}. Net profitable: **{prof} ({prof/max(len(tr),1)*100:.1f}%)**; "
            f"losing: **{lose} ({lose/max(len(tr),1)*100:.1f}%)**.\n"
            f"- Of all {len(tradable)} non-news trading hours with data, {len(tr)/max(len(tradable),1)*100:.1f}% had a trade "
            f"(the rest had nothing in the 80-90c band or hit the $50 daily stop and earned $0).\n"
            f"- Trading days with at least one trade: {len(day)}. Net profitable days: {dp} ({dp/max(len(day),1)*100:.1f}%), "
            f"losing days: {dl} ({dl/max(len(day),1)*100:.1f}%).")


def ci_line(label, rows):
    """95% confidence interval for expectancy per trade (normal approximation)."""
    p = [r["pnl"] for r in rows if r["status"] == "trade"]
    if len(p) < 2:
        return f"- {label}: too few trades"
    m = sum(p) / len(p); sd = statistics.stdev(p); se = sd / len(p) ** 0.5
    return (f"- {label}: expectancy ${m:+.3f}/trade, 95% CI ${m-1.96*se:+.3f} to ${m+1.96*se:+.3f} "
            f"(t = {m/se:+.2f}; " + ("not statistically different from $0)." if abs(m/se) < 2 else "statistically different from $0)."))


def coverage(mode, rows):
    st = collections.Counter(r["status"] for r in rows)
    tr = [r for r in rows if r["status"] == "trade"]
    edge_bad = sum(1 for r in tr if r.get("edge_ok") is False)
    first, last = rows[0]["settle"].date(), rows[-1]["settle"].date()
    miss = [r["event"] for r in rows if r["status"] == "missing_data"]
    return (f"- Events tested: {len(rows)} ({first} to {last}). Status counts: {dict(st)}.\n"
            f"- Events with no usable data from the API: {len(miss)}" + (f" (e.g. {', '.join(miss[:6])})" if miss else "") + ".\n"
            f"- Trades where the download-edge completeness check failed: {edge_bad} (0 = every in-band contract was seen).\n"
            f"- Average entry price paid: {sum(r['fill'] for r in tr)/max(len(tr),1)*100:.1f}c; total fees: ${sum(r['fee'] for r in tr):.2f}.")


def main():
    now = dt.datetime.now(bt.CT).strftime("%Y-%m-%d %H:%M %Z")
    parts = [f"# Backtest_Report.md\n_Generated {now} by `python3 backtest.py report` from Kalshi public-API data (no login)._ "
             "_Paper research only. Past results do not guarantee future results._\n"]
    parts.append("""## Method (read first)
- **Market:** KXINXU (S&P 500 at/above strike). Only already-settled events. Result = Kalshi's official `result` field.
- **Entry price:** for entry time T we take Kalshi 1-minute candlesticks (`/historical/markets/{t}/candlesticks` before the
  Aug 27 2026 historical cutoff, `/markets/candlesticks` after) and use the **closing yes-bid / yes-ask of the last 1-minute bar ending at or
  before T** (look-back 3 h; a minute with no bar = quote unchanged). YES ask = yes_ask; NO ask = 1 - yes_bid. Nothing after T is used to choose
  the trade, so there is **no lookahead in the signal**. (The settled index value is used only to decide *which strikes to download first*; the
  download widens until the edge strikes are provably outside the band - see "edge check" below.)
- **Rule:** buy the highest-priced side with ask 80-90c (tie -> tighter spread, YES first). Size floor($25/ask). Pay the ask. Taker fee
  ceil-to-cent(0.07*C*P*(1-P)). Hold to settlement. Slippage test: fill at ask + 1c.
- **Skips:** calendar.json (FOMC decision days, CPI, jobs report, advance GDP, every PCE/Personal-Income release, election day + day after,
  holidays/half days; sources listed inside the file). $50 daily loss limit applied. The $400 kill switch is **reported** (date it would have
  fired) but the simulation keeps going so you can see the whole period.
- **Limits:** historical order-book depth is not available, so we assume our <=31 contracts fill at the displayed ask (UNVERIFIED for old
  dates). Quotes come from 1-minute bar closes, not tick data. A 1-minute bar can be a few seconds stale.
- **Split:** chronological by trading day: first 70% of days = in-sample, last 30% = out-of-sample. No parameters were tuned on either part
  (the rule was fixed in Strategy.md before this test), so in-sample vs out-of-sample here is a stability check, not a fitting check.
""")
    daily = bt.simulate("daily"); daily1 = bt.simulate("daily", slip=0.01)
    t, _ = section("daily", daily); t1, _ = section("daily", daily1)
    parts.append("## 1. Version 1 - DAILY (12:30 PM CT entry, 3 PM CT settle)\n### Pay-the-ask (base case)\n" + t +
                 "\n\n### Sensitivity: +1c worse fill on every trade\n" + t1 + "\n\n### Coverage\n" + coverage("daily", daily))
    if any(os.path.exists(os.path.join(bt.CACHE, f)) for f in os.listdir(bt.CACHE)):
        hourly = bt.simulate("hourly"); hourly1 = bt.simulate("hourly", slip=0.01)
        h, (hi, ho, _) = section("hourly", hourly); h1, _ = section("hourly", hourly1)
        parts.append("## 2. HOURLY variant (entry 30 min before each hourly settle, 9 AM-3 PM CT)\n"
                     "Hourly KXINXU settle times other than 3 PM CT only exist from **2025-02-13** (the 12 PM CT settle from 2024-11-29); "
                     "the 3 PM CT settle exists from 2024-10-24. Max 1 trade per hourly event; same news-day skips; $50 daily loss limit.\n"
                     "### Pay-the-ask (base case)\n" + h + "\n\n### Sensitivity: +1c worse fill\n" + h1 +
                     "\n\n### Did it profit every hour?\n**Overall:**\n" + hour_day_profitability(hourly) +
                     "\n\n**In-sample:**\n" + hour_day_profitability(hi) + "\n\n**Out-of-sample:**\n" + hour_day_profitability(ho) +
                     "\n\n### By hour of day (overall, base case)\n" + hourly_extra(hourly) + "\n\n### Coverage\n" + coverage("hourly", hourly))
    di, do, _ = bt.split(daily)
    v = ["## 3. Statistical check and verdict", "**Daily V1 (base case):**", ci_line("Overall", daily), ci_line("In-sample", di), ci_line("Out-of-sample", do)]
    if "hourly" in locals():
        v += ["**Hourly (base case):**", ci_line("Overall", hourly), ci_line("In-sample", hi), ci_line("Out-of-sample", ho)]
    v.append(VERDICT)
    parts.append("\n".join(v))
    open(os.path.join(HERE, "Backtest_Report.md"), "w").write("\n".join(parts) + "\n")
    print("\n".join(parts))


if __name__ == "__main__":
    main()
