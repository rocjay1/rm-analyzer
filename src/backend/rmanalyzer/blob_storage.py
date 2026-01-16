"""
Blob Storage utilities for uploading CSVs.
"""

import logging
import os

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)

STORAGE_ACCOUNT_URL = os.environ.get("STORAGE_ACCOUNT_URL")
CONTAINER_NAME = "csv-uploads"


def _get_blob_service_client() -> BlobServiceClient:
    """Returns a BlobServiceClient."""
    if not STORAGE_ACCOUNT_URL:
        raise ValueError("STORAGE_ACCOUNT_URL environment variable is not set.")

    credential = DefaultAzureCredential()
    return BlobServiceClient(account_url=STORAGE_ACCOUNT_URL, credential=credential)


def upload_csv(file_name: str, content: bytes) -> str:
    """
    Uploads CSV content to the blob container.
    Returns the URL of the uploaded blob.
    """
    client = _get_blob_service_client()
    container_client = client.get_container_client(CONTAINER_NAME)

    # Ensure container exists (idempotent usually, or pre-created by terraform)
    if not container_client.exists():
        try:
            container_client.create_container()
        except Exception as e:
            logger.warning("Could not create container (might exist): %s", e)

    blob_client = container_client.get_blob_client(file_name)
    blob_client.upload_blob(content, overwrite=True)

    return blob_client.url


def download_csv(file_name: str) -> str:
    """
    Downloads CSV content from the blob container as a string.
    """
    client = _get_blob_service_client()
    container_client = client.get_container_client(CONTAINER_NAME)
    blob_client = container_client.get_blob_client(file_name)

    download_stream = blob_client.download_blob()
    return download_stream.readall().decode("utf-8")
