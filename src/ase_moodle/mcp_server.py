"""Server MCP (stdio) pentru Moodle BL@ASE.

Functioneaza cu Claude Code, Codex, opencode, Antigravity si orice client MCP.
Unelte cu anotari: citirile sunt marcate read-only, scrierile destructive, iar descarcarile locale.
Listele vin ca {"count": n, "items": [...]} intr-un singur raspuns.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import actions, activities, auth, materials, quiz
from .client import MoodleClient
from .config import download_root, load_settings
from .courses import fetch_courses, filter_courses

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)
LOCAL = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)

mcp = FastMCP(
    "ase-moodle",
    instructions=(
        "Access to the student's Moodle (BL@ASE, online.ase.ro). If a tool reports a missing token, call moodle_login "
        "(it opens a browser; the student logs in with Google once). Read tools are safe to use whenever the student "
        "asks. Write tools (submit_*, reply_to_post, new_discussion, mark_notification_read, quiz_start, quiz_answer, "
        "moodle_call for non-read functions) need confirm=true, set only after the student approved the exact content "
        "in this conversation. Assignments without drafts send the file immediately: keep allow_direct=false unless the "
        "student explicitly asks for a direct submission. Quizzes may be answered for the student: read the questions "
        "with quiz_questions, save with quiz_answer(finish=false), and finish only after approval."
    ),
)

_client: MoodleClient | None = None


def _c() -> MoodleClient:
    global _client
    if _client is None:
        settings = load_settings()
        _client = MoodleClient(settings.base_url, settings.token)
    return _client


def _list(values: list[Any]) -> dict[str, Any]:
    return {"count": len(values), "items": values}


# ---------- cont ----------

@mcp.tool(annotations=READ)
def whoami() -> dict[str, Any]:
    """Show the logged-in student, site name and the number of Web Service functions available."""
    return activities.whoami(_c())


@mcp.tool(annotations=READ)
def auth_status() -> dict[str, Any]:
    """Check whether a saved Moodle token exists and works. Returns logged_in and the user's name."""
    return auth.status()


@mcp.tool(annotations=LOCAL)
def moodle_login(method: str = "auto", timeout_s: int = 300) -> dict[str, Any]:
    """Log in to Moodle and save the token for future calls. Use it when tools report a missing or invalid token.
    method='auto' opens a browser window: the student logs in with Google (only the first time; later runs are
    automatic). method='manual' opens the login page and reads the token copied to the clipboard.
    Blocks until the login finishes or timeout_s expires."""
    global _client
    result = auth.authenticate(method=method, timeout_s=timeout_s)
    _client = None  # urmatorul apel foloseste tokenul nou
    return result


# ---------- cursuri si materiale ----------

@mcp.tool(annotations=READ)
def list_courses(
    study_year: int | None = None,
    semester: int | None = None,
    academic_year: str | None = None,
    tip: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """List enrolled courses. Filters: study_year (1,2,3), semester (1,2), academic_year ('2026-2027'),
    tip ('CURS', 'SEMINAR', 'LABORATOR'), search (substring of the course name)."""
    courses = filter_courses(fetch_courses(_c()), study_year, semester, academic_year, tip, search)
    return _list([c.to_dict() for c in courses])


@mcp.tool(annotations=READ)
def course_outline(course_id: int) -> dict[str, Any]:
    """Raw course structure: sections, modules (activities, resources, labels), contents and file URLs."""
    return _list(_c().call("core_course_get_contents", {"courseid": course_id}))


@mcp.tool(annotations=LOCAL)
def download_materials(
    course_ids: list[int] | None = None,
    study_year: int | None = None,
    semester: int | None = None,
    out_dir: str | None = None,
    deep: bool = True,
) -> dict[str, Any]:
    """Download courses to disk, in parallel: files, pages, assignments (teme.md), forums, quizzes, grades, links,
    raw JSON. Select courses by course_ids or by study_year/semester. deep=False skips assignments/forums/quizzes/grades.
    Existing files with the same size are skipped, so repeated runs are cheap."""
    client = _c()
    courses = fetch_courses(client)
    if course_ids:
        wanted = set(course_ids)
        selected = [c for c in courses if c.id in wanted]
    else:
        selected = filter_courses(courses, study_year, semester)
    if not selected:
        raise ValueError("No course matches the selection.")
    root = Path(out_dir).expanduser() if out_dir else download_root()
    reports = materials.download_materials(client, selected, root, deep=deep)
    return {
        "root": str(root),
        "courses": len(reports),
        "downloaded": sum(r["downloaded"] for r in reports),
        "skipped": sum(r["skipped"] for r in reports),
        "failed": sum(len(r["failed"]) for r in reports),
        "reports": reports,
    }


# ---------- teme ----------

@mcp.tool(annotations=READ)
def list_assignments(course_ids: list[int] | None = None) -> dict[str, Any]:
    """List assignments (teme) with due dates, submission types and instructions."""
    return _list(activities.list_assignments(_c(), course_ids))


@mcp.tool(annotations=READ)
def assignment_status(assign_id: int) -> dict[str, Any]:
    """Submission status for an assignment: drafts_enabled, submitted files/text, grade, feedback comments."""
    return activities.assignment_status(_c(), assign_id)


@mcp.tool(annotations=WRITE)
def submit_assignment_file(
    assign_id: int,
    file_path: str,
    submit_for_grading: bool = False,
    confirm: bool = False,
    allow_direct: bool = False,
) -> dict[str, Any]:
    """Upload a local file as the assignment submission. Replaces the previous draft file.
    submit_for_grading=False saves a draft, but only if the assignment has drafts enabled (drafts_enabled).
    True sends it for grading (final). allow_direct=true allows saving on assignments without drafts, which sends the
    file immediately. Requires confirm=true."""
    return actions.submit_assignment_file(_c(), assign_id, file_path, submit_for_grading, confirm, allow_direct)


@mcp.tool(annotations=WRITE)
def submit_assignment_text(
    assign_id: int,
    text: str,
    submit_for_grading: bool = False,
    confirm: bool = False,
    allow_direct: bool = False,
) -> dict[str, Any]:
    """Write the online-text submission for an assignment. Same draft rules as submit_assignment_file.
    Requires confirm=true."""
    return actions.submit_assignment_text(_c(), assign_id, text, submit_for_grading, confirm, allow_direct)


# ---------- forumuri ----------

@mcp.tool(annotations=READ)
def list_forums(course_ids: list[int] | None = None) -> dict[str, Any]:
    """List forums (including the 'news' Announcements forum) of the given or all courses."""
    return _list(activities.list_forums(_c(), course_ids))


@mcp.tool(annotations=READ)
def forum_discussions(forum_id: int) -> dict[str, Any]:
    """All discussions of a forum with their ids, authors, dates and reply counts."""
    return _list(activities.forum_discussions(_c(), forum_id))


@mcp.tool(annotations=READ)
def discussion_posts(discussion_id: int) -> dict[str, Any]:
    """All posts of a forum discussion, with text and attachments."""
    return _list(activities.discussion_posts(_c(), discussion_id))


@mcp.tool(annotations=WRITE)
def reply_to_post(post_id: int, subject: str, message: str, confirm: bool = False) -> dict[str, Any]:
    """Reply to a forum post. Requires confirm=true after the student approved the exact message."""
    return actions.reply_to_post(_c(), post_id, subject, message, confirm)


@mcp.tool(annotations=WRITE)
def new_discussion(forum_id: int, subject: str, message: str, confirm: bool = False) -> dict[str, Any]:
    """Start a new forum discussion. Requires confirm=true after the student approved the exact message."""
    return actions.new_discussion(_c(), forum_id, subject, message, confirm)


# ---------- note ----------

@mcp.tool(annotations=READ)
def grades_overview() -> dict[str, Any]:
    """Overall course grades for every enrolled course."""
    return _list(activities.grades_overview(_c()))


@mcp.tool(annotations=READ)
def course_grades(course_id: int) -> dict[str, Any]:
    """Grade items (items, grades, ranges, percentages, feedback) for one course."""
    return _list(activities.course_grades(_c(), course_id))


# ---------- quizuri ----------

@mcp.tool(annotations=READ)
def list_quizzes(course_ids: list[int] | None = None) -> dict[str, Any]:
    """List quizzes with open/close times and attempt limits."""
    return _list(activities.list_quizzes(_c(), course_ids))


@mcp.tool(annotations=READ)
def quiz_attempts(quiz_id: int) -> dict[str, Any]:
    """The student's past attempts at a quiz with state and grades."""
    return _list(activities.quiz_attempts(_c(), quiz_id))


@mcp.tool(annotations=WRITE)
def quiz_start(quiz_id: int, force_new: bool = False, confirm: bool = False) -> dict[str, Any]:
    """Start (or resume) an attempt at a quiz. Counts against the attempt limit. Requires confirm=true."""
    return quiz.start_attempt(_c(), quiz_id, force_new, confirm)


@mcp.tool(annotations=READ)
def quiz_questions(attempt_id: int) -> dict[str, Any]:
    """Questions of an attempt. Each input has a name (use it as the answer key), a type (radio, checkbox,
    text, textarea, select) and options with value and label for choice inputs."""
    result = quiz.attempt_questions(_c(), attempt_id)
    result.pop("_sequencechecks", None)
    return result


@mcp.tool(annotations=WRITE)
def quiz_answer(
    attempt_id: int, answers: dict[str, str], finish: bool = False, confirm: bool = False
) -> dict[str, Any]:
    """Save answers to an attempt (finish=false) or submit it for grading (finish=true, irreversible).
    answers maps input name -> value, e.g. {"q123:1_answer": "2"} for a radio option value.
    Requires confirm=true after the student approved the answers."""
    return quiz.save_answers(_c(), attempt_id, answers, finish, confirm)


@mcp.tool(annotations=READ)
def quiz_review(attempt_id: int) -> dict[str, Any]:
    """Review of a finished attempt: questions, the answers given and the marks (raw Moodle data)."""
    return quiz.review_attempt(_c(), attempt_id)


# ---------- notificari, termene, API ----------

@mcp.tool(annotations=READ)
def notifications(limit: int = 20, unread_only: bool = False) -> dict[str, Any]:
    """Recent Moodle notifications (new content, grades, forum activity) and the unread count."""
    return activities.notifications(_c(), limit, unread_only)


@mcp.tool(annotations=WRITE)
def mark_notification_read(notification_id: int, confirm: bool = False) -> dict[str, Any]:
    """Mark a notification as read. Requires confirm=true."""
    return actions.mark_notification_read(_c(), notification_id, confirm)


@mcp.tool(annotations=READ)
def deadlines(days: int = 30) -> dict[str, Any]:
    """Upcoming deadlines and events in the next N days, sorted by time."""
    return _list(activities.deadlines(_c(), days))


@mcp.tool(annotations=READ)
def moodle_functions(pattern: str | None = None) -> dict[str, Any]:
    """List every Moodle Web Service function available to this token. Optional regex filter, e.g. 'forum|assign'."""
    return _list(activities.moodle_functions(_c(), pattern))


@mcp.tool(annotations=WRITE)
def moodle_call(function: str, params: dict[str, Any] | None = None, confirm: bool = False) -> Any:
    """Call ANY Moodle Web Service function with a params dict (nested dicts/lists are encoded like Moodle expects).
    Functions that are not read-only need confirm=true."""
    return actions.call_function(_c(), function, params or {}, confirm)


# ---------- prompturi (fluxuri gata) ----------

@mcp.prompt()
def weekly_brief() -> str:
    """Ce am de facut in saptamana asta: termene, notificari necitite, teme deschise."""
    return (
        "Use the ase-moodle tools: deadlines(days=7), notifications(limit=20, unread_only=true) and list_assignments(). "
        "Answer in Romanian with three short sections: termene in ordine, notificari noi (ce s-a schimbat), teme deschise. "
        "Do not write anything to Moodle."
    )


@mcp.prompt()
def prepare_assignment(assign_id: int) -> str:
    """Pregateste o tema: cerinta, stare, ciorne, si ce trebuie trimis."""
    return (
        f"Use assignment_status({assign_id}) and read the requirement (list_assignments). Explain the requirement in "
        "Romanian, the due date, whether drafts are enabled, and what is already submitted. Propose a plan. "
        "Do not submit anything until the student approves the exact file or text, then use confirm=true."
    )


@mcp.prompt()
def solve_quiz(quiz_id: int) -> str:
    """Raspunde la un quiz cu aprobarea studentului: intrebari, raspunsuri propuse, salvare, apoi trimitere."""
    return (
        f"Use quiz_attempts({quiz_id}) to see the state. If there is no attempt in progress, ask the student before "
        "quiz_start. Read the questions with quiz_questions(attempt_id). Show the proposed answers in a table first. "
        "After approval, save with quiz_answer(finish=false, confirm=true). Finish with finish=true only after a second "
        "explicit approval. Report the result in Romanian."
    )


@mcp.prompt()
def download_year(study_year: int, semester: int) -> str:
    """Descarca materialele unui an si semestru, apoi rezuma ce s-a descarcat."""
    return (
        f"Call download_materials(study_year={study_year}, semester={semester}) and then summarize the report in Romanian: "
        "courses downloaded, files, failures, and the folder path. Do not open or run any downloaded executable."
    )


# ---------- resurse (context citibil) ----------

@mcp.resource("moodle://me")
def resource_me() -> str:
    """Profilul studentului conectat."""
    return json.dumps(activities.whoami(_c()), ensure_ascii=False, indent=2)


@mcp.resource("moodle://deadlines")
def resource_deadlines() -> str:
    """Termenele din urmatoarele 14 zile."""
    return json.dumps(activities.deadlines(_c(), 14), ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> None:
    # Cu argumente, ase-moodle-mcp ruleaza CLI-ul: "ase-moodle-mcp login" = "ase-moodle login".
    # Fara argumente porneste serverul MCP. Clientii MCP nu trimit argumente.
    args = sys.argv[1:] if argv is None else argv
    if args:
        from .cli import main as cli_main

        raise SystemExit(cli_main(args))
    mcp.run()


if __name__ == "__main__":
    main()
