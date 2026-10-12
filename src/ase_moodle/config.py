"""Setari si secrete. Ordinea de prioritate (prima valoare gasita castiga):

1. variabilele de mediu (ASE_MOODLE_TOKEN, ASE_MOODLE_URL, ...)
2. fisierul .env local (in .gitignore; ASE_MOODLE_ENV_FILE il poate muta in alt loc)
3. Windows Credential Manager (keyring) pentru token
4. ~/.ase-moodle/config.json: URL-ul si, doar ca rezerva daca keyring nu e disponibil, tokenul

Regula: tokenul nu intra niciodata in git, in mesaje de eroare sau in loguri.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://online.ase.ro"
CONFIG_DIR = Path.home() / ".ase-moodle"
CONFIG_FILE = CONFIG_DIR / "config.json"
KEYRING_SERVICE = "ase-moodle"
ENV_FILE_VAR = "ASE_MOODLE_ENV_FILE"


class SettingsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    base_url: str
    token: str
    source: str  # env | dotenv | keyring | file


def find_dotenv() -> Path | None:
    """.env explicit (ASE_MOODLE_ENV_FILE), altfel primul .env din directorul curent sau din parinti."""
    explicit = os.environ.get(ENV_FILE_VAR)
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.exists() else None
    here = Path.cwd().resolve()
    for folder in (here, *here.parents):
        candidate = folder / ".env"
        if candidate.is_file():
            return candidate
    return None


def read_dotenv(path: Path | None) -> dict[str, str]:
    """Parseaza KEY=VALUE. Ignora liniile goale si comentariile; accepta ghilimele simple sau duble."""
    values: dict[str, str] = {}
    if path is None or not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key] = value
    return values


def _env(name: str, dotenv: dict[str, str]) -> str | None:
    return os.environ.get(name) or dotenv.get(name) or None


def _keyring():
    try:
        import keyring
    except ImportError:
        return None
    return keyring


def _read_file() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def _restrict(path: Path, recursive: bool = False) -> None:
    """Doar utilizatorul curent poate citi fisierul sau folderul.

    Linux/macOS: chmod 600 pentru fisiere, 700 pentru foldere.
    Windows: scoate mostenirea de ACL si da acces doar utilizatorului curent.
    """
    if not path.exists():
        return
    if sys.platform != "win32":
        targets = [path, *path.rglob("*")] if recursive and path.is_dir() else [path]
        for target in targets:
            try:
                os.chmod(target, 0o700 if target.is_dir() else 0o600)
            except OSError:
                pass
        return
    user = os.environ.get("USERNAME")
    if not user:
        return
    cmd = ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(OI)(CI)F" if path.is_dir() else f"{user}:F"]
    if recursive:
        cmd.append("/T")
    subprocess.run(cmd, capture_output=True, check=False)


def store_token(base_url: str, token: str) -> str:
    """Pune tokenul in Credential Manager. Returneaza 'keyring' sau 'file' (rezerva)."""
    keyring = _keyring()
    if keyring is not None:
        try:
            keyring.set_password(KEYRING_SERVICE, base_url, token)
            return "keyring"
        except Exception:  # noqa: BLE001  (fara backend disponibil)
            pass
    return "file"


def forget_token(base_url: str) -> None:
    keyring = _keyring()
    if keyring is not None:
        try:
            keyring.delete_password(KEYRING_SERVICE, base_url)
        except Exception:  # noqa: BLE001
            pass
    if CONFIG_FILE.exists():
        data = _read_file()
        data.pop("token", None)
        CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_settings() -> Settings:
    dotenv = read_dotenv(find_dotenv())
    file_data = _read_file()
    base_url = (_env("ASE_MOODLE_URL", dotenv) or file_data.get("base_url") or DEFAULT_BASE_URL).rstrip("/")

    token = _env("ASE_MOODLE_TOKEN", dotenv)
    if token:
        source = "env" if os.environ.get("ASE_MOODLE_TOKEN") else "dotenv"
        return Settings(base_url=base_url, token=token.strip(), source=source)

    keyring = _keyring()
    if keyring is not None:
        try:
            stored = keyring.get_password(KEYRING_SERVICE, base_url)
        except Exception:  # noqa: BLE001
            stored = None
        if stored:
            return Settings(base_url=base_url, token=stored.strip(), source="keyring")

    if file_data.get("token"):
        legacy = file_data["token"].strip()
        # Migrare: tokenul in clar din config.json se muta in Credential Manager, cand e disponibil.
        if store_token(base_url, legacy) == "keyring":
            data = {k: v for k, v in file_data.items() if k != "token"}
            data["token_store"] = "keyring"
            CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            _restrict(CONFIG_FILE)
            return Settings(base_url=base_url, token=legacy, source="keyring")
        return Settings(base_url=base_url, token=legacy, source="file")

    raise SettingsError(
        "Lipseste tokenul. Ruleaza `ase-moodle login` (se deschide browserul) "
        "sau pune ASE_MOODLE_TOKEN in .env (vezi .env.example)."
    )


def save_settings(token: str, base_url: str = DEFAULT_BASE_URL, username: str | None = None) -> Path:
    """Salveaza tokenul (Credential Manager daca se poate) si URL-ul in config.json, fara token."""
    base_url = base_url.rstrip("/")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    where = store_token(base_url, token)
    data = {"base_url": base_url, "token_store": where}
    if username:
        data["username"] = username
    if where == "file":
        data["token"] = token
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _restrict(CONFIG_FILE)
    return CONFIG_FILE


def download_root() -> Path:
    """Folderul implicit pentru materiale: ASE_MOODLE_DOWNLOADS sau ~/ASE-Moodle."""
    dotenv = read_dotenv(find_dotenv())
    return Path(_env("ASE_MOODLE_DOWNLOADS", dotenv) or (Path.home() / "ASE-Moodle"))
