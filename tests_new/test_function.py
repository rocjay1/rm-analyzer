"""
Tests for the Azure Function App.
"""
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import azure.functions as func

from function_app import upload_and_analyze
import function_app
from rmanalyzer.models import Transaction, Category, IgnoredFrom


class TestFunctionApp(unittest.TestCase):
    """Test suite for the function app."""

    def setUp(self):
        """Set up test fixtures."""
        self.req = MagicMock(spec=func.HttpRequest)
        self.req.headers = {"x-ms-client-principal": "test-user"}
        self.req.files = {"file": MagicMock()}
        self.req.files["file"].filename = "test.csv"
        # csv content
        self.req.files["file"].stream.read.return_value = (
            b"Date,Name,Account Number,Amount,Category,Ignored From\n"
            b"2025-08-17,Test,123,42.5,Dining & Drinks,everything"
        )

        # Reset config cache
        # pylint: disable=protected-access
        function_app._CONFIG_CACHE = None

    def test_unauthorized(self):
        """Test that unauthorized requests return 401."""
        self.req.headers = {}
        resp = upload_and_analyze(self.req)
        self.assertEqual(resp.status_code, 401)

    def test_no_file(self):
        """Test that requests with no file return 400."""
        self.req.files = {}
        resp = upload_and_analyze(self.req)
        self.assertEqual(resp.status_code, 400)

    @patch("function_app.os.path.exists")
    def test_config_missing(self, mock_exists):
        """Test that missing config returns 500."""
        mock_exists.return_value = False
        resp = upload_and_analyze(self.req)
        self.assertEqual(resp.status_code, 500)

    @patch("function_app.os.path.exists")
    @patch("builtins.open")
    @patch("function_app.json.load")
    @patch("function_app.validate_config")
    @patch("function_app.get_transactions")
    @patch("function_app.SummaryEmail")
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def test_success(
            self, mock_email, mock_get_trans, _mock_validate,
            mock_json_load, _mock_open, mock_exists
    ):
        """Test successful execution."""
        mock_exists.return_value = True
        mock_json_load.return_value = {
            "People": [{"Name": "Alice", "Email": "alice@example.com", "Accounts": [123]}],
            "Owner": "Alice",
            "SenderEmail": "sender@example.com"
        }

        # Mock transaction that matches the person's account (123) and is not ignored
        t = Transaction(date(2025, 8, 17), "Test", 123, 42.5, Category.DINING, IgnoredFrom.NOTHING)
        # Mock return value of get_transactions to return (transactions, errors) tuple
        mock_get_trans.return_value = ([t], [])

        resp = upload_and_analyze(self.req)

        self.assertEqual(resp.status_code, 200)
        mock_email.return_value.send.assert_called_once()

        # Verify caching by calling again
        resp2 = upload_and_analyze(self.req)
        self.assertEqual(resp2.status_code, 200)

        # json.load should have been called ONCE.
        self.assertEqual(mock_json_load.call_count, 1)

if __name__ == "__main__":
    unittest.main()
