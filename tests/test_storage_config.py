"""
Tests for storage configuration and connection logic.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
from azure.core.credentials import AzureNamedKeyCredential
from rmanalyzer.storage import (
    BlobService,
    QueueService,
)


class TestStorageConfig(unittest.TestCase):
    """Test suite for storage configuration logic."""

    def setUp(self):
        # Save original environment to restore later
        self.original_env = dict(os.environ)
        # Clear relevant env vars to ensure clean state
        for key in [
            "BLOB_SERVICE_URL",
            "QUEUE_SERVICE_URL",
            "BLOB_CONTAINER_NAME",
            "QUEUE_NAME",
        ]:
            if key in os.environ:
                del os.environ[key]

    def tearDown(self):
        # Restore environment
        os.environ.clear()
        os.environ.update(self.original_env)

    @patch("rmanalyzer.storage.BlobServiceClient")
    def test_init_blob_service_missing_url(self, _):
        """Test that ValueError is raised when BLOB_SERVICE_URL is missing."""
        with self.assertRaises(ValueError) as cm:
            BlobService()
        self.assertIn("BLOB_SERVICE_URL", str(cm.exception))

    @patch("rmanalyzer.storage.BlobServiceClient")
    def test_get_blob_client_dev_url(self, mock_blob_client):
        """Test that http:// URL uses Azurite credentials."""
        os.environ["BLOB_SERVICE_URL"] = "http://127.0.0.1:10000/devstoreaccount1"

        service = BlobService()
        # pylint: disable=protected-access
        service._get_blob_service_client()

        _, kwargs = mock_blob_client.call_args
        self.assertEqual(
            kwargs["account_url"], "http://127.0.0.1:10000/devstoreaccount1"
        )
        self.assertIsInstance(kwargs["credential"], str)
        # Check for Azurite default key
        self.assertTrue(kwargs["credential"].startswith("Eby8vdM02xNOcq"))

    @patch("rmanalyzer.storage.DefaultAzureCredential")
    @patch("rmanalyzer.storage.BlobServiceClient")
    def test_get_blob_client_prod_url(self, mock_blob_client, mock_credential):
        """Test that https:// URL uses DefaultAzureCredential."""
        prod_url = "https://mystorage.blob.core.windows.net/"
        os.environ["BLOB_SERVICE_URL"] = prod_url

        mock_cred_instance = MagicMock()
        mock_credential.return_value = mock_cred_instance

        service = BlobService()
        # pylint: disable=protected-access
        service._get_blob_service_client()

        _, kwargs = mock_blob_client.call_args
        self.assertEqual(kwargs["account_url"], prod_url)
        # Should use the credential instance from DefaultAzureCredential()
        self.assertIs(kwargs["credential"], mock_cred_instance)

    @patch("rmanalyzer.storage.BlobServiceClient")
    def test_get_blob_client_cached(self, mock_blob_client):
        """Test that BlobServiceClient is cached."""
        os.environ["BLOB_SERVICE_URL"] = "http://127.0.0.1:10000/devstoreaccount1"
        service = BlobService()

        client1 = service._get_blob_service_client()
        client2 = service._get_blob_service_client()

        self.assertIs(client1, client2)
        mock_blob_client.assert_called_once()

    @patch("rmanalyzer.storage.QueueClient")
    def test_init_queue_service_missing_url(self, _):
        """Test that ValueError is raised when QUEUE_SERVICE_URL is missing."""
        with self.assertRaises(ValueError) as cm:
            QueueService()
        self.assertIn("QUEUE_SERVICE_URL", str(cm.exception))

    @patch("rmanalyzer.storage.QueueClient")
    def test_get_queue_client_dev_url(self, mock_queue_client):
        """Test that http:// URL uses Azurite credentials."""
        os.environ["QUEUE_SERVICE_URL"] = "http://127.0.0.1:10001/devstoreaccount1"
        os.environ["QUEUE_NAME"] = "test-queue"

        service = QueueService()
        # pylint: disable=protected-access
        service._get_queue_client()

        _, kwargs = mock_queue_client.call_args
        self.assertEqual(
            kwargs["account_url"], "http://127.0.0.1:10001/devstoreaccount1"
        )
        self.assertEqual(kwargs["queue_name"], "test-queue")
        self.assertIsInstance(kwargs["credential"], str)
        # Check for Azurite default key
        self.assertTrue(kwargs["credential"].startswith("Eby8vdM02xNOcq"))

    @patch("rmanalyzer.storage.DefaultAzureCredential")
    @patch("rmanalyzer.storage.QueueClient")
    def test_get_queue_client_prod_url(self, mock_queue_client, mock_credential):
        """Test that https:// URL uses DefaultAzureCredential."""
        prod_url = "https://mystorage.queue.core.windows.net/"
        os.environ["QUEUE_SERVICE_URL"] = prod_url
        # Test Default Queue Name
        # Not setting QUEUE_NAME env var

        mock_cred_instance = MagicMock()
        mock_credential.return_value = mock_cred_instance

        service = QueueService()
        # pylint: disable=protected-access
        service._get_queue_client()

        _, kwargs = mock_queue_client.call_args
        self.assertEqual(kwargs["account_url"], prod_url)
        self.assertEqual(kwargs["queue_name"], "csv-processing")
        # Should use the credential instance from DefaultAzureCredential()
        self.assertIs(kwargs["credential"], mock_cred_instance)

    @patch("rmanalyzer.storage.QueueClient")
    def test_get_queue_client_cached(self, mock_queue_client):
        """Test that QueueClient is cached."""
        os.environ["QUEUE_SERVICE_URL"] = "http://127.0.0.1:10001/devstoreaccount1"
        service = QueueService()

        client1 = service._get_queue_client()
        client2 = service._get_queue_client()

        self.assertIs(client1, client2)
        mock_queue_client.assert_called_once()


if __name__ == "__main__":
    unittest.main()
