"""Teste de integrare: CLI, client si logica completa, contra serverului Moodle FALS (date sintetice).

Nu atinge contul real si nu foloseste internetul. Tokenul e cel de test din fake_moodle.py.
"""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ase_moodle import actions, activities, auth, cli, materials, quiz
from ase_moodle.client import MoodleClient, MoodleError
from ase_moodle.courses import fetch_courses
from fake_moodle import TOKEN, FakeMoodle


def run_cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class IntegrationBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeMoodle().__enter__()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.env = mock.patch.dict(os.environ, {
            "ASE_MOODLE_URL": cls.fake.url,
            "ASE_MOODLE_TOKEN": TOKEN,
            "ASE_MOODLE_ENV_FILE": str(Path(cls.tmp.name) / "nu-exista.env"),
            "ASE_MOODLE_DOWNLOADS": str(Path(cls.tmp.name) / "downloads"),
        })
        cls.env.start()
        cls.client = MoodleClient(cls.fake.url, TOKEN)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.env.stop()
        cls.fake.__exit__(None, None, None)
        cls.tmp.cleanup()

    def setUp(self):
        # Fiecare test porneste cu o stare curata a serverului fals.
        from fake_moodle import _State
        self.fake.state = _State()
        self.workfile = Path(self.tmp.name) / "tema.txt"
        self.workfile.write_text("continut de test", encoding="utf-8")


class CliReadTests(IntegrationBase):
    def test_whoami(self):
        code, out, _ = run_cli("whoami")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["fullname"], "Student Test")

    def test_courses_filter_infers_missing_year_from_same_subject(self):
        code, out, _ = run_cli("courses", "--year", "3", "--sem", "1")
        self.assertEqual(code, 0)
        ids = sorted(c["id"] for c in json.loads(out))
        self.assertEqual(ids, [101, 102])

    def test_assignments_and_deadlines(self):
        code, out, _ = run_cli("assignments")
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)), 2)
        code, out, _ = run_cli("deadlines", "--days", "30")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)[0]["type"], "assign")

    def test_forum_discussion_and_posts(self):
        discussions = activities.forum_discussions(self.client, 401)
        self.assertEqual(discussions[0]["discussion_id"], 501)
        posts = activities.discussion_posts(self.client, 501)
        self.assertIn("Textul anuntului de test", posts[0]["message"])

    def test_grades(self):
        self.assertEqual(len(activities.grades_overview(self.client)), 3)
        rows = activities.course_grades(self.client, 101)
        self.assertEqual(rows[0]["item"], "Total curs")

    def test_notifications_unread_only(self):
        result = activities.notifications(self.client, limit=10, unread_only=True)
        self.assertEqual(result["unread_count"], 1)
        self.assertEqual([n["id"] for n in result["items"]], [9001])

    def test_wrong_token_is_a_clean_error(self):
        with MoodleClient(self.fake.url, "gresit") as bad:
            with self.assertRaises(MoodleError) as ctx:
                bad.call("core_webservice_get_site_info")
        self.assertEqual(ctx.exception.errorcode, "invalidtoken")

    def test_auth_status_with_env_token(self):
        result = auth.status()
        self.assertTrue(result["logged_in"])
        self.assertEqual(result["user"], "Student Test")


class DraftGuardTests(IntegrationBase):
    def test_direct_assignment_refuses_draft_save_with_no_side_effects(self):
        code, _, err = run_cli("submit", "202", str(self.workfile), "--yes")
        self.assertEqual(code, 1)
        self.assertIn("nu are ciorne", err)
        self.assertNotIn(202, self.fake.state.submissions)  # nimic trimis
        self.assertEqual(self.fake.state.uploads, {})        # nimic incarcat

    def test_text_draft_also_refused_on_direct_assignment(self):
        with self.assertRaises(actions.DirectSubmissionBlocked):
            actions.submit_assignment_text(self.client, 202, "text", confirm=True)
        self.assertNotIn(202, self.fake.state.submissions)

    def test_draft_saved_on_assignment_with_drafts(self):
        code, out, _ = run_cli("submit", "201", str(self.workfile), "--yes")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["status"]["status"], "draft")
        self.assertEqual(self.fake.state.submissions[201]["status"], "draft")

    def test_allow_direct_is_an_explicit_opt_in(self):
        code, out, _ = run_cli("submit", "202", str(self.workfile), "--yes", "--allow-direct")
        self.assertEqual(code, 0)
        self.assertEqual(self.fake.state.submissions[202]["status"], "submitted")

    def test_final_submission_is_allowed_without_allow_direct(self):
        code, out, _ = run_cli("submit", "202", str(self.workfile), "--yes", "--submit")
        self.assertEqual(code, 0)
        self.assertEqual(self.fake.state.submissions[202]["status"], "submitted")

    def test_write_without_confirmation_is_refused(self):
        code, _, err = run_cli("submit", "201", str(self.workfile))
        self.assertEqual(code, 2)
        self.assertIn("needs_confirmation", err)
        self.assertEqual(self.fake.state.uploads, {})

    def test_status_reports_drafts_flag(self):
        self.assertTrue(activities.assignment_status(self.client, 201)["drafts_enabled"])
        self.assertFalse(activities.assignment_status(self.client, 202)["drafts_enabled"])

    def test_empty_draft_clears_a_draft_submission(self):
        run_cli("submit", "201", str(self.workfile), "--yes")
        empty = self.client.call("core_files_get_unused_draft_itemid")["itemid"]
        self.client.call("mod_assign_save_submission", {"assignmentid": 201, "plugindata": {"files_filemanager": empty}})
        self.assertEqual(activities.assignment_status(self.client, 201)["files"], [])


class QuizTests(IntegrationBase):
    def test_full_quiz_flow_save_then_finish(self):
        started = quiz.start_attempt(self.client, 701, confirm=True)
        attempt = started["attempt_id"]
        questions = quiz.attempt_questions(self.client, attempt)
        radio = questions["questions"][0]["inputs"][0]
        self.assertEqual(radio["type"], "radio")
        self.assertEqual([o["label"] for o in radio["options"]], ["3", "4"])

        saved = quiz.save_answers(self.client, attempt, {radio["name"]: "1"}, finish=False, confirm=True)
        self.assertFalse(saved["finished"])
        self.assertEqual(self.fake.state.quiz_attempts[attempt]["state"], "inprogress")

        done = quiz.save_answers(self.client, attempt, {radio["name"]: "1"}, finish=True, confirm=True)
        self.assertTrue(done["finished"])
        self.assertEqual(self.fake.state.quiz_attempts[attempt]["state"], "finished")

    def test_unknown_answer_name_is_rejected_before_submit(self):
        attempt = quiz.start_attempt(self.client, 701, confirm=True)["attempt_id"]
        with self.assertRaises(ValueError):
            quiz.save_answers(self.client, attempt, {"q999:9_answer": "1"}, confirm=True)

    def test_quiz_cli_start_and_questions(self):
        code, out, _ = run_cli("quiz-start", "701", "--yes")
        self.assertEqual(code, 0)
        attempt = json.loads(out)["attempt_id"]
        code, out, _ = run_cli("quiz-questions", str(attempt))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["questions"][0]["type"], "multichoice")


class DownloadTests(IntegrationBase):
    def test_download_is_idempotent(self):
        courses = fetch_courses(self.client)
        root = Path(self.tmp.name) / "materiale"
        first = materials.download_materials(self.client, courses, root, deep=True)
        downloaded = sum(r["downloaded"] for r in first)
        self.assertGreaterEqual(downloaded, 1)
        self.assertEqual(sum(len(r["failed"]) for r in first), 0)
        self.assertTrue(any(p.name == "curs.txt" for p in root.rglob("curs.txt")))
        self.assertTrue((root / "_rezumat.json").exists())

        second = materials.download_materials(self.client, courses, root, deep=True)
        self.assertEqual(sum(r["downloaded"] for r in second), 0)
        self.assertGreaterEqual(sum(r["skipped"] for r in second), downloaded)

    def test_deep_download_writes_assignments_and_quiz_docs(self):
        courses = [c for c in fetch_courses(self.client) if c.id == 101]
        root = Path(self.tmp.name) / "deep"
        materials.download_materials(self.client, courses, root, deep=True)
        folder = next(root.glob("Materie Test - CURS"))
        self.assertTrue((folder / "teme.md").exists())
        self.assertTrue((folder / "quizuri.md").exists())
        self.assertTrue((folder / "note.md").exists())
        self.assertTrue((folder / "index.md").exists())


class NotificationWriteTests(IntegrationBase):
    def test_mark_read_sends_only_notificationid(self):
        code, out, _ = run_cli("read-notification", "9001", "--yes")
        self.assertEqual(code, 0)
        self.assertEqual(activities.notifications(self.client, limit=5, unread_only=True)["unread_count"], 0)

    def test_marking_an_already_read_notification_is_fine(self):
        code, _, _ = run_cli("read-notification", "9002", "--yes")
        self.assertEqual(code, 0)


class PolicyIntegrationTests(IntegrationBase):
    def test_read_tools_do_not_need_confirmation(self):
        code, _, _ = run_cli("notifications", "--limit", "3")
        self.assertEqual(code, 0)

    def test_moodle_call_write_needs_confirmation(self):
        code, _, err = run_cli("call", "mod_forum_add_discussion", "--json-params", '{"forumid": 401}')
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
