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

Pachetul nu e instalat, sau directorul executabilelor pipx nu e în PATH.

```bash
pipx install --force git+https://github.com/FiredMosquito831/ase-moodle-mcp.git
pipx ensurepath          # apoi deschide un terminal nou
```

Dacă ai instalat cu `pip` într-un venv, activează venv-ul înainte de comandă.

### `pipx install` eșuează pe Windows cu „Access denied” pe `ase-moodle-mcp.exe`

Un client MCP rulează și blochează executabilul. Închide Claude Code, Codex, opencode sau Antigravity (sau doar procesele `ase-moodle-mcp`), apoi rulează din nou. `doctor` le numără.

### Claude Code nu vede update-ul

Repornește Claude Code. Pluginul se încarcă la pornire.

### Claude Code nu detectează MCP-ul în folderul proiectului

Verifică în ordine:

1. **Repornește Claude Code în folderul proiectului.** O sesiune deschisă înainte de o schimbare de scop păstrează lista veche de servere.
2. **În sesiune, rulează `/mcp`.** Ar trebui să apară `plugin:ase-moodle:ase-moodle` cu statusul conectat.
3. **Verifică din terminal:** `ase-moodle claude doctor --project-dir <folderul-proiectului>`. Pentru scopul de proiect ar trebui să vezi `plugin (project)` cu `ok` și `mcp server` cu `conectat`.
4. **Verifică fișierul:** `.claude/settings.json` din folder trebuie să conțină `ase-moodle@ase-moodle-marketplace` în `enabledPlugins`.
5. **Dacă Claude Code cere aprobarea marketplace-ului sau a folderului,** acceptă. Fără asta, pluginul de proiect e ignorat.

Dacă tot nu apare după asta, `ase-moodle claude install --scope project` rescrie configurarea. Operația e idempotentă.

### Codex nu încarcă serverul pentru proiect

Codex cere să marchezi folderul ca proiect de încredere. Deschide folderul și acceptă cererea. Verifică și că fișierul `.codex/config.toml` există și conține `[mcp_servers.ase-moodle]`.

### `opencode.json` nu e JSON valid

Instalatorul se oprește și nu-l modifică. Corectează fișierul (virgule, ghilimele) și rulează din nou. Există și copie `.bak` de la rularea anterioară.

### Antigravity: `--scope project` e sărit

Așa e: Antigravity nu are instalare pe proiect. Rămâne global. Vezi [PLATFORMS.md](PLATFORMS.md).

### Două servere `ase-moodle` apar în client

Instalare veche (globală) și instalare de proiect. Rulează `ase-moodle install <platforma> --scope <scopul-dorit>`: scopul celălalt se curăță automat.

## npm și npx

### `npm install` s-a terminat, dar `ase-moodle login` spune că lipsește pachetul Python

Scriptul de instalare n-a reușit (pipx, git sau rețea). Rulează `npm install -g --foreground-scripts ase-moodle-mcp` ca să vezi mesajul de eroare, rezolvă cauza, apoi reia cu `npm rebuild -g ase-moodle-mcp`. Dacă tot nu merge, instalează direct: `pipx install git+https://github.com/FiredMosquito831/ase-moodle-mcp.git`.

### `npm install` pare blocat câteva minute

Normal la prima instalare: scriptul descarcă și instalează pachetul Python, iar npm nu afișează mesajele lui până la final. Pentru progres: `npm install -g --foreground-scripts ase-moodle-mcp`.

### `ase-moodle` nu e recunoscut după `npm install -g`

Deschide un terminal nou, ca să se încarce PATH-ul. Dacă tot nu merge, verifică directorul global npm: `npm prefix -g` (pe Windows) sau `npm prefix -g`/`bin` (Linux, macOS) trebuie să fie în PATH.

### `ase-moodle-mcp login` nu afișează nimic și pare blocat

Pachetul Python e mai vechi de 0.2.1. Versiunile vechi ignoră argumentele și pornesc serverul MCP, care așteaptă intrare. Apasă Ctrl+C și actualizează pachetul Python: `pipx install --force git+https://github.com/FiredMosquito831/ase-moodle-mcp.git` (sau `python -m pip install --upgrade git+…`). Apoi `ase-moodle-mcp login` face același lucru ca `ase-moodle login`.

### `npm update` nu a actualizat pachetul Python

Așa e: scriptul de instalare lasă pachetul Python neatins dacă există deja. Actualizează-l separat, vezi [INSTALL.md, Actualizare](INSTALL.md#actualizare).

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
