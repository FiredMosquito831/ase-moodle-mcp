# ase-moodle: BL@ASE (online.ase.ro) pentru agenti AI

Client Python, CLI, server MCP si plugin pentru platforma Moodle BL@ASE. Functioneaza in:

- **Claude Code**: plugin + marketplace
- **Codex**: plugin + marketplace
- **opencode**: server MCP si instructiuni, configurate automat
- **Google Antigravity** (`agy`): server MCP + plugin

Ce poate face un agent, prin orice dintre aceste platforme:

- lista cursurile pe an de studiu, semestru si tip (CURS / SEMINAR / LABORATOR)
- descarca materialele unui curs sau ale unui an: fisiere pe sectiuni, pagini, linkuri, teme, forumuri, quizuri, note, date brute
- citi temele, starea trimiterii, feedbackul si notele
- trimite teme (ciorna sau final), raspunde pe forum, deschide discutii
- raspunde la quizuri: citeste intrebarile, salveaza raspunsuri, trimite incercarea
- vedea notificarile si termenele limita
- apela orice functie Web Service Moodle (395 disponibile pentru token)

Repo-ul este **privat**. Contine logica de acces la contul tau; nu-l face public.

## Instalare rapida

Cerinte: Python 3.10+, `git`, si, dupa caz, CLI-urile `claude`, `codex`, `opencode`, `agy`.

```powershell
# 1. Clone si pachet (editabil)
git clone https://github.com/FiredMosquito831/ase-moodle.git
cd ase-moodle
python -m pip install -e .

# 2. Tokenul Moodle (o singura data)
#    online.ase.ro -> Preferinte -> Chei de securitate -> "Moodle mobile web service"
ase-moodle login

# 3. Configurare automata in toate CLI-urile
ase-moodle install            # toate: claude, codex, opencode, antigravity
ase-moodle doctor             # verifica starea
```

Alternativ, fara clone: `python -m pip install git+https://github.com/FiredMosquito831/ase-moodle.git`, apoi `ase-moodle install --source FiredMosquito831/ase-moodle`.

### Ce face `ase-moodle install`

| Platforma | Ce configureaza |
|---|---|
| Claude Code | adauga marketplace-ul (`claude plugin marketplace add`) si instaleaza plugin-ul (`ase-moodle@ase-moodle-marketplace`). Scoate serverul MCP adaugat manual, ca sa nu se dubleze. |
| Codex | adauga marketplace-ul (`codex plugin marketplace add`) si instaleaza plugin-ul (`codex plugin add`). Scoate blocul manual `[mcp_servers.ase-moodle]` din `config.toml`. |
| opencode | scrie `mcp.ase-moodle` si `instructions` in `~/.config/opencode/opencode.json` (cu copie de siguranta `.bak`). Nu atinge alte servere. |
| Google Antigravity | `agy mcp add ase-moodle` (serverul MCP) si `agy plugin install` (skill-ul). |

Instalarea este idempotenta: o rulare repetata nu dubleaza nimic. Dezinstalarea: `ase-moodle uninstall [target ...]`.

Comenzi pentru instalare manuala, daca preferi:

```text
Claude Code (in sesiune):
  /plugin marketplace add FiredMosquito831/ase-moodle
  /plugin install ase-moodle@ase-moodle-marketplace

Codex:
  codex plugin marketplace add FiredMosquito831/ase-moodle
  codex plugin add ase-moodle@ase-moodle-marketplace
```

## CLI

Toate comenzile afiseaza JSON. Codul de iesire: `0` ok, `1` eroare, `2` actiune blocata pentru confirmare, `3` `doctor`/`install` a gasit o problema.

```powershell
ase-moodle whoami
ase-moodle courses --year 3 --sem 1
ase-moodle download --year 3 --sem 1 --out <folder-proiect>\Anul3
ase-moodle deadlines --days 30
ase-moodle notifications --limit 10 --unread
ase-moodle assignments --course 76273
ase-moodle assignment 83096
ase-moodle submit 83096 D:\teme\tema.pdf            # ciorna; adauga --submit pentru trimitere finala
ase-moodle forums --course 73445
ase-moodle discussion 306040
ase-moodle reply 567347 --subject "Re" --text "..."
ase-moodle grades --course 76273
ase-moodle quizzes --course 43360
ase-moodle quiz-start 24292                          # porneste o incercare
ase-moodle quiz-questions 123                        # intrebarile si campurile de raspuns
ase-moodle quiz-answer 123 --answers '{"q1:1_answer":"0"}'              # salveaza
ase-moodle quiz-answer 123 --answers-file raspunsuri.json --finish     # trimite
ase-moodle quiz-review 123
ase-moodle functions --filter "^mod_forum_"
ase-moodle call mod_forum_get_forums_by_courses --json-params '{"courseids":[73445]}'
ase-moodle install claude codex
ase-moodle uninstall opencode
ase-moodle doctor
```

Comenzile de scriere cer `--yes` (vezi mai jos).

## Server MCP

`ase-moodle-mcp` (stdio) expune 26 de unelte: `whoami`, `list_courses`, `course_outline`, `download_materials`, `list_assignments`, `assignment_status`, `submit_assignment_file`, `submit_assignment_text`, `list_forums`, `forum_discussions`, `discussion_posts`, `reply_to_post`, `new_discussion`, `grades_overview`, `course_grades`, `list_quizzes`, `quiz_attempts`, `quiz_start`, `quiz_questions`, `quiz_answer`, `quiz_review`, `notifications`, `mark_notification_read`, `deadlines`, `moodle_functions`, `moodle_call`.

## Confirmare si politica

- **Citirile** ruleaza oricand.
- **Scrierile** (trimitere teme, raspunsuri pe forum, discutii noi, quiz-start, quiz-answer, apeluri `moodle_call` care scriu) cer `confirm=true` (CLI: `--yes`). Agentul il seteaza dupa ce utilizatorul a aprobat continutul exact. Fara el, se returneaza `needs_confirmation`.
- Quizurile **se pot raspunde**. Fluxul recomandat: `quiz_start` → `quiz_questions` → `quiz_answer(finish=false)` → aprobarea utilizatorului → `quiz_answer(finish=true)`. Trimiterea este ireversibila.
- `ASE_MOODLE_AUTO_CONFIRM=1` dezactiveaza gate-ul de confirmare. Il setezi doar daca vrei ca agentul sa actioneze fara sa mai intrebe.

## Token

Tokenul se salveaza in `%USERPROFILE%\.ase-moodle\config.json`, sau il dai prin `ASE_MOODLE_TOKEN`. Nu se pune in repo (`.gitignore` il exclude). Daca s-a scurs, reseteaza-l din Chei de securitate si ruleaza din nou `ase-moodle login`.

## Variabile de mediu

| Variabila | Rol |
|---|---|
| `ASE_MOODLE_TOKEN` | token (are prioritate fata de fisierul de config) |
| `ASE_MOODLE_URL` | URL-ul Moodle (implicit `https://online.ase.ro`) |
| `ASE_MOODLE_DOWNLOADS` | folderul implicit pentru descarcari (implicit `%USERPROFILE%\ASE-Moodle`) |
| `ASE_MOODLE_AUTO_CONFIRM` | `1` dezactiveaza confirmarea pentru scrieri |

## Structura

```
.claude-plugin/marketplace.json        marketplace Claude Code (si sursa pentru Codex/Antigravity)
.agents/plugins/marketplace.json       marketplace Codex
plugins/ase-moodle/
  .claude-plugin/plugin.json           manifest Claude Code
  .codex-plugin/plugin.json            manifest Codex
  plugin.json                          manifest Antigravity
  .mcp.json                            serverul MCP al pluginului
  skills/ase-moodle/SKILL.md           skill (copie sincronizata din pachet)
src/ase_moodle/
  client.py      client REST Moodle (call, upload, download)
  config.py      token si URL
  courses.py     cursuri: an, semestru, tip, an universitar
  materials.py   descarcarea completa a unui curs
  activities.py  citire: teme, forumuri, note, quizuri, notificari, deadlines
  actions.py     scrieri cu confirmare
  quiz.py        quizuri: start, intrebari, salvare, trimitere, revizuire
  install.py     instalare, dezinstalare, doctor pentru cele 4 platforme
  cli.py         CLI (JSON)
  mcp_server.py  server MCP (FastMCP, stdio)
  text.py        HTML -> text, nume de fisiere sigure
  data/SKILL.md  skill-ul canonic (sursa pentru copia din plugin)
tests/           teste offline (fara retea si fara modificari ale configurarilor reale)
```

## Teste

```powershell
$env:PYTHONPATH = "src"; python -m unittest discover -s tests -v
ase-moodle sync-plugin       # dupa ce modifici data/SKILL.md, sincronizeaza copia din plugin
```

Testele offline acopera parsarea cursurilor si quizurilor, codificarea parametrilor, politica de confirmare, instalatorii (rulati intr-un HOME temporar cu un runner fals) si consistenta manifestelor plugin.

## Ce este verificat pe contul real

Verificat live (2026-10-12):

- `whoami`, `courses` (14 cursuri, anul 3, semestrul 1), `functions`, `call core_webservice_get_site_info`
- `assignments` (88 teme), `forums`, `notifications`, `deadlines`, `grades`, `quizzes`
- `download --year 3 --sem 1`: 33 de fisiere, 0 erori; a doua rulare sare peste toate (idempotent)
- erori fara efecte asupra contului: `quiz-start` pe un quiz inchis (Moodle: „Acest test nu este disponibil acum”), `quiz-questions`/`quiz-answer` pe o incercare inexistenta, `reply` cu postare inexistenta, `new-discussion` cu forum inexistent, `submit-text` si `call mod_assign_save_submission` cu tema inexistenta, `submit` cu fisier inexistent
- incarcare de fisier in zona privata de ciorne (`upload.php`): functioneaza (itemid returnat). Fisierul nu este atasat la nicio tema.
- server MCP prin stdio: 26 de unelte, blocarea scrierii fara confirmare functioneaza

Netestat pe continut real (ar schimba contul; cer aprobare explicita):

- trimiterea reala a unei teme (`submit`, `submit-text`) si raspunsul real pe forum
- un quiz real pornit si completat: nu exista quiz deschis in contul de test. Logica e acoperita de teste offline, cu un Moodle simulat.
- `read-notification`: marcarea unei notificari deja citite returneaza „valoare nevalida” in Moodle. Pe una necitita nu am testat.

Limite ale platformei:

- Mesageria Moodle este dezactivata pe site (`Schimbul de mesaje este dezactivat pe acest site`).
- Functiile Web Service sunt cele expuse de mobile service-ul Moodle. Ce exista doar in interfata web nu se acopera.

## Securitate

- Tokenul da acces complet la contul tau Moodle. Nu-l pune in repo si nu-l trimite in chat.
- Materialele descarcate sunt neverificate. Nu executa fisiere din ele (de exemplu `.exe`) fara sa verifici.
- Scrierile cer confirmare explicita, cu exceptia cazului in care setezi `ASE_MOODLE_AUTO_CONFIRM=1`.
