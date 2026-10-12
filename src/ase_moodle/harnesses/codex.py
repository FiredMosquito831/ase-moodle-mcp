"""Codex: scopul 'global' = plugin + marketplace (in ~/.codex); scopul 'project' = doar serverul MCP, in .codex/config.toml.

Particularitati (de aceea adaptorul e separat):
- Codex tine marketplace-urile si pluginurile global, in ~/.codex. Nu exista plugin de proiect.
  Pe proiect instalam deci doar serverul MCP, in .codex/config.toml din folder. Skill-urile nu vin pe proiect.
- Codex cere sa marchezi folderul ca proiect de incredere, prima data cand il deschizi. Fara asta,
  .codex/config.toml nu se incarca. Nu marcam automat: e o decizie a ta.
- Schimbarea de scop curata celalalt scop, ca sa nu existe doua servere.
- Verificarea 'global' foloseste `codex plugin list`; verificarea 'project' citeste fisierul.
"""

from __future__ import annotations

import re

from .base import MARKETPLACE, PLUGIN, Capabilities, Ctx, Harness, Step, cleanup_step, step_from_result

NEEDLE = f"{PLUGIN}@{MARKETPLACE}"
TABLE = f"mcp_servers.{PLUGIN}"


def _remove_toml_table(path, table: str) -> int:
    """Scoate tabelul [table] si subtabelele [table.*] dintr-un TOML. Intoarce cate tabele [table] au fost scoase."""
    if not path.exists():
        return 0
    header = re.compile(r"^\s*\[\[?([^\]]+)\]\]?\s*$")
    keep: list[str] = []
    removed = 0
    skipping = False
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        match = header.match(line)
        if match:
            name = match.group(1).strip()
            if name == table or name.startswith(table + "."):
                skipping = True
                if name == table:
                    removed += 1
                continue
            skipping = False
        if not skipping:
            keep.append(line)
    if removed:
        path.write_text("".join(keep), encoding="utf-8")
    return removed


class CodexHarness(Harness):
    name = "codex"
    cli = "codex"
    capabilities = Capabilities(
        scopes=("global", "project"),
        needs_restart=False,
        notes=("global = plugin + marketplace in ~/.codex; project = doar serverul MCP in .codex/config.toml "
               "din folder (marcheaza folderul ca proiect de incredere)"),
    )

    def _project_cfg(self, ctx: Ctx):
        return ctx.project_dir / ".codex" / "config.toml"

    def _home_cfg(self, ctx: Ctx):
        return ctx.home / ".codex" / "config.toml"

    def _write_project_block(self, ctx: Ctx) -> Step:
        cfg = self._project_cfg(ctx)
        cfg.parent.mkdir(parents=True, exist_ok=True)
        _remove_toml_table(cfg, TABLE)  # idempotent: nu dublam tabelul
        text = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
        if text and not text.endswith("\n"):
            text += "\n"
        # Sir literal (apostrof): caile Windows nu cer escape.
        block = f"\n[{TABLE}]\ncommand = '{ctx.python}'\nargs = [\"-m\", \"ase_moodle.mcp_server\"]\n"
        cfg.write_text(text + block, encoding="utf-8")
        return Step(self.name, "project mcp", "ok",
                    f"{cfg} (marcheaza folderul ca proiect de incredere in Codex)")

    def install(self, ctx: Ctx, scope: str) -> list[Step]:
        self.check_scope(scope)
        if scope == "project":
            steps: list[Step] = []
            if self.cli_present(ctx):
                code, out = ctx.run(["codex", "plugin", "remove", NEEDLE])
                steps.append(cleanup_step(self.name, "plugin global scos", code, out))
                code, out = ctx.run(["codex", "plugin", "marketplace", "remove", MARKETPLACE])
                steps.append(cleanup_step(self.name, "marketplace global scos", code, out))
            self.forget(ctx, "global")
            if _remove_toml_table(self._home_cfg(ctx), TABLE):
                steps.append(Step(self.name, "bloc global scos", "ok", "ramane doar in folderul proiectului"))
            steps.append(self._write_project_block(ctx))
            self.record(ctx, "project", {"kind": "toml-table", "path": str(self._project_cfg(ctx)), "table": TABLE})
            return steps

        if not self.cli_present(ctx):
            return [Step(self.name, "install", "skipped", "CLI-ul 'codex' nu este in PATH")]
        steps = []
        code, out = ctx.run(["codex", "plugin", "marketplace", "add", ctx.source])
        steps.append(step_from_result(self.name, "marketplace add (global)", code, out))
        if code == 0 or "already" in out.lower():
            self.record(ctx, "global", {"kind": "marketplace", "name": MARKETPLACE})
        code, out = ctx.run(["codex", "plugin", "add", NEEDLE])
        steps.append(step_from_result(self.name, "plugin add (global)", code, out))
        if code == 0 or "already" in out.lower():
            self.record(ctx, "global", {"kind": "plugin", "name": NEEDLE})
        if _remove_toml_table(self._home_cfg(ctx), TABLE):
            steps.append(Step(self.name, "bloc manual scos", "ok", "il aduce acum pluginul"))
        if _remove_toml_table(self._project_cfg(ctx), TABLE):
            steps.append(Step(self.name, "bloc de proiect scos", "ok", "ramane doar global"))
        self.forget(ctx, "project")
        return steps

    def uninstall(self, ctx: Ctx, scope: str = "all") -> list[Step]:
        steps: list[Step] = []
        for sc in self.expand(scope):
            if sc == "project":
                if _remove_toml_table(self._project_cfg(ctx), TABLE):
                    steps.append(Step(self.name, "project uninstall", "ok", str(self._project_cfg(ctx))))
                else:
                    steps.append(Step(self.name, "project uninstall", "skipped", "nu exista in folderul proiectului"))
                self.forget(ctx, "project")
                continue
            if self.cli_present(ctx):
                code, out = ctx.run(["codex", "plugin", "remove", NEEDLE])
                steps.append(cleanup_step(self.name, "plugin remove (global)", code, out))
                code, out = ctx.run(["codex", "plugin", "marketplace", "remove", MARKETPLACE])
                steps.append(cleanup_step(self.name, "marketplace remove (global)", code, out))
            else:
                steps.append(Step(self.name, "global uninstall", "skipped", "CLI-ul 'codex' nu este in PATH"))
            _remove_toml_table(self._home_cfg(ctx), TABLE)
            self.forget(ctx, "global")
        return steps

    def update(self, ctx: Ctx, scope: str) -> list[Step]:
        self.check_scope(scope)
        if scope == "project":
            return [Step(self.name, "update", "skipped",
                         "serverul de proiect foloseste pachetul instalat; actualizeaza cu pip install -e .")]
        if not self.cli_present(ctx):
            return [Step(self.name, "update", "skipped", "CLI-ul 'codex' nu este in PATH")]
        steps = []
        code, out = ctx.run(["codex", "plugin", "marketplace", "upgrade", MARKETPLACE])
        steps.append(step_from_result(self.name, "marketplace upgrade", code, out))
        code, out = ctx.run(["codex", "plugin", "add", NEEDLE])
        steps.append(step_from_result(self.name, "plugin refresh", code, out))
        return steps

    def doctor(self, ctx: Ctx) -> list[Step]:
        steps: list[Step] = []
        present: list[str] = []
        if self.cli_present(ctx):
            code, out = ctx.run(["codex", "plugin", "list"])
            global_ok = NEEDLE in out
        else:
            global_ok = False
            steps.append(Step(self.name, "global", "skipped", "CLI-ul 'codex' nu este in PATH"))
        if global_ok:
            present.append("global")
            steps.append(Step(self.name, "global", "ok", "instalat (plugin)"))
        elif self.cli_present(ctx):
            steps.append(Step(self.name, "global", "skipped", "nu e instalat global"))

        cfg = self._project_cfg(ctx)
        project_ok = cfg.exists() and f"[{TABLE}]" in cfg.read_text(encoding="utf-8")
        if project_ok:
            present.append("project")
            steps.append(Step(self.name, "project", "ok", f"instalat (MCP in {cfg})"))
        else:
            steps.append(Step(self.name, "project", "skipped", "nu e instalat in folderul proiectului"))
        if not present:
            steps.append(Step(self.name, "status", "error", "nu e instalat nici global, nici in folderul proiectului"))
        return steps
