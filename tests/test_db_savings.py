import unittest
from unittest.mock import MagicMock, call, patch
import os
from rmanalyzer.services import DatabaseService


class TestSavingsDB(unittest.TestCase):
    def setUp(self):
        self.env_patcher = patch.dict(
            os.environ, {"TABLE_SERVICE_URL": "http://localhost:10002"}
        )
        self.env_patcher.start()
        self.db_service = DatabaseService()
        self.mock_client = MagicMock()
        # Mock _get_table_client on the instance
        self.db_service._get_table_client = MagicMock(return_value=self.mock_client)

    def tearDown(self):
        self.env_patcher.stop()

    def test_save_savings_creates_batch_ops(self):
        # Mock query return empty list (no existing to delete)
        self.mock_client.query_entities.return_value = []

        month = "2023-11"
        user = "test@example.com"
        pk = f"{user}_{month}"
        data = {
            "startingBalance": 1000.50,
            "items": [{"name": "Rent", "cost": 1500}, {"name": "Food", "cost": 500}],
        }

        self.db_service.save_savings(month, data, user)

        # Verify submit_transaction called
        self.mock_client.submit_transaction.assert_called_once()
        batch_args = self.mock_client.submit_transaction.call_args[0][0]

        # Expect 3 create operations: 1 summary + 2 items
        self.assertEqual(len(batch_args), 3)

        # Check integrity of operations
        op_types = [op[0] for op in batch_args]
        self.assertEqual(op_types, ["upsert", "create", "create"])

        # Check Summary
        summary = next(op[1] for op in batch_args if op[1]["RowKey"] == "SUMMARY")
        self.assertEqual(summary["PartitionKey"], pk)
        self.assertEqual(summary["StartingBalance"], 1000.50)

        # Check Items
        items = [op[1] for op in batch_args if op[1]["RowKey"].startswith("ITEM_")]
        self.assertEqual(len(items), 2)
        rent = next(i for i in items if i["Name"] == "Rent")
        self.assertEqual(rent["Cost"], 1500.0)

    def test_get_savings_reassembles_json(self):
        month = "2023-11"
        user = "test@example.com"
        pk = f"{user}_{month}"

        mock_entities = [
            {"PartitionKey": pk, "RowKey": "SUMMARY", "StartingBalance": 2000.0},
            {
                "PartitionKey": pk,
                "RowKey": "ITEM_1",
                "Name": "Utilities",
                "Cost": 150.0,
            },
            {
                "PartitionKey": pk,
                "RowKey": "ITEM_2",
                "Name": "Internet",
                "Cost": 80.0,
            },
        ]

        self.mock_client.query_entities.return_value = mock_entities

        result = self.db_service.get_savings(month, user)

        self.assertEqual(result["startingBalance"], 2000.0)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["name"], "Utilities")
        self.assertEqual(result["items"][1]["cost"], 80.0)

    def test_get_savings_returns_none_if_missing(self):
        # Mock empty query result
        self.mock_client.query_entities.return_value = []

        result = self.db_service.get_savings("2026-02", "user")
        self.assertIsNone(result)

    def test_save_savings_deletes_existing(self):
        month = "2023-11"
        user = "test@example.com"
        pk = f"{user}_{month}"

        # Mock existing items
        self.mock_client.query_entities.return_value = [
            {"PartitionKey": pk, "RowKey": "SUMMARY"},
            {"PartitionKey": pk, "RowKey": "ITEM_OLD"},
        ]

        self.db_service.save_savings(month, {}, user)

        batch_args = self.mock_client.submit_transaction.call_args[0][0]

        # Check that we have 1 delete (SUMMARY is skipped)
        deletes = [op for op in batch_args if op[0] == "delete"]
        self.assertEqual(len(deletes), 1)


if __name__ == "__main__":
    unittest.main()
