from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class ToolClient(Protocol):
    def call_tool(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class LoomweaveProbe:
    repo: Path
    command: str = "loomweave"

    def expected_tools(self) -> set[str]:
        return {
            "project_status_get",
            "entity_find",
            "entity_resolve",
            "entity_neighborhood_get",
            "entity_callers_list",
            "entity_source_get",
        }

    def probe(self) -> dict[str, Any]:
        executable = shutil.which(self.command) if "/" not in self.command else self.command
        if executable is None or not Path(executable).exists():
            return {"status": "skipped", "reason": "command_unavailable"}
        db_path = self.repo / ".weft" / "loomweave" / "loomweave.db"
        if not db_path.exists():
            return {"status": "skipped", "reason": "no_index"}
        version = subprocess.run(
            [executable, "--version"],
            check=False,
            text=True,
            capture_output=True,
        ).stdout.strip()
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        proc = subprocess.run(
            [executable, "serve", "--path", str(self.repo)],
            input=json.dumps(request) + "\n",
            check=False,
            text=True,
            capture_output=True,
            timeout=5,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return {
                "status": "skipped",
                "reason": "serve_failed",
                "detail": proc.stderr[-1000:],
                "version": version,
            }
        response = json.loads(proc.stdout.splitlines()[-1])
        tools = [tool["name"] for tool in response["result"]["tools"]]
        missing = sorted(self.expected_tools() - set(tools))
        if missing:
            return {
                "status": "skipped",
                "reason": "missing_tools",
                "missing": missing,
                "version": version,
            }
        return {"status": "available", "version": version, "tools": tools}


class LoomweaveMcpClient:
    def __init__(self, repo: Path, command: str = "loomweave") -> None:
        self.repo = repo
        self.command = command

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        proc = subprocess.run(
            [self.command, "serve", "--path", str(self.repo)],
            input=json.dumps(request) + "\n",
            check=False,
            text=True,
            capture_output=True,
            timeout=10,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[-1000:])
        envelope = json.loads(proc.stdout.splitlines()[-1])
        if "error" in envelope:
            raise RuntimeError(str(envelope["error"]))
        text = envelope["result"]["content"][0]["text"]
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise RuntimeError("loomweave tool returned non-object payload")
        result = payload.get("result")
        if payload.get("ok") is True and isinstance(result, dict):
            return result
        return payload

    def neighborhood(self, entity: str) -> dict[str, Any]:
        return self.call_tool("entity_neighborhood_get", {"id": entity, "limit": 100})


def resolve_sei_for_locator(client: ToolClient, locator: str) -> str | None:
    # HX1: the REAL loomweave entity_resolve resolves BARE dotted package
    # qualnames (e.g. "heddle.store.HeddleStore.timeline"), not the
    # "python:function:..." entity-id form and not the filesystem path. We send
    # bare candidates (src-layout stripped) so resolution works against the live
    # member, not only a FakeClient.
    candidates = loomweave_resolve_qualnames(locator)
    try:
        payload = client.call_tool("entity_resolve", {"qualnames": candidates})
    except Exception:
        return None
    for candidate in candidates:
        sei = _sei_from_resolve_results(payload, candidate)
        if sei is not None:
            return sei
    entity = payload.get("entity") if isinstance(payload, dict) else None
    if not isinstance(entity, dict):
        return None
    sei = entity.get("sei")
    return sei if isinstance(sei, str) and sei else None


def _sei_from_resolve_results(payload: dict[str, object], locator: str) -> str | None:
    results = payload.get("results")
    if not isinstance(results, list):
        return None
    for result in results:
        if not isinstance(result, dict):
            continue
        qualname = result.get("qualname")
        if isinstance(qualname, str) and qualname != locator:
            continue
        entity = result.get("entity")
        if isinstance(entity, dict):
            sei = entity.get("sei")
            if isinstance(sei, str) and sei:
                return sei
        candidates = result.get("candidates")
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            sei = candidate.get("sei")
            if isinstance(sei, str) and sei:
                return sei
    return None


_SOURCE_ROOTS = ("src", "lib")


def _module_paths(file_path: str) -> list[str]:
    """Dotted import-module candidates for a .py file path.

    Loomweave keys on the import path (``heddle.store``), not the filesystem
    path (``src/heddle/store.py``). We return the src-layout-stripped form first
    and the verbatim form second so both src-layout and flat-layout repos
    resolve with a single round trip.
    """

    if not file_path.endswith(".py"):
        return []
    parts = file_path[:-3].split("/")
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    stripped = parts[1:] if parts and parts[0] in _SOURCE_ROOTS else parts
    forms: list[str] = []
    for candidate in (stripped, parts):
        dotted = ".".join(p for p in candidate if p)
        if dotted and dotted not in forms:
            forms.append(dotted)
    return forms


def _split_entity_locator(locator: str) -> tuple[str, str, str] | None:
    """(kind_prefix, file_path, qualname) for a python entity locator, else None."""

    if locator.startswith(("python:function:", "python:class:")) and "::" in locator:
        namespace, kind, body = locator.split(":", 2)
        path, qualname = body.split("::", 1)
        return f"{namespace}:{kind}", path, qualname
    return None


def loomweave_resolve_qualnames(locator: str) -> list[str]:
    """Bare dotted qualnames for loomweave ``entity_resolve`` (HX1).

    entity_resolve resolves unprefixed import qualnames, so we strip the
    ``python:{kind}:`` prefix and the filesystem path entirely.
    """

    candidates: list[str] = []
    split = _split_entity_locator(locator)
    if split is not None:
        _, path, qualname = split
        for module in _module_paths(path):
            candidates.append(f"{module}.{qualname}")
    elif locator.startswith("file:") and locator.endswith(".py"):
        candidates.extend(_module_paths(locator.removeprefix("file:")))
    if locator not in candidates:
        candidates.append(locator)
    return candidates


def loomweave_entity_id_candidates(locator: str) -> list[str]:
    """Prefixed loomweave entity ids for a local Heddle locator.

    Used to query ``entity_neighborhood_get`` and to alias loomweave ids back to
    heddle entity keys. Returns the ``python:{kind}:<dotted-id>`` form
    (src-layout stripped first) and the verbatim locator as a fallback.
    """

    candidates: list[str] = []
    split = _split_entity_locator(locator)
    if split is not None:
        kind_prefix, path, qualname = split
        for module in _module_paths(path):
            candidates.append(f"{kind_prefix}:{module}.{qualname}")
    elif locator.startswith("file:") and locator.endswith(".py"):
        for module in _module_paths(locator.removeprefix("file:")):
            candidates.append(f"python:module:{module}")
    candidates.append(locator)
    deduped: list[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped
