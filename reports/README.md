# Report archive

Plan step 910: keep a copy of every evening report in the repo.

- `evening/YYYY-MM-DD.md` is the report text as sent that night. Charts stay with the evening report tools.
- Pretend money only. Reports are copied as written, losses included. Nothing is edited after the fact.

The desk also logs a read-only report card every 30 minutes (`desk report {json}`), built by
`paper-bots/desk_report.py`. Run it by hand with:

    python3 paper-bots/desk_report.py            # today, short and phone friendly
    python3 paper-bots/desk_report.py --week     # last 7 days, ranked, with a cautious win-rate floor
    python3 paper-bots/desk_report.py --month    # last 30 days
    python3 paper-bots/desk_report.py --json     # the raw card

The card's `checks` list is the number check. When it is not empty, `send_ok` is false and the
report should be held for a look instead of sent.
