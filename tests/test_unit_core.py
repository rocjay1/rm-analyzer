import unittest
from rmanalyzer.models import Transaction, Category, IgnoredFrom, Person, Group
from rmanalyzer.transactions import to_transaction, to_currency
from datetime import date

class TestTransactionHelpers(unittest.TestCase):
    def test_to_transaction_valid(self):
        row = {
            "Date": "2025-08-17",
            "Name": "Test",
            "Account Number": "123",
            "Amount": "42.5",
            "Category": "Dining & Drinks",
            "Ignored From": "everything"
        }
        t = to_transaction(row)
        self.assertIsInstance(t, Transaction)
        self.assertEqual(t.name, "Test")
        self.assertEqual(t.account_number, 123)
        self.assertEqual(t.amount, 42.5)
        self.assertEqual(t.category, Category.DINING)
        self.assertEqual(t.ignore, IgnoredFrom.EVERYTHING)

    def test_to_transaction_invalid(self):
        row = {"Date": "bad-date", "Name": "Test", "Account Number": "abc", "Amount": "bad", "Category": "bad", "Ignored From": "bad"}
        t = to_transaction(row)
        self.assertIsNone(t)

    def test_to_currency(self):
        self.assertEqual(to_currency(42), "42.00")
        self.assertEqual(to_currency(0), "0.00")
        self.assertEqual(to_currency(3.14159), "3.14")

class TestPersonGroup(unittest.TestCase):
    def setUp(self):
        self.t1 = Transaction(date(2025, 8, 1), "A", 1, 10.0, Category.DINING, IgnoredFrom.NOTHING)
        self.t2 = Transaction(date(2025, 8, 2), "B", 1, 20.0, Category.GROCERIES, IgnoredFrom.NOTHING)
        self.t3 = Transaction(date(2025, 8, 3), "C", 2, 30.0, Category.DINING, IgnoredFrom.NOTHING)
        self.p1 = Person("Alice", "alice@example.com", [1], [self.t1, self.t2])
        self.p2 = Person("Bob", "bob@example.com", [2], [self.t3])
        self.group = Group([self.p1, self.p2])

    def test_person_expenses(self):
        self.assertEqual(self.p1.get_expenses(), 30.0)
        self.assertEqual(self.p2.get_expenses(), 30.0)
        self.assertEqual(self.p1.get_expenses(Category.DINING), 10.0)
        self.assertEqual(self.p2.get_expenses(Category.DINING), 30.0)

    def test_group_expenses(self):
        self.assertEqual(self.group.get_expenses(), 60.0)
        diff = self.group.get_expenses_difference(self.p1, self.p2)
        self.assertEqual(diff, 0.0)
        debt = self.group.get_debt(self.p1, self.p2, 0.5)
        self.assertEqual(debt, 0.0)

    def test_group_add_transactions(self):
        t4 = Transaction(date(2025, 8, 4), "D", 1, 5.0, Category.DINING, IgnoredFrom.NOTHING)
        self.group.add_transactions([t4])
        self.assertIn(t4, self.p1.transactions)

    def test_group_invalid_member(self):
        p3 = Person("Eve", "eve@example.com", [3], [])
        with self.assertRaises(ValueError):
            self.group.get_expenses_difference(self.p1, p3)
        with self.assertRaises(ValueError):
            self.group.get_debt(self.p1, p3)

if __name__ == "__main__":
    unittest.main()
