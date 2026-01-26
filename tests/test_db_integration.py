import os
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from rmanalyzer.db import DatabaseService
from rmanalyzer.models import Category, IgnoredFrom, Transaction


class TestDB(unittest.TestCase):
    def setUp(self):
        # Mock TABLE_SERVICE_URL to avoid ValueError in DatabaseService.__init__
        self.env_patcher = patch.dict(
            os.environ, {"TABLE_SERVICE_URL": "http://localhost:10002"}
        )
        self.env_patcher.start()
        self.db_service = DatabaseService()

    def tearDown(self):
        self.env_patcher.stop()

    def test_generate_row_key(self):
        """Test that row keys are deterministic."""
        t1 = Transaction(
            transact_date=date(2023, 1, 1),
            name="Test Transaction",
            account_number=1234,
            amount="100.50",
            category=Category.DINING,
            ignore=IgnoredFrom.NOTHING,
        )

        # Access via instance
        key1 = self.db_service._generate_row_key(t1)
        key2 = self.db_service._generate_row_key(t1)  # Identity check

        # Should be identical now (idempotence)
        self.assertEqual(key1, key2)

        # Same data should produce SAME key if index is default
        t2 = Transaction(
            transact_date=date(2023, 1, 1),
            name="Test Transaction",
            account_number=1234,
            amount="100.50",
            category=Category.GROCERIES,
            ignore=IgnoredFrom.BUDGET,
        )
        key3 = self.db_service._generate_row_key(t2)
        self.assertEqual(key1, key3)

        # Different index should produce different key
        key4 = self.db_service._generate_row_key(t1, occurrence_index=1)
        self.assertNotEqual(key1, key4)

    def test_save_transactions(self):
        """Test that save_transactions calls submit_transaction correctly."""
        # Mock _get_table_client on the instance
        mock_client = MagicMock()
        self.db_service._get_table_client = MagicMock(return_value=mock_client)

        t = Transaction(
            transact_date=date(2023, 10, 15),
            name="Grocery Store",
            account_number=5678,
            amount="50.0",
            category=Category.GROCERIES,
            ignore=IgnoredFrom.NOTHING,
        )

        self.db_service.save_transactions([t])

        # Expect submit_transaction was called (batching)
        mock_client.submit_transaction.assert_called_once()
        batch_args = mock_client.submit_transaction.call_args[0][0]
        self.assertEqual(len(batch_args), 1)

        op_type, entity, options = batch_args[0]
        self.assertEqual(op_type, "upsert")
        self.assertEqual(entity["PartitionKey"], "default_2023-10")
        self.assertEqual(entity["Description"], "Grocery Store")
        self.assertEqual(entity["Amount"], 50.0)


if __name__ == "__main__":
    unittest.main()
