"""Service for interacting with Azure Blob Storage."""

import logging
import os
from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContainerClient
from .constants import AZURE_DEV_ACCOUNT_KEY

logger = logging.getLogger(__name__)


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
