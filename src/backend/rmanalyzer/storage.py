"""
Storage utilities for Azure Blob and Queue.
"""

import base64
import json
import logging
import os
from typing import Any

from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueClient

from .utils import AZURE_DEV_ACCOUNT_KEY

__all__ = [
    "BlobService",
    "BlobService",
    "QueueService",
]

logger = logging.getLogger(__name__)


class BlobService:
    """Service for interacting with Azure Blob Storage."""

    def __init__(self) -> None:
        self._blob_service_url = os.environ.get("BLOB_SERVICE_URL")
        if not self._blob_service_url:
            raise ValueError("BLOB_SERVICE_URL environment variable is not set.")

        self._container_name = os.environ.get("BLOB_CONTAINER_NAME", "csv-uploads")
        self._blob_client: BlobServiceClient | None = None

    def _get_blob_service_client(self) -> BlobServiceClient:
        """Returns a BlobServiceClient."""
        if self._blob_client:
            return self._blob_client

        # Check for Azurite for local development
        if self._blob_service_url.startswith("http://"):  # type: ignore
            # Azurite well-known credentials
            self._blob_client = BlobServiceClient(
                account_url=self._blob_service_url,  # type: ignore
                credential=AZURE_DEV_ACCOUNT_KEY,
            )
        else:
            # Production
            self._blob_client = BlobServiceClient(
                account_url=self._blob_service_url, credential=DefaultAzureCredential()  # type: ignore
            )
        return self._blob_client

    def upload_csv(self, file_name: str, content: bytes) -> str:
        """
        Uploads CSV content to the blob container.
        Returns the URL of the uploaded blob.
        """
        client = self._get_blob_service_client()
        container_client = client.get_container_client(self._container_name)

        # Ensure container exists (idempotent usually, or pre-created by terraform)
        if not container_client.exists():
            try:
                container_client.create_container()
            except ResourceExistsError:
                pass  # Container already exists
            except Exception as e:  # pylint: disable=broad-except
                logger.warning("Could not create container: %s", e)

        blob_client = container_client.get_blob_client(file_name)
        blob_client.upload_blob(content, overwrite=True)

        return blob_client.url

    def download_csv(self, file_name: str) -> str:
        """
        Downloads CSV content from the blob container as a string.
        """
        client = self._get_blob_service_client()
        container_client = client.get_container_client(self._container_name)
        blob_client = container_client.get_blob_client(file_name)

        download_stream = blob_client.download_blob()
        return download_stream.readall().decode("utf-8")


class QueueService:
    """Service for interacting with Azure Queue Storage."""

    def __init__(self) -> None:
        self._queue_service_url = os.environ.get("QUEUE_SERVICE_URL")
        if not self._queue_service_url:
            raise ValueError("QUEUE_SERVICE_URL environment variable is not set.")

        self._queue_name = os.environ.get("QUEUE_NAME", "csv-processing")
        self._queue_client: QueueClient | None = None

    def _get_queue_client(self) -> QueueClient:
        """Returns a QueueClient."""
        if self._queue_client:
            return self._queue_client

        # Check for Local Dev / Azurite
        if self._queue_service_url.startswith("http://"):  # type: ignore
            # Azurite well-known credentials
            self._queue_client = QueueClient(
                account_url=self._queue_service_url,  # type: ignore
                queue_name=self._queue_name,
                credential=AZURE_DEV_ACCOUNT_KEY,
            )
        else:
            # Production
            self._queue_client = QueueClient(
                account_url=self._queue_service_url,  # type: ignore
                queue_name=self._queue_name,
                credential=DefaultAzureCredential(),
            )
        return self._queue_client

    def enqueue_message(self, message: dict[str, Any]) -> None:
        """
        Enqueues a message to the processing queue.
        Message is JSON encoded and Base64 encoded (standard for Azure Functions Queue Trigger).
        """
        client = self._get_queue_client()

        try:
            client.create_queue()
        except ResourceExistsError:
            # Queue already exists, ignore
            pass
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("Could not create queue: %s", e)

        # Azure Functions usually expects base64 encoded string if not using binding native types,
        # but the python SDK handles generic text. Let's send plain JSON string;
        # the QueueTrigger will receive it.
        message_str = json.dumps(message)

        # Base64 encoding is standard for Azure Functions Queue Trigger
        message_bytes = message_str.encode("utf-8")
        message_b64 = base64.b64encode(message_bytes).decode("utf-8")

        client.send_message(message_b64)
