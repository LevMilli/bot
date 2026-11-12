"""Shared Kalshi door: pace, back-off, cache. Offline."""
import io
import urllib.error
import urllib.request

import pytest

import kalshi_gateway as gw

K = "https://api.elections.kalshi.com/trade-api/v2/markets/ABC"


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake(calls, body=b'{"ok": 1}', fail=None):
    def opener(req, timeout=15):
        url = req if isinstance(req, str) else req.full_url
        calls.append(url)
        if fail:
            raise fail
        return _Resp(body)
    return opener


def test_non_kalshi_goes_straight_out(monkeypatch):
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", _fake(calls))
    with gw.urlopen(urllib.request.Request("https://api.coinbase.com/x")) as resp:
        assert resp.read() == b'{"ok": 1}'
    assert gw.status()["sent"] == 0


def test_cache_answers_repeat_reads(monkeypatch):
    monkeypatch.setenv("KALSHI_CACHE_SECONDS", "30")
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", _fake(calls))
    assert gw.read(K) == gw.read(K) == b'{"ok": 1}'
    assert len(calls) == 1
    assert gw.status()["cache_hits"] == 1


def test_pace_spaces_turns_across_callers(monkeypatch):
    monkeypatch.setenv("KALSHI_READS_PER_SEC", "4")
    now = [1000.0]
    waits = [gw.reserve(K, clock=lambda: now[0]) for _ in range(3)]
    assert waits == pytest.approx([0.0, 0.25, 0.5])


def test_429_closes_door_for_everyone_and_reraises(monkeypatch):
    err = urllib.error.HTTPError(K, 429, "Too Many", {"Retry-After": "5"}, None)
    monkeypatch.setattr(urllib.request, "urlopen", _fake([], fail=err))
    with pytest.raises(urllib.error.HTTPError) as caught:
        gw.read(K, sleep=lambda s: None)
    assert caught.value.code == 429
    assert 4 <= gw.status()["cooldown_left_s"] <= 5
    assert gw.status()["count_429"] == 1
    # A second tower now waits the shared back-off instead of sending.
    slept = []
    monkeypatch.setattr(urllib.request, "urlopen", _fake([]))
    gw.read(K + "2", sleep=slept.append)
    assert slept and slept[0] > 3


def test_long_shutdown_is_a_429_right_away(monkeypatch):
    monkeypatch.setenv("KALSHI_GATEWAY_MAX_WAIT", "2")
    gw.note_429(retry_after=20)
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", _fake(calls))
    with pytest.raises(gw.GatewayBusy) as caught:
        gw.read(K)
    assert caught.value.code == 429 and not calls


def test_backoff_ladder_without_retry_after():
    now = [5000.0]
    clock = lambda: now[0]  # noqa: E731
    assert [gw.note_429(clock=clock) for _ in range(5)] == [2.0, 4.0, 8.0, 16.0, 30.0]


def test_post_is_never_routed(monkeypatch):
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", _fake(calls))
    req = urllib.request.Request(K, data=b"x", method="POST")
    gw.urlopen(req)
    assert calls == [K] and gw.status()["sent"] == 0
