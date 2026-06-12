from __future__ import annotations

import argparse
import json
from pathlib import Path

from heddle import __version__, commands
from heddle.git import backfill, ingest_commit
from heddle.install import install_hook
from heddle.loomweave import LoomweaveProbe
from heddle.store import HeddleStore, default_store_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="heddle")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init")
    init.add_argument("--repo", type=Path, default=Path("."))

    backfill_parser = sub.add_parser("backfill")
    backfill_parser.add_argument("--repo", type=Path, default=Path("."))
    backfill_parser.add_argument("--json", action="store_true")

    ingest = sub.add_parser("ingest-commit")
    ingest.add_argument("sha")
    ingest.add_argument("--repo", type=Path, default=Path("."))

    loomweave_probe = sub.add_parser("loomweave-probe")
    loomweave_probe.add_argument("--repo", type=Path, default=Path("."))
    loomweave_probe.add_argument("--command", dest="loomweave_command", default="loomweave")
    loomweave_probe.add_argument("--json", action="store_true")

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
    if args.command == "init":
        hook = install_hook(args.repo)
        print(str(hook))
        return 0
    if args.command == "backfill":
        with HeddleStore.open(default_store_path(args.repo)) as store:
            report = backfill(store, args.repo)
        print(json.dumps(report, sort_keys=True) if args.json else report)
        return 0
    if args.command == "ingest-commit":
        try:
            with HeddleStore.open(default_store_path(args.repo)) as store:
                ingest_commit(store, args.repo, args.sha)
        except Exception as exc:  # fail-soft hook contract
            with HeddleStore.open(default_store_path(args.repo)) as store:
                store.log_health(args.repo, "HOOK_INGEST_FAILED", str(exc))
        return 0
    if args.command == "loomweave-probe":
        payload = LoomweaveProbe(repo=args.repo, command=args.loomweave_command).probe()
        print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
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
