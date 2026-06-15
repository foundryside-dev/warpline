from __future__ import annotations

import argparse
import json
from pathlib import Path

from warpline import __version__, commands, install_support
from warpline.dogfood import DEFAULT_DOGFOOD_RESULTS, REAL_MEMBER_REPO, run_dogfood_evaluator
from warpline.git import backfill, ingest_commit
from warpline.install import install_hook
from warpline.loomweave import LoomweaveMcpClient, LoomweaveProbe, ToolClient
from warpline.mcp_smoke import run_mcp_smoke
from warpline.productization import read_productization_decision
from warpline.reresolve import sweep_reresolve_sei
from warpline.store import WarplineStore, default_store_path

# install/doctor component flags -> component keys
_INSTALL_FLAGS = {
    "claude_code": "claude-code",
    "codex": "codex",
    "claude_md": "claude_md",
    "agents_md": "agents_md",
    "gitignore": "gitignore",
    "hooks": "hooks",
    "session_hook": "session-hook",
    "skills": "skills",
    "codex_skills": "codex-skills",
    "config": "config",
}


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


def _co_change_payload(
    repo: Path,
    *,
    sei: str | None,
    locator: str | None,
    entity_key_id: int | None,
    min_count: int,
) -> dict[str, object]:
    """Compose the ``co-change`` read surface (NON-FROZEN/internal Track A).

    Resolves the requested entity to a warpline-local ``entity_key_id`` (by
    explicit id, SEI, or locator), then lists its co-change partners. Each
    partner carries an honest ``enrichment.sei`` state per the closed vocab:
    ``present`` when the partner's SEI resolved, ``absent`` when it is still NULL
    (``sei:null`` — minted before loomweave resolved it). The graph is keyed on
    warpline-local ids; the SEI is joined, never minted.
    """

    from warpline.coupling import classify_confidence

    with WarplineStore.open(default_store_path(repo)) as store:
        key_id: int | None = entity_key_id
        if key_id is None:
            if sei is not None:
                row = store.resolve_ref(repo, "sei", sei)
            elif locator is not None:
                row = store.resolve_ref(repo, "locator", locator)
            else:
                return {
                    "schema": "warpline.coupling.partners.v1",
                    "error": "one of --sei / --locator / --entity-key-id is required",
                    "partners": [],
                }
            if row is None:
                return {
                    "schema": "warpline.coupling.partners.v1",
                    "error": "entity not found",
                    "partners": [],
                }
            key_id = int(str(row["id"]))
        partners = store.co_change_partners(repo, key_id, min_count=min_count)

    enriched: list[dict[str, object]] = []
    for partner in partners:
        partner_sei = partner.get("sei")
        co_count = partner["co_change_count"]
        assert isinstance(co_count, int)
        enriched.append(
            {
                **partner,
                "confidence": classify_confidence(co_count),
                "enrichment": {"sei": "present" if partner_sei is not None else "absent"},
            }
        )
    return {
        "schema": "warpline.coupling.partners.v1",
        "entity_key_id": key_id,
        "partners": enriched,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="warpline")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init")
    init.add_argument("--repo", type=Path, default=Path("."))

    install_parser = sub.add_parser(
        "install", help="Install warpline MCP bindings, hooks, skills, and config."
    )
    install_parser.add_argument("--repo", type=Path, default=Path("."))
    install_parser.add_argument("--claude-code", action="store_true", help="Claude Code MCP only")
    install_parser.add_argument("--codex", action="store_true", help="Codex MCP only")
    install_parser.add_argument("--claude-md", action="store_true", help="CLAUDE.md block only")
    install_parser.add_argument("--agents-md", action="store_true", help="AGENTS.md block only")
    install_parser.add_argument("--gitignore", action="store_true", help="gitignore only")
    install_parser.add_argument("--hooks", action="store_true", help="git post-commit hook only")
    install_parser.add_argument(
        "--session-hook", action="store_true", help="SessionStart hook only"
    )
    install_parser.add_argument("--skills", action="store_true", help="Claude Code skill only")
    install_parser.add_argument("--codex-skills", action="store_true", help="Codex skill only")
    install_parser.add_argument("--config", action="store_true", help=".weft/warpline config only")
    install_parser.add_argument("--json", action="store_true")

    doctor_parser = sub.add_parser(
        "doctor", help="Verify the warpline installation; --fix autofixes."
    )
    doctor_parser.add_argument("--repo", type=Path, default=Path("."))
    doctor_parser.add_argument("--fix", action="store_true", help="autofix anything fixable")
    doctor_parser.add_argument("--json", action="store_true")

    session_parser = sub.add_parser("session-context")
    session_parser.add_argument("--repo", type=Path, default=Path("."))

    backfill_parser = sub.add_parser("backfill")
    backfill_parser.add_argument("--repo", type=Path, default=Path("."))
    # HX1: SEI resolution is ON by default; degrades cleanly when loomweave is
    # absent. Pass --no-resolve-sei to skip the loomweave probe entirely.
    backfill_parser.add_argument(
        "--resolve-sei", action=argparse.BooleanOptionalAction, default=True
    )
    backfill_parser.add_argument("--loomweave-command", default="loomweave")
    backfill_parser.add_argument("--json", action="store_true")

    ingest = sub.add_parser("ingest-commit")
    ingest.add_argument("sha")
    ingest.add_argument("--repo", type=Path, default=Path("."))
    ingest.add_argument(
        "--resolve-sei", action=argparse.BooleanOptionalAction, default=True
    )
    ingest.add_argument("--loomweave-command", default="loomweave")

    # NON-FROZEN/internal verb (Rung 1c). Not one of the six frozen v1 MCP
    # tools; the self-healing SEI re-resolution sweep, exposed for the hook and
    # for `doctor --fix`.
    reresolve_parser = sub.add_parser(
        "reresolve-sei",
        help="Re-resolve null-sei entity keys via loomweave (self-healing sweep).",
    )
    reresolve_parser.add_argument("--repo", type=Path, default=Path("."))
    reresolve_parser.add_argument("--limit", type=int, default=200)
    reresolve_parser.add_argument(
        "--resolve-sei", action=argparse.BooleanOptionalAction, default=True
    )
    reresolve_parser.add_argument("--loomweave-command", default="loomweave")
    reresolve_parser.add_argument("--json", action="store_true")

    # NON-FROZEN/internal verbs (Rung 2 Track A). Neither is one of the six
    # frozen v1 MCP tools; both are read-only advisory surfaces over the
    # warpline-owned co-change graph.
    rebuild_coupling = sub.add_parser(
        "rebuild-coupling",
        help="Rebuild the co-change coupling graph from change_events (idempotent).",
    )
    rebuild_coupling.add_argument("--repo", type=Path, default=Path("."))
    rebuild_coupling.add_argument("--json", action="store_true")

    co_change = sub.add_parser(
        "co-change",
        help="List temporal co-change partners of an entity (read-only advisory).",
    )
    co_change.add_argument("--repo", type=Path, default=Path("."))
    co_change.add_argument("--sei")
    co_change.add_argument("--locator")
    co_change.add_argument("--entity-key-id", type=int)
    co_change.add_argument("--min-count", type=int, default=2)
    co_change.add_argument("--json", action="store_true")

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

    churn_parser = sub.add_parser("churn")
    churn_parser.add_argument("--repo", type=Path, default=Path("."))
    churn_parser.add_argument("--sei", action="append", default=[])
    churn_parser.add_argument("--locator", action="append", default=[])
    churn_parser.add_argument("--json", action="store_true")

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
    dogfood_parser.add_argument("--real-member-repo", type=Path, default=REAL_MEMBER_REPO)
    dogfood_parser.add_argument("--skip-real-member", action="store_true")
    dogfood_parser.add_argument("--json", action="store_true")

    mcp_smoke = sub.add_parser("mcp-smoke")
    mcp_smoke.add_argument("--repo", type=Path, default=Path("."))
    mcp_smoke.add_argument("--no-bad-input", action="store_true")
    mcp_smoke.add_argument("--json", action="store_true")

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
        print(f"warpline {__version__}")
        return 0
    if args.command == "init":
        hook = install_hook(args.repo)
        print(str(hook))
        return 0
    if args.command == "install":
        selected = {key for attr, key in _INSTALL_FLAGS.items() if getattr(args, attr, False)}
        install_report = install_support.run_install(args.repo, selected or None)
        if args.json:
            print(
                json.dumps(
                    {
                        "schema": "warpline.install.v1",
                        "ok": install_report.ok,
                        "actions": [
                            {"component": n, "detail": d} for n, d in install_report.actions
                        ],
                        "errors": [
                            {"component": n, "detail": d} for n, d in install_report.errors
                        ],
                    },
                    sort_keys=True,
                )
            )
        else:
            for name, detail in install_report.actions:
                print(f"  ✓ {name}: {detail}")
            for name, detail in install_report.errors:
                print(f"  !! {name}: {detail}")
        return 0 if install_report.ok else 1
    if args.command == "doctor":
        doctor_report = install_support.run_doctor(args.repo, fix=args.fix)
        if args.json:
            print(json.dumps(install_support.doctor_summary(doctor_report), sort_keys=True))
        else:
            for result in doctor_report.results:
                print(f"  {'✓' if result.ok else '!!'} {result.name}: {result.detail}")
            for name, detail in doctor_report.fixed:
                print(f"  → fixed {name}: {detail}")
        return 0 if doctor_report.ok else 1
    if args.command == "session-context":
        print(commands.session_context(args.repo))
        return 0
    if args.command == "backfill":
        sei_client, sei_resolution = _optional_sei_client(
            args.repo,
            enabled=args.resolve_sei,
            command=args.loomweave_command,
        )
        with WarplineStore.open(default_store_path(args.repo)) as store:
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
            with WarplineStore.open(default_store_path(args.repo)) as store:
                ingest_commit(store, args.repo, args.sha, sei_client=sei_client)
        except Exception as exc:  # fail-soft hook contract
            with WarplineStore.open(default_store_path(args.repo)) as store:
                store.log_health(args.repo, "HOOK_INGEST_FAILED", str(exc))
        return 0
    if args.command == "reresolve-sei":
        try:
            sei_client, sei_resolution = _optional_sei_client(
                args.repo,
                enabled=args.resolve_sei,
                command=args.loomweave_command,
            )
            with WarplineStore.open(default_store_path(args.repo)) as store:
                report = sweep_reresolve_sei(
                    store, args.repo, sei_client, limit=args.limit
                )
        except Exception as exc:  # fail-soft: hook + doctor contract
            with WarplineStore.open(default_store_path(args.repo)) as store:
                store.log_health(args.repo, "RERESOLVE_FAILED", str(exc))
            report = {"error": str(exc), "loomweave": "unavailable"}
        else:
            if sei_resolution is not None:
                report["sei_resolution"] = sei_resolution
        print(json.dumps(report, sort_keys=True) if args.json else report)
        return 0
        payload = LoomweaveProbe(repo=args.repo, command=args.loomweave_command).probe()
        print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
        return 0
    if args.command == "rebuild-coupling":
        with WarplineStore.open(default_store_path(args.repo)) as store:
            report = store.rebuild_co_change_pairs(args.repo)
        out: dict[str, object] = {"schema": "warpline.coupling.rebuild.v1", **report}
        print(json.dumps(out, sort_keys=True) if args.json else json.dumps(out, indent=2))
        return 0
    if args.command == "co-change":
        payload = _co_change_payload(
            args.repo,
            sei=args.sei,
            locator=args.locator,
            entity_key_id=args.entity_key_id,
            min_count=args.min_count,
        )
        print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
        return 0
    if args.command == "changed":
        payload = commands.change_list(args.repo, args.rev_range)
        print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
        return 0
    if args.command == "timeline":
        payload = commands.entity_timeline(args.repo, args.entity)
        print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
        return 0
    if args.command == "churn":
        refs = [{"kind": "sei", "value": s} for s in args.sei]
        refs += [{"kind": "locator", "value": loc} for loc in args.locator]
        payload = commands.entity_churn_count(args.repo, refs)
        print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
        return 0
    if args.command == "blast-radius":
        payload = commands.impact_radius(args.repo, args.changed_entity_key_id, args.depth)
        print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
        return 0
    if args.command == "reverify":
        payload = commands.reverify_worklist(args.repo, args.changed_entity_key_id, args.depth)
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
        payload = run_dogfood_evaluator(
            output_path=args.output,
            work_dir=args.work_dir,
            real_member_repo=None if args.skip_real_member else args.real_member_repo,
            require_real_member=not args.skip_real_member,
        )
        print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
        return 0 if payload["ready"] else 2
    if args.command == "mcp-smoke":
        payload = run_mcp_smoke(args.repo, include_bad_input=not args.no_bad_input)
        print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
        return 0 if payload["ok"] else 2
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
