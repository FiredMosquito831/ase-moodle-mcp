"""Contract: lista din ase_moodle/functions.py contine exact functiile Moodle folosite in cod (fara retea)."""

import re
import unittest
from pathlib import Path

import ase_moodle
from ase_moodle.functions import OPTIONAL_FUNCTIONS, REQUIRED_FUNCTIONS, missing_functions

SRC = Path(ase_moodle.__file__).resolve().parent
# Literal de tip sir care incepe cu un prefix de componenta Moodle: core_, mod_, tool_, gradereport_, message_...
NAME = re.compile(
    r"""["']((?:core|mod|tool|gradereport|message|block|report|enrol|local|auth|qbank|qtype|theme|editor|filter)_[a-z0-9_]*[a-z0-9])["']"""
)


def referenced_functions() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(SRC.rglob("*.py")):
        if path.name == "functions.py" and path.parent == SRC:
            continue  # lista insasi
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for name in NAME.findall(line):
                found.setdefault(name, []).append(f"{path.relative_to(SRC).as_posix()}:{lineno}")
    return found


class MoodleFunctionListTests(unittest.TestCase):
    def test_every_referenced_function_is_listed(self):
        listed = set(REQUIRED_FUNCTIONS) | set(OPTIONAL_FUNCTIONS)
        missing = {name: where for name, where in referenced_functions().items() if name not in listed}
        self.assertEqual(missing, {}, "adauga functiile in src/ase_moodle/functions.py")

    def test_every_listed_function_is_still_used(self):
        unused = (set(REQUIRED_FUNCTIONS) | set(OPTIONAL_FUNCTIONS)) - set(referenced_functions())
        self.assertEqual(unused, set(), "scoate din src/ase_moodle/functions.py functiile nefolosite")

    def test_lists_have_no_duplicates_and_do_not_overlap(self):
        self.assertEqual(len(REQUIRED_FUNCTIONS), len(set(REQUIRED_FUNCTIONS)))
        self.assertEqual(len(OPTIONAL_FUNCTIONS), len(set(OPTIONAL_FUNCTIONS)))
        self.assertEqual(set(REQUIRED_FUNCTIONS) & set(OPTIONAL_FUNCTIONS), set())

    def test_scanner_finds_known_calls(self):
        found = referenced_functions()
        self.assertIn("mod_forum_get_forum_discussions", found)
        self.assertIn("mod_chat_get_chats_by_courses", found)
        self.assertIn("core_webservice_get_site_info", found)

    def test_missing_functions_splits_required_and_optional(self):
        available = set(REQUIRED_FUNCTIONS) - {"mod_quiz_start_attempt"}
        required, optional = missing_functions(available)
        self.assertEqual(required, ["mod_quiz_start_attempt"])
        self.assertEqual(optional, list(OPTIONAL_FUNCTIONS))


if __name__ == "__main__":
    unittest.main()
