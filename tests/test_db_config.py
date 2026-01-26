"""
Tests for database configuration and connection logic.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
from azure.core.credentials import AzureNamedKeyCredential
from rmanalyzer.services import DatabaseService


class TestDBConfig(unittest.TestCase):
    """Test suite for database configuration logic."""

    def setUp(self):
        # Save original environment to restore later
        self.original_env = dict(os.environ)
        # Clear relevant env vars to ensure clean state
        if "TABLE_SERVICE_URL" in os.environ:
            del os.environ["TABLE_SERVICE_URL"]

    def tearDown(self):
        # Restore environment
        os.environ.clear()
        os.environ.update(self.original_env)

    @patch("rmanalyzer.services.TableClient")
    def test_init_missing_url(self, _):
        """Test that ValueError is raised during init when TABLE_SERVICE_URL is missing."""
        with self.assertRaises(ValueError) as cm:
            DatabaseService()
            DatabaseService()
        self.assertIn("TABLE_SERVICE_URL", str(cm.exception))

    @patch("rmanalyzer.services.TableClient")
    def test_get_table_client_dev_url(self, mock_table_client):
        """Test that http:// URL uses Azurite credentials."""
        os.environ["TABLE_SERVICE_URL"] = "http://127.0.0.1:10002/devstoreaccount1"

        service = DatabaseService()
        service = DatabaseService()
        # pylint: disable=protected-access
        service._get_table_client("test_table")
        service._get_table_client("test_table")

        # Check that TableClient was initialized with AzureNamedKeyCredential
        _, kwargs = mock_table_client.call_args
        self.assertEqual(kwargs["endpoint"], "http://127.0.0.1:10002/devstoreaccount1")
        self.assertIsInstance(kwargs["credential"], AzureNamedKeyCredential)

    @patch("rmanalyzer.services.DefaultAzureCredential")
    @patch("rmanalyzer.services.TableClient")
    def test_get_table_client_prod_url(self, mock_table_client, mock_credential):
        """Test that https:// URL uses DefaultAzureCredential."""
        prod_url = "https://mystorage.table.core.windows.net/"
        os.environ["TABLE_SERVICE_URL"] = prod_url

        mock_cred_instance = MagicMock()
        mock_credential.return_value = mock_cred_instance

        service = DatabaseService()
        service = DatabaseService()
        # pylint: disable=protected-access
        service._get_table_client("test_table")
        service._get_table_client("test_table")

        _, kwargs = mock_table_client.call_args
        self.assertEqual(kwargs["endpoint"], prod_url)
        # Should use the credential instance from DefaultAzureCredential()
        # Note: The implementation in db.py creates DefaultAzureCredential() inside the function
        # We patch the class to return our mock
        self.assertIs(kwargs["credential"], mock_cred_instance)

    @patch("rmanalyzer.services.TableClient")
    def test_get_table_client_cached(self, mock_table_client):
        """Test that TableClient is cached."""
        os.environ["TABLE_SERVICE_URL"] = "http://127.0.0.1:10002/devstoreaccount1"
        service = DatabaseService()

        # First call
        client1 = service._get_table_client("test_table")

        # Second call
        client2 = service._get_table_client("test_table")

        self.assertIs(client1, client2)
        # Should only be called once (created once)
        mock_table_client.assert_called_once()


if __name__ == "__main__":
    unittest.main()
