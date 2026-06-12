from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
