"""
Utility functions for parsing and formatting.
"""

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple, Dict

from .models import Category, IgnoredFrom, Transaction

__all__ = ["parse_date", "to_transaction", "get_transactions", "to_currency"]


# Supported date formats
DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]


def parse_date(date_str: str) -> Optional[date]:
    """Parse a date string using supported formats."""
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Date '{date_str}' does not match any supported format.")


def to_transaction(  # pylint: disable=too-many-return-statements
    row: Dict[str, str],
) -> Tuple[Optional[Transaction], Optional[str]]:
    """
    Parses a CSV row into a Transaction object.
    Returns (Transaction, None) if successful, or (None, error_message) if not.
    """
    # Normalize keys and values
    try:
        clean_row = {k.strip(): v.strip() for k, v in row.items() if k}
    except AttributeError:
        return None, "Unexpected error: row is not a valid dictionary"

    # Date
    if "Date" not in clean_row:
        return None, "Missing 'Date' field"
    try:
        transaction_date = parse_date(clean_row["Date"])
    except ValueError as e:
        return None, str(e)

    if transaction_date is None:
        return None, "Date parse failed unexpectedly"

    # Name
    if "Name" not in clean_row:
        return None, "Missing 'Name' field"
    transaction_name = clean_row["Name"]

    # Account Number
    try:
        transaction_account_number = int(clean_row.get("Account Number", ""))
    except ValueError:
        return (
            None,
            f"Invalid or missing 'Account Number': {clean_row.get('Account Number')}",
        )

    # Amount
    try:
        # Use Decimal for financial calculations
        transaction_amount = Decimal(clean_row.get("Amount", "0"))
    except (ValueError, InvalidOperation):
        return None, f"Invalid or missing 'Amount': {clean_row.get('Amount')}"

    # Category (Optional)
    try:
        transaction_category = Category(clean_row.get("Category"))
    except ValueError:
        # Treat unknown categories as OTHER
        transaction_category = Category.OTHER

    # Ignored From (Optional)
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


def get_transactions(content: str) -> Tuple[List[Transaction], List[str]]:
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
