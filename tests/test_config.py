"""Teste pentru configurare si secrete: .env, Credential Manager (simulat), migrarea tokenului in clar."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ase_moodle import config

TOKEN_A = "0123456789abcdef0123456789abcdef"
TOKEN_B = "fedcba9876543210fedcba9876543210"


class FakeKeyring:
    """Tine loc de Credential Manager, in memorie."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def set_password(self, service, user, password):
        self.store[(service, user)] = password

    def get_password(self, service, user):
        return self.store.get((service, user))

    def delete_password(self, service, user):
        self.store.pop((service, user), None)


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.cfg = self.dir / "config.json"
        self.keyring = FakeKeyring()
        self.patches = [
            mock.patch.object(config, "CONFIG_FILE", self.cfg),
            mock.patch.object(config, "CONFIG_DIR", self.dir),
            mock.patch.object(config, "_keyring", return_value=self.keyring),
            mock.patch.object(config, "_restrict", lambda path: None),
        ]
        for p in self.patches:
            p.start()
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        for key in ("ASE_MOODLE_TOKEN", "ASE_MOODLE_URL", "ASE_MOODLE_ENV_FILE", "ASE_MOODLE_DOWNLOADS"):
            os.environ.pop(key, None)
        os.environ["ASE_MOODLE_ENV_FILE"] = str(self.dir / "nu-exista.env")

    def tearDown(self):
        self.env.stop()
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_environment_beats_everything(self):
        os.environ["ASE_MOODLE_TOKEN"] = TOKEN_A
        self.keyring.set_password(config.KEYRING_SERVICE, config.DEFAULT_BASE_URL, TOKEN_B)
        settings = config.load_settings()
        self.assertEqual((settings.token, settings.source), (TOKEN_A, "env"))

    def test_dotenv_file_is_read_and_parsed(self):
        env_file = self.dir / "local.env"
        env_file.write_text(
            "# comentariu\n\nASE_MOODLE_TOKEN='%s'\nASE_MOODLE_URL=\"https://example.invalid/\"\n" % TOKEN_A,
            encoding="utf-8",
        )
        os.environ["ASE_MOODLE_ENV_FILE"] = str(env_file)
        settings = config.load_settings()
        self.assertEqual(settings.token, TOKEN_A)
        self.assertEqual(settings.base_url, "https://example.invalid")
        self.assertEqual(settings.source, "dotenv")

    def test_keyring_is_used_when_no_env(self):
        self.keyring.set_password(config.KEYRING_SERVICE, config.DEFAULT_BASE_URL, TOKEN_B)
        settings = config.load_settings()
        self.assertEqual((settings.token, settings.source), (TOKEN_B, "keyring"))

    def test_plaintext_token_is_migrated_into_keyring(self):
        self.cfg.write_text(json.dumps({"base_url": config.DEFAULT_BASE_URL, "token": TOKEN_A}), encoding="utf-8")
        settings = config.load_settings()
        self.assertEqual(settings.source, "keyring")
        self.assertEqual(self.keyring.get_password(config.KEYRING_SERVICE, config.DEFAULT_BASE_URL), TOKEN_A)
        self.assertNotIn("token", json.loads(self.cfg.read_text(encoding="utf-8")))

    def test_save_with_keyring_keeps_token_out_of_the_file(self):
        config.save_settings(TOKEN_A, "https://example.invalid", username="student")
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        self.assertNotIn("token", data)
        self.assertEqual(data["token_store"], "keyring")
        self.assertEqual(self.keyring.get_password(config.KEYRING_SERVICE, "https://example.invalid"), TOKEN_A)

    def test_save_without_keyring_falls_back_to_file(self):
        with mock.patch.object(config, "_keyring", return_value=None):
            config.save_settings(TOKEN_A, "https://example.invalid")
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        self.assertEqual(data["token"], TOKEN_A)
        self.assertEqual(data["token_store"], "file")

    def test_forget_token_clears_keyring_and_file(self):
        config.save_settings(TOKEN_A, "https://example.invalid")
        config.forget_token("https://example.invalid")
        self.assertIsNone(self.keyring.get_password(config.KEYRING_SERVICE, "https://example.invalid"))

    def test_missing_token_gives_actionable_message(self):
        with self.assertRaises(config.SettingsError) as ctx:
            config.load_settings()
        self.assertIn("ase-moodle login", str(ctx.exception))

    def test_dotenv_parser_ignores_garbage_lines(self):
        env_file = self.dir / "x.env"
        env_file.write_text("linie fara egal\n=fara-cheie\nCHEIE=valoare\n", encoding="utf-8")
        self.assertEqual(config.read_dotenv(env_file), {"CHEIE": "valoare"})


if __name__ == "__main__":
    unittest.main()
