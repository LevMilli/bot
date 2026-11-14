"""Speed measurement: check times, targets, gateway waits, snapshot compression, plaza bloom. Offline."""
import json
import os
import re

import desk_speed
import kalshi_gateway

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def test_targets_match_the_plan():
    assert desk_speed.target_for("more-15m") == 20.0
    assert desk_speed.target_for("btc15m") == 20.0 and desk_speed.target_for("commodity-15m") == 20.0
    assert desk_speed.target_for("sports-gap") == 45.0
    assert desk_speed.target_for("anything-new", "sports") == 45.0
    assert desk_speed.target_for("weather-high") == 60.0


def test_record_keeps_last_runs_and_summary_sorts_slowest_first(tmp_path):
    for sec in (10, 12, 30, 31, 32):
        desk_speed.record(str(tmp_path), "more-15m", "run", sec, True, "t")
    for sec in (20, 22):
        desk_speed.record(str(tmp_path), "sports-gap", "run", sec, True, "t")
    desk_speed.record(str(tmp_path), "kalshi-sp", "settle", 99, True, "t")   # settles are not checks
    for _ in range(5):
        desk_speed.record(str(tmp_path), "weather-high", "run", 1, True, "t", keep=3)
    data = json.loads((tmp_path / desk_speed.FILE).read_text())
    assert len(data["weather-high"]) == 3
    s = desk_speed.summary(str(tmp_path), {"more-15m": "More 15m"},
                           waits={"more-15m": {"avg": 0.25, "max": 1.0}})
    assert [r["bot"] for r in s["rows"]] == ["more-15m", "sports-gap", "weather-high"]
    top = s["rows"][0]
    assert top["median_sec"] == 30 and top["over"] and s["over"] == ["more-15m"] and s["slowest"] == "more-15m"
    assert "target under 20s" in top["text"] and "Kalshi wait 0.25s a read" in top["text"]
    assert top["name"] == "More 15m"
    assert desk_speed.report_lines(s)[0].startswith("More 15m: median 30s")
    assert desk_speed.report_lines({"rows": []}) == ["No timed checks yet."]


def test_record_never_raises(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    desk_speed.record(str(blocker), "x", "run", 1, True)    # folder is a file: quietly skipped
    desk_speed.record(str(tmp_path), "x", "run", "nan?", True)


def test_timer_uses_the_clock():
    ticks = iter([5.0, 7.5])
    with desk_speed.Timer(clock=lambda: next(ticks)) as t:
        pass
    assert t.seconds == 2.5


def test_gateway_wait_counter_never_changes_a_turn(tmp_path, monkeypatch):
    monkeypatch.setenv("KALSHI_GATEWAY_DIR", str(tmp_path))
    monkeypatch.setenv("KALSHI_READS_PER_SEC", "2")
    clock = iter([100.0, 100.0, 100.0])
    waits = [kalshi_gateway.reserve("u", clock=lambda: next(clock)) for _ in range(3)]
    assert waits == [0.0, 0.5, 1.0]                     # the shared pace, as before
    who = os.path.basename(os.getcwd())
    row = kalshi_gateway.waits()[who]
    assert row["n"] == 3 and row["sec"] == 1.5 and row["max"] == 1.0 and row["avg"] == 0.5


def test_desk_times_each_check_and_shows_speed(monkeypatch, tmp_path):
    import pimp_desk

    src = open(pimp_desk.__file__, encoding="utf-8").read()
    body = src[src.index("def run_bot("):src.index("def speed_view(")]
    assert "started = time.monotonic()" in body and "desk_speed.record(" in body
    assert "run_speed.json" in pimp_desk.SETTLEMENT_FILES
    desk_speed.record(str(tmp_path), "more-15m", "run", 25, True, "t")
    view = pimp_desk.speed_view(str(tmp_path))
    assert view["rows"][0]["name"] == "More 15m" and view["rows"][0]["over"]


def test_snapshot_response_is_compressed_and_dashboard_shows_speed():
    src = open(os.path.join(REPO, "bot.py"), encoding="utf-8").read()
    start = src.index("async def dash_api_pimp(request)")
    body = src[start:src.index("async def dash_api_pimp_post")]
    assert "enable_compression()" in body and "Accept-Encoding" in body
    assert "Speed against targets" in src and "d.speed" in src


def test_plaza_keeps_bloom_off():
    """Step 411: the city plaza never loads the bloom pass (offices may)."""
    city = open(os.path.join(REPO, "trading-city", "src", "scene", "CityScene.tsx"), encoding="utf-8").read()
    assert not re.search(r"\bBloom\b|NeonBloom|EffectComposer", city)
