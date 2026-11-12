"""Local production-like server for the atlas and owner route API.

Set WATERMAP_OWNER_TOKEN before starting to enable editing. Secrets are never
stored in project files.
"""
from __future__ import annotations

import json
import os
import re
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from tools.owner_route_store import RouteStore, Unauthorized

ROOT = Path(__file__).parent
WEB = ROOT / "apps" / "web"
STORE = RouteStore(ROOT / "runtime" / "owner-routes.json", os.environ.get("WATERMAP_OWNER_TOKEN"))
MAX_BODY_BYTES = 1_000_000
ROUTE_ACTION = re.compile(r"^/api/routes/([^/]+)/(history|revert)$")


class AtlasHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def end_headers(self):
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob: https://server.arcgisonline.com https://*.arcgisonline.com https://tile.openstreetmap.org; "
            "connect-src 'self' https://server.arcgisonline.com https://*.arcgisonline.com https://tile.openstreetmap.org; "
            "worker-src 'self' blob:; child-src blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _json(self, status: int, payload: object):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _token(self):
        value = self.headers.get("Authorization", "")
        return value.removeprefix("Bearer ").strip() or None

    def _route_action(self, path: str):
        match = ROUTE_ACTION.fullmatch(path)
        return (unquote(match.group(1)), match.group(2)) if match else (None, None)

    def _read_json_body(self):
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("Content-Length is required")
        try:
            length = int(raw_length)
        except ValueError as error:
            raise ValueError("invalid Content-Length") from error
        if length < 0:
            raise ValueError("invalid Content-Length")
        if length > MAX_BODY_BYTES:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "request body too large"})
            return None
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/routes":
                return self._json(HTTPStatus.OK, {"routes": STORE.latest(), "editing_enabled": bool(STORE.owner_token)})
            if path == "/api/owner/session":
                STORE.authorize(self._token())
                return self._json(HTTPStatus.OK, {"authenticated": True})
            project_id, action = self._route_action(path)
            if action == "history":
                STORE.authorize(self._token())
                return self._json(HTTPStatus.OK, {"history": STORE.history(project_id)})
            return super().do_GET()
        except Unauthorized as error:
            return self._json(HTTPStatus.UNAUTHORIZED, {"error": str(error)})
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            project_id, action = self._route_action(path)
            if path != "/api/routes" and action != "revert":
                return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            STORE.authorize(self._token())
            payload = self._read_json_body()
            if payload is None:
                return None
            if path == "/api/routes":
                return self._json(HTTPStatus.CREATED, STORE.save(self._token(), payload))
            return self._json(HTTPStatus.CREATED, STORE.revert(self._token(), project_id, payload["version"]))
        except Unauthorized as error:
            return self._json(HTTPStatus.UNAUTHORIZED, {"error": str(error)})
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})


def main():
    host = os.environ.get("WATERMAP_HOST", "127.0.0.1")
    port = int(os.environ.get("WATERMAP_PORT", "8767"))
    print(f"Telangana WaterMap: http://{host}:{port}")
    print("Owner editing:", "enabled" if STORE.owner_token else "disabled (set WATERMAP_OWNER_TOKEN)")
    ThreadingHTTPServer((host, port), AtlasHandler).serve_forever()


if __name__ == "__main__":
    main()
