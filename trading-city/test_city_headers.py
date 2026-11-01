"""Header policy that was leaving SIGNAL-CITY a blank page.

Loads pimp_city_csp / dash_secure from bot.py without importing discord.
"""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Headers(dict):
    def __contains__(self, key):
        return any(k.lower() == key.lower() for k in self.keys())

    def __delitem__(self, key):
        for k in list(self.keys()):
            if k.lower() == key.lower():
                super().__delitem__(k)
                return
        raise KeyError(key)

    def __setitem__(self, key, value):
        for k in list(self.keys()):
            if k.lower() == key.lower() and k != key:
                super().__delitem__(k)
        super().__setitem__(key, value)


class Resp:
    def __init__(self, headers=None):
        self.headers = Headers(headers or {})


def _load():
    src = (ROOT / "bot.py").read_text()
    tree = ast.parse(src)
    want = {"pimp_city_csp", "_pimp_city_path", "dash_secure"}
    parts = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in want:
            parts.append(ast.get_source_segment(src, node))
    ns = {}
    exec("\n\n".join(parts), ns)
    return ns


def test_city_csp_allows_the_bundle_and_framing():
    ns = _load()
    csp = ns["pimp_city_csp"]()
    assert "script-src 'self'" in csp
    assert "style-src 'self'" in csp
    assert "frame-ancestors *" in csp
    assert "default-src 'none'" not in csp
    assert "frame-ancestors 'none'" not in csp


def test_city_response_is_frameable_and_executable():
    ns = _load()
    resp = Resp()
    ns["dash_secure"](resp, "/signal-city/")
    h = resp.headers
    assert "X-Frame-Options" not in h
    assert "frame-ancestors *" in h["Content-Security-Policy"]
    assert "script-src 'self'" in h["Content-Security-Policy"]
    assert h["Cross-Origin-Resource-Policy"] == "cross-origin"
    assert "storage-access=(self)" in h["Permissions-Policy"]


def test_city_policy_covers_assets_and_not_the_rest_of_the_dashboard():
    ns = _load()
    asset = Resp()
    ns["dash_secure"](asset, "/signal-city/assets/index.js")
    assert "X-Frame-Options" not in asset.headers
    assert "script-src 'self'" in asset.headers["Content-Security-Policy"]

    legacy = Resp()
    ns["dash_secure"](legacy, "/pimp-city/")
    assert "X-Frame-Options" not in legacy.headers
    assert "script-src 'self'" in legacy.headers["Content-Security-Policy"]

    other = Resp()
    ns["dash_secure"](other, "/staff")
    assert other.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in other.headers["Content-Security-Policy"]
    assert other.headers["Cross-Origin-Resource-Policy"] == "same-origin"


def test_shell_is_served_without_a_staff_cookie():
    src = (ROOT / "bot.py").read_text()
    start = src.index("async def dash_pimp_city")
    end = src.index("async def dash_api_pimp")
    body = src[start:end]
    assert "staff_uid_from_request" not in body
    assert "Live trades stay staff-only" in body


def test_path_matcher_covers_signal_and_legacy():
    ns = _load()
    fn = ns["_pimp_city_path"]
    assert fn("/signal-city/")
    assert fn("/signal-city/assets/x.js")
    assert fn("/pimp-city/")
    assert not fn("/staff")


if __name__ == "__main__":
    test_city_csp_allows_the_bundle_and_framing()
    test_city_response_is_frameable_and_executable()
    test_city_policy_covers_assets_and_not_the_rest_of_the_dashboard()
    test_shell_is_served_without_a_staff_cookie()
    test_path_matcher_covers_signal_and_legacy()
    print("ok")
