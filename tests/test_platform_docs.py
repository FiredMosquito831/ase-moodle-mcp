"""Teste de platforma (Windows/Linux) si de documentatie.

Documentatia trebuie sa acopere tot: fiecare comanda CLI, unealta MCP, prompt si resursa apare in docs/,
iar linkurile din README exista. Lista se ia din codul real, deci o comanda noua nedocumentata pica testul.
"""

import argparse
import re
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ase_moodle import auth, cli, config, install

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class PosixPermissionTests(unittest.TestCase):
    @unittest.skipIf(sys.platform == "win32", "permisiunile POSIX nu se aplica pe Windows")
    def test_config_file_and_profile_are_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "profil"
            (folder / "sub").mkdir(parents=True)
            (folder / "sub" / "cookies").write_text("x", encoding="utf-8")
            cfg_file = Path(tmp) / "config.json"
            cfg_file.write_text("{}", encoding="utf-8")
            config._restrict(cfg_file)
            config._restrict(folder, recursive=True)
            self.assertEqual(stat.S_IMODE(cfg_file.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(folder.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((folder / "sub" / "cookies").stat().st_mode), 0o600)


class DefaultFolderTests(unittest.TestCase):
    def test_without_project_dir_the_current_folder_is_used(self):
        args = cli.build_parser().parse_args(["install", "claude"])
        env = cli._install_env(args)
        self.assertEqual(env.project_dir, Path.cwd())

    def test_explicit_project_dir_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = cli.build_parser().parse_args(["install", "claude", "--project-dir", tmp])
            env = cli._install_env(args)
            self.assertEqual(env.project_dir, Path(tmp).resolve())

    def test_default_scope_is_global(self):
        self.assertEqual(cli.build_parser().parse_args(["install", "all"]).scope, "global")
        self.assertEqual(cli.build_parser().parse_args(["uninstall", "all"]).scope, "all")


class ClipboardTests(unittest.TestCase):
    def test_linux_tries_x11_then_wayland(self):
        with mock.patch.object(sys, "platform", "linux"):
            names = [c[0] for c in auth._clipboard_commands()]
        self.assertEqual(names, ["xclip", "xsel", "wl-paste"])

    def test_read_clipboard_returns_empty_when_no_tool_exists(self):
        with mock.patch.object(sys, "platform", "linux"), mock.patch.object(auth.shutil, "which", return_value=None):
            self.assertEqual(auth.read_clipboard(), "")


class DocumentationCoverageTests(unittest.TestCase):
    def _cli_commands(self) -> list[str]:
        parser = cli.build_parser()
        sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
        return list(sub.choices)

    def _mcp_names(self):
        from ase_moodle import mcp_server

        tools = [t.name for t in mcp_server.mcp._tool_manager.list_tools()]
        prompts = [p.name for p in mcp_server.mcp._prompt_manager.list_prompts()]
        resources = [str(r.uri) for r in mcp_server.mcp._resource_manager.list_resources()]
        return tools, prompts, resources

    def test_every_cli_command_is_documented(self):
        text = _read(DOCS / "USAGE.md")
        # Comanda apare ca `cmd`, ca `cmd <argumente>` sau `cmd [TARGET ...]` in titlu.
        missing = [c for c in self._cli_commands()
                   if not re.search(rf"`{re.escape(c)}[` ]", text) and f" {c} " not in text]
        self.assertEqual(missing, [], "comenzi CLI nedocumentate in docs/USAGE.md")

    def test_every_mcp_tool_prompt_and_resource_is_documented(self):
        tools, prompts, resources = self._mcp_names()
        text = _read(DOCS / "MCP.md")
        missing = [n for n in [*tools, *prompts, *resources] if n not in text]
        self.assertEqual(missing, [], "unelte, prompturi sau resurse nedocumentate in docs/MCP.md")
        self.assertEqual(len(tools), 28)

    def test_readme_links_point_to_existing_files(self):
        text = _read(REPO / "README.md")
        links = re.findall(r"\]\((?!https?://|#)([^)#]+)\)", text)
        self.assertTrue(links, "README nu are linkuri catre documentatie")
        broken = [link for link in links if not (REPO / link).exists()]
        self.assertEqual(broken, [], "linkuri rupte in README")

    def test_docs_do_not_contain_secret_looking_values(self):
        pattern = re.compile(r"\b[0-9a-f]{32}\b")
        for path in [REPO / "README.md", *DOCS.glob("*.md")]:
            hits = [m.group(0) for m in pattern.finditer(_read(path))
                    if m.group(0) not in {"0123456789abcdef0123456789abcdef", "a" * 32, "b" * 32}]
            self.assertEqual(hits, [], f"valoare care arata a secret in {path.name}")


class InstallDocsTests(unittest.TestCase):
    def test_install_doc_mentions_every_platform_and_scope(self):
        text = _read(DOCS / "PLATFORMS.md")
        for word in [*install.TARGETS, "global", "project", "Antigravity"]:
            self.assertIn(word, text)


if __name__ == "__main__":
    unittest.main()
