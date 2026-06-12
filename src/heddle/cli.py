from __future__ import annotations

import argparse
import json
from pathlib import Path

from heddle import __version__, commands
from heddle.dogfood import DEFAULT_DOGFOOD_RESULTS, run_dogfood_evaluator
from heddle.git import backfill, ingest_commit
from heddle.install import install_hook
from heddle.loomweave import LoomweaveMcpClient, LoomweaveProbe, ToolClient
from heddle.productization import read_productization_decision
from heddle.store import HeddleStore, default_store_path


def _optional_sei_client(
    repo: Path,
    *,
    enabled: bool,
    command: str,
) -> tuple[ToolClient | None, dict[str, object] | None]:
    if not enabled:
        return None, None
    probe = LoomweaveProbe(repo=repo, command=command).probe()
    resolution = {
        "status": probe.get("status"),
        "reason": probe.get("reason"),
    }
    if probe.get("status") != "available":
        return None, resolution
    return LoomweaveMcpClient(repo=repo, command=command), {
        "status": "available",
        "version": probe.get("version"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="heddle")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init")
    init.add_argument("--repo", type=Path, default=Path("."))

    backfill_parser = sub.add_parser("backfill")
    backfill_parser.add_argument("--repo", type=Path, default=Path("."))
    backfill_parser.add_argument("--resolve-sei", action="store_true")
    backfill_parser.add_argument("--loomweave-command", default="loomweave")
    backfill_parser.add_argument("--json", action="store_true")

    ingest = sub.add_parser("ingest-commit")
    ingest.add_argument("sha")
    ingest.add_argument("--repo", type=Path, default=Path("."))
    ingest.add_argument("--resolve-sei", action="store_true")
    ingest.add_argument("--loomweave-command", default="loomweave")

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

    blast_parser = sub.add_parser("blast-radius")
    blast_parser.add_argument("--repo", type=Path, default=Path("."))
    blast_parser.add_argument("--changed-entity-key-id", type=int, action="append", required=True)
    blast_parser.add_argument("--depth", type=int, default=2)
    blast_parser.add_argument("--json", action="store_true")

    reverify_parser = sub.add_parser("reverify")
    reverify_parser.add_argument("--repo", type=Path, default=Path("."))
    reverify_parser.add_argument(
        "--changed-entity-key-id",
        type=int,
        action="append",
        required=True,
    )
    reverify_parser.add_argument("--depth", type=int, default=2)
    reverify_parser.add_argument("--json", action="store_true")

    capture_snapshot_parser = sub.add_parser("capture-snapshot")
    capture_snapshot_parser.add_argument("--repo", type=Path, default=Path("."))
    capture_snapshot_parser.add_argument("--commit")
    capture_snapshot_parser.add_argument("--loomweave-command", default="loomweave")
    capture_snapshot_parser.add_argument("--json", action="store_true")

    dogfood_parser = sub.add_parser("dogfood-eval")
    dogfood_parser.add_argument("--output", type=Path, default=DEFAULT_DOGFOOD_RESULTS)
    dogfood_parser.add_argument("--work-dir", type=Path)
    dogfood_parser.add_argument("--json", action="store_true")

    productization_parser = sub.add_parser("productization-gate")
    productization_parser.add_argument("--report", default="spike/REPORT.md")
    productization_parser.add_argument(
        "--dogfood-results",
        type=Path,
        default=DEFAULT_DOGFOOD_RESULTS,
    )

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
        sei_client, sei_resolution = _optional_sei_client(
            args.repo,
            enabled=args.resolve_sei,
            command=args.loomweave_command,
        )
        with HeddleStore.open(default_store_path(args.repo)) as store:
            report = backfill(store, args.repo, sei_client=sei_client)
        if sei_resolution is not None:
            report["sei_resolution"] = sei_resolution
        print(json.dumps(report, sort_keys=True) if args.json else report)
        return 0
    if args.command == "ingest-commit":
        try:
            sei_client, _sei_resolution = _optional_sei_client(
                args.repo,
                enabled=args.resolve_sei,
                command=args.loomweave_command,
            )
            with HeddleStore.open(default_store_path(args.repo)) as store:
                ingest_commit(store, args.repo, args.sha, sei_client=sei_client)
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
    if args.command == "blast-radius":
        payload = commands.blast_radius(args.repo, args.changed_entity_key_id, args.depth)
        print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
        return 0
    if args.command == "reverify":
        payload = commands.reverify(args.repo, args.changed_entity_key_id, args.depth)
        print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
        return 0
    if args.command == "capture-snapshot":
        payload = commands.capture_snapshot(
            args.repo,
            commit=args.commit,
            loomweave_command=args.loomweave_command,
        )
        print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
        return 0
    if args.command == "dogfood-eval":
        payload = run_dogfood_evaluator(output_path=args.output, work_dir=args.work_dir)
        print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
        return 0 if payload["ready"] else 2
    if args.command == "productization-gate":
        decision = read_productization_decision(
            Path(args.report),
            dogfood_results_path=args.dogfood_results,
        )
        payload = {
            "allowed": decision.allowed,
            "recommendation": decision.recommendation,
            "reason": decision.reason,
        }
        print(json.dumps(payload, sort_keys=True))
        return 0 if decision.allowed else 2
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
