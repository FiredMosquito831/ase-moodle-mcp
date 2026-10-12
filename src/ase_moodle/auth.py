"""Autentificare: obtine tokenul pentru contul Moodle fara sa-l copiezi manual.

Metode:
- browser (implicit daca Playwright e instalat): deschide Edge/Chrome cu un profil dedicat. Prima data te loghezi
  cu Google in fereastra. Apoi tokenul se ia automat prin acelasi flux SSO pe care il foloseste aplicatia Moodle
  Mobile (launch.php -> moodlemobile://token=...). Rularile urmatoare sunt automate, fara login.
- manual: deschide pagina de login si citeste tokenul din clipboard dupa ce il copiezi din Chei de securitate.
"""

from __future__ import annotations

import base64
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any

from .client import MoodleClient
from .config import CONFIG_DIR, DEFAULT_BASE_URL, SettingsError, load_settings, save_settings

SERVICE = "moodle_mobile_app"
LAUNCH_PATH = "/admin/tool/mobile/launch.php"
TOKEN_PAGE = "/user/managetoken.php"
PROFILE_DIR = CONFIG_DIR / "browser-profile"

_TOKEN_RE = re.compile(r"[0-9a-f]{32}")
_SCHEME_RE = re.compile(r"moodlemobile://token=(?P<payload>\S+)")
_MANAGE_ROW_RE = re.compile(r"([0-9a-f]{32})</td>\s*<td[^>]*>\s*(?:<[^>]+>\s*)*Moodle mobile web service", re.IGNORECASE)


class AuthError(RuntimeError):
    """Autentificarea nu a reusit; mesajul spune ce sa faci."""


def is_valid_token(value: str | None) -> bool:
    return bool(value) and _TOKEN_RE.fullmatch(value.strip()) is not None


def decode_launch_url(url: str) -> str:
    """Extrage wstoken dintr-un redirect moodlemobile://token=BASE64, unde BASE64 = 'PRIVAT:::WSTOKEN'.

    Tokenul este ultimul sir hex de 32 de caractere din payloadul decodat. Nu apare niciodata in mesajele de eroare.
    """
    match = _SCHEME_RE.search(url.strip())
    if not match:
        raise AuthError("Redirectul nu are forma moodlemobile://token=...")
    payload = urllib.parse.unquote(match.group("payload")).replace("-", "+").replace("_", "/")
    payload += "=" * (-len(payload) % 4)
    try:
        decoded = base64.b64decode(payload).decode("utf-8", "replace")
    except ValueError as exc:
        raise AuthError("Payloadul redirectului nu este base64 valid") from exc
    candidates = _TOKEN_RE.findall(decoded)
    if not candidates:
        raise AuthError("Payloadul decodat nu contine un token de 32 caractere hex")
    return candidates[-1]


def _pick_token(urls: list[str]) -> str:
    """Primul redirect moodlemobile:// care contine un token valid."""
    if not urls:
        raise AuthError(
            "Nu am primit tokenul in timpul limitei. Daca fereastra a aparut, ai terminat login-ul cu Google? "
            "Poti incerca si: ase-moodle login --method manual"
        )
    problems = []
    for url in urls:
        try:
            return decode_launch_url(url)
        except AuthError as exc:
            problems.append(str(exc))
    raise AuthError("Am primit redirect moodlemobile://, dar niciunul nu are un token valid: " + "; ".join(sorted(set(problems))))


def token_from_managetoken_html(html: str) -> str | None:
    """Tokenul 'Moodle mobile web service' din pagina Chei de securitate, daca exista."""
    match = _MANAGE_ROW_RE.search(html)
    return match.group(1) if match else None


def _browser_channel() -> str | None:
    """Edge sau Chrome instalat, ca sa nu descarcam Chromium."""
    if sys.platform != "win32":
        return None
    roots = [os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")]
    candidates = [
        ("msedge", r"Microsoft\Edge\Application\msedge.exe"),
        ("chrome", r"Google\Chrome\Application\chrome.exe"),
    ]
    for channel, rel in candidates:
        for root in roots:
            if root and (Path(root) / rel).exists():
                return channel
    return None


def playwright_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("playwright") is not None


def login_browser(base_url: str, timeout_s: int = 300, headless: bool = False) -> str:
    """Deschide browserul, asteapta login-ul (daca e nevoie) si prinde tokenul din redirectul SSO."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise AuthError("Playwright nu este instalat: python -m pip install playwright") from exc

    passport = secrets.token_hex(16)
    launch_url = f"{base_url}{LAUNCH_PATH}?service={SERVICE}&passport={passport}"
    captured: list[str] = []
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    from .config import _restrict

    _restrict(PROFILE_DIR, recursive=True)  # profilul contine sesiunea Google: doar tu il poti citi
    options: dict[str, Any] = {"headless": headless, "ignore_default_args": ["--enable-automation"]}
    channel = _browser_channel()
    if channel:
        options["channel"] = channel

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE_DIR), **options)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.on("request", lambda req: captured.append(req.url) if req.url.startswith("moodlemobile://") else None)
            try:
                page.goto(launch_url, wait_until="commit", timeout=60_000)
            except Exception:  # navigarea catre schema moodlemobile:// este anulata de browser, asta e asteptat
                pass
            deadline = time.monotonic() + timeout_s
            while not captured and time.monotonic() < deadline:
                page.wait_for_timeout(500)
        finally:
            ctx.close()

    return _pick_token(captured)


def open_token_page(base_url: str) -> str:
    """Deschide pagina de login, care duce direct la Chei de securitate dupa autentificare."""
    url = f"{base_url}/login/index.php?wantsurl={urllib.parse.quote(base_url + TOKEN_PAGE, safe='')}"
    webbrowser.open(url)
    return url


def read_clipboard() -> str:
    if sys.platform == "win32":
        cmd = ["powershell", "-NoProfile", "-Command", "Get-Clipboard"]
    elif sys.platform == "darwin":
        cmd = ["pbpaste"]
    else:
        cmd = ["xclip", "-selection", "clipboard", "-o"]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def wait_for_clipboard_token(timeout_s: int = 180) -> str:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        text = read_clipboard()
        if is_valid_token(text):
            return text
        time.sleep(1)
    raise AuthError("Nu am gasit un token valid in clipboard. Copiaza tokenul si ruleaza din nou, sau foloseste --token.")


def verify_token(base_url: str, token: str) -> str:
    """Verifica tokenul cu un apel real. Returneaza numele utilizatorului."""
    with MoodleClient(base_url, token) as client:
        return client.siteinfo.get("fullname", "")


def authenticate(base_url: str | None = None, method: str = "auto", timeout_s: int = 300) -> dict[str, Any]:
    base_url = (base_url or os.environ.get("ASE_MOODLE_URL") or DEFAULT_BASE_URL).rstrip("/")
    if method == "auto":
        method = "browser" if playwright_available() else "manual"
    if method == "browser":
        token = login_browser(base_url, timeout_s)
    elif method == "manual":
        open_token_page(base_url)
        token = wait_for_clipboard_token(timeout_s)
    else:
        raise AuthError(f"Metoda necunoscuta: {method}. Valide: auto, browser, manual")
    user = verify_token(base_url, token)
    path = save_settings(token, base_url)
    return {"ok": True, "method": method, "user": user, "saved_to": str(path)}


def status() -> dict[str, Any]:
    try:
        settings = load_settings()
    except SettingsError as exc:
        return {"logged_in": False, "reason": str(exc)}
    try:
        user = verify_token(settings.base_url, settings.token)
    except Exception as exc:  # noqa: BLE001
        return {"logged_in": False, "reason": f"tokenul nu merge: {exc}"}
    return {"logged_in": True, "user": user, "base_url": settings.base_url}


def logout(forget_browser: bool = False) -> dict[str, Any]:
    """Sterge tokenul (Credential Manager si rezerva din config). Cu forget_browser si sesiunea Google."""
    import json

    from .config import CONFIG_FILE, forget_token

    removed = []
    base_url = DEFAULT_BASE_URL
    if CONFIG_FILE.exists():
        base_url = json.loads(CONFIG_FILE.read_text(encoding="utf-8")).get("base_url", DEFAULT_BASE_URL)
    forget_token(base_url)
    removed.append("token")
    if forget_browser and PROFILE_DIR.exists():
        shutil.rmtree(PROFILE_DIR, ignore_errors=True)
        removed.append(str(PROFILE_DIR))
    return {"ok": True, "removed": removed}
