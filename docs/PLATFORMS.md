# Platforme: Claude Code, Codex, opencode, Antigravity

Fiecare platformă are un adaptor izolat, cu comenzile și evidența proprii. Modelul și regulile comune sunt în [HARNESSES.md](HARNESSES.md). Aici e ce face fiecare și unde ajung fișierele.

`ase-moodle install` configurează pluginul sau serverul MCP în fiecare CLI, folosind mecanismul lui nativ. Aici e ce face fiecare și unde ajung fișierele.

## Scopuri

| Scop | Unde e disponibil | Opțiune |
|---|---|---|
| `global` (implicit) | în toate folderele, pentru contul tău | `--scope global` |
| `project` | doar în folderul proiectului | `--scope project --project-dir DIR` |

Folderul proiectului este `--project-dir`. Dacă nu-l dai, este folderul de unde rulezi comanda.

Schimbarea de scop curăță celălalt scop. Motivul: două servere cu același nume se dublează. Dacă instalezi pe proiect, scot instalarea globală a acelui CLI, și invers.

| Platformă | Global | Project |
|---|---|---|
| Claude Code | plugin + marketplace, scope `user` | plugin + marketplace, scope `project` (în `.claude/settings.json` din folder) |
| Codex | plugin + marketplace (în `~/.codex`) | doar serverul MCP, în `.codex/config.toml` din folder |
| opencode | `~/.config/opencode/opencode.json` + `SKILL.md` | `opencode.json` din folder |
| Antigravity | doar global (`agy`) | nu are: comanda e sărită cu un mesaj |

## Claude Code

**Ce instalează:** marketplace-ul `ase-moodle-marketplace` și pluginul `ase-moodle` (cu serverul MCP, skill-ul și comenzile `/ase-login`, `/ase-deadlines`, `/ase-download`).

**Instalare:**

```powershell
ase-moodle install claude                              # global
ase-moodle install claude --scope project              # doar folderul curent
```

Manual, în Claude Code:

```text
/plugin marketplace add FiredMosquito831/ase-moodle-mcp
/plugin install ase-moodle@ase-moodle-marketplace
```

**Verificare:** `claude plugin list` arată `ase-moodle@ase-moodle-marketplace`. `claude mcp list` arată serverul `plugin:ase-moodle:ase-moodle` cu statusul `Connected`.

**După instalare sau update:** repornește Claude Code. Pluginul nou intră în vigoare abia la repornire.

**Dezinstalare:** `ase-moodle uninstall claude`.

## Codex

**Ce instalează:**
- global: marketplace-ul și pluginul, în `~/.codex`. Pluginul aduce serverul MCP și skill-ul.
- project: doar serverul MCP, în `.codex/config.toml` din folder. Pluginul nu se instalează pe proiect, pentru că Codex ține marketplace-urile global.

**Instalare:**

```powershell
ase-moodle install codex                               # global
ase-moodle install codex --scope project               # doar folderul curent
```

Manual:

```text
codex plugin marketplace add FiredMosquito831/ase-moodle-mcp
codex plugin add ase-moodle@ase-moodle-marketplace
```

**Important pentru proiect:** Codex cere să marchezi folderul ca proiect de încredere, prima dată când îl deschizi. Fără asta, `.codex/config.toml` nu se încarcă.

**Verificare:** `codex plugin list` arată `ase-moodle@ase-moodle-marketplace  installed, enabled` (global). Pentru proiect, verifică că `.codex/config.toml` conține `[mcp_servers.ase-moodle]`.

**Dezinstalare:** `ase-moodle uninstall codex`.

## opencode

**Ce instalează:**
- global: `mcp.ase-moodle` și `instructions` (calea către skill) în `~/.config/opencode/opencode.json`. Skill-ul e copiat în `~/.config/opencode/ase-moodle/SKILL.md`.
- project: `mcp.ase-moodle` în `opencode.json` din folder. Fără `instructions`, pentru că serverul MCP își trimite singur descrierea.

Fișierul existent e păstrat: instalatorul adaugă doar cheia `ase-moodle` și face copie `.bak` înainte de scriere. Dacă fișierul nu e JSON valid, instalatorul se oprește și nu-l modifică.

**Instalare:**

```powershell
ase-moodle install opencode                            # global
ase-moodle install opencode --scope project            # doar folderul curent
```

**Verificare:** `opencode mcp list` arată `ase-moodle connected`.

**Notă:** `opencode.json` de proiect conține calea Python a calculatorului unde ai instalat. Dacă comiți fișierul, alt calculator nu-l va putea porni. Adaugă-l în `.gitignore` dacă nu vrei să-l distribui.

**Dezinstalare:** `ase-moodle uninstall opencode`.

## Google Antigravity (`agy`)

**Ce instalează:** serverul MCP (`agy mcp add ase-moodle`) și pluginul cu skill-ul (`agy plugin install`).

**Doar global.** Antigravity nu are instalare pe proiect. Cu `--scope project`, comanda o sare și întoarce un mesaj explicit.

```powershell
ase-moodle install antigravity
```

**Sursa pluginului:** dacă marketplace-ul e un clone local, pluginul vine din el. Dacă e `owner/repo`, instalatorul clonează repo-ul în `~/.ase-moodle/repo` (și face `git pull` la fiecare rulare).

**Verificare:** `agy mcp list` arată `ase-moodle` cu statusul `enabled`. `agy plugin list` arată importul pluginului.

**Dezinstalare:** `ase-moodle uninstall antigravity`.

## Fișiere atinse

| Platformă | Global | Project |
|---|---|---|
| Claude Code | gestionat de `claude plugin` (scope `user`) | `<proiect>/.claude/settings.json` (gestionat de `claude plugin`) |
| Codex | gestionat de `codex plugin` (în `~/.codex`) și `~/.codex/config.toml` (curățat) | `<proiect>/.codex/config.toml` |
| opencode | `~/.config/opencode/opencode.json` (+ `.bak`), `~/.config/opencode/ase-moodle/SKILL.md` | `<proiect>/opencode.json` (+ `.bak`) |
| Antigravity | gestionat de `agy` | — |
| Toate | token în Credential Manager sau în `~/.ase-moodle/config.json` | — |

Instalatorul nu modifică alte servere MCP din aceste fișiere.

## Linux și macOS

Calea de configurare pentru opencode (`~/.config/opencode`) și Codex (`~/.codex`) e aceeași pe Linux. Logica de instalare din pachet e testată pe Linux (suita de teste rulează în WSL Ubuntu 24.04 și în CI).

Nu am verificat încă pe Linux comenzile reale ale CLI-urilor (`claude`, `codex`, `opencode`, `agy`). Dacă ai un calculator Linux cu ele instalate, rulează `ase-moodle doctor` și spune-mi ce iese.

macOS nu e testat.

## Repornire și update

- Claude Code: repornește după `install` sau `update`.
- Codex, opencode, Antigravity: repornește clientul dacă nu vezi serverul.
- Procesele MCP vechi rămân pornite până le închizi. `ase-moodle doctor` le numără.

## Verificare generală

```powershell
ase-moodle doctor
```

Pentru fiecare platformă vezi `instalat`, `skipped` (nu e instalat sau CLI-ul lipsește) sau `error`.
