#!/usr/bin/env python3
"""Sursa unica a versiunii: scrie sau verifica fiecare copie a versiunii si a datei de release.

Sursele de adevar sunt `version` din pyproject.toml si `RELEASE_DATE` din src/ase_moodle/__init__.py.
Restul locurilor (manifeste, copii, pinuri `ase-moodle==` si `--exclude-newer` din fisierele urmarite)
se scriu de aici si se verifica de aici (si din tests/test_release.py).

Utilizare (din radacina repo-ului):
    python scripts/release.py 0.2.5                  versiunea noua, data = azi (UTC)
    python scripts/release.py 0.2.5 --date 2026-11-02
    python scripts/release.py --check                nu schimba nimic; exit 1 la orice nepotrivire
    python scripts/release.py --check --expect 0.2.5 in plus: tagul trebuie sa fie versiunea din pyproject

Doar biblioteca standard. Fisierele se citesc si se scriu cu newline="" (LF ramane LF).

Un loc nou (launcherul, pachetul npm) = o intrare in `locations()` si, daca e o copie, in `copies()`.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}T00:00:00Z")

# Pinurile din fisierele urmarite. Un placeholder (`ase-moodle==X.Y.Z`, `--exclude-newer <data>`) nu se potriveste.
PIN_RE = re.compile(r"ase-moodle==(\d[0-9A-Za-z.+!-]*)")
EXCLUDE_NEWER_RE = re.compile(r"--exclude-newer(?![\w-])(?:=|\s+)[\"']?(\d{4}-\d{2}-\d{2}[^\s\"'`)\],;]*)")

# Fisiere care contin pinuri de exemplu sau tiparele insele; nu se scaneaza.
SCAN_SKIP = {"scripts/release.py", "tests/test_release.py"}
# Fara git (de exemplu dintr-o arhiva sdist): se scaneaza doar aceste locuri.
SCAN_FALLBACK = ["README.md", "docs", "plugins", "npm", "src", "scripts", ".github"]
TEXT_SUFFIXES = {".md", ".py", ".json", ".toml", ".yml", ".yaml", ".js", ".mjs", ".cjs", ".txt", ".html", ".sh", ".ps1", ".cfg", ".ini"}


class ReleaseError(RuntimeError):
    """Un loc nu are forma asteptata (nu se poate citi sau scrie)."""


def read_text(path: Path) -> str:
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


def write_text(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


@dataclass(frozen=True)
class TextField:
    """O valoare intr-un fisier text, prinsa de grupul `value` al unei expresii (o singura potrivire)."""

    path: str
    pattern: str
    kind: str  # "version" sau "date"
    label: str

    def _match(self, text: str) -> re.Match:
        matches = list(re.finditer(self.pattern, text, re.MULTILINE))
        if len(matches) != 1:
            raise ReleaseError(f"{self.path}: {self.label}: {len(matches)} potriviri pentru {self.pattern!r} (astept 1)")
        return matches[0]

    def read(self, root: Path) -> str:
        return self._match(read_text(root / self.path)).group("value")

    def write(self, root: Path, value: str) -> bool:
        path = root / self.path
        text = read_text(path)
        match = self._match(text)
        if match.group("value") == value:
            return False
        write_text(path, text[: match.start("value")] + value + text[match.end("value"):])
        return True


@dataclass(frozen=True)
class JsonField:
    """O valoare dintr-un JSON (citita cu json); scrierea inlocuieste doar textul ei, formatarea ramane."""

    path: str
    keys: tuple[str, ...]
    kind: str
    label: str

    def read(self, root: Path) -> str:
        data = json.loads(read_text(root / self.path))
        for key in self.keys:
            if not isinstance(data, dict) or key not in data:
                raise ReleaseError(f"{self.path}: lipseste cheia {'.'.join(self.keys)}")
            data = data[key]
        if not isinstance(data, str):
            raise ReleaseError(f"{self.path}: {'.'.join(self.keys)} nu este un sir")
        return data

    def write(self, root: Path, value: str) -> bool:
        old = self.read(root)
        if old == value:
            return False
        path = root / self.path
        text = read_text(path)
        pattern = re.compile(r'("%s"\s*:\s*")%s(")' % (re.escape(self.keys[-1]), re.escape(old)))
        if len(pattern.findall(text)) != 1:
            raise ReleaseError(f"{self.path}: nu pot inlocui sigur {'.'.join(self.keys)} (valoarea apare de mai multe ori)")
        write_text(path, pattern.sub(lambda m: m.group(1) + value + m.group(2), text))
        return True


def locations() -> list:
    """Fiecare copie a versiunii sau a datei. Primele doua sunt sursele de adevar."""
    return [
        TextField("pyproject.toml", r'^version = "(?P<value>[^"]+)"$', "version", "[project].version"),
        TextField("src/ase_moodle/__init__.py", r'^RELEASE_DATE = "(?P<value>[^"]+)"$', "date", "RELEASE_DATE"),
        TextField("src/ase_moodle/__init__.py", r'^__version__ = "(?P<value>[^"]+)"$', "version", "__version__"),
        JsonField("plugins/ase-moodle/.claude-plugin/plugin.json", ("version",), "version", "plugin Claude"),
        JsonField("plugins/ase-moodle/.codex-plugin/plugin.json", ("version",), "version", "plugin Codex"),
        JsonField("plugins/ase-moodle/plugin.json", ("version",), "version", "plugin Antigravity"),
        JsonField(".claude-plugin/marketplace.json", ("metadata", "version"), "version", "marketplace"),
    ]


def copies() -> list[tuple[str, str]]:
    """(sursa, copie): copia trebuie sa fie identica octet cu octet."""
    return [
        ("src/ase_moodle/data/SKILL.md", "plugins/ase-moodle/skills/ase-moodle/SKILL.md"),
    ]


def sources(root: Path) -> tuple[str, str]:
    """(versiune, data) din sursele de adevar."""
    fields = locations()
    return fields[0].read(root), fields[1].read(root)


def scanned_files(root: Path) -> list[str]:
    """Fisierele urmarite de git (sau, fara git, locurile din SCAN_FALLBACK), ca cai relative cu `/`."""
    names: list[str] | None = None
    if (root / ".git").exists():
        try:
            out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True).stdout
            names = [n for n in out.decode("utf-8").split("\0") if n]
        except (OSError, subprocess.CalledProcessError):
            names = None
    if names is None:
        names = []
        for entry in SCAN_FALLBACK:
            base = root / entry
            if base.is_file():
                names.append(entry)
            elif base.is_dir():
                names.extend(p.relative_to(root).as_posix() for p in sorted(base.rglob("*")) if p.is_file())
    result = []
    for name in names:
        path = root / name
        if name in SCAN_SKIP or path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        result.append(name)
    return sorted(result)


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def scan_pins(root: Path, version: str, date: str) -> list[str]:
    """Fiecare `ase-moodle==<v>` si `--exclude-newer <d>` dintr-un fisier urmarit trebuie sa fie cel curent."""
    problems = []
    for name in scanned_files(root):
        try:
            text = read_text(root / name)
        except UnicodeDecodeError:
            continue
        for match in PIN_RE.finditer(text):
            if match.group(1) != version:
                problems.append(f"{name}:{_line(text, match.start())}: ase-moodle=={match.group(1)} (astept ase-moodle=={version})")
        for match in EXCLUDE_NEWER_RE.finditer(text):
            if match.group(1) != date:
                problems.append(f"{name}:{_line(text, match.start())}: --exclude-newer {match.group(1)} (astept {date})")
    return problems


def check(root: Path = ROOT, expect: str | None = None) -> list[str]:
    """Lista nepotrivirilor (goala = totul e coerent). Nu schimba nimic."""
    problems: list[str] = []
    try:
        version, date = sources(root)
    except (OSError, ReleaseError) as exc:
        return [str(exc)]
    if not VERSION_RE.fullmatch(version):
        problems.append(f"pyproject.toml: versiunea {version!r} nu are forma X.Y.Z")
    if not DATE_RE.fullmatch(date):
        problems.append(f"src/ase_moodle/__init__.py: RELEASE_DATE {date!r} nu are forma YYYY-MM-DDT00:00:00Z")
    else:
        try:
            _dt.datetime.strptime(date, DATE_FORMAT)
        except ValueError:
            problems.append(f"src/ase_moodle/__init__.py: RELEASE_DATE {date!r} nu este o data valida")
    if expect is not None and expect != version:
        problems.append(f"tagul cere versiunea {expect}, dar pyproject.toml are {version}")
    for field in locations()[2:]:
        expected = version if field.kind == "version" else date
        try:
            found = field.read(root)
        except (OSError, ReleaseError) as exc:
            problems.append(str(exc))
            continue
        if found != expected:
            problems.append(f"{field.path}: {field.label} = {found!r} (astept {expected!r})")
    for source, copy in copies():
        try:
            if (root / source).read_bytes() != (root / copy).read_bytes():
                problems.append(f"{copy}: nu este identic cu {source}")
        except OSError as exc:
            problems.append(f"{copy}: {exc}")
    problems.extend(scan_pins(root, version, date))
    return problems


def _replace_pins(root: Path, version: str, date: str) -> list[str]:
    changed = []
    for name in scanned_files(root):
        path = root / name
        try:
            text = read_text(path)
        except UnicodeDecodeError:
            continue
        new = PIN_RE.sub(lambda m: "ase-moodle==" + version, text)
        new = EXCLUDE_NEWER_RE.sub(lambda m: m.group(0)[: m.start(1) - m.start(0)] + date, new)
        if new != text:
            write_text(path, new)
            changed.append(name)
    return changed


def apply(root: Path, version: str, date: str) -> list[str]:
    """Scrie versiunea si data in fiecare loc; intoarce fisierele schimbate."""
    if not VERSION_RE.fullmatch(version):
        raise ReleaseError(f"versiunea {version!r} nu are forma X.Y.Z")
    if not DATE_RE.fullmatch(date):
        raise ReleaseError(f"data {date!r} nu are forma YYYY-MM-DDT00:00:00Z")
    changed: list[str] = []
    for field in locations():
        if field.write(root, version if field.kind == "version" else date) and field.path not in changed:
            changed.append(field.path)
    for source, copy in copies():
        data = (root / source).read_bytes()
        target = root / copy
        if not target.exists() or target.read_bytes() != data:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            changed.append(copy)
    for name in _replace_pins(root, version, date):
        if name not in changed:
            changed.append(name)
    return changed


def release_date(day: str | None) -> str:
    """`YYYY-MM-DD` (sau azi, in UTC) -> `YYYY-MM-DDT00:00:00Z`."""
    if day is None:
        day = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    try:
        parsed = _dt.datetime.strptime(day, "%Y-%m-%d")
    except ValueError as exc:
        raise ReleaseError(f"--date {day!r} nu are forma YYYY-MM-DD") from exc
    return parsed.strftime("%Y-%m-%dT00:00:00Z")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrie sau verifica versiunea si data de release in fiecare loc.")
    parser.add_argument("version", nargs="?", help="versiunea noua X.Y.Z (cu --check: versiunea asteptata)")
    parser.add_argument("--date", help="data release-ului, YYYY-MM-DD (implicit: azi, UTC)")
    parser.add_argument("--check", action="store_true", help="nu schimba nimic; exit 1 la orice nepotrivire")
    parser.add_argument("--expect", help="cu --check: versiunea ceruta de tag (vX.Y.Z fara v)")
    parser.add_argument("--root", default=str(ROOT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = Path(args.root)

    if args.check:
        if args.date:
            parser.error("--date nu se foloseste cu --check")
        expect = args.expect or args.version
        problems = check(root, expect)
        if problems:
            print(f"release: {len(problems)} nepotriviri:", file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
            return 1
        version, date = sources(root)
        print(f"release: ok, versiunea {version}, data {date}")
        return 0

    if args.expect:
        parser.error("--expect se foloseste doar cu --check")
    if not args.version:
        parser.error("lipseste versiunea (X.Y.Z) sau --check")
    try:
        changed = apply(root, args.version, release_date(args.date))
    except (OSError, ReleaseError) as exc:
        print(f"release: {exc}", file=sys.stderr)
        return 2
    for name in changed:
        print(f"scris: {name}")
    problems = check(root)
    if problems:
        print("release: dupa scriere raman nepotriviri:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    version, date = sources(root)
    print(f"release: ok, versiunea {version}, data {date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
