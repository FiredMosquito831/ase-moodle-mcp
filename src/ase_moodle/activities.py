"""Citire (read-only) pentru teme, forumuri, note, quizuri, notificari si termene limita."""

from __future__ import annotations

import time
from typing import Any

from .client import MoodleClient, MoodleError
from .courses import fetch_courses
from .text import fmt_ts, html_to_text


def whoami(client: MoodleClient) -> dict[str, Any]:
    info = client.siteinfo
    return {
        "fullname": info.get("fullname"),
        "userid": info.get("userid"),
        "username": info.get("username"),
        "site": info.get("sitename"),
        "moodle_release": info.get("release"),
        "available_functions": len(info.get("functions", [])),
    }


def _course_ids(client: MoodleClient, course_ids: list[int] | None) -> list[int]:
    if course_ids:
        return [int(c) for c in course_ids]
    return [c.id for c in fetch_courses(client)]


# ---------- Teme (assign) ----------

def assign_status_summary(resp: dict[str, Any]) -> dict[str, Any]:
    """Rezuma raspunsul mod_assign_get_submission_status: stare, fisiere trimise, text, feedback si nota."""
    last = resp.get("lastattempt") or {}
    submission = last.get("submission") or {}
    files: list[dict[str, Any]] = []
    text = None
    for plugin in submission.get("plugins") or []:
        for area in plugin.get("fileareas") or []:
            for f in area.get("files") or []:
                files.append({"filename": f.get("filename"), "size": f.get("filesize"), "url": f.get("fileurl")})
        for field in plugin.get("editorfields") or []:
            if field.get("text"):
                text = html_to_text(field.get("text"))
    feedback = resp.get("feedback") or {}
    comments = []
    for plugin in feedback.get("plugins") or []:
        for field in plugin.get("editorfields") or []:
            if field.get("text"):
                comments.append(html_to_text(field.get("text")))
    return {
        "status": submission.get("status"),
        "graded": last.get("graded"),
        "grading_status": last.get("gradingstatus"),
        "can_submit": last.get("cansubmit"),
        "locked": last.get("locked"),
        "extension_due": fmt_ts(last.get("extensionduedate")),
        "files": files,
        "text": text,
        "grade": (feedback.get("grade") or {}).get("gradefordisplay"),
        "feedback_comments": comments,
    }


def list_assignments(client: MoodleClient, course_ids: list[int] | None = None) -> list[dict[str, Any]]:
    resp = client.call("mod_assign_get_assignments", {"courseids": _course_ids(client, course_ids)})
    out = []
    for course in resp.get("courses", []):
        for a in course.get("assignments", []):
            types = list(dict.fromkeys(c.get("plugin") for c in a.get("configs") or [] if c.get("name") == "enabled" and str(c.get("value")) == "1"))
            out.append({
                "assign_id": a.get("id"),
                "course_id": course.get("id"),
                "course": course.get("shortname"),
                "name": a.get("name"),
                "due": fmt_ts(a.get("duedate")),
                "cutoff": fmt_ts(a.get("cutoffdate")),
                "opens": fmt_ts(a.get("allowsubmissionsfromdate")),
                "submission_types": types,
                "max_attempts": a.get("maxattempts"),
                "intro": html_to_text(a.get("intro")),
            })
    return out


def assignment_info(client: MoodleClient, assign_id: int) -> dict[str, Any]:
    """Setarile temei: are ciorne (drafts_enabled), termene, daca accepta trimiteri."""
    resp = client.call("mod_assign_get_assignments", {"courseids": _course_ids(client, None)})
    for course in resp.get("courses", []):
        for a in course.get("assignments", []):
            if int(a.get("id", -1)) == int(assign_id):
                return {
                    "assign_id": int(assign_id),
                    "course_id": course.get("id"),
                    "name": a.get("name"),
                    "drafts_enabled": bool(a.get("submissiondrafts")),
                    "no_submissions": bool(a.get("nosubmissions")),
                    "requires_statement": bool(a.get("requiresubmissionstatement")),
                    "due": fmt_ts(a.get("duedate")),
                }
    raise MoodleError(f"Tema {assign_id} nu apare printre cursurile tale.", function="mod_assign_get_assignments")


def assignment_status(client: MoodleClient, assign_id: int) -> dict[str, Any]:
    resp = client.call("mod_assign_get_submission_status", {"assignid": assign_id})
    info = assignment_info(client, assign_id)
    return {"assign_id": assign_id, "drafts_enabled": info["drafts_enabled"], **assign_status_summary(resp)}


# ---------- Forumuri ----------

def list_forums(client: MoodleClient, course_ids: list[int] | None = None) -> list[dict[str, Any]]:
    forums = client.call("mod_forum_get_forums_by_courses", {"courseids": _course_ids(client, course_ids)})
    return [
        {
            "forum_id": f.get("id"),
            "cmid": f.get("cmid"),
            "course_id": f.get("course"),
            "type": f.get("type"),
            "name": f.get("name"),
            "discussions": f.get("numdiscussions"),
        }
        for f in forums
    ]


def forum_discussions_all(client: MoodleClient, forum_id: int, perpage: int = 100) -> list[dict[str, Any]]:
    """Toate discutiile unui forum, pe pagini (mod_forum_get_forum_discussions_paginated)."""
    discussions: list[dict[str, Any]] = []
    for page in range(0, 200):
        resp = client.call(
            "mod_forum_get_forum_discussions_paginated",
            {"forumid": forum_id, "sortby": "timemodified", "sortdirection": "DESC", "page": page, "perpage": perpage},
        )
        batch = resp.get("discussions", [])
        discussions.extend(batch)
        if len(batch) < perpage:
            break
    return discussions


def forum_discussions(client: MoodleClient, forum_id: int) -> list[dict[str, Any]]:
    return [
        {
            "discussion_id": d.get("discussion"),
            "first_post_id": d.get("id"),
            "subject": d.get("subject") or d.get("name"),
            "author": d.get("userfullname"),
            "created": fmt_ts(d.get("created")),
            "replies": d.get("numreplies"),
            "unread": d.get("numunread"),
            "pinned": d.get("pinned"),
            "locked": d.get("locked"),
        }
        for d in forum_discussions_all(client, forum_id)
    ]


def discussion_posts(client: MoodleClient, discussion_id: int) -> list[dict[str, Any]]:
    resp = client.call("mod_forum_get_discussion_posts", {"discussionid": discussion_id})
    return [
        {
            "post_id": p.get("id"),
            "parent_id": p.get("parentid"),
            "subject": p.get("subject"),
            "author": (p.get("author") or {}).get("fullname"),
            "created": fmt_ts(p.get("timecreated")),
            "message": html_to_text(p.get("message")),
            "attachments": [{"filename": a.get("filename"), "url": a.get("fileurl")} for a in p.get("attachments") or []],
            "can_reply": (p.get("capabilities") or {}).get("reply"),
        }
        for p in resp.get("posts", [])
    ]


# ---------- Note ----------

def _cell(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if isinstance(value, dict):
        return html_to_text(value.get("content"))
    return ""


def course_grades(client: MoodleClient, course_id: int) -> list[dict[str, Any]]:
    resp = client.call("gradereport_user_get_grades_table", {"courseid": course_id, "userid": client.userid})
    rows = []
    for table in resp.get("tables", []):
        for row in table.get("tabledata", []):
            name = _cell(row, "itemname")
            if not name:
                continue
            rows.append({
                "item": name,
                "grade": _cell(row, "grade"),
                "range": _cell(row, "range"),
                "percentage": _cell(row, "percentage"),
                "feedback": _cell(row, "feedback"),
            })
    return rows


def grades_overview(client: MoodleClient) -> list[dict[str, Any]]:
    resp = client.call("gradereport_overview_get_course_grades", {"userid": client.userid})
    names = {c.id: c.name for c in fetch_courses(client)}
    return [
        {"course_id": g.get("courseid"), "course": names.get(int(g.get("courseid") or 0)), "grade": g.get("grade"), "raw": g.get("rawgrade")}
        for g in resp.get("grades", [])
    ]


# ---------- Quizuri (read-only; incercarile se fac in Moodle, nu aici) ----------

def list_quizzes(client: MoodleClient, course_ids: list[int] | None = None) -> list[dict[str, Any]]:
    resp = client.call("mod_quiz_get_quizzes_by_courses", {"courseids": _course_ids(client, course_ids)})
    return [
        {
            "quiz_id": q.get("id"),
            "cmid": q.get("coursemodule"),
            "course_id": q.get("course"),
            "name": q.get("name"),
            "opens": fmt_ts(q.get("timeopen")),
            "closes": fmt_ts(q.get("timeclose")),
            "attempts_allowed": q.get("attempts"),
            "max_grade": q.get("sumgrades"),
            "intro": html_to_text(q.get("intro")),
        }
        for q in resp.get("quizzes", [])
    ]


def quiz_attempts(client: MoodleClient, quiz_id: int) -> list[dict[str, Any]]:
    resp = client.call("mod_quiz_get_user_attempts", {"quizid": quiz_id, "userid": client.userid, "status": "all"})
    return [
        {
            "attempt_id": a.get("id"),
            "attempt": a.get("attempt"),
            "state": a.get("state"),
            "raw_grade": a.get("sumgrades"),
            "started": fmt_ts(a.get("timestart")),
            "finished": fmt_ts(a.get("timefinish")),
        }
        for a in resp.get("attempts", [])
    ]


# ---------- Notificari si termene ----------

def notifications(client: MoodleClient, limit: int = 20, unread_only: bool = False) -> dict[str, Any]:
    fetch = max(limit, 100) if unread_only else limit
    resp = client.call(
        "message_popup_get_popup_notifications",
        {"useridto": client.userid, "newestfirst": 1, "limit": fetch},
    )
    items = []
    for n in resp.get("notifications", []):
        if unread_only and n.get("read"):
            continue
        items.append({
            "id": n.get("id"),
            "subject": n.get("subject"),
            "text": html_to_text(n.get("fullmessagehtml") or n.get("fullmessage")),
            "created": fmt_ts(n.get("timecreated")),
            "read": bool(n.get("read")),
            "component": n.get("component"),
            "event": n.get("eventtype"),
            "url": n.get("contexturl"),
        })
        if len(items) >= limit:
            break
    return {"unread_count": resp.get("unreadcount"), "items": items}


def deadlines(client: MoodleClient, days: int = 30) -> list[dict[str, Any]]:
    now = int(time.time())
    resp = client.call(
        "core_calendar_get_action_events_by_timesort",
        {"timesortfrom": now, "timesortto": now + days * 86400, "limitnum": 50},
    )
    out = []
    for e in resp.get("events", []):
        course = e.get("course") or {}
        out.append({
            "name": e.get("name"),
            "course": course.get("shortname") if isinstance(course, dict) else None,
            "type": e.get("modulename"),
            "due": fmt_ts(e.get("timesort")),
            "overdue": e.get("overdue"),
            "url": e.get("url") or e.get("viewurl"),
        })
    return out


# ---------- Descoperire API ----------

def moodle_functions(client: MoodleClient, pattern: str | None = None) -> list[str]:
    import re

    names = client.available_functions()
    if pattern:
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            raise MoodleError(f"Expresie invalida: {exc}") from exc
        names = [n for n in names if regex.search(n)]
    return names
