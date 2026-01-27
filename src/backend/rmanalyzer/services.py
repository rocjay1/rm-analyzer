"""
Services for RMAnalyzer: storage, database, and email.
"""

import base64
import collections
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, List, Optional

from azure.communication.email import EmailClient
from azure.core.credentials import AzureNamedKeyCredential
from azure.core.exceptions import ResourceExistsError
from azure.data.tables import TableClient, TableTransactionError, UpdateMode
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.storage.queue import QueueClient

from .models import Category, Group, Transaction
from .utils import to_currency

__all__ = [
    "BlobService",
    "QueueService",
    "DatabaseService",
    "EmailService",
    "EmailRenderer",
]

logger = logging.getLogger(__name__)


# Azure Storage Device Account Key
AZURE_DEV_ACCOUNT_KEY = "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="  # pylint: disable=line-too-long


class BlobService:
    """Service for interacting with Azure Blob Storage."""

    def __init__(self) -> None:
        blob_service_url = os.environ.get("BLOB_SERVICE_URL")
        if not blob_service_url:
            raise ValueError("BLOB_SERVICE_URL environment variable is not set.")
        self._blob_service_url: str = blob_service_url

        self._container_name = os.environ.get("BLOB_CONTAINER_NAME", "csv-uploads")
        self._blob_service_client: BlobServiceClient | None = None
        self._container_clients: dict[str, ContainerClient] = {}

    def _get_blob_service_client(self) -> BlobServiceClient:
        """Returns a BlobServiceClient."""
        if self._blob_service_client:
            return self._blob_service_client

        if self._blob_service_url.startswith("http://"):
            # Azurite well-known credentials
            self._blob_service_client = BlobServiceClient(
                account_url=self._blob_service_url,
                credential=AZURE_DEV_ACCOUNT_KEY,
            )
        else:
            # Production
            self._blob_service_client = BlobServiceClient(
                account_url=self._blob_service_url,
                credential=DefaultAzureCredential(),
            )
        return self._blob_service_client

    def _get_container_client(self, container_name: str) -> ContainerClient:
        """Returns a ContainerClient, ensuring the container exists. Cached per instance."""
        if container_name in self._container_clients:
            return self._container_clients[container_name]

        client = self._get_blob_service_client()
        container_client = client.get_container_client(container_name)

        try:
            container_client.create_container()
        except ResourceExistsError:
            pass  # Container already exists
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("Could not create container: %s", e)

        self._container_clients[container_name] = container_client
        return container_client

    def upload_csv(self, file_name: str, content: bytes) -> str:
        """
        Uploads CSV content to the blob container.
        Returns the URL of the uploaded blob.
        """
        container_client = self._get_container_client(self._container_name)
        blob_client = container_client.get_blob_client(file_name)
        blob_client.upload_blob(content, overwrite=True)

        return blob_client.url

    def download_csv(self, file_name: str) -> str:
        """
        Downloads CSV content from the blob container as a string.
        """
        container_client = self._get_container_client(self._container_name)
        blob_client = container_client.get_blob_client(file_name)

        download_stream = blob_client.download_blob()
        return download_stream.readall().decode("utf-8")


class QueueService:  # pylint: disable=too-few-public-methods
    """Service for interacting with Azure Queue Storage."""

    def __init__(self) -> None:
        queue_service_url = os.environ.get("QUEUE_SERVICE_URL")
        if not queue_service_url:
            raise ValueError("QUEUE_SERVICE_URL environment variable is not set.")
        self._queue_service_url: str = queue_service_url

        self._queue_name = os.environ.get("QUEUE_NAME", "csv-processing")
        self._queue_clients: dict[str, QueueClient] = {}

    def _get_queue_client(self, queue_name: str) -> QueueClient:
        """Returns a QueueClient, ensuring the queue exists. Cached per instance."""
        if queue_name in self._queue_clients:
            return self._queue_clients[queue_name]

        if self._queue_service_url.startswith("http://"):
            # Azurite well-known credentials
            client = QueueClient(
                account_url=self._queue_service_url,
                queue_name=queue_name,
                credential=AZURE_DEV_ACCOUNT_KEY,
            )
        else:
            # Production
            client = QueueClient(
                account_url=self._queue_service_url,
                queue_name=queue_name,
                credential=DefaultAzureCredential(),
            )

        try:
            client.create_queue()
        except ResourceExistsError:
            pass  # Queue already exists, ignore
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("Could not create queue: %s", e)

        self._queue_clients[queue_name] = client
        return client

    def enqueue_message(self, message: dict[str, Any]) -> None:
        """
        Enqueues a message to the processing queue.
        Message is JSON encoded and Base64 encoded (standard for Azure Functions Queue Trigger).
        """
        client = self._get_queue_client(self._queue_name)

        # Azure Functions usually expects base64 encoded string if not using binding native types,
        # but the python SDK handles generic text. Let's send plain JSON string;
        # the QueueTrigger will receive it.
        message_str = json.dumps(message)

        # Base64 encoding is standard for Azure Functions Queue Trigger
        message_bytes = message_str.encode("utf-8")
        message_b64 = base64.b64encode(message_bytes).decode("utf-8")

        client.send_message(message_b64)


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

    def save_transactions(self, transactions: list[Transaction]) -> None:
        """
        Saves a list of transactions to Azure Table Storage using batched upserts.
        Groups by PartitionKey (Tenant_Month) first, then chunks into batches of 100.
        """
        if not transactions:
            return

        client = self._get_table_client(self._transactions_table)
        timestamp = datetime.now().isoformat()

        # Group by PartitionKey (Tenant_Month) to satisfy batch requirements
        partitions = collections.defaultdict(list)
        for t in transactions:
            # Partition Strategy: Tenant_Month
            pk = f"default_{t.date.strftime('%Y-%m')}"
            partitions[pk].append(t)

        # Process each partition group
        for pk, trans_list in partitions.items():
            # Track occurrences of identical transactions within this partition
            # to ensure unique (but deterministic) RowKeys for duplicates in the same file.
            occurrences: dict[Any, int] = collections.defaultdict(int)

            # Chunk into batches of 100
            for i in range(0, len(trans_list), 100):
                chunk = trans_list[i : i + 100]
                batch = []

                for t in chunk:
                    # Calculate occurrence index for this specific transaction signature
                    txn_signature = (t.date, t.name, t.amount, t.account_number)
                    occurrences[txn_signature] += 1
                    idx = occurrences[txn_signature] - 1

                    # Add to batch as an "upsert" operation (REPLACE mode)
                    batch.append(
                        (
                            "upsert",
                            self._create_transaction_entity(
                                t, pk, self._generate_row_key(t, idx), timestamp
                            ),
                            {"mode": UpdateMode.REPLACE},
                        )
                    )

                try:
                    if batch:
                        client.submit_transaction(batch)
                except TableTransactionError as e:
                    logger.error("Failed to submit batch for partition %s: %s", pk, e)

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


class EmailRenderer:
    """Service for rendering email content."""

    @staticmethod
    def _render_error_section(errors: Optional[List[str]]) -> str:
        """Renders the error section using f-strings."""
        if not errors:
            return ""

        error_items = "".join([f"<li>{e}</li>" for e in errors])
        return f"""
        <div style="background-color: #fff4f4; border-left: 5px solid #d13438; padding: 15px; margin-bottom: 20px;">
            <h3 style="color: #d13438; margin-top: 0; font-size: 18px;">⚠️ Warning: Some transactions were skipped</h3>
            <ul style="margin-bottom: 0; padding-left: 20px;">
                {error_items}
            </ul>
        </div>
        """

    @classmethod
    def render_error_body(cls, errors: List[str]) -> str:
        """Renders the body for an error email."""
        return f"""
        <html>
        <body style="font-family: 'Segoe UI', sans-serif; color: #333; line-height: 1.6; background-color: #f4f4f4; margin: 0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <div style="background-color: #d13438; padding: 20px; text-align: center; color: white;">
                    <h2 style="margin: 0;">Upload Failed</h2>
                </div>
                <div style="padding: 20px;">
                    <p>The uploaded CSV could not be processed due to the following errors:</p>
                    {cls._render_error_section(errors)}
                </div>
            </div>
        </body>
        </html>
        """

    @staticmethod
    def _render_rows(group: Group, tracked_categories: List[Category]) -> str:
        """Helper to render table rows."""
        rows_html = ""
        for p in group.members:
            row_cells = f"<td>{p.name}</td>"
            for c in tracked_categories:
                row_cells += f"<td>{to_currency(p.get_expenses(c))}</td>"
            row_cells += (
                f"<td style='font-weight: bold;'>{to_currency(p.get_expenses())}</td>"
            )
            rows_html += f"<tr>{row_cells}</tr>"

        # Difference Row (if 2 members)
        if len(group.members) == 2:
            p1, p2 = group.members
            diff_cells = "<td>Difference</td>"
            for c in tracked_categories:
                diff_cells += (
                    f"<td>{to_currency(group.get_expenses_difference(p1, p2, c))}</td>"
                )
            diff_cells += (
                f"<td style='font-weight: bold;'>"
                f"{to_currency(group.get_expenses_difference(p1, p2))}</td>"
            )
            rows_html += f"<tr style='background-color: #f8f9fa;'>{diff_cells}</tr>"
        return rows_html

    @classmethod
    def render_body(cls, group: Group, errors: Optional[List[str]] = None) -> str:
        """Generate the HTML body of the email based on the group's expenses."""
        tracked_categories: List[Category] = [
            c for c in Category if c != Category.OTHER
        ]

        # Build Table Headers
        headers_html = "<th></th>"
        for c in tracked_categories:
            headers_html += f"<th>{c.value}</th>"
        headers_html += "<th>Total</th>"

        # Build Table Rows
        rows_html = cls._render_rows(group, tracked_categories)

        # Debt Message
        debt_html = ""
        if len(group.members) == 2:
            p1, p2 = group.members
            msg = (
                f"{p1.name} owes {p2.name}: "
                f"<strong>{to_currency(group.get_debt(p1, p2))}</strong>"
            )
            debt_html = f"""
            <div style="margin-top: 25px; font-size: 16px; background-color: #f0f6ff; padding: 15px; border-radius: 4px; border: 1px solid #c7e0f4; color: #005a9e; text-align: center;">
                {msg}
            </div>
            """

        # Construct Full Body
        min_date = group.get_oldest_transaction()
        max_date = group.get_newest_transaction()
        date_range = (
            f"{min_date.strftime('%m/%d/%y')} - {max_date.strftime('%m/%d/%y')}"
        )

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; line-height: 1.6; background-color: #f4f4f4; margin: 0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <!-- Header -->
                <div style="background-color: #0078D4; padding: 20px; text-align: center; color: white;">
                    <h2 style="margin: 0; font-weight: 600;">Expense Summary</h2>
                    <p style="margin: 5px 0 0; opacity: 0.9;">{date_range}</p>
                </div>

                <div style="padding: 20px;">
                    {cls._render_error_section(errors)}

                    <div style="overflow-x: auto;">
                        <table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px;">
                            <thead>
                                <tr style="background-color: #f8f9fa; text-align: left;">
                                    {headers_html}
                                </tr>
                            </thead>
                            <tbody>
                                {rows_html}
                            </tbody>
                        </table>
                    </div>

                    {debt_html}
                </div>

                <!-- Footer -->
                <div style="padding: 15px; text-align: center; font-size: 12px; color: #666; border-top: 1px solid #eee;">
                    <p>Generated by RM Analyzer</p>
                </div>
            </div>

            <!-- CSS for Table Cells (Inline styles are safest for email, but this helps in some clients) -->
            <style>
                th, td {{ padding: 12px; border-bottom: 1px solid #e0e0e0; }}
                th {{ font-weight: 600; color: #666; }}
                tr:last-child td {{ border-bottom: none; }}
            </style>
        </body>
        </html>
        """

    @staticmethod
    def render_subject(group: Group) -> str:
        """Generate the email subject based on the transaction date range."""
        min_date = group.get_oldest_transaction()
        max_date = group.get_newest_transaction()
        return (
            f"Transactions Summary: {min_date.strftime('%m/%d/%y')} - "
            f"{max_date.strftime('%m/%d/%y')}"
        )


class EmailService:
    """Service for sending emails via Azure Communication Services."""

    def __init__(self) -> None:
        self._endpoint = os.environ.get("COMMUNICATION_SERVICES_ENDPOINT")
        self._sender = os.environ.get("SENDER_EMAIL")

        if not self._endpoint:
            raise ValueError(
                "COMMUNICATION_SERVICES_ENDPOINT environment variable is not set."
            )
        if not self._sender:
            raise ValueError("SENDER_EMAIL environment variable is not set.")

        self._email_client: EmailClient | None = None

    def _get_email_client(self) -> EmailClient:
        """Returns an EmailClient, creating it if necessary."""
        if self._email_client:
            return self._email_client

        # Ensure endpoint is present (already validated in __init__)
        assert self._endpoint is not None

        credential = DefaultAzureCredential()
        self._email_client = EmailClient(endpoint=self._endpoint, credential=credential)
        return self._email_client

    def send_email(self, to: list[str], subject: str, body: str) -> None:
        """Send an email using Azure Communication Services and Managed Identity."""
        try:
            email_client = self._get_email_client()

            message = {
                "senderAddress": self._sender,
                "recipients": {
                    "to": [{"address": email} for email in to],
                },
                "content": {
                    "subject": subject,
                    "plainText": "Please view this email in a client that supports HTML.",
                    "html": body,
                },
            }

            poller = email_client.begin_send(message)
            result = poller.result()

            # Extract message ID (result might be dict or object)
            message_id = None
            if isinstance(result, dict):
                message_id = (
                    result.get("messageId")
                    or result.get("message_id")
                    or result.get("id")
                )
            else:
                message_id = getattr(result, "message_id", None) or getattr(
                    result, "id", None
                )

            if message_id:
                logger.info("Email sent with message ID: %s", message_id)
            else:
                logger.info("Email sent successfully")

        except Exception as ex:
            logger.error("Error sending email: %s", ex)
            raise

    def send_error_email(self, recipients: list[str], errors: list[str]) -> None:
        """Helper to send an email with validation errors."""
        subject = "RMAnalyzer - Upload Failed"
        body = EmailRenderer.render_error_body(errors)
        self.send_email(recipients, subject, body)
