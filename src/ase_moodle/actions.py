"""Actiuni care scriu in contul Moodle. Cer confirm=True, cu exceptia cazului in care ASE_MOODLE_AUTO_CONFIRM=1."""

from __future__ import annotations

import html
import os
import re
from pathlib import Path
from typing import Any

from .activities import assignment_status
from .client import MoodleClient

AUTO_CONFIRM_ENV = "ASE_MOODLE_AUTO_CONFIRM"

READ_PATTERN = re.compile(r"(^|_)(get|view|search|can|is|list|data_for|check|count|fetch)(_|$)")


class NeedsConfirmation(RuntimeError):
    """Actiunea modifica contul; agentul trebuie sa ceara confirmarea utilizatorului."""


def auto_confirm() -> bool:
    return os.environ.get(AUTO_CONFIRM_ENV) == "1"


def is_read_only(function: str) -> bool:
    return bool(READ_PATTERN.search(function))


def require_confirm(confirm: bool, action: str) -> None:
    if confirm or auto_confirm():
        return
    raise NeedsConfirmation(
        f"Blocat: '{action}' modifica contul Moodle. Arata utilizatorului exact continutul si cere confirmare, "
        f"apoi reapeleaza cu confirm=true (sau seteaza {AUTO_CONFIRM_ENV}=1)."
    )


def text_to_html(text: str) -> str:
    parts = [part.strip() for part in text.split("\n\n") if part.strip()]
    return "".join("<p>" + html.escape(part).replace("\n", "<br>") + "</p>" for part in parts)


def submit_assignment_file(
    client: MoodleClient,
    assign_id: int,
    file_path: str,
    submit_for_grading: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Incarca un fisier la tema. Fara submit_for_grading ramane ciorna; cu el se trimite definitiv."""
    mode = "trimitere FINALA" if submit_for_grading else "salvare ciorna"
    require_confirm(confirm, f"{mode} fisier {Path(file_path).name} la tema {assign_id}")
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Fisierul nu exista: {path}")
    draft = client.upload(path)
    client.call("mod_assign_save_submission", {
        "assignmentid": assign_id,
        "plugindata": {"files_filemanager": draft["itemid"]},
    })
    if submit_for_grading:
        client.call("mod_assign_submit_for_grading", {"assignmentid": assign_id, "acceptsubmissionstatement": 1})
    return {
        "uploaded": draft.get("filename") or path.name,
        "submitted_for_grading": submit_for_grading,
        "status": assignment_status(client, assign_id),
    }


def submit_assignment_text(
    client: MoodleClient,
    assign_id: int,
    text: str,
    submit_for_grading: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    mode = "trimitere FINALA" if submit_for_grading else "salvare ciorna"
    require_confirm(confirm, f"{mode} text la tema {assign_id}")
    client.call("mod_assign_save_submission", {
        "assignmentid": assign_id,
        "plugindata": {"onlinetext_editor": {"text": text_to_html(text), "format": 1, "itemid": 0}},
    })
    if submit_for_grading:
        client.call("mod_assign_submit_for_grading", {"assignmentid": assign_id, "acceptsubmissionstatement": 1})
    return {"submitted_for_grading": submit_for_grading, "status": assignment_status(client, assign_id)}


def reply_to_post(client: MoodleClient, post_id: int, subject: str, message: str, confirm: bool = False) -> dict[str, Any]:
    require_confirm(confirm, f"raspuns pe forum la postarea {post_id}")
    return client.call("mod_forum_add_discussion_post", {
        "postid": post_id,
        "subject": subject,
        "message": text_to_html(message),
        "messageformat": 1,
    })


def new_discussion(client: MoodleClient, forum_id: int, subject: str, message: str, confirm: bool = False) -> dict[str, Any]:
    require_confirm(confirm, f"discutie noua pe forumul {forum_id}")
    return client.call("mod_forum_add_discussion", {
        "forumid": forum_id,
        "subject": subject,
        "message": text_to_html(message),
        "messageformat": 1,
    })


def mark_notification_read(client: MoodleClient, notification_id: int, confirm: bool = False) -> dict[str, Any]:
    require_confirm(confirm, f"marcare notificare {notification_id} ca citita")
    return client.call("core_message_mark_notification_read", {
        "notificationid": notification_id,
        "useridto": client.userid,
    })


def call_function(client: MoodleClient, function: str, params: dict[str, Any] | None = None, confirm: bool = False) -> Any:
    """Apel generic la orice functie Moodle. Functiile care nu par de citire cer confirm=True."""
    if not is_read_only(function):
        require_confirm(confirm, f"apel {function}")
    return client.call(function, params or {})
