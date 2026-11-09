"""Money-machine plan slice 1: half-Kelly CRB + fee-sim observe (paper only)."""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_profit
import desk_roi_plan


class HalfKellyCrbFeeSim(unittest.TestCase):
    def test_fee_sim_probe_clears_and_fails(self):
        ok = desk_roi_plan.fee_sim_probe(
            venue="kalshi_sports", fair=0.62, ask=0.52,
        )
        self.assertTrue(ok["clear"])
        self.assertGreaterEqual(ok["edge_after_fee"], 0.06 - 1e-9)
        self.assertEqual(ok["floor"], 0.06)
        self.assertTrue(ok["fee_floors_locked"])
        self.assertFalse(ok["live_orders_enabled"])

        thin = desk_roi_plan.fee_sim_probe(
            venue="kalshi_sports", fair=0.55, ask=0.52,
        )
        self.assertFalse(thin["clear"])
        self.assertLess(thin["edge_after_fee"], 0.06)

    def test_fee_sim_observe_board(self):
        out = desk_roi_plan.fee_sim_observe(".")
        self.assertTrue(out["observe_only"])
        self.assertTrue(out["paper_only"])
        self.assertFalse(out["auto_promote"])
        self.assertGreaterEqual(out["n"], 4)
        self.assertGreaterEqual(out["clears_n"], 1)

    def test_half_kelly_crb_is_counterfactual_only(self):
        cfg = {
            "max_open_risk": 100.0,
            "stake_lo_max": 20.0,
            "stake_hi_min": 20.0,
            "stake_hi_max": 100.0,
            "stake_hi_prob": 0.8,
            "sizing": "kelly_lite",
            "kelly_fraction": 0.25,
        }
        bots = [
            {"id": "sports-gap", "open_risk": 10.0, "shadow_only": False},
            {"id": "btc15m", "open_risk": 5.0, "shadow_only": False},
            {"id": "commodity-15m", "open_risk": 0.0, "shadow_only": False},
            {"id": "coinbase-spot", "open_risk": 25.0, "shadow_only": True},
        ]
        out = desk_roi_plan.half_kelly_crb_observe(".", bots=bots, cfg=cfg)
        self.assertTrue(out["observe_only"])
        self.assertEqual(out["live_kelly_fraction"], 0.25)
        self.assertEqual(out["observe_kelly_fraction"], 0.50)
        self.assertFalse(out["live_orders_enabled"])
        self.assertFalse(out["auto_promote"])
        self.assertAlmostEqual(out["desk_open_risk"], 15.0, places=2)
        # Shadow cash must not count toward CRB open risk.
        self.assertEqual(len(out["towers"]), 3)
        # Half-Kelly stake ≥ live stake for the same fee-clear probe.
        self.assertGreaterEqual(out["half_kelly_stake"], out["live_kelly_stake"])
        # Live cfg must stay at 0.25 — observe never mutates desk_profit defaults.
        self.assertEqual(
            float(cfg.get("kelly_fraction")),
            desk_roi_plan.LIVE_KELLY_FRACTION,
        )
        live = desk_profit.kelly_lite_dollars(
            0.62, 0.08, {**cfg, "kelly_fraction": 0.25},
            open_risk_used=15.0, ask=0.52,
        )
        self.assertEqual(out["live_kelly_stake"], live)

    def test_dutch_book_underround_and_overround(self):
        under = desk_roi_plan.dutch_book_probe(
            [{"side": "home", "ask": 0.44}, {"side": "away", "ask": 0.44}],
            venue="kalshi_sports",
        )
        self.assertTrue(under["clear"])
        self.assertGreaterEqual(under["edge"], 0.06 - 1e-9)
        over = desk_roi_plan.dutch_book_probe(
            [{"side": "home", "ask": 0.52}, {"side": "away", "ask": 0.52}],
            venue="kalshi_sports",
        )
        self.assertFalse(over["clear"])
        self.assertIn("overround", over["reason"].lower())
        board = desk_roi_plan.dutch_book_observe(".")
        self.assertTrue(board["observe_only"])
        self.assertGreaterEqual(board["clears_n"], 1)
        self.assertFalse(board["live_orders_enabled"])

    def test_poly_arb_fee_wall_and_fat_gap(self):
        thin = desk_roi_plan.cross_venue_arb_probe({
            "label": "thin",
            "kalshi_venue": "kalshi_sports",
            "poly_category": "sports",
            "kalshi_yes_ask": 0.48,
            "poly_no_ask": 0.50,
        })
        self.assertTrue(thin["ok"])
        self.assertFalse(thin["clear"])
        self.assertIn("fee wall", thin["reason"].lower())
        fat = desk_roi_plan.cross_venue_arb_probe({
            "label": "fat",
            "kalshi_venue": "kalshi_econ",
            "poly_category": "geopolitics",
            "kalshi_yes_ask": 0.40,
            "poly_no_ask": 0.48,
        })
        self.assertTrue(fat["clear"])
        self.assertGreaterEqual(fat["edge"], 0.05 - 1e-9)
        incomplete = desk_roi_plan.cross_venue_arb_probe({
            "kalshi_yes_ask": 0.45,
        })
        self.assertFalse(incomplete["ok"])
        self.assertIn("no invent", incomplete["reason"].lower())
        # Explicit fixtures — cwd may have a harvested file that is all fee-walled.
        board = desk_roi_plan.cross_venue_arb_observe(
            ".",
            pairs=[
                {
                    "label": "thin_gap_sports",
                    "kalshi_venue": "kalshi_sports",
                    "poly_category": "sports",
                    "kalshi_yes_ask": 0.48,
                    "poly_no_ask": 0.50,
                },
                {
                    "label": "fat_gap_geopolitics",
                    "kalshi_venue": "kalshi_econ",
                    "poly_category": "geopolitics",
                    "kalshi_yes_ask": 0.40,
                    "poly_no_ask": 0.48,
                },
            ],
        )
        self.assertTrue(board["idea_bank_only"])
        self.assertTrue(board["observe_only"])
        self.assertFalse(board["live_orders_enabled"])
        self.assertGreaterEqual(board["clears_n"], 1)

    def test_cpi_nowcast_clear_thin_and_incomplete(self):
        thin = desk_roi_plan.cpi_nowcast_probe({
            "label": "thin",
            "nowcast_fair": 0.55,
            "ask": 0.52,
        })
        self.assertTrue(thin["ok"])
        self.assertFalse(thin["clear"])
        self.assertIn("cpi edge", thin["reason"])
        fat = desk_roi_plan.cpi_nowcast_probe({
            "label": "fat",
            "nowcast_fair": 0.62,
            "ask": 0.50,
        })
        self.assertTrue(fat["clear"])
        self.assertEqual(fat["action"], "buy")
        self.assertGreaterEqual(fat["edge"], 0.05 - 1e-9)
        incomplete = desk_roi_plan.cpi_nowcast_probe({"ask": 0.48})
        self.assertFalse(incomplete["ok"])
        self.assertIn("no invent", incomplete["reason"].lower())
        # Explicit fixtures — cwd harvest leaves nowcast_fair null (waiting on staff).
        board = desk_roi_plan.cpi_nowcast_observe(
            ".",
            strikes=[
                {"label": "thin", "nowcast_fair": 0.55, "ask": 0.52},
                {"label": "fat", "nowcast_fair": 0.62, "ask": 0.50},
            ],
        )
        self.assertTrue(board["idea_bank_only"])
        self.assertTrue(board["observe_only"])
        self.assertFalse(board["live_orders_enabled"])
        self.assertGreaterEqual(board["clears_n"], 1)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_econ"], 0.05)

    def test_vol_curve_btc_and_commodity(self):
        thin_btc = desk_roi_plan.btc_vol_binary_probe({
            "vol_fair": 0.54, "ask": 0.52, "dvol": 48.0,
        })
        self.assertFalse(thin_btc["clear"])
        fat_btc = desk_roi_plan.btc_vol_binary_probe({
            "vol_fair": 0.62, "ask": 0.50, "dvol": 55.0,
        })
        self.assertTrue(fat_btc["clear"])
        self.assertEqual(fat_btc["venue"], "kalshi_btc15m")
        thin_cmd = desk_roi_plan.commodity_curve_probe({
            "curve_fair": 0.54, "ask": 0.52, "roll_yield": 0.001,
        })
        self.assertFalse(thin_cmd["clear"])
        fat_cmd = desk_roi_plan.commodity_curve_probe({
            "curve_fair": 0.61, "ask": 0.50,
            "roll_yield": -0.012, "eia_regime": "draw",
        })
        self.assertTrue(fat_cmd["clear"])
        self.assertEqual(fat_cmd["venue"], "kalshi_commodity15m")
        incomplete = desk_roi_plan.btc_vol_binary_probe({"ask": 0.51})
        self.assertIn("no invent", incomplete["reason"].lower())
        # Explicit fixtures — cwd may have a harvested file that is all thin.
        board = desk_roi_plan.vol_curve_observe(
            ".",
            btc_rows=[
                {"vol_fair": 0.54, "ask": 0.52},
                {"vol_fair": 0.62, "ask": 0.50},
            ],
            commodity_rows=[
                {"curve_fair": 0.54, "ask": 0.52},
                {"curve_fair": 0.61, "ask": 0.50},
            ],
        )
        self.assertTrue(board["observe_only"])
        self.assertFalse(board["live_orders_enabled"])
        self.assertGreaterEqual(board["btc"]["clears_n"], 1)
        self.assertGreaterEqual(board["commodity"]["clears_n"], 1)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_btc15m"], 0.05)
        self.assertEqual(desk_profit.DEFAULT_VENUE_MIN_EDGE["kalshi_commodity15m"], 0.05)

    def test_vol_curve_harvest_from_feature_store(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "desk_feature_store.jsonl")
            with open(store, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "bot": "btc15m", "ticker": "KXBTC15M-A",
                    "model_p": 0.62, "ask": 0.50, "dvol": 52.0,
                }) + "\n")
                handle.write(json.dumps({
                    "bot": "commodity-15m", "ticker": "KXWTI15M-B",
                    "model_p": 0.61, "ask": 0.50,
                    "skip_codes": ["EIA/inventory blackout"],
                }) + "\n")
                handle.write(json.dumps({
                    "bot": "commodity-15m", "ticker": "MISS",
                    "ask": 0.50,
                }) + "\n")
            out = desk_roi_plan.vol_curve_harvest(tmp, limit=10)
            self.assertTrue(out["ok"])
            self.assertEqual(out["btc_n"], 1)
            self.assertEqual(out["commodity_n"], 1)
            board = desk_roi_plan.vol_curve_observe(tmp)
            self.assertGreaterEqual(board["btc"]["clears_n"], 1)
            self.assertGreaterEqual(board["commodity"]["clears_n"], 1)
            with open(os.path.join(tmp, "desk_commodity_curve.json"), encoding="utf-8") as handle:
                cmd = json.load(handle)
            self.assertEqual(cmd["rows"][0]["eia_regime"], "eia_blackout")
            self.assertIsNone(cmd["rows"][0]["roll_yield"])

    def test_macro_kalshi_harvest_asks_no_invent_fair(self):
        import json
        import tempfile

        def opener(url: str):
            if "KXFEDDECISION" in url:
                return json.dumps({
                    "markets": [
                        {
                            "ticker": "KXFEDDECISION-A-H0",
                            "event_ticker": "KXFEDDECISION-A",
                            "title": "Hold",
                            "yes_ask_dollars": "0.44",
                        },
                        {
                            "ticker": "KXFEDDECISION-A-C25",
                            "event_ticker": "KXFEDDECISION-A",
                            "title": "Cut 25",
                            "yes_ask_dollars": "0.44",
                        },
                    ],
                }).encode()
            if "KXFED" in url and "DECISION" not in url:
                return json.dumps({"markets": []}).encode()
            if "KXCPI" in url:
                return json.dumps({
                    "markets": [{
                        "ticker": "KXCPI-26NOV-T0.2",
                        "title": "CPI >0.2",
                        "yes_ask_dollars": "0.50",
                    }],
                }).encode()
            return b"{}"

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "fed-watch-paper"))
            # harvest still writes bins/cpi even if quotes refresh is skipped.
            out = desk_roi_plan.macro_kalshi_harvest(tmp, opener=opener)
            self.assertTrue(out["ok"])
            self.assertEqual(out["fed_ask_n"], 2)
            self.assertEqual(out["cpi_ask_n"], 1)
            self.assertTrue(out["waiting_on_fedwatch_fair"])
            self.assertTrue(out["waiting_on_cpi_nowcast_fair"])
            self.assertGreaterEqual(out["dutch_clears_n"], 1)
            with open(
                os.path.join(tmp, "fed-watch-paper", "fedwatch_bins.json"),
                encoding="utf-8",
            ) as handle:
                bins = json.load(handle)
            self.assertIsNone(bins["bins"][0]["fedwatch_fair"])
            with open(os.path.join(tmp, "desk_cpi_nowcast.json"), encoding="utf-8") as handle:
                cpi = json.load(handle)
            self.assertIsNone(cpi["strikes"][0]["nowcast_fair"])

    def test_poly_kalshi_ask_harvest_no_invent_leg(self):
        import json
        import tempfile

        def opener(url: str):
            if "kalshi.com" in url and "KXFEDDECISION-26DEC-H0" in url:
                return json.dumps({
                    "market": {
                        "ticker": "KXFEDDECISION-26DEC-H0",
                        "yes_ask_dollars": "0.20",
                        "no_ask_dollars": "0.81",
                    },
                }).encode()
            if "polymarket.com" in url and "no-change" in url:
                return json.dumps([{
                    "slug": (
                        "will-there-be-no-change-in-fed-interest-rates-after-the-"
                        "december-2026-meeting-20260729232808635"
                    ),
                    "bestAsk": 0.19,
                    "bestBid": 0.18,
                }]).encode()
            # Missing other seeds → incomplete, never invent.
            return b"{}"

        matches = [dict(desk_roi_plan.POLY_ARB_MATCH_SEEDS[0])]
        with tempfile.TemporaryDirectory() as tmp:
            out = desk_roi_plan.poly_kalshi_ask_harvest(
                tmp, opener=opener, matches=matches,
            )
            self.assertTrue(out["ok"])
            self.assertEqual(out["complete_n"], 1)
            self.assertEqual(out["incomplete_n"], 0)
            with open(os.path.join(tmp, "desk_poly_arb_pairs.json"), encoding="utf-8") as handle:
                pairs = json.load(handle)["pairs"]
            self.assertEqual(pairs[0]["kalshi_yes_ask"], 0.2)
            self.assertEqual(pairs[0]["poly_yes_ask"], 0.19)
            self.assertAlmostEqual(pairs[0]["poly_no_ask"], 0.82)
            # Incomplete seed: kalshi only — poly leg stays null.
            incomplete = desk_roi_plan.poly_kalshi_ask_harvest(
                tmp,
                opener=opener,
                matches=[{
                    "label": "kalshi_only",
                    "kalshi_ticker": "KXFEDDECISION-26DEC-H0",
                    "poly_slug": "",
                    "kalshi_venue": "kalshi_econ",
                    "poly_category": "finance",
                }],
            )
            self.assertEqual(incomplete["complete_n"], 0)
            self.assertEqual(incomplete["incomplete_n"], 1)


if __name__ == "__main__":
    unittest.main()
