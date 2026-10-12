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

Instalatorul (`ase-moodle install`) configurează clienții automat. Detalii și comenzi manuale: [PLATFORMS.md](PLATFORMS.md).

În esență, fiecare client pornește serverul ca proces local:

- Claude Code și Codex: prin plugin (`plugins/ase-moodle/.mcp.json`), comanda `ase-moodle-mcp`.
- opencode: `mcp.ase-moodle` în `opencode.json`, cu comanda `[<python>, "-m", "ase_moodle.mcp_server"]`.
- Antigravity: `agy mcp add ase-moodle -- <python> -m ase_moodle.mcp_server`.

Serverul citește tokenul din Credential Manager sau din `.env` (vezi [AUTH.md](AUTH.md)). Nu primește tokenul prin clienți.

## Reguli pe care le respectă serverul

- Scrierile cer `confirm=true`. Fără el, serverul întoarce eroare și nu face nimic.
- Trimiterile la temele fără ciorne sunt refuzate, cu excepția `allow_direct=true`. Vezi [SAFETY.md](SAFETY.md).
- Erorile Moodle ajung ca erori ale uneltei, cu mesajul original.

## Verificare rapidă

După `ase-moodle install`, în clientul tău, întreabă: „Ce termene am în următoarele 7 zile?”. Serverul ar trebui să apeleze `deadlines`.
