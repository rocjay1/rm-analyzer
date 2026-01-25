"""
Tests for the emailer module.
"""

import os
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from rmanalyzer.email import render_body, render_subject, send_email
from rmanalyzer.models import Category, Group, IgnoredFrom, Person, Transaction


class TestEmailer(unittest.TestCase):
    """Test suite for the email functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.t1 = Transaction(
            date(2025, 8, 1),
            "A",
            1,
            Decimal("10.0"),
            Category.DINING,
            IgnoredFrom.NOTHING,
        )
        self.p1 = Person("Alice", "alice@example.com", [1], [self.t1])
        self.p2 = Person("Bob", "bob@example.com", [2], [])
        self.group = Group([self.p1, self.p2])

    def test_render_body(self):
        """Test rendering the email body."""
        body = render_body(self.group)
        self.assertIn("Alice", body)
        self.assertIn("10.00", body)
        self.assertIn("html", body)
        self.assertIn("Difference", body)

    def test_render_body_with_errors(self):
        """Test rendering body content with validation errors."""
        body = render_body(self.group, errors=["Error 1", "Error 2"])
        self.assertIn("Warning: Some transactions were skipped", body)
        self.assertIn("Error 1", body)
        self.assertIn("Error 2", body)
        self.assertIn("Alice", body)

    def test_render_subject(self):
        """Test generating the email subject."""
        subject = render_subject(self.group)
        self.assertIn("Transactions Summary", subject)
        self.assertIn("08/01/25", subject)

    @patch("rmanalyzer.email.EmailClient")
    @patch("rmanalyzer.email.DefaultAzureCredential")
    def test_send_email_success(self, mock_credential, mock_email_client):
        """Test sending the email with valid configuration."""
        mock_poller = unittest.mock.Mock()
        mock_poller.result.return_value = {"messageId": "test_id"}

        mock_client_instance = mock_email_client.return_value
        mock_client_instance.begin_send.return_value = mock_poller

        send_email(
            "https://test.communication.azure.com",
            "sender@example.com",
            ["alice@example.com"],
            "Test Subject",
            "Test Body"
        )

        mock_client_instance.begin_send.assert_called_once()
        args, _ = mock_client_instance.begin_send.call_args
        message = args[0]
        self.assertEqual(message["senderAddress"], "sender@example.com")
        self.assertEqual(message["recipients"]["to"][0]["address"], "alice@example.com")
        self.assertEqual(message["content"]["subject"], "Test Subject")

if __name__ == "__main__":
    unittest.main()
