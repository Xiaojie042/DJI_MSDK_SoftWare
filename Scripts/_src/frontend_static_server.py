"""Tiny static file server used by the Windows release folder."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


class SpaHandler(SimpleHTTPRequestHandler):
    """Serve static files and fall back to index.html for SPA routes."""

    def do_GET(self) -> None:  # noqa: N802 - inherited API
        parsed = urlparse(self.path)
        requested_path = Path(unquote(parsed.path.lstrip("/")))
        local_path = Path(self.directory) / requested_path

        if (
            parsed.path not in {"/", "/index.html"}
            and not local_path.exists()
            and "." not in requested_path.name
        ):
            self.path = "/index.html"

        super().do_GET()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a built frontend directory.")
    parser.add_argument("--root", required=True, help="Directory that contains built frontend files.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=3000, help="Bind port. Default: 3000")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"Frontend root not found: {root}")

    handler = partial(SpaHandler, directory=str(root))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving frontend from {root} on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
