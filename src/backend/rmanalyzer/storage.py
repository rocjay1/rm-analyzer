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

__all__ = [
    "upload_csv",
    "download_csv",
    "enqueue_message",
    "QUEUE_NAME",
    "BLOB_CONTAINER_NAME",
]

logger = logging.getLogger(__name__)

BLOB_CONTAINER_NAME = "csv-uploads"
QUEUE_NAME = "csv-processing"


def _get_blob_service_client() -> BlobServiceClient:
    """Returns a BlobServiceClient."""
    # 1. Get Blob Service URL
    blob_service_url = os.environ.get("BLOB_SERVICE_URL")

    if not blob_service_url:
        raise ValueError("BLOB_SERVICE_URL environment variable is not set.")

    # 2. Check for Local Dev / Azurite
    if blob_service_url.startswith("http://"):
        # Azurite well-known credentials
        return BlobServiceClient(
            account_url=blob_service_url,
            credential="Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==",
        )

    # 3. Production
    return BlobServiceClient(
        account_url=blob_service_url, credential=DefaultAzureCredential()
    )


def _get_queue_client() -> QueueClient:
    """Returns a QueueClient."""
    # 1. Get Queue Service URL
    queue_service_url = os.environ.get("QUEUE_SERVICE_URL")

    if not queue_service_url:
        raise ValueError("QUEUE_SERVICE_URL environment variable is not set.")

    # 2. Check for Local Dev / Azurite
    if queue_service_url.startswith("http://"):
        # Azurite well-known credentials
        return QueueClient(
            account_url=queue_service_url,
            queue_name=QUEUE_NAME,
            credential="Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==",
        )

    # 3. Production
    return QueueClient(
        account_url=queue_service_url,
        queue_name=QUEUE_NAME,
        credential=DefaultAzureCredential(),
    )


def upload_csv(file_name: str, content: bytes) -> str:
    """
    Uploads CSV content to the blob container.
    Returns the URL of the uploaded blob.
    """
    client = _get_blob_service_client()
    container_client = client.get_container_client(BLOB_CONTAINER_NAME)

    # Ensure container exists (idempotent usually, or pre-created by terraform)
    if not container_client.exists():
        try:
            container_client.create_container()
        except ResourceExistsError:
            pass  # Container already exists
        except Exception as e:
            logger.warning("Could not create container: %s", e)

    blob_client = container_client.get_blob_client(file_name)
    blob_client.upload_blob(content, overwrite=True)

    return blob_client.url


def download_csv(file_name: str) -> str:
    """
    Downloads CSV content from the blob container as a string.
    """
    client = _get_blob_service_client()
    container_client = client.get_container_client(BLOB_CONTAINER_NAME)
    blob_client = container_client.get_blob_client(file_name)

    download_stream = blob_client.download_blob()
    return download_stream.readall().decode("utf-8")


def enqueue_message(message: dict[str, Any]) -> None:
    """
    Enqueues a message to the processing queue.
    Message is JSON encoded and Base64 encoded (standard for Azure Functions Queue Trigger).
    """
    client = _get_queue_client()

    try:
        client.create_queue()
    except ResourceExistsError:
        # Queue already exists, ignore
        pass
    except Exception as e:
        logger.warning("Could not create queue: %s", e)

    # Azure Functions usually expects base64 encoded string if not using binding native types,
    # but the python SDK handles generic text. Let's send plain JSON string;
    # the QueueTrigger will receive it.
    message_str = json.dumps(message)

    # Base64 encoding is standard for Azure Functions Queue Trigger
    message_bytes = message_str.encode("utf-8")
    message_b64 = base64.b64encode(message_bytes).decode("utf-8")

    client.send_message(message_b64)
