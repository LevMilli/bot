#!/usr/bin/env python3
"""BTC + commodity CARD densify: evaluate skips surface on CARD (#396 sibling)."""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
BTC = HERE / "btc15m-signal" / "btc15m_signal.py"
CMD = HERE / "commodity-15m-paper" / "bot.py"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BtcCardSkipDensify(unittest.TestCase):
    def test_card_prefers_evaluate_skip_over_generic_no_buy(self):
        btc = _load(BTC, "btc15m_card_under_test")
        card = btc._card_sentence(
            buys=0,
            markets_n=3,
            eth_markets_n=2,
            last_sentence="Checked all open BTC 15-minute markets. No paper buy.",
            skip_reasons=["z < 1.25 (0.91); edge < 0.05 after fees"],
        )
        self.assertIn("z < 1.25", card)
        self.assertNotIn("No paper buy", card)

    def test_card_generic_only_when_skips_empty(self):
        btc = _load(BTC, "btc15m_card_under_test_empty")
        card = btc._card_sentence(
            buys=0,
            markets_n=3,
            eth_markets_n=0,
            last_sentence="Checked all open BTC 15-minute markets. No paper buy.",
            skip_reasons=[],
        )
        self.assertIn("No paper buy", card)

    def test_card_first_skip_wins(self):
        btc = _load(BTC, "btc15m_card_under_test_first")
        card = btc._card_sentence(
            buys=0,
            markets_n=1,
            eth_markets_n=0,
            last_sentence="Checked all open BTC 15-minute markets. No paper buy.",
            skip_reasons=["edge < 0.05 after fees", "firm queue blocks"],
        )
        self.assertEqual(card, "edge < 0.05 after fees")

    def test_sticky_skip_path_densifies_brain_like_firm(self):
        """Sticky buy-block must call record_decision (parity with firm + #403)."""
        src = BTC.read_text(encoding="utf-8")
        sticky_idx = src.find("if sticky_block:")
        firm_idx = src.find("if firm_block:")
        self.assertGreater(sticky_idx, 0)
        self.assertGreater(firm_idx, 0)
        sticky_chunk = src[sticky_idx:sticky_idx + 900]
        firm_chunk = src[firm_idx:firm_idx + 900]
        self.assertIn("desk_brain.record_decision", firm_chunk)
        self.assertIn("desk_brain.record_decision", sticky_chunk)
        self.assertIn("reasons=[sticky_block]", sticky_chunk)

    def test_max_buys_path_densifies_brain_like_sticky(self):
        """Max-buys capacity skip must call record_decision (#405 sibling)."""
        src = BTC.read_text(encoding="utf-8")
        max_idx = src.find("if buys >= max_buys_eff:")
        self.assertGreater(max_idx, 0)
        chunk = src[max_idx:max_idx + 1600]
        self.assertIn("desk_brain.record_decision", chunk)
        self.assertIn("reasons=[max_note]", chunk)
        cmd_src = CMD.read_text(encoding="utf-8")
        cmd_idx = cmd_src.find("if buys >= max_buys_eff:")
        self.assertGreater(cmd_idx, 0)
        cmd_chunk = cmd_src[cmd_idx:cmd_idx + 1400]
        self.assertIn("skip_reasons.append(max_note)", cmd_chunk)
        self.assertIn("_densify_evaluate_skip", cmd_chunk)
        self.assertIn("commodity max-buys densify", cmd_chunk)

    def test_desk_block_path_densifies_brain_like_max_buys(self):
        """Desk/account blocked fill must call record_decision (#407 sibling)."""
        src = BTC.read_text(encoding="utf-8")
        block_idx = src.find("desk/account blocked fill:")
        self.assertGreater(block_idx, 0)
        # Window around the BTC buy-fail densify (not ETH duplicate).
        chunk = src[max(0, block_idx - 400):block_idx + 900]
        self.assertIn("desk_brain.record_decision", chunk)
        self.assertIn("reasons=[block_note]", chunk)
        cmd_src = CMD.read_text(encoding="utf-8")
        self.assertIn("commodity desk-block densify", cmd_src)
        self.assertIn("skip_reasons.append(block_note)", cmd_src)

    def test_early_no_spot_densifies_not_generic_no_buy(self):
        """Prefer-1/2: all BTC spots down + no ETH windows densifies spot failed (#434 sibling)."""
        src = BTC.read_text(encoding="utf-8")
        early_idx = src.find("if not spots and not eth_markets:")
        self.assertGreater(early_idx, 0)
        chunk = src[early_idx:early_idx + 2200]
        self.assertIn('spot_reason = "spot failed"', chunk)
        self.assertIn("_densify_skip_brain", chunk)
        self.assertIn("btc spot densify", chunk)
        self.assertIn("return _card(spot_reason)", chunk)
        self.assertNotIn(
            'return _card("Checked all open BTC 15-minute markets. No paper buy.")',
            chunk,
        )
        import desk_brain
        import desk_more

        btc = _load(BTC, "btc15m_spot_fail_under_test")
        with tempfile.TemporaryDirectory() as tmp:
            btc.DESK_ROOT = tmp
            btc.IS_SHADOW = False
            btc._densify_skip_brain(
                reasons=["spot failed"],
                note="btc spot densify",
            )
            board = desk_more.skip_leaderboard(tmp)
            by_bot = board.get("by_bot") or {}
            self.assertIn("btc15m", by_bot)
            journal = desk_brain.load_journal(tmp)
            last = (journal.get("decisions") or [])[-1]
            self.assertEqual(last.get("action"), "skip")
            self.assertIn("spot failed", " ".join(last.get("reasons") or []))

    def test_eth_windows_no_eth_spot_densifies_not_generic_no_buy(self):
        """Prefer-1/2: open ETH windows + ETH spots down densify (#436 leftover).

        Early gate skips when eth_markets exist; silent eth_price is None break
        invented clean Checked… No paper buy (dual spot-down invent).
        """
        src = BTC.read_text(encoding="utf-8")
        gate_idx = src.find("if eth_markets and eth_price is None:")
        self.assertGreater(gate_idx, 0)
        chunk = src[gate_idx:gate_idx + 1600]
        self.assertIn('eth_spot_reason = "spot failed (eth)"', chunk)
        self.assertIn("skip_reasons.append(eth_spot_reason)", chunk)
        self.assertIn("_densify_skip_brain", chunk)
        self.assertIn("btc eth spot densify", chunk)
        self.assertIn('series="KXETH15M"', chunk)
        # Must not leave the silent break as the only ETH-spot handling.
        silent_break = src.find("for m in eth_markets:\n        if eth_price is None:\n            break")
        self.assertGreater(silent_break, gate_idx)

        import desk_brain
        import desk_more

        btc = _load(BTC, "btc15m_eth_spot_fail_under_test")
        with tempfile.TemporaryDirectory() as tmp:
            btc.DESK_ROOT = tmp
            btc.IS_SHADOW = False
            btc._densify_skip_brain(
                reasons=["spot failed (eth)"],
                note="btc eth spot densify",
            )
            board = desk_more.skip_leaderboard(tmp)
            by_bot = board.get("by_bot") or {}
            self.assertIn("btc15m", by_bot)
            journal = desk_brain.load_journal(tmp)
            last = (journal.get("decisions") or [])[-1]
            self.assertEqual(last.get("action"), "skip")
            self.assertIn("spot failed (eth)", " ".join(last.get("reasons") or []))

        # CARD prefers densified eth spot fail over ETH/BTC clean no-buy invent.
        card = btc._card_sentence(
            buys=0,
            markets_n=0,
            eth_markets_n=2,
            last_sentence="Checked ETH/BTC crypto Kalshi markets. No paper buy.",
            skip_reasons=["spot failed (eth)"],
        )
        self.assertIn("spot failed (eth)", card)
        self.assertNotIn("No paper buy", card)

    def test_eth_skip_paths_densify_brain(self):
        """ETH desk-block/delay/volatile must densify skip_board (#409 sibling)."""
        btc = _load(BTC, "btc15m_eth_brain_under_test")
        src = BTC.read_text(encoding="utf-8")
        self.assertIn("def _densify_skip_brain", src)
        for note in (
            "ETH desk-block densify",
            "ETH delay densify",
            "ETH volatile densify",
            "ETH parlay densify",
            "ETH evaluate densify",
            "ETH orderbook densify",
        ):
            self.assertIn(note, src)
        # Prefetch eth_errs must densify (BTC book_errs → reasons; not silent continue).
        self.assertIn("if key in eth_errs:", src)
        eth_err_chunk = src.split("if key in eth_errs:", 1)[1].split("ev_early = evaluate_window", 1)[0]
        self.assertIn("ETH orderbook densify", eth_err_chunk)
        self.assertIn("skip_reasons.append", eth_err_chunk)
        self.assertIn("_densify_skip_brain", eth_err_chunk)
        self.assertIn("orderbook failed", eth_err_chunk)
        import desk_brain
        import desk_more

        with tempfile.TemporaryDirectory() as tmp:
            # Helper uses module DESK_ROOT — point it at tmp.
            btc.DESK_ROOT = tmp
            btc.IS_SHADOW = False
            btc._densify_skip_brain(
                reasons=["ETH desk/account blocked fill"],
                ticker="KXETH-TEST",
                side="YES",
                edge=0.06,
                confidence=0.7,
                note="ETH desk-block densify",
            )
            board = desk_more.skip_leaderboard(tmp)
            by_bot = board.get("by_bot") or {}
            self.assertIn("btc15m", by_bot)
            codes = by_bot.get("btc15m") or {}
            self.assertGreaterEqual(sum(int(v) for v in codes.values()), 1)
            journal = desk_brain.load_journal(tmp)
            last = (journal.get("decisions") or [])[-1]
            self.assertEqual(last.get("action"), "skip")
            self.assertEqual(last.get("ticker"), "KXETH-TEST")
        # Consumer path: sticky reason → skip_board by_bot btc15m.
        import desk_brain
        import desk_more

        with tempfile.TemporaryDirectory() as tmp:
            desk_brain.record_decision(
                tmp,
                bot="btc15m",
                action="skip",
                ticker="KXBTC-STICKY",
                side="YES",
                edge=0.08,
                confidence=0.7,
                reasons=["sticky-open: exit first on red day"],
                note="sticky densify test",
            )
            board = desk_more.skip_leaderboard(tmp)
            by_bot = board.get("by_bot") or {}
            self.assertIn("btc15m", by_bot)
            codes = by_bot.get("btc15m") or {}
            self.assertGreaterEqual(sum(int(v) for v in codes.values()), 1)


class CommodityCardSkipDensify(unittest.TestCase):
    def test_card_prefers_evaluate_skip_over_generic_no_buy(self):
        cmd = _load(CMD, "commodity_card_under_test")
        card = cmd._card_sentence(
            buys=0,
            skip_reasons=["edge < 0.05 after fees; z < 1.0"],
        )
        self.assertIn("edge < 0.05", card)
        self.assertNotIn("No paper buy", card)

    def test_card_generic_only_when_skips_empty(self):
        cmd = _load(CMD, "commodity_card_under_test_empty")
        card = cmd._card_sentence(buys=0, skip_reasons=[])
        self.assertIn("No paper buy", card)

    def test_empty_windows_unchanged(self):
        cmd = _load(CMD, "commodity_card_under_test_empty_win")
        card = cmd._card_sentence(buys=0, open_windows=False)
        self.assertIn("No open windows", card)

    def test_card_spot_failed_beats_empty_windows_invent(self):
        """Prefer-1: all Yahoo down must not false-friend as No open windows (#433)."""
        cmd = _load(CMD, "commodity_card_spot_fail_under_test")
        card = cmd._card_sentence(
            buys=0,
            open_windows=False,
            skip_reasons=["spot failed (yahoo)"],
        )
        self.assertIn("spot failed", card)
        self.assertNotIn("No open windows", card)

    def test_card_kalshi_list_failed_beats_empty_windows_invent(self):
        """Prefer-1: Kalshi list-down must not false-friend as No open windows (#434 leftover)."""
        cmd = _load(CMD, "commodity_card_kalshi_list_fail_under_test")
        card = cmd._card_sentence(
            buys=0,
            open_windows=False,
            skip_reasons=["markets failed (kalshi)"],
        )
        self.assertIn("markets failed", card)
        self.assertNotIn("No open windows", card)

    def test_all_spot_fail_path_densifies_not_empty_windows(self):
        """Empty windows + no spots densifies spot failed into CARD/brain."""
        src = CMD.read_text(encoding="utf-8")
        empty_idx = src.find("if not windows:")
        self.assertGreater(empty_idx, 0)
        chunk = src[empty_idx:empty_idx + 4200]
        self.assertIn("if not spots:", chunk)
        self.assertIn("spot failed (yahoo)", chunk)
        self.assertIn("commodity spot densify", chunk)
        self.assertIn("_densify_evaluate_skip", chunk)
        self.assertIn("skip_reasons=empty_skip_reasons", chunk)
        cmd = _load(CMD, "commodity_spot_fail_brain_under_test")
        import desk_brain
        import desk_more

        with tempfile.TemporaryDirectory() as tmp:
            cmd.DESK_ROOT = tmp
            cmd._densify_evaluate_skip(
                reasons=["spot failed (yahoo)"],
                note="commodity spot densify",
            )
            journal = desk_brain.load_journal(tmp)
            last = (journal.get("decisions") or [])[-1]
            self.assertEqual(last.get("bot"), "commodity-15m")
            self.assertEqual(last.get("action"), "skip")
            self.assertIn("spot failed", " ".join(last.get("reasons") or []))
            board = desk_more.skip_leaderboard(tmp)
            self.assertIn("commodity-15m", board.get("by_bot") or {})

    def test_partial_spot_fail_empty_windows_densifies_not_invent(self):
        """Prefer-1: some Yahoo down + empty windows densifies — not clean empty (#434 leftover)."""
        src = CMD.read_text(encoding="utf-8")
        empty_idx = src.find("if not windows:")
        self.assertGreater(empty_idx, 0)
        chunk = src[empty_idx:empty_idx + 3200]
        self.assertIn("missing_spots", chunk)
        self.assertIn("elif missing_spots:", chunk)
        self.assertIn("commodity partial spot densify", chunk)
        self.assertIn("spot incomplete (yahoo", chunk)
        self.assertIn("_densify_evaluate_skip", chunk)
        # Partial must beat invent: CARD prefers densified skip over No open windows.
        # Incomplete (not total "spot failed") — spotted series may be true empty.
        cmd = _load(CMD, "commodity_partial_spot_card_under_test")
        card = cmd._card_sentence(
            buys=0,
            open_windows=False,
            skip_reasons=["spot incomplete (yahoo 2/6 missing)"],
        )
        self.assertIn("spot incomplete", card)
        self.assertNotIn("No open windows", card)
        import desk_brain
        import desk_more

        with tempfile.TemporaryDirectory() as tmp:
            cmd.DESK_ROOT = tmp
            cmd._densify_evaluate_skip(
                reasons=["spot incomplete (yahoo 2/6 missing)"],
                note="commodity partial spot densify",
            )
            journal = desk_brain.load_journal(tmp)
            last = (journal.get("decisions") or [])[-1]
            self.assertEqual(last.get("bot"), "commodity-15m")
            self.assertEqual(last.get("action"), "skip")
            self.assertIn("spot incomplete", " ".join(last.get("reasons") or []))
            board = desk_more.skip_leaderboard(tmp)
            self.assertIn("commodity-15m", board.get("by_bot") or {})

    def test_kalshi_list_fail_path_densifies_not_empty_windows(self):
        """Spots present + list_open raises densifies markets failed — not empty invent."""
        src = CMD.read_text(encoding="utf-8")
        # list_open must raise on GET fail (no silent []).
        list_fn = src.split("def list_open", 1)[1].split("\ndef ", 1)[0]
        self.assertNotIn("return []", list_fn)
        self.assertIn("get_json(", list_fn)
        empty_idx = src.find("if not windows:")
        self.assertGreater(empty_idx, 0)
        chunk = src[empty_idx:empty_idx + 3600]
        self.assertIn("elif list_errs:", chunk)
        self.assertIn("markets failed (kalshi)", chunk)
        self.assertIn("commodity kalshi list densify", chunk)
        self.assertIn("_densify_evaluate_skip", chunk)
        # Call site must catch list_open failures into list_errs.
        build_idx = src.find("list_errs: list[str] = []")
        self.assertGreater(build_idx, 0)
        build_chunk = src[build_idx:empty_idx]
        self.assertIn("Kalshi list failed", build_chunk)
        self.assertIn("list_errs.append(series)", build_chunk)
        cmd = _load(CMD, "commodity_kalshi_list_fail_brain_under_test")
        import desk_brain
        import desk_more

        with tempfile.TemporaryDirectory() as tmp:
            cmd.DESK_ROOT = tmp
            cmd._densify_evaluate_skip(
                reasons=["markets failed (kalshi)"],
                note="commodity kalshi list densify",
            )
            journal = desk_brain.load_journal(tmp)
            last = (journal.get("decisions") or [])[-1]
            self.assertEqual(last.get("bot"), "commodity-15m")
            self.assertEqual(last.get("action"), "skip")
            self.assertIn("markets failed", " ".join(last.get("reasons") or []))
            board = desk_more.skip_leaderboard(tmp)
            self.assertIn("commodity-15m", board.get("by_bot") or {})

        # Runtime: list_open raises instead of returning [].
        def _boom(_url, timeout=20):
            raise RuntimeError("kalshi 503")

        cmd.get_json = _boom
        with self.assertRaises(RuntimeError):
            cmd.list_open("KXGOLD15M", limit=1)

    def test_partial_kalshi_list_fail_empty_windows_densifies_not_invent(self):
        """Prefer-1: some list_errs + some [] + empty windows densifies incomplete — not total failed invent (#435 leftover)."""
        src = CMD.read_text(encoding="utf-8")
        empty_idx = src.find("if not windows:")
        self.assertGreater(empty_idx, 0)
        chunk = src[empty_idx:empty_idx + 3600]
        self.assertIn("listed_ok", chunk)
        self.assertIn("markets incomplete (kalshi", chunk)
        self.assertIn("commodity partial kalshi list densify", chunk)
        self.assertIn("_densify_evaluate_skip", chunk)
        # Partial must beat invent: CARD prefers densified skip over No open windows.
        # Incomplete (not total "markets failed") — listed-ok series may be true empty.
        cmd = _load(CMD, "commodity_partial_kalshi_list_card_under_test")
        card = cmd._card_sentence(
            buys=0,
            open_windows=False,
            skip_reasons=["markets incomplete (kalshi 2/4 failed)"],
        )
        self.assertIn("markets incomplete", card)
        self.assertNotIn("No open windows", card)
        import desk_brain
        import desk_more

        with tempfile.TemporaryDirectory() as tmp:
            cmd.DESK_ROOT = tmp
            cmd._densify_evaluate_skip(
                reasons=["markets incomplete (kalshi 2/4 failed)"],
                note="commodity partial kalshi list densify",
            )
            journal = desk_brain.load_journal(tmp)
            last = (journal.get("decisions") or [])[-1]
            self.assertEqual(last.get("bot"), "commodity-15m")
            self.assertEqual(last.get("action"), "skip")
            self.assertIn(
                "markets incomplete",
                " ".join(last.get("reasons") or []),
            )
            board = desk_more.skip_leaderboard(tmp)
            self.assertIn("commodity-15m", board.get("by_bot") or {})

    def test_evaluate_skip_densifies_brain_skip_board(self):
        cmd = _load(CMD, "commodity_brain_skip_under_test")
        import desk_brain
        import desk_more

        with tempfile.TemporaryDirectory() as tmp:
            cmd.DESK_ROOT = tmp
            cmd._densify_evaluate_skip(
                reasons=["edge < 0.05 after fees", "z < 1.0"],
                ticker="KXGOLD-TEST",
                side="YES",
                edge=0.02,
                confidence=0.61,
            )
            journal = desk_brain.load_journal(tmp)
            last = (journal.get("decisions") or [])[-1]
            self.assertEqual(last.get("bot"), "commodity-15m")
            self.assertEqual(last.get("action"), "skip")
            self.assertEqual(last.get("ticker"), "KXGOLD-TEST")
            board = desk_more.skip_leaderboard(tmp)
            by_bot = board.get("by_bot") or {}
            self.assertIn("commodity-15m", by_bot)
            bot_codes = by_bot.get("commodity-15m") or {}
            self.assertIsInstance(bot_codes, dict)
            self.assertGreaterEqual(sum(int(v) for v in bot_codes.values()), 1)

    def test_firm_sticky_append_card_skip_reasons(self):
        """Firm/sticky brain densify must also feed CARD skip_reasons."""
        src = CMD.read_text(encoding="utf-8")
        firm_idx = src.find("if firm_block:")
        sticky_idx = src.find("if sticky_block:")
        self.assertGreater(firm_idx, 0)
        self.assertGreater(sticky_idx, 0)
        firm_chunk = src[firm_idx:firm_idx + 500]
        sticky_chunk = src[sticky_idx:sticky_idx + 400]
        self.assertIn("skip_reasons.append(str(firm_block))", firm_chunk)
        self.assertIn("skip_reasons.append(str(sticky_block))", sticky_chunk)
        cmd = _load(CMD, "commodity_firm_card_under_test")
        card = cmd._card_sentence(
            buys=0,
            skip_reasons=["firm queue reserved for higher edge"],
        )
        self.assertIn("firm queue", card)
        self.assertNotIn("No paper buy", card)

    def test_daily_r_settle_only_prepends_card_skip(self):
        """Daily-R settle-only must densify CARD ahead of evaluate ask/band noise."""
        for path, label in ((CMD, "cmd"), (BTC, "btc")):
            src = path.read_text(encoding="utf-8")
            idx = src.find("daily_r_blocks(")
            self.assertGreater(idx, 0, label)
            chunk = src[idx:idx + 450]
            self.assertIn("skip_reasons.insert(0, str(r_block))", chunk, label)
        cmd = _load(CMD, "commodity_daily_r_card_under_test")
        card = cmd._card_sentence(
            buys=0,
            skip_reasons=[
                "daily R budget hit for commodity-15m: today $40.02 ≥ 2.0R ($40) — settle-only",
                "ask 0.550 outside band; spread 0.070; depth 0 < 2",
            ],
        )
        self.assertIn("settle-only", card.lower())
        self.assertTrue(card.lower().startswith("daily r") or "settle-only" in card.lower())
        # First skip wins CARD — settle-only must beat ask/band false-friend.
        self.assertNotEqual(card.lower().split(";")[0].strip()[:3], "ask")

    def test_btc_eth_commodity_near_miss_passes_ask(self):
        """#402 persist is a no-op unless callers pass ask — densify entry honesty."""
        btc_src = BTC.read_text(encoding="utf-8")
        self.assertIn('"ask": ev.get("ask")', btc_src)
        self.assertIn('"ask": ev_early.get("ask")', btc_src)
        self.assertIn('"series": "KXBTC15M"', btc_src)
        cmd_src = CMD.read_text(encoding="utf-8")
        self.assertIn('"ask": ev.get("ask")', cmd_src)

    def test_prefetch_book_errs_densify_not_depth_zero(self):
        """Prefetch OB fails densify as orderbook failed — not silent depth 0 (#431 sibling)."""
        src = CMD.read_text(encoding="utf-8")
        self.assertIn("commodity orderbook densify", src)
        self.assertIn("orderbook failed", src)
        # Return signature must surface errs (BTC books, book_errs parity).
        self.assertIn("books, book_errs = prefetch_commodity_books", src)
        self.assertIn("if tick in book_errs:", src)
        prefetch_fn = src.split("def prefetch_commodity_books", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("errs", prefetch_fn)
        self.assertNotIn("raw_ok, _errs", prefetch_fn)
        err_chunk = src.split("if tick in book_errs:", 1)[1].split("else:", 1)[0]
        self.assertIn("commodity orderbook densify", err_chunk)
        self.assertIn("skip_reasons.append", err_chunk)
        self.assertIn("_densify_evaluate_skip", err_chunk)
        self.assertIn("orderbook failed", err_chunk)
        # Runtime: failed fetch → errs map, not (None, 0) book.
        cmd = _load(CMD, "commodity_ob_errs_under_test")

        def _boom(_ticker):
            raise RuntimeError("kalshi 503")

        cmd._fetch_orderbook_raw = _boom
        books, errs = cmd.prefetch_commodity_books([("KXGOLD-OB", "YES", 0.55)])
        self.assertEqual(books, {})
        self.assertIn("KXGOLD-OB", errs)
        self.assertIn("503", str(errs["KXGOLD-OB"]))
        import desk_brain
        import desk_more

        with tempfile.TemporaryDirectory() as tmp:
            cmd.DESK_ROOT = tmp
            cmd._densify_evaluate_skip(
                reasons=[f"orderbook failed ({errs['KXGOLD-OB']})"],
                ticker="KXGOLD-OB",
                side="YES",
                note="commodity orderbook densify",
            )
            journal = desk_brain.load_journal(tmp)
            last = (journal.get("decisions") or [])[-1]
            self.assertEqual(last.get("action"), "skip")
            self.assertEqual(last.get("ticker"), "KXGOLD-OB")
            self.assertIn("orderbook failed", " ".join(last.get("reasons") or []))
            board = desk_more.skip_leaderboard(tmp)
            self.assertIn("commodity-15m", board.get("by_bot") or {})


if __name__ == "__main__":
    unittest.main()
