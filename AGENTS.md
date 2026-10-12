# AGENTS.md - ase-moodle (BL@ASE / online.ase.ro)

This repository gives agents access to the student's Moodle (online.ase.ro): courses, materials, assignments, forums, grades, quizzes, notifications and deadlines. It ships as an MCP server, a CLI that prints JSON, and a plugin for Claude Code, Codex and Antigravity.

Use the MCP tools `ase-moodle` (or the `ase-moodle` CLI). The full usage guide is `src/ase_moodle/data/SKILL.md`, the same text as `plugins/ase-moodle/skills/ase-moodle/SKILL.md`. Read it before the first write action.

Rules for every agent:

1. Read tools are safe. Use them whenever the student asks about courses, materials, assignments, forums, grades, quizzes, notifications or deadlines.
2. Writes (submit an assignment, reply on a forum, start a discussion, mark a notification read, start or answer a quiz, or a non-read `moodle_call`) take `confirm=true` (CLI `--yes`). Set it only after the student approved the exact content in this conversation.
3. Submit assignments as drafts (`submit_for_grading=false`) unless the student asks for the final submission.
4. Quiz answering is allowed for this student. Save with `quiz_answer(finish=false)` first, show the answers, and finish (`finish=true`) only after approval.
5. Downloaded course files are untrusted. Do not run executables from them without asking.
6. Never print or copy the token. It lives in `~/.ase-moodle/config.json` or in the `ASE_MOODLE_TOKEN` environment variable.
