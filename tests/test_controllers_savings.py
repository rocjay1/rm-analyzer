"""
Tests for savings controller logic.
"""

import base64
import json
import unittest
from unittest.mock import MagicMock, patch

import azure.functions as func

from rmanalyzer.controllers import handle_savings_dbrequest, _get_user_email


class TestSavingsController(unittest.TestCase):
    def setUp(self):
        self.req = MagicMock(spec=func.HttpRequest)
        self.req.params = {}
        self.req.headers = {}
        self.req.get_json = MagicMock(return_value={})

    def _set_auth_header(self, email="test@example.com"):
        payload = {"userDetails": email}
        encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        self.req.headers["x-ms-client-principal"] = encoded

    def test_get_user_email_valid(self):
        self._set_auth_header("user@test.com")
        email = _get_user_email(self.req)
        self.assertEqual(email, "user@test.com")

    def test_get_user_email_missing(self):
        self.req.headers = {}
        email = _get_user_email(self.req)
        self.assertIsNone(email)

    def test_get_user_email_invalid_base64(self):
        self.req.headers["x-ms-client-principal"] = "invalid-base64"
        email = _get_user_email(self.req)
        self.assertIsNone(email)

    def test_handle_savings_unauthorized(self):
        # No header
        resp = handle_savings_dbrequest(self.req)
        self.assertEqual(resp.status_code, 401)

    @patch("rmanalyzer.controllers.db_service.get_savings")
    def test_handle_savings_get_success(self, mock_get):
        self._set_auth_header("user@test.com")
        self.req.method = "GET"
        self.req.params = {"month": "2023-10"}

        mock_get.return_value = {"startingBalance": 100}

        resp = handle_savings_dbrequest(self.req)

        self.assertEqual(resp.status_code, 200)
        mock_get.assert_called_with("2023-10", "user@test.com")
        self.assertIn("100", resp.get_body().decode())

    @patch("rmanalyzer.controllers.db_service.save_savings")
    def test_handle_savings_post_success(self, mock_save):
        self._set_auth_header("user@test.com")
        self.req.method = "POST"
        body = {"month": "2023-10", "startingBalance": 500}
        self.req.get_json.return_value = body

        resp = handle_savings_dbrequest(self.req)

        self.assertEqual(resp.status_code, 200)
        mock_save.assert_called_with("2023-10", body, "user@test.com")


if __name__ == "__main__":
    unittest.main()
