from datetime import datetime
import csv
from typing import Optional, List
from .models import Transaction, Category, IgnoredFrom

__all__ = ["to_transaction", "get_transactions", "to_currency"]

DATE = "%Y-%m-%d"
MONEY_FORMAT = "{0:.2f}"

def to_transaction(row: dict) -> Optional[Transaction]:
    try:
        # Normalize keys and values
        clean_row = {k.strip(): v.strip() for k, v in row.items() if k}

        transaction_date = datetime.strptime(clean_row["Date"], DATE).date()
        transaction_name = str(clean_row["Name"])
        transaction_account_number = int(clean_row["Account Number"])
        transaction_amount = float(clean_row["Amount"])
        transaction_category = Category(clean_row["Category"])
        transaction_ignore = IgnoredFrom(clean_row["Ignored From"])
        return Transaction(
            transaction_date,
            transaction_name,
            transaction_account_number,
            transaction_amount,
            transaction_category,
            transaction_ignore,
        )
    except (ValueError, KeyError, AttributeError):
        return None

def get_transactions(content: str) -> List[Transaction]:
    # Filter out empty lines before parsing
    lines = [line for line in content.splitlines() if line.strip()]
    rows = csv.DictReader(lines)
    transactions = []

    # Handle case where fieldnames might have whitespace
    if rows.fieldnames:
        rows.fieldnames = [name.strip() for name in rows.fieldnames]

    for row in rows:
        transaction = to_transaction(row)
        if transaction:
            transactions.append(transaction)
    return transactions

def to_currency(num: float) -> str:
    return MONEY_FORMAT.format(num)
