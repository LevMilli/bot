"""Shadow evidence densify — labeler, durable persist, no LIVE / auto-promote."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import desk_more
import desk_profit
import desk_roi_plan
import pimp_desk


class ShadowEvidenceDensify(unittest.TestCase):
    def test_near_miss_record_settle_label_grows_labeled_n(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_more.record_near_miss(
                tmp,
                {
                    "bot": "btc15m",
                    "ticker": "KXBTC15M-DENSE-1",
                    "side": "YES",
                    "soft": ["z"],
                    "z": 0.58,
                    "p": 0.78,
                    "edge": 0.06,
                    "note": "soft z skip",
                },
            )
            before = desk_roi_plan.near_miss_promote_status(tmp)
            self.assertEqual(before["labeled_n"], 0)
            self.assertFalse(before["auto_promote"])
            self.assertFalse(before["promote_ready"])

            out = desk_roi_plan.label_near_miss_from_result(
                tmp,
                ticker="KXBTC15M-DENSE-1",
                result="yes",
                bot="btc15m",
                note="test settle",
            )
            self.assertGreaterEqual(out["labeled"], 1)
            after = desk_roi_plan.near_miss_promote_status(tmp)
            self.assertEqual(after["labeled_n"], 1)
            self.assertGreater(after["labeled_n"], before["labeled_n"])
            self.assertFalse(after["auto_promote"])
            self.assertFalse(after["live"])
            self.assertFalse(after["promote_ready"])  # still thin

    def test_near_miss_persists_ask_for_honest_settle_label(self):
        """Sports gap_bot passes ask — dropping it forced ±stake labels at entry 0.5."""
        with tempfile.TemporaryDirectory() as tmp:
            row = desk_more.record_near_miss(
                tmp,
                {
                    "bot": "sports-gap",
                    "ticker": "KXNFLGAME-ASK-KEEP",
                    "side": "YES",
                    "soft": ["p"],
                    "p": 0.76,
                    "edge": 0.01,
                    "ask": 0.81,
                    "league": "NFL",
                    "note": "sports shadow near-miss on p · away",
                },
            )
            self.assertEqual(row.get("ask"), 0.81)
            self.assertEqual(row.get("entry_price"), 0.81)
            self.assertEqual(row.get("league"), "NFL")
            stored = desk_more.load_more(tmp).get("near_miss") or []
            self.assertEqual(stored[-1].get("ask"), 0.81)
            self.assertEqual(stored[-1].get("league"), "NFL")

            out = desk_roi_plan.label_near_miss_from_result(
                tmp,
                ticker="KXNFLGAME-ASK-KEEP",
                result="yes",
                bot="sports-gap",
                note="test settle with ask",
            )
            self.assertEqual(out["labeled"], 1)
            labeled = [
                r for r in (desk_more.load_more(tmp).get("near_miss") or [])
                if r.get("ticker") == "KXNFLGAME-ASK-KEEP"
            ][0]
            # stake 2 / ask 0.81 → contracts≈2.469 → win pnl ≈ +0.4691 (not +2.0)
            self.assertAlmostEqual(float(labeled["would_pnl"]), 0.4691, places=3)
            self.assertNotAlmostEqual(float(labeled["would_pnl"]), 2.0, places=2)
            self.assertFalse(
                desk_roi_plan.near_miss_promote_status(tmp).get("auto_promote")
            )

    def test_label_near_miss_prefers_sibling_organic_ask(self):
        """Pre-#402 ask-less rows precede post-#402 siblings — use sibling ask."""
        with tempfile.TemporaryDirectory() as tmp:
            desk_more.record_near_miss(
                tmp,
                {
                    "bot": "sports-gap",
                    "ticker": "KXNFLGAME-26NOV08ARISEA-SEA",
                    "side": "YES",
                    "soft": ["p"],
                    "p": 0.76,
                    "edge": 0.01,
                    "note": "legacy ask-less",
                },
            )
            # Force ask absent on legacy row (pre-#402 shape).
            state = desk_more.load_more(tmp)
            state["near_miss"][0].pop("ask", None)
            state["near_miss"][0].pop("entry_price", None)
            desk_more.save_more(state, tmp)
            desk_more.record_near_miss(
                tmp,
                {
                    "bot": "sports-gap",
                    "ticker": "KXNFLGAME-26NOV08ARISEA-SEA",
                    "side": "YES",
                    "soft": ["p"],
                    "p": 0.76,
                    "edge": 0.01,
                    "ask": 0.79,
                    "league": "NFL",
                    "note": "post-402 organic ask",
                },
            )
            out = desk_roi_plan.label_near_miss_from_result(
                tmp,
                ticker="KXNFLGAME-26NOV08ARISEA-SEA",
                result="yes",
                bot="sports-gap",
                note="sibling ask densify",
            )
            self.assertGreaterEqual(out["labeled"], 1)
            labeled = [
                r for r in (desk_more.load_more(tmp).get("near_miss") or [])
                if r.get("ticker") == "KXNFLGAME-26NOV08ARISEA-SEA"
                and r.get("would_pnl") is not None
            ]
            self.assertTrue(labeled)
            # stake 2 / ask 0.79 → win pnl ≈ +0.5316 (not +2.0 from entry 0.5)
            for row in labeled:
                self.assertAlmostEqual(float(row["would_pnl"]), 0.5316, places=3)
                self.assertNotAlmostEqual(float(row["would_pnl"]), 2.0, places=2)
                self.assertAlmostEqual(float(row.get("ask") or 0), 0.79, places=4)

    def test_label_near_miss_keeps_per_row_organic_asks(self):
        """Mixed asks 0.75 then 0.79 must not collapse to first organic price."""
        with tempfile.TemporaryDirectory() as tmp:
            for ask in (0.75, 0.79):
                desk_more.record_near_miss(
                    tmp,
                    {
                        "bot": "sports-gap",
                        "ticker": "KXNFLGAME-26NOV08DETMIA-DET",
                        "side": "YES",
                        "soft": ["p"],
                        "p": 0.76,
                        "edge": 0.01,
                        "ask": ask,
                        "league": "NFL",
                        "note": f"ask {ask}",
                    },
                )
            out = desk_roi_plan.label_near_miss_from_result(
                tmp,
                ticker="KXNFLGAME-26NOV08DETMIA-DET",
                result="yes",
                bot="sports-gap",
            )
            self.assertEqual(out["labeled"], 2)
            by_ask = {
                round(float(r["ask"]), 4): float(r["would_pnl"])
                for r in (desk_more.load_more(tmp).get("near_miss") or [])
                if r.get("would_pnl") is not None
            }
            self.assertAlmostEqual(by_ask[0.75], 0.6667, places=3)
            self.assertAlmostEqual(by_ask[0.79], 0.5316, places=3)

    def test_recover_near_miss_ask_from_edge(self):
        """Pre-#408 rows kept edge=p−ask−fee — invert recovers organic ask."""
        ask = 0.98
        fee = desk_roi_plan._kalshi_fee_per_contract(ask)
        p = 0.764256841634797
        edge = p - ask - fee
        got = desk_roi_plan.recover_near_miss_ask_from_edge(p, edge)
        self.assertIsNotNone(got)
        self.assertAlmostEqual(float(got), ask, places=3)
        self.assertIsNone(desk_roi_plan.recover_near_miss_ask_from_edge(0.7, None))
        self.assertIsNone(desk_roi_plan.recover_near_miss_ask_from_edge(None, 0.01))

    def test_densify_near_miss_ask_catchup_sibling_and_edge(self):
        """Catch-up stamps sibling ask + p/edge recover; repairs ±stake poison."""
        with tempfile.TemporaryDirectory() as tmp:
            # Ask-less BTC with recoverable p+edge (pre-#408 shape).
            desk_more.record_near_miss(
                tmp,
                {
                    "bot": "btc15m",
                    "ticker": "KXBTC15M-EDGE-RECOVER",
                    "side": "YES",
                    "soft": ["p"],
                    "p": 0.764256841634797,
                    "edge": 0.764256841634797 - 0.98 - desk_roi_plan._kalshi_fee_per_contract(0.98),
                    "note": "pre-408 dropped ask",
                },
            )
            state = desk_more.load_more(tmp)
            state["near_miss"][0].pop("ask", None)
            state["near_miss"][0].pop("entry_price", None)
            # Poison label at default entry 0.5 (win → +stake).
            state["near_miss"][0]["would_pnl"] = 2.0
            state["near_miss"][0]["labeled_at"] = "2026-11-08T18:34:14Z"
            desk_more.save_more(state, tmp)
            # Sports ask-less + sibling with organic ask.
            desk_more.record_near_miss(
                tmp,
                {
                    "bot": "sports-gap",
                    "ticker": "KXNFLGAME-ASK-SIB",
                    "side": "YES",
                    "soft": ["p"],
                    "p": 0.76,
                    "edge": 0.01,
                    "note": "ask-less pending",
                },
            )
            state = desk_more.load_more(tmp)
            for row in state["near_miss"]:
                if row.get("ticker") == "KXNFLGAME-ASK-SIB":
                    row.pop("ask", None)
                    row.pop("entry_price", None)
            desk_more.save_more(state, tmp)
            desk_more.record_near_miss(
                tmp,
                {
                    "bot": "sports-gap",
                    "ticker": "KXNFLGAME-ASK-SIB",
                    "side": "YES",
                    "soft": ["p"],
                    "p": 0.76,
                    "edge": 0.01,
                    "ask": 0.79,
                    "note": "organic sibling",
                },
            )
            out = desk_roi_plan.densify_near_miss_ask_catchup(tmp)
            self.assertTrue(out["ok"])
            self.assertGreaterEqual(out["stamped"], 2)
            self.assertGreaterEqual(out["relabeled"], 1)
            self.assertFalse(out.get("live"))
            self.assertFalse(out.get("auto_promote"))
            rows = desk_more.load_more(tmp).get("near_miss") or []
            btc = next(r for r in rows if r.get("ticker") == "KXBTC15M-EDGE-RECOVER")
            self.assertAlmostEqual(float(btc["ask"]), 0.98, places=3)
            self.assertEqual(btc.get("ask_densify"), "p_edge")
            # Win at 0.98: contracts=2/0.98 → pnl ≈ 0.0408 (not +2.0)
            self.assertAlmostEqual(float(btc["would_pnl"]), 0.0408, places=3)
            self.assertTrue(btc.get("ask_densify_relabel"))
            sib = [
                r for r in rows
                if r.get("ticker") == "KXNFLGAME-ASK-SIB" and r.get("ask_densify") == "sibling"
            ]
            self.assertTrue(sib)
            self.assertAlmostEqual(float(sib[0]["ask"]), 0.79, places=4)

    def test_near_miss_catchup_cli_labels_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_more.record_near_miss(
                tmp,
                {
                    "bot": "btc15m",
                    "ticker": "KX-CATCH-YES",
                    "side": "YES",
                    "soft": ["z"],
                },
            )
            desk_more.record_near_miss(
                tmp,
                {
                    "bot": "btc15m",
                    "ticker": "KX-CATCH-OPEN",
                    "side": "NO",
                    "soft": ["p"],
                },
            )

            def fetch(ticker: str):
                if ticker == "KX-CATCH-YES":
                    return "yes"
                return None

            out = desk_roi_plan.label_near_miss_catchup(tmp, fetch_result=fetch)
            self.assertTrue(out["ok"])
            self.assertEqual(out["labeled"], 1)
            self.assertFalse(out["auto_promote"])
            self.assertFalse(out["live"])
            st = desk_roi_plan.near_miss_promote_status(tmp)
            self.assertEqual(st["labeled_n"], 1)
            self.assertFalse(st["auto_promote"])

    def test_settlement_files_include_shadow_journals(self):
        expected = {
            "desk_sports_hard_stop_shadow.json",
            "desk_commodity_time_stop_shadow.json",
            "desk_sports_time_final_shadow.json",
            "desk_helper_fills.json",
            "desk_fee_ledger.json",
            "btc15m-signal/shadow_edge08_account.json",
        }
        present = set(pimp_desk.SETTLEMENT_FILES)
        missing = expected - present
        self.assertFalse(missing, f"SETTLEMENT_FILES missing {missing}")

    def test_hard_stop_shadow_records_without_fair_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec = desk_roi_plan.record_sports_hard_stop_shadow(
                tmp,
                ticker="KXNBA-NOFAIR",
                side="home",
                league="NBA",
                entry_price=0.78,
                bid=0.60,
                fair=None,  # densify: fair optional
                contracts=10,
                cost=8.0,
                note="shadow hard-stop — no live sell",
            )
            self.assertTrue(rec["recorded"])
            self.assertTrue(rec.get("shadow_only", True))
            summ = desk_roi_plan.sports_hard_stop_shadow_summary(tmp)
            self.assertEqual(summ["n"], 1)
            self.assertFalse(summ["auto_promote"])
            self.assertFalse(desk_roi_plan.SPORTS_HARD_STOP_LIVE)

    def test_time_final_shadow_records_without_fair(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec = desk_roi_plan.record_sports_time_final_shadow(
                tmp,
                ticker="KXNBA-TF",
                side="away",
                league="NBA",
                minutes_left=1.0,
                entry_price=0.70,
                bid=0.40,
                contracts=10,
                cost=7.0,
                note="shadow time-final — no live sell",
            )
            self.assertTrue(rec["recorded"], rec)
            self.assertTrue(rec.get("shadow_only", True))
            self.assertFalse(desk_roi_plan.SPORTS_TIME_FINAL_LIVE)

    def test_helper_backfill_from_btc_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            acct_dir = os.path.join(tmp, "btc15m-signal")
            os.makedirs(acct_dir, exist_ok=True)
            closed = [
                {
                    "ticker": "KXBTC-H1",
                    "helper_source": "calendar_scanner",
                    "pnl": 0.12,
                    "contracts": 2,
                    "fill_id": "fill-h1",
                    "closed": "2026-11-07 01:00:00 UTC",
                },
                {
                    "ticker": "KXBTC-H2",
                    "calendar_loaded": True,
                    "pnl": 0.05,
                    "contracts": 1,
                    "fill_id": "fill-h2",
                    "closed": "2026-11-07 02:00:00 UTC",
                },
                {
                    "ticker": "KXBTC-NONE",
                    "pnl": 0.01,
                    "contracts": 1,
                    "fill_id": "fill-none",
                },
            ]
            with open(os.path.join(acct_dir, "paper_account.json"), "w", encoding="utf-8") as fh:
                json.dump({"cash": 100, "open": [], "closed": closed}, fh)
            out = desk_roi_plan.backfill_helper_fills_from_btc_closed(tmp)
            self.assertTrue(out["ok"])
            self.assertEqual(out["recorded"], 2)
            again = desk_roi_plan.backfill_helper_fills_from_btc_closed(tmp)
            self.assertEqual(again["recorded"], 0)  # idempotent
            self.assertFalse(out["places_orders"])
            self.assertFalse(out["auto_promote"])

    def test_repair_clv_completeness(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Missing close stays incomplete — repair must NOT invent binary 0/1.
            desk_more.record_sports_clv(
                tmp,
                ticker="KX-CLV-1",
                side="home",
                fair_entry=0.62,
                close_fair=None,
                pnl=1.0,
                league="NBA",
                exit_reason="settled",
            )
            state = desk_more.load_clv(tmp)
            row = state["rows"][0]
            row.pop("fair_close", None)
            row.pop("close_fair", None)
            row["clv"] = None
            row["exit"] = "settled"
            desk_more.save_clv(state, tmp)
            before = desk_roi_plan.clv_completeness(tmp)
            self.assertFalse(before["pass"])
            out = desk_roi_plan.repair_clv_completeness(tmp)
            self.assertTrue(out["ok"])
            self.assertEqual(out["repaired"], 0)
            self.assertGreaterEqual(out["skipped"], 1)
            after = desk_roi_plan.clv_completeness(tmp)
            self.assertFalse(after["pass"])
            # With both fairs present, repair only fills missing clv (line).
            desk_more.record_sports_clv(
                tmp,
                ticker="KX-CLV-2",
                side="home",
                fair_entry=0.70,
                close_fair=0.65,
                pnl=1.0,
                league="NBA",
                exit_reason="settled",
                clv_kind="line",
            )
            state = desk_more.load_clv(tmp)
            state["rows"][-1]["clv"] = None
            desk_more.save_clv(state, tmp)
            out2 = desk_roi_plan.repair_clv_completeness(tmp)
            self.assertGreaterEqual(out2["repaired"], 1)
            self.assertFalse(out2["auto_promote"])
            self.assertFalse(out2["live"])

    def test_repair_clv_upgrades_wipe_from_time_final_mark(self):
        """WVUTTU-shaped: binary fair_close=1.0 + t-final bid 0.83 → line CLV."""
        with tempfile.TemporaryDirectory() as tmp:
            desk_more.record_sports_clv(
                tmp,
                ticker="KXNCAAFGAME-26NOV07WVUTTU-TTU",
                side="home",
                fair_entry=0.9271,
                close_fair=1.0,
                pnl=3.45,
                league="NCAAF",
                exit_reason="settled",
            )
            # Untagged wipe close is excluded from green_boost.
            state = desk_more.load_clv(tmp)
            state["rows"][0]["clv_kind"] = None
            desk_more.save_clv(state, tmp)
            before = desk_more.clv_summary(tmp)
            self.assertEqual(before["n"], 0)
            self.assertEqual(before["binary_excluded_n"], 1)
            # Organic mid-open mark already on time-final journal.
            desk_roi_plan._save(
                desk_roi_plan._path(desk_roi_plan.SPORTS_TIME_FINAL_SHADOW, tmp),
                {
                    "paper_only": True,
                    "version": 1,
                    "live": False,
                    "rows": [{
                        "ticker": "KXNCAAFGAME-26NOV07WVUTTU-TTU",
                        "side": "home",
                        "bid": 0.83,
                        "minutes_left": 1.4,
                        "shadow_only": True,
                    }],
                },
            )
            out = desk_roi_plan.repair_clv_completeness(tmp)
            self.assertTrue(out["ok"], out)
            self.assertEqual(out.get("mark_upgraded"), 1)
            self.assertGreaterEqual(out["repaired"], 1)
            again = desk_more.load_clv(tmp)
            row = again["rows"][0]
            self.assertEqual(row.get("clv_kind"), "line")
            self.assertAlmostEqual(float(row["fair_close"]), 0.83, places=4)
            self.assertAlmostEqual(float(row["clv"]), 0.9271 - 0.83, places=4)
            after = desk_more.clv_summary(tmp)
            self.assertEqual(after["n"], 1)
            self.assertEqual(after["binary_excluded_n"], 0)
            # Idempotent — second pass does not re-upgrade.
            out2 = desk_roi_plan.repair_clv_completeness(tmp)
            self.assertEqual(out2.get("mark_upgraded"), 0)

    def test_exports_observe_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            nm = desk_roi_plan.export_near_miss_shadow_csv(tmp)
            e08 = desk_roi_plan.export_edge08_shadow_csv(tmp)
            gb = desk_roi_plan.export_green_boost_evidence(tmp)
            for packet in (nm, e08, gb):
                self.assertTrue(packet.get("ok") or packet.get("wrote") is not None)
                self.assertFalse(packet.get("auto_promote"))
                self.assertTrue(packet.get("fee_floors_locked"))
                self.assertTrue(packet.get("paper_only"))

    def test_no_live_no_force_floors_locked(self):
        self.assertFalse(desk_roi_plan.LIVE_ORDERS_ENABLED)
        self.assertFalse(desk_roi_plan.SPORTS_HARD_STOP_LIVE)
        self.assertFalse(desk_roi_plan.NEAR_MISS_LIVE)
        floors = desk_profit.venue_floors_locked()
        self.assertTrue(floors["locked"])
        self.assertTrue(floors["all_ok"])
        with tempfile.TemporaryDirectory() as tmp:
            st = desk_roi_plan.near_miss_promote_status(tmp)
            self.assertFalse(st["auto_promote"])
            self.assertFalse(st.get("live"))

    def test_settle_retro_bid_fetch_records_hard_stop_and_tfinal(self):
        """Final without pair → Kalshi bid fallback densifies hard-stop / t-final."""
        gap_path = os.path.join(HERE, "sports-gap-paper", "gap_bot.py")
        with open(gap_path, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("fetch_kalshi_market", src)
        self.assertIn("market_yes_bid", src)
        self.assertIn("settle-retro shadow hard-stop", src)
        self.assertIn("SETTLE-RETRO STOP", src)
        # Live settle path must not re-invent t-final with forced rem=0.
        self.assertIn("Time-final settle-retro disabled", src)
        self.assertNotIn("rem = 0.0  # final → treat as 0 min left", src)
        self.assertNotIn("LIVE_ORDERS = True", src)

    def test_gap_bot_skips_winner_wipe_hard_stop_source(self):
        gap_path = os.path.join(HERE, "sports-gap-paper", "gap_bot.py")
        with open(gap_path, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("wipe_quote", src)
        self.assertIn("never invent threshold stops", src.lower())
        cmd_path = os.path.join(HERE, "commodity-15m-paper", "bot.py")
        with open(cmd_path, encoding="utf-8") as fh:
            cmd = fh.read()
        self.assertIn("bid_ts >= 0", cmd)
        self.assertIn("wipe_quote", cmd)
        with tempfile.TemporaryDirectory() as tmp:
            # Simulate settle-retro path: no pair, bid from Kalshi market fetch.
            market = {"ticker": "KXNBA-RETRO-1", "yes_bid_dollars": "0.55"}
            # Import helpers from gap_bot without running main.
            import importlib.util
            spec = importlib.util.spec_from_file_location("gap_bot_settle", gap_path)
            mod = importlib.util.module_from_spec(spec)
            # Avoid executing main side effects: load only after patching? Spec loads full module.
            # Prefer unit-level record with fetched bid (same path settle-retro uses).
            bid = float(market["yes_bid_dollars"])
            hs = desk_roi_plan.record_sports_hard_stop_shadow(
                tmp,
                ticker="KXNBA-RETRO-1",
                side="home",
                league="NBA",
                entry_price=0.78,
                bid=bid,
                fair=None,
                contracts=10,
                cost=7.8,
                note="settle-retro shadow hard-stop — no live sell",
            )
            self.assertTrue(hs["recorded"])
            tf = desk_roi_plan.record_sports_time_final_shadow(
                tmp,
                ticker="KXNBA-RETRO-1",
                side="home",
                league="NBA",
                minutes_left=0.0,
                entry_price=0.78,
                bid=bid,
                contracts=10,
                cost=7.8,
                note="settle-retro shadow time-final — no live sell",
            )
            self.assertTrue(tf["recorded"])
            self.assertEqual(desk_roi_plan.sports_hard_stop_shadow_summary(tmp)["n"], 1)
            self.assertEqual(desk_roi_plan.sports_time_final_shadow_summary(tmp)["n"], 1)
            self.assertFalse(desk_roi_plan.SPORTS_HARD_STOP_LIVE)
            self.assertFalse(desk_roi_plan.SPORTS_TIME_FINAL_LIVE)

    def test_catchup_backfill_closed_loser_bid_zero(self):
        """Closed sports loser with Kalshi bid=0 densifies hard-stop + time-final."""
        with tempfile.TemporaryDirectory() as tmp:
            sports_dir = os.path.join(tmp, "sports-gap-paper")
            os.makedirs(sports_dir, exist_ok=True)
            state = {
                "cash": 100.0,
                "open": [],
                "closed": [
                    {
                        "ticker": "KX-CLOSED-LOSER",
                        "side": "home",
                        "league": "NCAAF",
                        "entry_price": 0.72,
                        "contracts": 27,
                        "cost": 19.98,
                        "pnl": -19.98,
                    }
                ],
                "paper_only": True,
            }
            with open(os.path.join(sports_dir, "state.json"), "w", encoding="utf-8") as fh:
                json.dump(state, fh)

            def fake_market(ticker: str):
                self.assertEqual(ticker, "KX-CLOSED-LOSER")
                return {"ticker": ticker, "yes_bid_dollars": "0", "status": "finalized"}

            out = desk_roi_plan.backfill_sports_exit_shadow_from_closed(
                tmp, fetch_market=fake_market,
            )
            self.assertTrue(out["ok"])
            self.assertEqual(out["hard_stop"], 1)
            # Time-final is not settle-retro densified.
            self.assertEqual(out["time_final"], 0)
            hs = desk_roi_plan.sports_hard_stop_shadow_summary(tmp)
            self.assertEqual(hs["n"], 1)
            self.assertGreater(hs["shadow_expectancy"], -19.98)
            self.assertEqual(desk_roi_plan.sports_time_final_shadow_summary(tmp)["n"], 0)
            # Idempotent — second pass records nothing.
            again = desk_roi_plan.backfill_sports_exit_shadow_from_closed(
                tmp, fetch_market=fake_market,
            )
            self.assertEqual(again["recorded"], 0)

    def test_catchup_api_wipe_on_loser_records_hard_stop(self):
        """API wipe 0 on settle loser densifies hard-stop; entry companion bid ignored."""
        with tempfile.TemporaryDirectory() as tmp:
            sports_dir = os.path.join(tmp, "sports-gap-paper")
            os.makedirs(sports_dir, exist_ok=True)
            state = {
                "cash": 100.0,
                "open": [],
                "closed": [
                    {
                        "ticker": "KX-WIPE-LOSER",
                        "side": "home",
                        "league": "NCAAF",
                        "entry_price": 0.70,
                        # Entry companion bid ≈ ask — must NOT block wipe densify.
                        "bid": 0.69,
                        "ask": 0.70,
                        "exit_price": 0.65,
                        "contracts": 21,
                        "cost": 15.12,
                        "pnl": -1.89,
                    }
                ],
                "paper_only": True,
            }
            with open(os.path.join(sports_dir, "state.json"), "w", encoding="utf-8") as fh:
                json.dump(state, fh)

            def fake_market(ticker: str):
                return {
                    "ticker": ticker,
                    "yes_bid_dollars": "0.0000",
                    "status": "finalized",
                    "result": "no",
                }

            out = desk_roi_plan.backfill_sports_exit_shadow_from_closed(
                tmp, fetch_market=fake_market,
            )
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["hard_stop"], 1)
            self.assertEqual(out["time_final"], 0)
            summ = desk_roi_plan.sports_hard_stop_shadow_summary(tmp)
            self.assertEqual(summ["n"], 1)
            with open(
                os.path.join(tmp, desk_roi_plan.SPORTS_HARD_STOP_SHADOW),
                encoding="utf-8",
            ) as fh:
                row = (json.load(fh).get("rows") or [])[0]
            self.assertEqual(row.get("bid"), 0.0)
            self.assertTrue(row.get("priced_at_threshold"))
            # Repair must keep loser wipe densify (not strip via entry bid).
            repair = desk_roi_plan.repair_sports_hard_stop_settle_poison(tmp)
            self.assertEqual(repair["removed"], 0)
            self.assertEqual(repair["kept"], 1)

    def test_catchup_prefers_exit_mark_not_entry_bid(self):
        """API missing → use exit_price/exit_bid; never entry companion bid."""
        with tempfile.TemporaryDirectory() as tmp:
            sports_dir = os.path.join(tmp, "sports-gap-paper")
            os.makedirs(sports_dir, exist_ok=True)
            state = {
                "cash": 100.0,
                "open": [],
                "closed": [
                    {
                        "ticker": "KX-EXIT-MARK",
                        "side": "home",
                        "league": "NCAAF",
                        "entry_price": 0.72,
                        "bid": 0.71,  # entry companion — not a stop
                        "exit_price": 0.55,  # underwater past −12¢
                        "ask": 0.72,
                        "contracts": 27,
                        "cost": 19.44,
                        "pnl": -4.59,
                    }
                ],
                "paper_only": True,
            }
            with open(os.path.join(sports_dir, "state.json"), "w", encoding="utf-8") as fh:
                json.dump(state, fh)

            def fake_missing(ticker: str):
                return None

            out = desk_roi_plan.backfill_sports_exit_shadow_from_closed(
                tmp, fetch_market=fake_missing,
            )
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["hard_stop"], 1)
            self.assertEqual(out["time_final"], 0)

            # Entry companion only — no densify invent.
            state2 = {
                "cash": 100.0,
                "open": [],
                "closed": [
                    {
                        "ticker": "KX-ENTRY-ONLY",
                        "side": "home",
                        "league": "NCAAF",
                        "entry_price": 0.72,
                        "bid": 0.71,
                        "ask": 0.72,
                        "contracts": 10,
                        "cost": 7.2,
                        "pnl": -2.0,
                    }
                ],
                "paper_only": True,
            }
            with open(os.path.join(sports_dir, "state.json"), "w", encoding="utf-8") as fh:
                json.dump(state2, fh)
            # Clear prior journal so we only count this ticker.
            hs_path = os.path.join(tmp, desk_roi_plan.SPORTS_HARD_STOP_SHADOW)
            if os.path.exists(hs_path):
                os.remove(hs_path)
            out2 = desk_roi_plan.backfill_sports_exit_shadow_from_closed(
                tmp, fetch_market=fake_missing,
            )
            self.assertEqual(out2["hard_stop"], 0)

    def test_catchup_prefers_exit_mark_when_api_recovered(self):
        """Gap-decay exit hits HS; recovered live api_bid must not drop it."""
        with tempfile.TemporaryDirectory() as tmp:
            sports_dir = os.path.join(tmp, "sports-gap-paper")
            os.makedirs(sports_dir, exist_ok=True)
            state = {
                "cash": 100.0,
                "open": [],
                "closed": [
                    {
                        "ticker": "KX-GAP-DECAY-HS",
                        "side": "home",
                        "league": "NFL",
                        "entry_price": 0.80,
                        "bid": 0.79,  # entry companion
                        "exit_price": 0.65,  # hits thr 0.68
                        "contracts": 10,
                        "cost": 8.0,
                        "pnl": -1.5,
                        "exit": "gap-decay: now 0.01 < 55% of entry 0.06",
                    }
                ],
                "paper_only": True,
            }
            with open(os.path.join(sports_dir, "state.json"), "w", encoding="utf-8") as fh:
                json.dump(state, fh)

            def fake_recovered(ticker: str):
                return {"yes_bid_dollars": "0.75"}  # above thr — old path dropped HS

            out = desk_roi_plan.backfill_sports_exit_shadow_from_closed(
                tmp, fetch_market=fake_recovered,
            )
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["hard_stop"], 1, out)
            hs = desk_roi_plan._load(
                desk_roi_plan._path(desk_roi_plan.SPORTS_HARD_STOP_SHADOW, tmp),
                {"rows": []},
            )
            row = (hs.get("rows") or [])[0]
            self.assertAlmostEqual(float(row.get("bid")), 0.65, places=4)
            # Idempotent
            again = desk_roi_plan.backfill_sports_exit_shadow_from_closed(
                tmp, fetch_market=fake_recovered,
            )
            self.assertEqual(again["hard_stop"], 0)

    def test_repair_removes_time_final_settle_retro_poison(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk_roi_plan.record_sports_time_final_shadow(
                tmp,
                ticker="KX-POISON-TF",
                minutes_left=0.0,
                entry_price=0.72,
                bid=0.55,
                contracts=10,
                cost=7.2,
                note="catchup settle-retro time-final — no live sell",
            )
            desk_roi_plan.record_sports_time_final_shadow(
                tmp,
                ticker="KX-REAL-TF",
                minutes_left=1.2,
                entry_price=0.72,
                bid=0.55,
                contracts=10,
                cost=7.2,
                note="shadow time-final — no live sell",
            )
            self.assertEqual(desk_roi_plan.sports_time_final_shadow_summary(tmp)["n"], 2)
            out = desk_roi_plan.repair_sports_time_final_settle_poison(tmp)
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["removed"], 1)
            self.assertEqual(out["kept"], 1)
            self.assertEqual(desk_roi_plan.sports_time_final_shadow_summary(tmp)["n"], 1)

    def test_catchup_skips_winner_wipe_hard_stop(self):
        """Finalized bid=0 on a settle winner must not invent a threshold hard-stop."""
        with tempfile.TemporaryDirectory() as tmp:
            sports_dir = os.path.join(tmp, "sports-gap-paper")
            os.makedirs(sports_dir, exist_ok=True)
            state = {
                "cash": 100.0,
                "open": [],
                "closed": [
                    {
                        "ticker": "KX-WINNER-WIPE",
                        "side": "home",
                        "league": "NCAAF",
                        "entry_price": 0.72,
                        "contracts": 27,
                        "cost": 19.44,
                        "pnl": 6.48,  # won — no mid-game stop evidence
                    }
                ],
                "paper_only": True,
            }
            with open(os.path.join(sports_dir, "state.json"), "w", encoding="utf-8") as fh:
                json.dump(state, fh)

            def fake_market(ticker: str):
                return {"ticker": ticker, "yes_bid": None, "status": "finalized"}

            out = desk_roi_plan.backfill_sports_exit_shadow_from_closed(
                tmp, fetch_market=fake_market,
            )
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["hard_stop"], 0)
            self.assertEqual(desk_roi_plan.sports_hard_stop_shadow_summary(tmp)["n"], 0)

    def test_repair_removes_threshold_poison_on_winners(self):
        with tempfile.TemporaryDirectory() as tmp:
            sports_dir = os.path.join(tmp, "sports-gap-paper")
            os.makedirs(sports_dir, exist_ok=True)
            # Seed a poisoned threshold row + a real loser stop.
            desk_roi_plan.record_sports_hard_stop_shadow(
                tmp,
                ticker="KX-POISON",
                entry_price=0.72,
                bid=0.0,
                contracts=10,
                cost=7.2,
                note="poison",
            )
            desk_roi_plan.record_sports_hard_stop_shadow(
                tmp,
                ticker="KX-REAL",
                entry_price=0.72,
                bid=0.50,
                contracts=10,
                cost=7.2,
                note="real",
            )
            with open(os.path.join(sports_dir, "state.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "cash": 100.0,
                    "open": [],
                    "closed": [
                        {
                            "ticker": "KX-POISON",
                            "entry_price": 0.72,
                            "bid": 0.71,
                            "pnl": 5.0,
                            "contracts": 10,
                            "cost": 7.2,
                        },
                        {
                            "ticker": "KX-REAL",
                            "entry_price": 0.72,
                            "bid": 0.50,
                            "pnl": -5.0,
                            "contracts": 10,
                            "cost": 7.2,
                        },
                    ],
                    "paper_only": True,
                }, fh)
            before = desk_roi_plan.sports_hard_stop_shadow_summary(tmp)["n"]
            self.assertEqual(before, 2)
            out = desk_roi_plan.repair_sports_hard_stop_settle_poison(tmp)
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["removed"], 1)
            self.assertEqual(out["kept"], 1)
            summ = desk_roi_plan.sports_hard_stop_shadow_summary(tmp)
            self.assertEqual(summ["n"], 1)

    def test_repair_drops_settle_retro_winner_even_without_threshold(self):
        """Catch-up / settle-retro notes on winners are poison even if bid≠threshold."""
        with tempfile.TemporaryDirectory() as tmp:
            sports_dir = os.path.join(tmp, "sports-gap-paper")
            os.makedirs(sports_dir, exist_ok=True)
            # Real underwater mid-open shadow — keep.
            desk_roi_plan.record_sports_hard_stop_shadow(
                tmp,
                ticker="KX-MID",
                entry_price=0.80,
                bid=0.60,
                contracts=10,
                cost=8.0,
                note="shadow hard-stop — no live sell",
            )
            # Settle-retro on a winner (exit 0.57 hits stop, settle pnl≥0) — drop.
            desk_roi_plan.record_sports_hard_stop_shadow(
                tmp,
                ticker="KX-WIN-RETRO",
                entry_price=0.75,
                bid=0.57,
                contracts=10,
                cost=7.5,
                note="catchup settle-retro hard-stop — no live sell",
            )
            # Settle-retro on a loser — keep (honest underwater finalize).
            desk_roi_plan.record_sports_hard_stop_shadow(
                tmp,
                ticker="KX-LOSE-RETRO",
                entry_price=0.70,
                bid=0.50,
                contracts=10,
                cost=7.0,
                note="settle-retro shadow hard-stop — no live sell",
            )
            with open(os.path.join(sports_dir, "state.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "cash": 100.0,
                    "open": [],
                    "closed": [
                        {
                            "ticker": "KX-MID",
                            "entry_price": 0.80,
                            "bid": 0.60,
                            "pnl": -3.0,
                            "contracts": 10,
                            "cost": 8.0,
                        },
                        {
                            "ticker": "KX-WIN-RETRO",
                            "entry_price": 0.75,
                            "bid": 0.90,
                            "pnl": 3.0,
                            "contracts": 10,
                            "cost": 7.5,
                        },
                        {
                            "ticker": "KX-LOSE-RETRO",
                            "entry_price": 0.70,
                            "bid": 0.50,
                            "pnl": -4.0,
                            "contracts": 10,
                            "cost": 7.0,
                        },
                    ],
                    "paper_only": True,
                }, fh)
            before = desk_roi_plan.sports_hard_stop_shadow_summary(tmp)["n"]
            self.assertEqual(before, 3)
            out = desk_roi_plan.repair_sports_hard_stop_settle_poison(tmp)
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["removed"], 1)
            self.assertEqual(out["kept"], 2)
            with open(
                os.path.join(tmp, desk_roi_plan.SPORTS_HARD_STOP_SHADOW),
                encoding="utf-8",
            ) as fh:
                rows = json.load(fh).get("rows") or []
            ticks = {r.get("ticker") for r in rows if isinstance(r, dict)}
            self.assertEqual(ticks, {"KX-MID", "KX-LOSE-RETRO"})

    def test_commodity_tstop_allows_bid_zero(self):
        hit = desk_roi_plan.commodity_time_stop_hit(
            close_time=None,
            bid=0.0,
            entry_price=0.55,
            cost=5.5,
            contracts=10,
            min_left=3.0,
            now=None,
        )
        # Without close_time, near_close is False — just assert bid=0 not rejected as invalid.
        self.assertEqual(hit["bid"], 0.0)
        self.assertTrue(hit["underwater"])


if __name__ == "__main__":
    unittest.main()
