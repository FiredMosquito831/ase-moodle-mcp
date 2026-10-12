"""CLI pentru Moodle BL@ASE. Iesirea este JSON, ca sa poata fi citita de orice agent sau script."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import actions, activities, auth, install, materials, quiz
from .client import MoodleClient, MoodleError
from .config import DEFAULT_BASE_URL, SettingsError, download_root, load_settings, save_settings
from .courses import fetch_courses, filter_courses


def _client() -> MoodleClient:
    settings = load_settings()
    return MoodleClient(settings.base_url, settings.token)


def _out(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _read_text(args: argparse.Namespace) -> str:
    if args.text is not None:
        return args.text
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Lipseste textul: foloseste --text, --file sau pipe.")


def _answers(args: argparse.Namespace) -> dict[str, str]:
    if args.answers_file:
        return json.loads(Path(args.answers_file).read_text(encoding="utf-8"))
    if args.answers:
        return json.loads(args.answers)
    if not sys.stdin.isatty():
        return json.loads(sys.stdin.read() or "{}")
    raise SystemExit("Lipsesc raspunsurile: --answers JSON, --answers-file sau pipe.")


# ---------- cont si cursuri ----------

def cmd_login(args: argparse.Namespace) -> None:
    if args.token or args.token_stdin:
        token = args.token or sys.stdin.read().strip()
        with MoodleClient(args.base_url, token) as client:
            info = activities.whoami(client)
        path = save_settings(token, args.base_url)
        _out({"ok": True, "method": "token", "user": info["fullname"], "saved_to": str(path)})
        return
    _out(auth.authenticate(args.base_url, args.method, args.timeout))


def cmd_logout(args: argparse.Namespace) -> None:
    _out(auth.logout(args.forget_browser))


def cmd_auth_status(args: argparse.Namespace) -> None:
    _out(auth.status())


def cmd_whoami(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(activities.whoami(c))


def cmd_courses(args: argparse.Namespace) -> None:
    with _client() as c:
        courses = filter_courses(fetch_courses(c), args.year, args.sem, args.ay, args.tip, args.search)
        _out([
            {"id": x.id, "name": x.name, "tip": x.tip, "semester": x.semester, "academic_year": x.academic_year,
             "study_year": x.study_year, "study_year_source": x.study_year_source, "shortname": x.shortname}
            for x in courses
        ])


def cmd_outline(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(c.call("core_course_get_contents", {"courseid": args.course_id}))


def cmd_download(args: argparse.Namespace) -> None:
    root = Path(args.out).expanduser() if args.out else download_root()
    with _client() as c:
        courses = fetch_courses(c)
        if args.course:
            wanted = set(args.course)
            selected = [x for x in courses if x.id in wanted]
        else:
            selected = filter_courses(courses, args.year, args.sem, args.ay, args.tip)
        if not selected:
            raise SystemExit("Niciun curs nu se potriveste filtrelor.")
        reports = materials.download_materials(c, selected, root, deep=not args.shallow)
    _out({
        "root": str(root),
        "courses": len(reports),
        "downloaded": sum(r["downloaded"] for r in reports),
        "skipped": sum(r["skipped"] for r in reports),
        "failed": sum(len(r["failed"]) for r in reports),
        "reports": reports,
    })


# ---------- teme, forumuri, note ----------

def cmd_assignments(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(activities.list_assignments(c, args.course))


def cmd_assignment(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(activities.assignment_status(c, args.assign_id))


def cmd_submit(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(actions.submit_assignment_file(c, args.assign_id, args.file, args.submit, args.yes, args.allow_direct))


def cmd_submit_text(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(actions.submit_assignment_text(c, args.assign_id, _read_text(args), args.submit, args.yes, args.allow_direct))


def cmd_forums(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(activities.list_forums(c, args.course))


def cmd_forum(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(activities.forum_discussions(c, args.forum_id))


def cmd_discussion(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(activities.discussion_posts(c, args.discussion_id))


def cmd_reply(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(actions.reply_to_post(c, args.post_id, args.subject, _read_text(args), args.yes))


def cmd_new_discussion(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(actions.new_discussion(c, args.forum_id, args.subject, _read_text(args), args.yes))


def cmd_grades(args: argparse.Namespace) -> None:
    with _client() as c:
        if args.course:
            _out(activities.course_grades(c, args.course))
        else:
            _out(activities.grades_overview(c))


# ---------- quizuri ----------

def cmd_quizzes(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(activities.list_quizzes(c, args.course))


def cmd_quiz_attempts(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(activities.quiz_attempts(c, args.quiz_id))


def cmd_quiz_start(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(quiz.start_attempt(c, args.quiz_id, args.force_new, args.yes))


def cmd_quiz_questions(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(quiz.attempt_questions(c, args.attempt_id))


def cmd_quiz_answer(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(quiz.save_answers(c, args.attempt_id, _answers(args), args.finish, args.yes))


def cmd_quiz_review(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(quiz.review_attempt(c, args.attempt_id))


# ---------- notificari, termene, API ----------

def cmd_notifications(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(activities.notifications(c, args.limit, args.unread))


def cmd_read_notification(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(actions.mark_notification_read(c, args.notification_id, args.yes))


def cmd_deadlines(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(activities.deadlines(c, args.days))


def cmd_functions(args: argparse.Namespace) -> None:
    with _client() as c:
        _out(activities.moodle_functions(c, args.filter))


def cmd_call(args: argparse.Namespace) -> None:
    params = json.loads(args.json_params) if args.json_params else {}
    with _client() as c:
        _out(actions.call_function(c, args.function, params, args.yes))


# ---------- instalare ----------

def _install_env(args: argparse.Namespace) -> install.Env:
    project = Path(args.project_dir).expanduser().resolve() if getattr(args, "project_dir", None) else Path.cwd()
    return install.Env(source=args.source or install.default_source(), project_dir=project)


def cmd_install(args: argparse.Namespace) -> None:
    steps = install.install(args.targets, _install_env(args), args.scope)
    _out([s.to_dict() for s in steps])
    if any(s.status == "error" for s in steps):
        raise SystemExit(3)


def cmd_uninstall(args: argparse.Namespace) -> None:
    _out([s.to_dict() for s in install.uninstall(args.targets, _install_env(args), args.scope)])


def cmd_update(args: argparse.Namespace) -> None:
    steps = install.update(args.targets, _install_env(args), args.scope)
    _out([s.to_dict() for s in steps])
    if any(s.status == "error" for s in steps):
        raise SystemExit(3)


def cmd_doctor(args: argparse.Namespace) -> None:
    steps = install.doctor()
    _out([s.to_dict() for s in steps])
    if any(s.status == "error" for s in steps):
        raise SystemExit(3)


def cmd_sync_plugin(args: argparse.Namespace) -> None:
    root = install.repo_root()
    if root is None:
        raise SystemExit("Nu gasesc radacina repo-ului (ruleaza din sursa, cu pip install -e).")
    _out({"synced": str(install.sync_plugin_skill(root))})


# ---------- parser ----------

def _add_course_filters(p: argparse.ArgumentParser) -> None:
    p.add_argument("--year", type=int, help="anul de studiu (1, 2, 3...)")
    p.add_argument("--sem", type=int, help="semestrul (1 sau 2)")
    p.add_argument("--ay", help="an universitar, ex. 2026-2027")
    p.add_argument("--tip", help="CURS, SEMINAR sau LABORATOR")


def _add_answers(p: argparse.ArgumentParser) -> None:
    p.add_argument("--answers", help='JSON, ex. \'{"q1:1_answer": "2"}\'')
    p.add_argument("--answers-file", help="fisier JSON cu raspunsurile")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ase-moodle", description="Acces la Moodle BL@ASE (online.ase.ro)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("login", help="Obtine tokenul automat (browser) sau il salveaza din --token")
    p.add_argument("--method", choices=["auto", "browser", "manual"], default="auto",
                   help="auto: browser daca e Playwright, altfel manual (clipboard)")
    p.add_argument("--timeout", type=int, default=300, help="secunde de asteptare pentru login")
    p.add_argument("--token", help="salveaza direct un token existent")
    p.add_argument("--token-stdin", action="store_true", help="citeste tokenul din stdin")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("logout", help="Sterge tokenul salvat")
    p.add_argument("--forget-browser", action="store_true", help="sterge si profilul browserului (sesiunea Google)")
    p.set_defaults(func=cmd_logout)

    sub.add_parser("auth-status", help="Verifica daca tokenul salvat functioneaza").set_defaults(func=cmd_auth_status)

    sub.add_parser("whoami", help="Cine sunt conectat").set_defaults(func=cmd_whoami)

    p = sub.add_parser("courses", help="Listeaza cursurile inscrise")
    _add_course_filters(p)
    p.add_argument("--search")
    p.set_defaults(func=cmd_courses)

    p = sub.add_parser("outline", help="Structura cursului (JSON Moodle brut)")
    p.add_argument("course_id", type=int)
    p.set_defaults(func=cmd_outline)

    p = sub.add_parser("download", help="Descarca materialele si datele cursurilor")
    _add_course_filters(p)
    p.add_argument("--course", type=int, action="append", help="id curs (poate fi repetat)")
    p.add_argument("--out", help=f"folderul destinatie (implicit {download_root()})")
    p.add_argument("--shallow", action="store_true", help="doar structura si fisierele")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("assignments", help="Lista temelor")
    p.add_argument("--course", type=int, action="append")
    p.set_defaults(func=cmd_assignments)

    p = sub.add_parser("assignment", help="Cerinta si starea trimiterii pentru o tema")
    p.add_argument("assign_id", type=int)
    p.set_defaults(func=cmd_assignment)

    p = sub.add_parser("submit", help="Incarca un fisier la tema (ciorna sau final)")
    p.add_argument("assign_id", type=int)
    p.add_argument("file")
    p.add_argument("--submit", action="store_true", help="trimite definitiv (altfel ramane ciorna)")
    p.add_argument("--allow-direct", action="store_true", help="permite salvarea la teme fara ciorne (se trimite direct)")
    p.add_argument("--yes", action="store_true", help="confirmarea utilizatorului")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("submit-text", help="Trimite text ca raspuns la tema")
    p.add_argument("assign_id", type=int)
    p.add_argument("--text")
    p.add_argument("--file")
    p.add_argument("--submit", action="store_true")
    p.add_argument("--allow-direct", action="store_true")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_submit_text)

    p = sub.add_parser("forums", help="Lista forumurilor")
    p.add_argument("--course", type=int, action="append")
    p.set_defaults(func=cmd_forums)

    p = sub.add_parser("forum", help="Discutiile unui forum")
    p.add_argument("forum_id", type=int)
    p.set_defaults(func=cmd_forum)

    p = sub.add_parser("discussion", help="Postarile unei discutii")
    p.add_argument("discussion_id", type=int)
    p.set_defaults(func=cmd_discussion)

    p = sub.add_parser("reply", help="Raspunde la o postare de forum")
    p.add_argument("post_id", type=int)
    p.add_argument("--subject", required=True)
    p.add_argument("--text")
    p.add_argument("--file")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_reply)

    p = sub.add_parser("new-discussion", help="Deschide o discutie noua pe un forum")
    p.add_argument("forum_id", type=int)
    p.add_argument("--subject", required=True)
    p.add_argument("--text")
    p.add_argument("--file")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_new_discussion)

    p = sub.add_parser("grades", help="Notele: toate cursurile sau un curs")
    p.add_argument("--course", type=int)
    p.set_defaults(func=cmd_grades)

    p = sub.add_parser("quizzes", help="Lista quizurilor")
    p.add_argument("--course", type=int, action="append")
    p.set_defaults(func=cmd_quizzes)

    p = sub.add_parser("quiz-attempts", help="Incercarile tale la un quiz")
    p.add_argument("quiz_id", type=int)
    p.set_defaults(func=cmd_quiz_attempts)

    p = sub.add_parser("quiz-start", help="Porneste o incercare la un quiz")
    p.add_argument("quiz_id", type=int)
    p.add_argument("--force-new", action="store_true")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_quiz_start)

    p = sub.add_parser("quiz-questions", help="Intrebarile unei incercari, cu campurile de raspuns")
    p.add_argument("attempt_id", type=int)
    p.set_defaults(func=cmd_quiz_questions)

    p = sub.add_parser("quiz-answer", help="Salveaza raspunsuri (sau trimite cu --finish)")
    p.add_argument("attempt_id", type=int)
    _add_answers(p)
    p.add_argument("--finish", action="store_true", help="trimite definitiv incercarea")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_quiz_answer)

    p = sub.add_parser("quiz-review", help="Revizuirea unei incercari terminate")
    p.add_argument("attempt_id", type=int)
    p.set_defaults(func=cmd_quiz_review)

    p = sub.add_parser("notifications", help="Notificari")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--unread", action="store_true")
    p.set_defaults(func=cmd_notifications)

    p = sub.add_parser("read-notification", help="Marcheaza o notificare ca citita")
    p.add_argument("notification_id", type=int)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_read_notification)

    p = sub.add_parser("deadlines", help="Termene limita viitoare")
    p.add_argument("--days", type=int, default=30)
    p.set_defaults(func=cmd_deadlines)

    p = sub.add_parser("functions", help="Functiile Moodle disponibile pentru token")
    p.add_argument("--filter", help="regex, ex. 'forum|assign'")
    p.set_defaults(func=cmd_functions)

    p = sub.add_parser("call", help="Apel generic la orice functie Moodle")
    p.add_argument("function")
    p.add_argument("--json-params", help='parametrii ca JSON, ex. \'{"courseid": 77587}\'')
    p.add_argument("--yes", action="store_true", help="confirmare pentru functii care scriu")
    p.set_defaults(func=cmd_call)

    targets = {"nargs": "*", "choices": [*install.TARGETS, "all"], "metavar": "TARGET"}

    def add_scope(p: argparse.ArgumentParser, default: str, choices: list[str]) -> None:
        p.add_argument("--scope", choices=choices, default=default,
                       help="global: pentru tot calculatorul; project: doar folderul proiectului (Antigravity ramane global)")
        p.add_argument("--project-dir", help="folderul proiectului (implicit: folderul curent)")

    p = sub.add_parser("install", help="Configureaza pluginul in Claude Code, Codex, opencode si/sau Antigravity")
    p.add_argument("targets", **targets)
    p.add_argument("--source", help="sursa marketplace-ului: cale locala sau owner/repo (implicit: repo-ul local)")
    add_scope(p, "global", ["global", "project"])
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("uninstall", help="Elimina configurarea din CLI-urile alese")
    p.add_argument("targets", **targets)
    p.add_argument("--source", help="sursa folosita la instalare (pentru calea plugin-ului)")
    add_scope(p, "all", ["global", "project", "all"])
    p.set_defaults(func=cmd_uninstall)

    p = sub.add_parser("update", help="Actualizeaza pluginul in CLI-urile alese (marketplace + plugin)")
    p.add_argument("targets", **targets)
    p.add_argument("--source", help="sursa marketplace-ului (implicit: repo-ul local sau GitHub)")
    add_scope(p, "global", ["global", "project"])
    p.set_defaults(func=cmd_update)

    sub.add_parser("doctor", help="Verifica starea instalarii, tokenul si procesele MCP").set_defaults(func=cmd_doctor)
    sub.add_parser("sync-plugin", help="(dezvoltare) copiaza SKILL.md canonic in plugin").set_defaults(func=cmd_sync_plugin)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
        return 0
    except actions.NeedsConfirmation as exc:
        print(json.dumps({"error": "needs_confirmation", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except (MoodleError, SettingsError, auth.AuthError, actions.DirectSubmissionBlocked,
            FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
