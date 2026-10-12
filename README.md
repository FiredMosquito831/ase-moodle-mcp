# ase-moodle: BL@ASE (online.ase.ro) pentru agenti AI

Client Python, CLI, server MCP si plugin pentru Moodle-ul BL@ASE. Functioneaza in:

- **Claude Code**: plugin + marketplace, cu comenzi `/ase-login`, `/ase-deadlines`, `/ase-download`
- **Codex**: plugin + marketplace
- **opencode**: server MCP si instructiuni, configurate automat
- **Google Antigravity** (`agy`): server MCP + plugin cu skill-uri

Repo-ul este **privat**. Contine logica de acces la contul tau.

Pentru notiunile de baza despre secrete (ce e secret, unde se tine tokenul, ce nu intra in git), citeste
[docs/SECURITATE-PE-INTELES.md](docs/SECURITATE-PE-INTELES.md).

## Ce poate face un agent

- lista cursurile pe an de studiu, semestru si tip (CURS / SEMINAR / LABORATOR)
- descarca materialele unui curs sau ale unui an, in paralel: fisiere, pagini, linkuri, teme, forumuri, quizuri, note, date brute
- citi temele, starea trimiterii, feedbackul si notele; sti daca tema are ciorne
- trimite teme (ciorna sau final), raspunde pe forum, deschide discutii
- raspunde la quizuri: citeste intrebarile, salveaza raspunsuri, trimite incercarea (cu aprobarea ta)
- vedea notificarile, termenele si marcheaza notificarile ca citite
- apela orice functie Web Service Moodle (395 disponibile pentru token)

## Instalare

Cerinte: Python 3.10+, `git`, si CLI-urile pe care vrei sa le configurezi (`claude`, `codex`, `opencode`, `agy`).

### Varianta rapida (un singur script)

```powershell
git clone https://github.com/FiredMosquito831/ase-moodle.git
cd ase-moodle
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
```

Scriptul instaleaza pachetul, te logheaza (se deschide browserul; o singura data, cu Google), configureaza
toate CLI-urile si verifica starea.

### Varianta manuala

```powershell
python -m pip install -e .
ase-moodle login                 # browser; sau: ase-moodle login --method manual (tokenul din clipboard)
ase-moodle install               # toate: claude, codex, opencode, antigravity
ase-moodle doctor                # verifica starea
```

### Autentificare

`ase-moodle login` deschide Edge (sau Chrome) cu un profil dedicat, in fereastra de login a Moodle:

1. prima data te loghezi tu, cu Google;
2. tokenul se ia automat prin fluxul SSO pe care il foloseste aplicatia Moodle Mobile;
3. tokenul ajunge in **Windows Credential Manager**, nu in fisiere din proiect;
4. rularile urmatoare sunt automate, fara login, cat timp sesiunea Google e valabila.

Parola Google nu este salvata nicaieri. Metoda `manual` deschide pagina de login; copiezi tokenul din
„Chei de securitate” si il citeste clipboard-ul. Pentru `--token` direct, vezi mai jos.

Comenzi: `ase-moodle auth-status`, `ase-moodle logout` (sterge tokenul), `ase-moodle logout --forget-browser`
(sterge si sesiunea din browser).

### Fisierul `.env` (optional, local)

Util pentru teste sau pentru un calculator fara Credential Manager. Copiaza `.env.example` in `.env` si completeaza:

```text
ASE_MOODLE_TOKEN=...          # tokenul; nu-l pune in git
ASE_MOODLE_DOWNLOADS=D:\...   # folderul pentru materiale (optional)
```

`.env` este in `.gitignore`. Ordinea de prioritate: variabile de mediu, apoi `.env`, apoi Credential Manager.

## Ce face `ase-moodle install` / `update`

| Platforma | Ce configureaza |
|---|---|
| Claude Code | marketplace (`claude plugin marketplace add`) + plugin (`ase-moodle@ase-moodle-marketplace`). Scoate serverul MCP manual, ca sa nu se dubleze. |
| Codex | marketplace (`codex plugin marketplace add`) + plugin (`codex plugin add`). Scoate blocul manual `[mcp_servers.ase-moodle]`. |
| opencode | `mcp.ase-moodle` si `instructions` in `~/.config/opencode/opencode.json` (cu copie `.bak`). Nu atinge alte servere. |
| Google Antigravity | `agy mcp add ase-moodle` (serverul MCP) si `agy plugin install` (skill-urile). |

- `ase-moodle install [claude|codex|opencode|antigravity|all] [--source FiredMosquito831/ase-moodle]`: idempotent.
- `ase-moodle update [...]`: aduce ultima versiune din marketplace. Claude Code cere repornire ca sa intre in vigoare.
- `ase-moodle uninstall [...]`: elimina configurarea.
- `ase-moodle doctor`: starea fiecarei platforme, sursa tokenului, procesele MCP pornite, metadatele pachetului.

Comenzi manuale, daca preferi:

```text
Claude Code (in sesiune):
  /plugin marketplace add FiredMosquito831/ase-moodle
  /plugin install ase-moodle@ase-moodle-marketplace

Codex:
  codex plugin marketplace add FiredMosquito831/ase-moodle
  codex plugin add ase-moodle@ase-moodle-marketplace
```

## CLI

Toate comenzile afiseaza JSON. Coduri de iesire: `0` ok, `1` eroare, `2` actiune blocata pentru confirmare,
`3` `doctor`/`install`/`update` a gasit o problema.

```powershell
ase-moodle whoami
ase-moodle courses --year 3 --sem 1
ase-moodle download --year 3 --sem 1 --out <folder-proiect>\Anul3
ase-moodle deadlines --days 30
ase-moodle notifications --limit 10 --unread
ase-moodle read-notification 22646760 --yes
ase-moodle assignments --course 76273
ase-moodle assignment 83096                       # include drafts_enabled
ase-moodle submit 83096 D:\teme\tema.pdf --yes    # ciorna; cere ciorne activate la tema
ase-moodle submit 83096 D:\teme\tema.pdf --yes --allow-direct   # doar daca tema NU are ciorne si studentul vrea asta
ase-moodle forums --course 73445
ase-moodle reply 567347 --subject "Re" --text "..." --yes
ase-moodle grades --course 76273
ase-moodle quizzes --course 43360
ase-moodle quiz-start 24292 --yes
ase-moodle quiz-questions 123
ase-moodle quiz-answer 123 --answers '{"q1:1_answer":"0"}' --yes
ase-moodle quiz-answer 123 --answers-file raspunsuri.json --finish --yes
ase-moodle functions --filter "^mod_forum_"
ase-moodle call mod_forum_get_forums_by_courses --json-params '{"courseids":[73445]}'
ase-moodle login | logout | auth-status
ase-moodle install | update | uninstall | doctor
ase-moodle sync-plugin          # dezvoltare: copiaza SKILL.md canonic in plugin
```

## Reguli de siguranta

- **Citirile** ruleaza oricand.
- **Scrierile** cer `confirm=true` (CLI: `--yes`). Agentul il seteaza dupa ce ai aprobat continutul exact.
- **Temele fara ciorne**: salvarea unui fisier trimite raspunsul imediat. Serverul refuza, cu `allow_direct=false`.
  Verifica `drafts_enabled` din `assignment_status`.
- **Quizurile** se pot raspunde. Flux: `quiz_start` → `quiz_questions` → `quiz_answer(finish=false)` → aprobarea ta →
  `quiz_answer(finish=true)`. Trimiterea e ireversibila.
- `ASE_MOODLE_AUTO_CONFIRM=1` dezactiveaza confirmarea. Nu il recomand.

## Server MCP

`ase-moodle-mcp` (stdio), versiunea 0.2.0, cu **28 de unelte**:

- cont: `whoami`, `auth_status`, `moodle_login`
- cursuri: `list_courses`, `course_outline`, `download_materials`
- teme: `list_assignments`, `assignment_status`, `submit_assignment_file`, `submit_assignment_text`
- forum: `list_forums`, `forum_discussions`, `discussion_posts`, `reply_to_post`, `new_discussion`
- note: `grades_overview`, `course_grades`
- quizuri: `list_quizzes`, `quiz_attempts`, `quiz_start`, `quiz_questions`, `quiz_answer`, `quiz_review`
- notificari si termene: `notifications`, `mark_notification_read`, `deadlines`
- API: `moodle_functions`, `moodle_call`

Fiecare unealta are anotari (`readOnlyHint`, `destructiveHint`), ca clientul MCP sa stie ce e sigur.
Listele vin ca `{"count": n, "items": [...]}`.

**Prompturi** (fluxuri gata): `weekly_brief`, `prepare_assignment(assign_id)`, `solve_quiz(quiz_id)`,
`download_year(study_year, semester)`.

**Resurse**: `moodle://me`, `moodle://deadlines`.

**Comenzi Claude Code** (plugin): `/ase-login`, `/ase-deadlines [zile]`, `/ase-download <an> <semestru>`.

## Teste, fara contul real

Testele ruleaza contra unui **server Moodle fals** (`tests/fake_moodle.py`): aceleasi endpoint-uri, date sintetice,
token de test, fara internet. Nu ating contul tau.

```powershell
python -m unittest discover -s tests -v          # 86 teste
python -m pyflakes src tests                      # lint
python tests\fake_moodle.py --port 8765           # serverul fals, pentru incercari manuale
# in alt terminal, cu mediul de test:
#   ASE_MOODLE_ENV_FILE=.env.test ase-moodle whoami
```

Acoperire: parsing, codificare, politica de confirmare, garda pentru ciorne, quizurile (start, intrebari, salvare,
trimitere), descarcarea (idempotenta), configurarea (`.env`, Credential Manager simulat, migrarea tokenului),
instalatorii (in HOME temporar), serverul MCP real prin stdio, consistenta versiunilor.

CI: `.github/workflows/ci.yml` ruleaza lint-ul si testele pe Windows la fiecare push.

## Ce este verificat pe contul real

Verificat live (2026-10-12):

- cont: `whoami`, `auth-status`, autentificare prin browser (SSO), salvare in Credential Manager
- cursuri (14, anul 3, semestrul 1), teme (88), forumuri, notificari, termene, note, quizuri (citire)
- descarcare: 33 de fisiere, 0 erori; a doua rulare nu descarca nimic
- erori fara efecte: `quiz-start` pe quiz inchis, obiecte inexistente, fisier inexistent
- incarcare in zona privata de ciorne: functioneaza
- instalare, update, dezinstalare si reinstalare in cele 4 platforme; `doctor` ok
- marcarea unei notificari ca citita: functioneaza (Moodle respinge parametrul `useridto`; acum nu-l mai trimitem)
- trimitere de ciorna pe o tema reala: **nu se poate** acum, pentru ca niciuna dintre temele deschise nu are ciorne.
  Testul a aratat ca salvarea directa trimite fisierul; am curatat-o prin butonul „Șterge răspunsul”.

Netestat pe contul real:

- quiz deschis pornit si completat: nu exista quiz deschis. Logica e acoperita de testele pe serverul fals.
- trimitere reala de tema cu ciorne activate: nu exista astfel de tema deschisa.

## Limite ale platformei

- Mesageria Moodle este dezactivata pe site (`Schimbul de mesaje este dezactivat pe acest site`).
- Functiile Web Service sunt cele expuse de serviciul mobil Moodle. Ce exista doar in interfata web nu se acopera.

## Variabile de mediu

| Variabila | Rol |
|---|---|
| `ASE_MOODLE_TOKEN` | token (are prioritate fata de `.env` si Credential Manager) |
| `ASE_MOODLE_URL` | URL-ul Moodle (implicit `https://online.ase.ro`) |
| `ASE_MOODLE_DOWNLOADS` | folderul implicit pentru materiale (implicit `~/ASE-Moodle`) |
| `ASE_MOODLE_ENV_FILE` | calea altui fisier `.env` (de ex. `.env.test`) |
| `ASE_MOODLE_AUTO_CONFIRM` | `1` dezactiveaza confirmarea pentru scrieri |

## Structura

```
.claude-plugin/marketplace.json        marketplace Claude Code
.agents/plugins/marketplace.json       marketplace Codex
plugins/ase-moodle/
  .claude-plugin/plugin.json           manifest Claude Code
  .codex-plugin/plugin.json            manifest Codex
  plugin.json                          manifest Antigravity
  .mcp.json                            serverul MCP al pluginului
  skills/ase-moodle/SKILL.md           skill (copie sincronizata)
  commands/                            /ase-login, /ase-deadlines, /ase-download
src/ase_moodle/
  config.py      token (Credential Manager), .env, setari in config.json
  auth.py        login prin browser (SSO) si manual; status; logout
  client.py      client REST Moodle (call, upload, download)
  courses.py     cursuri: an, semestru, tip, an universitar
  materials.py   descarcarea completa a cursurilor (in paralel)
  activities.py  citire: teme, forumuri, note, quizuri, notificari, termene
  actions.py     scrieri cu confirmare si garda pentru ciorne
  quiz.py        quizuri: start, intrebari, salvare, trimitere, revizuire
  install.py     instalare, update, dezinstalare, doctor
  cli.py         CLI (JSON)
  mcp_server.py  server MCP (FastMCP, stdio): unelte, prompturi, resurse
  data/SKILL.md  skill-ul canonic
tests/
  fake_moodle.py     server Moodle fals (date sintetice)
  test_*.py          teste offline si de integrare
docs/SECURITATE-PE-INTELES.md
scripts/bootstrap.ps1
.github/workflows/ci.yml
.env.example  .env.test
```
