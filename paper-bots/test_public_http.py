"""Public reads wait and retry on 429 instead of skipping the check."""
from __future__ import annotations

import io
import unittest
import urllib.error
from unittest import mock

import public_http
import shadow_missing


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http(code, retry_after=None):
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else {}
    return urllib.error.HTTPError("u", code, "x", headers, None)


class PublicHttpTests(unittest.TestCase):
    def _run(self, effects, **kw):
        waits = []
        with mock.patch.object(public_http.urllib.request, "urlopen", side_effect=effects) as op:
            out = public_http.read("https://x", sleep=waits.append, **kw)
        return out, waits, op.call_count

    def test_429_waits_and_retries(self):
        out, waits, calls = self._run([_http(429), _http(429), _Resp(b"ok")])
        self.assertEqual(out, b"ok")
        self.assertEqual(waits, [1, 2])
        self.assertEqual(calls, 3)

    def test_retry_after_header_is_honored(self):
        _out, waits, _calls = self._run([_http(429, 5), _Resp(b"ok")])
        self.assertEqual(waits, [5.0])

    def test_server_error_and_timeout_retry(self):
        out, _w, calls = self._run([_http(503), TimeoutError(), _Resp(b"ok")])
        self.assertEqual((out, calls), (b"ok", 3))

    def test_404_is_not_retried(self):
        with self.assertRaises(urllib.error.HTTPError):
            self._run([_http(404), _Resp(b"ok")])

    def test_gives_up_after_the_tries(self):
        with self.assertRaises(urllib.error.HTTPError):
            self._run([_http(429)] * 4, tries=4)

    def test_asks_for_gzip_and_unpacks_it(self):
        import gzip
        packed = _Resp(gzip.compress(b'[{"slug": "nba"}]'))
        packed.headers = {"Content-Encoding": "gzip"}
        with mock.patch.object(public_http.urllib.request, "urlopen", side_effect=[packed]) as op:
            out = public_http.read("https://gamma-api.polymarket.com/events?limit=500", sleep=lambda s: None)
        self.assertEqual(out, b'[{"slug": "nba"}]')
        req = op.call_args[0][0]
        self.assertEqual(req.get_header("Accept-encoding"), "gzip")
        self.assertIn("User-agent", req.headers)

    def test_plain_and_zip_bodies_are_left_alone(self):
        plain = _Resp(b"Date,10 Yr")
        plain.headers = {"Content-Type": "text/csv"}
        xlsx = _Resp(b"PK\x03\x04 zip body")
        xlsx.headers = {}
        with mock.patch.object(public_http.urllib.request, "urlopen", side_effect=[plain, xlsx]):
            self.assertEqual(public_http.read("https://x", sleep=lambda s: None), b"Date,10 Yr")
            self.assertEqual(public_http.read("https://y", sleep=lambda s: None), b"PK\x03\x04 zip body")

    def test_caller_headers_keep_their_own_encoding(self):
        with mock.patch.object(public_http.urllib.request, "urlopen", side_effect=[_Resp(b"ok")]) as op:
            public_http.read("https://x", headers={"User-Agent": "u", "Accept-Encoding": "identity"},
                             sleep=lambda s: None)
        self.assertEqual(op.call_args[0][0].get_header("Accept-encoding"), "identity")

    def test_research_tower_reads_through_a_429(self):
        body = b'{"markets": [{"ticker": "KXNFLTOTAL-A", "yes_bid_dollars": "0.40", "yes_ask_dollars": "0.45"}]}'
        effects = [_http(429), _Resp(body)]
        with mock.patch.object(public_http.urllib.request, "urlopen", side_effect=effects), \
                mock.patch.object(public_http.time, "sleep"):
            rows = shadow_missing._kalshi_markets("KXNFLTOTAL", None)
        self.assertEqual(rows[0]["ticker"], "KXNFLTOTAL-A")


if __name__ == "__main__":
    unittest.main()
