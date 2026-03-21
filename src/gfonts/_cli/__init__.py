"""CLI entry points for gfonts."""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(prog="gfonts", description="Google Fonts toolkit")
    sub = parser.add_subparsers(dest="command")

    curate_p = sub.add_parser("curate", help="Launch the font curation UI")
    curate_p.add_argument("--port", type=int, default=8250, help="Port (default 8250)")
    curate_p.add_argument("--no-open", action="store_true", help="Don't auto-open browser")
    curate_p.add_argument("--data-dir", type=str, default=None, help="Custom data directory")

    args = parser.parse_args()

    if args.command == "curate":
        from gfonts._cli.curate import run_curate_server

        run_curate_server(port=args.port, no_open=args.no_open, data_dir=args.data_dir)
    else:
        parser.print_help()
        sys.exit(1)
