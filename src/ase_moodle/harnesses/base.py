"""Contractul comun al adaptoarelor de harness.

Fiecare harness (Claude Code, Codex, opencode, Antigravity) are propriul modul, cu:
- CLI-ul si comenzile lui exacte (sau fisierele de configurare, daca nu are CLI);
- scopurile pe care le suporta, strict: nu se ghiceste nimic si nu se muta nimic in tacere;
- o evidenta proprie: ~/.ase-moodle/state/<harness>.json, cu exact ce a scris instalarea,
  ca dezinstalarea sa stearga doar acel lucru;
- verificarea lui (doctor), in felul in care chiar functioneaza harness-ul.

Adaptoarele nu se importa intre ele. Izolarea e intentionata: o problema la Codex nu afecteaza Claude.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PLUGIN = "ase-moodle"
MARKETPLACE = "ase-moodle-marketplace"
DEFAULT_SOURCE = "FiredMosquito831/ase-moodle"
SCOPES = ("global", "project")

Runner = Callable[..., tuple[int, str]]


def default_run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    exe = shutil.which(cmd[0])
    if exe is None:
        return 127, f"{cmd[0]} nu este in PATH"
    proc = subprocess.run(
        [exe, *cmd[1:]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        cwd=str(cwd) if cwd else None,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


@dataclass
class Ctx:
    """Tot ce are nevoie un adaptor: home, folderul proiectului, sursa, cum rulezi comenzi si ce python folosim."""

    home: Path = field(default_factory=Path.home)
    project_dir: Path = field(default_factory=Path.cwd)
    source: str = ""
    run: Runner = default_run
    which: Callable[[str], str | None] = shutil.which
    python: str = sys.executable


@dataclass
class Step:
    target: str
    action: str
    status: str  # ok | skipped | error
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"target": self.target, "action": self.action, "status": self.status, "detail": self.detail}


class UnsupportedScope(ValueError):
    """Harness-ul nu suporta scopul cerut. Mesajul spune ce poti face in schimb."""


@dataclass(frozen=True)
class Capabilities:
    scopes: tuple[str, ...]
    needs_restart: bool
    notes: str


def step_from_result(target: str, action: str, code: int, out: str) -> Step:
    """Pas de instalare: reusit daca codul e 0 sau Moodle/CLI-ul spune ca exista deja."""
    tail = out[-400:] if out else ""
    if code == 0 or "already" in out.lower():
        return Step(target, action, "ok", tail)
    return Step(target, action, "error", tail or f"cod {code}")


def cleanup_step(target: str, action: str, code: int, out: str) -> Step:
    """Pas de curatare: 'nu era instalat' nu e eroare."""
    if code == 0:
        return Step(target, action, "ok", out[-200:])
    return Step(target, action, "ok", "nimic de curatat (nu era instalat)")


def repo_root() -> Path | None:
    """Radacina repo-ului cand pachetul ruleaza din sursa (pip install -e), altfel None."""
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude-plugin" / "marketplace.json").exists():
            return parent
    return None


def default_source() -> str:
    """Sursa implicita e GitHub. Calea locala (repo-ul) se da doar cu --source, altfel instalarea din alt folder muta marketplace-ul."""
    return DEFAULT_SOURCE


def server_command(python: str) -> list[str]:
    return [python, "-m", "ase_moodle.mcp_server"]


def skill_text() -> str:
    from importlib import resources

    return resources.files("ase_moodle").joinpath("data/SKILL.md").read_text(encoding="utf-8")


class Harness:
    """Baza. Subclasele definesc name, cli, capabilities si metodele install/uninstall/doctor."""

    name = ""
    cli: str | None = None  # executabilul verificat cu which; None = harness-ul e configurat prin fisiere
    capabilities = Capabilities(scopes=SCOPES, needs_restart=False, notes="")

    # ---- scopuri ----

    def check_scope(self, scope: str) -> None:
        if scope not in self.capabilities.scopes:
            hint = f" {self.capabilities.notes}" if self.capabilities.notes else ""
            raise UnsupportedScope(
                f"{self.name} nu suporta scopul '{scope}'. Suporta: {', '.join(self.capabilities.scopes)}.{hint}"
            )

    def expand(self, scope: str) -> list[str]:
        """'all' = toate scopurile suportate; un scop explicit = validat."""
        if scope == "all":
            return list(self.capabilities.scopes)
        self.check_scope(scope)
        return [scope]

    def scope_key(self, ctx: Ctx, scope: str) -> str:
        return "global" if scope == "global" else f"project:{ctx.project_dir.resolve()}"

    def cli_present(self, ctx: Ctx) -> bool:
        return self.cli is None or ctx.which(self.cli) is not None

    # ---- evidenta proprie (izolata pe harness) ----

    def state_path(self, ctx: Ctx) -> Path:
        return ctx.home / ".ase-moodle" / "state" / f"{self.name}.json"

    def _load(self, ctx: Ctx) -> dict[str, Any]:
        path = self.state_path(ctx)
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def _save(self, ctx: Ctx, data: dict[str, Any]) -> None:
        path = self.state_path(ctx)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def record(self, ctx: Ctx, scope: str, item: dict[str, Any]) -> None:
        """Noteaza un lucru scris de instalare. Idempotent: acelasi element apare o singura data."""
        data = self._load(ctx)
        entry = data.setdefault(self.scope_key(ctx, scope), {"items": []})
        entry["items"] = [i for i in entry["items"] if i != item] + [item]
        entry["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._save(ctx, data)

    def recorded(self, ctx: Ctx, scope: str) -> list[dict[str, Any]]:
        return self._load(ctx).get(self.scope_key(ctx, scope), {}).get("items", [])

    def forget(self, ctx: Ctx, scope: str) -> None:
        data = self._load(ctx)
        if data.pop(self.scope_key(ctx, scope), None) is not None:
            self._save(ctx, data)

    # ---- contract (subclasele il implementeaza) ----

    def install(self, ctx: Ctx, scope: str) -> list[Step]:
        raise NotImplementedError

    def uninstall(self, ctx: Ctx, scope: str = "all") -> list[Step]:
        raise NotImplementedError

    def update(self, ctx: Ctx, scope: str) -> list[Step]:
        return self.install(ctx, scope)

    def doctor(self, ctx: Ctx) -> list[Step]:
        raise NotImplementedError
