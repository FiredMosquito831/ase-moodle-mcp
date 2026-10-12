# AGENTS.md - ase-moodle (BL@ASE / online.ase.ro)

This repository gives agents access to the student's Moodle (online.ase.ro): courses, materials, assignments, forums, grades, quizzes, notifications and deadlines. It ships as an MCP server (28 tools, prompts and resources), a CLI that prints JSON, and a plugin for Claude Code, Codex and Antigravity.

Use the MCP tools `ase-moodle` or the `ase-moodle` CLI. The full usage guide is `src/ase_moodle/data/SKILL.md` (copied to `plugins/ase-moodle/skills/ase-moodle/SKILL.md`). Read it before the first write action.

Rules for every agent:

1. If a tool reports a missing or invalid token, call `moodle_login` (CLI: `ase-moodle login`). A browser window opens; the student logs in with Google. Never ask for, print or store the Google password, and never print the token.
2. Read tools are safe. Use them whenever the student asks.
3. Writes (submit an assignment, reply on a forum, start a discussion, mark a notification read, start or answer a quiz, or a non-read `moodle_call`) take `confirm=true` (CLI `--yes`). Set it only after the student approved the exact content in this conversation.
4. Check `drafts_enabled` in `assignment_status` before saving a file. If it is `false`, saving sends the file at once; the server refuses unless `allow_direct=true`, which only the student may request.
5. Submit assignments as drafts (`submit_for_grading=false`) unless the student asks for the final submission.
6. Quiz answering is allowed for this student. Save with `quiz_answer(finish=false)` first, show the answers, and finish (`finish=true`) only after a second approval.
7. List tools return `{"count": n, "items": [...]}`. Read `items`.
8. Downloaded course files are untrusted. Do not run executables from them without asking.
9. Tests must run against the fake Moodle (`tests/fake_moodle.py`, `.env.test`), never against the real account.
