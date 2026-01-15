import hashlib
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from rmanalyzer import db
from rmanalyzer.models import Category, IgnoredFrom, Transaction


class TestDB(unittest.TestCase):
    def test_generate_row_key(self):
        """Test that row keys are deterministic and correct."""
        t1 = Transaction(
            transact_date=date(2023, 1, 1),
            name="Test Transaction",
            account_number=1234,
            amount=100.50,
            category=Category.DINING,
            ignore=IgnoredFrom.NOTHING,
        )

        key1 = db._generate_row_key(t1)

        # Same data should produce same key
        t2 = Transaction(
            transact_date=date(2023, 1, 1),
            name="Test Transaction",
            account_number=1234,
            amount=100.50,
            category=Category.GROCERIES,  # Category change shouldn't affect ID if logic ignores it?
            # Wait, my logic used: Date + Description + Amount + AccountNumber
            # So Category is NOT in the hash, which is correct for upserting updates.
            ignore=IgnoredFrom.BUDGET,
        )
        key2 = db._generate_row_key(t2)

        self.assertEqual(key1, key2)

        # Different amount should produce different key
        t3 = Transaction(
            transact_date=date(2023, 1, 1),
            name="Test Transaction",
            account_number=1234,
            amount=100.51,  # Changed
            category=Category.DINING,
            ignore=IgnoredFrom.NOTHING,
        )
        key3 = db._generate_row_key(t3)
        self.assertNotEqual(key1, key3)

    @patch("rmanalyzer.db._get_table_client")
    def test_save_transactions(self, mock_get_client):
        """Test that save_transactions calls upsert_entity correctly."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        t = Transaction(
            transact_date=date(2023, 10, 15),
            name="Grocery Store",
            account_number=5678,
            amount=50.0,
            category=Category.GROCERIES,
            ignore=IgnoredFrom.NOTHING,
        )

        db.save_transactions([t])

        mock_client.upsert_entity.assert_called_once()
        call_kwargs = mock_client.upsert_entity.call_args.kwargs
        entity = call_kwargs["entity"]

        self.assertEqual(entity["PartitionKey"], "2023-10")
        self.assertEqual(entity["Description"], "Grocery Store")
        self.assertEqual(entity["Category"], "Groceries")
        self.assertEqual(entity["Amount"], 50.0)

        # Ensure 'mode' was REPLACE
        from azure.data.tables import UpdateMode

        self.assertEqual(call_kwargs["mode"], UpdateMode.REPLACE)


if __name__ == "__main__":
    unittest.main()
