"""Multi-ex disagree + funding scout insight digests (observe-only)."""
from __future__ import annotations

import json
import tempfile
import unittest

import desk_living
from helpers import funding_scout, multi_ex_disagree


class MultiExFundingDigests(unittest.TestCase):
    def test_multi_ex_disagree_stats_and_alert(self):
        calm = multi_ex_disagree.disagree_stats({
            "coinbase": 100.0, "kraken": 100.05, "bitstamp": 99.98,
        })
        self.assertEqual(calm["n"], 3)
        self.assertFalse(calm["alert"])
        hot = multi_ex_disagree.disagree_stats({
            "coinbase": 100.0, "kraken": 100.30,
        })
        self.assertTrue(hot["alert"])
        self.assertGreaterEqual(hot["range_bps"], 15.0)
        thin = multi_ex_disagree.disagree_stats({"coinbase": 100.0})
        self.assertEqual(thin["n"], 1)
        self.assertFalse(thin["alert"])
        digest = multi_ex_disagree.build_digest({
            "coinbase": 100.0, "kraken": None, "bitstamp": 100.02,
        })
        self.assertEqual(digest["helper"], "multi_ex_disagree")
        self.assertFalse(digest["may_place_alone"])
        self.assertEqual(digest["present_n"], 2)
        self.assertIsNone(digest["marks"]["kraken"])

    def test_multi_ex_write_with_opener(self):
        def opener(url: str):
            if "coinbase" in url:
                return json.dumps({"price": "100.0"}).encode()
            if "kraken" in url:
                return json.dumps({
                    "result": {"XXBTZUSD": {"c": ["100.20", "1"]}},
                }).encode()
            if "bitstamp" in url:
                return json.dumps({"last": "99.90"}).encode()
            if "deribit" in url:
                return json.dumps({"result": {"index_price": 100.05}}).encode()
            return b"{}"

        with tempfile.TemporaryDirectory() as tmp:
            out = multi_ex_disagree.write_digest_from_desk(tmp, opener=opener)
            self.assertEqual(out["present_n"], 4)
            chip = desk_living.multi_ex_disagree_chip(tmp)
            self.assertIn("multi-ex", chip["label"])

    def test_funding_scout_hot_and_waiting(self):
        waiting = funding_scout.build_digest({})
        self.assertTrue(waiting["waiting"])
        self.assertFalse(waiting["may_place_alone"])
        self.assertFalse(waiting["opens_desk_cash"])
        hot = funding_scout.build_digest({
            "instrument": "BTC-PERPETUAL",
            "mark_price": 75000.0,
            "funding_8h": 0.0005,
            "current_funding": 0.0004,
        })
        self.assertTrue(hot["hot"])
        self.assertEqual(hot["funding_8h"], 0.0005)

    def test_funding_scout_write_opener(self):
        def opener(_url: str):
            return json.dumps({
                "result": [{
                    "instrument_name": "BTC-PERPETUAL",
                    "mark_price": 75100.0,
                    "funding_8h": 0.0001,
                    "current_funding": 0.00012,
                    "open_interest": 1e6,
                }],
            }).encode()

        with tempfile.TemporaryDirectory() as tmp:
            out = funding_scout.write_digest_from_desk(tmp, opener=opener)
            self.assertEqual(out["instrument"], "BTC-PERPETUAL")
            self.assertFalse(out["hot"])
            chip = desk_living.funding_scout_chip(tmp)
            self.assertIn("funding scout", chip["label"])

    def test_inventory_lists_helpers(self):
        self.assertIn("multi_ex_disagree_digest.json", desk_living.INSIGHT_HELPER_DIGESTS)
        self.assertIn("funding_scout_digest.json", desk_living.INSIGHT_HELPER_DIGESTS)


if __name__ == "__main__":
    unittest.main()
