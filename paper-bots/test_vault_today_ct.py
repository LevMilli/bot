"""The vault's "today" runs midnight to midnight Central time, not UTC."""
import datetime as dt

import pimp_desk as d

DAY = dt.date(2026, 11, 13)


def test_day_is_central_time():
    # 8 PM CT Nov 12 is 02:00 UTC Nov 13: yesterday, not today.
    assert not d._day_hit("2026-11-13T02:00:00+00:00", DAY)
    assert not d._day_hit("2026-11-13 02:00:00 UTC", DAY)
    assert not d._day_hit("2026-11-13T02:00:00Z", DAY)
    assert not d._day_hit("2026-11-13T02:00:00", DAY)          # naive = server UTC
    # 3:30 AM CT Nov 13 is today.
    assert d._day_hit("2026-11-13T09:30:29+00:00", DAY)
    # 8 PM CT Nov 13 is 02:00 UTC Nov 14: still today.
    assert d._day_hit("2026-11-14T02:00:00+00:00", DAY)
    assert d._day_hit(str(dt.datetime(2026, 11, 14, 2, tzinfo=dt.timezone.utc).timestamp()), DAY)
    # A bare date is a day.
    assert d._day_hit("2026-11-13", DAY) and not d._day_hit("2026-11-12", DAY)
    assert not d._day_hit("", DAY) and not d._day_hit(None, DAY)


def test_tower_today_counts_central_day_only():
    state = {"closed": [
        {"ticker": "A", "side": "yes", "pnl": 50.0, "closed": "2026-11-13T03:00:00+00:00"},   # 9 PM CT Nov 12
        {"ticker": "B", "side": "no", "pnl": -10.0, "closed": "2026-11-13T07:00:00+00:00"},   # 1 AM CT Nov 13
        {"ticker": "C", "side": "no", "pnl": 25.0, "closed": "2026-11-14T01:00:00+00:00"},    # 7 PM CT Nov 13
    ]}
    assert d._sports_positions(state, DAY)[3] == 15.0
