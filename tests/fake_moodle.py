"""Server Moodle FALS pentru teste si pentru dezvoltare locala.

Imita endpoint-urile REST (webservice/rest/server.php), upload-ul de fisiere si pluginfile-urile, cu date SINTETICE.
Nu contine nimic real: nume inventate, cursuri inventate, token de test. Nu se conecteaza la internet.

Porneste manual:  python tests/fake_moodle.py --port 8765   (apoi foloseste .env.test)
In teste:         with FakeMoodle() as fake: fake.url
"""

from __future__ import annotations

import email.parser
import email.policy
import http.server
import json
import re
import threading
import time
import urllib.parse
from typing import Any

TOKEN = "fake-token-for-tests-only"
DAY = 86400

STUDENT = {"userid": 1, "fullname": "Student Test", "username": "student.test", "sitename": "Moodle Test", "release": "4.1 (fake)"}

COURSES = [
    {"id": 101, "shortname": "Materie-CURS Sem1 (2026-2027)", "fullname": "Materie Test, Tip-CURS, Sem-1, Zi (2026-2027)",
     "categoryname": "Licenta", "summary": "<p>Program Test / Anul 3 - 2026-2027</p>", "startdate": 1, "enddate": 2},
    {"id": 102, "shortname": "Materie-SEMINAR Sem1 (2026-2027)", "fullname": "Materie Test, Tip-SEMINAR, Sem-1, Zi (2026-2027)",
     "categoryname": "Licenta", "summary": "", "startdate": 1, "enddate": 2},
    {"id": 103, "shortname": "Alta-CURS Sem2 (2025-2026)", "fullname": "Alta Materie, Tip-CURS, Sem-2, Zi (2025-2026)",
     "categoryname": "Licenta", "summary": "<p>Program Test / Anul 2 - 2025-2026</p>", "startdate": 1, "enddate": 2},
]

FORUM_ID, DISCUSSION_ID, POST_ID = 401, 501, 601
QUIZ_ID, QUIZ_CMID = 701, 801
NOTIF_IDS = [9001, 9002]


def _now() -> int:
    return int(time.time())


def _assignment(aid: int, name: str, drafts: int, due_days: int) -> dict[str, Any]:
    return {
        "id": aid, "cmid": 300 + aid, "course": 101, "name": name, "intro": f"<p>Cerinta pentru {name}</p>",
        "submissiondrafts": drafts, "nosubmissions": 0, "requiresubmissionstatement": 0,
        "duedate": _now() + due_days * DAY, "cutoffdate": 0, "allowsubmissionsfromdate": _now() - 10 * DAY,
        "maxattempts": -1, "introattachments": [],
        "configs": [{"plugin": "file", "subtype": "assignsubmission", "name": "enabled", "value": "1"},
                    {"plugin": "comments", "subtype": "assignfeedback", "name": "enabled", "value": "1"}],
    }


class _State:
    def __init__(self) -> None:
        self.assignments = {
            201: _assignment(201, "Tema cu ciorne", drafts=1, due_days=5),
            202: _assignment(202, "Tema fara ciorne", drafts=0, due_days=5),
        }
        self.assign_course = {201: 101, 202: 101}
        self.submissions: dict[int, dict[str, Any]] = {}
        self.uploads: dict[int, dict[str, Any]] = {}
        self.next_itemid = 1000
        self.files = {"/pluginfile.php/1/mod_resource/content/1/curs.txt": b"Continut de test pentru curs.\n"}
        self.notifications = [
            {"id": NOTIF_IDS[0], "subject": "Materie Test conținut nou", "fullmessage": "Resursa noua.",
             "timecreated": _now() - DAY, "read": False, "component": "moodle", "eventtype": "coursecontentupdated",
             "contexturl": "https://example.invalid/mod/resource/view.php?id=1", "useridto": 1},
            {"id": NOTIF_IDS[1], "subject": "Materie Test notă", "fullmessage": "Ai o nota noua.",
             "timecreated": _now() - 2 * DAY, "read": True, "component": "moodle", "eventtype": "gradeupdated",
             "contexturl": "", "useridto": 1},
        ]
        self.quiz_attempts: dict[int, dict[str, Any]] = {}
        self.next_attempt = 900
        # Optional, pentru teste: functii care "nu exista" pe site (raspuns ca la o functie necunoscuta).
        self.missing_functions: set[str] = set()

    def new_itemid(self) -> int:
        self.next_itemid += 1
        return self.next_itemid


QUIZ_HTML = """
<div class="que multichoice"><div class="qtext"><p>Care este 2+2?</p></div>
<div class="answer">
<div><input type="radio" name="q{a}:1_answer" value="0" id="q{a}:1_0"><label for="q{a}:1_0">3</label></div>
<div><input type="radio" name="q{a}:1_answer" value="1" id="q{a}:1_1"><label for="q{a}:1_1">4</label></div>
</div>
<input type="hidden" name="q{a}:1_:sequencecheck" value="1"></div>
"""


def _to_nested(form: dict[str, str]) -> dict[str, Any]:
    """Transforma courseids[0]=1 / data[0][name]=x in structuri Python (dict si liste)."""
    root: dict[str, Any] = {}
    for key, value in form.items():
        parts = re.findall(r"[^\[\]]+", key)
        if not parts:
            continue
        node: Any = root
        for i, part in enumerate(parts):
            last = i == len(parts) - 1
            container_key: Any = int(part) if part.isdigit() else part
            if isinstance(node, list):
                while len(node) <= container_key:
                    node.append(None)
            if last:
                node[container_key] = value
            else:
                nxt_is_index = parts[i + 1].isdigit()
                if isinstance(node, dict) and container_key not in node:
                    node[container_key] = [] if nxt_is_index else {}
                elif isinstance(node, list) and node[container_key] is None:
                    node[container_key] = [] if nxt_is_index else {}
                node = node[container_key]
    return _listify(root)


def _listify(value: Any) -> Any:
    if isinstance(value, dict):
        converted = {k: _listify(v) for k, v in value.items()}
        if converted and all(isinstance(k, int) for k in converted):
            return [converted[k] for k in sorted(converted)]
        return converted
    if isinstance(value, list):
        return [_listify(v) for v in value]
    return value


class FakeMoodle:
    """Porneste serverul in fire separat. Context manager: `with FakeMoodle() as fake: fake.url`."""

    def __init__(self, port: int = 0) -> None:
        self.state = _State()
        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", port), _make_handler(self))
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "FakeMoodle":
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()

    # --- dispatch REST ---

    def call(self, fn: str, p: dict[str, Any]) -> Any:
        handler = None if fn in self.state.missing_functions else getattr(self, "_fn_" + fn, None)
        if handler is None:
            # Ca Moodle real: functia lipsa din external_functions -> dml_missing_record_exception / invalidrecord.
            raise _MoodleFault("invalidrecord", f"Functie neimplementata in fake: {fn}",
                               exception="dml_missing_record_exception")
        return handler(p)

    def _fn_core_webservice_get_site_info(self, p):
        return {**STUDENT, "functions": [{"name": n} for n in sorted(
            name[4:] for name in dir(self) if name.startswith("_fn_")) if n not in self.state.missing_functions],
            "lang": "ro"}

    def _fn_core_enrol_get_users_courses(self, p):
        return [{"id": c["id"]} for c in COURSES]

    def _fn_core_course_get_courses_by_field(self, p):
        wanted = {int(x) for x in str(p.get("value", "")).split(",") if x}
        return {"courses": [c for c in COURSES if c["id"] in wanted]}

    def _fn_core_course_get_contents(self, p):
        cid = int(p["courseid"])
        mods = [{"id": 301, "modname": "resource", "name": "Curs test", "description": "",
                 "contents": [{"type": "file", "filename": "curs.txt", "filepath": "/", "filesize": 30,
                               "fileurl": self.state_url("/pluginfile.php/1/mod_resource/content/1/curs.txt")}]},
                {"id": 302, "modname": "url", "name": "Link test", "contents": [{"type": "url", "fileurl": "https://example.invalid/curs"}]},
                {"id": 303, "modname": "label", "name": "Eticheta", "description": "<p>Informatie</p>"}]
        for aid, a in self.state.assignments.items():
            if self.state.assign_course[aid] == cid:
                mods.append({"id": a["cmid"], "modname": "assign", "name": a["name"], "instance": aid, "contents": []})
        if cid == 101:
            mods.append({"id": 402, "modname": "forum", "name": "Announcements", "contents": []})
            mods.append({"id": QUIZ_CMID, "modname": "quiz", "name": "Quiz test", "contents": []})
        return [{"id": 1, "section": 1, "name": "Saptamana 1", "summary": "", "modules": mods}]

    def _fn_mod_assign_get_assignments(self, p):
        out = []
        for cid in sorted({int(c) for c in _ids(p.get("courseids", []))}):
            items = [a for aid, a in self.state.assignments.items() if self.state.assign_course[aid] == cid]
            out.append({"id": cid, "shortname": f"course-{cid}", "assignments": items})
        return {"courses": out, "warnings": []}

    def _submission_block(self, aid: int) -> dict[str, Any]:
        sub = self.state.submissions.get(aid, {"status": "new", "files": []})
        return {
            "submission": {"status": sub["status"], "plugins": [{
                "type": "file", "name": "Trimitere de fisier",
                "fileareas": [{"area": "submission_files", "files": [
                    {"filename": f["filename"], "filesize": f["filesize"], "fileurl": f["fileurl"]} for f in sub["files"]]}],
            }]},
            "submissionsenabled": True, "canedit": True, "cansubmit": sub["status"] == "new",
            "locked": False, "gradingstatus": "notgraded", "extensionduedate": 0,
        }

    def _fn_mod_assign_get_submission_status(self, p):
        aid = int(p["assignid"])
        if aid not in self.state.assignments:
            raise _MoodleFault("invalidrecord", "Nu se poate găsi înregistrarea datelor în tabelul bazei de date assign.")
        return {"lastattempt": self._submission_block(aid), "feedback": {}, "assignmentdata": {}, "warnings": []}

    def _fn_core_files_get_unused_draft_itemid(self, p):
        return {"itemid": self.state.new_itemid()}

    def _fn_mod_assign_save_submission(self, p):
        aid = int(p["assignmentid"])
        if aid not in self.state.assignments:
            raise _MoodleFault("invalidrecord", "Nu se poate găsi înregistrarea datelor în tabelul bazei de date assign.")
        item = int(p.get("plugindata", {}).get("files_filemanager", 0) or 0)
        files = self.state.uploads.get(item, {}).get("files", [])
        if not files and self.state.submissions.get(aid, {}).get("status") == "submitted":
            return {"warnings": [{"item": "Nu a fost trimis nimic", "warningcode": "couldnotsavesubmission"}]}
        drafts = self.state.assignments[aid]["submissiondrafts"]
        status = "draft" if drafts else "submitted"
        self.state.submissions[aid] = {"status": status, "files": [
            {"filename": f["filename"], "filesize": f["filesize"], "fileurl": f["fileurl"]} for f in files]}
        return {"warnings": []}

    def _fn_mod_assign_submit_for_grading(self, p):
        aid = int(p["assignmentid"])
        self.state.submissions.setdefault(aid, {"status": "new", "files": []})["status"] = "submitted"
        return {"warnings": []}

    def _fn_mod_forum_get_forums_by_courses(self, p):
        return [{"id": FORUM_ID, "cmid": 402, "course": 101, "type": "news", "name": "Announcements", "numdiscussions": 1}]

    def _fn_mod_forum_get_forum_discussions_paginated(self, p):
        if int(p.get("forumid", 0)) != FORUM_ID:
            raise _MoodleFault("invalidparameter", "A fost detectată o valoare nevalidă a parametrului")
        return {"discussions": [{"id": POST_ID, "discussion": DISCUSSION_ID, "name": "Anunt", "subject": "Anunt",
                                 "userfullname": "Profesor Test", "created": _now() - DAY, "numreplies": 0,
                                 "numunread": 0, "pinned": False, "locked": False}]}

    def _fn_mod_forum_get_forum_discussions(self, p):  # Moodle 3.7+; singura varianta in 4.5
        return {"discussions": self._fn_mod_forum_get_forum_discussions_paginated(p)["discussions"], "warnings": []}

    def _fn_mod_forum_get_discussion_posts(self, p):
        if int(p.get("discussionid", 0)) != DISCUSSION_ID:
            raise _MoodleFault("invalidparameter", "A fost detectată o valoare nevalidă a parametrului")
        return {"posts": [{"id": POST_ID, "subject": "Anunt", "message": "<p>Textul anuntului de test.</p>",
                           "author": {"fullname": "Profesor Test"}, "timecreated": _now() - DAY,
                           "attachments": [], "capabilities": {"reply": True}}]}

    def _fn_gradereport_user_get_grades_table(self, p):
        return {"tables": [{"courseid": p.get("courseid"), "tabledata": [
            {"itemname": {"content": "Total curs"}, "grade": {"content": "-"}, "range": {"content": "0–100"},
             "percentage": {"content": "-"}, "feedback": {"content": ""}}]}]}

    def _fn_gradereport_overview_get_course_grades(self, p):
        return {"grades": [{"courseid": c["id"], "grade": "-", "rawgrade": ""} for c in COURSES]}

    def _fn_message_popup_get_popup_notifications(self, p):
        items = sorted(self.state.notifications, key=lambda n: -n["timecreated"])
        limit = int(p.get("limit", 20))
        unread = sum(1 for n in self.state.notifications if not n["read"])
        return {"notifications": [dict(n) for n in items[:limit]], "unreadcount": unread}

    def _fn_core_message_mark_notification_read(self, p):
        nid = int(p["notificationid"])
        if set(p) - {"notificationid"}:  # Moodle respinge parametrii necunoscuti (ex. useridto)
            raise _MoodleFault("invalidparameter", "A fost detectată o valoare nevalidă a parametrului")
        for n in self.state.notifications:
            if n["id"] == nid:
                n["read"] = True  # idempotent: marcarea unei notificari citite reuseste
                return {"notificationid": nid, "warnings": []}
        raise _MoodleFault("invalidparameter", "A fost detectată o valoare nevalidă a parametrului")

    def _fn_core_calendar_get_action_events_by_timesort(self, p):
        return {"events": [{"name": "Tema cu ciorne", "modulename": "assign", "timesort": _now() + 5 * DAY,
                            "course": {"shortname": "Materie-CURS"}, "url": "https://example.invalid/assign/201",
                            "overdue": False}], "firstid": 0, "lastid": 0}

    def _fn_mod_quiz_get_quizzes_by_courses(self, p):
        return {"quizzes": [{"id": QUIZ_ID, "coursemodule": QUIZ_CMID, "course": 101, "name": "Quiz test",
                             "timeopen": 0, "timeclose": _now() + 3 * DAY, "attempts": 0, "sumgrades": 10, "intro": ""}],
                "warnings": []}

    def _fn_mod_quiz_get_user_attempts(self, p):
        return {"attempts": [dict(a) for a in self.state.quiz_attempts.values()], "warnings": []}

    def _fn_mod_quiz_start_attempt(self, p):
        if int(p["quizid"]) != QUIZ_ID:
            raise _MoodleFault("invalidparameter", "quiz necunoscut")
        self.state.next_attempt += 1
        aid = self.state.next_attempt
        self.state.quiz_attempts[aid] = {"id": aid, "attempt": 1, "state": "inprogress", "sumgrades": None,
                                         "timestart": _now(), "timefinish": 0}
        return {"attempt": {"id": aid, "attempt": 1, "state": "inprogress"}, "warnings": []}

    def _fn_mod_quiz_get_attempt_data(self, p):
        aid = int(p["attemptid"])
        if aid not in self.state.quiz_attempts:
            raise _MoodleFault("nopermissions", "Cursul sau activitatea nu sunt accesibile.")
        return {"attempt": {"id": aid, "state": self.state.quiz_attempts[aid]["state"]},
                "questions": [{"slot": 1, "type": "multichoice", "html": QUIZ_HTML.replace("{a}", str(aid))}],
                "nextpage": -1, "warnings": []}

    def _fn_mod_quiz_process_attempt(self, p):
        aid = int(p["attemptid"])
        if aid not in self.state.quiz_attempts:
            raise _MoodleFault("nopermissions", "Cursul sau activitatea nu sunt accesibile.")
        allowed = {f"q{aid}:1_answer", f"q{aid}:1_:sequencecheck"}
        names = {item["name"] for item in (p.get("data") or [])}
        unknown = names - allowed
        if unknown:
            raise _MoodleFault("invalidparameter", f"Camp necunoscut: {sorted(unknown)}")
        finished = str(p.get("finishattempt", "0")) == "1"
        self.state.quiz_attempts[aid]["state"] = "finished" if finished else "inprogress"
        return {"state": self.state.quiz_attempts[aid]["state"], "warnings": []}

    def _fn_mod_quiz_get_attempt_review(self, p):
        return {"questions": [], "warnings": []}

    # --- helpers ---

    def state_url(self, path: str) -> str:
        return f"{self.url}{path}?forcedownload=1"


def _ids(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return list(value.values())
    return list(value or [])


class _MoodleFault(Exception):
    def __init__(self, errorcode: str, message: str, exception: str = "moodle_exception") -> None:
        super().__init__(message)
        self.errorcode = errorcode
        self.message = message
        self.exception = exception


def _make_handler(fake: FakeMoodle):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # tacem logurile HTTP
            return

        def _send(self, code: int, payload: Any, ctype: str = "application/json; charset=utf-8") -> None:
            body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length)
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/webservice/upload.php":
                return self._upload(body)
            if parsed.path == "/webservice/rest/server.php":
                form = dict(urllib.parse.parse_qsl(body.decode("utf-8"), keep_blank_values=True))
                return self._rest(form)
            self._send(404, {"exception": "moodle_exception", "errorcode": "notfound", "message": "not found"})

        def _rest(self, form: dict[str, str]) -> None:
            if form.get("wstoken") != TOKEN:
                return self._send(200, {"exception": "moodle_exception", "errorcode": "invalidtoken",
                                        "message": "Invalid token - token not found"})
            fn = form.get("wsfunction", "")
            params = _to_nested({k: v for k, v in form.items() if k not in ("wstoken", "wsfunction", "moodlewsrestformat")})
            try:
                result = fake.call(fn, params)
            except _MoodleFault as fault:
                return self._send(200, {"exception": fault.exception, "errorcode": fault.errorcode, "message": fault.message})
            self._send(200, result)

        def _upload(self, body: bytes) -> None:
            ctype = self.headers.get("Content-Type", "")
            msg = email.parser.BytesParser(policy=email.policy.default).parsebytes(
                f"Content-Type: {ctype}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body)
            fields: dict[str, Any] = {}
            for part in msg.iter_parts():
                name = part.get_param("name", header="content-disposition")
                fields[name] = part
            if fields.get("token") is None or fields["token"].get_content().strip() != TOKEN:
                return self._send(200, {"exception": "moodle_exception", "errorcode": "invalidtoken", "message": "Invalid token"})
            upload = fields.get("file_1")
            if upload is None:
                return self._send(200, {"exception": "moodle_exception", "errorcode": "nofile", "message": "fara fisier"})
            content = upload.get_payload(decode=True) or b""
            filename = upload.get_filename() or "fisier"
            itemid = fake.state.new_itemid()
            fileurl = f"{fake.url}/pluginfile.php/1/user/draft/{itemid}/{filename}"
            info = {"filename": filename, "filesize": len(content), "fileurl": fileurl, "itemid": itemid}
            fake.state.uploads[itemid] = {"files": [info]}
            fake.state.files[f"/pluginfile.php/1/user/draft/{itemid}/{filename}"] = content
            self._send(200, [info])

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            query = dict(urllib.parse.parse_qsl(parsed.query))
            if parsed.path.startswith("/pluginfile.php"):
                if query.get("token") not in (None, TOKEN):
                    return self._send(403, {"exception": "moodle_exception", "errorcode": "invalidtoken"})
                content = fake.state.files.get(parsed.path)
                if content is None:
                    return self._send(404, b"not found", "text/plain")
                return self._send(200, content, "application/octet-stream")
            self._send(404, b"not found", "text/plain")

    return Handler


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Server Moodle fals (date sintetice) pentru teste locale")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = FakeMoodle(args.port)
    server.__enter__()
    print(f"Fake Moodle pe {server.url} (token: {TOKEN}). Ctrl+C pentru oprire.")
    try:
        server._thread.join()
    except KeyboardInterrupt:
        server.__exit__(None, None, None)
