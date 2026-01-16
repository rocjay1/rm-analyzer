"""
Tests for the business logic (models and transactions).
"""

import unittest
from datetime import date
from decimal import Decimal

from rmanalyzer.models import Category, Group, IgnoredFrom, Person, Transaction
from rmanalyzer.transactions import get_transactions, to_currency, to_transaction


class TestTransactionHelpers(unittest.TestCase):
    """Test suite for transaction helper functions."""

    def test_to_transaction_valid(self):
        """Test conversion of a valid row to a Transaction object."""
        row = {
            "Date": "2025-08-17",
            "Name": "Test",
            "Account Number": "123",
            "Amount": "42.5",
            "Category": "Dining & Drinks",
            "Ignored From": "everything",
        }
        t, err = to_transaction(row)
        self.assertIsInstance(t, Transaction)
        self.assertIsNone(err)
        self.assertEqual(t.name, "Test")
        self.assertEqual(t.account_number, 123)
        self.assertEqual(t.amount, Decimal("42.5"))
        self.assertEqual(t.category, Category.DINING)
        self.assertEqual(t.ignore, IgnoredFrom.EVERYTHING)

    def test_to_transaction_whitespace(self):
        """Test conversion of a row with whitespace in keys/values."""
        row = {
            " Date ": " 2025-08-17 ",
            "Name": "Test",
            "Account Number": "123",
            "Amount": "42.5",
            "Category": "Dining & Drinks",
            "Ignored From": "everything",
        }
        # Note: keys are usually cleaned by DictReader if configured,
        # but here we test to_transaction direct usage
        # Since to_transaction cleans keys too now:
        t, err = to_transaction(row)
        self.assertIsInstance(t, Transaction)
        self.assertIsNone(err)
        self.assertEqual(t.date, date(2025, 8, 17))

    def test_to_transaction_invalid(self):
        """Test conversion of an invalid row returns None."""
        row = {
            "Date": "bad-date",
            "Name": "Test",
            "Account Number": "abc",
            "Amount": "bad",
            "Category": "bad",
            "Ignored From": "bad",
        }
        t, err = to_transaction(row)
        self.assertIsNone(t)
        self.assertIsNotNone(err)
        self.assertTrue("bad-date" in err or "Date" in err)

    def test_to_currency(self):
        """Test currency formatting."""
        self.assertEqual(to_currency(42), "42.00")
        self.assertEqual(to_currency(0), "0.00")
        self.assertEqual(to_currency(3.14159), "3.14")

    def test_get_transactions_csv_parsing(self):
        """Test parsing transactions from CSV content."""
        # Ignored From must be empty string for NOTHING, or "everything" / "budget"
        csv_content = (
            "Date,Name,Account Number,Amount,Category,Ignored From\n"
            "2025-08-17,Test,123,42.5,Dining & Drinks,everything\n"
            "\n"
            "2025-08-18,Test2,123,10.0,Groceries,\n"
        )
        transactions, errors = get_transactions(csv_content)
        self.assertEqual(len(transactions), 2)
        self.assertEqual(len(errors), 0)
        self.assertEqual(transactions[0].name, "Test")
        self.assertEqual(transactions[1].name, "Test2")

    def test_get_transactions_csv_parsing_headers_whitespace(self):
        """Test parsing CSV with whitespace in headers."""
        csv_content = (
            " Date , Name , Account Number , Amount , Category , Ignored From\n"
            "2025-08-17,Test,123,42.5,Dining & Drinks,everything\n"
        )
        transactions, errors = get_transactions(csv_content)
        self.assertEqual(len(transactions), 1)
        self.assertEqual(len(errors), 0)
        self.assertEqual(transactions[0].name, "Test")

    def test_get_transactions_with_errors(self):
        """Test parsing CSV with mixed valid and invalid rows."""
        csv_content = (
            "Date,Name,Account Number,Amount,Category,Ignored From\n"
            "2025-08-17,Test,123,42.5,Dining & Drinks,everything\n"
            "bad-date,Bad,123,10.0,Groceries,\n"
        )
        transactions, errors = get_transactions(csv_content)
        self.assertEqual(len(transactions), 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("Row 2", errors[0])


class TestPersonGroup(unittest.TestCase):
    """Test suite for Person and Group models."""

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
        self.t2 = Transaction(
            date(2025, 8, 2),
            "B",
            1,
            Decimal("20.0"),
            Category.GROCERIES,
            IgnoredFrom.NOTHING,
        )
        self.t3 = Transaction(
            date(2025, 8, 3),
            "C",
            2,
            Decimal("30.0"),
            Category.DINING,
            IgnoredFrom.NOTHING,
        )
        self.p1 = Person("Alice", "alice@example.com", [1], [self.t1, self.t2])
        self.p2 = Person("Bob", "bob@example.com", [2], [self.t3])
        self.group = Group([self.p1, self.p2])

    def test_person_expenses(self):
        """Test calculating person expenses."""
        self.assertEqual(self.p1.get_expenses(), Decimal("30.0"))
        self.assertEqual(self.p2.get_expenses(), Decimal("30.0"))
        self.assertEqual(self.p1.get_expenses(Category.DINING), Decimal("10.0"))
        self.assertEqual(self.p2.get_expenses(Category.DINING), Decimal("30.0"))

    def test_group_expenses(self):
        """Test calculating group expenses."""
        self.assertEqual(self.group.get_expenses(), Decimal("60.0"))
        diff = self.group.get_expenses_difference(self.p1, self.p2)
        self.assertEqual(diff, Decimal("0.0"))
        debt = self.group.get_debt(self.p1, self.p2, Decimal("0.5"))
        self.assertEqual(debt, Decimal("0.0"))

    def test_group_add_transactions(self):
        """Test adding transactions to a group."""
        t4 = Transaction(
            date(2025, 8, 4),
            "D",
            1,
            Decimal("5.0"),
            Category.DINING,
            IgnoredFrom.NOTHING,
        )
        self.group.add_transactions([t4])
        self.assertIn(t4, self.p1.transactions)


if __name__ == "__main__":
    unittest.main()
