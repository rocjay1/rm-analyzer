"""
Data models for transactions, people, and groups.
"""

from datetime import date
from decimal import Decimal
from enum import Enum

__all__ = [
    "Category",
    "IgnoredFrom",
    "Transaction",
    "Person",
    "Group",
]


class Category(Enum):
    """Spending categories for transactions."""

    DINING = "Dining & Drinks"
    GROCERIES = "Groceries"
    PETS = "Pets"
    BILLS = "Bills & Utilities"
    PURCHASES = "Shared Purchases"
    SUBSCRIPTIONS = "Shared Subscriptions"
    TRAVEL = "Travel & Vacation"
    OTHER = "Other"


class IgnoredFrom(Enum):
    """Flags for ignoring transactions from certain calculations."""

    BUDGET = "budget"
    EVERYTHING = "everything"
    NOTHING = ""


class Transaction:
    """A single financial transaction."""

    def __init__(
        self,
        transact_date: date,
        name: str,
        account_number: int,
        amount: Decimal,
        category: Category,
        ignore: IgnoredFrom,
    ) -> None:
        self.date = transact_date
        self.name = name
        self.account_number = account_number
        self.amount = amount
        self.category = category
        self.ignore = ignore


class Person:
    """A person with accounts and transactions."""

    def __init__(
        self,
        name: str,
        email: str,
        account_numbers: list[int],
        transactions: list[Transaction] | None = None,
    ) -> None:
        self.name = name
        self.email = email
        self.account_numbers = account_numbers
        self.transactions = transactions or []

    def add_transaction(self, transaction: Transaction) -> None:
        """Add a transaction to the person's list."""
        self.transactions.append(transaction)

    def get_oldest_transaction(self) -> date | None:
        """Return the date of the oldest transaction."""
        if not self.transactions:
            return None
        return min(t.date for t in self.transactions)

    def get_newest_transaction(self) -> date | None:
        """Return the date of the newest transaction."""
        if not self.transactions:
            return None
        return max(t.date for t in self.transactions)

    def get_expenses(self, category: Category | None = None) -> Decimal:
        """Calculate total expenses, optionally filtered by category."""
        if not self.transactions:
            return Decimal("0.00")
        if not category:
            return sum((t.amount for t in self.transactions), start=Decimal("0.00"))
        return sum(
            (t.amount for t in self.transactions if t.category == category),
            start=Decimal("0.00"),
        )


class Group:
    """A group of people for expense analysis."""

    def __init__(self, members: list[Person]) -> None:
        self.members = members

    def add_transactions(self, transactions: list[Transaction]) -> None:
        """Add a list of transactions to the appropriate members."""
        for t in transactions:
            for p in self.members:
                if (
                    t.account_number in p.account_numbers
                    and t.ignore == IgnoredFrom.NOTHING
                    and t.category != Category.OTHER
                ):
                    p.add_transaction(t)

    def get_oldest_transaction(self) -> date:
        """Return the date of the oldest transaction in the group."""
        dates = [
            d
            for d in (p.get_oldest_transaction() for p in self.members)
            if d is not None
        ]
        if not dates:
            raise ValueError("No transactions found in group")
        return min(dates)

    def get_newest_transaction(self) -> date:
        """Return the date of the newest transaction in the group."""
        dates = [
            d
            for d in (p.get_newest_transaction() for p in self.members)
            if d is not None
        ]
        if not dates:
            raise ValueError("No transactions found in group")
        return max(dates)

    def get_expenses_difference(
        self, p1: Person, p2: Person, category: Category | None = None
    ) -> Decimal:
        """Calculate the difference in expenses between two people."""
        missing = [p for p in [p1, p2] if p not in self.members]
        if missing:
            raise ValueError("People args missing from group")
        return p1.get_expenses(category) - p2.get_expenses(category)

    def get_expenses(self) -> Decimal:
        """Calculate the total expenses of the group."""
        return sum((p.get_expenses() for p in self.members), start=Decimal("0.00"))

    def get_debt(
        self, p1: Person, p2: Person, p1_scale_factor: Decimal = Decimal("0.5")
    ) -> Decimal:
        """Calculate how much p1 owes p2 based on a scale factor."""
        missing = [p for p in [p1, p2] if p not in self.members]
        if missing:
            raise ValueError("People args missing from group")
        return p1_scale_factor * self.get_expenses() - p1.get_expenses()
