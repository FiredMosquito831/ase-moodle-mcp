# Serverul MCP (`ase-moodle-mcp`)

Serverul MCP vorbește prin stdio. Pornește-l cu `ase-moodle-mcp` sau cu `python -m ase_moodle.mcp_server`. Nu ai nevoie să-l pornești manual: clienții (Claude Code, Codex, opencode, Antigravity) îl pornesc singuri, după ce ai rulat `ase-moodle install`.

Versiunea curentă are **28 de unelte**, **4 prompturi** și **2 resurse**.

## Unelte

Fiecare unealtă are anotări: `readOnlyHint` (doar citește) sau `destructiveHint` (scrie în contul Moodle). Clienții care respectă anotările pot cere confirmare pentru cele distructive.

Listele vin ca `{"count": n, "items": [...]}`.

### Cont

| Unealtă | Tip | Ce face |
|---|---|---|
| `whoami` | citire | contul conectat, site, număr de funcții disponibile |
| `auth_status` | citire | tokenul salvat funcționează? |
| `moodle_login` | local | deschide browserul sau citește clipboard-ul și salvează tokenul. Parametri: `method` (`auto`, `browser`, `manual`), `timeout_s` |

### Cursuri și materiale

| Unealtă | Tip | Parametri |
|---|---|---|
| `list_courses` | citire | `study_year`, `semester`, `academic_year`, `tip`, `search` |
| `course_outline` | citire | `course_id` |
| `download_materials` | local | `course_ids`, `study_year`, `semester`, `out_dir`, `deep` (implicit `true`) |

### Teme

| Unealtă | Tip | Parametri |
|---|---|---|
| `list_assignments` | citire | `course_ids` |
| `assignment_status` | citire | `assign_id`. Răspunsul include `drafts_enabled` |
| `submit_assignment_file` | scriere | `assign_id`, `file_path`, `submit_for_grading`, `confirm`, `allow_direct` |
| `submit_assignment_text` | scriere | `assign_id`, `text`, `submit_for_grading`, `confirm`, `allow_direct` |

### Forumuri

| Unealtă | Tip | Parametri |
|---|---|---|
| `list_forums` | citire | `course_ids` |
| `forum_discussions` | citire | `forum_id` |
| `discussion_posts` | citire | `discussion_id` |
| `reply_to_post` | scriere | `post_id`, `subject`, `message`, `confirm` |
| `new_discussion` | scriere | `forum_id`, `subject`, `message`, `confirm` |

### Note

| Unealtă | Tip | Parametri |
|---|---|---|
| `grades_overview` | citire | — |
| `course_grades` | citire | `course_id` |

### Quizuri

| Unealtă | Tip | Parametri |
|---|---|---|
| `list_quizzes` | citire | `course_ids` |
| `quiz_attempts` | citire | `quiz_id` |
| `quiz_start` | scriere | `quiz_id`, `force_new`, `confirm` |
| `quiz_questions` | citire | `attempt_id` |
| `quiz_answer` | scriere | `attempt_id`, `answers` (dicționar nume de câmp → valoare), `finish`, `confirm` |
| `quiz_review` | citire | `attempt_id` |

### Notificări și termene

| Unealtă | Tip | Parametri |
|---|---|---|
| `notifications` | citire | `limit`, `unread_only` |
| `mark_notification_read` | scriere | `notification_id`, `confirm` |
| `deadlines` | citire | `days` |

### API Moodle

| Unealtă | Tip | Parametri |
|---|---|---|
| `moodle_functions` | citire | `pattern` (regex) |
| `moodle_call` | scriere sau citire | `function`, `params`, `confirm`. Funcțiile care nu sunt de citire cer `confirm` |

## Prompturi

Prompturile sunt fluxuri gata, pe care clientul le poate oferi ca comenzi.

| Prompt | Parametri | Ce face |
|---|---|---|
| `weekly_brief` | — | termene, notificări necitite și teme deschise, pe scurt (nu scrie nimic) |
| `prepare_assignment` | `assign_id` | cerința, termenul, starea, plan. Trimiterea doar după aprobare |
| `solve_quiz` | `quiz_id` | întrebările, răspunsuri propuse, salvare, apoi trimitere după a doua aprobare |
| `download_year` | `study_year`, `semester` | descarcă materialele și rezumă raportul |

## Resurse

| Resursă | Conținut |
|---|---|
| `moodle://me` | profilul studentului conectat |
| `moodle://deadlines` | termenele din următoarele 14 zile |

## Conectarea clienților

Serverul e același peste tot: comanda `ase-moodle-mcp`, care pornește prin stdio. Ce diferă este locul unde clientul îl găsește și cât de larg se aplică. Cea mai simplă cale e `ase-moodle install`, care scrie configurația corectă pentru fiecare client. Detalii pe platformă: [PLATFORMS.md](PLATFORMS.md).

### Unde se adaugă, pe scope

| Client | Global (tot calculatorul) | Doar un folder | Unde se scrie |
|---|---|---|---|
| Claude Code | `ase-moodle install claude` (scope user, implicit) | `ase-moodle install claude --scope project` | global: `~/.claude/settings.json`; folder: `<folder>/.claude/settings.json` |
| Codex | `ase-moodle install codex` | `ase-moodle install codex --scope project` | global: `~/.codex/config.toml`; folder: `<folder>/.codex/config.toml` |
| opencode | `ase-moodle install opencode` | `ase-moodle install opencode --scope project` | global: `~/.config/opencode/opencode.json`; folder: `<folder>/opencode.json` |
| Antigravity | `ase-moodle install antigravity` | nu are | `agy mcp add` (global) |

Ce înseamnă scope-ul pentru fiecare:

- **Claude Code, global (user):** serverul e disponibil în orice folder, inclusiv în subfoldere.
- **Claude Code, proiect:** serverul e disponibil doar dacă pornești Claude Code din folderul respectiv. Nu se aplică în subfoldere: am verificat asta pentru plugin.
- **opencode, proiect:** `opencode.json` e căutat în folderul curent și în toți părinții lui, până la rădăcina discului. Deci un `opencode.json` pus într-un folder se aplică și în subfolderele lui.
- **Codex, proiect:** `.codex/config.toml` se folosește doar pentru proiecte de încredere.
- **Antigravity:** doar global. Nu are scope de proiect.

### Comenzi manuale, dacă nu vrei instalatorul

Dacă adaugi serverul manual, nu-l pune pe lângă instalator, ca să nu pornească de două ori.

```bash
# Claude Code, pentru toate folderele (scope user)
claude mcp add --scope user ase-moodle -- ase-moodle-mcp

# Claude Code, doar folderul curent (scope local, implicit)
claude mcp add --scope local ase-moodle -- ase-moodle-mcp

# Claude Code, în .mcp.json din folder, versionat (scope project)
claude mcp add --scope project ase-moodle -- ase-moodle-mcp

# Codex, global (~/.codex/config.toml)
codex mcp add ase-moodle -- ase-moodle-mcp

# Antigravity, global
agy mcp add ase-moodle -- ase-moodle-mcp
```

Pentru opencode, în `opencode.json` (global sau din folder):

```json
{
  "mcp": {
    "ase-moodle": {
      "type": "local",
      "command": ["ase-moodle-mcp"],
      "enabled": true
    }
  }
}
```

Pentru Codex, în `~/.codex/config.toml` sau în `.codex/config.toml`:

```toml
[mcp_servers.ase-moodle]
command = "ase-moodle-mcp"
```

Comanda `ase-moodle-mcp` trebuie să fie în `PATH`. Dacă ai instalat cu `pipx`, asta e deja adevărat. Instalatorul scrie în unele locuri calea absolută a Python-ului, ca să nu depindă de `PATH`.

Pentru Claude Code, `ase-moodle install` șterge singur o intrare manuală `ase-moodle`, ca să nu se dubleze cu pluginul. Pentru Codex și opencode, instalatorul își scrie propria intrare `ase-moodle`, iar o intrare manuală cu același nume poate fi suprascrisă sau poate dubla serverul. Antigravity actualizează intrarea cu același nume, în loc să adauge una nouă.

### Ce alegi pentru folderul tău

- Vrei serverul în `Facultate` și în toate subfolderele: scope global (`ase-moodle install claude`). Scope-ul de proiect nu ajunge în subfoldere.
- Vrei serverul doar într-un repo: scope de proiect, rulat din folderul repo-ului.
- Antigravity: întotdeauna global.

Global înseamnă că serverul e disponibil în orice folder al calculatorului, cu contul tău Moodle. Scrierile rămân protejate de confirmare (`confirm=true`).

Serverul citește tokenul din Credential Manager sau din `.env` (vezi [AUTH.md](AUTH.md)). Nu primește tokenul prin clienți.

## Reguli pe care le respectă serverul

- Scrierile cer `confirm=true`. Fără el, serverul întoarce eroare și nu face nimic.
- Trimiterile la temele fără ciorne sunt refuzate, cu excepția `allow_direct=true`. Vezi [SAFETY.md](SAFETY.md).
- Erorile Moodle ajung ca erori ale uneltei, cu mesajul original.

## Verificare rapidă

După `ase-moodle install`, în clientul tău, întreabă: „Ce termene am în următoarele 7 zile?”. Serverul ar trebui să apeleze `deadlines`.
