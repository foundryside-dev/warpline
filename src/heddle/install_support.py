"""Federation-standard `install` / `doctor` for heddle.

Mirrors the sibling install contract (filigree): `install` wires the MCP
bindings, hooks, skill injection, instruction blocks and `.weft/heddle/` config;
`doctor` verifies each and `doctor --fix` re-applies anything autofixable. All
writes are idempotent, atomic, and symlink-safe, and never clobber a foreign
member's block.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from heddle import __version__
from heddle.install import install_hook
from heddle.store import HEDDLE_GITIGNORE_CONTENTS

MEMBER = "heddle"
SKILL_NAME = "heddle-workflow"
INSTALL_VERSION = 1

INSTRUCTIONS_OPEN_PREFIX = f"<!-- {MEMBER}:instructions"
INSTRUCTIONS_OPEN = f"<!-- {MEMBER}:instructions:v{__version__} -->"
INSTRUCTIONS_END = f"<!-- /{MEMBER}:instructions -->"
# A foreign fence is any other member's instruction marker — never delete it.
_FOREIGN_FENCE = "<!-- "

CODEX_BLOCK_OPEN = "# >>> heddle mcp (managed) >>>"
CODEX_BLOCK_END = "# <<< heddle mcp (managed) <<<"

INSTRUCTIONS_BODY = """\
## Heddle (temporal change-impact)

`heddle` is the Weft federation's temporal / change-impact authority — "if I
touch X, what breaks, and what must I re-verify?". Prefer the MCP tools
(`mcp__heddle__*`); fall back to the `heddle` CLI. Endorsed names and short
shims return identical schema+data.

- `heddle_change_list` / `changed` — changed entities for a rev range; call first.
- `heddle_impact_radius_get` / `blast_radius` — downstream affected set.
- `heddle_reverify_worklist_get` / `reverify` — worklist to recheck before done.
- `heddle_entity_timeline_get` / `timeline`, `heddle_entity_churn_count_get` /
  `churn`, `heddle_edge_snapshot_capture` / `capture_snapshot` (only mutating
  tool; writes `.weft/heddle/` only).

Enrich-only and local-only: every response is `meta.local_only: true`,
`peer_side_effects: []`. `enrichment` is a CLOSED vocab
(`present|absent|unavailable`); sibling absence is explicit, never an implied
clean/allowed state. heddle facts are advisory and never gate. See the
`heddle-workflow` skill for the full loop.
"""


# --------------------------------------------------------------------------- paths
def skills_source() -> Path:
    return Path(__file__).resolve().parent / "skills" / SKILL_NAME


def weft_member_dir(repo: Path) -> Path:
    return repo.resolve() / ".weft" / MEMBER


def reject_symlink(path: Path) -> None:
    if path.is_symlink():
        raise OSError(f"refusing to write through symlink: {path}")


def _atomic_write_text(path: Path, text: str) -> None:
    reject_symlink(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".heddle-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        if path.exists():
            shutil.copymode(path, tmp)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def mcp_command() -> tuple[str, list[str]]:
    """The stdio command that launches heddle's MCP server."""

    found = shutil.which("heddle-mcp")
    if found:
        return found, []
    return sys.executable, ["-m", "heddle.mcp"]


# --------------------------------------------------------------------------- components
@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    fixable: bool = True


@dataclass
class Component:
    key: str
    name: str
    check: Callable[[Path], CheckResult]
    apply: Callable[[Path], str]


def _result(name: str, ok: bool, detail: str, fixable: bool = True) -> CheckResult:
    return CheckResult(name=name, ok=ok, detail=detail, fixable=fixable)


# --- MCP: Claude Code (.mcp.json) ------------------------------------------------
def _mcp_json_path(repo: Path) -> Path:
    return repo.resolve() / ".mcp.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def check_mcp_claude(repo: Path) -> CheckResult:
    data = _load_json(_mcp_json_path(repo))
    entry = data.get("mcpServers", {}).get(MEMBER) if isinstance(data, dict) else None
    if not isinstance(entry, dict) or not entry.get("command"):
        return _result("Claude Code MCP", False, ".mcp.json has no heddle server")
    return _result("Claude Code MCP", True, f"command={entry['command']}")


def apply_mcp_claude(repo: Path) -> str:
    path = _mcp_json_path(repo)
    data = _load_json(path)
    servers = data.setdefault("mcpServers", {})
    command, args = mcp_command()
    servers[MEMBER] = {"type": "stdio", "command": command, "args": args, "env": {}}
    _atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")
    return f"registered heddle MCP (stdio) -> {command} {' '.join(args)}".strip()


# --- MCP: Codex (~/.codex/config.toml) ------------------------------------------
def _codex_config_path() -> Path:
    return Path.home() / ".codex" / "config.toml"


def check_mcp_codex(repo: Path) -> CheckResult:
    path = _codex_config_path()
    if not path.exists():
        return _result("Codex MCP", False, "~/.codex/config.toml absent")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return _result("Codex MCP", False, "config.toml unreadable")
    entry = data.get("mcp_servers", {}).get(MEMBER)
    if not isinstance(entry, dict) or not entry.get("command"):
        return _result("Codex MCP", False, "no [mcp_servers.heddle] table")
    return _result("Codex MCP", True, f"command={entry['command']}")


def apply_mcp_codex(repo: Path) -> str:
    path = _codex_config_path()
    command, args = mcp_command()
    args_toml = ", ".join(json.dumps(a) for a in args)
    block = (
        f"{CODEX_BLOCK_OPEN}\n"
        f"[mcp_servers.{MEMBER}]\n"
        f"command = {json.dumps(command)}\n"
        f"args = [{args_toml}]\n"
        f"{CODEX_BLOCK_END}\n"
    )
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    updated = _replace_or_append_block(existing, CODEX_BLOCK_OPEN, CODEX_BLOCK_END, block)
    # Validate before persisting — never leave the user's global config broken.
    tomllib.loads(updated)
    _atomic_write_text(path, updated)
    return "registered [mcp_servers.heddle] in ~/.codex/config.toml"


def _replace_or_append_block(text: str, open_marker: str, end_marker: str, block: str) -> str:
    start = text.find(open_marker)
    if start != -1:
        end = text.find(end_marker, start)
        if end != -1:
            end += len(end_marker)
            tail = text[end:]
            if tail.startswith("\n"):
                tail = tail[1:]
            return text[:start] + block + tail
    if text and not text.endswith("\n"):
        text += "\n"
    if text and not text.endswith("\n\n"):
        text += "\n"
    return text + block


# --- Instruction injection (CLAUDE.md / AGENTS.md) -------------------------------
def _build_instructions_block() -> str:
    return f"{INSTRUCTIONS_OPEN}\n{INSTRUCTIONS_BODY}{INSTRUCTIONS_END}\n"


def _has_instructions(text: str) -> bool:
    return INSTRUCTIONS_OPEN_PREFIX in text and INSTRUCTIONS_END in text


def _inject_instructions(text: str) -> str:
    block = _build_instructions_block()
    start = text.find(INSTRUCTIONS_OPEN_PREFIX)
    if start != -1:
        end = text.find(INSTRUCTIONS_END, start)
        if end != -1:
            end += len(INSTRUCTIONS_END)
            tail = text[end:]
            if tail.startswith("\n"):
                tail = tail[1:]
            return text[:start] + block + tail
    if text and not text.endswith("\n"):
        text += "\n"
    if text:
        text += "\n"
    return text + block


def _make_instruction_component(filename: str) -> Component:
    def check(repo: Path) -> CheckResult:
        path = repo.resolve() / filename
        if not path.exists() or not _has_instructions(path.read_text(encoding="utf-8")):
            return _result(filename, False, f"{filename} missing heddle:instructions block")
        return _result(filename, True, "heddle:instructions block present")

    def apply(repo: Path) -> str:
        path = repo.resolve() / filename
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        _atomic_write_text(path, _inject_instructions(text))
        return f"injected heddle:instructions into {filename} (foreign blocks preserved)"

    key = "claude_md" if filename == "CLAUDE.md" else "agents_md"
    return Component(key=key, name=filename, check=check, apply=apply)


# --- Skill injection -------------------------------------------------------------
def _make_skill_component(key: str, root_name: str, label: str) -> Component:
    def skill_dir(repo: Path) -> Path:
        return repo.resolve() / root_name / "skills" / SKILL_NAME

    def check(repo: Path) -> CheckResult:
        sentinel = skill_dir(repo) / "SKILL.md"
        if not sentinel.exists():
            return _result(label, False, f"{root_name}/skills/{SKILL_NAME}/SKILL.md absent")
        return _result(label, True, "skill installed")

    def apply(repo: Path) -> str:
        target = skill_dir(repo)
        reject_symlink(target)
        for part in target.parents:
            if part == repo.resolve():
                break
            if part.is_symlink():
                raise OSError(f"refusing to install skill through symlink: {part}")
        staging = target.parent / f"{SKILL_NAME}.installing.{os.getpid()}"
        if staging.exists():
            shutil.rmtree(staging)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skills_source(), staging)
        if target.exists():
            shutil.rmtree(target)
        os.replace(staging, target)
        return f"installed {SKILL_NAME} skill into {root_name}/skills/"

    return Component(key=key, name=label, check=check, apply=apply)


# --- gitignore -------------------------------------------------------------------
def check_gitignore(repo: Path) -> CheckResult:
    path = repo.resolve() / ".gitignore"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if ".weft/" not in text.splitlines():
        return _result(".gitignore", False, ".weft/ not ignored")
    return _result(".gitignore", True, ".weft/ ignored")


def apply_gitignore(repo: Path) -> str:
    path = repo.resolve() / ".gitignore"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if ".weft/" in text.splitlines():
        return ".gitignore already ignores .weft/"
    if text and not text.endswith("\n"):
        text += "\n"
    text += "\n# Heddle federation runtime store\n.weft/\n"
    _atomic_write_text(path, text)
    return "added .weft/ to .gitignore"


# --- git post-commit hook --------------------------------------------------------
def check_git_hook(repo: Path) -> CheckResult:
    hook = repo.resolve() / ".git" / "hooks" / "post-commit"
    if not (repo.resolve() / ".git").exists():
        return _result("git post-commit hook", False, "not a git repository", fixable=False)
    if not hook.exists() or "BEGIN HEDDLE MANAGED BLOCK" not in hook.read_text(encoding="utf-8"):
        return _result("git post-commit hook", False, "heddle ingest hook not installed")
    return _result("git post-commit hook", True, "ingest hook installed")


def apply_git_hook(repo: Path) -> str:
    install_hook(repo.resolve())
    return "installed fail-soft post-commit ingest hook"


# --- Claude Code SessionStart hook ----------------------------------------------
def _settings_path(repo: Path) -> Path:
    return repo.resolve() / ".claude" / "settings.json"


def _session_command(repo: Path) -> str:
    heddle = shutil.which("heddle") or "heddle"
    return f"{heddle} session-context --repo '{repo.resolve()}'"


def _settings_has_heddle(data: dict[str, Any]) -> bool:
    groups = data.get("hooks", {}).get("SessionStart", [])
    if not isinstance(groups, list):
        return False
    for group in groups:
        for hook in (group or {}).get("hooks", []) if isinstance(group, dict) else []:
            if isinstance(hook, dict) and "heddle session-context" in str(hook.get("command", "")):
                return True
            if isinstance(hook, dict) and "session-context" in str(hook.get("command", "")) and (
                "heddle" in str(hook.get("command", ""))
            ):
                return True
    return False


def check_session_hook(repo: Path) -> CheckResult:
    data = _load_json(_settings_path(repo))
    if _settings_has_heddle(data):
        return _result("Claude Code SessionStart hook", True, "session-context hook installed")
    return _result("Claude Code SessionStart hook", False, "no heddle session-context hook")


def apply_session_hook(repo: Path) -> str:
    path = _settings_path(repo)
    data = _load_json(path)
    if _settings_has_heddle(data):
        return "session-context hook already present"
    hooks = data.setdefault("hooks", {})
    session = hooks.setdefault("SessionStart", [])
    if not isinstance(session, list):
        session = []
        hooks["SessionStart"] = session
    session.append(
        {"hooks": [{"type": "command", "command": _session_command(repo), "timeout": 5000}]}
    )
    _atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")
    return "added heddle session-context SessionStart hook (sibling hooks preserved)"


# --- .weft/heddle config ---------------------------------------------------------
def check_config(repo: Path) -> CheckResult:
    member = weft_member_dir(repo)
    config = member / "config.json"
    version = member / "INSTALL_VERSION"
    if not config.exists() or not version.exists():
        return _result(".weft/heddle config", False, "config.json/INSTALL_VERSION missing")
    return _result(".weft/heddle config", True, "config + version marker present")


def apply_config(repo: Path) -> str:
    member = weft_member_dir(repo)
    member.mkdir(parents=True, exist_ok=True)
    nested_gitignore = member / ".gitignore"
    if not nested_gitignore.exists():
        _atomic_write_text(nested_gitignore, HEDDLE_GITIGNORE_CONTENTS)
    config = {"prefix": MEMBER, "name": MEMBER, "version": INSTALL_VERSION}
    _atomic_write_text(member / "config.json", json.dumps(config, indent=2, sort_keys=True) + "\n")
    _atomic_write_text(member / "INSTALL_VERSION", f"{INSTALL_VERSION}\n")
    return "wrote .weft/heddle/config.json + INSTALL_VERSION"


# --------------------------------------------------------------------------- registry
def components() -> list[Component]:
    return [
        Component("claude-code", "Claude Code MCP", check_mcp_claude, apply_mcp_claude),
        Component("codex", "Codex MCP", check_mcp_codex, apply_mcp_codex),
        _make_instruction_component("CLAUDE.md"),
        _make_instruction_component("AGENTS.md"),
        Component("gitignore", ".gitignore", check_gitignore, apply_gitignore),
        Component("hooks", "git post-commit hook", check_git_hook, apply_git_hook),
        Component(
            "session-hook",
            "Claude Code SessionStart hook",
            check_session_hook,
            apply_session_hook,
        ),
        _make_skill_component("skills", ".claude", "Claude Code skills"),
        _make_skill_component("codex-skills", ".agents", "Codex skills"),
        Component("config", ".weft/heddle config", check_config, apply_config),
    ]


# component keys selectable via install flags (config + claude-md/agents-md grouping)
_DEFAULT_KEYS = {c.key for c in components()}


@dataclass
class InstallReport:
    actions: list[tuple[str, str]] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def run_install(repo: Path, selected: set[str] | None = None) -> InstallReport:
    keys = selected or _DEFAULT_KEYS
    # config first so .weft/heddle exists for everything else.
    ordered = sorted(components(), key=lambda c: 0 if c.key == "config" else 1)
    report = InstallReport()
    for component in ordered:
        if component.key not in keys:
            continue
        try:
            report.actions.append((component.name, component.apply(repo)))
        except Exception as exc:  # noqa: BLE001 — surface, don't crash the installer
            report.errors.append((component.name, str(exc)))
    return report


@dataclass
class DoctorReport:
    results: list[CheckResult]
    fixed: list[tuple[str, str]] = field(default_factory=list)
    unfixable: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)


def run_doctor(repo: Path, fix: bool = False) -> DoctorReport:
    comps = components()
    results = [c.check(repo) for c in comps]
    report = DoctorReport(results=results)
    if not fix:
        report.unfixable = [r for r in results if not r.ok and not r.fixable]
        return report
    by_name = {c.name: c for c in comps}
    new_results: list[CheckResult] = []
    for result in results:
        if result.ok:
            new_results.append(result)
            continue
        component = by_name[result.name]
        if not result.fixable:
            report.unfixable.append(result)
            new_results.append(result)
            continue
        try:
            detail = component.apply(repo)
            report.fixed.append((result.name, detail))
            new_results.append(component.check(repo))
        except Exception as exc:  # noqa: BLE001
            new_results.append(_result(result.name, False, f"fix failed: {exc}", fixable=False))
            report.unfixable.append(new_results[-1])
    report.results = new_results
    return report


def doctor_summary(report: DoctorReport) -> dict[str, Any]:
    return {
        "schema": "heddle.doctor.v1",
        "ok": report.ok,
        "checks": [
            {"name": r.name, "ok": r.ok, "detail": r.detail, "fixable": r.fixable}
            for r in report.results
        ],
        "fixed": [{"name": n, "detail": d} for n, d in report.fixed],
    }
