"""
Queue Storage utilities for async processing.
"""

import base64
import json
import logging
import os
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.storage.queue import QueueClient

__all__ = ["enqueue_message"]

logger = logging.getLogger(__name__)

STORAGE_ACCOUNT_URL = os.environ.get("STORAGE_ACCOUNT_URL")
QUEUE_NAME = "csv-processing"


def _get_queue_client() -> QueueClient:
    """Returns a QueueClient."""
    credential = DefaultAzureCredential()

    # 1. Prefer explicit Queue Service URL (Local Dev / Azurite)
    queue_service_url = os.environ.get("QUEUE_SERVICE_URL")

    if queue_service_url:
        if queue_service_url.startswith("http://"):
            # Azurite well-known credentials
            return QueueClient(
                account_url=queue_service_url,
                queue_name=QUEUE_NAME,
                credential="Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==",
            )
        return QueueClient(
            account_url=queue_service_url, queue_name=QUEUE_NAME, credential=credential
        )

    # 2. Fallback to constructing from Blob URL (Production)
    if not STORAGE_ACCOUNT_URL:
        raise ValueError("STORAGE_ACCOUNT_URL environment variable is not set.")

    # Construct the queue endpoint URL safely
    queue_endpoint = STORAGE_ACCOUNT_URL.replace(".blob.", ".queue.")

    return QueueClient(
        account_url=queue_endpoint, queue_name=QUEUE_NAME, credential=credential
    )


def enqueue_message(message: dict[str, Any]) -> None:
    """
    Enqueues a message to the processing queue.
    Message is JSON encoded and Base64 encoded (standard for Azure Functions Queue Trigger).
    """
    client = _get_queue_client()

    try:
        client.create_queue()
    except Exception as e:
        # Ignore if queue already exists
        if "QueueAlreadyExists" not in str(e):
            logger.warning("Could not create queue (might exist): %s", e)

    # Azure Functions usually expects base64 encoded string if not using binding native types,
    # but the python SDK handles generic text. Let's send plain JSON string;
    # the QueueTrigger will receive it.
    message_str = json.dumps(message)

    # Base64 encoding is standard for Azure Functions Queue Trigger
    message_bytes = message_str.encode("utf-8")
    message_b64 = base64.b64encode(message_bytes).decode("utf-8")

    client.send_message(message_b64)
