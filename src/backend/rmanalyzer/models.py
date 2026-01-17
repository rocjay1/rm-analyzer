"""
Data models for transactions, people, and groups.
"""

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum

__all__ = [
    "Category",
    "IgnoredFrom",
    "Transaction",
    "Person",
    "Group",
    "to_transaction",
    "get_transactions",
    "to_currency",
]

# Supported date formats
DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]


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


def parse_date(date_str: str) -> date | None:
    """Parse a date string using supported formats."""
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Date '{date_str}' does not match any supported format.")


def to_transaction(  # pylint: disable=too-many-return-statements
    row: dict,
) -> tuple[Transaction | None, str | None]:
    """
    Parses a CSV row into a Transaction object.
    Returns (Transaction, None) if successful, or (None, error_message) if not.
    """
    # Normalize keys and values
    try:
        clean_row = {k.strip(): v.strip() for k, v in row.items() if k}
    except AttributeError:
        return None, "Unexpected error: row is not a valid dictionary"

    # 1. Date
    if "Date" not in clean_row:
        return None, "Missing 'Date' field"
    try:
        transaction_date = parse_date(clean_row["Date"])
    except ValueError as e:
        return None, str(e)

    if transaction_date is None:
        return None, "Date parse failed unexpectedly"

    # 2. Name
    if "Name" not in clean_row:
        return None, "Missing 'Name' field"
    transaction_name = clean_row["Name"]

    # 3. Account Number
    try:
        transaction_account_number = int(clean_row.get("Account Number", ""))
    except ValueError:
        return (
            None,
            f"Invalid or missing 'Account Number': {clean_row.get('Account Number')}",
        )

    # 4. Amount
    try:
        # Use Decimal for financial calculations
        transaction_amount = Decimal(clean_row.get("Amount", "0"))
    except (ValueError, InvalidOperation):
        return None, f"Invalid or missing 'Amount': {clean_row.get('Amount')}"

    # 5. Category (Optional)
    try:
        transaction_category = Category(clean_row.get("Category"))
    except ValueError:
        # Treat unknown categories as OTHER
        transaction_category = Category.OTHER

    # 6. Ignored From (Optional)
    try:
        ignored_from_val = clean_row.get("Ignored From", "")
        transaction_ignore = IgnoredFrom(ignored_from_val)
    except ValueError:
        return (
            None,
            f"Invalid 'Ignored From' value: {clean_row.get('Ignored From')}",
        )

    return (
        Transaction(
            transaction_date,
            transaction_name,
            transaction_account_number,
            transaction_amount,
            transaction_category,
            transaction_ignore,
        ),
        None,
    )


def get_transactions(content: str) -> tuple[list[Transaction], list[str]]:
    """
    Parses CSV content into a list of Transactions.
    Returns (List[Transaction], List[str]) where the second list contains error messages.
    """
    lines = [line for line in content.splitlines() if line.strip()]
    rows = csv.DictReader(lines)
    transactions = []
    errors = []

    # Handle case where fieldnames might have whitespace
    if rows.fieldnames:
        rows.fieldnames = [name.strip() for name in rows.fieldnames]

    for i, row in enumerate(rows, start=1):
        transaction, error = to_transaction(row)
        if transaction:
            transactions.append(transaction)
        else:
            errors.append(f"Row {i}: {error}")

    return transactions, errors


def to_currency(num: Decimal | float | int) -> str:
    """Format a number as a currency string."""
    return f"{num:.2f}"
