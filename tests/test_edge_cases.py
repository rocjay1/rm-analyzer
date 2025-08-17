import unittest
from rmanalyzer.models import Person, Group, Transaction, Category, IgnoredFrom
from rmanalyzer.transactions import to_transaction, get_transactions
from datetime import date

class TestEdgeCases(unittest.TestCase):
    def test_empty_transactions(self):
        self.assertEqual(get_transactions(""), [])

    def test_empty_people(self):
        group = Group([])
        with self.assertRaises(ValueError):
            group.get_oldest_transaction()
        with self.assertRaises(ValueError):
            group.get_newest_transaction()

    def test_transaction_missing_fields(self):
        row = {"Date": "2025-08-17"}  # missing required fields
        t = to_transaction(row)
        self.assertIsNone(t)

    def test_ignored_transactions(self):
        t1 = Transaction(date(2025, 8, 1), "A", 1, 10.0, Category.DINING, IgnoredFrom.BUDGET)
        t2 = Transaction(date(2025, 8, 2), "B", 1, 20.0, Category.DINING, IgnoredFrom.NOTHING)
        p = Person("Test", "test@example.com", [1], [t1, t2])
        self.assertEqual(p.get_expenses(), 30.0)
        group = Group([p])
        group.add_transactions([t1, t2])  # Only t2 should be added again
        self.assertEqual(len(p.transactions), 3)

if __name__ == "__main__":
    unittest.main()
