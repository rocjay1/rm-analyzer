"""
Tests for the Azure Function App.
"""

import unittest
from unittest.mock import MagicMock, patch

import azure.functions as func

from function_app import upload


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

    def test_unauthorized(self):
        """Test that unauthorized requests return 401."""
        self.req.headers = {}
        resp = upload(self.req)
        self.assertEqual(resp.status_code, 401)

    def test_no_file(self):
        """Test that requests with no file return 400."""
        self.req.files = {}
        resp = upload(self.req)
        self.assertEqual(resp.status_code, 400)

    @patch("rmanalyzer.blob_utils.upload_csv")
    @patch("rmanalyzer.queue_utils.enqueue_message")
    def test_success_async(
        self,
        mock_enqueue,
        mock_upload,
    ):
        """Test successful async upload (202 Accepted)."""
        mock_upload.return_value = "https://example.com/blob.csv"

        resp = upload(self.req)

        self.assertEqual(resp.status_code, 202)
        mock_upload.assert_called_once()
        mock_enqueue.assert_called_once()


if __name__ == "__main__":
    unittest.main()
