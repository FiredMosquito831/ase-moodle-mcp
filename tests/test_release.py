"""Teste de release: versiuni coerente, serverul MCP real prin stdio (contra serverului fals) si comanda update."""

import asyncio
import json
import os
import re
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from fake_moodle import TOKEN, FakeMoodle
from test_harnesses import Recorder, make_env

from ase_moodle import install

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"


class VersionTests(unittest.TestCase):
    def test_all_versions_match(self):
        pyproject = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        init = re.search(r'__version__ = "([^"]+)"', (SRC / "ase_moodle" / "__init__.py").read_text(encoding="utf-8")).group(1)
        manifests = {
            "plugin claude": json.loads((REPO / "plugins/ase-moodle/.claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"],
            "plugin codex": json.loads((REPO / "plugins/ase-moodle/.codex-plugin/plugin.json").read_text(encoding="utf-8"))["version"],
            "plugin antigravity": json.loads((REPO / "plugins/ase-moodle/plugin.json").read_text(encoding="utf-8"))["version"],
            "marketplace": json.loads((REPO / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))["metadata"]["version"],
        }
        mismatched = {k: v for k, v in manifests.items() if v != pyproject}
        self.assertEqual(init, pyproject)
        self.assertEqual(mismatched, {}, f"versiunile nu coincid cu pyproject ({pyproject})")

    def test_every_pin_matches_the_release(self):
        """Acelasi verificator ca `scripts/release.py --check`: manifeste, data, copia SKILL, pinurile din fisiere."""
        problems = load_release_script().check(REPO)
        self.assertEqual(problems, [], "ruleaza: python scripts/release.py X.Y.Z\n" + "\n".join(problems))


def load_release_script():
    """scripts/release.py nu e un pachet: il incarc dupa cale."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("ase_moodle_release_script", REPO / "scripts" / "release.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses cauta modulul in sys.modules
    spec.loader.exec_module(module)
    return module


class ReleaseScriptTests(unittest.TestCase):
    """scripts/release.py pe o copie a fisierelor de versiune, intr-un folder temporar (fara git)."""

    FILES = [
        "pyproject.toml",
        "src/ase_moodle/__init__.py",
        "src/ase_moodle/data/SKILL.md",
        "plugins/ase-moodle/.claude-plugin/plugin.json",
        "plugins/ase-moodle/.codex-plugin/plugin.json",
        "plugins/ase-moodle/plugin.json",
        "plugins/ase-moodle/skills/ase-moodle/SKILL.md",
        ".claude-plugin/marketplace.json",
        "README.md",
    ]

    def setUp(self):
        import shutil

        self.release = load_release_script()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for name in self.FILES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / name, target)
        (self.root / "docs").mkdir()
        self.version, self.date = self.release.sources(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def edit(self, name, old, new):
        path = self.root / name
        text = path.read_bytes().decode("utf-8")
        self.assertIn(old, text)
        path.write_bytes(text.replace(old, new, 1).encode("utf-8"))

    def assertReported(self, name):
        problems = self.release.check(self.root)
        self.assertTrue(any(p.startswith(name) for p in problems), f"{name} lipseste din {problems}")

    def test_copy_is_clean(self):
        self.assertEqual(self.release.check(self.root), [])

    def test_manifest_version_mismatch_names_the_file(self):
        self.edit("plugins/ase-moodle/.codex-plugin/plugin.json", f'"version": "{self.version}"', '"version": "9.9.9"')
        self.assertReported("plugins/ase-moodle/.codex-plugin/plugin.json")

    def test_release_date_format(self):
        self.edit("src/ase_moodle/__init__.py", f'RELEASE_DATE = "{self.date}"', 'RELEASE_DATE = "2026-10-30"')
        self.assertReported("src/ase_moodle/__init__.py")

    def test_skill_copy_must_be_identical(self):
        self.edit("plugins/ase-moodle/skills/ase-moodle/SKILL.md", "\n", "\r\n")
        self.assertReported("plugins/ase-moodle/skills/ase-moodle/SKILL.md")

    def test_wrong_pin_in_a_doc(self):
        (self.root / "docs" / "X.md").write_bytes(
            f"uvx --from ase-moodle==0.0.1 --exclude-newer {self.date} ase-moodle-mcp\n".encode())
        problems = self.release.check(self.root)
        self.assertEqual([p.split(":")[0] for p in problems], ["docs/X.md"])
        (self.root / "docs" / "X.md").write_bytes(b"uvx --exclude-newer 2020-01-01T00:00:00Z --from ase-moodle==X.Y.Z\n")
        self.assertReported("docs/X.md")

    def test_placeholders_are_not_pins(self):
        (self.root / "docs" / "X.md").write_bytes(
            b"uvx --from ase-moodle==X.Y.Z --exclude-newer <data> --exclude-newer-package ase-moodle=false\n")
        self.assertEqual(self.release.check(self.root), [])

    def test_expect_must_equal_the_version(self):
        self.assertEqual(self.release.check(self.root, expect=self.version), [])
        self.assertTrue(self.release.check(self.root, expect="9.9.9"))

    def test_apply_writes_every_location_and_keeps_lf(self):
        (self.root / "docs" / "X.md").write_bytes(
            f"a\nuvx --from ase-moodle=={self.version} --exclude-newer {self.date} ase-moodle-mcp\n".encode())
        self.edit("plugins/ase-moodle/skills/ase-moodle/SKILL.md", "\n", "\n\n")
        changed = self.release.apply(self.root, "7.8.9", "2031-02-03T00:00:00Z")
        self.assertEqual(self.release.check(self.root), [])
        self.assertEqual(self.release.sources(self.root), ("7.8.9", "2031-02-03T00:00:00Z"))
        self.assertIn("docs/X.md", changed)
        self.assertEqual((self.root / "docs" / "X.md").read_bytes(),
                         b"a\nuvx --from ase-moodle==7.8.9 --exclude-newer 2031-02-03T00:00:00Z ase-moodle-mcp\n")
        for name in self.FILES:
            self.assertNotIn(b"\r\n", (self.root / name).read_bytes(), name)
        marketplace = json.loads((self.root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(marketplace["metadata"]["version"], "7.8.9")

    def test_cli_check_exit_codes(self):
        with mock.patch("sys.stdout"):
            self.assertEqual(self.release.main(["--check", "--root", str(self.root)]), 0)
        with mock.patch("sys.stderr"):
            self.assertEqual(self.release.main(["--check", "--expect", "9.9.9", "--root", str(self.root)]), 1)


class EntryPointTests(unittest.TestCase):
    """ase-moodle-mcp fara argumente porneste serverul; cu argumente ruleaza CLI-ul."""

    def test_arguments_run_the_cli(self):
        from ase_moodle import mcp_server

        with mock.patch("ase_moodle.cli.main", return_value=0) as cli_main, \
                mock.patch.object(mcp_server.mcp, "run") as run:
            with self.assertRaises(SystemExit) as stop:
                mcp_server.main(["auth-status"])
        cli_main.assert_called_once_with(["auth-status"])
        run.assert_not_called()
        self.assertEqual(stop.exception.code, 0)

    def test_no_arguments_start_the_mcp_server(self):
        from ase_moodle import mcp_server

        with mock.patch("ase_moodle.cli.main") as cli_main, \
                mock.patch.object(mcp_server.mcp, "run") as run, \
                mock.patch.object(sys, "argv", ["ase-moodle-mcp"]):
            mcp_server.main()
        run.assert_called_once()
        cli_main.assert_not_called()


class UpdateTests(unittest.TestCase):
    def test_update_refreshes_marketplaces_and_plugins(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Recorder()
            install.update(["claude", "codex"], make_env(Path(tmp), run=run, source=str(REPO)))
        joined = [" ".join(c) for c in run.commands]
        self.assertTrue(any("claude plugin marketplace update ase-moodle-marketplace" in c for c in joined))
        self.assertTrue(any(c.startswith("claude plugin update ase-moodle@ase-moodle-marketplace") for c in joined))
        self.assertTrue(any("codex plugin marketplace upgrade ase-moodle-marketplace" in c for c in joined))
        self.assertTrue(any(c.startswith("codex plugin add ase-moodle@ase-moodle-marketplace") for c in joined))

    def test_update_rejects_unknown_target(self):
        with self.assertRaises(ValueError):
            install.update(["emacs"], make_env(Path(tempfile.gettempdir())))


class McpStdioTests(unittest.TestCase):
    """Porneste serverul MCP real (subprocess) si vorbeste cu el prin protocolul MCP, contra serverului fals."""

    def test_server_tools_prompts_resources_and_guards(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        with FakeMoodle() as fake:
            env = dict(os.environ)
            env.update({
                "PYTHONPATH": str(SRC),
                "ASE_MOODLE_URL": fake.url,
                "ASE_MOODLE_TOKEN": TOKEN,
                "ASE_MOODLE_ENV_FILE": str(REPO / "nu-exista.env"),
            })
            work = Path(tempfile.gettempdir()) / "ase-moodle-mcp-test.txt"
            work.write_text("test", encoding="utf-8")

            async def scenario():
                params = StdioServerParameters(command=sys.executable, args=["-m", "ase_moodle.mcp_server"], env=env)
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools = (await session.list_tools()).tools
                        prompts = {p.name for p in (await session.list_prompts()).prompts}
                        resources = {str(r.uri) for r in (await session.list_resources()).resources}
                        who = await session.call_tool("whoami", {})
                        blocked = await session.call_tool(
                            "submit_assignment_file",
                            {"assign_id": 202, "file_path": str(work), "confirm": True},
                        )
                        listing = await session.call_tool("list_courses", {"study_year": 3, "semester": 1})
                        return tools, prompts, resources, who, blocked, listing

            tools, prompts, resources, who, blocked, listing = asyncio.run(scenario())

        self.assertEqual(len(tools), 28)
        for tool in tools:
            self.assertIsNotNone(tool.annotations, f"{tool.name} nu are anotari")
        read_only = {t.name for t in tools if t.annotations and t.annotations.readOnlyHint}
        self.assertIn("whoami", read_only)
        self.assertNotIn("submit_assignment_file", read_only)
        self.assertTrue({"weekly_brief", "prepare_assignment", "solve_quiz", "download_year"} <= prompts)
        self.assertIn("moodle://me", resources)
        self.assertIn("Student Test", who.content[0].text)
        self.assertTrue(blocked.isError)
        self.assertIn("nu are ciorne", blocked.content[0].text)
        payload = json.loads(listing.content[0].text)
        self.assertEqual(payload["count"], 2)


if __name__ == "__main__":
    unittest.main()
