"""Descarcarea completa a unui curs: structura, fisiere, pagini, teme, forumuri, quizuri, note si date brute."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, TypeVar

from .activities import assign_status_summary, forum_discussions_all
from .client import MoodleClient, MoodleError
from .courses import Course
from .text import clean_filename, fmt_ts, html_to_text

T = TypeVar("T")

# Tip de modul -> functia Moodle care listeaza modulele de acel tip pentru mai multe cursuri.
MODULE_LISTERS: dict[str, str] = {
    "assign": "mod_assign_get_assignments",
    "forum": "mod_forum_get_forums_by_courses",
    "quiz": "mod_quiz_get_quizzes_by_courses",
    "page": "mod_page_get_pages_by_courses",
    "book": "mod_book_get_books_by_courses",
    "lesson": "mod_lesson_get_lessons_by_courses",
    "glossary": "mod_glossary_get_glossaries_by_courses",
    "wiki": "mod_wiki_get_wikis_by_courses",
    "data": "mod_data_get_databases_by_courses",
    "choice": "mod_choice_get_choices_by_courses",
    "feedback": "mod_feedback_get_feedbacks_by_courses",
    "survey": "mod_survey_get_surveys_by_courses",
    "workshop": "mod_workshop_get_workshops_by_courses",
    "h5pactivity": "mod_h5pactivity_get_h5pactivities_by_courses",
    "scorm": "mod_scorm_get_scorms_by_courses",
    "url": "mod_url_get_urls_by_courses",
    "folder": "mod_folder_get_folders_by_courses",
    "resource": "mod_resource_get_resources_by_courses",
    "label": "mod_label_get_labels_by_courses",
    "chat": "mod_chat_get_chats_by_courses",
    "imscp": "mod_imscp_get_imscps_by_courses",
    "lti": "mod_lti_get_ltis_by_courses",
}


class ModuleIndex:
    """Listele modulelor pentru mai multe cursuri, cu un singur apel per tip (cache in memorie)."""

    def __init__(self, client: MoodleClient, course_ids: list[int]):
        self.client = client
        self.course_ids = list(course_ids)
        self._cache: dict[str, dict[int, list[dict[str, Any]]]] = {}
        self.warnings: list[str] = []

    def items(self, modtype: str, course_id: int) -> list[dict[str, Any]]:
        if modtype not in self._cache:
            self._cache[modtype] = self._fetch(modtype)
        return self._cache[modtype].get(course_id, [])

    def _fetch(self, modtype: str) -> dict[int, list[dict[str, Any]]]:
        function = MODULE_LISTERS.get(modtype)
        if not function:
            return {}
        try:
            resp = self.client.call(function, {"courseids": self.course_ids})
        except MoodleError as exc:
            self.warnings.append(f"{modtype}: {exc}")
            return {}
        grouped: dict[int, list[dict[str, Any]]] = {}
        if modtype == "assign":
            for course in resp.get("courses", []):
                grouped[int(course["id"])] = list(course.get("assignments", []))
            return grouped
        payload = resp if isinstance(resp, list) else next(
            (v for k, v in resp.items() if k != "warnings" and isinstance(v, list)), []
        )
        for item in payload:
            if item.get("course") is not None:
                grouped.setdefault(int(item["course"]), []).append(item)
        return grouped

    def by_cmid(self, modtype: str, course_id: int, cmid: int) -> dict[str, Any] | None:
        for item in self.items(modtype, course_id):
            if int(item.get("coursemodule") or item.get("cmid") or 0) == cmid:
                return item
        return None


def _safe(report: dict[str, Any], label: str, fn: Callable[[], T], default: T) -> T:
    """Ruleaza fn; o eroare Moodle pe un element nu oprește descarcarea restului cursului."""
    try:
        return fn()
    except MoodleError as exc:
        report["warnings"].append(f"{label}: {exc}")
        return default


def _unique_target(folder: Path, filename: str, size: int | None) -> tuple[Path, bool]:
    """Returneaza (cale, exista_deja). Daca exista un fisier cu alt continut, adauga (2), (3)..."""
    base = clean_filename(filename)
    target = folder / base
    stem, suffix = os.path.splitext(base)
    counter = 2
    while target.exists():
        if size is None or target.stat().st_size == int(size):
            return target, True
        target = folder / f"{stem} ({counter}){suffix}"
        counter += 1
    return target, False


def _fetch_file(client: MoodleClient, item: dict[str, Any], folder: Path, report: dict[str, Any]) -> str:
    url = item.get("fileurl")
    if not url:
        return "fara URL"
    folder.mkdir(parents=True, exist_ok=True)
    target, exists = _unique_target(folder, item.get("filename") or "fisier", item.get("filesize"))
    if exists:
        report["skipped"] += 1
        return "exista deja"
    try:
        size = client.download(url, target)
    except MoodleError as exc:
        report["failed"].append(f"{target}: {exc}")
        return "ESUAT"
    report["downloaded"] += 1
    return f"{size // 1024} KB"


def _save_attachments(client: MoodleClient, items: list[dict[str, Any]], folder: Path, report: dict[str, Any]) -> list[str]:
    lines = []
    for item in items or []:
        status = _fetch_file(client, item, folder, report)
        lines.append(f"{item.get('filename')} ({status})")
    return lines


def _with_filepath(folder: Path, filepath: str | None) -> Path:
    if not filepath or filepath == "/":
        return folder
    for segment in filepath.strip("/").split("/"):
        if segment:
            folder = folder / clean_filename(segment)
    return folder


def _indent(text: str, prefix: str = "  ") -> str:
    return "\n".join(prefix + line if line else "" for line in text.splitlines())


def _write_assignments(client: MoodleClient, cdir: Path, cid: int, index: ModuleIndex, report: dict[str, Any]) -> bool:
    assigns = index.items("assign", cid)
    if not assigns:
        return False
    out = ["# Teme si evaluari", ""]
    for a in assigns:
        name = a.get("name") or f"tema-{a.get('id')}"
        status = _safe(
            report, f"stare tema {a.get('id')}",
            lambda a=a: assign_status_summary(client.call("mod_assign_get_submission_status", {"assignid": a["id"]})),
            None,
        )
        out.append(f"## {name}")
        out.append(f"- Deschidere: {fmt_ts(a.get('allowsubmissionsfromdate')) or '-'}")
        out.append(f"- Termen: {fmt_ts(a.get('duedate')) or '-'} | Limita: {fmt_ts(a.get('cutoffdate')) or '-'}")
        if status:
            out.append(f"- Stare trimitere: {status['status']} | Notare: {status['grading_status']} | Nota: {status['grade'] or '-'}")
            if status["files"]:
                out.append("- Fisiere trimise: " + ", ".join(f["filename"] for f in status["files"]))
            if status["text"]:
                out.append("- Text trimis: " + status["text"].replace("\n", " "))
            for comment in status["feedback_comments"]:
                out.append("- Feedback: " + comment.replace("\n", " "))
        intro = html_to_text(a.get("intro"))
        if intro:
            out += ["", "### Cerinta", intro]
        files = _save_attachments(client, a.get("introattachments") or [], cdir / "teme_fisiere" / clean_filename(name), report)
        if files:
            out.append("- Atasamente cerinta: " + "; ".join(files))
        out.append("")
    (cdir / "teme.md").write_text("\n".join(out), encoding="utf-8")
    return True


def _write_forums(client: MoodleClient, cdir: Path, cid: int, index: ModuleIndex, report: dict[str, Any]) -> list[str]:
    written = []
    for forum in index.items("forum", cid):
        fname = clean_filename(forum.get("name") or f"forum-{forum.get('id')}")
        discussions = _safe(
            report, f"forum {fname}",
            lambda f=forum: forum_discussions_all(client, int(f["id"])),
            [],
        )
        out = [f"# {forum.get('name')}", f"Tip: {forum.get('type')}", ""]
        for d in discussions:
            out.append(f"## {d.get('subject') or d.get('name')}")
            out.append(f"Autor: {d.get('userfullname')} | Data: {fmt_ts(d.get('created')) or '-'}")
            posts = _safe(
                report, f"postari {d.get('discussion')}",
                lambda d=d: client.call("mod_forum_get_discussion_posts", {"discussionid": d["discussion"]}).get("posts", []),
                [],
            )
            for p in posts:
                author = (p.get("author") or {}).get("fullname", "")
                out.append(f"### {p.get('subject') or ''} - {author} ({fmt_ts(p.get('timecreated')) or '-'})")
                out.append(html_to_text(p.get("message")))
                files = _save_attachments(client, p.get("attachments") or [], cdir / "forumuri" / "_fisiere" / fname, report)
                if files:
                    out.append("Atasamente: " + "; ".join(files))
                out.append("")
        target = cdir / "forumuri" / f"{fname}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(out), encoding="utf-8")
        written.append(str(target.relative_to(cdir)))
    return written


def _write_quizzes(client: MoodleClient, cdir: Path, cid: int, index: ModuleIndex, report: dict[str, Any]) -> bool:
    quizzes = index.items("quiz", cid)
    if not quizzes:
        return False
    out = ["# Quiz-uri", ""]
    for q in quizzes:
        attempts = _safe(
            report, f"incercari quiz {q.get('id')}",
            lambda q=q: client.call(
                "mod_quiz_get_user_attempts", {"quizid": q["id"], "userid": client.userid, "status": "all"}
            ).get("attempts", []),
            [],
        )
        out.append(f"## {q.get('name')}")
        out.append(f"Deschis: {fmt_ts(q.get('timeopen')) or '-'} | Inchis: {fmt_ts(q.get('timeclose')) or '-'}")
        out.append(f"Incercari permise: {q.get('attempts')} | Nota maxima: {q.get('sumgrades')}")
        intro = html_to_text(q.get("intro"))
        if intro:
            out.append(intro)
        for a in attempts:
            out.append(
                f"- Incercarea #{a.get('attempt')}: stare={a.get('state')} "
                f"nota_bruta={a.get('sumgrades')} terminata={fmt_ts(a.get('timefinish')) or '-'}"
            )
            if a.get("state") == "finished":
                review = _safe(
                    report, f"revizuire incercare {a.get('id')}",
                    lambda a=a: client.call("mod_quiz_get_attempt_review", {"attemptid": a["id"]}),
                    None,
                )
                if review:
                    raw_dir = cdir / "_raw"
                    raw_dir.mkdir(exist_ok=True)
                    (raw_dir / f"quiz_{q.get('id')}_incercare_{a.get('id')}.json").write_text(
                        json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
        out.append("")
    (cdir / "quizuri.md").write_text("\n".join(out), encoding="utf-8")
    return True


def _write_grades(client: MoodleClient, cdir: Path, cid: int, report: dict[str, Any]) -> bool:
    resp = _safe(
        report, "note",
        lambda: client.call("gradereport_user_get_grades_table", {"courseid": cid, "userid": client.userid}),
        None,
    )
    if not resp:
        return False
    raw_dir = cdir / "_raw"
    raw_dir.mkdir(exist_ok=True)
    (raw_dir / "note.json").write_text(json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8")
    out = ["# Note", ""]
    rows = 0
    for table in resp.get("tables", []):
        for row in table.get("tabledata", []):
            name = _cell_text(row, "itemname")
            if not name:
                continue
            rows += 1
            out.append(
                f"- {name} | nota: {_cell_text(row, 'grade') or '-'} | interval: {_cell_text(row, 'range') or '-'} "
                f"| procent: {_cell_text(row, 'percentage') or '-'} | feedback: {_cell_text(row, 'feedback') or '-'}"
            )
    if rows == 0:
        return False
    (cdir / "note.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    return True


def _cell_text(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    return html_to_text(value.get("content")) if isinstance(value, dict) else ""


def download_course(
    client: MoodleClient,
    course: Course,
    root: Path,
    index: ModuleIndex,
    deep: bool = True,
) -> dict[str, Any]:
    """Descarca un curs complet in root/<Materie - Tip>/. deep=False: doar structura si fisierele."""
    report: dict[str, Any] = {
        "course_id": course.id,
        "course": course.fullname,
        "study_year": course.study_year,
        "semester": course.semester,
        "tip": course.tip,
        "folder": None,
        "downloaded": 0,
        "skipped": 0,
        "failed": [],
        "warnings": [],
        "documents": [],
    }
    cdir = root / f"{clean_filename(course.name)} - {clean_filename(course.tip or 'ALTELE')}"
    cdir.mkdir(parents=True, exist_ok=True)
    report["folder"] = str(cdir)

    outline = client.call("core_course_get_contents", {"courseid": course.id})
    (cdir / "course.json").write_text(
        json.dumps({"course": course.to_dict(), "outline": outline}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    raw_dir = cdir / "_raw"
    for modtype in MODULE_LISTERS:
        items = index.items(modtype, course.id)
        if items:
            raw_dir.mkdir(exist_ok=True)
            (raw_dir / f"{modtype}.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# {course.fullname}",
        f"Moodle id={course.id} | an universitar {course.academic_year} | semestru {course.semester} | "
        f"anul de studiu {course.study_year or '?'} ({course.study_year_source or 'necunoscut'})",
    ]
    links: list[str] = []
    seen_urls: set[str] = set()
    for section in outline:
        sname = section.get("name") or f"Sectiunea {section.get('section', 0)}"
        sdir = cdir / clean_filename(sname)
        lines += ["", f"## {sname}"]
        section_summary = html_to_text(section.get("summary"))
        if section_summary:
            lines.append(section_summary)
        for mod in section.get("modules", []):
            modname = mod.get("modname", "?")
            mname = mod.get("name") or modname
            lines.append(f"- [{modname}] {mname}")
            description = html_to_text(mod.get("description"))
            if description:
                lines.append(_indent(description))
            folder = sdir / clean_filename(mname) if modname == "folder" else sdir
            for content in mod.get("contents") or []:
                ctype = content.get("type")
                if ctype == "url" and content.get("fileurl") not in seen_urls:
                    seen_urls.add(content["fileurl"])
                    links.append(f"{sname} | {mname} | {content['fileurl']}")
                    lines.append(f"  - link: {content['fileurl']}")
                elif ctype == "file":
                    fdir = _with_filepath(folder, content.get("filepath"))
                    status = _fetch_file(client, content, fdir, report)
                    lines.append(f"  - fisier: {content.get('filename')} ({status})")
            if modname == "page":
                page = index.by_cmid("page", course.id, int(mod.get("id", 0)))
                if page:
                    pdir = folder / "_fisiere" / clean_filename(mname)
                    page_text = html_to_text(page.get("content"))
                    target = folder / f"{clean_filename(mname)}.md"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(f"# {mname}\n\n{page_text}\n", encoding="utf-8")
                    lines.append(f"  - pagina salvata: {target.name}")
                    files = _save_attachments(client, page.get("contentfiles") or [], pdir, report)
                    for f in files:
                        lines.append(f"    - fisier pagina: {f}")
            if modname == "url":
                url_item = index.by_cmid("url", course.id, int(mod.get("id", 0)))
                external = (url_item or {}).get("externalurl")
                if external and external not in seen_urls:
                    seen_urls.add(external)
                    links.append(f"{sname} | {mname} | {external}")
                    lines.append(f"  - link: {external}")
    lines.append("")

    if links:
        (cdir / "linkuri.txt").write_text("\n".join(links) + "\n", encoding="utf-8")
        report["documents"].append("linkuri.txt")

    if deep:
        if _write_assignments(client, cdir, course.id, index, report):
            report["documents"].append("teme.md")
        report["documents"] += _write_forums(client, cdir, course.id, index, report)
        if _write_quizzes(client, cdir, course.id, index, report):
            report["documents"].append("quizuri.md")
        if _write_grades(client, cdir, course.id, report):
            report["documents"].append("note.md")

    (cdir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    report["documents"].insert(0, "index.md")
    return report


def download_materials(
    client: MoodleClient,
    courses: list[Course],
    root: Path,
    deep: bool = True,
) -> list[dict[str, Any]]:
    """Descarca mai multe cursuri. Scrie si root/_rezumat.json cu raportul complet."""
    root.mkdir(parents=True, exist_ok=True)
    index = ModuleIndex(client, [c.id for c in courses])
    reports = []
    for course in courses:
        reports.append(download_course(client, course, root, index, deep=deep))
    summary = {"root": str(root), "courses": reports, "warnings": index.warnings}
    (root / "_rezumat.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return reports
