from datetime import date
from enum import Enum
from typing import List, Optional

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
        amount: float,
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
        account_numbers: List[int],
        transactions: Optional[List[Transaction]] = None,
    ) -> None:
        self.name = name
        self.email = email
        self.account_numbers = account_numbers
        self.transactions = transactions or []

    def add_transaction(self, transaction: Transaction) -> None:
        self.transactions.append(transaction)

    def get_oldest_transaction(self) -> Optional[date]:
        if not self.transactions:
            return None
        return min(t.date for t in self.transactions)

    def get_newest_transaction(self) -> Optional[date]:
        if not self.transactions:
            return None
        return max(t.date for t in self.transactions)

    def get_expenses(self, category: Optional[Category] = None) -> float:
        if not self.transactions:
            return 0.0
        if not category:
            return sum(t.amount for t in self.transactions)
        return sum(t.amount for t in self.transactions if t.category == category)


class Group:
    """A group of people for expense analysis."""

    def __init__(self, members: List[Person]) -> None:
        self.members = members

    def add_transactions(self, transactions: List[Transaction]) -> None:
        for t in transactions:
            for p in self.members:
                if (
                    t.account_number in p.account_numbers
                    and t.ignore == IgnoredFrom.NOTHING
                ):
                    p.add_transaction(t)

    def get_oldest_transaction(self) -> date:
        dates = [
            p.get_oldest_transaction()
            for p in self.members
            if p.get_oldest_transaction()
        ]
        if not dates:
            raise ValueError("No transactions found in group")
        return min(dates)

    def get_newest_transaction(self) -> date:
        dates = [
            p.get_newest_transaction()
            for p in self.members
            if p.get_newest_transaction()
        ]
        if not dates:
            raise ValueError("No transactions found in group")
        return max(dates)

    def get_expenses_difference(
        self, p1: Person, p2: Person, category: Optional[Category] = None
    ) -> float:
        missing = [p for p in [p1, p2] if p not in self.members]
        if missing:
            raise ValueError("People args missing from group")
        return p1.get_expenses(category) - p2.get_expenses(category)

    def get_expenses(self) -> float:
        return sum(p.get_expenses() for p in self.members)

    def get_debt(self, p1: Person, p2: Person, p1_scale_factor: float = 0.5) -> float:
        missing = [p for p in [p1, p2] if p not in self.members]
        if missing:
            raise ValueError("People args missing from group")
        return p1_scale_factor * self.get_expenses() - p1.get_expenses()
