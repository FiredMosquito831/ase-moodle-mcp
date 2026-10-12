# Depanare

Pornește mereu de la `ase-moodle doctor` și `ase-moodle auth-status`. Ele spun ce e instalat, ce token există și unde se află.

## Autentificare

### „Lipsește tokenul”

Nu ai rulat `ase-moodle login`, sau tokenul a fost șters.

```powershell
ase-moodle login
```

### Login-ul din browser expiră (`Nu am primit tokenul în timpul limitei`)

- Fereastra s-a deschis, dar nu te-ai logat (sau n-ai ajuns pe pagina cu tokenul). Rulează din nou și loghează-te cu Google.
- Crește timpul: `ase-moodle login --timeout 600`.
- Încearcă metoda manuală: `ase-moodle login --method manual`.

### „Browserul pentru login nu e instalat”

Pe Linux (și pe macOS) Playwright are nevoie de Chromium:

```bash
python3 -m playwright install chromium
```

Sau folosește `--method manual`.

### Browserul se deschide, dar Google refuză login-ul

Unele conturi Google cer verificare suplimentară. Termin-o în fereastră. Dacă Google afișează „browserul nu e sigur”, folosește `--method manual`: tokenul îl copiezi din browserul tău obișnuit.

### Metoda manual nu găsește tokenul

- Pe Linux, instalează `xclip`, `xsel` sau `wl-paste`. Fără ele, clipboard-ul nu se citește.
- Verifică că ai copiat exact șirul de 32 de caractere (fără spații).
- Pentru test, `ase-moodle login --token-stdin` acceptă tokenul direct.

### `auth-status` spune că tokenul nu merge

Tokenul a fost resetat în Moodle sau a expirat. Obține unul nou:

```powershell
ase-moodle login
```

### Credential Manager nu e disponibil (Linux)

`doctor` arată `token source: file`. Tokenul e în `~/.ase-moodle/config.json`, cu `chmod 600`. Dacă vrei Secret Service, instalează GNOME Keyring sau KWallet și rulează din nou `ase-moodle login`.

## Instalare

### `doctor` arată `error` pentru o platformă

- `nu apare în lista`: pluginul nu e instalat. Rulează `ase-moodle install <platforma>`.
- `<cli> nu este în PATH`: CLI-ul nu e instalat sau nu e în PATH. Instalează-l sau sari peste el (`install` îl marchează `skipped`).

### `ase-moodle-mcp` nu e în PATH

Pachetul nu e instalat, sau Scripts-ul Python nu e în PATH.

```powershell
python -m pip install -e .
```

Pe Linux, dacă ai instalat în venv, activează venv-ul înainte.

### `pip install -e .` eșuează pe Windows cu „Access denied” pe `ase-moodle-mcp.exe`

Un client MCP rulează și blochează executabilul. Închide Claude Code, Codex, opencode sau Antigravity (sau doar procesele `ase-moodle-mcp`), apoi rulează din nou. `doctor` le numără.

### Claude Code nu vede update-ul

Repornește Claude Code. Pluginul se încarcă la pornire.

### Codex nu încarcă serverul pentru proiect

Codex cere să marchezi folderul ca proiect de încredere. Deschide folderul și acceptă cererea. Verifică și că fișierul `.codex/config.toml` există și conține `[mcp_servers.ase-moodle]`.

### `opencode.json` nu e JSON valid

Instalatorul se oprește și nu-l modifică. Corectează fișierul (virgule, ghilimele) și rulează din nou. Există și copie `.bak` de la rularea anterioară.

### Antigravity: `--scope project` e sărit

Așa e: Antigravity nu are instalare pe proiect. Rămâne global. Vezi [PLATFORMS.md](PLATFORMS.md).

### Două servere `ase-moodle` apar în client

Instalare veche (globală) și instalare de proiect. Rulează `ase-moodle install <platforma> --scope <scopul-dorit>`: scopul celălalt se curăță automat.

## Scrieri și confirmări

### `needs_confirmation` (cod 2)

Scrierea nu are confirmare. Dacă tu ești cel care rulează comanda, adaugă `--yes` după ce ai verificat ce trimiți. Dacă e un agent, agentul trebuie să-ți arate conținutul și să ceară aprobare.

### `Tema N nu are ciorne`

Tema nu are ciorne activate. Salvarea ar trimite fișierul direct. Opțiuni:

- trimitere finală: `--submit` (rămâne ce ți-ai propus);
- salvare directă, doar dacă studentul vrea asta: `--allow-direct`.

Vezi [SAFETY.md](SAFETY.md).

### `Tema N nu apare printre cursurile tale`

ID-ul nu e al tău, sau nu e din cursurile la care ești înscris. Verifică cu `ase-moodle assignments`.

### Quiz: `Campuri necunoscute`

Numele câmpurilor din `quiz-answer` nu se potrivesc cu cele din `quiz-questions`. Copiază numele exact din răspuns.

### Quiz: `Nu s-a putut porni încercarea`

Quizul e închis, sau ai atins limita de încercări. Mesajul Moodle explică.

## Descărcare

### Materiale lipsă

- Rulează din nou: fișierele cu aceeași dimensiune se sar, cele lipsă se descarcă.
- Verifică `_rezumat.json` din folderul de descărcare: are erorile și avertismentele.
- Un curs fără fișiere e normal (multe cursuri au doar forumuri sau linkuri).

### `EȘUAT` la un fișier

Link-ul a expirat sau nu ai acces. Mesajul e în `_rezumat.json`.

## Linux

### Testele eșuează

Verifică versiunea Python (3.10+) și că ai rulat `pip install -e .` în același venv.

### `xclip`/`xsel`/`wl-paste` lipsesc

Instalează-le din managerul de pachete:

```bash
sudo apt install xclip        # X11
sudo apt install wl-clipboard # Wayland
```

## Diverse

### `doctor` raportează metadatele pachetului rupte

Rulează `python -m pip install -e .` după ce închizi procesele MCP. Metadatele se repară.

### Comanda `ase-moodle` nu există

Pachetul nu e instalat în Python-ul din PATH. Folosește `python -m ase_moodle.cli ...` sau instalează din nou.

### Unde sunt log-urile

Pachetul nu scrie fișiere de log. Erorile apar pe stderr (CLI) sau în răspunsul uneltei (MCP). Serverul MCP scrie mesajele lui pe stderr, pe care clientul le poate arăta în interfață.

## Când ceva nu e clar

Rulează `ase-moodle doctor` și salvează output-ul (nu conține tokenul). Cu el, problema e de obicei ușor de găsit.
