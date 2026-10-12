"""Dispatcher pentru instalare. Logica fiecarui harness e in ase_moodle/harnesses/<nume>.py, izolata.

- `install all` / `update all` / `uninstall all` ruleaza adaptoarele, unul dupa altul, fara sa-si imparta nimic.
  Un harness care nu suporta scopul cerut e sarit cu un mesaj; cu un nume explicit, e eroare.
- Comenzile per harness (`ase-moodle claude install ...`) sunt in cli.py si merg direct la adaptorul respectiv.
- `doctor` verifica fiecare harness in felul lui, plus token, .env si procesele MCP.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .harnesses.base import (
    DEFAULT_SOURCE,
    PLUGIN,
    SCOPES,
    Ctx,
    Step,
    UnsupportedScope,
    default_source,
    repo_root,
    server_command,
    skill_text,
)
from .config import find_dotenv, load_settings
from .harnesses import REGISTRY

Env = Ctx
TARGETS = tuple(REGISTRY)
UNINSTALL_SCOPES = (*SCOPES, "all")

__all__ = [
    "DEFAULT_SOURCE", "Env", "PLUGIN", "SCOPES", "TARGETS", "Step", "default_source", "doctor", "install",
    "repo_root", "server_command", "skill_text", "sync_plugin_skill", "uninstall", "update",
]


def sync_plugin_skill(root: Path) -> Path:
    """Copiaza SKILL.md canonic (din pachet) in plugin, ca sa ramana identice."""
    target = root / "plugins" / PLUGIN / "skills" / PLUGIN / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(skill_text(), encoding="utf-8")
    return target


def _targets(names: list[str] | None) -> list[str]:
    if not names or "all" in names:
        return list(TARGETS)
    unknown = [n for n in names if n not in TARGETS]
    if unknown:
        raise ValueError(f"Tinte necunoscute: {unknown}. Valide: {', '.join(TARGETS)} sau all")
    return names


def _check(scope: str, valid: tuple[str, ...]) -> None:
    if scope not in valid:
        raise ValueError(f"Scop necunoscut: {scope}. Valide: {', '.join(valid)}")


def _dispatch(names, env, scope, action, method_name, valid_scopes):
    _check(scope, valid_scopes)
    explicit = bool(names) and "all" not in names
    steps: list[Step] = []
    for name in _targets(names):
        harness = REGISTRY[name]
        try:
            steps += getattr(harness, method_name)(env, scope)
        except UnsupportedScope as exc:
            if explicit:
                raise
            steps.append(Step(name, action, "skipped", str(exc)))
    return steps


def install(names: list[str] | None = None, env: Env | None = None, scope: str = "global") -> list[Step]:
    env = env or Env(source=default_source())
    return _dispatch(names, env, scope, "install", "install", SCOPES)


def update(names: list[str] | None = None, env: Env | None = None, scope: str = "global") -> list[Step]:
    env = env or Env(source=default_source())
    return _dispatch(names, env, scope, "update", "update", SCOPES)


def uninstall(names: list[str] | None = None, env: Env | None = None, scope: str = "all") -> list[Step]:
    env = env or Env(source=default_source())
    _check(scope, UNINSTALL_SCOPES)
    explicit = bool(names) and "all" not in names
    steps: list[Step] = []
    for name in _targets(names):
        try:
            steps += REGISTRY[name].uninstall(env, scope)
        except UnsupportedScope as exc:
            if explicit:
                raise
            steps.append(Step(name, "uninstall", "skipped", str(exc)))
    return steps


def _running_mcp_processes() -> int:
    """Cate procese ase-moodle-mcp ruleaza (Windows: tasklist; Linux/macOS: pgrep)."""
    if sys.platform == "win32":
        cmd = ["tasklist", "/FI", "IMAGENAME eq ase-moodle-mcp.exe", "/FO", "CSV", "/NH"]
    else:
        if shutil.which("pgrep") is None:
            return 0
        cmd = ["pgrep", "-f", "ase-moodle-mcp|ase_moodle.mcp_server"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    if sys.platform == "win32":
        return sum(1 for line in out.splitlines() if "ase-moodle-mcp" in line.lower())
    return sum(1 for line in out.splitlines() if line.strip().isdigit())


def doctor(env: Env | None = None) -> list[Step]:
    """Verifica fiecare harness in felul lui, plus token, .env, procese MCP si versiunea pachetului."""
    env = env or Env(source=default_source())
    steps: list[Step] = []
    try:
        load_settings()
        steps.append(Step("package", "token", "ok", "token gasit"))
    except Exception as exc:  # noqa: BLE001
        steps.append(Step("package", "token", "error", str(exc)))
    mcp_bin = env.which("ase-moodle-mcp")
    steps.append(Step("package", "ase-moodle-mcp in PATH", "ok" if mcp_bin else "error",
                      mcp_bin or "lipseste; ruleaza: pipx install --force git+https://github.com/FiredMosquito831/ase-moodle-mcp.git"))

    for name in TARGETS:
        steps += REGISTRY[name].doctor(env)

    try:
        settings = load_settings()
        steps.append(Step("security", "token source", "ok", f"{settings.source} (tokenul nu se afiseaza)"))
        dotenv = find_dotenv()
        steps.append(Step("security", ".env", "ok", str(dotenv) if dotenv else "nu exista (optional)"))
    except Exception as exc:  # noqa: BLE001
        steps.append(Step("security", "token source", "error", str(exc)))

    running = _running_mcp_processes()
    steps.append(Step("package", "procese MCP pornite", "ok" if running == 0 else "warning",
                      f"{running} proces(e) ase-moodle-mcp. Inchide-le inainte de reinstalare (pipx install --force ...) dupa update"))
    try:
        from importlib.metadata import version

        steps.append(Step("package", "metadate pachet", "ok", f"versiunea {version('ase-moodle')}"))
    except Exception as exc:  # noqa: BLE001
        steps.append(Step("package", "metadate pachet", "warning",
                          f"metadatele sunt rupte ({exc.__class__.__name__}); ruleaza pipx install --force ... dupa inchiderea MCP"))
    return steps
