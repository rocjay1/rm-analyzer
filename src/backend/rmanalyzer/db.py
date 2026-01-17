"""
Database module for Azure Table Storage integration.
"""

import collections
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any

from azure.core.credentials import AzureNamedKeyCredential
from azure.data.tables import TableClient, TableTransactionError, UpdateMode
from azure.identity import DefaultAzureCredential

from .models import Transaction

__all__ = [
    "save_transactions",
    "get_savings",
    "save_savings",
    "save_person",
    "get_all_people",
]

logger = logging.getLogger(__name__)

# Environment variable set by our infrastructure
STORAGE_ACCOUNT_URL = os.environ.get("STORAGE_ACCOUNT_URL")
TRANSACTIONS_TABLE = "transactions"
SAVINGS_TABLE = "savings"
PEOPLE_TABLE = "people"


def _get_table_client(table_name: str) -> TableClient:
    """Returns a TableClient, ensuring the table exists."""
    credential = DefaultAzureCredential()

    # 1. Prefer explicit Table Service URL (Local Dev / Azurite)
    table_service_url = os.environ.get("TABLE_SERVICE_URL")

    if table_service_url:
        # For local HTTP (Azurite), use the well-known account name/key
        if table_service_url.startswith("http://"):
            # Azurite well-known credentials
            client = TableClient(
                endpoint=table_service_url,
                table_name=table_name,
                credential=AzureNamedKeyCredential(
                    "devstoreaccount1",
                    "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==",
                ),
            )
        else:
            client = TableClient(
                endpoint=table_service_url, table_name=table_name, credential=credential
            )
    elif STORAGE_ACCOUNT_URL:
        # 2. Fallback to constructing from Blob URL (Production)
        # STORAGE_ACCOUNT_URL is like "https://<account>.blob.core.windows.net/"
        # We need "https://<account>.table.core.windows.net/"
        table_endpoint = STORAGE_ACCOUNT_URL.replace(".blob.", ".table.")
        client = TableClient(
            endpoint=table_endpoint, table_name=table_name, credential=credential
        )
    else:
        raise ValueError(
            "Neither TABLE_SERVICE_URL nor RM_ANALYZER_STORAGE_ACCOUNT_URL environment variable is set."
        )

    try:
        client.create_table()
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Ignore if table already exists
        if "TableAlreadyExists" not in str(e):
            logger.warning("Could not create table (might already exist): %s", e)

    return client


def _generate_row_key(t: Transaction, occurrence_index: int = 0) -> str:
    """
    Generates a deterministic unique key for a transaction to handle deduplication logic.
    Uses an occurrence index to handle identical transactions strictly within the same upload batch.
    """
    # Deterministic part including occurrence index
    unique_string = f"{t.date.isoformat()}|{t.name}|{t.amount}|{t.account_number}|{occurrence_index}"
    return hashlib.sha256(unique_string.encode("utf-8")).hexdigest()


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
        # Track occurrences of identical transactions within this partition
        # to ensure unique (but deterministic) RowKeys for duplicates in the same file.
        occurrences: dict[Any, int] = collections.defaultdict(int)

        # 3. Chunk into batches of 100
        for i in range(0, len(trans_list), 100):
            chunk = trans_list[i : i + 100]
            batch = []

            for t in chunk:
                # Calculate occurrence index for this specific transaction signature
                txn_signature = (t.date, t.name, t.amount, t.account_number)
                idx = occurrences[txn_signature]
                occurrences[txn_signature] += 1

                row_key = _generate_row_key(t, idx)

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
    Attempts to use a single atomic transaction if operations <= 100.
    Otherwise, splits into multiple batches (atomicity not guaranteed across batches).
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

    # 4. Submit transaction
    # Azure Table Batch is limited to 100 operations.
    if len(operations) <= 100:
        # Atomic Transaction
        try:
            client.submit_transaction(operations)
        except TableTransactionError as e:
            logger.error("Failed to submit atomic savings transaction: %s", e)
            raise e
    else:
        # Split Transaction (Loss of strict atomicity)
        logger.warning(
            "Savings save operation exceeds 100 items (%d). Splitting batches - atomicity not guaranteed.",
            len(operations),
        )
        batch_size = 100
        for i in range(0, len(operations), batch_size):
            batch = operations[i : i + batch_size]
            try:
                client.submit_transaction(batch)
            except TableTransactionError as e:
                logger.error("Failed to submit savings batch chunk %d: %s", i, e)
                raise e


def save_person(person: dict) -> None:
    """
    Saves a person to the People table.
    person dict must have: Name, Email, Accounts (list[int]).
    """
    client = _get_table_client(PEOPLE_TABLE)

    entity = {
        "PartitionKey": "PEOPLE",
        "RowKey": person["Email"],
        "Name": person["Name"],
        "Email": person["Email"],
        # Azure Tables doesn't support lists, store as JSON string
        "Accounts": json.dumps(person["Accounts"]),
    }

    try:
        client.upsert_entity(entity, mode=UpdateMode.REPLACE)
    except Exception as e:
        logger.error("Failed to save person %s: %s", person["Email"], e)
        raise e


def get_all_people() -> list[dict]:
    """
    Retrieves all people from the database.
    Returns a list of dicts with keys: Name, Email, Accounts (list[int]).
    """
    client = _get_table_client(PEOPLE_TABLE)
    people = []

    try:
        entities = client.query_entities(query_filter="PartitionKey eq 'PEOPLE'")
        for entity in entities:
            people.append(
                {
                    "Name": entity.get("Name"),
                    "Email": entity.get("Email", entity["RowKey"]),
                    "Accounts": json.loads(entity.get("Accounts", "[]")),
                }
            )
    except Exception as e:
        logger.error("Failed to retrieve people: %s", e)
        # If table doesn't exist or empty, return empty list is acceptable
        return []

    return people
