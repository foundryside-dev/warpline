"""The published reverify-worklist contract artifact (federation D1).

These tests are warpline's half of the drift-checkable seam with wardline:

  * the artifact at ``contracts/reverify_worklist.v1.schema.json`` is a valid
    JSON Schema, and
  * REAL warpline worklist output (NO_SNAPSHOT / complete / partial) validates
    against it, including the additive ``impact_completeness`` object and
    ``generated_at``, and
  * a round-tripped partial worklist degrades warpline's own consumer-side risk
    path to ``risk=unavailable(completeness_partial)`` — never clean.

wardline's existence-gated conformance test
(``test_vendored_worklist_matches_published_artifact``) finds this artifact at the
exact path above and will tighten to validate its vendored fixtures against it.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from warpline import commands
from warpline._completeness import completeness_risk
from warpline.store import WarplineStore, default_store_path

jsonschema = pytest.importorskip("jsonschema")

_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = _ROOT / "contracts" / "reverify_worklist.v1.schema.json"
FIXTURE_PATH = (
    _ROOT / "tests" / "fixtures" / "contracts" / "warpline" / "mcp-response-reverify.json"
)


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate(instance: dict) -> None:
    jsonschema.validate(instance=instance, schema=_schema())


# --------------------------------------------------------------------------- repo helpers
def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, capture_output=True
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "agent@example.test")
    _git(repo, "config", "user.name", "agent")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed")
    return repo


def _no_snapshot_worklist(tmp_path: Path) -> dict:
    repo = _repo(tmp_path)
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        a = store.ensure_entity_key(
            repo_id, locator="python:function:m.py::a", sei="loomweave:eid:aaaa", commit_sha="c1"
        )
    # No snapshot, no loomweave -> NO_SNAPSHOT (lazy capture is a no-op fail-soft).
    return commands.reverify_worklist(repo, [a], depth=2, loomweave_command="/no/such/binary")


def _seed_complete(tmp_path: Path) -> tuple[Path, int]:
    """A FULL snapshot AT HEAD with no out-edges -> fresh graph, no depth cap, zero
    unresolved -> impact_completeness.status == complete. Returns (repo, a)."""
    repo = _repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        a = store.ensure_entity_key(
            repo_id, locator="python:function:m.py::a", sei="loomweave:eid:aaaa", commit_sha=head
        )
        store.create_edge_snapshot(repo_id, head, "loomweave", "t", "FULL")
    return repo, a


def _complete_worklist(tmp_path: Path) -> dict:
    repo, a = _seed_complete(tmp_path)
    return commands.reverify_worklist(repo, [a], depth=2)


def _seed_partial(tmp_path: Path) -> tuple[Path, int]:
    """A FULL snapshot AT HEAD over an a->b->c chain. Returns (repo, a). Querying
    at depth=1 truncates the chain at b -> depth_capped -> status partial."""
    repo = _repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        a = store.ensure_entity_key(
            repo_id, locator="python:function:m.py::a", sei="loomweave:eid:aaaa", commit_sha=head
        )
        b = store.ensure_entity_key(
            repo_id, locator="python:function:m.py::b", sei="loomweave:eid:bbbb", commit_sha=head
        )
        c = store.ensure_entity_key(
            repo_id, locator="python:function:m.py::c", sei="loomweave:eid:cccc", commit_sha=head
        )
        snap = store.create_edge_snapshot(repo_id, head, "loomweave", "t", "FULL")
        for src, dst in ((a, b), (b, c)):
            store.append_snapshot_edge(
                snap, source_entity_key_id=src, target_entity_key_id=dst,
                edge_kind="calls", confidence="resolved",
            )
    return repo, a


def _partial_worklist(tmp_path: Path) -> dict:
    repo, a = _seed_partial(tmp_path)
    return commands.reverify_worklist(repo, [a], depth=1)


# --------------------------------------------------------------------------- schema tests
def test_published_schema_is_itself_valid_jsonschema() -> None:
    jsonschema.Draft202012Validator.check_schema(_schema())


def test_vendored_fixture_validates_against_published_schema() -> None:
    _validate(json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))


def test_real_no_snapshot_output_validates_and_is_unknown(tmp_path: Path) -> None:
    env = _no_snapshot_worklist(tmp_path)
    _validate(env)
    ic = env["data"]["impact_completeness"]
    assert env["data"]["completeness"] == "NO_SNAPSHOT"
    assert ic["status"] == "unknown"
    assert ic["graph_ref"] is None
    assert "no_snapshot" in ic["reasons"]
    # the producer timestamp (staleness axis) lives INSIDE the object, not at data.*
    assert isinstance(ic["as_of"], str)
    assert "generated_at" not in env["data"]


def test_real_complete_output_validates_and_is_complete(tmp_path: Path) -> None:
    env = _complete_worklist(tmp_path)
    _validate(env)
    ic = env["data"]["impact_completeness"]
    assert ic["status"] == "complete"
    assert ic["graph_fresh"] is True
    assert ic["depth_capped"] is False
    assert ic["unresolved_count"] == 0
    assert ic["reasons"] == []
    # Rung 2: complete but NO attest bundle supplied -> the honest gap, on the
    # real command path (not just the pure consumer).
    assert env["data"]["risk_verification"]["risk"] == "unavailable"
    assert env["data"]["risk_verification"]["reason_code"] == "verification_source_absent"


def _matching_bundle(commit: str, sei: str, content_hash: str) -> dict:
    return {
        "schema": "wardline-attest-2",
        "payload": {
            "commit": commit, "dirty": False, "attested_at": "2026-06-27",
            "sei_source": "loomweave", "posture": {},
            "boundaries": [{"qualname": "x", "sei": sei, "content_hash": content_hash,
                            "verdict": "clean", "tier": "INTEGRAL"}],
        },
        "signature": {"alg": "HMAC-SHA256", "value": "x", "key_id": "y"},
    }


def test_reverify_path_consumes_bundle_honestly_without_loomweave(tmp_path: Path) -> None:
    # A bundle IS supplied and the worklist is complete, but loomweave is
    # unreachable (bad command) -> warpline cannot fetch the current content_hash,
    # so the entity is honestly unmatched (attestation_incomplete), NEVER faked-good.
    # Proves the bundle is consumed on the real command path + the fail-soft edge.
    from warpline import commands

    repo, a = _seed_complete(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    bundle = _matching_bundle(head, "loomweave:eid:aaaa", "somehash")
    env = commands.reverify_worklist(
        repo, [a], depth=2, attest_bundle=bundle, loomweave_command="/no/such/binary"
    )
    _validate(env)
    rv = env["data"]["risk_verification"]
    assert rv["risk"] == "unavailable"
    assert rv["reason_code"] == "attestation_incomplete"


def test_real_partial_output_validates_and_is_partial(tmp_path: Path) -> None:
    env = _partial_worklist(tmp_path)
    _validate(env)
    ic = env["data"]["impact_completeness"]
    assert ic["status"] == "partial"
    assert ic["depth_capped"] is True
    assert "depth_capped" in ic["reasons"]


def _bad_status(d: dict) -> None:
    d["impact_completeness"]["status"] = "exhaustive"  # outside the enum


def _bad_as_of(d: dict) -> None:
    d["impact_completeness"]["as_of"] = "not-a-date"  # fails the RFC3339 pattern


def _bad_reason(d: dict) -> None:
    d["impact_completeness"]["reasons"].append("made_up_code")  # outside closed vocab


def _missing_required(d: dict) -> None:
    d["impact_completeness"].pop("graph_ref")  # required key removed


def _completeness_as_object(d: dict) -> None:
    d["completeness"] = {"obj": 1}  # the frozen field must stay a string enum


def _entity_missing_sei(d: dict) -> None:
    d["items"][0]["entity"].pop("sei")  # entity must carry locator + sei


@pytest.mark.parametrize(
    "mutate",
    [
        _bad_status,
        _bad_as_of,
        _bad_reason,
        _missing_required,
        _completeness_as_object,
        _entity_missing_sei,
    ],
)
def test_schema_rejects_malformed_payloads(mutate) -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    mutate(fixture["data"])
    with pytest.raises(jsonschema.ValidationError):
        _validate(fixture)


# ---------------------------------------------------------- real emission surfaces (MCP + CLI)
def test_mcp_handler_surface_emits_impact_completeness(tmp_path: Path) -> None:
    # wardline consumes the worklist as emitted by the MCP TOOL, not the internal
    # commands.* return value. Prove the field survives the handler with no response
    # projection stripping it, and that the raw `completeness` string is preserved.
    from warpline import mcp

    repo, a = _seed_partial(tmp_path)
    env = mcp._h_reverify({"repo": str(repo), "changed_entity_key_ids": [a], "depth": 1})
    _validate(env)
    ic = env["data"]["impact_completeness"]
    assert ic["status"] == "partial"
    assert "as_of" in ic
    assert env["data"]["completeness"] == "FULL"  # FROZEN raw string still present
    # Rung-2 verdict is emitted on the MCP surface; a partial worklist can't be proven.
    assert env["data"]["risk_verification"]["reason_code"] == "completeness_partial"


def test_mcp_handler_consumes_pushed_attest_bundle(tmp_path: Path) -> None:
    # The PUSHED bundle arrives as an MCP arg and is consumed on the handler path.
    from warpline import mcp

    repo, a = _seed_complete(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    bundle = _matching_bundle(head, "loomweave:eid:aaaa", "somehash")
    env = mcp._h_reverify(
        {"repo": str(repo), "changed_entity_key_ids": [a], "depth": 2, "attest_bundle": bundle}
    )
    _validate(env)
    # bundle consumed (complete worklist), but loomweave can't key 'aaaa' here, so
    # the verdict is honest unavailable — NOT verification_source_absent (which would
    # mean the bundle was ignored), proving the bundle reached the consumer.
    assert env["data"]["risk_verification"]["reason_code"] != "verification_source_absent"


def test_cli_surface_emits_impact_completeness(tmp_path: Path, capsys) -> None:
    # The documented "hand wardline a worklist" path: `warpline reverify --json`.
    from warpline import cli

    repo, a = _seed_partial(tmp_path)
    rc = cli.main(
        ["reverify", "--repo", str(repo),
         "--changed-entity-key-id", str(a), "--depth", "1", "--json"]
    )
    assert rc == 0
    env = json.loads(capsys.readouterr().out)
    _validate(env)
    assert env["data"]["impact_completeness"]["status"] == "partial"
    assert env["data"]["completeness"] == "FULL"


# --------------------------------------------------------------------------- consumer round-trip
def test_partial_worklist_roundtrip_degrades_risk_to_unavailable(tmp_path: Path) -> None:
    env = _partial_worklist(tmp_path)
    # Round-trip exactly as a pushed payload would travel: serialize -> parse.
    roundtripped = json.loads(json.dumps(env))
    verdict = completeness_risk(roundtripped["data"]["impact_completeness"])
    assert verdict["risk"] == "unavailable"
    assert verdict["reason_code"] == "completeness_partial"
    assert verdict["reason"]["reason_class"] != "clean"


def test_pre_d1_worklist_without_field_degrades_to_not_declared(tmp_path: Path) -> None:
    # A worklist from an OLD warpline carries no impact_completeness: the consumer
    # must report risk=unavailable(completeness_not_declared), never clean.
    env = _complete_worklist(tmp_path)
    data = json.loads(json.dumps(env))["data"]
    data.pop("impact_completeness", None)
    verdict = completeness_risk(data.get("impact_completeness"))
    assert verdict["risk"] == "unavailable"
    assert verdict["reason_code"] == "completeness_not_declared"
