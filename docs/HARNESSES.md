# Harness-uri: adaptoare izolate

Fiecare CLI în care rulează pachetul (Claude Code, Codex, opencode, Google Antigravity) are **propriul adaptor**. Adaptorul știe exact cum funcționează acel CLI: ce comenzi folosește, unde scrie, ce scopuri acceptă și cum se verifică. Adaptoarele nu se importă între ele, deci o problemă la un CLI nu afectează celelalte.

## Comenzi per harness

```text
ase-moodle claude     install|update|uninstall|doctor
ase-moodle codex      install|update|uninstall|doctor
ase-moodle opencode   install|update|uninstall|doctor
ase-moodle antigravity install|update|uninstall|doctor
```

Fiecare comandă are doar opțiunile care au sens pentru harness-ul ei. Un scop nesuportat e refuzat de parser, nu ignorat.

| Harness | Scopuri | Opțiuni | Cere CLI-ul |
|---|---|---|---|
| `claude` | `global`, `project` | `--scope`, `--project-dir`, `--source` (install/update) | da: `claude` |
| `codex` | `global`, `project` | `--scope`, `--project-dir`, `--source` (install/update) | pentru global; proiectul merge și fără CLI |
| `opencode` | `global`, `project` | `--scope`, `--project-dir` | nu (verificare: `opencode mcp list`, dacă există) |
| `antigravity` | doar `global` | `--source` (install/update) | da: `agy` |

Exemple:

```powershell
ase-moodle claude install --scope project                 # doar folderul curent, pentru Claude Code
ase-moodle codex doctor --project-dir D:\Proiecte\alt     # verifica un alt folder
ase-moodle opencode uninstall --scope global              # doar configurarea globala
ase-moodle antigravity install --scope project            # eroare: Antigravity nu are scop de proiect
```

## Izolarea

Trei reguli, valabile pentru toate adaptoarele:

1. **Fișiere proprii.** Adaptorul scrie doar în locurile lui. Instalarea pentru Claude Code nu atinge `~/.codex`, `~/.config/opencode` sau `agy`.
2. **Evidență proprie.** Fiecare adaptor își ține lista de lucruri instalate în `~/.ase-moodle/state/<harness>.json`, pe scop:
   - `"global"` pentru instalarea globală;
   - `"project:<folder>"` pentru fiecare folder de proiect.
   Dezinstalarea șterge doar ce e în evidența lui. Un alt harness sau un alt folder nu sunt atinse.
3. **Schimbarea de scop curăță doar același harness.** Dacă instalezi Claude Code pe proiect, se scoate pluginul global al Claude Code, nu al Codex. Așa nu există două servere cu același nume.

Adaptorul șterge și intrările cu numele `ase-moodle` din configurările care nu sunt ale lui (de exemplu blocul manual `[mcp_servers.ase-moodle]` din Codex). Nu șterge alte servere, alți provideri sau alte setări.

## Claude Code

- **Ce instalează:** marketplace `ase-moodle-marketplace` și pluginul `ase-moodle@ase-moodle-marketplace`, cu serverul MCP, skill-ul și comenzile.
- **Global:** `claude plugin marketplace add <sursa> --scope user`, apoi `claude plugin install ... --scope user -y`.
- **Proiect:** aceleași comenzi cu `--scope project`, rulate din folderul proiectului. Configurarea ajunge în `.claude/settings.json` din folder (`extraKnownMarketplaces` și `enabledPlugins`). Fișierul nu conține căi locale și poate fi comis.
- **Particularitate:** `claude plugin list` arată pluginurile de proiect doar din folderul proiectului. De aceea `doctor` verifică fiecare scop din folderul lui.
- **Restart:** Claude Code trebuie repornit ca să încarce pluginul. Sesiunea veche păstrează lista veche de servere.
- **Curățare:** scoate serverul MCP adăugat manual (`claude mcp add`), ca să nu se dubleze cu pluginul.
- **Dezinstalare:** scoate doar pluginul din scopul cerut. Marketplace-ul rămâne înregistrat, pentru că e comun tuturor folderelor. `claude plugin marketplace remove` ar scoate pluginul și din celelalte foldere (verificat live), așa că nu îl folosim.

## Codex

- **Global:** `codex plugin marketplace add <sursa>`, apoi `codex plugin add ase-moodle@ase-moodle-marketplace`. Totul rămâne în `~/.codex`.
- **Proiect:** doar serverul MCP, în `.codex/config.toml` din folder, tabelul `[mcp_servers.ase-moodle]`, cu `command` (calea Python) și `args`. Pluginul și skill-urile nu merg pe proiect, pentru că Codex ține marketplace-urile global.
- **Încredere:** Codex cere să marchezi folderul ca proiect de încredere. Fără asta, `.codex/config.toml` nu se încarcă. Adaptorul nu marchează nimic singur.
- **Fișierul de proiect conține calea Python de pe acest calculator** și e în `.gitignore`.
- **Verificare:** global prin `codex plugin list`; proiect prin citirea fișierului.

## opencode

- **Global:** `~/.config/opencode/opencode.json`, cu `mcp.ase-moodle` și o intrare în `instructions` care trimite la skill-ul copiat în `~/.config/opencode/ase-moodle/SKILL.md`.
- **Proiect:** `opencode.json` din folder, doar cu `mcp.ase-moodle`, fără instrucțiuni. Serverul își trimite singur descrierea.
- **Siguranță:** face copie `.bak` înainte de orice scriere. Dacă JSON-ul nu e valid, se oprește și nu modifică nimic. Alte servere MCP rămân neatinse.
- **Restart:** opencode trebuie repornit ca să citească fișierul.

## Google Antigravity (`agy`)

- **Doar global.** `agy` nu are scop de proiect. Cererea `--scope project` pentru Antigravity e refuzată explicit. În `ase-moodle install all --scope project`, Antigravity e sărit cu un mesaj clar.
- **Ce instalează:** `agy mcp add ase-moodle -- <python> -m ase_moodle.mcp_server` și `agy plugin install <folder>`.
- **Folderul pluginului:** repo-ul local (dacă sursa e o cale) sau un clone în `~/.ase-moodle/repo` (dacă sursa e `owner/repo`).

## Ce returnează `doctor`

`ase-moodle <harness> doctor` verifică fiecare scop din locul lui și raportează:

| Stare | Sens |
|---|---|
| `ok` | instalat în acel scop |
| `skipped` | nu e instalat în acel scop. Nu e eroare, dacă e instalat în celălalt |
| `warning` | instalat, dar ceva nu e complet (de exemplu serverul Claude nu e conectat) |
| `error` | nu e instalat nicăieri, sau configurarea e defectă |

Exit code `3` apare doar la `error`.

## Dispecerul `install all`

`ase-moodle install [TARGET...]` (fără nume de harness) rulează adaptoarele unul după altul. Un harness care nu suportă scopul cerut e sărit, cu motivul în output. Cu un nume explicit (`ase-moodle install antigravity --scope project`), e eroare.

## Adăugarea unui harness

Vezi [DEVELOPMENT.md](DEVELOPMENT.md#adăugarea-unui-harness).
