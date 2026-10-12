"""opencode: configurare in fisiere JSON, fara plugin.

- global: ~/.config/opencode/opencode.json (mcp.ase-moodle + instructions) si skill-ul copiat in
  ~/.config/opencode/ase-moodle/SKILL.md.
- project: opencode.json in folderul proiectului (doar mcp.ase-moodle). Calea Python din comanda e
  specifica acestui calculator, de aceea fisierul de proiect nu se comite (vezi .gitignore).

Particularitati:
- Scrie doar cheia 'ase-moodle'. Restul configurarii (alte servere MCP, provideri) ramane neatins.
- Face copie .bak inainte de orice scriere. Daca JSON-ul nu e valid, se opreste si nu modifica nimic.
- Schimbarea de scop curata celalalt scop.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .base import PLUGIN, Capabilities, Ctx, Harness, Step, server_command, skill_text


def _read(path: Path) -> dict:
    if not path.exists():
        return {"$schema": "https://opencode.ai/config.json"}
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _backup(path: Path) -> None:
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))


def _drop(path: Path, instruction: str | None) -> bool:
    """Scoate doar intrarea noastra (mcp.ase-moodle, si instructiunea data). Intoarce daca a schimbat ceva."""
    if not path.exists():
        return False
    data = _read(path)
    changed = data.get("mcp", {}).pop(PLUGIN, None) is not None
    if instruction and instruction in data.get("instructions", []):
        data["instructions"].remove(instruction)
        changed = True
    if changed:
        _backup(path)
        _write(path, data)
    return changed


class OpencodeHarness(Harness):
    name = "opencode"
    cli = None  # configurat prin fisiere; `opencode` e folosit doar pentru verificare, daca exista
    capabilities = Capabilities(
        scopes=("global", "project"),
        needs_restart=True,
        notes="global = ~/.config/opencode; project = opencode.json in folderul proiectului",
    )

    def _global_cfg(self, ctx: Ctx) -> Path:
        return ctx.home / ".config" / "opencode" / "opencode.json"

    def _project_cfg(self, ctx: Ctx) -> Path:
        return ctx.project_dir / "opencode.json"

    def _skill_dir(self, ctx: Ctx) -> Path:
        return ctx.home / ".config" / "opencode" / PLUGIN

    def _instruction(self, ctx: Ctx) -> str:
        return (self._skill_dir(ctx) / "SKILL.md").as_posix()

    def install(self, ctx: Ctx, scope: str) -> list[Step]:
        self.check_scope(scope)
        cfg = self._global_cfg(ctx) if scope == "global" else self._project_cfg(ctx)
        try:
            data = _read(cfg)
        except json.JSONDecodeError as exc:
            return [Step(self.name, "config", "error", f"{cfg} nu este JSON valid: {exc}")]
        _backup(cfg)
        data.setdefault("mcp", {})[PLUGIN] = {"type": "local", "command": server_command(ctx.python), "enabled": True}
        steps: list[Step] = []

        if scope == "global":
            skill_dir = self._skill_dir(ctx)
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(skill_text(), encoding="utf-8")
            instructions = data.setdefault("instructions", [])
            if self._instruction(ctx) not in instructions:
                instructions.append(self._instruction(ctx))
            _write(cfg, data)
            steps.append(Step(self.name, "global mcp", "ok", f"{cfg}: mcp.{PLUGIN}"))
            steps.append(Step(self.name, "global instructions", "ok", self._instruction(ctx)))
            self.record(ctx, "global", {"kind": "json-key", "path": str(cfg), "key": f"mcp.{PLUGIN}"})
            self.record(ctx, "global", {"kind": "instruction", "path": str(cfg), "value": self._instruction(ctx)})
            self.record(ctx, "global", {"kind": "dir", "path": str(skill_dir)})
            if _drop(self._project_cfg(ctx), None):
                steps.append(Step(self.name, "project cleanup", "ok", "scos mcp din opencode.json-ul proiectului"))
            self.forget(ctx, "project")
        else:
            _write(cfg, data)
            steps.append(Step(self.name, "project mcp", "ok",
                              f"{cfg} (comanda contine calea Python a acestui calculator)"))
            self.record(ctx, "project", {"kind": "json-key", "path": str(cfg), "key": f"mcp.{PLUGIN}"})
            if _drop(self._global_cfg(ctx), self._instruction(ctx)):
                steps.append(Step(self.name, "global cleanup", "ok", "scos mcp si instructiuni globale"))
            shutil.rmtree(self._skill_dir(ctx), ignore_errors=True)
            self.forget(ctx, "global")
        return steps

    def uninstall(self, ctx: Ctx, scope: str = "all") -> list[Step]:
        steps: list[Step] = []
        for sc in self.expand(scope):
            if sc == "global":
                cfg = self._global_cfg(ctx)
                if not cfg.exists():
                    steps.append(Step(self.name, "global uninstall", "skipped", "nu exista opencode.json"))
                elif _drop(cfg, self._instruction(ctx)):
                    steps.append(Step(self.name, "global uninstall", "ok", "mcp si instructiuni eliminate"))
                else:
                    steps.append(Step(self.name, "global uninstall", "skipped", "nu era instalat global"))
                shutil.rmtree(self._skill_dir(ctx), ignore_errors=True)
            else:
                if _drop(self._project_cfg(ctx), None):
                    steps.append(Step(self.name, "project uninstall", "ok", "mcp scos din opencode.json-ul proiectului"))
                else:
                    steps.append(Step(self.name, "project uninstall", "skipped", "nu era instalat in proiect"))
            self.forget(ctx, sc)
        return steps

    def doctor(self, ctx: Ctx) -> list[Step]:
        steps: list[Step] = []
        present = []
        for sc, cfg in (("global", self._global_cfg(ctx)), ("project", self._project_cfg(ctx))):
            try:
                ok = PLUGIN in _read(cfg).get("mcp", {})
            except (OSError, json.JSONDecodeError) as exc:
                steps.append(Step(self.name, sc, "error", f"{cfg}: {exc}"))
                continue
            if ok:
                present.append(sc)
            steps.append(Step(self.name, sc, "ok" if ok else "skipped",
                              f"instalat ({cfg})" if ok else "nu e instalat"))
        if ctx.which("opencode") is not None:
            code, out = ctx.run(["opencode", "mcp", "list"])
            steps.append(Step(self.name, "cli mcp list", "ok" if PLUGIN in out else "warning",
                              "serverul apare in 'opencode mcp list'" if PLUGIN in out else "nu apare in 'opencode mcp list'"))
        if not present:
            steps.append(Step(self.name, "status", "error", "nu e instalat nici global, nici in folderul proiectului"))
        return steps
