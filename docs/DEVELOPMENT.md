# Dezvoltare

## Structura

```
src/ase_moodle/
  config.py      token (Credential Manager / Secret Service), .env, config.json, folderul de descărcare
  auth.py        login prin browser (SSO) și manual; status; logout
  client.py      client REST Moodle: call, upload, download; MoodleError
  courses.py     cursuri: an de studiu, semestru, tip, an universitar; filtre
  materials.py   descărcarea unui curs (și a mai multor cursuri, în paralel)
  activities.py  citiri: teme, forumuri, note, quizuri, notificări, termene, funcții
  actions.py     scrieri cu confirmare; garda pentru ciorne; notificări citite
  quiz.py        quizuri: start, întrebări, salvare, trimitere, revizuire
  install.py     instalare, update, dezinstalare, doctor, pe ambele scopuri
  cli.py         CLI (argparse, JSON)
  mcp_server.py  server MCP (FastMCP): unelte, prompturi, resurse
  text.py        HTML → text, nume de fișiere sigure, timestamp-uri
  data/SKILL.md  skill-ul canonic (copiat în plugin cu `sync-plugin`)

plugins/ase-moodle/       plugin: manifeste, .mcp.json, skills/, commands/
.claude-plugin/           marketplace Claude Code
.agents/plugins/          marketplace Codex
tests/                    teste offline, server Moodle fals (fake_moodle.py)
scripts/                  bootstrap.ps1 (Windows), bootstrap.sh (Linux/macOS)
docs/                     documentația
```

Fluxul unei comenzi:

- `cli.py` sau `mcp_server.py` primește cererea;
- `client.py` vorbește cu Moodle (sau cu serverul fals);
- `activities.py` (citiri) sau `actions.py` (scrieri, cu confirmare) face logica;
- `materials.py`, `quiz.py`, `install.py` sunt pentru funcții mari.

## Adăugarea unei funcții

1. **Logica** în modulul potrivit (`activities.py` pentru citiri, `actions.py` pentru scrieri, `quiz.py` pentru quizuri).
2. **CLI** în `cli.py`: funcția `cmd_*`, subcomanda în `build_parser()`.
3. **MCP** în `mcp_server.py`: funcție cu `@mcp.tool(annotations=READ|WRITE|LOCAL)`. Pentru liste, returnează `_list(...)`.
4. **Documentație**: `docs/USAGE.md` (CLI) și `docs/MCP.md` (unelte). Testul `test_platform_docs.py` pică dacă uiți una.
5. **Teste**: în `test_integration.py` contra serverului fals. Dacă apelul nu există în server, adaugă funcția în `tests/fake_moodle.py`.
6. **Politică**: o scriere trebuie să ceară `require_confirm` (sau să treacă prin `call_function`).

Pentru funcții Moodle noi, verifică întâi că există în serviciul mobil: `ase-moodle functions --filter 'nume'`.

## Adăugarea unui harness

Harness-urile sunt adaptoare izolate (vezi [HARNESSES.md](HARNESSES.md)). Pentru unul nou:

1. **Modul nou** în `src/ase_moodle/harnesses/<nume>.py`, cu o clasă care moștenește `Harness`:
   - `name` și `cli` (executabilul verificat cu `which`, sau `None` dacă harness-ul e configurat prin fișiere);
   - `capabilities = Capabilities(scopes=..., needs_restart=..., notes=...)`: strict ce suportă;
   - `install(ctx, scope)`, `uninstall(ctx, scope)`, `doctor(ctx)`, și `update` dacă diferă de install.
2. **Evidență:** la fiecare scriere, `self.record(ctx, scope, {...})`. La dezinstalare, șterge doar ce ai înregistrat și intrările tale cu numele `ase-moodle`.
3. **Scopuri:** `self.check_scope(scope)` la început. Pentru `uninstall`, `self.expand(scope)` (`all` = scopurile suportate).
4. **Registru:** o intrare în `harnesses/__init__.py`. Comenzile `ase-moodle <nume> ...` apar singure.
5. **Nu importa alte adaptoare.** Dacă ai nevoie de ceva comun, mută-l în `base.py`.
6. **Teste** în `tests/test_harnesses.py`: scrierea, dezinstalarea, doctor-ul pe scopuri, izolarea față de alte harness-uri.
7. **Documentație:** secțiunea din `HARNESSES.md`, rândul din tabelul de la `USAGE.md`, și `PLATFORMS.md`.

## Versiune

Versiunea apare în patru locuri, și testul `test_release.py` le compară:

- `pyproject.toml` (`version`)
- `src/ase_moodle/__init__.py` (`__version__`)
- `plugins/ase-moodle/.claude-plugin/plugin.json`, `plugins/ase-moodle/.codex-plugin/plugin.json`, `plugins/ase-moodle/plugin.json`
- `.claude-plugin/marketplace.json` (`metadata.version`)

Schimbă toate patru în același commit.

Pachetul npm are versiunea lui, în `npm/package.json`. Testul nu o verifică, dar trebuie crescută la fiecare modificare din `npm/`: workflow-ul `npm` publică doar versiuni noi, iar o versiune publicată nu se mai poate republica.

## Skill-ul

Sursa este `src/ase_moodle/data/SKILL.md`. Copia din plugin trebuie să fie identică:

```powershell
ase-moodle sync-plugin
```

`test_release.py` verifică sincronizarea. Clientul (Claude Code, Antigravity) vede skill-ul din plugin.

## Plugin-ul

- `plugins/ase-moodle/.mcp.json`: pornește `ase-moodle-mcp` din PATH.
- `plugins/ase-moodle/commands/*.md`: comenzile `/ase-login`, `/ase-deadlines`, `/ase-download`.
- Validare: `claude plugin validate plugins/ase-moodle` și `claude plugin validate .`.
- Antigravity: `agy plugin validate plugins/ase-moodle`.

## Lansare (release)

1. Modifică codul și testele. Rulează `python -m unittest discover -s tests` și `python -m pyflakes src tests`.
2. Actualizează versiunea în cele patru locuri (și în `npm/package.json`, dacă ai modificat `npm/`).
3. `ase-moodle sync-plugin` dacă ai modificat skill-ul.
4. Verifică `docs/`.
5. Scanează secretele (vezi mai jos).
6. Commit cu atribuirea cerută (linia `by FiredMosquito831` la final).
7. `git push`, apoi verifică CI: `gh run list --repo FiredMosquito831/ase-moodle-mcp --limit 2`. Dacă ai modificat `npm/`, verifică și publicarea: `npm view ase-moodle-mcp version`.
8. Pe calculatorul tău: `ase-moodle update`, apoi repornește Claude Code.

### Scanarea secretelor înainte de commit

```powershell
git grep --cached -l -E "<tokenul-tău>|<parola-ta>|<adresa-ta-de-student>"
```

Nu scrie valorile reale în comandă sau în documentație. Pune-le într-o variabilă de mediu pentru sesiunea curentă. Dacă găsești un secret în istoric, consideră-l compromis și schimbă-l.

## Blocarea executabilului pe Windows

Procesele `ase-moodle-mcp.exe` pornite de clienți blochează fișierul executabil. `pip install -e .` nu-l poate rescrie atunci. Închide clienții MCP înainte de reinstalare, sau lasă instalarea existentă (codul din sursă se încarcă oricum).
