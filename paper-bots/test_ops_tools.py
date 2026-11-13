"""Deploy check, smoke test, change log, incident stats, runbook. Offline."""
import datetime as dt
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))

import changelog  # noqa: E402
import deploy_check  # noqa: E402
import incident_stats  # noqa: E402


def _healthy(**over):
    body = {"ok": True, "paper_only": True, "timer_alive": True, "last_pass_age_s": 40,
            "build": {"sha": "2256d39abcde"}}
    body.update(over)
    return lambda url: body


def test_smoke_passes_on_a_healthy_desk(capsys):
    assert deploy_check.smoke("http://desk", "http://bot/health", "2256d39", get_json=_healthy(),
                              get_status=lambda url: 200) == 0
    assert "Smoke test passed." in capsys.readouterr().out


def test_smoke_fails_on_old_pass_wrong_build_or_blank_city(capsys):
    assert deploy_check.smoke("http://desk", get_json=_healthy(last_pass_age_s=900)) == 1
    assert deploy_check.smoke("http://desk", sha="ffffff", get_json=_healthy()) == 1
    assert deploy_check.smoke("http://desk", "http://bot", get_json=_healthy(), get_status=lambda url: 502) == 1
    assert deploy_check.smoke("http://desk", get_json=_healthy(paper_only=False)) == 1
    out = capsys.readouterr().out
    assert "FAIL  last timer pass is recent (900s)" in out


def test_smoke_fails_when_desk_is_down():
    def boom(url):
        raise OSError("refused")
    assert deploy_check.smoke("http://desk", get_json=boom) == 1


def test_floor_check_catches_a_lower_floor(capsys):
    rep = deploy_check.Report()
    floors = dict(deploy_check.LOCKED_FLOORS, kalshi_btc15m=0.04)
    deploy_check.check_floors(rep, types.SimpleNamespace(DEFAULTS={"venue_min_edge": floors}))
    assert rep.failed == 1 and "kalshi_btc15m 0.04 < 0.05" in capsys.readouterr().out


def test_real_desk_floors_and_money_pass():
    import pimp_desk
    rep = deploy_check.Report()
    deploy_check.check_floors(rep, pimp_desk)
    deploy_check.check_money_off(rep, pimp_desk)
    deploy_check.check_towers(rep, pimp_desk)
    assert rep.failed == 0


def test_locked_floor_list_matches_the_brief():
    assert deploy_check.LOCKED_FLOORS == {
        "kalshi_sports": 0.06, "kalshi_btc15m": 0.05, "kalshi_commodity15m": 0.05, "kalshi_inx": 0.02,
        "solana_dex": 0.02, "coinbase_spot": 0.05, "binance_btc_carry": 0.02, "kalshi_econ": 0.05,
        "equity_qqq": 0.02}


def test_changelog_parses_squash_titles_and_marks_rules():
    stamp = int(dt.datetime(2026, 11, 13, 20, 0, tzinfo=dt.timezone.utc).timestamp())
    rows = changelog.parse([
        f"{stamp}\tLog desk open count for the evening report (#708)",
        f"{stamp}\tLower the sports cap for shadow twin (#709)",
        f"{stamp}\tA direct commit with no PR",
    ])
    assert [r["pr"] for r in rows] == [708, 709]
    assert rows[0]["date"] == "2026-11-13" and not rows[0]["rule"] and rows[1]["rule"]
    text = changelog.markdown(rows)
    assert "## 2026-11-13" in text and "- #709 (rule): Lower the sports cap for shadow twin" in text
    assert changelog.since(rows, 7, dt.date(2026, 11, 30)) == []


def test_incident_stats(tmp_path):
    (tmp_path / "TEMPLATE.md").write_text("- Started: 2026-01-01 09:00 CT\n")
    (tmp_path / "2026-11-01-a.md").write_text(
        "- Started: 2026-11-01 09:00 CT\n- Noticed: 2026-11-01 09:10 CT\n- Fixed: 2026-11-01 10:00 CT\n")
    (tmp_path / "2026-11-02-b.md").write_text(
        "- Started: 2026-11-02 09:00 CT\n- Noticed: 2026-11-02 09:30 CT\n- Fixed: 2026-11-02 09:40 CT\n")
    (tmp_path / "2026-11-03-c.md").write_text("- Started: 2026-11-03 09:00 CT\n")
    s = incident_stats.summary(str(tmp_path))
    assert s == {"incidents": 2, "mean_minutes_to_notice": 20.0, "mean_minutes_to_fix": 50.0,
                 "missing_times": ["2026-11-03-c.md"]}


def test_runbook_covers_the_on_call_pages():
    with open(os.path.join(HERE, "docs", "RUNBOOK.md"), encoding="utf-8") as handle:
        text = handle.read()
    for head in ("## Is the desk healthy?", "## Deploy checklist", "## Roll back a bad deploy",
                 "## Backups and restore", "## On call: a tower stopped trading",
                 "## On call: the numbers look wrong", "## On call: the city is blank", "## Incidents"):
        assert head in text
    assert "Last reviewed:" in text
    for word in ("scrape", "crawl", "!"):
        assert word not in text.lower()
    assert os.path.isfile(os.path.join(HERE, "docs", "incidents", "TEMPLATE.md"))
    assert os.path.isfile(os.path.join(HERE, "docs", "DATA_SOURCES.md"))
