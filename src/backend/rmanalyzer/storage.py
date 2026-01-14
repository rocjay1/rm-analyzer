"""
Storage helper for saving/loading data from Azure Blob Storage.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)

# Environment variable set by our infrastructure, e.g. "https://<account>.blob.core.windows.net/"
STORAGE_ACCOUNT_URL = os.environ.get("RM_ANALYZER_STORAGE_ACCOUNT_URL")
CONTAINER_NAME = "savings-data"
BLOB_NAME = "savings.json"


def _get_blob_client():
    """Returns a BlobClient for the savings file, creating container if needed."""
    if not STORAGE_ACCOUNT_URL:
        raise ValueError("RM_ANALYZER_STORAGE_ACCOUNT_URL environment variable is not set.")

    # Use Managed Identity credential
    credential = DefaultAzureCredential()
    
    blob_service_client = BlobServiceClient(account_url=STORAGE_ACCOUNT_URL, credential=credential)
    
    # Ensure container exists
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)
    if not container_client.exists():
        try:
            container_client.create_container()
        except Exception as e:
            # Handle race condition where container might be created by another process
            logger.warning(f"Could not create container (might already exist): {e}")

    return container_client.get_blob_client(BLOB_NAME)


def load_savings_data() -> Dict[str, Any]:
    """Loads savings data from blob storage. Returns empty structure if not found."""
    default_data = {
        "startingBalance": 0,
        "items": []
    }

    try:
        blob = _get_blob_client()
        if not blob.exists():
            return default_data
        
        download_stream = blob.download_blob()
        content = download_stream.readall()
        return json.loads(content)
    except Exception as e:
        logger.error(f"Error loading savings data: {e}")
        # Return default data on error to allow page to load
        return default_data


def save_savings_data(data: Dict[str, Any]) -> None:
    """Saves savings data to blob storage."""
    try:
        blob = _get_blob_client()
        content = json.dumps(data, indent=2)
        blob.upload_blob(content, overwrite=True)
    except Exception as e:
        logger.error(f"Error saving savings data: {e}")
        raise
