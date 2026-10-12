"""Teste pentru autentificare, fara retea: decodarea redirectului SSO si extragerea tokenului din pagina."""

import base64
import unittest
from unittest import mock

from ase_moodle import auth

# Valori SINTETICE pentru teste: nu sunt tokenuri reale. Redirectul se construieste in cod, ca sa nu existe secrete in fisier.
SAMPLE_TOKEN = "0123456789abcdef0123456789abcdef"
SAMPLE_PRIVATE = "fedcba9876543210fedcba9876543210"
SAMPLE_REDIRECT = "moodlemobile://token=" + base64.b64encode(f"{SAMPLE_PRIVATE}:::{SAMPLE_TOKEN}".encode()).decode()

MANAGE_TOKEN_HTML = f"""
<table><tbody>
<tr><td>{SAMPLE_TOKEN}</td><td>Moodle mobile web service</td><td></td></tr>
<tr><td>{'a' * 32}</td><td>Attendance</td><td></td></tr>
</tbody></table>
"""


class DecodeTests(unittest.TestCase):
    def test_redirect_yields_the_wstoken(self):
        self.assertEqual(auth.decode_launch_url(SAMPLE_REDIRECT), SAMPLE_TOKEN)

    def test_url_encoded_padding_is_accepted(self):
        encoded = SAMPLE_REDIRECT.replace("==", "%3D%3D")
        self.assertEqual(auth.decode_launch_url(encoded), SAMPLE_TOKEN)

    def test_wrong_scheme_is_rejected(self):
        with self.assertRaises(auth.AuthError):
            auth.decode_launch_url("https://online.ase.ro/token=abc")

    def test_payload_without_valid_token_is_rejected(self):
        import base64
        bad = "moodlemobile://token=" + base64.b64encode(b"123:::nu-e-token").decode()
        with self.assertRaises(auth.AuthError):
            auth.decode_launch_url(bad)


class ManageTokenTests(unittest.TestCase):
    def test_extracts_mobile_service_token(self):
        self.assertEqual(auth.token_from_managetoken_html(MANAGE_TOKEN_HTML), SAMPLE_TOKEN)

    def test_other_service_tokens_are_not_returned(self):
        html = f"<tr><td>{'b' * 32}</td><td>Attendance</td></tr>"
        self.assertIsNone(auth.token_from_managetoken_html(html))

    def test_validator(self):
        self.assertTrue(auth.is_valid_token(SAMPLE_TOKEN))
        self.assertTrue(auth.is_valid_token(f"  {SAMPLE_TOKEN}\n"))
        self.assertFalse(auth.is_valid_token("hello world"))
        self.assertFalse(auth.is_valid_token(SAMPLE_TOKEN.upper()))
        self.assertFalse(auth.is_valid_token(None))


class ClipboardTests(unittest.TestCase):
    def test_waits_for_a_valid_token_in_the_clipboard(self):
        values = iter(["text oarecare", SAMPLE_TOKEN])
        with mock.patch.object(auth, "read_clipboard", side_effect=lambda: next(values)), \
                mock.patch.object(auth.time, "sleep", lambda s: None):
            self.assertEqual(auth.wait_for_clipboard_token(timeout_s=10), SAMPLE_TOKEN)

    def test_times_out_without_token(self):
        with mock.patch.object(auth, "read_clipboard", return_value="nimic"), \
                mock.patch.object(auth.time, "sleep", lambda s: None), \
                mock.patch.object(auth.time, "monotonic", side_effect=[0, 0, 100]):
            with self.assertRaises(auth.AuthError):
                auth.wait_for_clipboard_token(timeout_s=5)


class MethodTests(unittest.TestCase):
    def test_unknown_method_is_rejected(self):
        with self.assertRaises(auth.AuthError):
            auth.authenticate(base_url="https://example.invalid", method="magic")

    def test_auto_uses_manual_when_playwright_is_missing(self):
        with mock.patch.object(auth, "playwright_available", return_value=False), \
                mock.patch.object(auth, "open_token_page", return_value="u"), \
                mock.patch.object(auth, "wait_for_clipboard_token", return_value=SAMPLE_TOKEN), \
                mock.patch.object(auth, "verify_token", return_value="Test User"), \
                mock.patch.object(auth, "save_settings", return_value="cfg.json") as save:
            result = auth.authenticate(base_url="https://example.invalid", method="auto")
        self.assertEqual(result["method"], "manual")
        self.assertEqual(result["user"], "Test User")
        save.assert_called_once_with(SAMPLE_TOKEN, "https://example.invalid")


if __name__ == "__main__":
    unittest.main()
