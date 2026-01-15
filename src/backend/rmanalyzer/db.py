"""
Database module for Azure Table Storage integration.
"""

import hashlib
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

from azure.data.tables import TableClient, TableTransactionError, UpdateMode
from azure.identity import DefaultAzureCredential

from .models import Transaction

logger = logging.getLogger(__name__)

# Environment variable set by our infrastructure
STORAGE_ACCOUNT_URL = os.environ.get("RM_ANALYZER_STORAGE_ACCOUNT_URL")
TRANSACTIONS_TABLE = "transactions"
SAVINGS_TABLE = "savings"


def _get_table_client(table_name: str) -> TableClient:
    """Returns a TableClient, ensuring the table exists."""
    if not STORAGE_ACCOUNT_URL:
        raise ValueError(
            "RM_ANALYZER_STORAGE_ACCOUNT_URL environment variable is not set."
        )

    credential = DefaultAzureCredential()

    # Construct the table endpoint URL safely
    # STORAGE_ACCOUNT_URL is like "https://<account>.blob.core.windows.net/"
    # We need "https://<account>.table.core.windows.net/"
    table_endpoint = STORAGE_ACCOUNT_URL.replace(".blob.", ".table.")

    client = TableClient(
        endpoint=table_endpoint, table_name=table_name, credential=credential
    )

    try:
        client.create_table()
    except Exception as e:
        # Ignore if table already exists
        if "TableAlreadyExists" not in str(e):
            logger.warning("Could not create table (might already exist): %s", e)

    return client


def _generate_row_key(t: Transaction) -> str:
    """
    Generates a deterministic unique key for a transaction to handle deduplication.
    Composite of: Date + Description + Amount + AccountNumber
    """
    unique_string = f"{t.date.isoformat()}|{t.name}|{t.amount}|{t.account_number}"
    return hashlib.sha256(unique_string.encode("utf-8")).hexdigest()


def save_transactions(transactions: List[Transaction]) -> None:
    """
    Saves a list of transactions to Azure Table Storage using upsert logic.
    """
    if not transactions:
        return

    client = _get_table_client(TRANSACTIONS_TABLE)
    timestamp = datetime.now().isoformat()

    for t in transactions:
        row_key = _generate_row_key(t)
        partition_key = t.date.strftime("%Y-%m")  # Group by Month

        entity = {
            "PartitionKey": partition_key,
            "RowKey": row_key,
            "Date": t.date.isoformat(),
            "Description": t.name,
            "Amount": float(t.amount),
            "AccountNumber": int(t.account_number),
            "Category": t.category.value if t.category else "Other",
            "IgnoredFrom": t.ignore.value if t.ignore else None,
            "ImportedAt": timestamp,
        }

        try:
            # upsert_entity with REPLACE mode will update existing entities
            client.upsert_entity(mode=UpdateMode.REPLACE, entity=entity)
        except Exception as e:
            logger.error("Failed to save transaction %s: %s", row_key, e)
            # Continue saving others even if one fails


def get_savings(month: str) -> Dict[str, Any]:
    """
    Retrieves savings data (Summary and Items) for a specific month.
    """
    client = _get_table_client(SAVINGS_TABLE)

    entities = client.query_entities(query_filter=f"PartitionKey eq '{month}'")

    items: List[Dict[str, Any]] = []
    result: Dict[str, Any] = {"startingBalance": 0.0, "items": items}

    for entity in entities:
        if entity["RowKey"] == "SUMMARY":
            result["startingBalance"] = entity.get("StartingBalance", 0.0)
        elif entity["RowKey"].startswith("ITEM_"):
            items.append(
                {"name": entity.get("Name", ""), "cost": entity.get("Cost", 0.0)}
            )

    return result


def save_savings(month: str, data: Dict[str, Any]) -> None:
    """
    Saves savings data for a month using a batch transaction (Delete All + Insert All).
    """
    client = _get_table_client(SAVINGS_TABLE)

    # 1. Fetch existing entities to delete
    existing_entities = list(
        client.query_entities(
            query_filter=f"PartitionKey eq '{month}'", select=["RowKey"]
        )
    )

    operations = []

    # 2. Add delete operations
    for entity in existing_entities:
        operations.append(("delete", entity))

    # 3. Add create operations
    # Summary
    operations.append(
        (
            "create",
            {
                "PartitionKey": month,
                "RowKey": "SUMMARY",
                "StartingBalance": float(data.get("startingBalance", 0)),
            },
        )
    )

    # Items
    for item in data.get("items", []):
        row_key = f"ITEM_{uuid.uuid4()}"
        operations.append(
            (
                "create",
                {
                    "PartitionKey": month,
                    "RowKey": row_key,
                    "Name": item.get("name", ""),
                    "Cost": float(item.get("cost", 0)),
                },
            )
        )

    if not operations:
        return

    # 4. Submit transaction (chunking if necessary)
    # Azure Table Batch is limited to 100 operations.
    BATCH_SIZE = 100
    for i in range(0, len(operations), BATCH_SIZE):
        batch = operations[i : i + BATCH_SIZE]
        try:
            client.submit_transaction(batch)
        except TableTransactionError as e:
            logger.error("Failed to submit savings batch transaction: %s", e)
            raise e
