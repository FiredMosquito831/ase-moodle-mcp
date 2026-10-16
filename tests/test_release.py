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
