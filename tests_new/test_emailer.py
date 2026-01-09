import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src/backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/backend')))

from rmanalyzer.emailer import SummaryEmail
from rmanalyzer.models import Group, Person, Transaction, Category, IgnoredFrom
from datetime import date

class TestEmailer(unittest.TestCase):
    def setUp(self):
        self.t1 = Transaction(date(2025, 8, 1), "A", 1, 10.0, Category.DINING, IgnoredFrom.NOTHING)
        self.p1 = Person("Alice", "alice@example.com", [1], [self.t1])
        self.p2 = Person("Bob", "bob@example.com", [2], [])
        self.group = Group([self.p1, self.p2])
        self.email = SummaryEmail("sender@example.com", ["alice@example.com", "bob@example.com"])

    def test_add_body(self):
        self.email.add_body(self.group)
        self.assertIn("Alice", self.email.body)
        self.assertIn("10.00", self.email.body)
        self.assertIn("html", self.email.body)
        self.assertIn("Difference", self.email.body)

    def test_add_subject(self):
        self.email.add_subject(self.group)
        self.assertIn("Transactions Summary", self.email.subject)
        self.assertIn("08/01/25", self.email.subject)

    @patch("rmanalyzer.emailer.send_email")
    @patch.dict(os.environ, {"COMMUNICATION_SERVICES_ENDPOINT": "https://test.communication.azure.com"})
    def test_send(self, mock_send_email):
        self.email.subject = "Test Subject"
        self.email.body = "Test Body"
        self.email.send()

        mock_send_email.assert_called_once_with(
            "https://test.communication.azure.com",
            "sender@example.com",
            ["alice@example.com", "bob@example.com"],
            "Test Subject",
            "Test Body"
        )

    @patch("rmanalyzer.emailer.send_email")
    def test_send_missing_env_var(self, mock_send_email):
        # Ensure env var is not set
        if "COMMUNICATION_SERVICES_ENDPOINT" in os.environ:
            del os.environ["COMMUNICATION_SERVICES_ENDPOINT"]

        with self.assertRaises(ValueError):
            self.email.send()

if __name__ == "__main__":
    unittest.main()
