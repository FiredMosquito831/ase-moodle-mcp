"""Setarile: URL-ul Moodle si tokenul. Tokenul vine din ASE_MOODLE_TOKEN sau din ~/.ase-moodle/config.json."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://online.ase.ro"
CONFIG_DIR = Path.home() / ".ase-moodle"
CONFIG_FILE = CONFIG_DIR / "config.json"


class SettingsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    base_url: str
    token: str


def load_settings() -> Settings:
    file_data: dict = {}
    if CONFIG_FILE.exists():
        file_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    token = os.environ.get("ASE_MOODLE_TOKEN") or file_data.get("token")
    base_url = os.environ.get("ASE_MOODLE_URL") or file_data.get("base_url") or DEFAULT_BASE_URL
    if not token:
        raise SettingsError("Lipseste tokenul. Ruleaza `ase-moodle login` sau seteaza ASE_MOODLE_TOKEN.")
    return Settings(base_url=base_url.rstrip("/"), token=token.strip())


def save_settings(token: str, base_url: str = DEFAULT_BASE_URL) -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"base_url": base_url, "token": token}, indent=2), encoding="utf-8")
    return CONFIG_FILE


def download_root() -> Path:
    """Folderul implicit pentru materiale: ASE_MOODLE_DOWNLOADS sau ~/ASE-Moodle."""
    return Path(os.environ.get("ASE_MOODLE_DOWNLOADS") or (Path.home() / "ASE-Moodle"))
