"""Desk report card (plan steps 886-925). Read only; losses always count."""
import datetime as dt
import json
import os
import tempfile
import unittest

import desk_report
import desk_service
import pimp_desk

CT = desk_report.CT
NOW = dt.datetime(2026, 11, 13, 20, 0, tzinfo=CT)


def _iso(hour, minute=0):
    return dt.datetime(2026, 11, 13, hour, minute, tzinfo=CT).astimezone(dt.timezone.utc).isoformat()


def _view(bot, today=0.0, shadow=False, **extra):
    v = {"id": bot, "name": bot, "present": True, "status": "running", "today": today,
         "open_count": 0, "open_risk": 0.0, "shadow_only": shadow}
    v.update(extra)
    return v


CFG = {"max_open_positions": 12, "max_open_risk": 100.0, "daily_loss_stop": 150.0}


class FeeTests(unittest.TestCase):
    def test_fee_once_vs_old_way(self):
        row = {"contracts": 40, "ask": 0.5, "order_fee": 0.7, "exit": "settled"}
        f = desk_report.trade_fees(row)
        self.assertTrue(f["per_order"])
        self.assertEqual(f["charged"], 0.70)
        self.assertEqual(f["old_way"], 0.80)  # 40 x 2 cents

    def test_early_sale_counts_the_exit_fee_too(self):
        row = {"contracts": 10, "ask": 0.3, "order_fee": 0.15, "exit": "model-flip", "exit_bid": 0.6}
        f = desk_report.trade_fees(row)
        self.assertAlmostEqual(f["charged"], 0.15 + 0.17, places=2)
        self.assertAlmostEqual(f["old_way"], 10 * 0.02 + 10 * 0.02, places=2)

    def test_old_trades_are_not_counted_as_saved(self):
        f = desk_report.trade_fees({"contracts": 5, "fee": 0.02, "exit": "settled"})
        self.assertFalse(f["per_order"])
        self.assertEqual(f["charged"], f["old_way"])
        self.assertFalse(desk_report.trade_fees({"pnl": 1})["known"])


class CardTests(unittest.TestCase):
    def setUp(self):
        self.closed = {
            "more-15m": [
                {"ticker": "KXSOL15M-A", "side": "yes", "label": "SOL up", "contracts": 40, "ask": 0.5,
                 "order_fee": 0.7, "exit": "settled", "pnl": 19.3, "why": "fair 0.62 vs ask 0.50"},
                {"ticker": "KXXRP15M-B", "side": "no", "contracts": 30, "ask": 0.6, "order_fee": 0.51,
                 "exit": "model-flip", "exit_bid": 0.7, "pnl": 2.4},
                {"ticker": "KXBNB15M-C", "side": "yes", "contracts": 40, "ask": 0.55, "order_fee": 0.7,
                 "exit": "settled", "pnl": -22.7},
            ],
            "btc15m": [{"ticker": "KXBTC15M-D", "side": "yes", "contracts": 10, "fee": 0.02,
                        "exit": "settled", "pnl": -4.0}],
        }
        self.views = [
            _view("btc15m", today=-4.0),
            _view("sports-gap", today=0.0, why="No game cleared the gap rule."),
            _view("more-15m", today=-1.0, shadow=True),
            _view("weather-high", shadow=True, status="error", read_error="state file is half written"),
            _view("calibration-lab", shadow=True),
        ]

    def card(self, **kw):
        args = dict(research_ids={"calibration-lab"}, settled_by_bot={"more-15m": 51, "weather-high": 7},
                    checked_ids={"btc15m", "more-15m"}, now=NOW)
        args.update(kw)
        return desk_report.report_card(self.views, self.closed, "", CFG, **args)

    def test_tower_counts_keep_losses(self):
        c = self.card()
        more = next(t for t in c["towers"] if t["id"] == "more-15m")
        self.assertEqual((more["trades"], more["wins"], more["losses"]), (3, 2, 1))
        self.assertEqual(more["profit"], -1.0)  # the loss is in the total
        self.assertEqual(more["exits"]["held"], {"n": 2, "wins": 1, "losses": 1, "profit": -3.4})
        self.assertEqual(more["exits"]["sold_early"]["n"], 1)
        self.assertGreater(more["fee_once"]["saved"], 0)
        self.assertEqual(c["fee_once"]["trades"], 3)

    def test_biggest_win_and_loss_have_reasons(self):
        c = self.card()
        self.assertEqual(c["biggest_win"]["pnl"], 19.3)
        self.assertIn("held to the end", c["biggest_win"]["why"])
        self.assertEqual(c["biggest_loss"]["pnl"], -22.7)

    def test_health_quiet_errors_and_practice(self):
        c = self.card()
        self.assertEqual(c["health"], {"btc15m": "running", "sports-gap": "running", "more-15m": "running",
                                       "weather-high": "error", "calibration-lab": "research"})
        gap = next(t for t in c["towers"] if t["id"] == "sports-gap")
        self.assertIn("No game cleared the gap rule", gap["quiet"])
        self.assertTrue(any("half written" in e for e in c["errors"]))
        more = next(t for t in c["towers"] if t["id"] == "more-15m")
        self.assertTrue(more["practice"]["counts"])
        lab = next(t for t in c["towers"] if t["id"] == "calibration-lab")
        self.assertNotIn("practice", lab)
        self.assertTrue(any("More" in q or "more-15m" in q for q in c["questions"]))

    def test_numbers_add_up(self):
        c = self.card()
        self.assertEqual(c["checks"], [])
        self.assertTrue(c["send_ok"])
        self.assertEqual(c["desk_today"], -4.0)
        self.assertEqual(len(c["summary"]), 3)
        self.assertIn("-$4.00", c["summary"][0])

    def test_mismatch_stops_the_send(self):
        self.views[0]["today"] = 5.0  # tower says +5, its trades say -4
        c = self.card()
        self.assertFalse(c["send_ok"])
        self.assertTrue(any("add up" in p for p in c["checks"]))
        self.assertIn("number check", c["summary"][2])
        self.assertTrue(any("Hold the report" in q for q in c["questions"]))

    def test_stop_status(self):
        c = desk_report.report_card(self.views, self.closed, "Daily loss stop is hit.", CFG, now=NOW)
        self.assertTrue(c["stop"]["blocked"])
        self.assertEqual(c["stop"]["loss_room"], 146.0)

    def test_markdown_is_short_and_plain(self):
        text = desk_report.markdown(self.card(city_url="https://example.test/city"))
        self.assertIn("## Desk status", text)
        self.assertIn("## Words", text)
        self.assertIn("City page: https://example.test/city", text)
        self.assertNotIn("!", text)
        for word in ("scrape", "crawl"):
            self.assertNotIn(word, text.lower())
        self.assertLess(max(len(line) for line in text.splitlines()), 400)

    def test_log_line_is_json(self):
        line = desk_report.log_line(self.card())
        self.assertTrue(line.startswith("desk report {"))
        data = json.loads(line.split("desk report ", 1)[1])
        self.assertTrue(data["paper_only"])
        self.assertIn("quiet_count", data)

    def test_central_dates(self):
        self.assertEqual(desk_report.ct_date("November 13, 2026, 11:58 PM Central"), dt.date(2026, 11, 13))
        self.assertEqual(desk_report.ct_date("2026-11-14T03:00:00+00:00"), dt.date(2026, 11, 13))
        self.assertIsNone(desk_report.ct_date(""))


class DeskCardTests(unittest.TestCase):
    def test_reads_tower_state_and_matches_the_card(self):
        with tempfile.TemporaryDirectory() as root:
            folder = os.path.join(root, "btc15m-signal")
            os.makedirs(folder)
            open(os.path.join(folder, "btc15m_signal.py"), "w").close()
            spec = next(s for s in pimp_desk.BOTS if s["id"] == "btc15m")
            open(os.path.join(folder, spec["script"]), "a").close()
            state = {"cash": 95.0, "open": [], "closed": [
                {"ticker": "KXBTC15M-26NOV131400-00", "side": "yes", "contracts": 5, "cost": 2.5,
                 "fee": 0.02, "exit": "settled", "pnl": 2.4, "closed": _iso(14)},
                {"ticker": "KXBTC15M-26NOV131500-00", "side": "no", "contracts": 5, "cost": 3.0,
                 "fee": 0.02, "exit": "settled", "pnl": -3.0, "closed": _iso(15)},
                {"ticker": "KXBTC15M-26NOV121500-00", "side": "no", "contracts": 5, "cost": 3.0,
                 "fee": 0.02, "exit": "settled", "pnl": -1.0, "closed": "2026-11-12T12:00:00+00:00"},
            ]}
            with open(os.path.join(folder, spec["state"]), "w") as fh:
                json.dump(state, fh)
            card = pimp_desk.desk_report_card(root, now=NOW)
        btc = next(t for t in card["towers"] if t["id"] == "btc15m")
        self.assertEqual((btc["trades"], btc["wins"], btc["losses"]), (2, 1, 1))
        self.assertEqual(btc["profit"], -0.6)
        self.assertEqual(btc["desk_today"], -0.6)
        self.assertTrue(btc.get("checked"))
        self.assertEqual(card["checks"], [])
        self.assertTrue(card["paper_only"])


class DeskReportLogTests(unittest.TestCase):
    def setUp(self):
        desk_service._last_report_log[0] = 0.0

    def test_logs_every_thirty_minutes(self):
        class D:
            n = 0

            def desk_report_card(self):
                D.n += 1
                return desk_report.report_card([_view("btc15m")], {}, "", CFG, now=NOW)

        self.assertTrue(desk_service.log_desk_report(D(), now=10_000.0).startswith("desk report "))
        self.assertEqual(desk_service.log_desk_report(D(), now=10_600.0), "")
        self.assertTrue(desk_service.log_desk_report(D(), now=11_801.0))
        self.assertEqual(D.n, 2)

    def test_failure_never_stops_the_pass(self):
        class D:
            def desk_report_card(self):
                raise RuntimeError("boom")

        self.assertEqual(desk_service.log_desk_report(D(), now=50_000.0), "")

    def test_desk_without_the_helper_is_fine(self):
        self.assertEqual(desk_service.log_desk_report(object(), now=90_000.0), "")


if __name__ == "__main__":
    unittest.main()


class PeriodTests(unittest.TestCase):
    def test_week_totals_rank_and_lower_bound(self):
        views = [_view("btc15m"), _view("more-15m", shadow=True)]
        rows = {"btc15m": [{"pnl": 1.0, "cost": 2}, {"pnl": -3.0, "cost": 4}],
                "more-15m": [{"pnl": 5.0}, {"pnl": 2.0}, {"pnl": -1.0}]}
        c = desk_report.period_card(views, rows, dt.date(2026, 11, 7), dt.date(2026, 11, 13))
        self.assertEqual(c["desk_profit"], -2.0)
        self.assertEqual(c["practice_profit"], 6.0)
        self.assertEqual([t["id"] for t in c["towers"]], ["more-15m", "btc15m"])
        more = c["towers"][0]
        self.assertLess(more["win_rate_low"], more["win_rate"])
        self.assertIn("| 1 | more-15m", desk_report.period_markdown(c))

    def test_wilson(self):
        self.assertIsNone(desk_report.wilson_low(0, 0))
        self.assertAlmostEqual(desk_report.wilson_low(50, 100), 0.4189, places=3)

    def test_desk_period_reads_the_week(self):
        with tempfile.TemporaryDirectory() as root:
            spec = next(s for s in pimp_desk.BOTS if s["id"] == "btc15m")
            folder = os.path.join(root, spec["folder"])
            os.makedirs(folder)
            open(os.path.join(folder, spec["script"]), "a").close()
            closed = [{"pnl": 1.0, "exit": "settled", "closed": _iso(10)},
                      {"pnl": -2.0, "exit": "settled", "closed": "2026-11-09T15:00:00+00:00"},
                      {"pnl": 9.0, "exit": "settled", "closed": "2026-10-01T15:00:00+00:00"}]
            with open(os.path.join(folder, spec["state"]), "w") as fh:
                json.dump({"cash": 99, "open": [], "closed": closed}, fh)
            c = pimp_desk.desk_period_card(root, days=7, now=NOW)
        btc = next(t for t in c["towers"] if t["id"] == "btc15m")
        self.assertEqual((btc["trades"], btc["profit"]), (2, -1.0))
