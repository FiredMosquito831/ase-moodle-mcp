"""Teste pentru adaptoarele de harness: fiecare izolat, cu comenzile lui, scopurile lui si evidenta lui.

Totul ruleaza in foldere temporare, cu un runner fals. Nicio comanda reala, nicio scriere in configurarea ta.
"""

import json
import tempfile
import unittest
from pathlib import Path

from ase_moodle import cli, install
from ase_moodle.harnesses import REGISTRY, UnsupportedScope
from ase_moodle.harnesses.base import Ctx


class Recorder:
    """Runner fals: retine comenzile si cwd-ul, raspunde cu un cod si un text fixe."""

    def __init__(self, output: str = "", code: int = 0):
        self.commands: list[list[str]] = []
        self.cwds: list = []
        self.output = output
        self.code = code

    def __call__(self, cmd, cwd=None):
        self.commands.append(cmd)
        self.cwds.append(cwd)
        return self.code, self.output


class Scripted(Recorder):
    """Runner cu raspuns in functie de comanda si de cwd (ca sa imite `claude plugin list` din alte foldere)."""

    def __init__(self, answer):
        super().__init__()
        self.answer = answer

    def __call__(self, cmd, cwd=None):
        self.commands.append(cmd)
        self.cwds.append(cwd)
        return self.answer(cmd, cwd)


def make_env(home: Path, run=None, which=None, source: str = "C:/repo", project_dir: Path | None = None) -> Ctx:
    project = project_dir or (home / "proiect")
    project.mkdir(parents=True, exist_ok=True)
    return Ctx(
        home=home,
        source=source,
        project_dir=project,
        run=run or Recorder(),
        which=which or (lambda name: f"/bin/{name}"),
        python="C:/Python313/python.exe",
    )


class IsolatedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()

    def tearDown(self):
        self.tmp.cleanup()


class ClaudeTests(IsolatedTest):
    def test_project_install_uses_project_scope_from_project_folder(self):
        run = Recorder()
        env = make_env(self.home, run=run)
        REGISTRY["claude"].install(env, "project")
        add = run.commands[0]
        self.assertEqual(add[add.index("--scope") + 1], "project")
        self.assertEqual(Path(run.cwds[0]), env.project_dir)
        self.assertTrue(any("plugin uninstall ase-moodle@ase-moodle-marketplace --scope user" in " ".join(c)
                            for c in run.commands), "scopul user trebuie curatat")

    def test_install_records_state_only_for_its_harness_and_scope(self):
        env = make_env(self.home, run=Recorder())
        REGISTRY["claude"].install(env, "project")
        state = json.loads((self.home / ".ase-moodle" / "state" / "claude.json").read_text(encoding="utf-8"))
        key = f"project:{env.project_dir.resolve()}"
        self.assertIn(key, state)
        kinds = {item["kind"] for item in state[key]["items"]}
        self.assertEqual(kinds, {"marketplace", "plugin"})
        self.assertFalse((self.home / ".ase-moodle" / "state" / "codex.json").exists())

    def test_uninstall_all_covers_both_scopes_and_forgets_state(self):
        run = Recorder()
        env = make_env(self.home, run=run)
        REGISTRY["claude"].install(env, "project")
        run.commands.clear(); run.cwds.clear()
        REGISTRY["claude"].uninstall(env, "all")
        scopes = [c[c.index("--scope") + 1] for c in run.commands if "uninstall" in c]
        self.assertEqual(sorted(scopes), ["project", "user"])
        state = json.loads((self.home / ".ase-moodle" / "state" / "claude.json").read_text(encoding="utf-8"))
        self.assertNotIn(f"project:{env.project_dir.resolve()}", state)

    def test_update_project_uses_project_scope(self):
        run = Recorder()
        env = make_env(self.home, run=run)
        REGISTRY["claude"].update(env, "project")
        upd = next(c for c in run.commands if "update" in c and "ase-moodle@ase-moodle-marketplace" in c)
        self.assertEqual(upd[upd.index("--scope") + 1], "project")

    def test_doctor_checks_each_scope_from_its_own_folder(self):
        def answer(cmd, cwd):
            if cmd[:3] == ["claude", "plugin", "list"] and cwd is not None:
                return 0, "  ❯ ase-moodle@ase-moodle-marketplace\n    Scope: project\n"
            if cmd[:3] == ["claude", "plugin", "list"]:
                return 0, ""
            return 0, ""
        env = make_env(self.home, run=Scripted(answer))
        steps = {s.action: s for s in REGISTRY["claude"].doctor(env)}
        self.assertEqual(steps["plugin (project)"].status, "ok")
        self.assertEqual(steps["plugin (global)"].status, "skipped")

    def test_global_plugin_visible_from_project_is_not_counted_as_project(self):
        def answer(cmd, cwd):
            return 0, "  ❯ ase-moodle@ase-moodle-marketplace\n    Scope: user\n"
        env = make_env(self.home, run=Scripted(answer))
        steps = {s.action: s for s in REGISTRY["claude"].doctor(env)}
        self.assertEqual(steps["plugin (global)"].status, "ok")
        self.assertEqual(steps["plugin (project)"].status, "skipped")

    def test_missing_cli_is_skipped_not_error(self):
        steps = REGISTRY["claude"].install(make_env(self.home, which=lambda n: None), "global")
        self.assertEqual([s.status for s in steps], ["skipped"])


class CodexTests(IsolatedTest):
    CODEX_HOME = (
        '[features]\nfoo = 1\n\n'
        '[mcp_servers.context7]\ncommand = "npx"\n\n'
        '[mcp_servers.ase-moodle]\ncommand = "ase-moodle-mcp"\n\n'
        '[mcp_servers.ase-moodle.env]\nX = "1"\n'
    )

    def test_project_install_writes_only_its_table_and_no_plugin_add(self):
        run = Recorder()
        env = make_env(self.home, run=run)
        (self.home / ".codex").mkdir()
        (self.home / ".codex" / "config.toml").write_text(self.CODEX_HOME, encoding="utf-8")
        REGISTRY["codex"].install(env, "project")
        project = (env.project_dir / ".codex" / "config.toml").read_text(encoding="utf-8")
        self.assertIn("[mcp_servers.ase-moodle]", project)
        self.assertIn("command = 'C:/Python313/python.exe'", project)
        home_text = (self.home / ".codex" / "config.toml").read_text(encoding="utf-8")
        self.assertIn("[mcp_servers.context7]", home_text, "tabelele altor servere nu se ating")
        self.assertNotIn("[mcp_servers.ase-moodle]", home_text)
        self.assertFalse(any(" ".join(c).startswith("codex plugin add") for c in run.commands))

    def test_project_block_is_idempotent(self):
        env = make_env(self.home, run=Recorder())
        REGISTRY["codex"].install(env, "project")
        REGISTRY["codex"].install(env, "project")
        text = (env.project_dir / ".codex" / "config.toml").read_text(encoding="utf-8")
        self.assertEqual(text.count("[mcp_servers.ase-moodle]"), 1)

    def test_uninstall_project_keeps_other_servers(self):
        env = make_env(self.home, run=Recorder())
        (env.project_dir / ".codex").mkdir()
        cfg = env.project_dir / ".codex" / "config.toml"
        cfg.write_text('[mcp_servers.context7]\ncommand = "npx"\n', encoding="utf-8")
        REGISTRY["codex"].install(env, "project")
        REGISTRY["codex"].uninstall(env, "project")
        text = cfg.read_text(encoding="utf-8")
        self.assertNotIn("ase-moodle", text)
        self.assertIn("[mcp_servers.context7]", text)

    def test_global_install_removes_project_block(self):
        env = make_env(self.home, run=Recorder())
        REGISTRY["codex"].install(env, "project")
        REGISTRY["codex"].install(env, "global")
        self.assertNotIn("ase-moodle", (env.project_dir / ".codex" / "config.toml").read_text(encoding="utf-8"))

    def test_doctor_reports_project_only_install_as_ok(self):
        env = make_env(self.home, run=Recorder(output=""))
        REGISTRY["codex"].install(env, "project")
        steps = {s.action: s for s in REGISTRY["codex"].doctor(env)}
        self.assertEqual(steps["project"].status, "ok")
        self.assertEqual(steps["global"].status, "skipped")
        self.assertFalse(any(s.status == "error" for s in REGISTRY["codex"].doctor(env)))

    def test_doctor_error_when_nothing_installed(self):
        steps = REGISTRY["codex"].doctor(make_env(self.home, run=Recorder(output="")))
        self.assertIn("error", [s.status for s in steps])


class OpencodeTests(IsolatedTest):
    def test_global_install_writes_mcp_instructions_and_skill_and_records(self):
        env = make_env(self.home, run=Recorder())
        REGISTRY["opencode"].install(env, "global")
        cfg = json.loads((self.home / ".config" / "opencode" / "opencode.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["mcp"]["ase-moodle"]["command"],
                         ["C:/Python313/python.exe", "-m", "ase_moodle.mcp_server"])
        self.assertEqual(cfg["instructions"].count((self.home / ".config/opencode/ase-moodle/SKILL.md").as_posix()), 1)
        self.assertTrue((self.home / ".config" / "opencode" / "ase-moodle" / "SKILL.md").exists())

    def test_project_install_keeps_other_mcp_servers_and_no_instructions(self):
        env = make_env(self.home, run=Recorder())
        (env.project_dir / "opencode.json").write_text(json.dumps(
            {"mcp": {"context7": {"type": "remote", "url": "https://example.invalid"}}}), encoding="utf-8")
        REGISTRY["opencode"].install(env, "project")
        cfg = json.loads((env.project_dir / "opencode.json").read_text(encoding="utf-8"))
        self.assertIn("context7", cfg["mcp"])
        self.assertIn("ase-moodle", cfg["mcp"])
        self.assertNotIn("instructions", cfg)

    def test_project_install_removes_global_entry_only(self):
        env = make_env(self.home, run=Recorder())
        REGISTRY["opencode"].install(env, "global")
        REGISTRY["opencode"].install(env, "project")
        glob = json.loads((self.home / ".config" / "opencode" / "opencode.json").read_text(encoding="utf-8"))
        self.assertNotIn("ase-moodle", glob.get("mcp", {}))
        self.assertFalse((self.home / ".config" / "opencode" / "ase-moodle").exists())

    def test_invalid_json_is_never_overwritten(self):
        env = make_env(self.home, run=Recorder())
        cfg = env.project_dir / "opencode.json"
        cfg.write_text("{ nu e json", encoding="utf-8")
        steps = REGISTRY["opencode"].install(env, "project")
        self.assertEqual(steps[0].status, "error")
        self.assertEqual(cfg.read_text(encoding="utf-8"), "{ nu e json")

    def test_uninstall_keeps_other_servers(self):
        env = make_env(self.home, run=Recorder())
        REGISTRY["opencode"].install(env, "global")
        cfg = self.home / ".config" / "opencode" / "opencode.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["mcp"]["exa"] = {"type": "remote", "url": "https://example.invalid"}
        cfg.write_text(json.dumps(data), encoding="utf-8")
        REGISTRY["opencode"].uninstall(env, "global")
        after = json.loads(cfg.read_text(encoding="utf-8"))
        self.assertNotIn("ase-moodle", after["mcp"])
        self.assertIn("exa", after["mcp"])


class AntigravityTests(IsolatedTest):
    def test_project_scope_is_refused_explicitly(self):
        env = make_env(self.home, run=Recorder())
        with self.assertRaises(UnsupportedScope):
            REGISTRY["antigravity"].install(env, "project")
        self.assertEqual(Recorder().commands, [])

    def test_global_install_runs_agy_mcp_add_and_plugin_install(self):
        run = Recorder()
        env = make_env(self.home, run=run, source=str(Path(self.tmp.name)))
        (Path(self.tmp.name) / "plugins" / "ase-moodle").mkdir(parents=True)
        REGISTRY["antigravity"].install(env, "global")
        self.assertEqual(run.commands[0],
                         ["agy", "mcp", "add", "ase-moodle", "--", "C:/Python313/python.exe", "-m", "ase_moodle.mcp_server"])
        self.assertEqual(run.commands[1][:3], ["agy", "plugin", "install"])

    def test_uninstall_all_means_global_only(self):
        run = Recorder()
        REGISTRY["antigravity"].uninstall(make_env(self.home, run=run), "all")
        self.assertIn(["agy", "mcp", "remove", "ase-moodle"], run.commands)


class DispatcherIsolationTests(IsolatedTest):
    def test_install_all_on_project_skips_only_antigravity(self):
        env = make_env(self.home, run=Recorder())
        steps = install.install(["all"], env, "project")
        skipped = {s.target for s in steps if s.status == "skipped"}
        self.assertEqual(skipped, {"antigravity"})
        self.assertTrue(any(s.target == "claude" and s.status == "ok" for s in steps))

    def test_explicit_antigravity_on_project_is_an_error(self):
        with self.assertRaises(UnsupportedScope):
            install.install(["antigravity"], make_env(self.home, run=Recorder()), "project")

    def test_claude_install_never_touches_other_harness_files(self):
        env = make_env(self.home, run=Recorder())
        REGISTRY["claude"].install(env, "project")
        # Claude e configurat prin CLI-ul lui: singurul fisier pe care il scriem e evidenta lui.
        written = {p.relative_to(self.home).as_posix() for p in self.home.rglob("*") if p.is_file()}
        self.assertEqual(written, {".ase-moodle/state/claude.json"})

    def test_unknown_target_and_scope_are_rejected(self):
        with self.assertRaises(ValueError):
            install.install(["emacs"], make_env(self.home))
        with self.assertRaises(ValueError):
            install.install(["claude"], make_env(self.home), "planet")
        with self.assertRaises(ValueError):
            install.uninstall(["claude"], make_env(self.home), "planet")

    def test_doctor_covers_every_harness_and_package(self):
        steps = install.doctor(make_env(self.home, run=Recorder(output="")))
        targets = {s.target for s in steps}
        self.assertTrue({"claude", "codex", "opencode", "antigravity", "package", "security"} <= targets)


class CliPerHarnessTests(unittest.TestCase):
    def test_per_harness_commands_parse(self):
        parser = cli.build_parser()
        args = parser.parse_args(["codex", "install", "--scope", "project", "--project-dir", "X"])
        self.assertEqual((args.harness, args.harness_action, args.scope, args.project_dir), ("codex", "install", "project", "X"))
        args = parser.parse_args(["claude", "uninstall"])
        self.assertEqual(args.scope, "all")
        args = parser.parse_args(["opencode", "doctor"])
        self.assertEqual(args.harness_action, "doctor")

    def test_antigravity_project_scope_is_rejected_by_the_parser(self):
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["antigravity", "install", "--scope", "project"])

    def test_dispatcher_defaults_stay_global(self):
        self.assertEqual(cli.build_parser().parse_args(["install", "all"]).scope, "global")


class PlatformLayoutTests(unittest.TestCase):
    def test_every_registered_harness_declares_its_capabilities(self):
        for name, harness in REGISTRY.items():
            self.assertEqual(harness.name, name)
            self.assertTrue(harness.capabilities.scopes, name)
            self.assertIn("global", harness.capabilities.scopes, name)


if __name__ == "__main__":
    unittest.main()
