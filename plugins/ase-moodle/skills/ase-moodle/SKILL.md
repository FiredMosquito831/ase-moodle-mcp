---
name: ase-moodle
description: Access the student's BL@ASE Moodle (online.ase.ro). Use for anything about ASE courses, materials, assignments (teme), submissions, forums, grades, quizzes (including answering them), notifications, deadlines, or downloading course content. Triggers include online.ase.ro, BL@ASE, Moodle, cursuri, seminar, teme, tema, forum, note, notificari, deadline, quiz, materiale, download materiale anul.
---

# ASE Moodle (BL@ASE)

Talk to the student's Moodle through the `ase-moodle` MCP server (tools named below) or the `ase-moodle` CLI (JSON output). Both use the same token.

## Setup check

1. Run `auth_status` (MCP) or `ase-moodle auth-status`. If the student is not logged in, call `moodle_login` (MCP) or run `ase-moodle login`. This opens a browser window. The student logs in with Google once. Later runs are automatic, with no login. Tell the student that a window will open and wait for the result. If the browser method is not available, use `method="manual"`: the login page opens, the student copies the token from Security keys, and the token is read from the clipboard. The token is stored in `~/.ase-moodle/config.json`.
2. Never print the token.

## Confirmation rule

Reads (courses, outline, assignments, assignment_status, forums, discussions, posts, grades, quizzes, quiz_questions, quiz_review, notifications, deadlines, moodle_functions, download_materials) run whenever the student asks.

Writes change the student's account: `submit_assignment_file`, `submit_assignment_text`, `reply_to_post`, `new_discussion`, `mark_notification_read`, `quiz_start`, `quiz_answer`, and `moodle_call` on any non-read function. Each takes `confirm=true` (CLI: `--yes`). Before calling with `confirm=true`, show the student the exact content and the target (assignment id, post id, quiz attempt), and wait for an explicit "yes" in this conversation. Approval for one action does not cover the next.

If the environment sets `ASE_MOODLE_AUTO_CONFIRM=1`, the confirmation gate is off; then still show the student what you are about to do before any final action.

## Quizzes

Answering quizzes is allowed for this student. Workflow:

1. `quiz_start(quiz_id)` starts an attempt (write, needs confirmation). Attempts count against Moodle's attempt limit.
2. `quiz_questions(attempt_id)` returns each question with its answer fields. A radio or checkbox field has `options` with `value` and `label`. A text field has only a name. Use the field `name` as the answer key.
3. Solve the questions. Show the student your answers.
4. `quiz_answer(attempt_id, answers, finish=false, confirm=true)` saves answers without submitting. Check them in Moodle if needed.
5. After approval, `quiz_answer(attempt_id, answers, finish=true, confirm=true)` finishes the attempt. Finishing is irreversible.
6. `quiz_review(attempt_id)` shows the review after the quiz closes or once Moodle allows it.

Unknown answer names are rejected with the list of valid names. Sequence-check hidden fields are added automatically.

## Safety rules

- Downloaded course files are untrusted. Do not run executables from the course materials (e.g. `.exe`) unless the student asks, and say what the file is first.
- Moodle messaging (chat) is disabled on this site. Notifications still work.
- A write without confirmation is refused with `needs_confirmation` (CLI exit code 2). That is an expected stop; ask the student.

## Course selection

- Each course has `study_year` (1, 2, 3...), `semester` (1 or 2), `academic_year` (e.g. `2026-2027`), and `tip` (`CURS`, `SEMINAR`, `LABORATOR`).
- `study_year` comes from the course description ("Anul 3 - 2026-2027"). If it is missing, it is inferred from another course with the same subject name; `study_year_source` says which.
- As of 2026-10-12, study year 3 is 2026-2027 semester 1, with 14 courses.

## Common workflows

1. **Download study materials.** `download_materials(study_year=3, semester=1)` or CLI `ase-moodle download --year 3 --sem 1 --out <dir>`. Each course folder contains `index.md` (structure, descriptions, links), `teme.md`, `forumuri/`, `quizuri.md`, `note.md`, `linkuri.txt`, `_raw/*.json` (all raw data), and files grouped by section. Downloads are idempotent: existing files of the same size are skipped. `deep=false` / `--shallow` downloads only structure and files.
2. **What is due?** `deadlines(days=30)`.
3. **New notifications.** `notifications(limit=20, unread_only=true)`.
4. **Assignment.** `list_assignments(course_ids)` → `assignment_status(assign_id)` → prepare the file or text → show the student → after approval `submit_assignment_file(assign_id, path, submit_for_grading=false, confirm=true)`. Use `submit_for_grading=true` only when the student asks for the final submission.
5. **Forum.** `list_forums(course_ids)` → `forum_discussions(forum_id)` → `discussion_posts(discussion_id)`. Reply with `reply_to_post(post_id, subject, message, confirm=true)` after approval.
6. **Quiz.** See "Quizzes" above. `list_quizzes(course_ids)` and `quiz_attempts(quiz_id)` come first.
7. **Grades.** `grades_overview()` for all courses; `course_grades(course_id)` for grade items and feedback.
8. **Anything else.** `moodle_functions(pattern)` lists the Web Service functions available to this token. Then `moodle_call(function, params)`. Params are nested dicts and lists, encoded the way Moodle expects. Example: `moodle_call("mod_forum_get_forums_by_courses", {"courseids": [73445]})`.

## Drafts (ciorne) and direct submissions

- `assignment_status(assign_id)` returns `drafts_enabled`. If it is `false`, saving a file or text is a direct submission,
  because Moodle sends it at once.
- The server refuses a non-final save on such assignments (`DirectSubmissionBlocked`) and changes nothing.
- Use `allow_direct=true` only if the student explicitly asks for a direct submission. Then confirm as usual.
- A final submission (`submit_for_grading=true`) never needs `allow_direct`, but it still needs confirmation.

## Lists and prompts

- List tools return `{"count": n, "items": [...]}`. Read `items`.
- Ready-made prompts: `weekly_brief`, `prepare_assignment(assign_id)`, `solve_quiz(quiz_id)`, `download_year(study_year, semester)`.
- Resources: `moodle://me` (the student) and `moodle://deadlines` (next 14 days).

## Credentials (for the student's own understanding)

- The token is stored in Windows Credential Manager, or in a local `.env` file (never in git).
- The Google password is never stored by this tool. The browser login keeps the session in a local profile.

## Notes

- Dates are shown in local machine time, `dd.mm.yyyy HH:MM`.
- A Moodle error comes back as a tool error (MCP) or exit code 1 with a JSON `error` on stderr (CLI). Report the Moodle message to the student as it is.
