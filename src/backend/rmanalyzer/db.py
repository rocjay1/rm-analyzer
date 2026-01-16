"""
Database module for Azure Table Storage integration.
"""

import collections
import hashlib
import logging
import os
import uuid
from datetime import datetime
from typing import Any

from azure.data.tables import TableClient, TableTransactionError, UpdateMode
from azure.identity import DefaultAzureCredential

from .models import Transaction

logger = logging.getLogger(__name__)

# Environment variable set by our infrastructure
STORAGE_ACCOUNT_URL = os.environ.get("STORAGE_ACCOUNT_URL")
TRANSACTIONS_TABLE = "transactions"
SAVINGS_TABLE = "savings"


def _get_table_client(table_name: str) -> TableClient:
    """Returns a TableClient, ensuring the table exists."""
    if not STORAGE_ACCOUNT_URL:
        raise ValueError("STORAGE_ACCOUNT_URL environment variable is not set.")

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
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Ignore if table already exists
        if "TableAlreadyExists" not in str(e):
            logger.warning("Could not create table (might already exist): %s", e)

    return client


def _generate_row_key(t: Transaction) -> str:
    """
    Generates a deterministic unique key for a transaction to handle deduplication logic,
    but appends a salt to ensure true uniqueness for identical transactions.
    """
    # Deterministic part
    unique_string = f"{t.date.isoformat()}|{t.name}|{t.amount}|{t.account_number}"
    base_hash = hashlib.sha256(unique_string.encode("utf-8")).hexdigest()

    # Non-deterministic random suffix to prevent legitimate duplicates from being overwritten
    random_suffix = str(uuid.uuid4())[:8]

    return f"{base_hash}-{random_suffix}"


def save_transactions(transactions: list[Transaction]) -> None:
    """
    Saves a list of transactions to Azure Table Storage using batched upserts.
    Groups by PartitionKey (Tenant_Month) first, then chunks into batches of 100.
    """
    if not transactions:
        return

    client = _get_table_client(TRANSACTIONS_TABLE)
    timestamp = datetime.now().isoformat()
    # Default tenant for now
    tenant_id = "default"

    # 1. Group by PartitionKey (Tenant_Month) to satisfy batch requirements
    partitions = collections.defaultdict(list)
    for t in transactions:
        # Partition Strategy: Tenant_Month
        pk = f"{tenant_id}_{t.date.strftime('%Y-%m')}"
        partitions[pk].append(t)

    # 2. Process each partition group
    for pk, trans_list in partitions.items():
        # 3. Chunk into batches of 100
        for i in range(0, len(trans_list), 100):
            chunk = trans_list[i : i + 100]
            batch = []

            for t in chunk:
                row_key = _generate_row_key(t)

                entity = {
                    "PartitionKey": pk,
                    "RowKey": row_key,
                    "Date": t.date.isoformat(),
                    "Description": t.name,
                    # Convert Decimal to float for Table Storage
                    "Amount": float(t.amount),
                    "AccountNumber": int(t.account_number),
                    "Category": t.category.value if t.category else "Other",
                    "IgnoredFrom": t.ignore.value if t.ignore else None,
                    "ImportedAt": timestamp,
                }
                # Add to batch as an "upsert" operation (REPLACE mode)
                batch.append(("upsert", entity, {"mode": UpdateMode.REPLACE}))

            try:
                if batch:
                    client.submit_transaction(batch)
            except TableTransactionError as e:
                logger.error("Failed to submit batch for partition %s: %s", pk, e)
                # Depending on requirements, might want to raise or continue
                # For now, we log and continue to attempt other batches.


def get_savings(month: str) -> dict[str, object]:
    """
    Retrieves savings data (Summary and Items) for a specific month.
    """
    client = _get_table_client(SAVINGS_TABLE)

    entities = client.query_entities(query_filter=f"PartitionKey eq '{month}'")

    items: list[dict[str, object]] = []
    result: dict[str, object] = {"startingBalance": 0.0, "items": items}

    for entity in entities:
        if entity["RowKey"] == "SUMMARY":
            result["startingBalance"] = entity.get("StartingBalance", 0.0)
        elif entity["RowKey"].startswith("ITEM_"):
            items.append(
                {"name": entity.get("Name", ""), "cost": entity.get("Cost", 0.0)}
            )

    return result


def save_savings(month: str, data: dict[str, object]) -> None:
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

    operations: list[tuple[str, dict[str, Any]]] = []

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
                "StartingBalance": float(data.get("startingBalance", 0)),  # type: ignore
            },
        )
    )

    # Items
    items_data = data.get("items", [])
    if isinstance(items_data, list):
        for item in items_data:
            if isinstance(item, dict):
                row_key = f"ITEM_{uuid.uuid4()}"
                operations.append(
                    (
                        "create",
                        {
                            "PartitionKey": month,
                            "RowKey": row_key,
                            "Name": item.get("name", ""),
                            "Cost": float(item.get("cost", 0)),  # type: ignore
                        },
                    )
                )

    if not operations:
        return

    # 4. Submit transaction (chunking if necessary)
    # Azure Table Batch is limited to 100 operations.
    batch_size = 100
    for i in range(0, len(operations), batch_size):
        batch = operations[i : i + batch_size]
        try:
            client.submit_transaction(batch)
        except TableTransactionError as e:
            logger.error("Failed to submit savings batch transaction: %s", e)
            raise e
