"""
Blob Storage utilities for uploading CSVs.
"""

import logging
import os

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

__all__ = ["upload_csv", "download_csv"]

logger = logging.getLogger(__name__)

STORAGE_ACCOUNT_URL = os.environ.get("STORAGE_ACCOUNT_URL")
CONTAINER_NAME = "csv-uploads"


def _get_blob_service_client() -> BlobServiceClient:
    """Returns a BlobServiceClient."""
    credential = DefaultAzureCredential()

    # 1. Prefer explicit Blob Service URL (Local Dev / Azurite)
    blob_service_url = os.environ.get("BLOB_SERVICE_URL")

    if blob_service_url:
        if blob_service_url.startswith("http://"):
            # Azurite well-known credentials
            return BlobServiceClient(
                account_url=blob_service_url,
                credential="Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==",
            )
        return BlobServiceClient(account_url=blob_service_url, credential=credential)

    # 2. Fallback to STORAGE_ACCOUNT_URL (Production)
    if not STORAGE_ACCOUNT_URL:
        raise ValueError("STORAGE_ACCOUNT_URL environment variable is not set.")

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
