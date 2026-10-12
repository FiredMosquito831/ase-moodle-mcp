"""Teste pentru instalatori: rulate intr-un HOME temporar cu un runner fals (nu modifica configurarea reala)."""

import json
import tempfile
import unittest
from pathlib import Path

from ase_moodle import install

REPO = Path(__file__).resolve().parents[1]


class Recorder:
    """Runner fals: inregistreaza comenzile si raspunde cu cod 0 si un text predefinit."""

    def __init__(self, output: str = "", code: int = 0):
        self.commands: list[list[str]] = []
        self.output = output
        self.code = code

    def __call__(self, cmd: list[str]) -> tuple[int, str]:
        self.commands.append(cmd)
        return self.code, self.output


def make_env(home: Path, run=None, which=None, source: str = "C:/repo") -> install.Env:
    return install.Env(
        home=home,
        source=source,
        run=run or Recorder(),
        which=which or (lambda name: f"/bin/{name}"),
        python="C:/Python313/python.exe",
    )


class ClaudeTests(unittest.TestCase):
    def test_marketplace_then_plugin_then_legacy_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Recorder()
            steps = install.install_claude(make_env(Path(tmp), run=run))
            self.assertEqual(run.commands[0][:4], ["claude", "plugin", "marketplace", "add"])
            self.assertIn("C:/repo", run.commands[0])
            self.assertEqual(run.commands[1][:3], ["claude", "plugin", "install"])
            self.assertIn("ase-moodle@ase-moodle-marketplace", run.commands[1])
            self.assertEqual(run.commands[2][:4], ["claude", "mcp", "remove", "ase-moodle"])
            self.assertTrue(all(s.status == "ok" for s in steps))

    def test_missing_cli_is_skipped_not_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            steps = install.install_claude(make_env(Path(tmp), which=lambda name: None))
            self.assertEqual([s.status for s in steps], ["skipped"])

    def test_already_present_marketplace_counts_as_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Recorder(output="marketplace already exists", code=1)
            steps = install.install_claude(make_env(Path(tmp), run=run))
            self.assertEqual(steps[0].status, "ok")


class CodexTests(unittest.TestCase):
    LEGACY = (
        '[features]\nfoo = 1\n\n'
        '[mcp_servers.context7]\ncommand = "npx"\n\n'
        '[mcp_servers.ase-moodle]\ncommand = "ase-moodle-mcp"\n\n'
        '[mcp_servers.ase-moodle.env]\nX = "1"\n\n'
        '[projects.\'c:\\users\']\ntrust = true\n'
    )

    def test_plugin_commands_and_legacy_block_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".codex").mkdir()
            cfg = home / ".codex" / "config.toml"
            cfg.write_text(self.LEGACY, encoding="utf-8")
            run = Recorder()
            install.install_codex(make_env(home, run=run))
            self.assertEqual(run.commands[0][:4], ["codex", "plugin", "marketplace", "add"])
            self.assertEqual(run.commands[1], ["codex", "plugin", "add", "ase-moodle@ase-moodle-marketplace"])
            text = cfg.read_text(encoding="utf-8")
            self.assertNotIn("[mcp_servers.ase-moodle]", text)
            self.assertNotIn("[mcp_servers.ase-moodle.env]", text)
            self.assertIn("[mcp_servers.context7]", text)  # alte servere nu se ating
            self.assertIn("[projects.", text)


class OpencodeTests(unittest.TestCase):
    def test_writes_mcp_and_instructions_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            env = make_env(home)
            install.install_opencode(env)
            install.install_opencode(env)  # a doua rulare nu dubleaza nimic
            cfg = json.loads((home / ".config" / "opencode" / "opencode.json").read_text(encoding="utf-8"))
            server = cfg["mcp"]["ase-moodle"]
            self.assertEqual(server["type"], "local")
            self.assertEqual(server["command"], ["C:/Python313/python.exe", "-m", "ase_moodle.mcp_server"])
            self.assertTrue(server["enabled"])
            skill = (home / ".config" / "opencode" / "ase-moodle" / "SKILL.md")
            self.assertTrue(skill.exists())
            self.assertEqual(cfg["instructions"].count(skill.as_posix()), 1)

    def test_keeps_existing_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg_dir = home / ".config" / "opencode"
            cfg_dir.mkdir(parents=True)
            (cfg_dir / "opencode.json").write_text(json.dumps({
                "$schema": "https://opencode.ai/config.json",
                "mcp": {"context7": {"type": "remote", "url": "https://example.invalid"}},
                "instructions": ["CONTRIBUTING.md"],
            }), encoding="utf-8")
            install.install_opencode(make_env(home))
            cfg = json.loads((cfg_dir / "opencode.json").read_text(encoding="utf-8"))
            self.assertIn("context7", cfg["mcp"])
            self.assertIn("CONTRIBUTING.md", cfg["instructions"])
            self.assertTrue((cfg_dir / "opencode.json.bak").exists())

    def test_invalid_json_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg_dir = home / ".config" / "opencode"
            cfg_dir.mkdir(parents=True)
            (cfg_dir / "opencode.json").write_text("{ not json", encoding="utf-8")
            steps = install.install_opencode(make_env(home))
            self.assertEqual(steps[0].status, "error")
            self.assertEqual((cfg_dir / "opencode.json").read_text(encoding="utf-8"), "{ not json")

    def test_uninstall_removes_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            env = make_env(home)
            install.install_opencode(env)
            install.uninstall_opencode(env)
            cfg = json.loads((home / ".config" / "opencode" / "opencode.json").read_text(encoding="utf-8"))
            self.assertNotIn("ase-moodle", cfg.get("mcp", {}))
            self.assertEqual(cfg.get("instructions", []), [])


class AntigravityTests(unittest.TestCase):
    def test_mcp_add_then_plugin_install_from_local_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Recorder()
            env = make_env(Path(tmp), run=run, source=str(REPO))
            install.install_antigravity(env)
            self.assertEqual(run.commands[0],
                             ["agy", "mcp", "add", "ase-moodle", "--", "C:/Python313/python.exe", "-m", "ase_moodle.mcp_server"])
            self.assertEqual(run.commands[1][:3], ["agy", "plugin", "install"])
            self.assertEqual(Path(run.commands[1][3]), REPO / "plugins" / "ase-moodle")


class InstallApiTests(unittest.TestCase):
    def test_unknown_target_is_rejected(self):
        with self.assertRaises(ValueError):
            install.install(["vscode"], make_env(Path(tempfile.gettempdir())))

    def test_all_targets_run_without_touching_real_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            steps = install.install(["all"], make_env(Path(tmp), which=lambda name: None))
            self.assertEqual({s.target for s in steps}, set(install.TARGETS))
            self.assertTrue(all(s.status in ("ok", "skipped") for s in steps))


class PluginLayoutTests(unittest.TestCase):
    def test_manifests_are_valid_json(self):
        for rel in (
            ".claude-plugin/marketplace.json",
            ".agents/plugins/marketplace.json",
            "plugins/ase-moodle/.claude-plugin/plugin.json",
            "plugins/ase-moodle/.codex-plugin/plugin.json",
            "plugins/ase-moodle/plugin.json",
            "plugins/ase-moodle/.mcp.json",
        ):
            json.loads((REPO / rel).read_text(encoding="utf-8"))

    def test_plugin_skill_is_in_sync_with_packaged_skill(self):
        packaged = (REPO / "src" / "ase_moodle" / "data" / "SKILL.md").read_text(encoding="utf-8")
        plugin = (REPO / "plugins" / "ase-moodle" / "skills" / "ase-moodle" / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(packaged, plugin, "ruleaza: ase-moodle sync-plugin")

    def test_marketplace_points_to_plugin_folder(self):
        data = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(data["plugins"][0]["source"], "./plugins/ase-moodle")
        self.assertTrue((REPO / "plugins" / "ase-moodle" / "skills" / "ase-moodle" / "SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
