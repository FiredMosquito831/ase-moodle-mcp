"""Instalare, verificare si dezinstalare in Claude Code, Codex, opencode si Google Antigravity (agy).

Fiecare CLI se configureaza prin mecanismul lui nativ:
- Claude Code: marketplace + plugin (claude plugin ...)
- Codex: marketplace + plugin (codex plugin ...)
- opencode: serverul MCP si instructiunile in ~/.config/opencode/opencode.json
- Antigravity: serverul MCP (agy mcp add) si plugin-ul cu skill (agy plugin install)
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

Runner = Callable[[list[str]], tuple[int, str]]


def default_run(cmd: list[str]) -> tuple[int, str]:
    exe = shutil.which(cmd[0])
    if exe is None:
        return 127, f"{cmd[0]} nu este in PATH"
    proc = subprocess.run(
        [exe, *cmd[1:]], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


@dataclass
class Env:
    home: Path = field(default_factory=Path.home)
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


def _step(target: str, action: str, code: int, out: str) -> Step:
    tail = out[-400:] if out else ""
    if code == 0 or "already" in out.lower():
        return Step(target, action, "ok", tail)
    return Step(target, action, "error", tail or f"cod {code}")


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

def install_claude(env: Env) -> list[Step]:
    if env.which("claude") is None:
        return [Step("claude", "install", "skipped", "CLI-ul 'claude' nu este in PATH")]
    steps = []
    code, out = env.run(["claude", "plugin", "marketplace", "add", env.source, "--scope", "user"])
    steps.append(_step("claude", "marketplace add", code, out))
    code, out = env.run(["claude", "plugin", "install", f"{PLUGIN}@{MARKETPLACE}", "--scope", "user", "-y"])
    steps.append(_step("claude", "plugin install", code, out))
    # Serverul MCP adaugat manual inainte ar dubla pe cel din plugin.
    env.run(["claude", "mcp", "remove", PLUGIN, "--scope", "user"])
    legacy = env.home / ".claude" / "skills" / PLUGIN
    if (legacy / "SKILL.md").exists() and "name: ase-moodle" in (legacy / "SKILL.md").read_text(encoding="utf-8"):
        shutil.rmtree(legacy)
        steps.append(Step("claude", "legacy skill", "ok", "copia manuala eliminata (o aduce plugin-ul)"))
    return steps


def uninstall_claude(env: Env) -> list[Step]:
    if env.which("claude") is None:
        return [Step("claude", "uninstall", "skipped", "CLI-ul 'claude' nu este in PATH")]
    code, out = env.run(["claude", "plugin", "uninstall", f"{PLUGIN}@{MARKETPLACE}"])
    steps = [_step("claude", "plugin uninstall", code, out)]
    code, out = env.run(["claude", "plugin", "marketplace", "remove", MARKETPLACE])
    steps.append(_step("claude", "marketplace remove", code, out))
    return steps


# ---------- Codex ----------

def install_codex(env: Env) -> list[Step]:
    if env.which("codex") is None:
        return [Step("codex", "install", "skipped", "CLI-ul 'codex' nu este in PATH")]
    steps = []
    code, out = env.run(["codex", "plugin", "marketplace", "add", env.source])
    steps.append(_step("codex", "marketplace add", code, out))
    code, out = env.run(["codex", "plugin", "add", f"{PLUGIN}@{MARKETPLACE}"])
    steps.append(_step("codex", "plugin add", code, out))
    removed = _remove_toml_tables(env.home / ".codex" / "config.toml", f"mcp_servers.{PLUGIN}")
    if removed:
        steps.append(Step("codex", "legacy mcp block", "ok", f"scos {removed} bloc manual (il aduce plugin-ul)"))
    return steps


def uninstall_codex(env: Env) -> list[Step]:
    if env.which("codex") is None:
        return [Step("codex", "uninstall", "skipped", "CLI-ul 'codex' nu este in PATH")]
    code, out = env.run(["codex", "plugin", "remove", f"{PLUGIN}@{MARKETPLACE}"])
    steps = [_step("codex", "plugin remove", code, out)]
    code, out = env.run(["codex", "plugin", "marketplace", "remove", MARKETPLACE])
    steps.append(_step("codex", "marketplace remove", code, out))
    return steps


# ---------- opencode ----------

def install_opencode(env: Env) -> list[Step]:
    cfg_dir = env.home / ".config" / "opencode"
    cfg = cfg_dir / "opencode.json"
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
    return [
        Step("opencode", "mcp server", "ok", f"{cfg}: mcp.{PLUGIN}"),
        Step("opencode", "instructions", "ok", entry),
    ]


def uninstall_opencode(env: Env) -> list[Step]:
    cfg_dir = env.home / ".config" / "opencode"
    cfg = cfg_dir / "opencode.json"
    if not cfg.exists():
        return [Step("opencode", "uninstall", "skipped", "nu exista opencode.json")]
    data = _read_json(cfg)
    _backup(cfg)
    data.get("mcp", {}).pop(PLUGIN, None)
    entry = (cfg_dir / PLUGIN / "SKILL.md").as_posix()
    if entry in data.get("instructions", []):
        data["instructions"].remove(entry)
    _write_json(cfg, data)
    shutil.rmtree(cfg_dir / PLUGIN, ignore_errors=True)
    return [Step("opencode", "uninstall", "ok", "mcp si instructiuni eliminate")]


# ---------- Google Antigravity ----------

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


def install_antigravity(env: Env) -> list[Step]:
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


def uninstall_antigravity(env: Env) -> list[Step]:
    if env.which("agy") is None:
        return [Step("antigravity", "uninstall", "skipped", "CLI-ul 'agy' nu este in PATH")]
    code, out = env.run(["agy", "mcp", "remove", PLUGIN])
    steps = [_step("antigravity", "mcp remove", code, out)]
    code, out = env.run(["agy", "plugin", "uninstall", PLUGIN])
    steps.append(_step("antigravity", "plugin uninstall", code, out))
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


def install(names: list[str] | None = None, env: Env | None = None) -> list[Step]:
    env = env or Env(source=default_source())
    steps: list[Step] = []
    for name in _targets(names):
        steps += INSTALLERS[name](env)
    return steps


def uninstall(names: list[str] | None = None, env: Env | None = None) -> list[Step]:
    env = env or Env(source=default_source())
    steps: list[Step] = []
    for name in _targets(names):
        steps += UNINSTALLERS[name](env)
    return steps


def update(names: list[str] | None = None, env: Env | None = None) -> list[Step]:
    """Actualizeaza pluginul: Claude si Codex refac marketplace-ul si plugin-ul; opencode si Antigravity se rescriu."""
    env = env or Env(source=default_source())
    steps: list[Step] = []
    for name in _targets(names):
        if name == "claude":
            if env.which("claude") is None:
                steps.append(Step("claude", "update", "skipped", "CLI-ul 'claude' nu este in PATH"))
                continue
            code, out = env.run(["claude", "plugin", "marketplace", "update", MARKETPLACE])
            steps.append(_step("claude", "marketplace update", code, out))
            code, out = env.run(["claude", "plugin", "update", f"{PLUGIN}@{MARKETPLACE}", "--scope", "user", "-y"])
            steps.append(_step("claude", "plugin update", code, out))
            steps.append(Step("claude", "restart", "ok", "reporneste Claude Code ca sa intre in vigoare"))
        elif name == "codex":
            if env.which("codex") is None:
                steps.append(Step("codex", "update", "skipped", "CLI-ul 'codex' nu este in PATH"))
                continue
            code, out = env.run(["codex", "plugin", "marketplace", "upgrade", MARKETPLACE])
            steps.append(_step("codex", "marketplace upgrade", code, out))
            code, out = env.run(["codex", "plugin", "add", f"{PLUGIN}@{MARKETPLACE}"])
            steps.append(_step("codex", "plugin refresh", code, out))
        else:
            steps += INSTALLERS[name](env)
    return steps


def _running_mcp_processes() -> int:
    if sys.platform != "win32":
        return 0
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq ase-moodle-mcp.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    return sum(1 for line in out.splitlines() if "ase-moodle-mcp" in line.lower())


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

    def check(target: str, cmd: list[str], needle: str) -> None:
        if env.which(cmd[0]) is None:
            steps.append(Step(target, "status", "skipped", f"{cmd[0]} nu este in PATH"))
            return
        code, out = env.run(cmd)
        found = needle in out
        steps.append(Step(target, "status", "ok" if found else "error",
                          "instalat" if found else "nu apare in lista"))

    check("claude", ["claude", "plugin", "list"], f"{PLUGIN}@{MARKETPLACE}")
    check("codex", ["codex", "plugin", "list"], PLUGIN)
    check("antigravity", ["agy", "mcp", "list"], PLUGIN)

    cfg = env.home / ".config" / "opencode" / "opencode.json"
    try:
        has = PLUGIN in _read_json(cfg).get("mcp", {})
        steps.append(Step("opencode", "status", "ok" if has else "error", "instalat" if has else "lipseste mcp"))
    except (OSError, json.JSONDecodeError) as exc:
        steps.append(Step("opencode", "status", "error", str(exc)))

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
