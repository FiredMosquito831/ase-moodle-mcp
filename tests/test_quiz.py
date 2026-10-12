"""Teste pentru quizuri, fara retea: parsarea campurilor de raspuns si validarea raspunsurilor."""

import os
import unittest
from unittest import mock

from ase_moodle import actions, quiz

MULTICHOICE = """
<div class="que multichoice"><div class="qtext"><p>Care este capitala Romaniei?</p></div>
<div class="answer">
<div><input type="radio" name="q12:1_answer" value="0" id="q12:1_0"><label for="q12:1_0">Cluj</label></div>
<div><input type="radio" name="q12:1_answer" value="1" id="q12:1_1"><label for="q12:1_1">Bucuresti</label></div>
</div>
<input type="hidden" name="q12:1_:sequencecheck" value="3">
</div>
"""

SHORT_AND_SELECT = """
<div class="que shortanswer"><p>Scrie un numar</p>
<input type="text" name="q12:2_answer" size="10">
<select name="q12:3_answer"><option value="">Alege</option><option value="a">Varianta A</option></select>
<input type="hidden" name="q12:2_:sequencecheck" value="1">
</div>
"""


class FakeMoodle:
    """Simuleaza mod_quiz_get_attempt_data si mod_quiz_process_attempt."""

    userid = 1

    def __init__(self):
        self.calls = []

    def call(self, function, params=None):
        self.calls.append((function, params))
        if function == "mod_quiz_get_attempt_data":
            return {
                "attempt": {"state": "inprogress"},
                "questions": [
                    {"slot": 1, "type": "multichoice", "html": MULTICHOICE},
                    {"slot": 2, "type": "shortanswer", "html": SHORT_AND_SELECT},
                ],
                "nextpage": -1,
            }
        if function == "mod_quiz_process_attempt":
            return {"state": "inprogress", "warnings": []}
        raise AssertionError(f"functie neasteptata: {function}")


class ParseTests(unittest.TestCase):
    def test_radio_group_gets_options_with_labels(self):
        inputs, hidden = quiz.parse_inputs(MULTICHOICE)
        self.assertEqual(len(inputs), 1)
        radio = inputs[0]
        self.assertEqual(radio["name"], "q12:1_answer")
        self.assertEqual(radio["type"], "radio")
        self.assertEqual(radio["options"], [
            {"value": "0", "label": "Cluj"},
            {"value": "1", "label": "Bucuresti"},
        ])
        self.assertEqual(hidden, {"q12:1_:sequencecheck": "3"})

    def test_text_and_select_fields(self):
        inputs, hidden = quiz.parse_inputs(SHORT_AND_SELECT)
        by_name = {i["name"]: i for i in inputs}
        self.assertEqual(by_name["q12:2_answer"]["type"], "text")
        self.assertEqual(by_name["q12:3_answer"]["type"], "select")
        self.assertEqual(by_name["q12:3_answer"]["options"][1], {"value": "a", "label": "Varianta A"})
        self.assertEqual(hidden, {"q12:2_:sequencecheck": "1"})

    def test_empty_fragment(self):
        self.assertEqual(quiz.parse_inputs(None), ([], {}))


class StartTests(unittest.TestCase):
    def test_start_without_attempt_id_is_an_error_with_moodle_reason(self):
        class Closed(FakeMoodle):
            def call(self, function, params=None):
                if function == "mod_quiz_start_attempt":
                    return {"attempt": None, "warnings": [{"message": "Acest test nu este disponibil acum."}]}
                return super().call(function, params)

        from ase_moodle.client import MoodleError
        with self.assertRaises(MoodleError) as ctx:
            quiz.start_attempt(Closed(), 24292, confirm=True)
        self.assertIn("nu este disponibil", str(ctx.exception))

    def test_start_returns_attempt_id(self):
        class Opened(FakeMoodle):
            def call(self, function, params=None):
                if function == "mod_quiz_start_attempt":
                    return {"attempt": {"id": 555, "attempt": 1, "state": "inprogress"}, "warnings": []}
                return super().call(function, params)

        result = quiz.start_attempt(Opened(), 24292, confirm=True)
        self.assertEqual(result["attempt_id"], 555)


class AttemptTests(unittest.TestCase):
    def test_attempt_questions_lists_fields_and_text(self):
        result = quiz.attempt_questions(FakeMoodle(), 77)
        self.assertEqual(len(result["questions"]), 2)
        self.assertIn("capitala Romaniei", result["questions"][0]["text"])
        self.assertEqual(result["questions"][0]["inputs"][0]["name"], "q12:1_answer")

    def test_unknown_answer_name_is_rejected_before_submit(self):
        fake = FakeMoodle()
        with self.assertRaises(ValueError) as ctx:
            quiz.save_answers(fake, 77, {"q99:9_answer": "1"}, finish=False, confirm=True)
        self.assertIn("q12:1_answer", str(ctx.exception))
        self.assertNotIn("mod_quiz_process_attempt", [c[0] for c in fake.calls])

    def test_save_sends_answers_with_sequencecheck_and_no_finish(self):
        fake = FakeMoodle()
        result = quiz.save_answers(fake, 77, {"q12:1_answer": "1"}, finish=False, confirm=True)
        function, params = fake.calls[-1]
        self.assertEqual(function, "mod_quiz_process_attempt")
        self.assertEqual(params["attemptid"], 77)
        self.assertFalse(params["finishattempt"])
        data = {d["name"]: d["value"] for d in params["data"]}
        self.assertEqual(data["q12:1_answer"], "1")
        self.assertEqual(data["q12:1_:sequencecheck"], "3")
        self.assertEqual(data["q12:2_:sequencecheck"], "1")
        self.assertFalse(result["finished"])

    def test_finish_flag_is_passed_through(self):
        fake = FakeMoodle()
        result = quiz.save_answers(fake, 77, {"q12:1_answer": "0"}, finish=True, confirm=True)
        self.assertTrue(fake.calls[-1][1]["finishattempt"])
        self.assertTrue(result["finished"])

    def test_save_without_confirmation_is_refused(self):
        with mock.patch.dict(os.environ, {}):
            os.environ.pop(actions.AUTO_CONFIRM_ENV, None)
            with self.assertRaises(actions.NeedsConfirmation):
                quiz.save_answers(FakeMoodle(), 77, {"q12:1_answer": "1"}, finish=True, confirm=False)


if __name__ == "__main__":
    unittest.main()
