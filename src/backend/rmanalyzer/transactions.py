"""
Transaction parsing and handling utilities.
"""

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .models import Category, IgnoredFrom, Transaction

__all__ = ["to_transaction", "get_transactions", "to_currency"]

# Supported date formats
DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]


def parse_date(date_str: str) -> date | None:
    """Parse a date string using supported formats."""
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Date '{date_str}' does not match any supported format.")


def _parse_account_number(clean_row: dict) -> int:
    try:
        return int(clean_row.get("Account Number", ""))
    except ValueError as e:
        raise ValueError(
            f"Invalid or missing 'Account Number': {clean_row.get('Account Number')}"
        ) from e


def _parse_amount(clean_row: dict) -> Decimal:
    try:
        return Decimal(clean_row.get("Amount", "0"))
    except (ValueError, InvalidOperation) as e:
        raise ValueError(f"Invalid or missing 'Amount': {clean_row.get('Amount')}") from e


def _parse_category(clean_row: dict) -> Category:
    try:
        return Category(clean_row.get("Category"))
    except ValueError:
        return Category.OTHER


def _parse_ignored_from(clean_row: dict) -> IgnoredFrom | None:
    ignored_from_val = clean_row.get("Ignored From", "")
    try:
        return IgnoredFrom(ignored_from_val)
    except ValueError as e:
        raise ValueError(
            f"Invalid 'Ignored From' value: {clean_row.get('Ignored From')}"
        ) from e


def to_transaction(
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

    try:
        # 1. Date
        if "Date" not in clean_row:
            return None, "Missing 'Date' field"
        transaction_date = parse_date(clean_row["Date"])

        if transaction_date is None:
            return None, "Date parse failed unexpectedly"

        # 2. Name
        if "Name" not in clean_row:
            return None, "Missing 'Name' field"
        transaction_name = clean_row["Name"]

        # 3. Account Number
        transaction_account_number = _parse_account_number(clean_row)

        # 4. Amount
        transaction_amount = _parse_amount(clean_row)

        # 5. Category (Optional)
        transaction_category = _parse_category(clean_row)

        # 6. Ignored From (Optional)
        transaction_ignore = _parse_ignored_from(clean_row)

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

    except ValueError as e:
        return None, str(e)


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
