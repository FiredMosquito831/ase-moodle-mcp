"""Server MCP (stdio) pentru Moodle BL@ASE. Functioneaza cu Claude Code, Codex, opencode, Antigravity si orice client MCP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import actions, activities, materials, quiz
from .client import MoodleClient
from .config import download_root, load_settings
from .courses import fetch_courses, filter_courses

mcp = FastMCP(
    "ase-moodle",
    instructions=(
        "Access to the student's Moodle (BL@ASE, online.ase.ro). Read tools are safe to use whenever the student asks. "
        "Write tools (submit_*, reply_to_post, new_discussion, mark_notification_read, quiz_start, quiz_answer, "
        "moodle_call for non-read functions) require confirm=true. Set confirm=true only after the student approved "
        "the exact content in this conversation. Quizzes may be answered for the student: read the questions with "
        "quiz_questions, save answers with quiz_answer(finish=false), and finish only after approval."
    ),
)

_client: MoodleClient | None = None


def _c() -> MoodleClient:
    global _client
    if _client is None:
        settings = load_settings()
        _client = MoodleClient(settings.base_url, settings.token)
    return _client


@mcp.tool()
def whoami() -> dict[str, Any]:
    """Show the logged-in student, site name and the number of Web Service functions available."""
    return activities.whoami(_c())


@mcp.tool()
def list_courses(
    study_year: int | None = None,
    semester: int | None = None,
    academic_year: str | None = None,
    tip: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """List enrolled courses. Filters: study_year (1,2,3), semester (1,2), academic_year ('2026-2027'),
    tip ('CURS', 'SEMINAR', 'LABORATOR'), search (substring of the course name)."""
    courses = filter_courses(fetch_courses(_c()), study_year, semester, academic_year, tip, search)
    return [c.to_dict() for c in courses]


@mcp.tool()
def course_outline(course_id: int) -> list[dict[str, Any]]:
    """Raw course structure: sections, modules (activities, resources, labels), contents and file URLs."""
    return _c().call("core_course_get_contents", {"courseid": course_id})


@mcp.tool()
def download_materials(
    course_ids: list[int] | None = None,
    study_year: int | None = None,
    semester: int | None = None,
    out_dir: str | None = None,
    deep: bool = True,
) -> dict[str, Any]:
    """Download courses to disk: files, pages, assignments (teme.md), forums, quizzes, grades, links, raw JSON.
    Select courses by course_ids or by study_year/semester. deep=False skips assignments/forums/quizzes/grades."""
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


@mcp.tool()
def list_assignments(course_ids: list[int] | None = None) -> list[dict[str, Any]]:
    """List assignments (teme) with due dates, submission types and instructions."""
    return activities.list_assignments(_c(), course_ids)


@mcp.tool()
def assignment_status(assign_id: int) -> dict[str, Any]:
    """Submission status for an assignment: submitted files/text, grade, feedback comments."""
    return activities.assignment_status(_c(), assign_id)


@mcp.tool()
def submit_assignment_file(
    assign_id: int, file_path: str, submit_for_grading: bool = False, confirm: bool = False
) -> dict[str, Any]:
    """Upload a local file as the assignment submission. Replaces the previous draft file.
    submit_for_grading=False saves a draft; True sends it for grading (final). Requires confirm=true."""
    return actions.submit_assignment_file(_c(), assign_id, file_path, submit_for_grading, confirm)


@mcp.tool()
def submit_assignment_text(
    assign_id: int, text: str, submit_for_grading: bool = False, confirm: bool = False
) -> dict[str, Any]:
    """Write the online-text submission for an assignment. Requires confirm=true."""
    return actions.submit_assignment_text(_c(), assign_id, text, submit_for_grading, confirm)


@mcp.tool()
def list_forums(course_ids: list[int] | None = None) -> list[dict[str, Any]]:
    """List forums (including the 'news' Announcements forum) of the given or all courses."""
    return activities.list_forums(_c(), course_ids)


@mcp.tool()
def forum_discussions(forum_id: int) -> list[dict[str, Any]]:
    """All discussions of a forum with their ids, authors, dates and reply counts."""
    return activities.forum_discussions(_c(), forum_id)


@mcp.tool()
def discussion_posts(discussion_id: int) -> list[dict[str, Any]]:
    """All posts of a forum discussion, with text and attachments."""
    return activities.discussion_posts(_c(), discussion_id)


@mcp.tool()
def reply_to_post(post_id: int, subject: str, message: str, confirm: bool = False) -> dict[str, Any]:
    """Reply to a forum post. Requires confirm=true after the user approved the exact message."""
    return actions.reply_to_post(_c(), post_id, subject, message, confirm)


@mcp.tool()
def new_discussion(forum_id: int, subject: str, message: str, confirm: bool = False) -> dict[str, Any]:
    """Start a new forum discussion. Requires confirm=true after the user approved the exact message."""
    return actions.new_discussion(_c(), forum_id, subject, message, confirm)


@mcp.tool()
def grades_overview() -> dict[str, Any]:
    """Overall course grades for every enrolled course."""
    return {"grades": activities.grades_overview(_c())}


@mcp.tool()
def course_grades(course_id: int) -> list[dict[str, Any]]:
    """Grade items (items, grades, ranges, percentages, feedback) for one course."""
    return activities.course_grades(_c(), course_id)


@mcp.tool()
def list_quizzes(course_ids: list[int] | None = None) -> list[dict[str, Any]]:
    """List quizzes with open/close times and attempt limits."""
    return activities.list_quizzes(_c(), course_ids)


@mcp.tool()
def quiz_attempts(quiz_id: int) -> list[dict[str, Any]]:
    """The student's past attempts at a quiz with state and grades."""
    return activities.quiz_attempts(_c(), quiz_id)


@mcp.tool()
def quiz_start(quiz_id: int, force_new: bool = False, confirm: bool = False) -> dict[str, Any]:
    """Start (or resume) an attempt at a quiz. Counts against the attempt limit. Requires confirm=true."""
    return quiz.start_attempt(_c(), quiz_id, force_new, confirm)


@mcp.tool()
def quiz_questions(attempt_id: int) -> dict[str, Any]:
    """Questions of an attempt. Each input has a name (use it as the answer key), a type (radio, checkbox,
    text, textarea, select) and options with value and label for choice inputs."""
    return quiz.attempt_questions(_c(), attempt_id)


@mcp.tool()
def quiz_answer(
    attempt_id: int, answers: dict[str, str], finish: bool = False, confirm: bool = False
) -> dict[str, Any]:
    """Save answers to an attempt (finish=false) or submit it for grading (finish=true, irreversible).
    answers maps input name -> value, e.g. {"q123:1_answer": "2"} for a radio option value.
    Requires confirm=true after the student approved the answers."""
    return quiz.save_answers(_c(), attempt_id, answers, finish, confirm)


@mcp.tool()
def quiz_review(attempt_id: int) -> dict[str, Any]:
    """Review of a finished attempt: questions, the answers given and the marks (raw Moodle data)."""
    return quiz.review_attempt(_c(), attempt_id)


@mcp.tool()
def notifications(limit: int = 20, unread_only: bool = False) -> dict[str, Any]:
    """Recent Moodle notifications (new content, grades, forum activity) and the unread count."""
    return activities.notifications(_c(), limit, unread_only)


@mcp.tool()
def mark_notification_read(notification_id: int, confirm: bool = False) -> dict[str, Any]:
    """Mark a notification as read. Requires confirm=true."""
    return actions.mark_notification_read(_c(), notification_id, confirm)


@mcp.tool()
def deadlines(days: int = 30) -> list[dict[str, Any]]:
    """Upcoming deadlines and events in the next N days, sorted by time."""
    return activities.deadlines(_c(), days)


@mcp.tool()
def moodle_functions(pattern: str | None = None) -> list[str]:
    """List every Moodle Web Service function available to this token. Optional regex filter, e.g. 'forum|assign'."""
    return activities.moodle_functions(_c(), pattern)


@mcp.tool()
def moodle_call(function: str, params: dict[str, Any] | None = None, confirm: bool = False) -> Any:
    """Call ANY Moodle Web Service function with a params dict (nested dicts/lists are encoded like Moodle expects).
    Functions that are not read-only need confirm=true."""
    return actions.call_function(_c(), function, params or {}, confirm)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
