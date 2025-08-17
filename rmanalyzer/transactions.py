"""
Transaction parsing and helpers for RMAnalyzer.

This module provides helpers for parsing transactions and formatting currency.
"""
from datetime import datetime
import csv
from typing import Optional, List
from .models import Transaction, Category, IgnoredFrom

__all__ = ["to_transaction", "get_transactions", "to_currency"]

DATE = "%Y-%m-%d"
MONEY_FORMAT = "{0:.2f}"

def to_transaction(row: dict) -> Optional[Transaction]:
    """Convert a CSV row dict to a Transaction object, or None if invalid."""
    try:
        transaction_date = datetime.strptime(row["Date"], DATE).date()
        transaction_name = str(row["Name"])
        transaction_account_number = int(row["Account Number"])
        transaction_amount = float(row["Amount"])
        transaction_category = Category(row["Category"])
        transaction_ignore = IgnoredFrom(row["Ignored From"])
        return Transaction(
            transaction_date,
            transaction_name,
            transaction_account_number,
            transaction_amount,
            transaction_category,
            transaction_ignore,
        )
    except (ValueError, KeyError):
        return None

def get_transactions(content: str) -> List[Transaction]:
    """Parse CSV content into a list of Transaction objects."""
    rows = csv.DictReader(content.splitlines())
    transactions = []
    for row in rows:
        transaction = to_transaction(row)
        if transaction:
            transactions.append(transaction)
    return transactions

def to_currency(num: float) -> str:
    """Format a float as a currency string."""
    return MONEY_FORMAT.format(num)
