# Dezvoltare

## Structura

```
src/ase_moodle/
  config.py      token (Credential Manager / Secret Service), .env, config.json, folderul de descărcare
  auth.py        login prin browser (SSO) și manual; status; logout
  client.py      client REST Moodle: call, upload, download; MoodleError
  functions.py   lista funcțiilor Moodle folosite (obligatorii / opționale), verificată de `doctor`
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
tests/                    teste offline, server Moodle fals (fake_moodle.py), smoke_mcp.py (handshake MCP)
scripts/                  bootstrap.ps1 (Windows), bootstrap.sh (Linux/macOS), release.py (versiunea)
.github/workflows/        ci.yml (teste), pypi.yml (publicare PyPI), npm.yml, pages.yml
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

Pentru funcții Moodle noi, verifică întâi că există în serviciul mobil: `ase-moodle functions --filter 'nume'`. Adaugă numele în `src/ase_moodle/functions.py` (obligatorie sau opțională); `test_moodle_functions.py` pică altfel.

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

Versiunea are o singură sursă: `version` din `pyproject.toml`. Lângă ea, `RELEASE_DATE` din `src/ase_moodle/__init__.py` este ziua release-ului (UTC, forma `AAAA-LL-ZZT00:00:00Z`); pinurile de lansare o folosesc la `--exclude-newer`. Restul copiilor le scrie `scripts/release.py`:

```powershell
python scripts/release.py 0.2.5                    # versiunea nouă, data = azi (UTC)
python scripts/release.py 0.2.5 --date 2026-11-02  # altă zi
python scripts/release.py --check                  # nu schimbă nimic; exit 1 și lista nepotrivirilor
python scripts/release.py --check --expect 0.2.5   # în plus: versiunea cerută de tag (folosit de pypi.yml)
```

Ce scrie și verifică:

- `pyproject.toml` (`version`) și `src/ase_moodle/__init__.py` (`__version__`, `RELEASE_DATE`)
- `plugins/ase-moodle/.claude-plugin/plugin.json`, `plugins/ase-moodle/.codex-plugin/plugin.json`, `plugins/ase-moodle/plugin.json`
- `.claude-plugin/marketplace.json` (`metadata.version`)
- copia skill-ului din plugin, identică octet cu octet cu `src/ase_moodle/data/SKILL.md`
- fiecare `ase-moodle==<versiune>` și `--exclude-newer <dată>` dintr-un fișier urmărit de git. În documentație, preferă un placeholder (`ase-moodle==X.Y.Z`); un pin scris de mână trebuie să fie cel curent.

`tests/test_release.py` rulează același verificator (`test_every_pin_matches_the_release`), deci un loc uitat pică testele. Un loc nou (de exemplu launcherul sau pachetul npm) se adaugă în `locations()` sau `copies()` din `scripts/release.py`.

Pachetul npm are versiunea lui, în `npm/package.json`. Testul nu o verifică, dar trebuie crescută la fiecare modificare din `npm/`: workflow-ul `npm` publică doar versiuni noi, iar o versiune publicată nu se mai poate republica.

## Skill-ul

Sursa este `src/ase_moodle/data/SKILL.md`. Copia din plugin trebuie să fie identică:

```powershell
ase-moodle sync-plugin
```

`scripts/release.py` face aceeași copie. `test_release.py` verifică sincronizarea (octet cu octet). Clientul (Claude Code, Antigravity) vede skill-ul din plugin.

## Plugin-ul

- `plugins/ase-moodle/.mcp.json`: pornește `ase-moodle-mcp` din PATH.
- `plugins/ase-moodle/commands/*.md`: comenzile `/ase-login`, `/ase-deadlines`, `/ase-download`.
- Validare: `claude plugin validate plugins/ase-moodle` și `claude plugin validate .`.
- Antigravity: `agy plugin validate plugins/ase-moodle`.

## Lansare (release)

Pachetul Python se publică pe PyPI de workflow-ul `.github/workflows/pypi.yml`, la un tag `vX.Y.Z`, prin trusted publishing (fără token stocat).

**Ordinea contează: tagul și publicarea întâi, push pe `main` abia după ce jobul `pypi-verify` e verde.** Marketplace-ul pluginului citește `main`. Un plugin care cere o versiune care nu e încă pe PyPI nu pornește la nimeni, iar Claude Code sare peste un server eșuat 15 minute.

1. Modifică codul și testele. Rulează `python -m unittest discover -s tests` și `python -m pyflakes src tests scripts`.
2. `python scripts/release.py X.Y.Z` (versiunea, data, manifestele, copia skill-ului, pinurile). Dacă ai modificat `npm/`, crește și `npm/package.json`.
3. `python scripts/release.py --check` trebuie să spună `ok`.
4. Verifică `docs/`.
5. Scanează secretele (vezi mai jos).
6. Commit pe o ramură, cu atribuirea cerută (linia `by FiredMosquito831` la final).
7. Tag pe acel commit și push doar al tagului: `git tag vX.Y.Z <sha>`, apoi `git push origin vX.Y.Z`.
8. Urmărește workflow-ul: `gh run list --repo FiredMosquito831/ase-moodle-mcp --workflow pypi.yml --limit 1`, apoi `gh run watch <id>`. Joburile:
   - `build`: `release.py --check --expect X.Y.Z` (tagul = versiunea din pyproject = fiecare copie), `uv build`, conținutul wheel-ului (inclusiv `ase_moodle/data/SKILL.md`), SHA-256;
   - `smoke` (Ubuntu, Windows, macOS): wheel-ul și sdist-ul pornite cu `uvx --isolated --from <fișier> ase-moodle-mcp`, handshake MCP cu 28 de unelte (`tests/smoke_mcp.py`);
   - `testpypi`: upload pe TestPyPI;
   - `testpypi-verify`: fișierele de pe TestPyPI au același SHA-256 ca build-ul (fără să instaleze nimic de acolo);
   - `pypi`: așteaptă aprobarea ta (environment `pypi`), apoi upload pe PyPI;
   - `pypi-verify` (Ubuntu, Windows): SHA-256 egal, apoi `uvx --isolated --from ase-moodle==X.Y.Z ase-moodle-mcp` cu un cache uv gol dă 28 de unelte.
9. Doar după ce `pypi-verify` e verde: push pe `main` (fast-forward până la commitul cu tag). Verifică CI: `gh run list --repo FiredMosquito831/ase-moodle-mcp --limit 2`. Dacă ai modificat `npm/`, verifică și publicarea: `npm view ase-moodle-mcp version`.
10. Pe calculatorul tău: `ase-moodle update`, apoi repornește Claude Code.

Probă fără publicare: GitHub → Actions → `pypi` → Run workflow (`workflow_dispatch`). Rulează doar `build` și `smoke`.

Probă locală, înainte de tag (cu un cache uv separat, ca să nu atingi cache-ul obișnuit):

```powershell
$env:UV_CACHE_DIR = "$env:TEMP\uv-cache-proba"
uv build --out-dir dist
python tests/smoke_mcp.py -- uvx --isolated --from dist/ase_moodle-X.Y.Z-py3-none-any.whl ase-moodle-mcp
python tests/smoke_mcp.py -- uvx --isolated --from dist/ase_moodle-X.Y.Z.tar.gz ase-moodle-mcp
```

`smoke_mcp.py` trimite doar `initialize` și `tools/list` (nicio unealtă), cu `ASE_MOODLE_URL=http://127.0.0.1:9`, keyring nul și un home temporar, deci nu poate citi tokenul tău.

### Configurarea publicării (o singură dată, de mâna maintainerului)

Fă pașii aproape de primul tag: un „pending publisher” nu rezervă numele.

1. Verifică că `https://pypi.org/pypi/ase-moodle/json` răspunde încă 404 (numele e liber).
2. test.pypi.org (cont cu 2FA) → Your account → Publishing → „Add a new pending publisher” → GitHub: PyPI project name `ase-moodle`, Owner `FiredMosquito831`, Repository name `ase-moodle-mcp`, Workflow name `pypi.yml`, Environment name `testpypi`.
3. pypi.org: la fel, cu Environment name `pypi`.
4. GitHub → repo Settings → Environments: creează `testpypi`, apoi `pypi` cu „Required reviewers: FiredMosquito831” și o regulă de deployment pentru taguri `v*`.
5. Primul release: tagul `v0.2.4` pe commitul care conține `pypi.yml`, apoi aprobarea jobului `pypi` după ce `testpypi-verify` e verde.

Dacă PyPI refuză numele, rezerva este un wheel atașat unui GitHub Release.

### Scanarea secretelor înainte de commit

```powershell
git grep --cached -l -E "<tokenul-tău>|<parola-ta>|<adresa-ta-de-student>"
```

Nu scrie valorile reale în comandă sau în documentație. Pune-le într-o variabilă de mediu pentru sesiunea curentă. Dacă găsești un secret în istoric, consideră-l compromis și schimbă-l.

## Blocarea executabilului pe Windows

Procesele `ase-moodle-mcp.exe` pornite de clienți blochează fișierul executabil. `pip install -e .` nu-l poate rescrie atunci. Închide clienții MCP înainte de reinstalare, sau lasă instalarea existentă (codul din sursă se încarcă oricum).
