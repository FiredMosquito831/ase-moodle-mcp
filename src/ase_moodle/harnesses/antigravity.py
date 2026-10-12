"""Google Antigravity (agy): doar global. Serverul MCP + pluginul cu skill-uri.

Particularitati (de aceea adaptorul e separat):
- agy nu are scop de proiect. Cerere pe 'project' se refuza explicit (nu se sare in tacere).
- Serverul MCP se adauga cu `agy mcp add`; pluginul cu `agy plugin install <folder>`.
- Folderul pluginului: repo-ul local (daca sursa e o cale) sau un clone in ~/.ase-moodle/repo (daca e owner/repo).
- Pluginul trebuie sa aiba commands/ -> skill-uri; agy le converteste singur.
"""

from __future__ import annotations

from pathlib import Path

from .base import PLUGIN, Capabilities, Ctx, Harness, Step, cleanup_step, step_from_result


def plugin_dir_for(ctx: Ctx) -> Path | None:
    """Folderul pluginului: din repo local sau dintr-un clone GitHub in ~/.ase-moodle/repo."""
    src = Path(ctx.source)
    if src.is_dir():
        return src / "plugins" / PLUGIN
    clone = ctx.home / ".ase-moodle" / "repo"
    if clone.exists():
        ctx.run(["git", "-C", str(clone), "pull", "--ff-only"])
    else:
        clone.parent.mkdir(parents=True, exist_ok=True)
        code, _ = ctx.run(["git", "clone", f"https://github.com/{ctx.source}.git", str(clone)])
        if code != 0:
            return None
    return clone / "plugins" / PLUGIN


class AntigravityHarness(Harness):
    name = "antigravity"
    cli = "agy"
    capabilities = Capabilities(
        scopes=("global",),
        needs_restart=False,
        notes="agy nu are instalare pe proiect; instalarea ramane globala",
    )

    def install(self, ctx: Ctx, scope: str) -> list[Step]:
        self.check_scope(scope)
        if not self.cli_present(ctx):
            return [Step(self.name, "install", "skipped", "CLI-ul 'agy' nu este in PATH")]
        steps: list[Step] = []
        code, out = ctx.run(["agy", "mcp", "add", PLUGIN, "--", ctx.python, "-m", "ase_moodle.mcp_server"])
        steps.append(step_from_result(self.name, "mcp add", code, out))
        if code == 0 or "already" in out.lower():
            self.record(ctx, "global", {"kind": "agy-mcp", "name": PLUGIN})

        plugin_dir = plugin_dir_for(ctx)
        if plugin_dir is None:
            steps.append(Step(self.name, "plugin install", "error", "nu am putut obtine folderul pluginului"))
            return steps
        code, out = ctx.run(["agy", "plugin", "install", str(plugin_dir)])
        steps.append(step_from_result(self.name, "plugin install", code, out))
        if code == 0 or "already" in out.lower():
            self.record(ctx, "global", {"kind": "agy-plugin", "name": PLUGIN})
        return steps

    def uninstall(self, ctx: Ctx, scope: str = "all") -> list[Step]:
        self.expand(scope)  # 'all' = global; 'project' explicit e refuzat
        if not self.cli_present(ctx):
            return [Step(self.name, "uninstall", "skipped", "CLI-ul 'agy' nu este in PATH")]
        code, out = ctx.run(["agy", "mcp", "remove", PLUGIN])
        steps = [cleanup_step(self.name, "mcp remove", code, out)]
        code, out = ctx.run(["agy", "plugin", "uninstall", PLUGIN])
        steps.append(cleanup_step(self.name, "plugin uninstall", code, out))
        self.forget(ctx, "global")
        return steps

    def update(self, ctx: Ctx, scope: str) -> list[Step]:
        return self.install(ctx, scope)

    def doctor(self, ctx: Ctx) -> list[Step]:
        if not self.cli_present(ctx):
            return [Step(self.name, "status", "skipped", "CLI-ul 'agy' nu este in PATH")]
        code, out = ctx.run(["agy", "mcp", "list"])
        if PLUGIN in out:
            return [Step(self.name, "global", "ok", "instalat (serverul MCP apare in 'agy mcp list')")]
        return [Step(self.name, "status", "error", "nu apare in 'agy mcp list'")]
