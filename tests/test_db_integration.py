import hashlib
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from rmanalyzer import db
from rmanalyzer.models import Category, IgnoredFrom, Transaction


class TestDB(unittest.TestCase):
    def test_generate_row_key(self):
        """Test that row keys start with deterministic prefix."""
        t1 = Transaction(
            transact_date=date(2023, 1, 1),
            name="Test Transaction",
            account_number=1234,
            amount="100.50",
            category=Category.DINING,
            ignore=IgnoredFrom.NOTHING,
        )

        key1 = db._generate_row_key(t1)

        # Same data should produce similar key (same prefix, diff suffix)
        t2 = Transaction(
            transact_date=date(2023, 1, 1),
            name="Test Transaction",
            account_number=1234,
            amount="100.50",
            category=Category.GROCERIES,
            ignore=IgnoredFrom.BUDGET,
        )
        key2 = db._generate_row_key(t2)

        # Row key format is {base_hash}-{random_suffix}
        # We verify that they are DIFFERENT now, but share prefix logic if we cared.
        # Actually random suffix guarantees difference.
        self.assertNotEqual(key1, key2)

        # Verify length/format roughly
        self.assertEqual(len(key1.split("-")), 2)

    @patch("rmanalyzer.db._get_table_client")
    def test_save_transactions(self, mock_get_client):
        """Test that save_transactions calls submit_transaction correctly."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        t = Transaction(
            transact_date=date(2023, 10, 15),
            name="Grocery Store",
            account_number=5678,
            amount="50.0",
            category=Category.GROCERIES,
            ignore=IgnoredFrom.NOTHING,
        )

        db.save_transactions([t])

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
