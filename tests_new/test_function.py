import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import azure.functions as func
import json

# Add src/backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/backend')))

from function_app import upload_and_analyze
from rmanalyzer.models import Transaction, Category, IgnoredFrom
from datetime import date

class TestFunctionApp(unittest.TestCase):
    def setUp(self):
        self.req = MagicMock(spec=func.HttpRequest)
        self.req.headers = {"x-ms-client-principal": "test-user"}
        self.req.files = {"file": MagicMock()}
        self.req.files["file"].filename = "test.csv"
        # csv content
        self.req.files["file"].stream.read.return_value = b"Date,Name,Account Number,Amount,Category,Ignored From\n2025-08-17,Test,123,42.5,Dining & Drinks,everything"

        # Reset config cache
        import function_app
        function_app._CONFIG_CACHE = None

    def test_unauthorized(self):
        self.req.headers = {}
        resp = upload_and_analyze(self.req)
        self.assertEqual(resp.status_code, 401)

    def test_no_file(self):
        self.req.files = {}
        resp = upload_and_analyze(self.req)
        self.assertEqual(resp.status_code, 400)

    @patch("function_app.os.path.exists")
    def test_config_missing(self, mock_exists):
        mock_exists.return_value = False
        resp = upload_and_analyze(self.req)
        self.assertEqual(resp.status_code, 500)

    @patch("function_app.os.path.exists")
    @patch("builtins.open")
    @patch("function_app.json.load")
    @patch("function_app.validate_config")
    @patch("function_app.get_transactions")
    @patch("function_app.SummaryEmail")
    def test_success(self, mock_email, mock_get_trans, mock_validate, mock_json_load, mock_open, mock_exists):
        mock_exists.return_value = True
        mock_json_load.return_value = {
            "People": [{"Name": "Alice", "Email": "alice@example.com", "Accounts": [123]}],
            "Owner": "Alice",
            "SenderEmail": "sender@example.com"
        }

        # Mock transaction that matches the person's account (123) and is not ignored
        t = Transaction(date(2025, 8, 17), "Test", 123, 42.5, Category.DINING, IgnoredFrom.NOTHING)
        mock_get_trans.return_value = [t]

        resp = upload_and_analyze(self.req)

        self.assertEqual(resp.status_code, 200)
        mock_email.return_value.send.assert_called_once()

        # Verify caching by calling again
        resp2 = upload_and_analyze(self.req)
        self.assertEqual(resp2.status_code, 200)
        # Should NOT call json.load again if cached.
        # However, setUp resets cache, so we need to check in same test.
        # But wait, setUp runs before each test. I need to run calling twice in one test method.
        # I just did that.

        # json.load should have been called ONCE.
        # Because the first call populated cache.
        self.assertEqual(mock_json_load.call_count, 1)

if __name__ == "__main__":
    unittest.main()
