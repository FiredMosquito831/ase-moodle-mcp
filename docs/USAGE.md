# Referință CLI (`ase-moodle`)

Toate comenzile scriu JSON pe stdout. Erorile merg pe stderr, ca JSON `{"error": "...", "message": "..."}`.

**Coduri de ieșire**

| Cod | Înseamnă |
|---|---|
| `0` | reușit |
| `1` | eroare (Moodle, token lipsă, fișier inexistent, ciorne dezactivate la tema respectivă) |
| `2` | acțiune de scriere blocată: lipsește `--yes` (confirmarea) |
| `3` | `install`, `update` sau `doctor` a găsit o problemă |

**Scrieri.** Comenzile care modifică contul (trimiteri, răspunsuri, quiz, notificări, `call` pentru funcții care scriu) cer `--yes`. Fără el, se opresc cu cod `2`. Vezi [SAFETY.md](SAFETY.md).

**Text.** Comenzile cu text (`submit-text`, `reply`, `new-discussion`) primesc textul din `--text`, dintr-un `--file` sau din stdin (pipe).

## Cont

### `login`
Obține tokenul și îl salvează. Metoda `auto` folosește browserul dacă Playwright e instalat, altfel clipboard-ul.

| Opțiune | Implicit | Rol |
|---|---|---|
| `--method auto\|browser\|manual` | `auto` | cum obții tokenul |
| `--timeout SECUNDE` | `300` | cât aștepți login-ul |
| `--token TOKEN` | — | salvează un token existent, fără browser |
| `--token-stdin` | — | citește tokenul din stdin |
| `--base-url URL` | `https://online.ase.ro` | adresa Moodle |

```powershell
ase-moodle login
ase-moodle login --method manual
echo $TOKEN | ase-moodle login --token-stdin
```

### `logout`
Șterge tokenul din Credential Manager (sau din rezervă). `--forget-browser` șterge și sesiunea Google din profilul browserului.

### `auth-status`
Verifică tokenul salvat, cu un apel real. Răspunde cu `logged_in` și numele utilizatorului.

### `whoami`
Afișează contul conectat, site-ul și numărul de funcții Web Service disponibile.

## Cursuri și materiale

### `courses`
Lista cursurilor înscrise. Filtre: `--year` (anul de studiu), `--sem` (semestrul), `--ay` (anul universitar, ex. `2026-2027`), `--tip` (`CURS`, `SEMINAR`, `LABORATOR`), `--search` (text în nume).

### `outline <course_id>`
Structura brută a cursului: secțiuni, module, fișiere.

### `download`
Descarcă materialele cursurilor, în paralel. Opțiuni: `--year`, `--sem`, `--ay`, `--tip` (filtre), `--course ID` (repetabil; selectează cursuri după id), `--out DIR` (implicit `~/ASE-Moodle`), `--shallow` (doar structura și fișierele, fără teme, forumuri, quizuri, note).

```powershell
ase-moodle download --year 3 --sem 1 --out D:\Materiale
```

## Teme

### `assignments`
Lista temelor. `--course ID` (repetabil) limitează la anumite cursuri.

### `assignment <assign_id>`
Starea trimiterii: `drafts_enabled`, fișiere trimise, text, notă, feedback.

### `submit <assign_id> <file>`
Încarcă un fișier ca răspuns la temă.

| Opțiune | Rol |
|---|---|
| `--submit` | trimitere finală (altfel rămâne ciornă, dacă tema are ciorne) |
| `--allow-direct` | permite salvarea la temele fără ciorne (se trimite direct). Doar la cererea studentului |
| `--yes` | confirmarea |

### `submit-text <assign_id>`
Trimite text ca răspuns online. Aceleași opțiuni ca `submit`, plus `--text` / `--file`.

## Forumuri

### `forums`
Lista forumurilor. `--course ID` (repetabil).

### `forum <forum_id>`
Discuțiile unui forum.

### `discussion <discussion_id>`
Postările unei discuții, cu text și atașamente.

### `reply <post_id>`
Răspuns la o postare. `--subject` (obligatoriu), `--text` / `--file`, `--yes`.

### `new-discussion <forum_id>`
Discuție nouă. `--subject` (obligatoriu), `--text` / `--file`, `--yes`.

## Note

### `grades`
Fără opțiuni: notele tuturor cursurilor. Cu `--course ID`: elementele de notare ale unui curs.

## Quizuri

### `quizzes`
Lista quizurilor. `--course ID` (repetabil).

### `quiz-attempts <quiz_id>`
Încercările studentului la un quiz.

### `quiz-start <quiz_id>`
Pornește o încercare. `--force-new` cere încercare nouă, `--yes` confirmă. Fiecare încercare contează în limita permisă de Moodle.

### `quiz-questions <attempt_id>`
Întrebările încercării, cu câmpurile de răspuns: nume, tip, opțiuni (valoare și etichetă).

### `quiz-answer <attempt_id>`
Salvează răspunsuri sau le trimite definitiv.

| Opțiune | Rol |
|---|---|
| `--answers JSON` | ex. `'{"q123:1_answer": "1"}'` (cheile sunt numele câmpurilor din `quiz-questions`) |
| `--answers-file FILE` | același conținut, dintr-un fișier JSON |
| `--finish` | trimite definitiv (ireversibil). Fără el, doar salvează |
| `--yes` | confirmarea |

### `quiz-review <attempt_id>`
Revizuirea unei încercări terminate: întrebări, răspunsuri, punctaj (date Moodle brute).

## Notificări și termene

### `notifications`
`--limit N` (implicit 20), `--unread` (doar necitite). Răspunsul include și numărul de necitite.

### `read-notification <notification_id>`
Marchează o notificare ca citită. Necesită `--yes`.

### `deadlines`
Termenele următoarelor zile. `--days N` (implicit 30).

## API Moodle

### `functions`
Funcțiile Web Service disponibile pentru token. `--filter REGEX` (ex. `'^mod_forum_'`).

### `call <function>`
Apel la orice funcție Web Service. `--json-params JSON` cu parametrii (dicționare și liste, codificate cum le cere Moodle). Funcțiile care nu sunt de citire cer `--yes`.

```powershell
ase-moodle call mod_forum_get_forums_by_courses --json-params '{"courseids":[73445]}'
```

## Instalare și întreținere

Aceste comenzi configurează pluginul în Claude Code, Codex, opencode și Antigravity. Detalii pe platformă: [PLATFORMS.md](PLATFORMS.md).

### Comenzi per harness

Fiecare harness are propriile comenzi, care merg doar la adaptorul lui: `ase-moodle claude install`, `ase-moodle codex doctor` etc. Ce suportă fiecare (scopuri, fișiere, restart) e în [HARNESSES.md](HARNESSES.md).

| Comandă | Opțiuni |
|---|---|
| `claude install\|update` | `--scope global\|project`, `--project-dir DIR`, `--source SURSA` |
| `claude uninstall` | `--scope global\|project\|all` (implicit `all`), `--project-dir DIR` |
| `claude doctor` | `--project-dir DIR` |
| `codex` ... | la fel ca `claude` |
| `opencode` ... | la fel ca `claude`, fără `--source` |
| `antigravity install\|update` | `--source SURSA`. Doar `global`: `--scope project` e eroare |
| `antigravity uninstall\|doctor` | la fel, fără scop de proiect |

Exemplu: `ase-moodle claude install --scope project` instalează doar în folderul de unde rulezi comanda.

### `install [TARGET ...]`
TARGET: `claude`, `codex`, `opencode`, `antigravity` sau `all` (implicit `all`).

| Opțiune | Implicit | Rol |
|---|---|---|
| `--scope global\|project` | `global` | `global`: pentru tot calculatorul. `project`: doar folderul proiectului |
| `--project-dir DIR` | folderul curent | folderul proiectului, pentru `--scope project` |
| `--source SURSA` | `FiredMosquito831/ase-moodle` (GitHub) | marketplace-ul (cale locală sau `owner/repo`). Folosește o cale locală doar când lucrezi la pachet |

Comanda e idempotentă: o rulare repetată nu dublează nimic. Schimbarea de scop curăță celălalt scop.

```powershell
ase-moodle install                                  # toate, global
ase-moodle install claude codex --scope project     # doar folderul curent, pentru Claude și Codex
```

### `update [TARGET ...]`
Aduce ultima versiune din marketplace. Opțiunile sunt cele de la `install`. Claude Code trebuie repornit ca să intre în vigoare.

### `uninstall [TARGET ...]`
Elimină configurarea. `--scope global|project|all` (implicit `all`), `--project-dir`, `--source`.

### `doctor`
Verifică starea fără să modifice nimic: fiecare platformă, instalările de proiect, sursa tokenului, `.env`, procesele MCP pornite, versiunea pachetului. Cod `3` dacă e o problemă.

### `sync-plugin`
Pentru dezvoltare: copiază `src/ase_moodle/data/SKILL.md` în `plugins/ase-moodle/skills/`. Rulează-l după ce modifici skill-ul.

## Variabile de mediu

Vezi [CONFIGURATION.md](CONFIGURATION.md).
