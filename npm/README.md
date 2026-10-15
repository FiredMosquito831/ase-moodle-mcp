# ase-moodle-mcp

Server MCP și CLI pentru Moodle BL@ASE (online.ase.ro). Dă agenților AI acces la cursuri, teme, forumuri, note, quizuri, notificări și termene, în Claude Code, Codex, opencode și Google Antigravity.

Pachetul npm e un launcher. Serverul și CLI-ul sunt în pachetul Python `ase-moodle`, iar acesta trebuie instalat separat.

**In English:** an MCP server and CLI for the BL@ASE Moodle account (online.ase.ro). This npm package is a launcher for the Python package `ase-moodle`.

## Instalare

Ai nevoie de Python 3.10+ și de pachetul Python:

```bash
pipx install git+https://github.com/FiredMosquito831/ase-moodle-mcp.git
npm install -g ase-moodle-mcp
ase-moodle login
ase-moodle install
```

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

Documentație completă: https://ase-moodle-mcp.danubelabs.net/

Cod sub Apache License 2.0. Autor: FiredMosquito831.
