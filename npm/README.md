# ase-moodle-mcp

Server MCP, CLI și plugin pentru Moodle BL@ASE (online.ase.ro). Dă agenților AI (Claude Code, Codex, opencode, Google Antigravity) acces la cursuri, materiale, teme, forumuri, note, quizuri, notificări și termene.

**In English:** an MCP server, CLI and plugin for the BL@ASE Moodle account (online.ase.ro). This npm package is a launcher. The code is in the Python package `ase-moodle`, which the install script installs for you through pipx.

## Instalare

Ai nevoie de Node.js 18+ și Python 3.10+. Git e recomandat.

```bash
npm install -g ase-moodle-mcp
ase-moodle login
ase-moodle install
ase-moodle doctor
```

Instalarea pune și pachetul Python, prin pipx. La prima instalare durează câteva minute, iar npm nu afișează progresul. Ca să-l vezi, rulează `npm install -g --foreground-scripts ase-moodle-mcp`.

**Fără instalare globală:**

```bash
npx ase-moodle-mcp auth-status
```

Dacă pachetul Python nu s-a instalat, după ce rezolvi cauza rulează `npm rebuild -g ase-moodle-mcp`. Pașii complet: [INSTALL.md](https://github.com/FiredMosquito831/ase-moodle-mcp/blob/main/docs/INSTALL.md).

## Comenzi

| Comandă | Ce face |
|---|---|
| `ase-moodle login` | te loghezi în Moodle în browser, cu Google (o singură dată) |
| `ase-moodle auth-status` | verifică dacă ești logat |
| `ase-moodle install` | adaugă pluginul în Claude Code, Codex, opencode și Antigravity |
| `ase-moodle doctor` | verifică instalarea și arată ce lipsește |
| `ase-moodle courses --year 3 --sem 1` | cursurile unui semestru |
| `ase-moodle deadlines --days 14` | termenele din următoarele 14 zile |
| `ase-moodle download --year 3 --sem 1 --out <folder>` | materialele unui an și semestru |

Lista completă, cu toate opțiunile: [USAGE.md](https://github.com/FiredMosquito831/ase-moodle-mcp/blob/main/docs/USAGE.md).

Pachetul are două binare:

- `ase-moodle` rulează CLI-ul.
- `ase-moodle-mcp` fără argumente pornește serverul MCP, pe care îl pornesc clienții. Cu argumente rulează CLI-ul, la fel ca `ase-moodle`.

`npx ase-moodle-mcp <comandă>` rulează CLI-ul fără instalare globală.

## Configurare MCP

În orice client care citește `mcpServers`:

```json
{
  "mcpServers": {
    "ase-moodle": {
      "command": "ase-moodle-mcp"
    }
  }
}
```

Cu `ase-moodle install` configurația se scrie singură pentru fiecare client. Detalii: [MCP.md](https://github.com/FiredMosquito831/ase-moodle-mcp/blob/main/docs/MCP.md).

## Dezinstalare

```bash
ase-moodle uninstall                  # scoate pluginul din toate CLI-urile
ase-moodle logout --forget-browser    # șterge tokenul și sesiunea din browser
npm uninstall -g ase-moodle-mcp       # scoate launcherul
pipx uninstall ase-moodle             # scoate pachetul Python
```

`npm uninstall` șterge doar launcherul. Pachetul Python îl șterge pipx (sau `python -m pip uninstall ase-moodle`, dacă l-ai instalat cu pip). Pașii complet: [INSTALL.md, Dezinstalare](https://github.com/FiredMosquito831/ase-moodle-mcp/blob/main/docs/INSTALL.md#dezinstalare).

## Actualizare

```bash
npm install -g ase-moodle-mcp@latest
pipx install --force git+https://github.com/FiredMosquito831/ase-moodle-mcp.git
ase-moodle update
```

Scriptul npm nu actualizează pachetul Python dacă e deja instalat, deci îl actualizezi separat, ca mai sus.

## Probleme

Erori frecvente și soluții: [TROUBLESHOOTING.md](https://github.com/FiredMosquito831/ase-moodle-mcp/blob/main/docs/TROUBLESHOOTING.md).

## Site, cod și licență

- Site: https://ase-moodle-mcp.danubelabs.net/
- Cod: https://github.com/FiredMosquito831/ase-moodle-mcp
- Cod sub Apache License 2.0. Autor: FiredMosquito831.
