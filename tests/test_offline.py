"""Teste offline (fara retea): parsing, codificare parametri, politica de confirmare."""

import os
import unittest
from unittest import mock

from ase_moodle import actions
from ase_moodle.client import MoodleClient, flatten_params
from ase_moodle.courses import Course, _infer_missing_years, filter_courses, parse_course
from ase_moodle.text import clean_filename, html_to_text


class FakeClient:
    """Inlocuieste MoodleClient: orice apel de retea esueaza, ca sa dovedim ca blocarile au loc inainte."""

    userid = 1

    def call(self, *args, **kwargs):
        raise AssertionError("Nu trebuia sa ajunga la retea")


RAW_TEMA = {
    "id": 77497,
    "shortname": "Cibernetica-SEMINAR Sem1(601072)(2026-2027) 99535",
    "fullname": "Cibernetica sistemelor economice, Tip-SEMINAR, Sem-1, Zi (2026-2027)",
    "categoryname": "Licenta",
    "summary": "<p>CIBERNETICĂ / Informatică economică-Engleză / Anul 3 - 2026-2027<br /></p>",
    "startdate": 1790542800,
    "enddate": 1802556000,
}


class ParsingTests(unittest.TestCase):
    def test_parse_course_reads_year_semester_type_and_study_year(self):
        course = parse_course(RAW_TEMA)
        self.assertEqual(course.name, "Cibernetica sistemelor economice")
        self.assertEqual(course.tip, "SEMINAR")
        self.assertEqual(course.semester, 1)
        self.assertEqual(course.academic_year, "2026-2027")
        self.assertEqual(course.study_year, 3)
        self.assertEqual(course.study_year_source, "descriere")

    def test_legacy_tip_letters_are_normalized(self):
        raw = dict(RAW_TEMA, fullname="Bazele ciberneticii economice, Tip-C, Sem-2, Zi (2024-2025)", summary="")
        course = parse_course(raw)
        self.assertEqual(course.tip, "CURS")
        self.assertIsNone(course.study_year)

    def test_missing_study_year_is_inferred_from_same_subject(self):
        with_year = parse_course(RAW_TEMA)
        without = parse_course(dict(RAW_TEMA, id=1, fullname="Cibernetica sistemelor economice, Tip-CURS, Sem-1, Zi (2026-2027)", summary=""))
        courses = [with_year, without]
        _infer_missing_years(courses)
        self.assertEqual(courses[1].study_year, 3)
        self.assertEqual(courses[1].study_year_source, "dedus din aceeasi materie")

    def test_filter_by_year_semester_and_tip(self):
        a = parse_course(RAW_TEMA)
        b = Course(**{**a.to_dict(), "id": 2, "tip": "CURS"})
        c = Course(**{**a.to_dict(), "id": 3, "study_year": 2})
        self.assertEqual([x.id for x in filter_courses([a, b, c], study_year=3, semester=1)], [77497, 2])
        self.assertEqual([x.id for x in filter_courses([a, b, c], tip="curs")], [2])
        self.assertEqual([x.id for x in filter_courses([a, b, c], tip="C")], [2])


class EncodingTests(unittest.TestCase):
    def test_nested_params_are_flattened_like_moodle_expects(self):
        flat = flatten_params({
            "courseids": [77587, 73445],
            "plugindata": {"onlinetext_editor": {"text": "salut", "format": 1}},
            "acceptsubmissionstatement": True,
            "skip": None,
        })
        self.assertEqual(flat["courseids[0]"], "77587")
        self.assertEqual(flat["courseids[1]"], "73445")
        self.assertEqual(flat["plugindata[onlinetext_editor][text]"], "salut")
        self.assertEqual(flat["plugindata[onlinetext_editor][format]"], "1")
        self.assertEqual(flat["acceptsubmissionstatement"], "1")
        self.assertNotIn("skip", flat)

    def test_list_of_objects_uses_moodle_data_array_form(self):
        flat = flatten_params({"data": [{"name": "q1:1_answer", "value": "2"}]})
        self.assertEqual(flat["data[0][name]"], "q1:1_answer")
        self.assertEqual(flat["data[0][value]"], "2")

    def test_client_construction_does_not_touch_network(self):
        with MoodleClient("https://example.invalid/", "t") as client:
            self.assertEqual(client.base_url, "https://example.invalid")


class TextTests(unittest.TestCase):
    def test_html_links_keep_their_url(self):
        text = html_to_text('<p>Vezi <a href="https://x.ro/a">aici</a></p><script>x()</script>')
        self.assertEqual(text, "Vezi aici (https://x.ro/a)")

    def test_filenames_are_windows_safe(self):
        self.assertEqual(clean_filename('a/b:c*d?"e<f>g|h.'), "a_b_c_d__e_f_g_h")
        self.assertEqual(clean_filename(""), "_")


class PolicyTests(unittest.TestCase):
    def test_write_without_confirm_is_refused_before_network(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(actions.AUTO_CONFIRM_ENV, None)
            with self.assertRaises(actions.NeedsConfirmation):
                actions.reply_to_post(FakeClient(), 1, "s", "m", confirm=False)
            with self.assertRaises(actions.NeedsConfirmation):
                actions.submit_assignment_text(FakeClient(), 1, "text", confirm=False)
            with self.assertRaises(actions.NeedsConfirmation):
                actions.call_function(FakeClient(), "mod_forum_add_discussion_post", {}, confirm=False)

    def test_auto_confirm_env_disables_the_gate(self):
        with mock.patch.dict(os.environ, {actions.AUTO_CONFIRM_ENV: "1"}):
            self.assertTrue(actions.auto_confirm())
            with self.assertRaises(AssertionError):  # a ajuns la retea (fals client), deci gate-ul a trecut
                actions.call_function(FakeClient(), "mod_forum_add_discussion_post", {}, confirm=False)

    def test_read_functions_are_classified_as_read_only(self):
        for name in ("core_webservice_get_site_info", "mod_forum_get_discussion_posts",
                     "message_popup_get_popup_notifications", "tool_lp_data_for_plan_page",
                     "mod_quiz_get_attempt_data", "mod_quiz_get_attempt_review"):
            self.assertTrue(actions.is_read_only(name), name)
        for name in ("mod_assign_save_submission", "mod_forum_add_discussion_post",
                     "core_message_send_instant_messages", "mod_quiz_start_attempt", "mod_quiz_process_attempt"):
            self.assertFalse(actions.is_read_only(name), name)

    def test_quiz_functions_are_no_longer_blocked(self):
        # Politica noua: quizurile se pot raspunde; doar gate-ul de confirmare ramane.
        with mock.patch.dict(os.environ, {actions.AUTO_CONFIRM_ENV: "1"}):
            with self.assertRaises(AssertionError):  # ajunge la client, nu e blocat de politica
                actions.call_function(FakeClient(), "mod_quiz_start_attempt", {"quizid": 1}, confirm=False)


if __name__ == "__main__":
    unittest.main()
