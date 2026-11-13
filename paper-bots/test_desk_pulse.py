"""The Discord bot's outside watch on the trading service: missed passes, down, build skew."""
import datetime as dt

import desk_pulse as pulse

NOW = dt.datetime(2026, 11, 13, 18, 0, tzinfo=dt.timezone.utc)


def _fetch(body):
    return lambda url: body


def test_missed_two_passes_posts_once_then_back():
    state = {}
    assert pulse.check("http://x", state, now=NOW, fetch=_fetch({"ok": True, "last_pass_age_s": 70})) == []
    assert pulse.check("http://x", state, now=NOW, fetch=_fetch({"ok": True, "last_pass_age_s": 150})) == []
    notes = pulse.check("http://x", state, now=NOW, fetch=_fetch({"ok": True, "last_pass_age_s": 190}))
    assert notes == ["Desk watch: the desk timer has missed at least 2 passes. The last pass finished 3m 10s ago."]
    assert pulse.check("http://x", state, now=NOW, fetch=_fetch({"ok": True, "last_pass_age_s": 400})) == []
    assert pulse.check("http://x", state, now=NOW, fetch=_fetch({"ok": True, "last_pass_age_s": 20})) == [
        "Desk watch: the desk timer is running again."]


def test_service_down_needs_two_misses():
    state = {}

    def boom(url):
        raise OSError("refused")
    assert pulse.check("http://x", state, now=NOW, fetch=boom) == []
    notes = pulse.check("http://x", state, now=NOW, fetch=boom)
    assert len(notes) == 1 and "not answering" in notes[0]
    assert pulse.snapshot()["offline"] is True
    assert pulse.check("http://x", state, now=NOW, fetch=boom) == []
    assert pulse.check("http://x", state, now=NOW, fetch=_fetch({"ok": True, "last_pass_age_s": 10})) == [
        "Desk watch: the trading service is answering again."]
    assert pulse.snapshot()["offline"] is False


def test_build_skew_after_ten_minutes():
    state = {}
    mine = {"sha": "aaa"}
    body = {"ok": True, "last_pass_age_s": 10, "build": {"sha": "bbb"}}
    assert pulse.check("http://x", state, mine, now=NOW, fetch=_fetch(body)) == []
    assert pulse.check("http://x", state, mine, now=NOW + dt.timedelta(minutes=9), fetch=_fetch(body)) == []
    notes = pulse.check("http://x", state, mine, now=NOW + dt.timedelta(minutes=11), fetch=_fetch(body))
    assert len(notes) == 1 and "aaa" in notes[0] and "bbb" in notes[0]
    same = {"ok": True, "last_pass_age_s": 10, "build": {"sha": "aaa"}}
    assert pulse.check("http://x", state, mine, now=NOW + dt.timedelta(minutes=12), fetch=_fetch(same)) == [
        "Desk watch: both services run the same build again."]


def test_unknown_builds_never_alert():
    state = {}
    body = {"ok": True, "last_pass_age_s": 10, "build": {"sha": ""}}
    for minutes in range(0, 60, 5):
        assert pulse.check("http://x", state, {"sha": "aaa"}, now=NOW + dt.timedelta(minutes=minutes),
                           fetch=_fetch(body)) == []
