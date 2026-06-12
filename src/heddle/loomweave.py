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
    try:
        payload = client.call_tool("entity_resolve", {"qualnames": [locator]})
    except Exception:
        return None
    sei = _sei_from_resolve_results(payload, locator)
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
