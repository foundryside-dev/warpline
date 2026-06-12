from __future__ import annotations

import argparse
import json
from pathlib import Path

from heddle import __version__, commands


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="heddle")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    sub = parser.add_subparsers(dest="command")

    changed_parser = sub.add_parser("changed")
    changed_parser.add_argument("--repo", type=Path, default=Path("."))
    changed_parser.add_argument("--rev-range")
    changed_parser.add_argument("--json", action="store_true")

    timeline_parser = sub.add_parser("timeline")
    timeline_parser.add_argument("--repo", type=Path, default=Path("."))
    timeline_parser.add_argument("--entity", required=True)
    timeline_parser.add_argument("--json", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"heddle {__version__}")
        return 0
    if args.command == "changed":
        payload = commands.changed(args.repo, args.rev_range)
        print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
        return 0
    if args.command == "timeline":
        payload = commands.timeline(args.repo, args.entity)
        print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
