"""
Transaction parsing and handling utilities.
"""

import csv
from datetime import datetime
from typing import List, Optional, Tuple

from .models import Category, IgnoredFrom, Transaction

__all__ = ["to_transaction", "get_transactions", "to_currency"]

# Supported date formats
DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]


def parse_date(date_str: str) -> Optional[datetime.date]:
    """Parse a date string using supported formats."""
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Date '{date_str}' does not match any supported format.")


def to_transaction(row: dict) -> Tuple[Optional[Transaction], Optional[str]]:
    """
    Parses a CSV row into a Transaction object.
    Returns (Transaction, None) if successful, or (None, error_message) if not.
    """
    try:
        # Normalize keys and values
        clean_row = {k.strip(): v.strip() for k, v in row.items() if k}
    except Exception as e:
        return None, f"Unexpected error parsing row: {str(e)}"

    # Required fields
    if "Date" not in clean_row:
        return None, "Missing 'Date' field"

    try:
        transaction_date = parse_date(clean_row["Date"])
    except ValueError as e:
        return None, str(e)

    if "Name" not in clean_row:
        return None, "Missing 'Name' field"
    transaction_name = str(clean_row["Name"])

    try:
        transaction_account_number = int(clean_row["Account Number"])
    except (ValueError, KeyError):
        return (
            None,
            f"Invalid or missing 'Account Number': {clean_row.get('Account Number')}",
        )

    try:
        transaction_amount = float(clean_row["Amount"])
    except (ValueError, KeyError):
        return None, f"Invalid or missing 'Amount': {clean_row.get('Amount')}"

    # Optional / Defaulted fields
    try:
        transaction_category = Category(clean_row.get("Category"))
    except (ValueError, KeyError):
        # Treat unknown categories as OTHER
        transaction_category = Category.OTHER

    try:
        # Handle empty string for NOTHING
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


def to_currency(num: float) -> str:
    """Format a number as a currency string."""
    return f"{num:.2f}"
