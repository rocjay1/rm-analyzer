"""
Tests for the emailer module.
"""

import os
import unittest
from datetime import date
from unittest.mock import patch

from rmanalyzer.emailer import SummaryEmail
from rmanalyzer.models import Category, Group, IgnoredFrom, Person, Transaction


class TestEmailer(unittest.TestCase):
    """Test suite for the SummaryEmail class."""

    def setUp(self):
        """Set up test fixtures."""
        self.t1 = Transaction(
            date(2025, 8, 1), "A", 1, 10.0, Category.DINING, IgnoredFrom.NOTHING
        )
        self.p1 = Person("Alice", "alice@example.com", [1], [self.t1])
        self.p2 = Person("Bob", "bob@example.com", [2], [])
        self.group = Group([self.p1, self.p2])
        self.email = SummaryEmail(
            "sender@example.com", ["alice@example.com", "bob@example.com"]
        )

    def test_add_body(self):
        """Test adding body content to the email."""
        self.email.add_body(self.group)
        self.assertIn("Alice", self.email.body)
        self.assertIn("10.00", self.email.body)
        self.assertIn("html", self.email.body)
        self.assertIn("Difference", self.email.body)

    def test_add_subject(self):
        """Test generating the email subject."""
        self.email.add_subject(self.group)
        self.assertIn("Transactions Summary", self.email.subject)
        self.assertIn("08/01/25", self.email.subject)

    @patch("rmanalyzer.emailer.send_email")
    @patch.dict(
        os.environ,
        {"COMMUNICATION_SERVICES_ENDPOINT": "https://test.communication.azure.com"},
    )
    def test_send(self, mock_send_email):
        """Test sending the email with valid configuration."""
        self.email.subject = "Test Subject"
        self.email.body = "Test Body"
        self.email.send()

        mock_send_email.assert_called_once_with(
            "https://test.communication.azure.com",
            "sender@example.com",
            ["alice@example.com", "bob@example.com"],
            "Test Subject",
            "Test Body",
        )

    @patch("rmanalyzer.emailer.send_email")
    def test_send_missing_env_var(self, _):
        """Test that sending fails when environment variable is missing."""
        # Ensure env var is not set
        if "COMMUNICATION_SERVICES_ENDPOINT" in os.environ:
            del os.environ["COMMUNICATION_SERVICES_ENDPOINT"]

        with self.assertRaises(ValueError):
            self.email.send()


if __name__ == "__main__":
    unittest.main()
