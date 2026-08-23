"""Serve the games directory over HTTP.

The evaluator accepts a URL, so a candidate can be scored where it is actually
deployed. This is the smallest way to get that path exercised locally and in a
cloud VM: `python scripts/serve.py --port 8000` then
`orbit evaluate http://127.0.0.1:8000/orbit/index.html`.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "games"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--bind", default="0.0.0.0")
    args = parser.parse_args()

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(args.root)
    )
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((args.bind, args.port), handler) as server:
        print(f"serving {args.root} at http://{args.bind}:{args.port}/orbit/index.html")
        server.serve_forever()


if __name__ == "__main__":
    main()
