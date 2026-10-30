# Instalare

## Ce ai nevoie

| | Windows | Linux | macOS |
|---|---|---|---|
| Python | 3.10+ (testat cu 3.13) | 3.10+ (testat cu 3.12, Ubuntu 24.04) | 3.10+ (netestat) |
| `git` | da | da | da |
| `pipx` | `python -m pip install --user pipx` | `python3 -m pip install --user pipx` | la fel |
| Node.js 18+ și npm | doar pentru varianta npm | doar pentru varianta npm | doar pentru varianta npm |
| Browser pentru login | Edge sau Chrome instalat (detectat automat) | Chromium (comanda afișată de `ase-moodle login`), sau `--method manual` | Chromium (netestat) |
| Clipboard pentru `--method manual` | PowerShell (inclus) | `xclip`, `xsel` sau `wl-paste` | `pbpaste` (inclus) |
| Credential Manager | Windows Credential Manager (inclus) | Secret Service (GNOME Keyring, KWallet), altfel fișier `chmod 600` | Keychain (netestat) |
| CLI-urile pe care vrei să le configurezi | `claude`, `codex`, `opencode`, `agy` | la fel | la fel |

Nu ai nevoie de toate CLI-urile. `ase-moodle install claude` funcționează și dacă ai doar Claude Code.

Alege una dintre variantele 1 și 2. Rezultatul e același: pachetul Python `ase-moodle`, cu comenzile `ase-moodle` și `ase-moodle-mcp` în PATH.

## Varianta 1: pipx (recomandată)

Pipx instalează aplicațiile Python în medii izolate și le pune în `PATH`. Îl instalezi o singură dată.

```bash
pipx install git+https://github.com/FiredMosquito831/ase-moodle-mcp.git
ase-moodle login
ase-moodle install
ase-moodle doctor
```

| Comandă | Ce face |
|---|---|
| `pipx install git+…` | instalează `ase-moodle` și serverul MCP, izolat de restul Python-ului |
| `ase-moodle login` | deschide browserul; te loghezi cu Google o singură dată, iar tokenul se salvează în Credential Manager |
| `ase-moodle install` | adaugă pluginul în toate CLI-urile găsite: Claude Code, Codex, opencode, Antigravity |
| `ase-moodle doctor` | verifică instalarea și arată ce lipsește |

`ase-moodle install` pune pluginul global, pentru tot calculatorul. Pentru folderul curent, folosește `ase-moodle install --scope project` (vezi [Instalare pe proiect](#instalare-pe-proiect)).

## Varianta 2: npm

Pachetul npm `ase-moodle-mcp` e un launcher. Codul e în pachetul Python, pe care îl instalează scriptul de instalare, prin pipx. Ai nevoie de Node.js 18+ și de Python 3.10+. Git e recomandat, nu obligatoriu.

```bash
npm install -g ase-moodle-mcp
ase-moodle login
ase-moodle install
ase-moodle doctor
```

Scriptul de instalare (`postinstall`) face, în ordine:

1. Dacă modulul `ase_moodle` există deja în Python, nu face nimic.
2. Altfel, instalează pipx cu `pip --user`, dacă lipsește, și rulează `pipx ensurepath`.
3. Instalează pachetul Python prin pipx, din prima sursă disponibilă: `git` (dacă e în PATH), apoi arhiva de pe GitHub descărcată cu `curl`, apoi arhiva direct, pe care pip o descarcă singur.

Scriptul nu oprește niciodată `npm install`. Dacă un pas eșuează, afișează ce trebuie făcut. După ce rezolvi cauza, reia cu:

```bash
npm rebuild -g ase-moodle-mcp
```

Instalarea durează câteva minute, iar npm nu afișează mesajele scriptului până la final. Ca să vezi progresul:

```bash
npm install -g --foreground-scripts ase-moodle-mcp
```

**Fără instalare globală.** După ce ai npm, poți rula orice comandă direct:

```bash
npx ase-moodle-mcp auth-status
npx ase-moodle-mcp courses --year 3 --sem 1
```

`npx ase-moodle-mcp` trimite argumentele către CLI, la fel ca `ase-moodle`. La prima rulare instalează și pachetul Python, cum face `npm install`. Pentru clienții MCP folosește instalarea globală, ca să existe o comandă fixă `ase-moodle-mcp` în PATH. Detalii despre cele două binare: [MCP.md](MCP.md).

## Varianta 3: script automat

Scripturile din repo fac tot din clonă: instalează pachetul, instalează Chromium (doar Linux și macOS), te loghează, configurează CLI-urile și rulează `doctor`.

```bash
git clone https://github.com/FiredMosquito831/ase-moodle-mcp.git
cd ase-moodle-mcp
```

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
```

Parametri: `-Source owner/repo`, `-Targets claude,codex`, `-Scope project`, `-SkipLogin`.

**Linux și macOS (bash):**

```bash
bash scripts/bootstrap.sh
```

Variabile: `TARGETS="claude codex"`, `SCOPE=project`, `SKIP_LOGIN=1`, `SKIP_BROWSER=1`, `PYTHON=python3.12`, și un argument opțional `owner/repo` pentru sursa marketplace-ului.

**Atenție:** `SCOPE=project` și `-Scope project` instalează în folderul de unde rulezi scriptul, nu în clonă.

## Varianta 4: pas cu pas, din clonă

Pentru dezvoltare, unde vrei ca modificările din cod să fie active imediat:

```bash
git clone https://github.com/FiredMosquito831/ase-moodle-mcp.git
cd ase-moodle-mcp
python -m pip install -e .            # pachetul, editabil
ase-moodle login                      # token (browser sau manual)
ase-moodle install                    # toate CLI-urile, global
ase-moodle doctor                     # verificare
```

Pe Linux, înainte de `login` (metoda browser), instalează Chromium cu același Python cu care ai instalat pachetul (comanda exactă o afișează și `ase-moodle login`, dacă browserul lipsește):

```bash
python -m playwright install chromium
```

Pe Linux, pentru `--method manual`, ai nevoie de un utilitar de clipboard (`xclip`, `xsel` sau `wl-paste`).

## Varianta 5: pip direct

Fără pipx, în Python-ul tău global sau într-un venv:

```bash
python -m pip install git+https://github.com/FiredMosquito831/ase-moodle-mcp.git
ase-moodle login
ase-moodle install
```

## Instalare pe proiect

Dacă vrei ca serverul să fie disponibil doar într-un folder:

```powershell
cd D:\Projecte\mai-ales-acest-folder
ase-moodle install claude codex opencode --scope project
```

Folderul curent e folosit fiindcă nu ai dat `--project-dir`. Antigravity rămâne global. Detalii: [PLATFORMS.md](PLATFORMS.md).

## Actualizare

### Cu pipx

```bash
pipx install --force git+https://github.com/FiredMosquito831/ase-moodle-mcp.git
ase-moodle update
```

`pipx upgrade` nu aduce codul nou din GitHub, deci folosește `--force`.

### Cu npm

```bash
npm install -g ase-moodle-mcp@latest
pipx install --force git+https://github.com/FiredMosquito831/ase-moodle-mcp.git
ase-moodle update
```

Scriptul npm nu actualizează pachetul Python dacă există deja, așa că îl actualizezi separat, cu aceeași metodă ca la instalare. Dacă l-ai instalat cu pip: `python -m pip install --upgrade git+https://github.com/FiredMosquito831/ase-moodle-mcp.git`.

Repornește Claude Code după `update`. Dacă actualizarea cere să închizi procese, închide clienții MCP (`ase-moodle doctor` îi numără) și rulează din nou.

## Dezinstalare

Pachetul are mai multe părți, instalate separat. Rulează întâi pașii care folosesc `ase-moodle`, apoi șterge pachetul.

```bash
ase-moodle uninstall                  # scoate pluginul din toate CLI-urile, ambele scopuri
ase-moodle logout --forget-browser    # șterge tokenul și sesiunea Google din browser
npm uninstall -g ase-moodle-mcp       # doar dacă ai instalat cu npm: scoate launcherul
pipx uninstall ase-moodle             # pachetul Python, dacă l-ai instalat cu pipx
```

Dacă ai instalat pachetul Python cu pip, în loc de `pipx uninstall` rulează `python -m pip uninstall ase-moodle`.

`npm uninstall` nu șterge pachetul Python. Pluginul din proiecte e scris în folderul unde l-ai instalat. Pentru fiecare astfel de folder, rulează `ase-moodle uninstall --project-dir <folder>`.

## Verificare după instalare

```bash
ase-moodle auth-status                # ești logat?
ase-moodle courses --year 3 --sem 1   # citire reală
ase-moodle doctor                     # starea platformelor
```

Teste offline (din clona repo-ului): `python -m unittest discover -s tests`.

## Probleme

Vezi [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
