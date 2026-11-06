"""Tiny web server for the paper-trading dashboard (stdlib only)."""

from __future__ import annotations

import json
import logging
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

log = logging.getLogger(__name__)

DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"


class _Handler(SimpleHTTPRequestHandler):
    data_dir: Path = Path("data")

    def log_message(self, fmt, *args):  # quiet access log
        log.debug(fmt, *args)

    def _json(self, code: int, payload) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        url = urlparse(self.path)
        if url.path == "/api/states":
            names = sorted(p.name[: -len("_state.json")] for p in self.data_dir.glob("*_state.json"))
            return self._json(200, names)
        if url.path == "/api/state":
            name = parse_qs(url.query).get("name", ["paper"])[0]
            if not name.replace("-", "").replace("_", "").isalnum():
                return self._json(400, {"error": "bad name"})
            path = self.data_dir / f"{name}_state.json"
            try:
                raw = path.read_bytes()
            except FileNotFoundError:
                return self._json(404, {"error": f"{path.name} not found - start the bot or run a backtest"})
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("cache-control", "no-store")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return None
        if url.path not in ("/", "/index.html"):
            return self._json(404, {"error": "not found"})
        return super().do_GET()


def make_server(data_dir: str | Path, host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    handler = type("Handler", (_Handler,), {"data_dir": Path(data_dir)})
    return ThreadingHTTPServer((host, port), partial(handler, directory=str(DASHBOARD_DIR)))


def serve(data_dir: str | Path, host: str = "127.0.0.1", port: int = 8000, background: bool = False):
    server = make_server(data_dir, host, port)
    log.info("dashboard on http://%s:%d", host, server.server_address[1])
    if background:
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        return server
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return server
