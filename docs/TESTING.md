# Testare

Suita rulează fără internet și fără contul tău. Testele folosesc un server Moodle **fals** (`tests/fake_moodle.py`), cu date sintetice și un token de test.

## Rulare

Din folderul repo-ului:

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
python -m pyflakes src tests
```

La prima rulare pe un calculator nou, `pip install -e .` instalează și dependențele (`httpx`, `mcp`, `playwright`). Playwright nu are nevoie de browser pentru teste.

Linux (sau WSL):

```bash
python3 -m venv ~/venv-ase && . ~/venv-ase/bin/activate
pip install -e . pyflakes
python -m unittest discover -s tests
python -m pyflakes src tests
```

Numărul de teste crește cu versiunile. Rezultatul așteptat: `OK`, fără `FAILED` și fără erori.

## Structura

| Fișier | Ce acoperă |
|---|---|
| `test_offline.py` | parsing cursuri, codificarea parametrilor, politica de confirmare |
| `test_quiz.py` | parsarea câmpurilor de răspuns, validarea numelor, start, salvare, trimitere |
| `test_config.py` | `.env`, Credential Manager (simulat), migrarea tokenului, rezerva |
| `test_auth.py` | decodarea redirectului SSO, extragerea tokenului din pagină, clipboard |
| `test_install.py` | instalatorii pe toate platformele, ambele scopuri, în foldere temporare |
| `test_integration.py` | CLI și client contra serverului fals: teme, ciorne, quiz, descărcare, notificări |
| `test_release.py` | versiuni coerente, serverul MCP real prin stdio, comanda `update` |
| `test_platform_docs.py` | permisiuni POSIX, folderul implicit, clipboard Linux, documentația |

## Serverul fals

`tests/fake_moodle.py` imită endpoint-urile REST, upload-ul și `pluginfile.php`. Are:

- un student inventat (`Student Test`), trei cursuri, două teme (una cu ciorne, una fără), un forum, un quiz, notificări;
- un token fix (`fake-token-for-tests-only`);
- niciun apel la internet, niciun date reale.

Îl poți porni manual, ca să încerci comenzile fără cont real:

```powershell
python tests\fake_moodle.py --port 8765
```

Apoi, în alt terminal:

```powershell
$env:ASE_MOODLE_ENV_FILE = ".env.test"
ase-moodle whoami
ase-moodle courses --year 3 --sem 1
```

`.env.test` (în repo) conține adresa `http://127.0.0.1:8765` și tokenul de test. Nu are valori reale.

**Regulă:** testele nu trebuie să ruleze niciodată contra contului real. `test_integration.py` setează `ASE_MOODLE_URL` pe serverul fals, iar `ASE_MOODLE_ENV_FILE` pe un fișier inexistent, ca să nu fie citit `.env`-ul tău.

## CI

`.github/workflows/ci.yml` rulează la fiecare push, pe **Windows** și pe **Ubuntu**:

1. `pip install -e . pyflakes`
2. `python -m pyflakes src tests`
3. `python -m unittest discover -s tests -v`

Statusul e vizibil cu `gh run list --repo FiredMosquito831/ase-moodle-mcp`.

## Verificare live (manuală)

Nu rula asta automat. Testele live schimbă contul Moodle.

Ce poți verifica fără efecte:

- `whoami`, `auth-status`, `courses`, `assignments`, `deadlines`, `notifications`, `grades`;
- `assignment <id>` pe o temă: vezi `drafts_enabled`;
- `submit <id> <file>` pe o temă fără ciorne (fără `--allow-direct`): trebuie refuzat, fără efecte;
- `quiz-start <id>` pe un quiz închis: Moodle răspunde „nu este disponibil”.

Ce schimbă contul (fă-le doar cu aprobare): trimiteri, răspunsuri pe forum, marcare notificări, quizuri pornite sau trimise.

## Ce nu e testat

- Quizuri deschise, completate de la cap la coadă, pe contul real (nu există quiz deschis în momentul scrierii).
- Trimiteri reale de teme cu ciorne activate.
- CLI-urile `claude`, `codex`, `opencode`, `agy` pe Linux (comenzile de instalare reală). Logica instalatorului e testată cu runner fals.
- macOS.

## După o modificare

1. `python -m unittest discover -s tests`
2. `python -m pyflakes src tests`
3. Dacă ai modificat `src/ase_moodle/data/SKILL.md`: `ase-moodle sync-plugin`
4. Dacă ai modificat comenzile CLI sau uneltele MCP: actualizează `docs/USAGE.md` sau `docs/MCP.md` (testele de documentație pică altfel)
5. Commit, push, verifică CI
