"""Service for interacting with Azure Table Storage."""

import collections
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, date
from decimal import Decimal

from typing import Any

from azure.core.credentials import AzureNamedKeyCredential
from azure.data.tables import TableClient, TableTransactionError, UpdateMode
from azure.identity import DefaultAzureCredential

from ..models import Transaction, Account, CreditCard
from .constants import AZURE_DEV_ACCOUNT_KEY

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for interacting with Azure Table Storage."""

    def __init__(self) -> None:
        self._table_clients: dict[str, TableClient] = {}
        url = os.environ.get("TABLE_SERVICE_URL")
        if not url:
            raise ValueError("TABLE_SERVICE_URL environment variable is not set.")
        self._table_service_url = url

        self._transactions_table = os.environ.get("TRANSACTIONS_TABLE", "transactions")
        self._savings_table = os.environ.get("SAVINGS_TABLE", "savings")
        self._people_table = os.environ.get("PEOPLE_TABLE", "people")
        self._accounts_table = os.environ.get("ACCOUNTS_TABLE", "accounts")
        self._credit_cards_table = os.environ.get("CREDIT_CARDS_TABLE", "creditcards")

    def _get_table_client(self, table_name: str) -> TableClient:
        """Returns a TableClient, ensuring the table exists. Cached per instance."""
        if table_name in self._table_clients:
            return self._table_clients[table_name]

        # Azurite well-known credentials
        if self._table_service_url.startswith("http://"):
            client = TableClient(
                endpoint=self._table_service_url,
                table_name=table_name,
                credential=AzureNamedKeyCredential(
                    "devstoreaccount1",
                    AZURE_DEV_ACCOUNT_KEY,
                ),
            )
        else:
            client = TableClient(
                endpoint=self._table_service_url,
                table_name=table_name,
                credential=DefaultAzureCredential(),
            )

        try:
            client.create_table()
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Ignore if table already exists
            if "TableAlreadyExists" not in str(e):
                logger.warning("Could not create table (might already exist): %s", e)

        self._table_clients[table_name] = client
        return client

    def _generate_row_key(self, t: Transaction, occurrence_index: int = 0) -> str:
        """
        Generates a deterministic unique key for a transaction to handle deduplication logic.
        Uses an occurrence index to handle identical transactions strictly within
        the same upload batch.
        """
        # Deterministic part including occurrence index
        unique_string = (
            f"{t.date.isoformat()}|{t.name}|{t.amount}|"
            f"{t.account_number}|{occurrence_index}"
        )
        return hashlib.sha256(unique_string.encode("utf-8")).hexdigest()

    def save_transactions(self, transactions: list[Transaction]) -> list[Transaction]:
        """
        Saves a list of transactions to Azure Table Storage using batched upserts.
        Groups by PartitionKey (Tenant_Month) first.
        Returns a list of transactions that were ACTUALLY new (not previously in DB).
        """
        if not transactions:
            return []

        client = self._get_table_client(self._transactions_table)
        timestamp = datetime.now().isoformat()
        new_transactions = []

        # Group by PartitionKey (Tenant_Month)
        partitions = collections.defaultdict(list)
        for t in transactions:
            pk = f"default_{t.date.strftime('%Y-%m')}"
            partitions[pk].append(t)

        # Process each partition
        for pk, trans_list in partitions.items():
            # 1. Calculate RowKeys for all potential transactions
            occurrences: dict[Any, int] = collections.defaultdict(int)
            trans_with_keys = []

            for t in trans_list:
                txn_signature = (t.date, t.name, t.amount, t.account_number)
                occurrences[txn_signature] += 1
                idx = occurrences[txn_signature] - 1
                row_key = self._generate_row_key(t, idx)
                trans_with_keys.append((t, row_key))

            # 2. Check for existing RowKeys in this partition
            # Querying all RowKeys in partition is safer for bulk checks.
            try:
                # Select only RowKey to minimize payload
                existing_entities = client.query_entities(
                    query_filter=f"PartitionKey eq '{pk}'", select=["RowKey"]
                )
                existing_keys = {e["RowKey"] for e in existing_entities}
            except Exception as e:
                logger.warning(
                    "Failed to query existing transactions for partition %s: %s", pk, e
                )
                existing_keys = set()

            # 3. Filter New vs Existing
            batch = []
            for t, rk in trans_with_keys:
                if rk not in existing_keys:
                    new_transactions.append(t)
                    # Add to batch
                    batch.append(
                        (
                            "upsert",
                            self._create_transaction_entity(t, pk, rk, timestamp),
                            {"mode": UpdateMode.REPLACE},
                        )
                    )

            # 4. Submit Batch(es)
            if batch:
                # Chunk into 100s
                for i in range(0, len(batch), 100):
                    sub_batch = batch[i : i + 100]
                    try:
                        client.submit_transaction(sub_batch)
                    except TableTransactionError as e:
                        logger.error(
                            "Failed to submit batch for partition %s: %s", pk, e
                        )

        return new_transactions

    def _create_transaction_entity(
        self, t: Transaction, partition_key: str, row_key: str, timestamp: str
    ) -> dict[str, Any]:
        """Helper to create a transaction entity dict."""
        return {
            "PartitionKey": partition_key,
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

    def get_savings(self, month: str, user_id: str) -> dict[str, object] | None:
        """
        Retrieves savings data (Summary and Items) for a specific month and user.
        """
        client = self._get_table_client(self._savings_table)
        partition_key = f"{user_id}_{month}"

        entities = client.query_entities(
            query_filter=f"PartitionKey eq '{partition_key}'"
        )

        items: list[dict[str, object]] = []
        result: dict[str, object] = {"startingBalance": 0.0, "items": items}

        found_any = False
        for entity in entities:
            found_any = True
            if entity["RowKey"] == "SUMMARY":
                result["startingBalance"] = entity.get("StartingBalance", 0.0)
            elif entity["RowKey"].startswith("ITEM_"):
                items.append(
                    {"name": entity.get("Name", ""), "cost": entity.get("Cost", 0.0)}
                )

        if not found_any:
            return None

        return result

    def save_savings(self, month: str, data: dict[str, object], user_id: str) -> None:
        """
        Saves savings data for a month and user using a batch transaction (Delete All + Insert All).
        Attempts to use a single atomic transaction if operations <= 100.
        Otherwise, splits into multiple batches (atomicity not guaranteed across batches).
        """
        client = self._get_table_client(self._savings_table)
        partition_key = f"{user_id}_{month}"

        # Fetch existing entities to delete
        existing_entities = list(
            client.query_entities(
                query_filter=f"PartitionKey eq '{partition_key}'",
                select=["PartitionKey", "RowKey"],
            )
        )

        operations: list[tuple[str, Any] | tuple[str, Any, dict[str, Any]]] = []

        if existing_entities:
            operations.extend(
                [
                    ("delete", entity)
                    for entity in existing_entities
                    if entity["RowKey"] != "SUMMARY"
                ]
            )

        # Add create operations
        operations.extend(self._create_savings_upserts(partition_key, data))

        if not operations:
            return

        # Submit transaction
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
                "Savings save operation exceeds 100 items (%d). "
                "Splitting batches - atomicity not guaranteed.",
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

    def _create_savings_upserts(
        self, partition_key: str, data: dict[str, object]
    ) -> list[tuple[str, Any] | tuple[str, Any, dict[str, Any]]]:
        """Helper to create savings upsert operations."""
        ops: list[tuple[str, Any] | tuple[str, Any, dict[str, Any]]] = []

        # Summary
        ops.append(
            (
                "upsert",
                {
                    "PartitionKey": partition_key,
                    "RowKey": "SUMMARY",
                    "StartingBalance": float(data.get("startingBalance", 0)),  # type: ignore
                },
                {"mode": UpdateMode.REPLACE},
            )
        )

        # Items
        items_data = data.get("items", [])
        if isinstance(items_data, list):
            for item in items_data:
                if isinstance(item, dict):
                    row_key = f"ITEM_{uuid.uuid4()}"
                    ops.append(
                        (
                            "create",
                            {
                                "PartitionKey": partition_key,
                                "RowKey": row_key,
                                "Name": item.get("name", ""),
                                "Cost": float(item.get("cost", 0)),  # type: ignore
                            },
                        )
                    )
        return ops

    def save_person(self, person: dict) -> None:
        """
        Saves a person to the People table.
        person dict must have: Name, Email, Accounts (list[int]).
        """
        client = self._get_table_client(self._people_table)

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

    def get_all_people(self) -> list[dict]:
        """
        Retrieves all people from the database.
        Returns a list of dicts with keys: Name, Email, Accounts (list[int]).
        """
        client = self._get_table_client(self._people_table)
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
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Failed to retrieve people: %s", e)
            # If table doesn't exist or empty, return empty list is acceptable
            return []

        return people

    def upsert_accounts(self, accounts: list[Account], user_email: str) -> None:
        """Upserts a list of accounts for a specific user."""
        if not accounts:
            return

        client = self._get_table_client(self._accounts_table)

        batch = []
        for account in accounts:
            batch.append(
                (
                    "upsert",
                    self._create_account_entity(account, user_email),
                    {"mode": UpdateMode.REPLACE},
                )
            )

        # Chunk into 100
        for i in range(0, len(batch), 100):
            try:
                client.submit_transaction(batch[i : i + 100])
            except TableTransactionError as e:
                logger.error("Failed to upsert accounts batch: %s", e)
                raise e

    def _create_account_entity(
        self, account: Account, partition_key: str
    ) -> dict[str, Any]:
        """Helper to create an account entity dict."""
        return {
            "PartitionKey": partition_key,
            "RowKey": account.id,
            "Name": account.name,
            "Mask": account.mask,
            "Institution": account.institution,
            "CurrentBalance": float(account.current_balance),
            "CreditLimit": float(account.credit_limit),
            "Type": account.type,
            "UpdatedAt": datetime.now().isoformat(),
        }

    def get_credit_cards(self) -> list[CreditCard]:
        """Retrieves all configured credit cards."""
        client = self._get_table_client(self._credit_cards_table)
        cards = []

        try:
            entities = client.query_entities(
                query_filter="PartitionKey eq 'CREDIT_CARDS'"
            )
            for entity in entities:
                last_rec_str = entity.get("LastReconciled")
                last_rec = date.fromisoformat(last_rec_str) if last_rec_str else None
                cards.append(
                    CreditCard(
                        id=entity["RowKey"],
                        name=entity.get("Name", "Unknown Card"),
                        account_number=int(entity.get("AccountNumber", 0)),
                        credit_limit=Decimal(str(entity.get("CreditLimit", 0))),
                        due_day=int(entity.get("DueDay", 1)),
                        statement_balance=Decimal(
                            str(entity.get("StatementBalance", 0))
                        ),
                        current_balance=Decimal(str(entity.get("CurrentBalance", 0))),
                        last_reconciled=last_rec,
                    )
                )
        except Exception as e:
            logger.error("Failed to retrieve credit cards: %s", e)
            return []

        return cards

    def save_credit_card(self, card: CreditCard) -> None:
        """Upserts a credit card configuration."""
        client = self._get_table_client(self._credit_cards_table)
        entity = {
            "PartitionKey": "CREDIT_CARDS",
            "RowKey": card.id,
            "Name": card.name,
            "AccountNumber": int(card.account_number),
            "CreditLimit": float(card.credit_limit),
            "DueDay": int(card.due_day),
            "StatementBalance": float(card.statement_balance),
            "CurrentBalance": float(card.current_balance),
        }
        if card.last_reconciled:
            entity["LastReconciled"] = card.last_reconciled.isoformat()
        try:
            client.upsert_entity(entity, mode=UpdateMode.REPLACE)
        except Exception as e:
            logger.error("Failed to save credit card %s: %s", card.name, e)
            raise e

    def update_card_balance(self, account_number: int, delta: Decimal) -> None:
        """
        Atomically updates a card's current balance.
        Finds card by AccountNumber (inefficient scan if RowKey != AccountNumber,
        but we'll assume RowKey IS AccountNumber or we query first).
        Actually, we should make RowKey = AccountNumberStr for easy lookup.
        """
        client = self._get_table_client(self._credit_cards_table)
        row_key = str(account_number)

        try:
            entity = client.get_entity(partition_key="CREDIT_CARDS", row_key=row_key)
            current_bal = Decimal(str(entity.get("CurrentBalance", 0)))
            new_bal = current_bal + delta

            # Update
            entity["CurrentBalance"] = float(new_bal)
            client.update_entity(entity, mode=UpdateMode.REPLACE)
            logger.info(
                "Updated balance for card %s: %s -> %s", row_key, current_bal, new_bal
            )
        except Exception as e:
            # Try to find by AccountNumber if RowKey mismatch (less efficient)
            try:
                entities = list(
                    client.query_entities(
                        query_filter=f"PartitionKey eq 'CREDIT_CARDS' and AccountNumber eq {account_number}"
                    )
                )
                if entities:
                    entity = entities[0]
                    current_bal = Decimal(str(entity.get("CurrentBalance", 0)))
                    new_bal = current_bal + delta
                    entity["CurrentBalance"] = float(new_bal)
                    client.update_entity(entity, mode=UpdateMode.REPLACE)
                    logger.info(
                        "Updated balance for card (query) %s: %s -> %s",
                        account_number,
                        current_bal,
                        new_bal,
                    )
                    return
                # If still not found
                logger.error(
                    "Failed to update balance for card %s: %s. Card might not exist.",
                    row_key,
                    e,
                )
            except Exception as e2:
                logger.error(
                    "Failed to update balance (fallback) for card %s: %s.",
                    account_number,
                    e2,
                )
