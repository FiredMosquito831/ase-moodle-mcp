"""Claude Code: marketplace + plugin, pe scop 'user' (global) sau 'project' (folderul proiectului).

Particularitati (de aceea adaptorul e separat):
- `claude plugin list` arata pluginurile vizibile DIN FOLDERUL in care rulezi comanda. Pluginul de proiect
  apare doar cand rulezi din folderul lui. Verificarea pe fiecare scop se face deci din folderul corespunzator.
- Scopul 'project' scrie in .claude/settings.json din folder (extraKnownMarketplaces + enabledPlugins).
- Scopul 'global' e 'user'. Un plugin instalat pe ambele scopuri ar dubla serverul, deci schimbarea de scop
  curata celalalt scop.
- Pluginul nou intra in vigoare abia dupa repornirea Claude Code.
- Serverul MCP adaugat manual (`claude mcp add`) ar dubla serverul din plugin: il scoatem la instalare.
"""

from __future__ import annotations

import re
import shutil

from .base import MARKETPLACE, PLUGIN, Capabilities, Ctx, Harness, Step, cleanup_step, step_from_result

NEEDLE = f"{PLUGIN}@{MARKETPLACE}"
MCP_NAME = f"plugin:{PLUGIN}:{PLUGIN}"


def _claude_scope(scope: str) -> str:
    return "user" if scope == "global" else "project"


def listed_scope(text: str, needle: str) -> str | None:
    """Scopul din `claude plugin list` ('Scope: user|project|local'). None daca nu e gasit."""
    idx = text.find(needle)
    if idx < 0:
        return None
    match = re.search(r"Scope:\s*(\w+)", text[idx:idx + 300])
    if not match:
        return None
    scope = match.group(1).lower()
    return "global" if scope == "user" else scope


class ClaudeHarness(Harness):
    name = "claude"
    cli = "claude"
    capabilities = Capabilities(
        scopes=("global", "project"),
        needs_restart=True,
        notes="global = scope user; project = scope project (.claude/settings.json in folderul proiectului)",
    )

    def _cwd(self, ctx: Ctx, scope: str):
        return ctx.project_dir if scope == "project" else None

    def install(self, ctx: Ctx, scope: str) -> list[Step]:
        self.check_scope(scope)
        if not self.cli_present(ctx):
            return [Step(self.name, "install", "skipped", "CLI-ul 'claude' nu este in PATH")]
        s, cwd = _claude_scope(scope), self._cwd(ctx, scope)
        steps: list[Step] = []

        code, out = ctx.run(["claude", "plugin", "marketplace", "add", ctx.source, "--scope", s], cwd=cwd)
        steps.append(step_from_result(self.name, f"marketplace add ({scope})", code, out))
        if code == 0 or "already" in out.lower():
            self.record(ctx, scope, {"kind": "marketplace", "scope": s})

        code, out = ctx.run(["claude", "plugin", "install", NEEDLE, "--scope", s, "-y"], cwd=cwd)
        steps.append(step_from_result(self.name, f"plugin install ({scope})", code, out))
        if code == 0 or "already" in out.lower():
            self.record(ctx, scope, {"kind": "plugin", "scope": s})

        # Serverul MCP adaugat manual, in oricare scop, ar dubla pluginul.
        ctx.run(["claude", "mcp", "remove", PLUGIN, "--scope", "user"])
        ctx.run(["claude", "mcp", "remove", PLUGIN, "--scope", "project"], cwd=ctx.project_dir)

        # Celalalt scop se curata: un singur server, in locul in care vrei.
        other = "project" if scope == "global" else "global"
        code, out = ctx.run(["claude", "plugin", "uninstall", NEEDLE, "--scope", _claude_scope(other), "-y"],
                            cwd=self._cwd(ctx, other))
        ctx.run(["claude", "plugin", "marketplace", "remove", MARKETPLACE, "--scope", _claude_scope(other)],
                cwd=self._cwd(ctx, other))
        steps.append(cleanup_step(self.name, f"scope {other} curatat", code, out))
        self.forget(ctx, other)

        legacy = ctx.home / ".claude" / "skills" / PLUGIN
        if (legacy / "SKILL.md").exists() and "name: ase-moodle" in (legacy / "SKILL.md").read_text(encoding="utf-8"):
            shutil.rmtree(legacy)
            steps.append(Step(self.name, "legacy skill", "ok", "copia manuala eliminata (o aduce plugin-ul)"))
        steps.append(Step(self.name, "restart", "ok", "reporneste Claude Code in folderul proiectului"))
        return steps

    def uninstall(self, ctx: Ctx, scope: str = "all") -> list[Step]:
        if not self.cli_present(ctx):
            return [Step(self.name, "uninstall", "skipped", "CLI-ul 'claude' nu este in PATH")]
        steps: list[Step] = []
        for sc in self.expand(scope):
            s, cwd = _claude_scope(sc), self._cwd(ctx, sc)
            code, out = ctx.run(["claude", "plugin", "uninstall", NEEDLE, "--scope", s, "-y"], cwd=cwd)
            steps.append(cleanup_step(self.name, f"plugin uninstall ({sc})", code, out))
            code, out = ctx.run(["claude", "plugin", "marketplace", "remove", MARKETPLACE, "--scope", s], cwd=cwd)
            steps.append(cleanup_step(self.name, f"marketplace remove ({sc})", code, out))
            self.forget(ctx, sc)
        return steps

    def update(self, ctx: Ctx, scope: str) -> list[Step]:
        self.check_scope(scope)
        if not self.cli_present(ctx):
            return [Step(self.name, "update", "skipped", "CLI-ul 'claude' nu este in PATH")]
        steps = []
        code, out = ctx.run(["claude", "plugin", "marketplace", "update", MARKETPLACE])
        steps.append(step_from_result(self.name, "marketplace update", code, out))
        code, out = ctx.run(["claude", "plugin", "update", NEEDLE, "--scope", _claude_scope(scope), "-y"],
                            cwd=self._cwd(ctx, scope))
        steps.append(step_from_result(self.name, f"plugin update ({scope})", code, out))
        steps.append(Step(self.name, "restart", "ok", "reporneste Claude Code ca sa intre in vigoare"))
        return steps

    def doctor(self, ctx: Ctx) -> list[Step]:
        """Verifica fiecare scop din folderul lui: asa il vede Claude Code."""
        if not self.cli_present(ctx):
            return [Step(self.name, "status", "skipped", "CLI-ul 'claude' nu este in PATH")]
        steps: list[Step] = []
        present: list[str] = []
        for sc in self.capabilities.scopes:
            code, out = ctx.run(["claude", "plugin", "list"], cwd=self._cwd(ctx, sc))
            # Un plugin global apare si din folderul proiectului: conteaza eticheta scopului, nu doar numele.
            found = listed_scope(out, NEEDLE) == sc
            if found:
                present.append(sc)
            steps.append(Step(self.name, f"plugin ({sc})", "ok" if found else "skipped",
                              "instalat" if found else f"nu e instalat in scopul {sc}"))
        code, out = ctx.run(["claude", "mcp", "list"], cwd=ctx.project_dir)
        connected = MCP_NAME in out and "Connected" in out
        if present:
            steps.append(Step(self.name, "mcp server", "ok" if connected else "warning",
                              "conectat" if connected else "pluginul e instalat, dar serverul nu e conectat: reporneste Claude Code"))
        else:
            steps.append(Step(self.name, "status", "error", "nu e instalat nici global, nici in folderul proiectului"))
        return steps
