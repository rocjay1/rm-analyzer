"""Service for interacting with Azure Queue Storage."""

import base64
import json
import logging
import os
from typing import Any
from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.storage.queue import QueueClient
from .constants import AZURE_DEV_ACCOUNT_KEY

logger = logging.getLogger(__name__)


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
