"""Instalare, update, verificare si dezinstalare in Claude Code, Codex, opencode si Google Antigravity (agy).

Fiecare CLI se configureaza prin mecanismul lui nativ, pe un scop:
- global  (implicit): pentru tot calculatorul (contul tau, toate folderele)
- project: doar pentru folderul proiectului (--project-dir, implicit folderul curent)

Pe scopuri:
- Claude Code: global = scope user; project = scope project (.claude/settings.json in folder)
- Codex: global = plugin + marketplace (~/.codex); project = serverul MCP in .codex/config.toml din folder
  (Codex cere sa marchezi folderul ca proiect de incredere, prima data)
- opencode: global = ~/.config/opencode/opencode.json; project = opencode.json din folder
- Antigravity (agy): doar global; nu are instalare pe proiect

Scopul schimbat curata celalalt scop, ca sa nu existe doua servere care sa se dubleze.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .config import find_dotenv, load_settings

PLUGIN = "ase-moodle"
MARKETPLACE = "ase-moodle-marketplace"
DEFAULT_SOURCE = "FiredMosquito831/ase-moodle"
TARGETS = ("claude", "codex", "opencode", "antigravity")
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
class Env:
    home: Path = field(default_factory=Path.home)
    source: str = ""
    project_dir: Path = field(default_factory=Path.cwd)
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


def repo_root() -> Path | None:
    """Radacina repo-ului cand pachetul ruleaza din sursa (pip install -e), altfel None."""
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude-plugin" / "marketplace.json").exists():
            return parent
    return None


def default_source() -> str:
    root = repo_root()
    return str(root) if root else DEFAULT_SOURCE


def server_command(python: str) -> list[str]:
    return [python, "-m", "ase_moodle.mcp_server"]


def skill_text() -> str:
    from importlib import resources

    return resources.files("ase_moodle").joinpath("data/SKILL.md").read_text(encoding="utf-8")


def sync_plugin_skill(root: Path) -> Path:
    """Copiaza SKILL.md canonic (din pachet) in plugin, ca sa ramana identice."""
    target = root / "plugins" / PLUGIN / "skills" / PLUGIN / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(skill_text(), encoding="utf-8")
    return target


def _scopes(scope: str) -> list[str]:
    if scope == "all":
        return list(SCOPES)
    if scope not in SCOPES:
        raise ValueError(f"Scop necunoscut: {scope}. Valide: global, project, all")
    return [scope]


def _cwd(env: Env, scope: str) -> Path | None:
    return env.project_dir if scope == "project" else None


def _claude_scope(scope: str) -> str:
    return "project" if scope == "project" else "user"


def _step(target: str, action: str, code: int, out: str) -> Step:
    tail = out[-400:] if out else ""
    if code == 0 or "already" in out.lower():
        return Step(target, action, "ok", tail)
    return Step(target, action, "error", tail or f"cod {code}")


def _cleanup(target: str, action: str, code: int, out: str) -> Step:
    """Pas de curatare: 'nu era instalat' nu e eroare."""
    if code == 0:
        return Step(target, action, "ok", out[-200:])
    return Step(target, action, "ok", "nimic de curatat (nu era instalat)")


def _remove_toml_tables(path: Path, prefix: str) -> int:
    """Sterge din config.toml tabelul [prefix] si subtabelele [prefix.*]. Returneaza cate tabele au fost scoase."""
    if not path.exists():
        return 0
    header = re.compile(r"^\s*\[\[?([^\]]+)\]\]?\s*$")
    keep: list[str] = []
    removed = 0
    skipping = False
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        m = header.match(line)
        if m:
            name = m.group(1).strip()
            if name == prefix or name.startswith(prefix + "."):
                skipping = True
                if name == prefix:
                    removed += 1
                continue
            skipping = False
        if not skipping:
            keep.append(line)
    if removed:
        path.write_text("".join(keep), encoding="utf-8")
    return removed


def _backup(path: Path) -> None:
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {"$schema": "https://opencode.ai/config.json"}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------- Claude Code ----------

def install_claude(env: Env, scope: str = "global") -> list[Step]:
    if env.which("claude") is None:
        return [Step("claude", "install", "skipped", "CLI-ul 'claude' nu este in PATH")]
    s, cwd = _claude_scope(scope), _cwd(env, scope)
    steps = []
    code, out = env.run(["claude", "plugin", "marketplace", "add", env.source, "--scope", s], cwd=cwd)
    steps.append(_step("claude", f"marketplace add ({scope})", code, out))
    code, out = env.run(["claude", "plugin", "install", f"{PLUGIN}@{MARKETPLACE}", "--scope", s, "-y"], cwd=cwd)
    steps.append(_step("claude", f"plugin install ({scope})", code, out))
    # Serverul MCP adaugat manual (in oricare scop) ar dubla pe cel din plugin.
    env.run(["claude", "mcp", "remove", PLUGIN, "--scope", "user"])
    env.run(["claude", "mcp", "remove", PLUGIN, "--scope", "project"], cwd=env.project_dir)
    other = "project" if scope == "global" else "global"
    code, out = env.run(["claude", "plugin", "uninstall", f"{PLUGIN}@{MARKETPLACE}", "--scope",
                         _claude_scope(other), "-y"], cwd=_cwd(env, other))
    env.run(["claude", "plugin", "marketplace", "remove", MARKETPLACE, "--scope", _claude_scope(other)],
            cwd=_cwd(env, other))
    steps.append(_cleanup("claude", f"scope {other} curatat", code, out))
    legacy = env.home / ".claude" / "skills" / PLUGIN
    if (legacy / "SKILL.md").exists() and "name: ase-moodle" in (legacy / "SKILL.md").read_text(encoding="utf-8"):
        shutil.rmtree(legacy)
        steps.append(Step("claude", "legacy skill", "ok", "copia manuala eliminata (o aduce plugin-ul)"))
    return steps


def uninstall_claude(env: Env, scope: str = "all") -> list[Step]:
    if env.which("claude") is None:
        return [Step("claude", "uninstall", "skipped", "CLI-ul 'claude' nu este in PATH")]
    steps = []
    for sc in _scopes(scope):
        s, cwd = _claude_scope(sc), _cwd(env, sc)
        code, out = env.run(["claude", "plugin", "uninstall", f"{PLUGIN}@{MARKETPLACE}", "--scope", s, "-y"], cwd=cwd)
        steps.append(_cleanup("claude", f"plugin uninstall ({sc})", code, out))
        code, out = env.run(["claude", "plugin", "marketplace", "remove", MARKETPLACE, "--scope", s], cwd=cwd)
        steps.append(_cleanup("claude", f"marketplace remove ({sc})", code, out))
    return steps


# ---------- Codex ----------

BLOCK_PREFIX = f"mcp_servers.{PLUGIN}"


def _codex_project_cfg(env: Env) -> Path:
    return env.project_dir / ".codex" / "config.toml"


def _write_codex_project_block(env: Env) -> Step:
    cfg = _codex_project_cfg(env)
    cfg.parent.mkdir(parents=True, exist_ok=True)
    _remove_toml_tables(cfg, BLOCK_PREFIX)
    text = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
    if text and not text.endswith("\n"):
        text += "\n"
    # Sirurile literale (apostrof) nu au nevoie de escape pentru caile Windows.
    block = f"\n[{BLOCK_PREFIX}]\ncommand = '{env.python}'\nargs = [\"-m\", \"ase_moodle.mcp_server\"]\n"
    cfg.write_text(text + block, encoding="utf-8")
    return Step("codex", "project mcp", "ok",
                f"{cfg} (Codex cere sa marchezi folderul ca proiect de incredere)")


def install_codex(env: Env, scope: str = "global") -> list[Step]:
    if scope == "project":
        steps = []
        if env.which("codex") is not None:
            code, out = env.run(["codex", "plugin", "remove", f"{PLUGIN}@{MARKETPLACE}"])
            steps.append(_cleanup("codex", "global plugin removed", code, out))
            code, out = env.run(["codex", "plugin", "marketplace", "remove", MARKETPLACE])
            steps.append(_cleanup("codex", "global marketplace removed", code, out))
        if _remove_toml_tables(env.home / ".codex" / "config.toml", BLOCK_PREFIX):
            steps.append(Step("codex", "global mcp block", "ok", "scos blocul global (ramane doar in proiect)"))
        steps.append(_write_codex_project_block(env))
        return steps

    if env.which("codex") is None:
        return [Step("codex", "install", "skipped", "CLI-ul 'codex' nu este in PATH")]
    steps = []
    code, out = env.run(["codex", "plugin", "marketplace", "add", env.source])
    steps.append(_step("codex", "marketplace add", code, out))
    code, out = env.run(["codex", "plugin", "add", f"{PLUGIN}@{MARKETPLACE}"])
    steps.append(_step("codex", "plugin add", code, out))
    if _remove_toml_tables(env.home / ".codex" / "config.toml", BLOCK_PREFIX):
        steps.append(Step("codex", "legacy mcp block", "ok", "scos blocul manual global (il aduce plugin-ul)"))
    if _remove_toml_tables(_codex_project_cfg(env), BLOCK_PREFIX):
        steps.append(Step("codex", "project mcp block", "ok", "scos blocul de proiect (ramane doar global)"))
    return steps


def uninstall_codex(env: Env, scope: str = "all") -> list[Step]:
    steps = []
    for sc in _scopes(scope):
        if sc == "project":
            if _remove_toml_tables(_codex_project_cfg(env), BLOCK_PREFIX):
                steps.append(Step("codex", "project mcp removed", "ok", str(_codex_project_cfg(env))))
            else:
                steps.append(Step("codex", "project mcp removed", "skipped", "nu exista in folderul proiectului"))
            continue
        if env.which("codex") is None:
            steps.append(Step("codex", "uninstall (global)", "skipped", "CLI-ul 'codex' nu este in PATH"))
            continue
        code, out = env.run(["codex", "plugin", "remove", f"{PLUGIN}@{MARKETPLACE}"])
        steps.append(_cleanup("codex", "plugin remove (global)", code, out))
        code, out = env.run(["codex", "plugin", "marketplace", "remove", MARKETPLACE])
        steps.append(_cleanup("codex", "marketplace remove (global)", code, out))
    return steps


# ---------- opencode ----------

def _opencode_global_cfg(env: Env) -> Path:
    return env.home / ".config" / "opencode" / "opencode.json"


def _opencode_project_cfg(env: Env) -> Path:
    return env.project_dir / "opencode.json"


def _instruction_entry(env: Env) -> str:
    return (env.home / ".config" / "opencode" / PLUGIN / "SKILL.md").as_posix()


def _drop_opencode(cfg: Path, instruction: str | None) -> bool:
    """Scoate intrarea ase-moodle din mcp (si instructiunea, daca e data). Returneaza daca a schimbat ceva."""
    if not cfg.exists():
        return False
    data = _read_json(cfg)
    changed = data.get("mcp", {}).pop(PLUGIN, None) is not None
    if instruction and instruction in data.get("instructions", []):
        data["instructions"].remove(instruction)
        changed = True
    if changed:
        _backup(cfg)
        _write_json(cfg, data)
    return changed


def _install_opencode_project(env: Env) -> list[Step]:
    cfg = _opencode_project_cfg(env)
    try:
        data = _read_json(cfg)
    except json.JSONDecodeError as exc:
        return [Step("opencode", "project config", "error", f"{cfg} nu este JSON valid: {exc}")]
    _backup(cfg)
    data.setdefault("mcp", {})[PLUGIN] = {"type": "local", "command": server_command(env.python), "enabled": True}
    _write_json(cfg, data)
    steps = [Step("opencode", "project mcp", "ok", f"{cfg} (comanda contine calea Python a acestui calculator)")]
    if _drop_opencode(_opencode_global_cfg(env), _instruction_entry(env)):
        steps.append(Step("opencode", "global cleanup", "ok", "scos mcp si instructiuni globale"))
    return steps


def install_opencode(env: Env, scope: str = "global") -> list[Step]:
    if scope == "project":
        return _install_opencode_project(env)
    cfg_dir = env.home / ".config" / "opencode"
    cfg = _opencode_global_cfg(env)
    try:
        data = _read_json(cfg)
    except json.JSONDecodeError as exc:
        return [Step("opencode", "config", "error", f"{cfg} nu este JSON valid: {exc}")]
    _backup(cfg)
    data.setdefault("mcp", {})[PLUGIN] = {
        "type": "local",
        "command": server_command(env.python),
        "enabled": True,
    }
    skill_path = cfg_dir / PLUGIN / "SKILL.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(skill_text(), encoding="utf-8")
    instructions = data.setdefault("instructions", [])
    entry = skill_path.as_posix()
    if entry not in instructions:
        instructions.append(entry)
    _write_json(cfg, data)
    steps = [
        Step("opencode", "mcp server", "ok", f"{cfg}: mcp.{PLUGIN}"),
        Step("opencode", "instructions", "ok", entry),
    ]
    if _drop_opencode(_opencode_project_cfg(env), None):
        steps.append(Step("opencode", "project cleanup", "ok", "scos mcp din opencode.json-ul proiectului"))
    return steps


def uninstall_opencode(env: Env, scope: str = "all") -> list[Step]:
    steps = []
    for sc in _scopes(scope):
        if sc == "project":
            if _drop_opencode(_opencode_project_cfg(env), None):
                steps.append(Step("opencode", "project uninstall", "ok", "mcp scos din opencode.json-ul proiectului"))
            else:
                steps.append(Step("opencode", "project uninstall", "skipped", "nu exista in folderul proiectului"))
            continue
        cfg = _opencode_global_cfg(env)
        if not cfg.exists():
            steps.append(Step("opencode", "global uninstall", "skipped", "nu exista opencode.json"))
            continue
        _drop_opencode(cfg, _instruction_entry(env))
        shutil.rmtree(cfg.parent / PLUGIN, ignore_errors=True)
        steps.append(Step("opencode", "global uninstall", "ok", "mcp si instructiuni eliminate"))
    return steps


# ---------- Google Antigravity (doar global) ----------

ANTIGRAVITY_PROJECT_SKIP = "Antigravity nu are instalare pe proiect; ramane global"


def _plugin_dir_for(env: Env) -> Path | None:
    """Folderul plugin-ului: din repo local sau dintr-un clone GitHub in ~/.ase-moodle/repo."""
    src = Path(env.source)
    if src.is_dir():
        return src / "plugins" / PLUGIN
    clone = env.home / ".ase-moodle" / "repo"
    if clone.exists():
        env.run(["git", "-C", str(clone), "pull", "--ff-only"])
    else:
        clone.parent.mkdir(parents=True, exist_ok=True)
        code, out = env.run(["git", "clone", f"https://github.com/{env.source}.git", str(clone)])
        if code != 0:
            return None
    return clone / "plugins" / PLUGIN


def install_antigravity(env: Env, scope: str = "global") -> list[Step]:
    if scope == "project":
        return [Step("antigravity", "install", "skipped", ANTIGRAVITY_PROJECT_SKIP)]
    if env.which("agy") is None:
        return [Step("antigravity", "install", "skipped", "CLI-ul 'agy' nu este in PATH")]
    steps = []
    code, out = env.run(["agy", "mcp", "add", PLUGIN, "--", env.python, "-m", "ase_moodle.mcp_server"])
    steps.append(_step("antigravity", "mcp add", code, out))
    plugin_dir = _plugin_dir_for(env)
    if plugin_dir is None:
        steps.append(Step("antigravity", "plugin install", "error", "nu am putut obtine folderul plugin-ului"))
    else:
        code, out = env.run(["agy", "plugin", "install", str(plugin_dir)])
        steps.append(_step("antigravity", "plugin install", code, out))
    return steps


def uninstall_antigravity(env: Env, scope: str = "all") -> list[Step]:
    if scope == "project":
        return [Step("antigravity", "uninstall", "skipped", ANTIGRAVITY_PROJECT_SKIP)]
    if env.which("agy") is None:
        return [Step("antigravity", "uninstall", "skipped", "CLI-ul 'agy' nu este in PATH")]
    code, out = env.run(["agy", "mcp", "remove", PLUGIN])
    steps = [_cleanup("antigravity", "mcp remove", code, out)]
    code, out = env.run(["agy", "plugin", "uninstall", PLUGIN])
    steps.append(_cleanup("antigravity", "plugin uninstall", code, out))
    return steps


INSTALLERS = {
    "claude": install_claude,
    "codex": install_codex,
    "opencode": install_opencode,
    "antigravity": install_antigravity,
}
UNINSTALLERS = {
    "claude": uninstall_claude,
    "codex": uninstall_codex,
    "opencode": uninstall_opencode,
    "antigravity": uninstall_antigravity,
}


def _targets(names: list[str] | None) -> list[str]:
    if not names or "all" in names:
        return list(TARGETS)
    unknown = [n for n in names if n not in TARGETS]
    if unknown:
        raise ValueError(f"Tinte necunoscute: {unknown}. Valide: {', '.join(TARGETS)} sau all")
    return names


def install(names: list[str] | None = None, env: Env | None = None, scope: str = "global") -> list[Step]:
    env = env or Env(source=default_source())
    if scope not in SCOPES:
        raise ValueError(f"Scop necunoscut: {scope}. Valide: global, project")
    steps: list[Step] = []
    for name in _targets(names):
        steps += INSTALLERS[name](env, scope)
    return steps


def uninstall(names: list[str] | None = None, env: Env | None = None, scope: str = "all") -> list[Step]:
    env = env or Env(source=default_source())
    _scopes(scope)
    steps: list[Step] = []
    for name in _targets(names):
        steps += UNINSTALLERS[name](env, scope)
    return steps


def update(names: list[str] | None = None, env: Env | None = None, scope: str = "global") -> list[Step]:
    """Actualizeaza pluginul: Claude si Codex refac marketplace-ul si plugin-ul; opencode si Antigravity se rescriu."""
    env = env or Env(source=default_source())
    if scope not in SCOPES:
        raise ValueError(f"Scop necunoscut: {scope}. Valide: global, project")
    steps: list[Step] = []
    for name in _targets(names):
        if name == "claude":
            if env.which("claude") is None:
                steps.append(Step("claude", "update", "skipped", "CLI-ul 'claude' nu este in PATH"))
                continue
            code, out = env.run(["claude", "plugin", "marketplace", "update", MARKETPLACE])
            steps.append(_step("claude", "marketplace update", code, out))
            code, out = env.run(["claude", "plugin", "update", f"{PLUGIN}@{MARKETPLACE}", "--scope",
                                 _claude_scope(scope), "-y"], cwd=_cwd(env, scope))
            steps.append(_step("claude", f"plugin update ({scope})", code, out))
            steps.append(Step("claude", "restart", "ok", "reporneste Claude Code ca sa intre in vigoare"))
        elif name == "codex":
            if scope == "project":
                steps.append(Step("codex", "update", "skipped",
                                  "MCP de proiect foloseste pachetul instalat; se actualizeaza cu pip install -e ."))
                continue
            if env.which("codex") is None:
                steps.append(Step("codex", "update", "skipped", "CLI-ul 'codex' nu este in PATH"))
                continue
            code, out = env.run(["codex", "plugin", "marketplace", "upgrade", MARKETPLACE])
            steps.append(_step("codex", "marketplace upgrade", code, out))
            code, out = env.run(["codex", "plugin", "add", f"{PLUGIN}@{MARKETPLACE}"])
            steps.append(_step("codex", "plugin refresh", code, out))
        else:
            steps += INSTALLERS[name](env, scope)
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


def _listed_scope(text: str, needle: str) -> str:
    """Scopul in care apare pluginul in lista CLI-ului (Claude: 'Scope: user|project|local'). Implicit: global."""
    idx = text.find(needle)
    match = re.search(r"Scope:\s*(\w+)", text[idx:idx + 300]) if idx >= 0 else None
    if not match:
        return "global"
    scope = match.group(1).lower()
    return "global" if scope == "user" else scope


def doctor(env: Env | None = None) -> list[Step]:
    """Verifica starea fiecarei instalari, fara sa modifice nimic."""
    env = env or Env(source=default_source())
    steps: list[Step] = []
    try:
        load_settings()
        steps.append(Step("package", "token", "ok", "token gasit"))
    except Exception as exc:  # noqa: BLE001
        steps.append(Step("package", "token", "error", str(exc)))
    steps.append(Step("package", "ase-moodle-mcp in PATH", "ok" if env.which("ase-moodle-mcp") else "error",
                      env.which("ase-moodle-mcp") or "lipseste; ruleaza pip install -e ."))

    def check(target: str, cmd: list[str], needle: str, project_ok: bool = False) -> None:
        """Global: CLI-ul listeaza pluginul. Project: project_ok spune ca instalarea de proiect exista."""
        if env.which(cmd[0]) is None:
            if project_ok:
                steps.append(Step(target, "status", "ok", "instalat (proiect; nu e global)"))
            else:
                steps.append(Step(target, "status", "skipped", f"{cmd[0]} nu este in PATH"))
            return
        code, out = env.run(cmd)
        if needle in out:
            steps.append(Step(target, "status", "ok", f"instalat ({_listed_scope(out, needle)})"))
        elif project_ok:
            steps.append(Step(target, "status", "ok", "instalat (proiect; nu e global)"))
        else:
            steps.append(Step(target, "status", "error", "nu apare in lista"))

    codex_cfg = _codex_project_cfg(env)
    codex_project = codex_cfg.exists() and f"[{BLOCK_PREFIX}]" in codex_cfg.read_text(encoding="utf-8")
    check("claude", ["claude", "plugin", "list"], f"{PLUGIN}@{MARKETPLACE}")
    check("codex", ["codex", "plugin", "list"], PLUGIN, project_ok=codex_project)
    check("antigravity", ["agy", "mcp", "list"], PLUGIN)

    try:
        has_global = PLUGIN in _read_json(_opencode_global_cfg(env)).get("mcp", {})
        has_project = PLUGIN in _read_json(_opencode_project_cfg(env)).get("mcp", {})
        if has_global:
            steps.append(Step("opencode", "status", "ok", "instalat (global)"))
        elif has_project:
            steps.append(Step("opencode", "status", "ok", "instalat (proiect; nu e global)"))
        else:
            steps.append(Step("opencode", "status", "error", "lipseste mcp (nici global, nici in proiect)"))
    except (OSError, json.JSONDecodeError) as exc:
        steps.append(Step("opencode", "status", "error", str(exc)))

    # Instalari pe folderul proiectului (optionale)
    steps.append(Step("project", "folder", "ok", str(env.project_dir)))
    codex_proj = _codex_project_cfg(env)
    has_codex = codex_proj.exists() and f"[{BLOCK_PREFIX}]" in codex_proj.read_text(encoding="utf-8")
    steps.append(Step("project", "codex .codex/config.toml", "ok" if has_codex else "skipped",
                      "instalat (proiect)" if has_codex else "nu e instalat pe proiect"))
    try:
        has_oc = PLUGIN in _read_json(_opencode_project_cfg(env)).get("mcp", {})
        steps.append(Step("project", "opencode opencode.json", "ok" if has_oc else "skipped",
                          "instalat (proiect)" if has_oc else "nu e instalat pe proiect"))
    except (OSError, json.JSONDecodeError) as exc:
        steps.append(Step("project", "opencode opencode.json", "error", str(exc)))

    # Mediu si securitate
    try:
        settings = load_settings()
        steps.append(Step("security", "token source", "ok", f"{settings.source} (tokenul nu se afiseaza)"))
        dotenv = find_dotenv()
        steps.append(Step("security", ".env", "ok", str(dotenv) if dotenv else "nu exista (optional)"))
    except Exception as exc:  # noqa: BLE001
        steps.append(Step("security", "token source", "error", str(exc)))

    running = _running_mcp_processes()
    steps.append(Step("package", "procese MCP pornite", "ok" if running == 0 else "warning",
                      f"{running} proces(e) ase-moodle-mcp. Inchide-le inainte de pip install -e . dupa update"))
    try:
        from importlib.metadata import version

        steps.append(Step("package", "metadate pachet", "ok", f"versiunea {version('ase-moodle')}"))
    except Exception as exc:  # noqa: BLE001
        steps.append(Step("package", "metadate pachet", "warning",
                          f"metadatele sunt rupte ({exc.__class__.__name__}); ruleaza pip install -e . dupa inchiderea MCP"))
    return steps
