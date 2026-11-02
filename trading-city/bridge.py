#!/usr/bin/env python3
"""Localhost-only read bridge for APEX-CITY.

Serves GET /api/pimp-trading.json from paper-bots.pimp_desk.snapshot() only.
Binds to 127.0.0.1 so live paper state is not exposed on the LAN.
Never re-parses bot files in the front-end — this is the thin desk path for local/dev.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper-bots"
sys.path.insert(0, str(PAPER))

import pimp_desk  # noqa: E402


def _snapshot(query: dict[str, list[str]]) -> dict:
    q = (query.get("q") or [""])[0]
    filt = (query.get("filter") or ["all"])[0]
    try:
        page = int((query.get("page") or ["1"])[0])
    except (TypeError, ValueError):
        page = 1
    return pimp_desk.snapshot(str(PAPER), q=q, filt=filt, page=page)


class Handler(BaseHTTPRequestHandler):
    server_version = "TradingCityBridge/0.1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _cors(self) -> None:
        origin = self.headers.get("Origin") or ""
        if origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost"):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path not in ("/api/pimp-trading.json", "/health"):
            self.send_response(404)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":false,"error":"not found"}')
            return

        if path == "/health":
            body = b'{"ok":true,"source":"pimp_desk.snapshot"}'
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        try:
            snap = _snapshot(parse_qs(parsed.query))
            payload = json.dumps(snap, default=str).encode("utf-8")
        except Exception as exc:  # noqa: BLE001 — surface desk failures to the city UI
            err = json.dumps({"ok": False, "error": f"snapshot failed: {exc}"}).encode("utf-8")
            self.send_response(500)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)
            return

        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Localhost bridge for APEX-CITY snapshot")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Bind port (default 8765)")
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        sys.stderr.write("Refusing non-localhost bind — live paper desk must stay private.\n")
        sys.exit(2)
    os.chdir(ROOT)
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    sys.stderr.write(
        f"APEX-CITY bridge on http://{args.host}:{args.port}/api/pimp-trading.json\n"
        f"  source: pimp_desk.snapshot({PAPER})\n"
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\nbye\n")


if __name__ == "__main__":
    main()
