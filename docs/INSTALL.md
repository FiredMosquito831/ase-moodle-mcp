# Instalare

## Ce ai nevoie

| | Windows | Linux | macOS |
|---|---|---|---|
| Python | 3.10+ (testat cu 3.13) | 3.10+ (testat cu 3.12, Ubuntu 24.04) | 3.10+ (netestat) |
| `git` | da | da | da |
| Browser pentru login | Edge sau Chrome instalat (detectat automat) | Chromium (`python -m playwright install chromium`), sau `--method manual` | Chromium (netestat) |
| Clipboard pentru `--method manual` | PowerShell (inclus) | `xclip`, `xsel` sau `wl-paste` | `pbpaste` (inclus) |
| Credential Manager | Windows Credential Manager (inclus) | Secret Service (GNOME Keyring, KWallet), altfel fișier `chmod 600` | Keychain (netestat) |
| CLI-urile pe care vrei să le configurezi | `claude`, `codex`, `opencode`, `agy` | la fel | la fel |

Nu ai nevoie de toate CLI-urile. `ase-moodle install claude` funcționează și dacă ai doar Claude Code.

## Varianta 1: script automat

### Windows (PowerShell)

```powershell
git clone https://github.com/FiredMosquito831/ase-moodle.git
cd ase-moodle
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
```

Parametri: `-Source owner/repo`, `-Targets claude,codex`, `-Scope project`, `-SkipLogin`.

### Linux și macOS (bash)

```bash
git clone https://github.com/FiredMosquito831/ase-moodle.git
cd ase-moodle
bash scripts/bootstrap.sh
```

Variabile: `TARGETS="claude codex"`, `SCOPE=project`, `SKIP_LOGIN=1`, `SKIP_BROWSER=1`, `PYTHON=python3.12`, și un argument opțional `owner/repo` pentru sursa marketplace-ului.

**Atenție:** `SCOPE=project` și `-Scope project` instalează în folderul de unde rulezi scriptul, nu în clonă.

Scriptul face, în ordine: instalează pachetul, instalează Chromium (doar Linux/macOS, sărit cu `SKIP_BROWSER=1`), te loghează, configurează CLI-urile, rulează `doctor`.

## Varianta 2: pas cu pas

```powershell
git clone https://github.com/FiredMosquito831/ase-moodle.git
cd ase-moodle
python -m pip install -e .            # pachetul, editabil
ase-moodle login                      # token (browser sau manual)
ase-moodle install                    # toate CLI-urile, global
ase-moodle doctor                     # verificare
```

Pe Linux, înainte de `login` (metoda browser), instalează Chromium:

```bash
python3 -m playwright install chromium
```

Pe Linux, pentru `--method manual`, ai nevoie de un utilitar de clipboard (`xclip`, `xsel` sau `wl-paste`).

## Varianta 3: direct din GitHub

Fără clonă, dar cu acces la repo-ul privat (`gh auth login` sau SSH):

```powershell
python -m pip install git+https://github.com/FiredMosquito831/ase-moodle.git
ase-moodle login
ase-moodle install --source FiredMosquito831/ase-moodle
```

Fără `--source`, instalatorul folosește implicit `FiredMosquito831/ase-moodle` (GitHub). Din clonă, implicit folosește folderul clonei ca marketplace local.

## Instalare pe proiect

Dacă vrei ca serverul să fie disponibil doar într-un folder:

```powershell
cd D:\Projecte\mai-ales-acest-folder
ase-moodle install claude codex opencode --scope project
```

Folderul curent e folosit fiindcă nu ai dat `--project-dir`. Antigravity rămâne global. Detalii: [PLATFORMS.md](PLATFORMS.md).

## Actualizare

```powershell
cd ase-moodle
git pull
python -m pip install -e .
ase-moodle update
```

Repornește Claude Code după `update`. Dacă `pip install` cere să închizi procese, închide clienții MCP (`ase-moodle doctor` îi numără) și rulează din nou.

## Dezinstalare

```powershell
ase-moodle uninstall                  # toate CLI-urile, ambele scopuri
ase-moodle logout --forget-browser    # șterge tokenul și sesiunea din browser
python -m pip uninstall ase-moodle
```

## Verificare după instalare

```powershell
ase-moodle auth-status                # ești logat?
ase-moodle courses --year 3 --sem 1   # citire reală
ase-moodle doctor                     # starea platformelor
python -m unittest discover -s tests  # teste offline (din clona repo-ului)
```

## Probleme

Vezi [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
